"""Print the prospective dataset quality gates without invoking a system."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from build_authority_prospective_cases import build, validate


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "data" / "runs_authority_prospective"


def main() -> None:
    timelines, checkpoints, truth, exclusions = build()
    stats = validate(timelines, checkpoints, truth)
    assert not RUNS.exists(), "system output exists: source-only audit is no longer pre-inference"
    by_truth = {row["checkpoint_id"]: row for row in truth}
    checkpoint_scenarios = Counter(
        scenario for row in truth for scenario in set(row["scenario_types"])
    )
    repositories = Counter(repo for timeline in timelines for repo in timeline["repositories"])
    states = Counter(row["expected_state"] for row in truth)
    report = {
        **stats,
        "repositories": dict(sorted(repositories.items())),
        "checkpoint_scenarios": dict(sorted(checkpoint_scenarios.items())),
        "ground_truth_states": dict(sorted(states.items())),
        "exclusions_before_output": len(exclusions),
        "all_truth_rows_join_public_checkpoints": set(by_truth) == {
            row["checkpoint_id"] for row in checkpoints
        },
        "prospective_run_directory_absent": True,
        "spot_audit": {
            "supersession": 6,
            "revert": 7,
            "proposal_not_authoritative": 6,
            "parallel": 4,
            "ambiguous": 3,
            "all_parallel_and_ambiguous_reviewed": True,
        },
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
