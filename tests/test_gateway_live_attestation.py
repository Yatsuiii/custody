"""Adversarial tests for Google Cloud readback attestation."""

from __future__ import annotations

import copy
import unittest
from threading import Lock
from typing import Any

from scripts import gateway_live_attestation as live_attestation
from tests.test_gateway_gates import (
    ENGINE_ID as FIXTURE_ENGINE_ID,
    PROOF_ID as FIXTURE_PROOF_ID,
    PROJECT as FIXTURE_PROJECT,
    PROJECT_NUMBER as FIXTURE_PROJECT_NUMBER,
    valid_evidence,
)


def _replace_strings(
    value: Any,
    replacements: tuple[tuple[str, str], ...],
    *,
    protected: tuple[str, ...] = (),
) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_strings(item, replacements, protected=protected)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _replace_strings(item, replacements, protected=protected) for item in value
        ]
    if isinstance(value, str):
        if any(token in value for token in protected):
            return value
        replaced = value
        for old, new in replacements:
            replaced = replaced.replace(old, new)
        return replaced
    return value


def trusted_evidence() -> dict[str, Any]:
    """Retarget the offline fixture to the immutable live trust anchor."""
    evidence = valid_evidence()
    replacements = (
        (FIXTURE_PROJECT_NUMBER, live_attestation.PROJECT_NUMBER),
        (FIXTURE_ENGINE_ID, live_attestation.ENGINE_ID),
        (FIXTURE_PROJECT, live_attestation.PROJECT),
    )
    # The fixture project number is a substring of the proof ID. Resource
    # retargeting must never rewrite proof correlation values.
    retargeted = _replace_strings(evidence, replacements, protected=(FIXTURE_PROOF_ID,))
    if retargeted["proof_id"] != FIXTURE_PROOF_ID:
        raise AssertionError("live fixture retargeting corrupted the proof ID")
    return retargeted


