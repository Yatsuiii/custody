"""Freeze the holdout's ground truth, and hash it, before anything is tuned.

This writes `results/holdout-lock.json`: every variant, its declared relations,
and the state the engine computes from them, plus a digest over the whole thing.
It is committed. If the holdout's truth is ever edited after a model has been run
against it, the digest changes and the claim built on it is void.

Running this is offline and touches no model.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import harness  # noqa: E402
from bench.holdout import HOLDOUT  # noqa: E402
from keel.model import digest  # noqa: E402

OUT = ROOT / "results" / "holdout-lock.json"


def main() -> int:
    entries = []
    for variant in HOLDOUT:
        scenario = harness.build(variant)
        entries.append({
            "id": variant.id,
            "intent": variant.intent,
            "notes": variant.notes,
            "program": variant.program,
            "document": variant.document.id,
            "sentences": list(variant.document.sentences),
            "confirmed": variant.confirmed,
            "truth_relations": [
                {"target": r.target, "relation": r.relation,
                 "strength": r.strength, "sentence": r.sentence}
                for r in variant.truth
            ],
            "before": scenario.before.as_dict(),
            "truth_changed": scenario.truth_changed,
            "truth_because": {k: list(v)
                              for k, v in scenario.truth_because.items()},
        })
    payload = {
        "locked_at": datetime.now(UTC).isoformat(),
        "variants": entries,
        "digest": digest(entries),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True),
                   encoding="utf-8")
    changed = sum(1 for e in entries if e["truth_changed"])
    print(f"locked {len(entries)} variants, {len(entries) - changed} of them "
          f"expecting no change at all")
    print(f"digest {payload['digest']}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
