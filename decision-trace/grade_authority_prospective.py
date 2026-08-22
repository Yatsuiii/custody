"""Mechanically grade the frozen prospective authority outputs.

This is the only prospective module allowed to join public histories, raw runs,
and hidden adjudication.  It makes no model calls and never edits frozen input.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "prospective"
RUNS = ROOT / "data" / "runs_authority_prospective"
CONDITIONS = ("decisiontrace", "rag_embedding", "rag_full_context")
AUTHORITATIVE_STATUSES = {"FINAL", "ACCEPTED", "ACTIVE", "MERGED", "REVERT_MERGED"}
PROPOSED_STATUSES = {"DRAFT", "OPEN", "NOTE"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def wilson(successes: int, total: int, z: float = 1.96) -> list[float]:
    if not total:
        return [0.0, 0.0]
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half = z / denominator * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return [max(0.0, center - half), min(1.0, center + half)]


def rate(successes: int, total: int, *, interval: bool = True) -> dict:
    result = {
        "numerator": successes,
        "denominator": total,
        "rate": successes / total if total else 0.0,
    }
    if interval:
        result["wilson95"] = wilson(successes, total)
    return result


def load() -> tuple[list[dict], list[dict], dict[str, dict]]:
    timelines = json.loads((DATA / "timelines.json").read_text())
    checkpoints = read_jsonl(DATA / "checkpoints.jsonl")
    truth = {item["checkpoint_id"]: item for item in read_jsonl(DATA / "ground_truth.jsonl")}
    return timelines, checkpoints, truth


def _visible(timeline: dict, checkpoint: dict) -> list[dict]:
    return [item for item in timeline["artifacts"]
            if item["sequence"] <= checkpoint["visible_through"]]


def _failure_classes(gt: dict, state: str, predicted_ids: set[str],
                     evidence_correct: bool, authority_correct: bool,
                     proposed_ids: set[str], stale_ids: set[str],
                     latest_decision_id: str) -> list[str]:
    classes = []
    applicable = set(gt["applicable_failures"])
    expected = set(gt["expected_decision_ids"])
    positive = bool(predicted_ids) or state in {"GOVERNING", "MULTIPLE_GOVERNING"}
    if not authority_correct:
        if predicted_ids & stale_ids:
            classes.append("STALE_DECISION")
        if predicted_ids & proposed_ids:
            classes.append("PROPOSAL_PROMOTED")
        if "REVERT_MISSED" in applicable:
            classes.append("REVERT_MISSED")
        if "SUPERSESSION_MISSED" in applicable:
            classes.append("SUPERSESSION_MISSED")
        if "PARALLEL_DECISION_COLLAPSE" in applicable:
            classes.append("PARALLEL_DECISION_COLLAPSE")
        if positive and (gt["expected_state"] in {"UNRESOLVED", "NO_GOVERNING_DECISION"}
                         or not predicted_ids <= expected):
            classes.append("UNSUPPORTED_AUTHORITY")
        if latest_decision_id in predicted_ids and latest_decision_id not in expected:
            classes.append("RECENCY_CONFUSION")
        if not expected <= predicted_ids or state != gt["expected_state"]:
            classes.append("MISSING_CORRECT_DECISION")
    if not evidence_correct:
        classes.append("EVIDENCE_ERROR")
    return list(dict.fromkeys(classes))


PRIMARY_PRIORITY = (
    "PROPOSAL_PROMOTED", "STALE_DECISION", "REVERT_MISSED",
    "SUPERSESSION_MISSED", "PARALLEL_DECISION_COLLAPSE",
    "UNSUPPORTED_AUTHORITY", "MISSING_CORRECT_DECISION", "EVIDENCE_ERROR",
    "RECENCY_CONFUSION",
)


def _primary_failure(classes: list[str]) -> str | None:
    return next((item for item in PRIMARY_PRIORITY if item in classes), None)


def grade_condition(condition: str, timelines: list[dict], checkpoints: list[dict],
                    truth: dict[str, dict]) -> list[dict]:
    by_timeline = {item["timeline_id"]: item for item in timelines}
    rows = []
    for cp in checkpoints:
        gt = truth[cp["checkpoint_id"]]
        timeline = by_timeline[cp["timeline_id"]]
        visible = _visible(timeline, cp)
        run = json.loads((RUNS / condition / f"{cp['checkpoint_id']}.json").read_text())
        prediction = run["prediction"]
        state = prediction.get("authority_state", "MALFORMED")
        predicted_ids = set(prediction.get("governing_decision_ids", []))
        predicted_evidence = set(prediction.get("evidence_artifact_ids", []))
        expected_ids = set(gt["expected_decision_ids"])
        visible_artifact_ids = {item["artifact_id"] for item in visible}
        evidence_by_decision: dict[str, set[str]] = defaultdict(set)
        for artifact in visible:
            evidence_by_decision[artifact["decision_id"]].add(artifact["artifact_id"])
        acceptable = [set(group) for group in gt["acceptable_evidence_sets"]]
        sufficient = any(group <= predicted_evidence for group in acceptable)
        known_evidence = predicted_evidence <= visible_artifact_ids
        supports_assertions = all(
            bool(evidence_by_decision[decision_id] & predicted_evidence)
            for decision_id in predicted_ids
        )
        evidence_correct = sufficient and known_evidence and supports_assertions
        authority_correct = state == gt["expected_state"] and predicted_ids == expected_ids
        latest_status = {}
        for artifact in visible:
            latest_status[artifact["decision_id"]] = artifact["status"]
        proposed_ids = {key for key, value in latest_status.items() if value in PROPOSED_STATUSES}
        stale_ids = {
            target for artifact in visible
            if artifact["status"] in AUTHORITATIVE_STATUSES
            for target in artifact.get("replaces", [])
        }
        latest_decision_id = visible[-1]["decision_id"]
        classes = _failure_classes(
            gt, state, predicted_ids, evidence_correct, authority_correct,
            proposed_ids, stale_ids, latest_decision_id,
        )
        positive = bool(predicted_ids) or state in {"GOVERNING", "MULTIPLE_GOVERNING"}
        false_authority = positive and (
            gt["expected_state"] in {"UNRESOLVED", "NO_GOVERNING_DECISION"}
            or not predicted_ids <= expected_ids
        )
        rows.append({
            "checkpoint_id": cp["checkpoint_id"],
            "timeline_id": cp["timeline_id"],
            "ecosystem": timeline["ecosystem"],
            "repositories": timeline["repositories"],
            "composition": timeline["composition"],
            "scenario_types": gt["scenario_types"],
            "applicable_failures": gt["applicable_failures"],
            "expected_state": gt["expected_state"],
            "expected_decision_ids": sorted(expected_ids),
            "predicted_state": state,
            "predicted_decision_ids": sorted(predicted_ids),
            "predicted_evidence_artifact_ids": sorted(predicted_evidence),
            "authority_correct": authority_correct,
            "evidence_correct": evidence_correct,
            "combined_correct": authority_correct and evidence_correct,
            "false_authority": false_authority,
            "failure_classes": classes,
            "primary_failure": _primary_failure(classes),
            "parse_error": prediction.get("parse_error"),
        })
    return rows


def metric(rows: list[dict], field: str) -> dict:
    return rate(sum(bool(row[field]) for row in rows), len(rows))


def incidence(rows: list[dict], failure: str) -> dict:
    return rate(sum(failure in row["failure_classes"] for row in rows), len(rows))


def applicable_error(rows: list[dict], label: str) -> dict:
    eligible = [row for row in rows if label in row["applicable_failures"]]
    return rate(sum(not row["authority_correct"] for row in eligible), len(eligible))


def applicable_incidence(rows: list[dict], label: str) -> dict:
    eligible = [row for row in rows if label in row["applicable_failures"]]
    return rate(sum(label in row["failure_classes"] for row in eligible), len(eligible))


def unsupported_applicable_error(rows: list[dict]) -> dict:
    eligible = [row for row in rows if "UNSUPPORTED_AUTHORITY" in row["applicable_failures"]]
    return rate(sum("UNSUPPORTED_AUTHORITY" in row["failure_classes"] for row in eligible),
                len(eligible))


def consistency(rows: list[dict], checkpoints: list[dict]) -> dict:
    cp_by_id = {item["checkpoint_id"]: item for item in checkpoints}
    groups: dict[str, list[tuple[str, tuple[str, ...]]]] = defaultdict(list)
    for row in rows:
        group = cp_by_id[row["checkpoint_id"]].get("consistency_group")
        if group:
            groups[group].append((row["predicted_state"], tuple(row["predicted_decision_ids"])))
    tested = [values for values in groups.values() if len(values) > 1]
    return rate(sum(len(set(values)) == 1 for values in tested), len(tested), interval=False)


def unresolved_calibration(rows: list[dict]) -> dict:
    actual = [row for row in rows if row["expected_state"] == "UNRESOLVED"]
    predicted = [row for row in rows if row["predicted_state"] == "UNRESOLVED"]
    true_positive = sum(row["expected_state"] == "UNRESOLVED" for row in predicted)
    return {
        "exact_accuracy": rate(sum(row["authority_correct"] for row in actual), len(actual)),
        "abstention_recall": rate(true_positive, len(actual)),
        "abstention_precision": rate(true_positive, len(predicted)),
    }


def summarize(rows: list[dict], checkpoints: list[dict]) -> dict:
    return {
        "governing_accuracy": metric(rows, "authority_correct"),
        "evidence_correctness": metric(rows, "evidence_correct"),
        "combined_accuracy": metric(rows, "combined_correct"),
        "false_authority_rate": metric(rows, "false_authority"),
        "stale_decision_rate": incidence(rows, "STALE_DECISION"),
        "proposal_promoted_rate": applicable_incidence(rows, "PROPOSAL_PROMOTED"),
        "revert_miss_rate": applicable_error(rows, "REVERT_MISSED"),
        "supersession_miss_rate": applicable_error(rows, "SUPERSESSION_MISSED"),
        "parallel_collapse_rate": applicable_error(rows, "PARALLEL_DECISION_COLLAPSE"),
        "unsupported_authority_rate": incidence(rows, "UNSUPPORTED_AUTHORITY"),
        "unsupported_authority_eligible_rate": unsupported_applicable_error(rows),
        "unresolved_calibration": unresolved_calibration(rows),
        "consistency": consistency(rows, checkpoints),
        "parse_failures": rate(sum(bool(row["parse_error"]) for row in rows), len(rows)),
        "primary_failure_counts": dict(sorted(Counter(
            row["primary_failure"] for row in rows if row["primary_failure"]
        ).items())),
        "overlapping_failure_counts": dict(sorted(Counter(
            failure for row in rows for failure in row["failure_classes"]
        ).items())),
    }


def bucket_accuracy(rows: list[dict], key: str) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        values = row[key] if isinstance(row[key], list) else [row[key]]
        for value in values:
            buckets[value].append(row)
    return {
        name: rate(sum(row["authority_correct"] for row in group), len(group))
        for name, group in sorted(buckets.items())
    }


def paired_bootstrap(dt_rows: list[dict], rag_rows: list[dict],
                     samples: int = 100_000, seed: int = 20260822) -> dict:
    timeline_ids = sorted({row["timeline_id"] for row in dt_rows})
    dt_by = {timeline: [row for row in dt_rows if row["timeline_id"] == timeline]
             for timeline in timeline_ids}
    rag_by = {timeline: [row for row in rag_rows if row["timeline_id"] == timeline]
              for timeline in timeline_ids}
    dt_success = np.array([sum(row["authority_correct"] for row in dt_by[item])
                           for item in timeline_ids])
    rag_success = np.array([sum(row["authority_correct"] for row in rag_by[item])
                            for item in timeline_ids])
    totals = np.array([len(dt_by[item]) for item in timeline_ids])
    rng = np.random.default_rng(seed)
    chosen = rng.integers(0, len(timeline_ids), size=(samples, len(timeline_ids)))
    denominators = totals[chosen].sum(axis=1)
    differences = ((dt_success[chosen].sum(axis=1) - rag_success[chosen].sum(axis=1))
                   / denominators)
    observed = (sum(row["authority_correct"] for row in dt_rows) / len(dt_rows)
                - sum(row["authority_correct"] for row in rag_rows) / len(rag_rows))
    return {
        "dt_minus_rag": observed,
        "ci90": [float(item) for item in np.quantile(differences, [0.05, 0.95])],
        "samples": samples,
        "seed": seed,
        "unit": "timeline cluster; checkpoint-weighted within resample",
    }


def dt_forensic(row: dict) -> str | None:
    if row["authority_correct"] and not row["evidence_correct"]:
        return "evidence_binding"
    if row["authority_correct"] and row["evidence_correct"]:
        return None
    scenarios = set(row["scenario_types"])
    if "conflicting_or_ambiguous" in scenarios or "partial_supersession" in scenarios:
        return "lifecycle_representation"
    if "parallel_scopes" in scenarios:
        return "scope_resolution"
    if "implementation_vs_policy" in scenarios:
        return "role_resolution"
    if "proposal_while_current" in scenarios:
        return "status_resolution"
    return "deterministic_authority_resolver"


def rag_forensic(row: dict, condition: str) -> str | None:
    if row["authority_correct"] and row["evidence_correct"]:
        return None
    classes = set(row["failure_classes"])
    if row["authority_correct"] and "EVIDENCE_ERROR" in classes:
        return "evidence_mistake"
    mapping = (
        ("STALE_DECISION", "stale_artifact_preferred"),
        ("PROPOSAL_PROMOTED", "proposal_promoted"),
        ("REVERT_MISSED", "revert_missed"),
        ("SUPERSESSION_MISSED", "supersession_missed"),
        ("PARALLEL_DECISION_COLLAPSE", "parallel_collapse"),
        ("RECENCY_CONFUSION", "recency_confusion"),
    )
    for failure, mechanism in mapping:
        if failure in classes:
            return mechanism
    if condition == "rag_embedding":
        prepared = json.loads((DATA / "prepared" / f"{row['checkpoint_id']}.json").read_text())
        retrieved = set(prepared["retrieved_artifact_ids"])
        gt = next(item for item in read_jsonl(DATA / "ground_truth.jsonl")
                  if item["checkpoint_id"] == row["checkpoint_id"])
        if not any(set(group) <= retrieved for group in gt["acceptable_evidence_sets"]):
            return "retrieval_miss"
    return "generation_reasoning_failure"


def choose_comparator(summaries: dict) -> str:
    embedding = summaries["rag_embedding"]
    full = summaries["rag_full_context"]
    e_acc = embedding["governing_accuracy"]["rate"]
    f_acc = full["governing_accuracy"]["rate"]
    if e_acc != f_acc:
        return "rag_embedding" if e_acc > f_acc else "rag_full_context"
    e_evidence = embedding["evidence_correctness"]["rate"]
    f_evidence = full["evidence_correctness"]["rate"]
    if e_evidence != f_evidence:
        return "rag_embedding" if e_evidence > f_evidence else "rag_full_context"
    return "rag_full_context"


def gate(summaries: dict, bootstrap: dict, comparator: str) -> dict:
    dt = summaries["decisiontrace"]
    rag = summaries[comparator]
    difference = dt["governing_accuracy"]["rate"] - rag["governing_accuracy"]["rate"]
    false_materially_worse = (
        dt["false_authority_rate"]["rate"] > rag["false_authority_rate"]["rate"] + 0.03
        and dt["false_authority_rate"]["numerator"] >= rag["false_authority_rate"]["numerator"] + 2
    )
    secondary_metrics = (
        "revert_miss_rate", "supersession_miss_rate", "proposal_promoted_rate",
        "parallel_collapse_rate", "unsupported_authority_eligible_rate",
    )
    secondary_wins = [
        name for name in secondary_metrics
        if dt[name]["denominator"] and dt[name]["rate"] < rag[name]["rate"]
    ]
    conditions = {
        "dt_accuracy_at_least_90": dt["governing_accuracy"]["rate"] >= 0.90,
        "dt_lead_at_least_8_points": difference >= 0.08,
        "bootstrap_90ci_strictly_positive": bootstrap["ci90"][0] > 0,
        "dt_evidence_within_3_points": (
            dt["evidence_correctness"]["rate"] >= rag["evidence_correctness"]["rate"] - 0.03
        ),
        "false_authority_not_materially_worse": not false_materially_worse,
        "at_least_two_secondary_wins": len(secondary_wins) >= 2,
    }
    passed = all(conditions.values())
    if passed:
        verdict = "STRONG AUTHORITY ADVANTAGE — USE CLAIM"
    elif difference > 0:
        verdict = "MODEST AUTHORITY ADVANTAGE — KEEP RESEARCHING"
    elif difference == 0:
        verdict = "TIED WITH RAG — PRODUCT VALUE MUST COME FROM WORKFLOW"
    else:
        verdict = "RAG WINS — DO NOT CLAIM AUTHORITY ADVANTAGE"
    return {
        "passed": passed,
        "conditions": conditions,
        "secondary_wins": secondary_wins,
        "difference": difference,
        "verdict": verdict,
    }


def main() -> None:
    timelines, checkpoints, truth = load()
    rows = {
        condition: grade_condition(condition, timelines, checkpoints, truth)
        for condition in CONDITIONS
    }
    summaries = {condition: summarize(rows[condition], checkpoints) for condition in CONDITIONS}
    comparator = choose_comparator(summaries)
    bootstrap = paired_bootstrap(rows["decisiontrace"], rows[comparator])
    gate_result = gate(summaries, bootstrap, comparator)
    for row in rows["decisiontrace"]:
        row["forensic_category"] = dt_forensic(row)
    for condition in ("rag_embedding", "rag_full_context"):
        for row in rows[condition]:
            row["forensic_category"] = rag_forensic(row, condition)
    output = {
        "conditions": summaries,
        "primary_rag_comparator": comparator,
        "paired_timeline_bootstrap": bootstrap,
        "strict_gate": gate_result,
        "breakdowns": {
            condition: {
                "composition": bucket_accuracy(rows[condition], "composition"),
                "ecosystem": bucket_accuracy(rows[condition], "ecosystem"),
                "scenario": bucket_accuracy(rows[condition], "scenario_types"),
                "expected_state": bucket_accuracy(rows[condition], "expected_state"),
            }
            for condition in CONDITIONS
        },
        "forensic_taxonomy": {
            condition: dict(sorted(Counter(
                row["forensic_category"] for row in rows[condition]
                if row["forensic_category"]
            ).items()))
            for condition in CONDITIONS
        },
        "all_rows": rows,
    }
    (DATA / "scores.json").write_text(json.dumps(output, indent=2) + "\n")
    failures = [
        {"condition": condition, **row}
        for condition in CONDITIONS for row in rows[condition]
        if not row["combined_correct"]
    ]
    (DATA / "failures.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in failures)
    )
    headline = {
        "primary_rag_comparator": comparator,
        "accuracy": {condition: summaries[condition]["governing_accuracy"]
                     for condition in CONDITIONS},
        "evidence": {condition: summaries[condition]["evidence_correctness"]
                     for condition in CONDITIONS},
        "paired_timeline_bootstrap": bootstrap,
        "strict_gate": gate_result,
        "forensic_taxonomy": output["forensic_taxonomy"],
        "failure_rows": len(failures),
    }
    print(json.dumps(headline, indent=2))


if __name__ == "__main__":
    main()