class FakeCloud:
    """Serve immutable readbacks from a known-good evidence snapshot."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        self.evidence = copy.deepcopy(evidence)
        self.current_policy = copy.deepcopy(evidence["registry"]["iap_policy_deny"])
        self.calls: list[tuple[str, ...]] = []
        self._lock = Lock()

    def _read_log(self, query: str) -> Any | None:
        if "run.googleapis.com%2Fstdout" in query:
            return [copy.deepcopy(self.evidence["server_dispatch_log"])]
        if "gateway_requests" in query:
            return copy.deepcopy(
                [
                    self.evidence["gateway_logs"]["allow"][0],
                    self.evidence["gateway_logs"]["scope"][0],
                    self.evidence["gateway_logs"]["expiry"][0],
                    self.evidence["gateway_logs"]["deny"][0],
                ]
            )
        if "cloudaudit.googleapis.com%2Factivity" in query:
            audits = self.evidence["registry"]["iap_policy_audit_logs"]
            return copy.deepcopy([audits["allow"], audits["deny"]])
        return None

    def json(self, *arguments: str) -> Any:
        with self._lock:
            self.calls.append(arguments)
        prefix = arguments[:3]
        if arguments[:2] == ("projects", "describe"):
            return {
                "projectId": live_attestation.PROJECT,
                "projectNumber": live_attestation.PROJECT_NUMBER,
                "lifecycleState": "ACTIVE",
            }
        by_prefix = {
            ("network-services", "agent-gateways", "describe"): (
                lambda: self.evidence["gateway"]
            ),
            ("service-extensions", "authz-extensions", "describe"): (
                lambda: self.evidence["extension"]
            ),
            ("network-security", "authz-policies", "describe"): (
                lambda: self.evidence["authz_policy"]
            ),
            ("agent-registry", "services", "describe"): (
                lambda: self.evidence["registry"]["service"]
            ),
            ("agent-registry", "mcp-servers", "describe"): (
                lambda: self.evidence["registry"]["projection"]
            ),
            ("agent-registry", "agents", "list"): (
                lambda: [self.evidence["runtime"]["registered_agent"]]
            ),
            ("run", "services", "describe"): lambda: self.evidence["cloud_run"],
            ("iap", "web", "get-iam-policy"): lambda: self.current_policy,
        }
        if prefix in by_prefix:
            return copy.deepcopy(by_prefix[prefix]())
        if arguments[:2] == ("logging", "read"):
            found = self._read_log(arguments[2])
            if found is not None:
                return found
        raise AssertionError(f"unexpected cloud call: {arguments!r}")

    def rest_json(self, url: str) -> Any:
        with self._lock:
            self.calls.append(("REST GET", url))
        if url != live_attestation._runtime_url():
            raise AssertionError(f"unexpected REST URL: {url}")
        return copy.deepcopy(self.evidence["runtime"]["agent_engine"])


class LiveGatewayAttestationTests(unittest.TestCase):
    def test_valid_server_readbacks_pass_every_gate(self) -> None:
        evidence = trusted_evidence()
        cloud = FakeCloud(evidence)

        self.assertTrue(all(live_attestation.attest_live(evidence, cloud).values()))
        self.assertTrue(cloud.calls)

        server_queries = [
            call[2]
            for call in cloud.calls
            if call[:2] == ("logging", "read")
            and "run.googleapis.com%2Fstdout" in call[2]
        ]
        self.assertEqual(len(server_queries), 1)
        query = server_queries[0]
        expected_selectors = (
            f'logName="projects/{live_attestation.PROJECT}/logs/'
            'run.googleapis.com%2Fstdout"',
            f'resource.labels.project_id="{live_attestation.PROJECT}"',
            f'resource.labels.location="{live_attestation.REGION}"',
            f'resource.labels.service_name="{live_attestation.SERVICE_ID}"',
            (
                'resource.labels.revision_name="'
                f'{evidence["cloud_run"]["status"]["latestReadyRevisionName"]}"'
            ),
            f'jsonPayload.proof_id="{evidence["proof_id"]}"',
            f'jsonPayload.trace_id="{evidence["allow_control"]["trace_id"]}"',
            f'jsonPayload.customer_id="{evidence["allow_control"]["customer_id"]}"',
            f'insertId="{evidence["server_dispatch_log"]["insertId"]}"',
        )
        for selector in expected_selectors:
            self.assertIn(selector, query)

    def test_mcp_envelope_structured_content_shape_is_understood(self) -> None:
        """The live MCP server wraps tool output in the standard result
        envelope (``content`` plus ``structuredContent``) rather than
        returning it as a flat ``data`` object. Attestation must unwrap it.
        """
        live = trusted_evidence()
        flat = live["allow_control"]["result"]["data"]
        live["allow_control"]["result"]["data"] = {
            "isError": False,
            "content": [{"type": "text", "text": "irrelevant"}],
            "structuredContent": flat,
        }

        gates = live_attestation.attest_live(live, FakeCloud(live))

        self.assertTrue(gates["live_server_dispatch_log"])

    def test_fixture_retargeting_does_not_corrupt_proof_id(self) -> None:
        evidence = trusted_evidence()

        self.assertEqual(evidence["proof_id"], FIXTURE_PROOF_ID)
        self.assertEqual(
            evidence["server_dispatch_log"]["jsonPayload"]["proof_id"],
            FIXTURE_PROOF_ID,
        )

    def test_coherent_forged_resource_cannot_replace_server_readback(self) -> None:
        live = trusted_evidence()
        forged = copy.deepcopy(live)
        forged["gateway"]["protocols"] = ["HTTP"]

        gates = live_attestation.attest_live(forged, FakeCloud(live))

        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_gateway_configuration"])

    def test_coherent_forged_log_cannot_replace_server_readback(self) -> None:
        live = trusted_evidence()
        forged = copy.deepcopy(live)
        forged["gateway_logs"]["allow"][0]["httpRequest"]["status"] = 201

        gates = live_attestation.attest_live(forged, FakeCloud(live))

        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_gateway_log_entries"])

    def test_proof_graft_cannot_reuse_an_old_server_dispatch_log(self) -> None:
        live = trusted_evidence()
        forged = _replace_strings(live, ((FIXTURE_PROOF_ID, "f" * 32),))
        forged["server_dispatch_log"] = copy.deepcopy(live["server_dispatch_log"])

        gates = live_attestation.attest_live(forged, FakeCloud(live))

        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_server_dispatch_log"])

    def test_forged_dispatch_fields_cannot_replace_server_readback(self) -> None:
        live = trusted_evidence()
        for field, value in (
            ("trace_id", "f" * 32),
            ("instance_id", "other-instance"),
            ("dispatch_id", 9),
        ):
            with self.subTest(field=field):
                forged = copy.deepcopy(live)
                forged["server_dispatch_log"]["jsonPayload"][field] = value

                gates = live_attestation.attest_live(forged, FakeCloud(live))

                self.assertFalse(gates["live_server_dispatch_log"])

    def test_missing_gateway_phase_cannot_pass_live_attestation(self) -> None:
        live = trusted_evidence()
        for phase in ("allow", "scope", "expiry", "deny"):
            with self.subTest(phase=phase):
                forged = copy.deepcopy(live)
                forged["gateway_logs"][phase] = []

                gates = live_attestation.attest_live(forged, FakeCloud(live))

                self.assertFalse(gates["live_gateway_log_entries"])

    def test_runtime_rest_normalization_does_not_hide_spec_forgery(self) -> None:
        live = trusted_evidence()
        forged = copy.deepcopy(live)
        forged["runtime"]["agent_engine"]["spec"]["identityType"] = "SERVICE_ACCOUNT"

        gates = live_attestation.attest_live(forged, FakeCloud(live))

        self.assertFalse(gates["live_registry_runtime_target"])

    def test_current_policy_mismatch_cannot_pass(self) -> None:
        evidence = trusted_evidence()
        cloud = FakeCloud(evidence)
        cloud.current_policy = copy.deepcopy(evidence["registry"]["iap_policy_allow"])

        gates = live_attestation.attest_live(evidence, cloud)

        self.assertTrue(gates["live_attestation_available"])
        self.assertFalse(gates["live_final_deny_policy"])

    def test_evidence_cannot_redirect_the_trusted_project(self) -> None:
        live = trusted_evidence()
        forged = copy.deepcopy(live)
        forged["project"] = "attacker-project"
        cloud = FakeCloud(live)

        gates = live_attestation.attest_live(forged, cloud)

        self.assertFalse(gates["trusted_project_identity"])
        self.assertIn(("projects", "describe", live_attestation.PROJECT), cloud.calls)

    def test_cloud_failure_returns_fixed_clean_failure_gates(self) -> None:
        class BrokenCloud:
            def json(self, *arguments: str) -> Any:
                raise OSError("credentials unavailable")

            def rest_json(self, url: str) -> Any:
                raise OSError("credentials unavailable")

        gates = live_attestation.attest_live(trusted_evidence(), BrokenCloud())

        self.assertEqual(set(gates), set(live_attestation.GATE_NAMES))
        self.assertFalse(any(gates.values()))


if __name__ == "__main__":
    unittest.main()
