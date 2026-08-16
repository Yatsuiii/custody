"""F5: does gemini-3.7-flash already prepare a compliant dbGaP request?

    python3 scripts/f5_probe.py --runs 3
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

from probe import score  # noqa: E402
from probe.gemini import Gemini  # noqa: E402
from probe.operator import prepare  # noqa: E402
from probe.scenarios import SCENARIOS  # noqa: E402

OUT = ROOT / "proof-out" / "f5.json"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default="gemini-3.7-flash")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv[1:])

    client = Gemini(model=args.model)
    jobs = [(s, run) for run in range(1, args.runs + 1) for s in SCENARIOS]
    started = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        packets = list(pool.map(lambda j: prepare(j[0], j[1], client), jobs))
    rows = [p.as_dict() for p in packets]
    totals = score.summarise(rows)
    artifact = {
        "proof_id": uuid.uuid4().hex,
        "started": started.isoformat(),
        "wall_clock_seconds": round(
            (datetime.now(UTC) - started).total_seconds(), 1),
        "runs": args.runs,
        "model": client.describe(),
        "help_given": "The published requirements are in the prompt and the "
                      "blocking-issue codes are a fixed enum the model chooses "
                      "from. Both inflate performance and are disclosed.",
        "results": totals,
        "verdict": score.verdict(totals),
        "packets": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True),
                   encoding="utf-8")
    _print(artifact)
    return 0


def _print(artifact: dict) -> None:
    totals = artifact["results"]
    print(f"{artifact['runs']} runs, {len(SCENARIOS)} scenarios, "
          f"{totals['packets']} packets, {artifact['wall_clock_seconds']}s\n")
    for key in ("trap_catch", "false_alarm_on_clean", "fabrication",
                "completeness", "call_errors"):
        print(f"  {key:<24}{totals[key]}")
    print("\nper scenario:")
    for name, row in totals["per_scenario"].items():
        got = row["caught"] if row["caught"] is not None else row["false_alarm"]
        label = "caught" if row["caught"] is not None else "false alarm"
        print(f"  {name:<26} {row['expected']:<38} {label} {got}")
    call = artifact["verdict"]
    print(f"\nregistered: drop if {call['registered']['drop_if']}")
    print(f"            build if {call['registered']['build_if']}")
    print(f"\nVERDICT: {call['outcome']}  {call['meaning']}")
    print(f"\nwrote {OUT}  proof {artifact['proof_id']}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
