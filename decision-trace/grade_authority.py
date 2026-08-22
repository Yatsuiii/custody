"""Deterministically grade authority outputs and write inspectable summaries."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from authority_benchmark import AUTHORITY_DIR, RUNS_DIR, load_public, read_jsonl

CONDITIONS = ("decisiontrace", "rag", "decisiontrace_intervention")


def wilson(k, n, z=1.96):
    if not n: return [0.0,0.0]
    p=k/n; denom=1+z*z/n
    centre=(p+z*z/(2*n))/denom
    half=z/denom*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return [max(0,centre-half),min(1,centre+half)]


def normalize_id(value, artifact_map):
    return artifact_map.get(value,value) if isinstance(value,str) else None


def primary_failure(gt, pred, proposed_ids, terminal_ids):
    state, expected=gt["expected_state"],gt["expected_decision_id"]
    pstate,pid=pred["authority_state"],pred["governing_decision_id"]
    applicable=set(gt["applicable_failures"])
    if pstate==state and pid==expected: return None
    if pstate=="GOVERNING" and pid in proposed_ids: return "PROPOSAL_PROMOTED"
    if pstate=="GOVERNING" and pid in terminal_ids: return "UNSUPPORTED_AUTHORITY"
    if pstate=="GOVERNING" and state != "GOVERNING": return "UNSUPPORTED_AUTHORITY"
    if "REVERT_MISSED" in applicable and pstate=="GOVERNING": return "REVERT_MISSED"
    if "SUPERSESSION_MISSED" in applicable and pstate=="GOVERNING": return "SUPERSESSION_MISSED"
    if "PARALLEL_DECISION_COLLAPSE" in applicable: return "PARALLEL_DECISION_COLLAPSE"
    if "STALE_DECISION" in applicable and pstate=="GOVERNING": return "STALE_DECISION"
    return "MISSING_CORRECT_DECISION"


def mechanism_for(gt, pred, prepared, failure):
    if failure is None: return None
    if pred["authority_state"] in {"API_ERROR","PARSE_ERROR"}: return "generation"
    expected=gt["expected_decision_id"]
    derivation_ids={d["decision_id"] for d in prepared["derivations"] if d["decision_id"]}
    retrieved={r["decision_id"] for r in prepared["structured"]["retrieved"]}
    if expected:
        if expected not in derivation_ids: return "ingestion/extraction"
        if expected not in retrieved: return "retrieval"
        resolution=prepared["resolver"].get(expected,{})
        if resolution.get("ambiguous") or resolution.get("active_id") != expected:
            return "deterministic resolver"
        return "generation"
    if "parallel_decisions" in gt["scenario_types"]:
        return "lifecycle representation"
    return "generation"


def grade_condition(condition, timelines, checkpoints, truth):
    timeline_map={t["timeline_id"]:t for t in timelines}
    rows=[]
    for checkpoint in checkpoints:
        cid=checkpoint["checkpoint_id"]; gt=truth[cid]
        run=json.loads((RUNS_DIR/condition/f"{cid}.json").read_text())
        pred=dict(run["prediction"])
        visible=[a for a in timeline_map[checkpoint["timeline_id"]]["artifacts"]
                 if a["sequence"]<=checkpoint["visible_through"]]
        amap={a["artifact_id"]:a["decision_id"] for a in visible}
        latest={}
        for artifact in visible: latest[artifact["decision_id"]]=artifact["status"]
        proposed={did for did,status in latest.items() if status in {"DRAFT","OPEN"}}
        terminal={did for did,status in latest.items() if status in {"WITHDRAWN","REJECTED"}}
        pred["governing_decision_id"]=normalize_id(pred.get("governing_decision_id"),amap)
        pred["evidence_ids"]=sorted({normalize_id(x,amap) for x in pred.get("evidence_ids",[]) if normalize_id(x,amap)})
        authority=(pred["authority_state"]==gt["expected_state"] and
                   pred["governing_decision_id"]==gt["expected_decision_id"])
        expected_evidence=set(gt["expected_evidence_ids"])
        evidence=(expected_evidence.issubset(pred["evidence_ids"])
                  if expected_evidence else not pred["evidence_ids"])
        failure=primary_failure(gt,pred,proposed,terminal)
        if authority and not evidence: failure="EVIDENCE_ERROR"
        prepared=json.loads((AUTHORITY_DIR/"prepared"/f"{cid}.json").read_text())
        mechanism=(mechanism_for(gt,pred,prepared,failure)
                   if condition=="decisiontrace" else None)
        rows.append({
            "checkpoint_id":cid,"timeline_id":checkpoint["timeline_id"],
            "repository":timeline_map[checkpoint["timeline_id"]]["repository"],
            "composition":timeline_map[checkpoint["timeline_id"]]["composition"],
            "position":"final" if checkpoint["visible_through"]==max(a["sequence"] for a in timeline_map[checkpoint["timeline_id"]]["artifacts"]) else "intermediate",
            "scenarios":gt["scenario_types"],"applicable":gt["applicable_failures"],
            "expected_state":gt["expected_state"],"expected_id":gt["expected_decision_id"],
            "predicted_state":pred["authority_state"],"predicted_id":pred["governing_decision_id"],
            "predicted_evidence":pred["evidence_ids"],
            "authority_correct":authority,"evidence_correct":evidence,
            "combined_correct":authority and evidence,"failure":failure,
            "mechanism":mechanism,
        })
    return rows


def rate(rows, field):
    k=sum(bool(r[field]) for r in rows); n=len(rows)
    return {"numerator":k,"denominator":n,"rate":k/n if n else 0,"wilson95":wilson(k,n)}


def error_rate(rows, failure, applicable=None):
    base=[r for r in rows if not applicable or applicable in r["applicable"]]
    k=sum(r["failure"]==failure for r in base); n=len(base)
    return {"numerator":k,"denominator":n,"rate":k/n if n else 0,"wilson95":wilson(k,n)}


def summarize(rows):
    false=sum(r["predicted_state"]=="GOVERNING" and not r["authority_correct"] for r in rows)
    stale=sum(r["failure"]=="STALE_DECISION" for r in rows)
    def applicable_miss(label):
        base=[r for r in rows if label in r["applicable"]]
        missed=sum(not r["authority_correct"] for r in base)
        return {"numerator":missed,"denominator":len(base),
                "rate":missed/len(base) if base else 0,
                "wilson95":wilson(missed,len(base))}
    metrics={
        "governing_accuracy":rate(rows,"authority_correct"),
        "evidence_correctness":rate(rows,"evidence_correct"),
        "combined_accuracy":rate(rows,"combined_correct"),
        "stale_decision_rate":{"numerator":stale,"denominator":len(rows),"rate":stale/len(rows),"wilson95":wilson(stale,len(rows))},
        "false_authority_rate":{"numerator":false,"denominator":len(rows),"rate":false/len(rows),"wilson95":wilson(false,len(rows))},
        "proposal_promoted_rate":error_rate(rows,"PROPOSAL_PROMOTED","PROPOSAL_PROMOTED"),
        "revert_miss_rate":applicable_miss("REVERT_MISSED"),
        "supersession_miss_rate":applicable_miss("SUPERSESSION_MISSED"),
        "api_parse_failures":{"numerator":sum(r["predicted_state"] in {"API_ERROR","PARSE_ERROR"} for r in rows),"denominator":len(rows)},
        "failure_counts":dict(Counter(r["failure"] for r in rows if r["failure"])),
    }
    groups=defaultdict(list)
    checkpoints={c["checkpoint_id"]:c for c in read_jsonl(AUTHORITY_DIR/"checkpoints.jsonl")}
    for r in rows:
        group=checkpoints[r["checkpoint_id"]].get("consistency_group")
        if group: groups[group].append((r["predicted_state"],r["predicted_id"]))
    tested=[v for v in groups.values() if len(v)>1]
    consistent=sum(len(set(v))==1 for v in tested)
    metrics["consistency"]={"numerator":consistent,"denominator":len(tested),"rate":consistent/len(tested) if tested else 0}
    return metrics


def breakdown(rows, key):
    buckets=defaultdict(list)
    for row in rows:
        values=row[key] if isinstance(row[key],list) else [row[key]]
        for value in values: buckets[value].append(row)
    return {name:rate(group,"authority_correct") for name,group in sorted(buckets.items())}


def paired_bootstrap(dt, rag, samples=10_000, seed=20260822):
    by_dt=defaultdict(list); by_rag=defaultdict(list)
    for row in dt: by_dt[row["timeline_id"]].append(row)
    for row in rag: by_rag[row["timeline_id"]].append(row)
    tids=sorted(by_dt); rng=np.random.default_rng(seed); diffs=[]; errdiff=[]
    for _ in range(samples):
        chosen=rng.choice(tids,size=len(tids),replace=True)
        drows=[r for tid in chosen for r in by_dt[tid]]
        rrows=[r for tid in chosen for r in by_rag[tid]]
        diffs.append(np.mean([r["authority_correct"] for r in drows])-np.mean([r["authority_correct"] for r in rrows]))
        def bad(rows): return np.mean([r["predicted_state"]=="GOVERNING" and r["expected_state"]!="GOVERNING" or r["failure"] in {"STALE_DECISION","REVERT_MISSED","SUPERSESSION_MISSED"} for r in rows])
        errdiff.append(bad(drows)-bad(rrows))
    return {"accuracy_difference":float(np.mean(diffs)),"accuracy_difference_90ci":[float(x) for x in np.quantile(diffs,[.05,.95])],"stale_false_difference":float(np.mean(errdiff)),"stale_false_difference_90ci":[float(x) for x in np.quantile(errdiff,[.05,.95])]}


def main():
    timelines,checkpoints=load_public(); truth={g["checkpoint_id"]:g for g in read_jsonl(AUTHORITY_DIR/"ground_truth.jsonl")}
    available=[c for c in CONDITIONS if (RUNS_DIR/c).exists()]
    rows={c:grade_condition(c,timelines,checkpoints,truth) for c in available}
    summary={"conditions":{c:summarize(rows[c]) for c in CONDITIONS},
             "breakdown":{c:{"scenario":breakdown(rows[c],"scenarios"),"repository":breakdown(rows[c],"repository"),"composition":breakdown(rows[c],"composition"),"position":breakdown(rows[c],"position")} for c in CONDITIONS},
             "paired_bootstrap":paired_bootstrap(rows["decisiontrace"],rows["rag"]),
             "decisiontrace_mechanisms":dict(Counter(r["mechanism"] for r in rows["decisiontrace"] if r["mechanism"])),
             "all_rows":rows}
    if "decisiontrace_intervention" in rows:
        summary["intervention_paired_bootstrap"]=paired_bootstrap(rows["decisiontrace_intervention"],rows["rag"])
    (AUTHORITY_DIR/"baseline_scores.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="all_rows"},indent=2))


if __name__=="__main__": main()
