"""F3: ten interacting documents, three systems, one pre-registered verdict.

    python3 scripts/f3_bench.py --mode stub
    python3 scripts/f3_bench.py --mode live --runs 3

A0 recomputes from the current description. A1 maintains a canonical structured
state and is handed it back every step, corrections included. B keeps relations
in an event log and lets the engine compute state. The kill condition is
evaluated by `bench/killcondition.py` from the recorded numbers, not by whoever
reads the table.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import killcondition, seqscore, sequence, timeline  # noqa: E402
from bench.replay import ReplayModel, SequenceStub, answers_for  # noqa: E402

DEFAULT_PROJECT = "project-988bc9fe-092c-4b32-90c"
OUT = ROOT / "proof-out" / "f3-sequence.json"
ALTERNATE_ORDERS = ("swap-early", "swap-late")


def _run(system: str, order: str, model, truth) -> list:
    if system == "B":
        return timeline.run_b(order, model)
    return timeline.run_a(order, model, persistent=(system == "A1"),
                          truth=truth)


def _job(spec: tuple, args, truths) -> dict:
    system, order, run = spec
    model = _model(args, order, spec)
    trail = _run(system, order, model, truths[order])
    row = seqscore.score_trail(trail, truths[order], order)
    row |= {"system": system, "run": run}
    row["trail"] = [
        {"step": s.step, "document": s.document, "states": s.states,
         "because": s.because, "raw": s.raw}
        for s in trail
    ]
    return row


def _model(args, order: str, spec: tuple | None = None):
    if args.mode == "stub":
        return SequenceStub(order)
    if args.mode == "replay":
        return ReplayModel(answers_for(_recorded(args)[spec]))
    from bench.gemini import Gemini  # noqa: PLC0415

    return Gemini(args.project, model=args.model)


def _recorded(args) -> dict:
    """Rows from a finished run, so scoring can be redone without new calls."""
    if not getattr(args, "_rows", None):
        artifact = json.loads(Path(args.source).read_text(encoding="utf-8"))
        args._rows = {(r["system"], r["order"], r["run"]): r
                      for r in artifact["rows"]}
        args._model_note = artifact["model"]
    return args._rows


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("stub", "live", "replay"),
                        default="stub")
    parser.add_argument("--source", default="proof-out/f3-sequence-asrun.json")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv[1:])

    truths = {name: timeline.truth_trajectory(name) for name in sequence.ORDERS}
    specs = [
        (system, "canonical", run)
        for system in ("A0", "A1", "B") for run in range(1, args.runs + 1)
    ] + [
        (system, order, 1)
        for system in ("A0", "A1", "B") for order in ALTERNATE_ORDERS
    ]
    started = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda spec: _job(spec, args, truths), specs))
    finished = datetime.now(UTC)

    results = {
        system: seqscore.aggregate_trails(
            [r for r in rows if r["system"] == system]
        )
        for system in ("A0", "A1", "B")
    }
    artifact = {
        "proof_id": uuid.uuid4().hex,
        "mode": args.mode,
        "started": started.isoformat(),
        "wall_clock_seconds": round((finished - started).total_seconds(), 1),
        "runs": args.runs,
        "model": _describe(args),
        "sequence_digest": json.loads(
            (ROOT / "results" / "sequence-lock.json").read_text(encoding="utf-8")
        )["digest"],
        "systems": {
            "A0": "recomputes from the current program description each step",
            "A1": "maintains a canonical structured state, handed back every "
                  "step, corrections included",
            "B": "bounded judgments into an event log, engine computes state",
        },
        "results": results,
        "kill_condition": killcondition.evaluate(results["A1"], results["B"]),
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True),
                   encoding="utf-8")
    _print(artifact)
    return 0


def _describe(args) -> dict:
    if args.mode == "replay":
        _recorded(args)
        return dict(args._model_note,
                    note="rescored from recorded answers, no new calls")
    if args.mode == "stub":
        return {"model": "stub", "api": "recorded, no network"}
    from bench.gemini import Gemini  # noqa: PLC0415

    return Gemini(args.project, model=args.model).describe()


SHOWN = ("mean_end_accuracy", "mean_step_accuracy", "steps_exactly_right",
         "steps_total", "mean_correction_persistence", "regressions",
         "unnecessary_changes", "wrong_node_steps", "longest_error_survival",
         "orders_agreeing", "distinct_end_states", "auditable_justifications",
         "prompt_tokens", "calls", "seconds")


def _print(artifact: dict) -> None:
    print(f"mode {artifact['mode']}, {artifact['runs']} runs of the canonical "
          f"order plus two alternates, {artifact['wall_clock_seconds']}s\n")
    keys = ("A0", "A1", "B")
    header = "metric".ljust(32) + "".join(k.rjust(16) for k in keys)
    print(header)
    print("-" * len(header))
    for key in SHOWN:
        print(key.ljust(32)
              + "".join(str(artifact["results"][k][key]).rjust(16)
                        for k in keys))
    verdict = artifact["kill_condition"]
    print(f"\npre-registered criteria met: {verdict['criteria_met']} of "
          f"{verdict['criteria_needed']} needed")
    for item in verdict["criteria"]:
        mark = "MET " if item["met"] else "not "
        print(f"  {mark} {item['name']:<24} A1 {item['a1']}  B {item['b']}"
              f"   ({item['requires']})")
    if verdict["hard_override_triggered"]:
        print("  hard override triggered: " + verdict["hard_override"])
    print(f"\nVERDICT: {verdict['verdict']}")
    print(f"wrote {OUT}  proof {artifact['proof_id']}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
