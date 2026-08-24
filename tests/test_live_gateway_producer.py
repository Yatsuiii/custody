"""Fault-injection tests for the live Gateway policy mutation state machine."""

from __future__ import annotations

import asyncio
import copy
import json
import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.live_gateway import (
    DENY_EXPRESSION,
    DENY_TITLE,
    EXPECTED_PRINCIPAL,
    GATEWAY_LOG_POLL_ATTEMPTS,
    ActiveAdmissionError,
    DedicatedIapPolicy,
    TemporaryAdmission,
    _gateway_logs,
    _iap_policy,
    _invoke,
    _require_mutation_targets,
    _temporary_admission,
    _TEMPORARY_ALLOW,
)

PROOF_A = "a" * 32
PROOF_B = "b" * 32
PROJECTION = "agentregistry-00000000-0000-0000-test"


def _policy(expression: str, *, title: str, etag: str = "etag-0") -> dict[str, object]:
    return {
        **_iap_policy(EXPECTED_PRINCIPAL, expression, title=title),
        "etag": etag,
    }


class FakePolicyCloud:
    """Model authoritative IAP readback and controllable write failures."""

    def __init__(self, state: dict[str, object]) -> None:
        self.state = copy.deepcopy(state)
        self.writes = 0
        self.fail_writes = 0
        self.ambiguous_writes = 0

    def json(self, *arguments: str) -> dict[str, object]:
        if arguments[:3] != ("iap", "web", "get-iam-policy"):
            raise AssertionError(f"unexpected read: {arguments!r}")
        return copy.deepcopy(self.state)

    def run(self, *arguments: str, capture: bool = False) -> str:
        del capture
        if arguments[:3] != ("iap", "web", "set-iam-policy"):
            raise AssertionError(f"unexpected write: {arguments!r}")
        path = Path(arguments[3])
        requested = json.loads(path.read_text())
        if requested["etag"] != self.state["etag"]:
            raise subprocess.CalledProcessError(1, ["gcloud"], "etag race")
        self.writes += 1
        if self.fail_writes:
            self.fail_writes -= 1
            raise subprocess.TimeoutExpired(["gcloud"], 120)
        applied = copy.deepcopy(requested)
        applied["etag"] = f"etag-{self.writes}"
        self.state = applied
        if self.ambiguous_writes:
            self.ambiguous_writes -= 1
            raise subprocess.TimeoutExpired(["gcloud"], 120)
        return ""


def _boundary(cloud: FakePolicyCloud, proof_id: str = PROOF_A) -> DedicatedIapPolicy:
    return DedicatedIapPolicy(
        cloud,  # type: ignore[arg-type]
        projection_id=PROJECTION,
        principal=EXPECTED_PRINCIPAL,
        proof_id=proof_id,
    )


class LiveGatewayProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sleep = patch("scripts.live_gateway.time.sleep", return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_temporary_admission_is_proof_owned_and_server_expiring(self) -> None:
        admission = TemporaryAdmission(
            PROOF_A, datetime.now(UTC) + timedelta(minutes=10)
        )
        policy = _policy(admission.expression, title=admission.title)

        parsed = _temporary_admission(policy, principal=EXPECTED_PRINCIPAL)

        self.assertEqual(parsed, admission)
        self.assertIn("request.time < timestamp(", admission.expression)
        self.assertIn("lookup_customer", admission.expression)
        self.assertIn(PROOF_A, admission.title)

    def test_live_foreign_admission_is_not_overwritten(self) -> None:
        foreign = TemporaryAdmission(PROOF_B, datetime.now(UTC) + timedelta(minutes=5))
        cloud = FakePolicyCloud(_policy(foreign.expression, title=foreign.title))

        with self.assertRaises(ActiveAdmissionError):
            _boundary(cloud).prepare_safe_deny()

        self.assertEqual(cloud.writes, 0)

    def test_expired_admission_is_repaired_to_safe_deny(self) -> None:
        expired = TemporaryAdmission(PROOF_B, datetime.now(UTC) - timedelta(seconds=1))
        cloud = FakePolicyCloud(_policy(expired.expression, title=expired.title))

        repaired = _boundary(cloud).prepare_safe_deny()

        self.assertTrue(
            DedicatedIapPolicy._is_exact(
                repaired, expression=DENY_EXPRESSION, title=DENY_TITLE
            )
        )
        self.assertEqual(cloud.writes, 1)

    def test_ambiguous_write_is_accepted_only_after_exact_readback(self) -> None:
        cloud = FakePolicyCloud(_policy(DENY_EXPRESSION, title=DENY_TITLE))
        cloud.ambiguous_writes = 1
        admission = TemporaryAdmission(
            PROOF_A, datetime.now(UTC) + timedelta(minutes=10)
        )

        applied = _boundary(cloud).apply_temporary(admission)

        self.assertEqual(applied.applied, cloud.state)
        self.assertTrue(
            DedicatedIapPolicy._is_exact(
                applied.applied,
                expression=admission.expression,
                title=admission.title,
            )
        )
        self.assertEqual(cloud.writes, 1)

    def test_cleanup_failure_leaves_only_a_bounded_server_expiring_lease(self) -> None:
        expires = datetime.now(UTC) + timedelta(minutes=10)
        admission = TemporaryAdmission(PROOF_A, expires)
        cloud = FakePolicyCloud(_policy(admission.expression, title=admission.title))
        cloud.fail_writes = 3

        with self.assertRaises(RuntimeError):
            _boundary(cloud).ensure_deny()

        remaining = _temporary_admission(cloud.state, principal=EXPECTED_PRINCIPAL)
        self.assertIsNotNone(remaining)
        assert remaining is not None
        self.assertEqual(remaining.proof_id, PROOF_A)
        self.assertLessEqual(remaining.expires_at, expires)
        self.assertEqual(cloud.writes, 3)

    def test_two_producers_cannot_both_own_the_allow_state(self) -> None:
        cloud = FakePolicyCloud(_policy(DENY_EXPRESSION, title=DENY_TITLE))
        first = _boundary(cloud, PROOF_A)
        second = _boundary(cloud, PROOF_B)
        first_admission = TemporaryAdmission(
            PROOF_A, datetime.now(UTC) + timedelta(minutes=10)
        )
        second_admission = TemporaryAdmission(
            PROOF_B, datetime.now(UTC) + timedelta(minutes=10)
        )

        first.apply_temporary(first_admission)
        with self.assertRaises(ActiveAdmissionError):
            second.apply_temporary(second_admission)
        with self.assertRaises(ActiveAdmissionError):
            second.ensure_deny()

        self.assertEqual(
            _temporary_admission(cloud.state, principal=EXPECTED_PRINCIPAL),
            first_admission,
        )

    def test_unowned_principal_and_projection_are_rejected_before_reads(self) -> None:
        cloud = FakePolicyCloud({"etag": "e", "bindings": []})
        with self.assertRaises(ValueError):
            DedicatedIapPolicy(
                cloud,  # type: ignore[arg-type]
                projection_id="../../other",
                principal=EXPECTED_PRINCIPAL,
                proof_id=PROOF_A,
            )
        with self.assertRaises(ValueError):
            DedicatedIapPolicy(
                cloud,  # type: ignore[arg-type]
                projection_id=PROJECTION,
                principal="principal://attacker",
                proof_id=PROOF_A,
            )

    def test_resource_validation_rejects_before_policy_mutation(self) -> None:
        resources = {
            "gateway": {"name": "projects/attacker/agentGateways/other"},
            "extension": {},
            "authz_policy": {},
            "service": {
                "registryResource": (
                    "projects/742122658452/locations/us-central1/mcpServers/"
                    + PROJECTION
                )
            },
            "projection": {},
            "cloud_run": {},
        }

        with self.assertRaises(RuntimeError):
            _require_mutation_targets(
                resources,
                agent={},
                endpoint=("https://custody-export-mcp-anexdhueiq-uc.a.run.app/mcp"),
            )


def _cel_admits(expression: str, *, tool_name: str, now: datetime) -> bool:
    """Evaluate Custody's canonical two-clause temporary-admission CEL shape.

    IAP evaluates this server-side; this mirrors the documented boolean
    semantics of ``request.time < timestamp(...)`` (Google IAM conditions)
    against the exact shape ``_TEMPORARY_ALLOW`` parses, so the admission
    logic is falsifiable offline without a live IAP evaluation.
    """
    match = _TEMPORARY_ALLOW.fullmatch(expression)
    if match is None:
        raise ValueError("not the canonical temporary admission shape")
    expires_at = datetime.fromisoformat(match.group("expires").replace("Z", "+00:00"))
    return tool_name == "" or (now < expires_at and tool_name == "lookup_customer")


class TemporaryAdmissionCelSemanticsTests(unittest.TestCase):
    def test_empty_name_handshake_passthrough_survives_expiry(self) -> None:
        admission = TemporaryAdmission(
            PROOF_A, datetime.now(UTC) + timedelta(minutes=10)
        )
        self.assertTrue(
            _cel_admits(
                admission.expression,
                tool_name="",
                now=admission.expires_at + timedelta(minutes=5),
            )
        )

    def test_lookup_customer_admitted_before_denied_after_expiry(self) -> None:
        admission = TemporaryAdmission(
            PROOF_A, datetime.now(UTC) + timedelta(minutes=10)
        )
        self.assertTrue(
            _cel_admits(
                admission.expression,
                tool_name="lookup_customer",
                now=admission.expires_at - timedelta(seconds=1),
            )
        )
        self.assertFalse(
            _cel_admits(
                admission.expression,
                tool_name="lookup_customer",
                now=admission.expires_at + timedelta(seconds=1),
            )
        )

    def test_policy_canary_never_admitted_by_temporary_allow(self) -> None:
        admission = TemporaryAdmission(
            PROOF_A, datetime.now(UTC) + timedelta(minutes=10)
        )
        for when in (
            admission.expires_at - timedelta(minutes=5),
            admission.expires_at + timedelta(minutes=5),
        ):
            with self.subTest(when=when):
                self.assertFalse(
                    _cel_admits(
                        admission.expression,
                        tool_name="custody_policy_canary",
                        now=when,
                    )
                )

    def test_previous_all_expiring_shape_is_rejected(self) -> None:
        """schema-v1's CEL expired the empty-name handshake clause too, so a
        post-expiry initialize call could fail before ``tools/call`` and
        never produce the log the proof needs. The parser must reject it.
        """
        expires = (
            (datetime.now(UTC) + timedelta(minutes=10))
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        old_shape = (
            f"request.time < timestamp('{expires}') && "
            "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
            "in ['lookup_customer', '']"
        )
        policy = _policy(
            old_shape, title=f"Custody temporary lookup admission/{PROOF_A}"
        )
        self.assertIsNone(_temporary_admission(policy, principal=EXPECTED_PRINCIPAL))


class BoundedWaitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sleep = patch("scripts.live_gateway.time.sleep", return_value=None)
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def test_runtime_query_has_a_bounded_outer_timeout(self) -> None:
        class HangingEngine:
            async def async_query(self, **kwargs: object) -> dict[str, object]:
                del kwargs
                await asyncio.sleep(999)
                return {}

        with patch("scripts.live_gateway.RUNTIME_QUERY_TIMEOUT_SECONDS", 0.01):
            with self.assertRaises(TimeoutError):
                asyncio.run(
                    _invoke(
                        HangingEngine(),
                        customer_id="c",
                        trace_id="t" * 32,
                        proof_id=PROOF_A,
                    )
                )

    def test_gateway_log_polling_recovers_from_transient_reads_and_is_bounded(
        self,
    ) -> None:
        class AlwaysTransientCloud:
            def __init__(self) -> None:
                self.calls = 0

            def json(self, *arguments: str) -> list[dict[str, object]]:
                del arguments
                self.calls += 1
                raise subprocess.CalledProcessError(1, ["gcloud"], "transient")

        cloud = AlwaysTransientCloud()

        with self.assertRaises(RuntimeError):
            _gateway_logs(cloud, "a" * 32)  # type: ignore[arg-type]

        self.assertEqual(cloud.calls, GATEWAY_LOG_POLL_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
