"""Run the one preregistered authority-resolver intervention exactly once."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import vertex
from authority_benchmark import AUTHORITY_DIR, RUNS_DIR, adapt_decisions, load_public, prompt_hash, visible_checkpoint

sys.path.insert(0,str(Path(__file__).resolve().parent/"app"))
from authority import resolve_authority  # noqa: E402

OUT=RUNS_DIR/"decisiontrace_intervention"


def main():
    if OUT.exists() and any(OUT.glob("*.json")):
        raise SystemExit("intervention outputs already exist; selective rerun forbidden")
    timelines,checkpoints=load_public(); by_t={t["timeline_id"]:t for t in timelines}
    errors=[]
    for i,checkpoint in enumerate(checkpoints,1):
        print(f"[{i}/{len(checkpoints)}] {checkpoint['checkpoint_id']}",flush=True)
        visible=visible_checkpoint(by_t[checkpoint["timeline_id"]],checkpoint)
        decisions,_=adapt_decisions(visible)
        resolution=resolve_authority(decisions,checkpoint["authority_scope"])
        evidence=[]
        for decision in decisions:
            if decision.id in resolution.evidence_ids:
                evidence.extend(f"{decision.id}: {item.url} — {item.quote}" for item in decision.evidence)
        prompt=("You are DecisionTrace's explanation layer. A deterministic authority resolver has already "
                "decided the state below. Do not change, omit, or second-guess it. Explain the result in one "
                "brief sentence grounded only in the evidence. Output only the sentence.\n\n"
                f"State: {resolution.state}\nGoverning decision ID: {resolution.governing_decision_id}\n"
                f"Resolver explanation: {resolution.explanation}\nEvidence:\n"+"\n".join(evidence)+
                f"\n\nDeveloper question: {checkpoint['question']}")
        try:
            explanation=vertex.generate(prompt).strip()
        except Exception as exc:
            errors.append({"checkpoint_id":checkpoint["checkpoint_id"],"error":f"{type(exc).__name__}: {exc}"})
            explanation=""
        out=OUT/f"{checkpoint['checkpoint_id']}.json"; out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({
            "checkpoint_id":checkpoint["checkpoint_id"],"timeline_id":checkpoint["timeline_id"],
            "question":checkpoint["question"],"prompt_sha256":prompt_hash(prompt),
            "visible_history":json.loads((AUTHORITY_DIR/"prepared"/f"{checkpoint['checkpoint_id']}.json").read_text())["visible_history"],
            "prediction":{"authority_state":resolution.state,
                          "governing_decision_id":resolution.governing_decision_id,
                          "evidence_ids":list(resolution.evidence_ids),
                          "resolver_explanation":resolution.explanation,
                          "model_explanation":explanation},
        },indent=2)+"\n")
    manifest={"model":vertex.GEN_MODEL,"generation_calls":len(checkpoints),"errors":errors,
              "intervention":"scope/status/role-aware deterministic authority resolver"}
    (AUTHORITY_DIR/"intervention_run_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__=="__main__":main()
