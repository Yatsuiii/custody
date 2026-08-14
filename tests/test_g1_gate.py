"""G1 is judged from raw live evidence, never a producer's status field."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.gates import judge_g1, judge_g5

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
            "write_path": "write_record",
            "framework": "google-adk",
            "configured_model": "gemini-3.5-flash",
            "agent_run_completed": True,
            "runner_event_count": 1,
            "agent_text": f"Confirmed {PROOF_ID}",
            "agent_engine": (
                "projects/project-123/locations/us-central1/reasoningEngines/1"
            ),
            "scope": {"app_name": "custody-g1", "user_id": scope},
            "memory_write_count": 3,
            "written_memory_ids": [
                "cr-aaaa",
                "cr-bbbb",
                "cr-50b22b0e9a2bf54667a24fca4bafcbb9",
            ],
            "conversational_memory_write_count": 2,
            "custody_split": {"total": 2, "withheld": 0, "refused": 0},
            "retrieved_memory_count": 1,
            "retrieved_facts": ["Sales exports require a signed approval."],
            "revocation_proof": {
                "tool": "sales_export_audit_tool",
                "tool_record_id": "g1-tool-1:0:0",
                "tool_memory_id": "cr-50b22b0e9a2bf54667a24fca4bafcbb9",
                "tool_fact": "Sales export audit control TOOL-abcd1234 requires dual sign-off.",
                "before_revoke_facts": [
                    "Sales exports require a signed approval.",
                    "Sales export audit control TOOL-abcd1234 requires dual sign-off.",
                ],
                "after_revoke_facts": ["Sales exports require a signed approval."],
                "revocation_id": "g1-revoke-proof-123",
                "removed": ["g1-tool-1:0:0"],
            },
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


class G5NamesTheGroupsItCannotDemonstrate(unittest.TestCase):
    """G5 stays BLOCKED on elapsed time, but for reasons that stay true.

    Telemetry was hardcoded unreachable while O1 was unbuilt. Once O1
    landed, the hardcode kept G5 unpassable for a reason that had stopped
    being true, which is exactly the drift between a claim and its
    computation that this whole gate file exists to catch.
    """

    def test_telemetry_is_read_from_the_observability_artifact(self):
        blank = {"g1": None, "registry": None, "gateway": None}
        without = judge_g5(blank)
        with_junk = judge_g5({**blank, "observability": {"not": "an artifact"}})

        self.assertIn("telemetry", without.detail)
        self.assertIn("telemetry", with_junk.detail)
        self.assertEqual(without.state, "BLOCKED")

    def test_g5_stays_blocked_even_with_every_group_demonstrable(self):
        """Real elapsed time is the one thing no artifact can stand in for."""
        self.assertEqual(judge_g5({}).state, "BLOCKED")


if __name__ == "__main__":
    unittest.main()
