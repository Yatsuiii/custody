"""The G5 elapsed-time artifact is re-judged from bounded raw evidence."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.scheduler_gates import CLAIM_BOUNDARY, judge_offline

NOW = datetime(2026, 8, 31, 14, 0, tzinfo=UTC)


def valid_evidence() -> dict:
    return {
        "schema_version": 1,
        "captured_at": (NOW - timedelta(minutes=1)).isoformat(),
        "project": "project-123",
        "region": "us-central1",
        "service": "custody-control-plane",
        "job": "custody-g5-auditor",
        "claim_boundary": CLAIM_BOUNDARY,
        "scheduler": {
            "state": "ENABLED",
            "schedule": "0 6 * * *",
            "last_attempt_time": (NOW - timedelta(hours=8)).isoformat(),
        },
        "auditor": {
            "day": NOW.date().isoformat(),
            "elapsed_days_since_seed": 17,
            "first_run": False,
        },
        "seed": {
            "id": "g5-elapsed-time-seed",
            "revocation_id": None,
        },
    }


class SchedulerEvidenceTests(unittest.TestCase):
    def test_complete_evidence_passes_every_gate(self):
        self.assertTrue(all(judge_offline(valid_evidence(), now=NOW).values()))

    def test_stale_capture_cannot_stand_in_for_a_current_scheduler_check(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["captured_at"] = (NOW - timedelta(hours=25)).isoformat()
        self.assertFalse(judge_offline(evidence, now=NOW)["fresh_live_evidence"])

    def test_old_scheduler_fire_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["scheduler"]["last_attempt_time"] = (
            NOW - timedelta(hours=26)
        ).isoformat()
        gates = judge_offline(evidence, now=NOW)
        self.assertFalse(
            gates["scheduler_last_natural_fire_within_25_hours_of_capture"]
        )

    def test_fast_forwarded_or_first_run_elapsed_time_cannot_pass(self):
        for elapsed, first_run in ((0, False), (17, True), (True, False)):
            evidence = copy.deepcopy(valid_evidence())
            evidence["auditor"]["elapsed_days_since_seed"] = elapsed
            evidence["auditor"]["first_run"] = first_run
            with self.subTest(elapsed=elapsed, first_run=first_run):
                gates = judge_offline(evidence, now=NOW)
                self.assertFalse(
                    gates["elapsed_days_since_seed_is_a_real_positive_multi_day_span"]
                    and gates["live_auditor_reports_this_was_not_the_first_run"]
                )


if __name__ == "__main__":
    unittest.main()
