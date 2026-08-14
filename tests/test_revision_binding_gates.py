"""Adversarial checks for the independent R2 revision-binding evidence judge."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime

from scripts.revision_binding_gates import judge


def valid_evidence() -> dict:
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "project": "proof-project",
        "claim_boundary": (
            "It does not detect a behavior-only change under an identical "
            "tools/list."
        ),
        "nonce_ledger_backend": "firestore",
        "cloud_run": {
            "service": "custody-export-mcp",
            "v1_revision": "custody-export-mcp-00001-aaa",
            "v2_revision": "custody-export-mcp-00002-bbb",
            "v1_restart_revision": "custody-export-mcp-00003-ccc",
        },
        "v1_token": {"revision": "rev-v1", "nonce": "nonce-v1"},
        "v2_token": {"revision": "rev-v2", "nonce": "nonce-v2"},
        "positive_control": {
            "result": {"is_error": False},
            "dispatch_count_before": 0,
            "dispatch_count_after": 1,
        },
        "replay_control": {
            "denied": True,
            "dispatch_count_before": 1,
            "dispatch_count_after": 1,
            "denial_log": {
                "insertId": "insert-replay",
                "jsonPayload": {
                    "reason": "replayed",
                    "revision": "v1",
                    "tool_name": "lookup_customer",
                },
            },
        },
        "digest_mismatch_control": {
            "denied": True,
            "dispatch_count_before": 0,
            "dispatch_count_after": 0,
            "instance_id_before": "instance-v2",
            "instance_id_after": "instance-v2",
            "denial_log": {
                "insertId": "insert-mismatch",
                "jsonPayload": {
                    "reason": "digest_mismatch",
                    "revision": "v2",
                    "tool_name": "lookup_customer",
                },
            },
        },
        "v2_positive_control": {
            "result": {"is_error": False},
            "dispatch_count_before": 0,
            "dispatch_count_after": 1,
        },
        "restart_replay_control": {
            "denied": True,
            "dispatch_count_before": 1,
            "dispatch_count_after": 1,
            "instance_id_before": "instance-v1-restart",
            "instance_id_after": "instance-v1-restart",
            "denial_log": {
                "insertId": "insert-restart-replay",
                "jsonPayload": {
                    "reason": "replayed",
                    "revision": "v1",
                    "tool_name": "lookup_customer",
                },
            },
        },
    }


class RevisionBindingGateJudgeTests(unittest.TestCase):
    def test_valid_artifact_passes_every_gate(self):
        gates = judge(valid_evidence())
        self.assertTrue(gates)
        self.assertTrue(all(gates.values()), gates)

    def test_a_replay_that_still_dispatched_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["replay_control"]["dispatch_count_after"] = 2
        gates = judge(evidence)
        self.assertFalse(gates["replay_was_refused_without_a_second_dispatch"])

    def test_a_stale_token_that_was_admitted_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["digest_mismatch_control"]["denied"] = False
        gates = judge(evidence)
        self.assertFalse(
            gates["stale_revision_token_was_refused_on_v2_with_no_dispatch"]
        )

    def test_identical_v1_and_v2_revisions_cannot_pass(self):
        """A fabricated artifact claiming a revision swap that never changed
        the digest must not be able to launder itself through this gate."""
        evidence = copy.deepcopy(valid_evidence())
        evidence["v2_token"]["revision"] = evidence["v1_token"]["revision"]
        gates = judge(evidence)
        self.assertFalse(gates["v1_and_v2_tokens_have_different_revisions"])

    def test_a_missing_claim_boundary_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["claim_boundary"] = "everything works, no caveats"
        gates = judge(evidence)
        self.assertFalse(gates["claim_boundary_states_the_behavior_only_gap"])

    def test_stale_evidence_cannot_pass_even_if_everything_else_is_valid(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["captured_at"] = "2020-01-01T00:00:00+00:00"
        gates = judge(evidence)
        self.assertFalse(gates["fresh_live_evidence"])
        self.assertFalse(all(gates.values()))

    def test_a_restart_replay_that_dispatched_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["restart_replay_control"]["denied"] = False
        gates = judge(evidence)
        self.assertFalse(gates["replay_survives_process_restart"])

    def test_an_in_memory_backed_run_cannot_pass_the_durability_gate(self):
        """The pre-fix state must genuinely fail this gate, not be treated
        as a malformed artifact: it is a real, honest FAIL."""
        evidence = copy.deepcopy(valid_evidence())
        evidence["nonce_ledger_backend"] = "in_memory"
        gates = judge(evidence)
        self.assertFalse(gates["replay_survives_process_restart"])

    def test_evidence_captured_before_this_control_existed_fails_not_crashes(self):
        evidence = copy.deepcopy(valid_evidence())
        del evidence["restart_replay_control"]
        del evidence["cloud_run"]["v1_restart_revision"]
        gates = judge(evidence)
        self.assertFalse(gates["replay_survives_process_restart"])

    def test_a_timestamp_with_no_timezone_is_rejected_outright(self):
        """Ambiguous local time cannot stand in for a server-issued instant."""
        evidence = copy.deepcopy(valid_evidence())
        evidence["captured_at"] = "2020-01-01T00:00:00"
        gates = judge(evidence)
        self.assertEqual(gates, {"fresh_live_evidence": False})


if __name__ == "__main__":
    unittest.main()
