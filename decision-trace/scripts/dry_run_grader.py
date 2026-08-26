#!/usr/bin/env python3
"""Condition-blind dummy grader used only by the orchestration dry-run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    # Deliberately do not accept or inspect an arm/condition field.  This is a
    # schema smoke test, not a task grader and never runs during the experiment.
    result = {
        "run_id": payload["run_id"],
        "TASK_COMPLETED": True,
        "TESTS_PASS": True,
        "AUTHORITY_COMPLIANT": True,
        "violation_category": None,
    }
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
