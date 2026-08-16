"""Write a small, committed summary of a benchmark artifact.

`proof-out/` is not committed, so without this the numbers would live only in
prose. The summary is recomputed from the raw model answers the same way the
judge does it, never copied from the producer's own totals, and it records the
proof id so it can be traced back to the full artifact.

    python3 scripts/summarise_result.py proof-out/f1-dev.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import harness, repair, score  # noqa: E402

import f1_judge  # noqa: E402, isort: skip


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: summarise_result.py <artifact.json> [out.json]")
        return 1
    path = Path(argv[1])
    artifact = json.loads(path.read_text(encoding="utf-8"))
    suite = f1_judge.SUITES[artifact.get("suite", "dev")]
    scenarios = {v.id: harness.build(v) for v in suite}
    rows = f1_judge.judge_rows(f1_judge.Judgement(), artifact, scenarios)

    configs = sorted({row["config"] for row in rows})
    summary = {
        "proof_id": artifact["proof_id"],
        "suite": artifact.get("suite", "dev"),
        "mode": artifact["mode"],
        "model": artifact["model"],
        "runs": artifact["runs"],
        "variants": len(artifact["variants"]),
        "recomputed_by": "scripts/summarise_result.py, from the raw answers",
        "results": {
            key: {
                "aggregate": score.aggregate(
                    [r for r in rows if r["config"] == key]),
                "stability": score.stability(
                    [r for r in rows if r["config"] == key]),
                "repair": repair.aggregate_repair(
                    [r for r in rows if r["config"] == key]),
            }
            for key in configs
        },
    }
    out = Path(argv[2]) if len(argv) > 2 else (
        ROOT / "results" / f"{path.stem}-summary.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True),
                   encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} for proof {artifact['proof_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
