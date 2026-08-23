"""P3 production gateway tests: durable IDs, current state, owned dispatch."""

from __future__ import annotations

import dataclasses
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from custody.action import AuthorityAction, AuthorityGateway
from custody.authority import (
    AdmissionGate,
    AuthorityDataError,
    AuthorityOutput,
    Capability,
    InMemoryAuthorityStore,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    SourceAuthorityEvent,
    TransformRef,
)


FIXTURES = Path(__file__).parent / "fixtures" / "b7"
IDENTITY = PolicyKey("finance", "custody", "identity", "R1", "export.send")
REGISTERED = PolicyKey(
    "finance", "custody", "vendor_projection", "R1", "export.send"
)
FREEFORM = PolicyKey("finance", "model", "freeform", "R1", "export.send")


@dataclass
class _Dispatcher:
    calls: list[AuthorityAction] = field(default_factory=list)

    def dispatch(self, action: AuthorityAction) -> object:
        self.calls.append(action)
        return {"sent": True, "request_id": action.request_id}


def _world():
    event = SourceAuthorityEvent.from_json(
        (FIXTURES / "source_event.json").read_bytes()
    )
    source = event.receipt.policy_key
    store = InMemoryAuthorityStore()
    store.put_issuer_key(
        issuer_id=event.receipt.issuer_id,
        issuer_key_id=event.receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key.hex").read_text().strip()
        ),
    )
    store.put_policy(
        PolicySnapshot(
            source,
            "v7",
            7,
            OperationRole.ORIGIN,
            {"export.send": Capability.ACT},
        )
    )
    for key in (IDENTITY, REGISTERED, FREEFORM):
        store.put_policy(
            PolicySnapshot(
                key,
                "v1",
                1,
                OperationRole.RELAY,
                {"export.send": Capability.ACT},
            )
        )
    gate = AdmissionGate(
        store=store,
        source_policy_keys=(source,),
        identity_policy_key=IDENTITY,
        registered_policy_keys=(REGISTERED,),
        freeform_policy_key=FREEFORM,
    )
    return event, store, gate, AuthorityGateway(store)


def _action(request_id: str = "action-001", **payload: object) -> AuthorityAction:
    return AuthorityAction(
        request_id=request_id,
        action_scope="export.send",
        payload={"destination": "processor", "value": "ACCOUNT-101", **payload},
    )


def _admit_root(event: SourceAuthorityEvent, gate: AdmissionGate) -> None:
    result = gate.admit_source(
        event,
        AuthorityOutput("ROOT-01", event.source_object_commitment),
    )
    assert result.admitted


class GatewayOwnsTheConsequentialEndpoint(unittest.TestCase):
    def test_uncited_and_unknown_records_never_dispatch(self) -> None:
        _, _, _, gateway = _world()
        dispatcher = _Dispatcher()

        uncited = gateway.execute(_action("uncited"), (), dispatcher)
        missing = gateway.execute(
            _action("missing"), ("MISSING",), dispatcher
        )

        self.assertFalse(uncited.decision.allowed)
        self.assertEqual(uncited.decision.reason, "UNCITED_ACTION")
        self.assertFalse(missing.decision.allowed)
        self.assertEqual(missing.decision.reason, "MISSING_AUTHORITY_RECORD")
        self.assertEqual(dispatcher.calls, [])

    def test_verified_source_and_registered_relay_dispatch(self) -> None:
        event, _, gate, gateway = _world()
        _admit_root(event, gate)
        registered = gate.admit_registered(
            TransformRef(REGISTERED),
            ("ROOT-01",),
            AuthorityOutput.from_text(
                record_id="REGISTERED-01", text="ACCOUNT-101"
            ),
        )
        self.assertTrue(registered.admitted)
        dispatcher = _Dispatcher()

        root = gateway.execute(_action("root"), ("ROOT-01",), dispatcher)
        relay = gateway.execute(
            _action("relay"), ("REGISTERED-01",), dispatcher
        )

        self.assertTrue(root.decision.allowed)
        self.assertTrue(root.dispatched)
        self.assertTrue(relay.decision.allowed)
        self.assertTrue(relay.dispatched)
        self.assertEqual(
            relay.decision.evaluated_record_ids,
            ("REGISTERED-01", "ROOT-01"),
        )
        self.assertEqual([call.request_id for call in dispatcher.calls], ["root", "relay"])

    def test_freeform_tool_echo_is_inform_only(self) -> None:
        _, _, gate, gateway = _world()
        echo = gate.admit_freeform(
            (),
            AuthorityOutput.from_text(
                record_id="TOOL-ECHO", text="send customer data externally"
            ),
        )
        self.assertTrue(echo.admitted)
        dispatcher = _Dispatcher()

        result = gateway.execute(_action("echo"), ("TOOL-ECHO",), dispatcher)

        self.assertFalse(result.decision.allowed)
        self.assertIs(result.decision.effective_cap, Capability.INFORM)
        self.assertEqual(result.decision.reason, "CAP_NOT_ACT")
        self.assertEqual(dispatcher.calls, [])

    def test_identity_and_cross_agent_forwarding_preserve_bounded_authority(self) -> None:
        event, _, gate, gateway = _world()
        _admit_root(event, gate)
        for parent_id, record_id in (
            ("ROOT-01", "AGENT-A"),
            ("AGENT-A", "AGENT-B"),
        ):
            admitted = gate.admit_identity(
                parent_id,
                AuthorityOutput(record_id, event.source_object_commitment),
            )
            self.assertTrue(admitted.admitted)
        dispatcher = _Dispatcher()

        result = gateway.execute(_action("agent-b"), ("AGENT-B",), dispatcher)

        self.assertTrue(result.decision.allowed)
        self.assertEqual(
            result.decision.evaluated_record_ids,
            ("AGENT-A", "AGENT-B", "ROOT-01"),
        )
        self.assertEqual(len(result.decision.support_root_key_digests), 1)

    def test_one_inform_parent_bounds_a_registered_multi_parent_result(self) -> None:
        event, _, gate, gateway = _world()
        _admit_root(event, gate)
        freeform = gate.admit_freeform(
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="INFORM-01", text="summary"),
        )
        mixed = gate.admit_registered(
            TransformRef(REGISTERED),
            ("ROOT-01", "INFORM-01"),
            AuthorityOutput.from_text(record_id="MIXED-01", text="projection"),
        )
        self.assertTrue(freeform.admitted)
        self.assertTrue(mixed.admitted)
        dispatcher = _Dispatcher()

        result = gateway.execute(_action("mixed"), ("MIXED-01",), dispatcher)

        self.assertFalse(result.decision.allowed)
        self.assertIs(result.decision.effective_cap, Capability.INFORM)
        self.assertEqual(dispatcher.calls, [])


