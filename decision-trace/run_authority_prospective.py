"""Generate each frozen prospective condition exactly once."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone

import vertex
from authority_prospective import DATA, PREPARED, RUNS, load_public, parse_rag_response, visible_checkpoint


CONDITIONS = ("decisiontrace", "rag_embedding", "rag_full_context")


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("condition", choices=CONDITIONS)
    args = parser.parse_args()
    output = RUNS / args.condition
    if output.exists() and any(output.glob("*.json")):
        raise SystemExit(f"{args.condition} output exists; selective rerun forbidden")
    timelines, checkpoints = load_public()
    by_timeline = {item["timeline_id"]: item for item in timelines}
    output.mkdir(parents=True, exist_ok=False)
    errors = []
    started = datetime.now(timezone.utc).isoformat()
    for index, cp in enumerate(checkpoints, 1):
        print(f"[{index}/{len(checkpoints)}] {args.condition} {cp['checkpoint_id']}", flush=True)
        prepared = json.loads((PREPARED / f"{cp['checkpoint_id']}.json").read_text())
        prompt = prepared["prompts"][args.condition]
        raw = ""
        error = None
        try:
            raw = vertex.generate(prompt)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            errors.append({"checkpoint_id": cp["checkpoint_id"], "error": error})
        if args.condition == "decisiontrace":
            fixed = prepared["deterministic_prediction"]
            prediction = {
                "authority_state": fixed["authority_state"],
                "governing_decision_ids": fixed["governing_decision_ids"],
                "evidence_artifact_ids": fixed["evidence_artifact_ids"],
                "explanation": raw.strip(),
                "parse_error": error,
            }
        else:
            visible = visible_checkpoint(by_timeline[cp["timeline_id"]], cp)
            prediction = parse_rag_response(raw, visible)
            if error:
                prediction["parse_error"] = error
        row = {
            "checkpoint_id": cp["checkpoint_id"],
            "timeline_id": cp["timeline_id"],
            "condition": args.condition,
            "prompt_sha256": prepared["prompt_sha256"][args.condition],
            "source_artifact_ids": prepared["condition_source_artifact_ids"][args.condition],
            "retrieved_artifact_ids": (prepared["retrieved_artifact_ids"]
                                       if args.condition == "rag_embedding" else None),
            "prediction": prediction,
            "raw_response": raw,
        }
        (output / f"{cp['checkpoint_id']}.json").write_text(json.dumps(row, indent=2) + "\n")
    manifest = {
        "condition": args.condition,
        "git_sha": git_sha(),
        "generation_model": vertex.GEN_MODEL,
        "generation_calls": len(checkpoints),
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
    }
    (RUNS / f"{args.condition}_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
