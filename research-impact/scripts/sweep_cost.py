"""How much of the per-assumption sweep was wasted, and what retrieval must beat.

System B's cost is one model call per assumption per document. On a program with
eight assumptions that is cheap; on one with two hundred it is the reason nobody
would run it. The obvious fix is a retrieval stage that proposes candidate
assumptions and only judges those, but retrieval that misses a true relation
destroys the one property this architecture has that the baseline does not:
never silently failing to ask.

So this reads a finished artifact and reports the numbers that decide whether
retrieval is worth building: how many judgments returned nothing, how small a
candidate set could have been while still containing every true target, and what
the call count would have been.

    python3 scripts/sweep_cost.py proof-out/f1-holdout.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: sweep_cost.py <artifact.json>")
        return 1
    artifact = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    truth_targets = {
        item["id"]: {r["target"] for r in item["truth_relations"]}
        for item in artifact["variants"]
    }
    rows = [r for r in artifact["rows"] if r["system"] == "B"]
    if not rows:
        print("no System B rows in this artifact")
        return 1

    judgments = sum(len(r["raw"]) for r in rows)
    answered = sum(
        1 for r in rows for item in r["raw"]
        if item["answer"]["relation"] in ("SUPPORTS", "CONTRADICTS")
    )
    needed = sum(len(truth_targets[r["variant"]]) for r in rows)
    print(f"System B rows: {len(rows)}")
    print(f"judgments made:                 {judgments}")
    print(f"judgments returning a relation: {answered} "
          f"({answered / judgments:.1%})")
    print(f"judgments a perfect retriever would have needed: {needed} "
          f"({needed / judgments:.1%})")
    print(f"calls saved by perfect retrieval: {judgments - needed}")
    print()
    print("A retriever is only allowed to cut a call it can prove is not a "
          "true target. At 100% recall the ceiling above is what it competes "
          "for; below 100% recall it trades away the property the sweep buys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
