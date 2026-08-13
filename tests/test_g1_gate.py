"""G1 is judged from raw live evidence, never a producer's status field."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.gates import judge_g1

NOW = datetime(2026, 8, 13, 3, 0, tzinfo=UTC)
PROOF_ID = "proof-123"


def valid_evidence() -> dict:
    scope = f"g1-{PROOF_ID}"
    return {
        "schema_version": 1,
        "proof_id": PROOF_ID,
        "captured_at": (NOW - timedelta(minutes=1)).isoformat(),
        "project": "project-123",
        "cloud_run": {
            "service": "custody-control-plane",
            "region": "us-central1",
            "url": "https://custody.example",
            "revision": "custody-00001",
            "ready": True,
            "traffic_percent": 100,
            "health": {"status": "ok"},
            "trigger": {
                "run_id": "run-1",
                "department": scope,
                "seen": 1,
                "admitted": 1,
                "quarantined": 0,
                "refused": 0,
            },
        },
        "gemini": {
            "vertex": True,
            "requested_model": "gemini-3.5-flash",
            "model_version": "gemini-3.5-flash-001",
            "response": f"CUSTODY_G1_OK:{PROOF_ID}",
            "expected_response": f"CUSTODY_G1_OK:{PROOF_ID}",
        },
        "adk_memory_bank": {
            "framework": "google-adk",
            "configured_model": "gemini-3.5-flash",
            "agent_run_completed": True,
            "runner_event_count": 1,
            "agent_text": f"Confirmed {PROOF_ID}",
            "agent_engine": (
                "projects/project-123/locations/us-central1/reasoningEngines/1"
            ),
            "scope": {"app_name": "custody-g1", "user_id": scope},
            "memory_write_count": 1,
            "memory_operation_names": ["projects/project-123/operations/1"],
            "written_event_count": 2,
            "custody_split": {"total": 2, "withheld": 0, "refused": 0},
            "retrieved_memory_count": 1,
            "retrieved_memory_names": [
                "projects/project-123/locations/us-central1/reasoningEngines/1/memories/1"
            ],
            "retrieved_fact": "Sales exports require a signed approval.",
        },
    }


class G1EvidenceIsIndependentlyJudged(unittest.TestCase):
    def test_complete_live_evidence_passes(self):
        self.assertEqual(judge_g1(valid_evidence(), now=NOW).state, "PASS")

    def test_absent_evidence_is_blocked(self):
        self.assertEqual(judge_g1(None, now=NOW).state, "BLOCKED")

    def test_a_claimed_pass_cannot_hide_an_old_model(self):
        evidence = valid_evidence()
        evidence["status"] = "pass"
        evidence["gemini"]["model_version"] = "gemini-2.5-flash"
        self.assertEqual(judge_g1(evidence, now=NOW).state, "FAIL")

    def test_an_old_scope_cannot_satisfy_a_new_proof(self):
        evidence = valid_evidence()
        evidence["adk_memory_bank"]["scope"]["user_id"] = "g1-old-proof"
        self.assertEqual(judge_g1(evidence, now=NOW).state, "FAIL")

    def test_unhealthy_cloud_run_fails(self):
        evidence = valid_evidence()
        evidence["cloud_run"]["health"] = {"status": "down"}
        self.assertEqual(judge_g1(evidence, now=NOW).state, "FAIL")

    def test_expired_evidence_requires_a_rerun(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["captured_at"] = (NOW - timedelta(hours=25)).isoformat()
        self.assertEqual(judge_g1(evidence, now=NOW).state, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
