#!/usr/bin/env python3
"""Command-line entry point for independent P7 raw-trace scoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from live.b7_production_equivalence import _write_json  # noqa: E402
from live.b7_production_equivalence_gates import load_and_score  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cleanup", type=Path)
    parser.add_argument("--recomputation-match", choices=("true", "false"))
    parser.add_argument("--score-digest")
    arguments = parser.parse_args()
    result = load_and_score(
        arguments.raw,
        cleanup_path=arguments.cleanup,
        recomputation_match=(
            None
            if arguments.recomputation_match is None
            else arguments.recomputation_match == "true"
        ),
        score_digest=arguments.score_digest,
    )
    _write_json(arguments.out, result)
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "raw_trace_digest": result["raw_trace_digest"],
                "canonical_result_digest": result["canonical_result_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
