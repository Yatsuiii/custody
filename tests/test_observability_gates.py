"""Adversarial tests for the independent Agent Observability evidence judge."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.observability_gates import (
    CLAIM_BOUNDARY,
    LOG_EVENT,
    PROJECT,
    REGION,
    SPAN_NAME,
    attest_live,
    judge,
)

NOW = datetime(2026, 8, 13, 12, tzinfo=UTC)
PROOF_ID = "0123456789abcdef0123456789abcdef"
TRACE_ID = "a" * 32
SPAN_ID = "b" * 16
DIGEST = "c" * 64
OTHER_DIGEST = "d" * 64
LOG_NAME = f"projects/{PROJECT}/logs/custody-observability"


def _log_entry(
    *,
    proof_id: str = PROOF_ID,
    trace_id: str = TRACE_ID,
    span_id: str = SPAN_ID,
    digest: str = DIGEST,
    timestamp: datetime,
    insert_id: str = "insert-1",
) -> dict:
    return {
        "insertId": insert_id,
        "logName": LOG_NAME,
        "severity": "INFO",
        "timestamp": timestamp.isoformat(),
        "receiveTimestamp": (timestamp + timedelta(milliseconds=200)).isoformat(),
        "trace": f"projects/{PROJECT}/traces/{trace_id}",
        "spanId": span_id,
        "jsonPayload": {
            "event": LOG_EVENT,
            "proof_id": proof_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "span_name": SPAN_NAME,
            "custody_digest": digest,
            "admitted_digest_count": 2,
        },
    }


def valid_evidence() -> dict:
    timestamp = NOW - timedelta(minutes=2)
    return {
        "schema_version": 1,
        "proof_id": PROOF_ID,
        "started_at": (NOW - timedelta(minutes=3)).isoformat(),
        "captured_at": (NOW - timedelta(seconds=30)).isoformat(),
        "project": PROJECT,
        "region": REGION,
        "claim_boundary": CLAIM_BOUNDARY,
        "trace_id": TRACE_ID,
        "span_id": SPAN_ID,
        "span_name": SPAN_NAME,
        "custody_digest": DIGEST,
        "admitted_digest_count": 2,
        "g1_admission": {
            "framework": "google-adk",
            "agent_run_completed": True,
            "agent_text": f"Recorded, audit identifier {PROOF_ID}.",
            "memory_write_count": 1,
            "custody_split": {"total": 2, "withheld": 0, "refused": 0},
            "retrieved_memory_count": 1,
            "admitted_digests": [DIGEST, OTHER_DIGEST],
        },
        "log_entry": _log_entry(timestamp=timestamp),
    }


class ObservabilityGateJudgeTests(unittest.TestCase):
    def test_valid_live_artifact_passes_every_gate(self):
        self.assertTrue(all(judge(valid_evidence(), now=NOW).values()))

    def test_proof_duration_is_bounded(self):
        evidence = valid_evidence()
        evidence["started_at"] = (NOW - timedelta(minutes=15)).isoformat()
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_stale_artifact_cannot_pass(self):
        evidence = valid_evidence()
        evidence["captured_at"] = (NOW - timedelta(hours=25)).isoformat()
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_broader_claim_boundary_cannot_pass(self):
        evidence = valid_evidence()
        evidence["claim_boundary"] = "Every trace proves every quarantine."
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_all_zero_ids_cannot_pass(self):
        for field in ("trace_id", "span_id"):
            with self.subTest(field=field):
                evidence = valid_evidence()
                evidence[field] = "0" * len(evidence[field])
                self.assertFalse(
                    judge(evidence, now=NOW)["trace_and_span_ids_are_well_formed"]
                )

    def test_malformed_digest_cannot_pass(self):
        evidence = valid_evidence()
        evidence["custody_digest"] = "not-a-real-digest"
        self.assertFalse(
            judge(evidence, now=NOW)["trace_and_span_ids_are_well_formed"]
        )

    def test_g1_run_that_withheld_or_refused_cannot_pass(self):
        for field in ("withheld", "refused"):
            with self.subTest(field=field):
                evidence = valid_evidence()
                evidence["g1_admission"]["custody_split"][field] = 1
                self.assertFalse(
                    judge(evidence, now=NOW)["g1_admission_reached_memory_bank"]
                )

    def test_g1_run_not_bound_to_this_proof_id_cannot_pass(self):
        evidence = valid_evidence()
        evidence["g1_admission"]["agent_text"] = "Recorded, audit identifier f00d."
        self.assertFalse(
            judge(evidence, now=NOW)["g1_admission_reached_memory_bank"]
        )

    def test_digest_not_among_admitted_records_cannot_pass(self):
        evidence = valid_evidence()
        evidence["custody_digest"] = "e" * 64
        self.assertFalse(
            judge(evidence, now=NOW)["digest_is_one_of_the_admitted_records"]
        )

    def test_foreign_digest_grafted_from_another_run_cannot_pass(self):
        """The digest is real, but not one this run's ADK flow produced."""
        evidence = valid_evidence()
        evidence["g1_admission"]["admitted_digests"] = ["f" * 64, "0" * 64]
        self.assertFalse(
            judge(evidence, now=NOW)["digest_is_one_of_the_admitted_records"]
        )

    def test_log_entry_with_wrong_trace_or_span_cannot_pass(self):
        for field, value in (("trace", f"projects/{PROJECT}/traces/{'f' * 32}"), ("spanId", "f" * 16)):
            with self.subTest(field=field):
                evidence = valid_evidence()
                evidence["log_entry"][field] = value
                self.assertFalse(
                    judge(evidence, now=NOW)["log_entry_binds_trace_span_and_digest"]
                )

    def test_log_entry_with_wrong_digest_payload_cannot_pass(self):
        evidence = valid_evidence()
        evidence["log_entry"]["jsonPayload"]["custody_digest"] = OTHER_DIGEST
        self.assertFalse(
            judge(evidence, now=NOW)["log_entry_binds_trace_span_and_digest"]
        )

    def test_log_entry_from_another_proof_cannot_pass(self):
        evidence = valid_evidence()
        evidence["log_entry"]["jsonPayload"]["proof_id"] = "f" * 32
        self.assertFalse(
            judge(evidence, now=NOW)["log_entry_binds_trace_span_and_digest"]
        )

    def test_log_entry_outside_the_proof_window_cannot_pass(self):
        evidence = valid_evidence()
        evidence["log_entry"]["timestamp"] = (NOW - timedelta(hours=2)).isoformat()
        self.assertFalse(
            judge(evidence, now=NOW)["log_entry_binds_trace_span_and_digest"]
        )

    def test_malformed_evidence_is_a_clean_failure(self):
        evidence = valid_evidence()
        del evidence["log_entry"]
        self.assertEqual(judge(evidence, now=NOW), {"well_formed_evidence": False})

    def test_wrong_schema_version_is_a_clean_failure(self):
        evidence = valid_evidence()
        evidence["schema_version"] = 2
        self.assertEqual(judge(evidence, now=NOW), {"well_formed_evidence": False})


