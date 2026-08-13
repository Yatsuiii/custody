"""Adversarial tests for the independent Model Armor evidence judge."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.model_armor_gates import (
    CLAIM_BOUNDARY,
    CLEAN_PROMPT_TEMPLATE,
    MALICIOUS_PROMPT_TEMPLATE,
    PROJECT,
    PROJECT_NUMBER,
    REGION,
    TEMPLATE_ID,
    attest_live,
    judge,
)

NOW = datetime(2026, 8, 13, 11, tzinfo=UTC)
PROOF_ID = "0123456789abcdef0123456789abcdef"
TEMPLATE_NAME = (
    f"projects/{PROJECT}/locations/{REGION}/templates/{TEMPLATE_ID}"
)


def _log(
    *, prompt: str, verdict: str, match_state: str, timestamp: datetime, insert_id: str
) -> dict:
    return {
        "insertId": insert_id,
        "logName": (
            f"projects/{PROJECT}/logs/modelarmor.googleapis.com%2Fsanitize_operations"
        ),
        "timestamp": timestamp.isoformat(),
        "receiveTimestamp": (timestamp + timedelta(milliseconds=200)).isoformat(),
        "severity": "INFO",
        "resource": {
            "type": "modelarmor.googleapis.com/SanitizeOperation",
            "labels": {
                "location": REGION,
                "template_id": TEMPLATE_ID,
                "resource_container": f"projects/{PROJECT_NUMBER}",
            },
        },
        "labels": {
            "modelarmor.googleapis.com/api_version": "v1",
            "modelarmor.googleapis.com/operation_type": "SANITIZE_USER_PROMPT",
        },
        "jsonPayload": {
            "@type": "type.googleapis.com/google.cloud.modelarmor.logging.v1.SanitizeOperationLogEntry",
            "operationType": "SANITIZE_USER_PROMPT",
            "sanitizationInput": {"text": prompt},
            "sanitizationResult": {
                "filterMatchState": match_state,
                "filterResults": {
                    "pi_and_jailbreak": {
                        "piAndJailbreakFilterResult": {
                            "executionState": "EXECUTION_SUCCESS",
                            "matchState": match_state,
                        }
                    },
                },
                "invocationResult": "SUCCESS",
                "sanitizationVerdict": verdict,
                "sanitizationVerdictReason": "fixture reason",
            },
        },
    }


def _result(*, match_state: str) -> dict:
    return {
        "filterMatchState": match_state,
        "filterResults": {
            "csam": {
                "csamFilterFilterResult": {
                    "executionState": "EXECUTION_SUCCESS",
                    "matchState": "NO_MATCH_FOUND",
                }
            },
            "pi_and_jailbreak": {
                "piAndJailbreakFilterResult": {
                    "executionState": "EXECUTION_SUCCESS",
                    "matchState": match_state,
                }
            },
        },
        "invocationResult": "SUCCESS",
    }


def valid_evidence() -> dict:
    malicious_prompt = MALICIOUS_PROMPT_TEMPLATE.format(proof_id=PROOF_ID)
    clean_prompt = CLEAN_PROMPT_TEMPLATE.format(proof_id=PROOF_ID)
    malicious_time = NOW - timedelta(minutes=2)
    clean_time = NOW - timedelta(minutes=1)
    return {
        "schema_version": 1,
        "proof_id": PROOF_ID,
        "started_at": (NOW - timedelta(minutes=3)).isoformat(),
        "captured_at": (NOW - timedelta(seconds=30)).isoformat(),
        "project": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "claim_boundary": CLAIM_BOUNDARY,
        "template": {
            "name": TEMPLATE_NAME,
            "createTime": (NOW - timedelta(days=1)).isoformat(),
            "updateTime": (NOW - timedelta(days=1)).isoformat(),
            "filterConfig": {
                "piAndJailbreakFilterSettings": {
                    "confidenceLevel": "MEDIUM_AND_ABOVE",
                    "filterEnforcement": "ENABLED",
                }
            },
            "labels": {"custody-proof": "approved-tool-ingress"},
            "templateMetadata": {
                "logSanitizeOperations": True,
                "logTemplateOperations": True,
            },
        },
        "malicious_control": {
            "prompt": malicious_prompt,
            "result": _result(match_state="MATCH_FOUND"),
            "log": _log(
                prompt=malicious_prompt,
                verdict="MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK",
                match_state="MATCH_FOUND",
                timestamp=malicious_time,
                insert_id="insert-malicious",
            ),
        },
        "clean_control": {
            "prompt": clean_prompt,
            "result": _result(match_state="NO_MATCH_FOUND"),
            "log": _log(
                prompt=clean_prompt,
                verdict="MODEL_ARMOR_SANITIZATION_VERDICT_ALLOW",
                match_state="NO_MATCH_FOUND",
                timestamp=clean_time,
                insert_id="insert-clean",
            ),
        },
    }


class ModelArmorGateJudgeTests(unittest.TestCase):
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
        evidence["claim_boundary"] = "Model Armor screens all Custody traffic."
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_wrong_project_cannot_pass(self):
        evidence = valid_evidence()
        evidence["project"] = "attacker-project"
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_drifted_or_wrong_template_cannot_pass(self):
        mutations = {
            "weaker_confidence": lambda t: t["filterConfig"][
                "piAndJailbreakFilterSettings"
            ].update({"confidenceLevel": "LOW_AND_ABOVE"}),
            "disabled": lambda t: t["filterConfig"][
                "piAndJailbreakFilterSettings"
            ].update({"filterEnforcement": "DISABLED"}),
            "unlogged": lambda t: t["templateMetadata"].update(
                {"logSanitizeOperations": False}
            ),
            "wrong_name": lambda t: t.update({"name": TEMPLATE_NAME + "-other"}),
            "unowned_label": lambda t: t["labels"].update({"custody-proof": "other"}),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                evidence = valid_evidence()
                mutate(evidence["template"])
                self.assertFalse(judge(evidence, now=NOW)["owned_template_bound"])

    def test_unblocked_malicious_control_cannot_pass(self):
        for mutation in ("no_match", "wrong_prompt"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                if mutation == "no_match":
                    evidence["malicious_control"]["result"] = _result(
                        match_state="NO_MATCH_FOUND"
                    )
                else:
                    evidence["malicious_control"]["prompt"] = "a harmless prompt"
                self.assertFalse(
                    judge(evidence, now=NOW)["malicious_prompt_blocked"]
                )

    def test_falsely_matched_clean_control_cannot_pass(self):
        evidence = valid_evidence()
        evidence["clean_control"]["result"] = _result(match_state="MATCH_FOUND")
        self.assertFalse(judge(evidence, now=NOW)["clean_prompt_allowed"])

    def test_reused_log_between_controls_cannot_pass(self):
        evidence = valid_evidence()
        evidence["clean_control"]["log"] = copy.deepcopy(
            evidence["malicious_control"]["log"]
        )
        self.assertFalse(
            judge(evidence, now=NOW)["controls_are_distinct_and_proof_bound"]
        )

    def test_foreign_proof_id_prompt_cannot_be_grafted(self):
        evidence = valid_evidence()
        foreign_prompt = MALICIOUS_PROMPT_TEMPLATE.format(proof_id="f" * 32)
        evidence["malicious_control"]["prompt"] = foreign_prompt
        evidence["malicious_control"]["log"]["jsonPayload"]["sanitizationInput"][
            "text"
        ] = foreign_prompt
        self.assertFalse(judge(evidence, now=NOW)["malicious_prompt_blocked"])

    def test_log_missing_verdict_reason_cannot_pass(self):
        evidence = valid_evidence()
        evidence["malicious_control"]["log"]["jsonPayload"]["sanitizationResult"][
            "sanitizationVerdictReason"
        ] = ""
        self.assertFalse(judge(evidence, now=NOW)["logs_correlate_enforcement"])

    def test_wrong_verdict_on_log_cannot_pass(self):
        evidence = valid_evidence()
        evidence["malicious_control"]["log"]["jsonPayload"]["sanitizationResult"][
            "sanitizationVerdict"
        ] = "MODEL_ARMOR_SANITIZATION_VERDICT_ALLOW"
        self.assertFalse(judge(evidence, now=NOW)["logs_correlate_enforcement"])

    def test_log_from_another_template_or_region_cannot_pass(self):
        for mutation in ("template", "region", "container"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                labels = evidence["malicious_control"]["log"]["resource"]["labels"]
                if mutation == "template":
                    labels["template_id"] = "other-template"
                elif mutation == "region":
                    labels["location"] = "us-east1"
                else:
                    labels["resource_container"] = "projects/999999999"
                self.assertFalse(
                    judge(evidence, now=NOW)["logs_correlate_enforcement"]
                )

    def test_log_outside_the_proof_window_cannot_pass(self):
        evidence = valid_evidence()
        evidence["malicious_control"]["log"]["timestamp"] = (
            NOW - timedelta(hours=2)
        ).isoformat()
        self.assertFalse(judge(evidence, now=NOW)["logs_correlate_enforcement"])

    def test_malformed_evidence_is_a_clean_failure(self):
        evidence = valid_evidence()
        del evidence["template"]
        self.assertEqual(judge(evidence, now=NOW), {"well_formed_evidence": False})

    def test_wrong_schema_version_is_a_clean_failure(self):
        evidence = valid_evidence()
        evidence["schema_version"] = 2
        self.assertEqual(judge(evidence, now=NOW), {"well_formed_evidence": False})


class FakeCloud:
    """Serve immutable readbacks from a known-good evidence snapshot."""

    def __init__(self, evidence: dict) -> None:
        self.evidence = copy.deepcopy(evidence)
        self.calls: list[tuple[str, ...]] = []

    def json(self, *arguments: str):
        self.calls.append(arguments)
        if arguments[:3] == ("model-armor", "templates", "describe"):
            return copy.deepcopy(self.evidence["template"])
        if arguments[:2] == ("logging", "read"):
            query = arguments[2]
            for phase in ("malicious_control", "clean_control"):
                insert_id = self.evidence[phase]["log"]["insertId"]
                if f'insertId="{insert_id}"' in query:
                    return [copy.deepcopy(self.evidence[phase]["log"])]
            return []
        raise AssertionError(f"unexpected cloud call: {arguments!r}")


class ModelArmorLiveAttestationTests(unittest.TestCase):
    def test_valid_live_readbacks_pass(self):
        evidence = valid_evidence()
        gates = attest_live(evidence, FakeCloud(evidence))
        self.assertTrue(all(gates.values()))

    def test_forged_template_cannot_replace_live_readback(self):
        live = valid_evidence()
        forged = copy.deepcopy(live)
        forged["template"]["filterConfig"]["piAndJailbreakFilterSettings"][
            "confidenceLevel"
        ] = "LOW_AND_ABOVE"
        gates = attest_live(forged, FakeCloud(live))
        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_template_bound"])

    def test_forged_log_cannot_replace_live_readback(self):
        live = valid_evidence()
        forged = copy.deepcopy(live)
        forged["malicious_control"]["log"]["jsonPayload"]["sanitizationResult"][
            "sanitizationVerdictReason"
        ] = "a forged reason the server never wrote"
        gates = attest_live(forged, FakeCloud(live))
        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_sanitize_log_entries"])

    def test_missing_server_log_is_reported_not_masked(self):
        live = valid_evidence()
        forged = copy.deepcopy(live)
        forged["clean_control"]["log"]["insertId"] = "insert-that-does-not-exist"
        gates = attest_live(forged, FakeCloud(live))
        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_sanitize_log_entries"])


if __name__ == "__main__":
    unittest.main()
