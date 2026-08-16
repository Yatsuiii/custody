"""F1: does the deterministic layer earn its place, or is the graph decoration?

Runs the configured systems over every variant in a suite, several times, and
writes one artifact carrying the raw model answers as well as the scores, so
`scripts/f1_judge.py` can recompute the comparison from the model's own words.

    python3 scripts/f1_bench.py --mode stub                       # harness only
    python3 scripts/f1_bench.py --mode live --suite dev            # the dev run
    python3 scripts/f1_bench.py --mode live --suite holdout \\
        --configs A:v1,A:v2,B:v1,B:v2                              # the report

A config is a system and an admission boundary. v1 asks the model for a strength
label; v2 asks two narrower factual questions and computes strength from them.
Both stay runnable forever, so the dev numbers remain reproducible and the
boundary change is an ablation rather than an edit.
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

from bench import harness, repair, score, systems, variants  # noqa: E402
from bench.holdout import HOLDOUT  # noqa: E402
from bench.stub import StubModel  # noqa: E402

DEFAULT_PROJECT = "project-988bc9fe-092c-4b32-90c"
SUITES = {"dev": variants.VARIANTS, "holdout": HOLDOUT}
RUNNERS = {"A": systems.run_baseline_a, "B": systems.run_system_b}

CIRCULARITY = (
    "Ground truth is this project's own state policy applied to the relations "
    "each variant declares as true, so the experiment measures whether "
    "unconstrained reasoning reproduces a written rule set that both systems "
    "were given. It does not establish that the rule set is the right one. "
    "Two columns are asymmetric by construction and are reported as such: "
    "System B cannot emit a state outside the vocabulary and cannot cite a "
    "justification other than the engine's, because it does not author either."
)


def _model(mode: str, scenario, project: str, name: str):
    if mode == "stub":
        return StubModel(scenario)
    from bench.gemini import Gemini  # noqa: PLC0415

    return Gemini(project, model=name)


def _one(job: tuple, args) -> list[dict]:
    scenario, run = job
    rows = []
    for system, boundary in args.configs:
        outcome = RUNNERS[system](
            scenario, _model(args.mode, scenario, args.project, args.model),
            boundary,
        )
        row = score.score_outcome(scenario, outcome)
        row["run"] = run
        row["boundary"] = boundary
        row["config"] = f"{system}:{boundary}"
        row["raw"] = outcome.raw
        row["because"] = outcome.because
        row["repair"] = repair.repair_cost(scenario, outcome)
        rows.append(row)
    return rows


def _configs(text: str) -> list[tuple[str, str]]:
    parsed = []
    for item in text.split(","):
        system, _, boundary = item.strip().partition(":")
        if system not in RUNNERS or boundary not in ("v1", "v2"):
            raise ValueError(f"unknown config {item}")
        parsed.append((system, boundary))
    return parsed


def main(argv: list[str]) -> int:
    args = _parse(argv)
    out = (Path(args.out) if args.out
           else ROOT / "proof-out" / f"f1-{args.suite}.json")
    suite = SUITES[args.suite]
    chosen = suite[:args.limit] if args.limit else suite
    scenarios = {v.id: harness.build(v) for v in chosen}
    jobs = [(scenarios[v.id], run)
            for run in range(1, args.runs + 1) for v in chosen]

    started = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: _one(job, args), jobs))
    rows = [row for batch in results for row in batch]
    finished = datetime.now(UTC)

    artifact = {
        "proof_id": uuid.uuid4().hex,
        "mode": args.mode,
        "suite": args.suite,
        "started": started.isoformat(),
        "wall_clock_seconds": round((finished - started).total_seconds(), 1),
        "runs": args.runs,
        "model": _describe(args, scenarios),
        "circularity": CIRCULARITY,
        "systems": {
            "A": "one call: whole graph, whole document, full rule set",
            "B": "one bounded call per assumption, then deterministic propagation",
            "v1": "the model chooses a strength label",
            "v2": "the model answers inference distance and setting transfer, "
                  "and code computes strength from a fixed table",
        },
        "variants": [_variant_record(scenarios[v.id]) for v in chosen],
        "results": _summarise(rows, args.configs),
        "rows": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True),
                   encoding="utf-8")
    _print_table(artifact, out)
    return 0


def _parse(argv: list[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("stub", "live"), default="stub")
    parser.add_argument("--suite", choices=tuple(SUITES), default="dev")
    parser.add_argument("--configs", default="A:v1,B:v1")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv[1:])
    args.configs = _configs(args.configs)
    return args


def _summarise(rows: list[dict], configs: list[tuple[str, str]]) -> dict:
    summary = {}
    for system, boundary in configs:
        key = f"{system}:{boundary}"
        mine = [r for r in rows if r["config"] == key]
        summary[key] = {
            "aggregate": score.aggregate(mine),
            "stability": score.stability(mine),
            "repair": repair.aggregate_repair(mine),
        }
    return summary


def _describe(args, scenarios) -> dict:
    if args.mode == "stub":
        return StubModel(next(iter(scenarios.values()))).describe()
    from bench.gemini import Gemini  # noqa: PLC0415

    return Gemini(args.project, model=args.model).describe()


def _variant_record(scenario) -> dict:
    return {
        "id": scenario.variant.id,
        "intent": scenario.variant.intent,
        "notes": scenario.variant.notes,
        "document": scenario.variant.document.id,
        "truth_relations": [
            {"target": r.target, "relation": r.relation, "strength": r.strength,
             "sentence": r.sentence}
            for r in scenario.variant.truth
        ],
        "before": scenario.before.as_dict(),
        "truth_changed": scenario.truth_changed,
        "truth_because": {k: list(v) for k, v in scenario.truth_because.items()},
    }


AGGREGATE_ROWS = (
    "precision", "recall", "f1", "state_exact_of_hits", "unrelated_preserved",
    "unrelated_disturbed", "provenance_exact", "invalid_transitions",
    "edge_errors", "edge_judgments", "call_failures", "prompt_tokens", "calls",
)
REPAIR_ROWS = ("wrong_nodes", "corrections_required",
               "nodes_repaired_per_correction",
               "residual_wrong_nodes_after_correction")


def _print_table(artifact: dict, out: Path) -> None:
    keys = list(artifact["results"])
    print(f"{artifact['suite']} suite, mode {artifact['mode']}, "
          f"{artifact['runs']} runs, {len(artifact['variants'])} variants, "
          f"{artifact['wall_clock_seconds']}s\n")
    width = 18
    header = "metric".ljust(32) + "".join(k.rjust(width) for k in keys)
    print(header)
    print("-" * len(header))
    for section, rows in (("aggregate", AGGREGATE_ROWS),
                          ("stability", ("identical_rate", "mean_jaccard")),
                          ("repair", REPAIR_ROWS)):
        for key in rows:
            cells = "".join(
                str(artifact["results"][k][section][key]).rjust(width)
                for k in keys
            )
            print(key.ljust(32) + cells)
    print(f"\nwrote {out}  proof {artifact['proof_id']}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