class FakeCloud:
    """Serve immutable readbacks from a known-good evidence snapshot."""

    def __init__(self, evidence: dict) -> None:
        self.evidence = copy.deepcopy(evidence)

    def json(self, *arguments: str):
        if arguments[:2] == ("logging", "read"):
            insert_id = self.evidence["log_entry"]["insertId"]
            if f'insertId="{insert_id}"' in arguments[2]:
                return [copy.deepcopy(self.evidence["log_entry"])]
            return []
        raise AssertionError(f"unexpected cloud call: {arguments!r}")


class ObservabilityLiveAttestationTests(unittest.TestCase):
    def test_valid_live_readback_passes(self):
        evidence = valid_evidence()
        gates = attest_live(evidence, FakeCloud(evidence))
        self.assertTrue(all(gates.values()))

    def test_forged_log_entry_cannot_replace_live_readback(self):
        live = valid_evidence()
        forged = copy.deepcopy(live)
        forged["log_entry"]["jsonPayload"]["custody_digest"] = OTHER_DIGEST
        gates = attest_live(forged, FakeCloud(live))
        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_log_entry_matches"])

    def test_missing_server_log_is_reported_not_masked(self):
        live = valid_evidence()
        forged = copy.deepcopy(live)
        forged["log_entry"]["insertId"] = "insert-that-does-not-exist"
        gates = attest_live(forged, FakeCloud(live))
        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_log_entry_matches"])


if __name__ == "__main__":
    unittest.main()
