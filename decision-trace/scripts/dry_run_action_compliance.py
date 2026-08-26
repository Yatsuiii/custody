#!/usr/bin/env python3
"""Repeat the blind action-compliance orchestration dry run without a model."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_action_compliance_codex import PLAN_SEED, run_no_model_dry_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contexts_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=PLAN_SEED)
    args = parser.parse_args()
    run_no_model_dry_run(
        contexts_root=args.contexts_root,
        output_root=args.output_dir,
        repetitions=args.repetitions,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
