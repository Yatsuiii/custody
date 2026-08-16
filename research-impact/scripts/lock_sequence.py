"""Freeze the longitudinal sequence: adjudication, trajectory, and a digest.

Refuses to lock unless every document is judged against every assumption, so a
pair cannot be left undeclared by accident. That is the defect the holdout ran
into: an unlabelled pair silently becomes NO_RELATION and then punishes a system
for a defensible reading. Here the third label, AMBIGUOUS, exists precisely so a
debatable pair can be recorded as debatable instead of guessed at.

Also refuses to lock unless the three orders converge, since order convergence
is one of the pre-registered criteria and a benchmark whose orders disagree
would make that criterion meaningless.

Offline. No model is involved.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import sequence, timeline  # noqa: E402
from bench.harness import base_program  # noqa: E402
from keel.model import digest  # noqa: E402

OUT = ROOT / "results" / "sequence-lock.json"


def main() -> int:
    assumptions = [a["id"] for a in base_program(sequence.PROGRAM)["assumptions"]]
    grid, counts = _grid(assumptions)
    trajectories = {name: timeline.truth_trajectory(name)
                    for name in sequence.ORDERS}
    ends = {name: trail[-1].states for name, trail in trajectories.items()}
    if len({json.dumps(state, sort_keys=True) for state in ends.values()}) != 1:
        print("orders do not converge; the benchmark is not lockable")
        return 1

    payload = {
        "locked_at": datetime.now(UTC).isoformat(),
        "program": sequence.PROGRAM,
        "documents": [
            {"id": name, "title": doc.title, "sentences": list(doc.sentences)}
            for name, doc in sorted(sequence.DOCUMENTS.items())
        ],
        "adjudication": grid,
        "label_counts": counts,
        "ambiguous_pairs": [list(pair) for pair in sequence.ambiguous_pairs()],
        "correction": sequence.CORRECTION,
        "orders": {name: list(order)
                   for name, order in sorted(sequence.ORDERS.items())},
        "trajectories": {
            name: [{"step": s.step, "document": s.document, "states": s.states}
                   for s in trail]
            for name, trail in sorted(trajectories.items())
        },
    }
    payload["digest"] = digest(
        {k: v for k, v in payload.items() if k != "locked_at"}
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True),
                   encoding="utf-8")
    print(f"adjudicated {sum(counts.values())} pairs: "
          + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    print(f"orders converge: {len(sequence.ORDERS)} of {len(sequence.ORDERS)}")
    print(f"digest {payload['digest']}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


def _grid(assumptions: list[str]) -> tuple[dict, dict]:
    grid, counts = {}, {}
    for document in sorted(sequence.DOCUMENTS):
        for assumption in assumptions:
            entry = sequence.ADJUDICATION.get((document, assumption))
            label = sequence.NO_RELATION if entry is None else entry[0]
            record = {"label": label}
            if label == sequence.RELATION:
                record |= {"relation": entry[1], "strength": entry[2],
                           "sentence": entry[3]}
            grid[f"{document}x{assumption}"] = record
            counts[label] = counts.get(label, 0) + 1
    return grid, counts


if __name__ == "__main__":
    raise SystemExit(main())