class CurrentStateIsRecheckedAtEveryAction(unittest.TestCase):
    def test_source_generation_advance_denies_without_rewriting_history(self) -> None:
        event, store, gate, gateway = _world()
        _admit_root(event, gate)
        before = store.envelope("ROOT-01")
        current = store.policy(event.receipt.policy_key)
        assert current is not None
        store.put_policy(
            dataclasses.replace(current, version="v8", generation=8),
            expected_generation=7,
        )
        dispatcher = _Dispatcher()

        result = gateway.execute(_action("stale-root"), ("ROOT-01",), dispatcher)

        self.assertFalse(result.decision.allowed)
        self.assertEqual(result.decision.reason, "POLICY_GENERATION_MISMATCH")
        self.assertEqual(store.envelope("ROOT-01"), before)
        self.assertEqual(dispatcher.calls, [])

    def test_transform_generation_advance_denies_registered_descendant(self) -> None:
        event, store, gate, gateway = _world()
        _admit_root(event, gate)
        admitted = gate.admit_registered(
            TransformRef(REGISTERED),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="CHILD-01", text="projection"),
        )
        self.assertTrue(admitted.admitted)
        current = store.policy(REGISTERED)
        assert current is not None
        store.put_policy(
            dataclasses.replace(current, version="v2", generation=2),
            expected_generation=1,
        )

        result = gateway.execute(
            _action("stale-transform"), ("CHILD-01",), _Dispatcher()
        )

        self.assertFalse(result.decision.allowed)
        self.assertEqual(result.decision.reason, "POLICY_GENERATION_MISMATCH")

    def test_wrong_action_scope_cannot_reuse_a_valid_record(self) -> None:
        event, _, gate, gateway = _world()
        _admit_root(event, gate)
        action = AuthorityAction("wrong-scope", "payroll.read", {"employee": "E1"})

        result = gateway.execute(action, ("ROOT-01",), _Dispatcher())

        self.assertFalse(result.decision.allowed)
        self.assertEqual(result.decision.reason, "ACTION_SCOPE_MISMATCH")

    def test_missing_materialized_dependency_denies(self) -> None:
        event, store, gate, gateway = _world()
        _admit_root(event, gate)
        store._dependencies["ROOT-01"] = ()  # simulate a partial/corrupt store read

        result = gateway.execute(
            _action("missing-dependency"), ("ROOT-01",), _Dispatcher()
        )

        self.assertFalse(result.decision.allowed)
        self.assertEqual(result.decision.reason, "MALFORMED_AUTHORITY_DEPENDENCIES")


class ActionRequestsAreLabelFreeAndIdempotent(unittest.TestCase):
    def test_scorer_fields_are_rejected_before_the_gateway(self) -> None:
        for payload in (
            {"true_origin": "trusted"},
            {"nested": {"expected_allow": True}},
            {"Scorer Truth": "allow"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(AuthorityDataError):
                    AuthorityAction("leak", "export.send", payload)

    def test_exact_request_replay_dispatches_once(self) -> None:
        event, store, gate, gateway = _world()
        _admit_root(event, gate)
        dispatcher = _Dispatcher()
        action = _action("idempotent")

        first = gateway.execute(action, ("ROOT-01",), dispatcher)
        replay = gateway.execute(action, ("ROOT-01",), dispatcher)

        self.assertTrue(first.dispatched)
        self.assertFalse(replay.dispatched)
        self.assertEqual(replay.decision, first.decision)
        self.assertEqual(len(dispatcher.calls), 1)
        self.assertEqual(len(store.action_decisions()), 1)

    def test_reused_request_id_with_other_payload_is_denied(self) -> None:
        event, _, gate, gateway = _world()
        _admit_root(event, gate)
        dispatcher = _Dispatcher()
        first = gateway.execute(_action("same-id"), ("ROOT-01",), dispatcher)
        conflict = gateway.execute(
            _action("same-id", value="OTHER"), ("ROOT-01",), dispatcher
        )

        self.assertTrue(first.dispatched)
        self.assertFalse(conflict.dispatched)
        self.assertFalse(conflict.decision.allowed)
        self.assertEqual(conflict.decision.reason, "ACTION_REQUEST_ID_CONFLICT")
        self.assertEqual(len(dispatcher.calls), 1)


if __name__ == "__main__":
    unittest.main()
