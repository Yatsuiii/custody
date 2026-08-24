"""P4 selective receipt-root revocation through production APIs."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import threading
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from custody.action import AuthorityAction, AuthorityGateway
from custody.authority import (
    AdmissionGate,
    AuthorityConflict,
    AuthorityDataError,
    AuthorityOutput,
    Capability,
    FORBIDDEN_RUNTIME_FIELDS,
    InMemoryAuthorityStore,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
    TransformRef,
)
from custody.control_plane import ControlPlane


FIXTURES = Path(__file__).parent / "fixtures" / "b7"
IDENTITY = PolicyKey("finance", "custody", "identity", "R1", "export.send")
REGISTERED = PolicyKey("finance", "custody", "vendor_projection", "R1", "export.send")
FREEFORM = PolicyKey("finance", "model", "freeform", "R1", "export.send")


@dataclass
class _Dispatcher:
    calls: list[str] = field(default_factory=list)

    def dispatch(self, action: AuthorityAction) -> object:
        self.calls.append(action.request_id)
        return action.request_id


class _BarrierStore(InMemoryAuthorityStore):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.candidate_read = threading.Event()
        self.continue_action = threading.Event()
        self.barrier_enabled = False

    def linearize_action(self, **kwargs):
        if self.barrier_enabled:
            self.envelope("DESC-01")
            self.candidate_read.set()
            if not self.continue_action.wait(timeout=2):
                raise TimeoutError("action race barrier did not release")
        return super().linearize_action(**kwargs)


def _load_events() -> tuple[SourceAuthorityEvent, ...]:
    names = (
        "source_event.json",
        "source_event_002.json",
        "source_event_003.json",
        "source_event_004.json",
    )
    return tuple(
        SourceAuthorityEvent.from_json((FIXTURES / name).read_bytes()) for name in names
    )


def _world(store: InMemoryAuthorityStore | None = None):
    events = _load_events()
    store = store or InMemoryAuthorityStore()
    store.put_issuer_key(
        issuer_id=events[0].receipt.issuer_id,
        issuer_key_id=events[0].receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key.hex").read_text().strip()
        ),
    )
    store.put_issuer_key(
        issuer_id=events[1].receipt.issuer_id,
        issuer_key_id=events[1].receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key_v2.hex").read_text().strip()
        ),
    )
    source = events[0].receipt.policy_key
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
    for index, event in enumerate(events, 1):
        admitted = gate.admit_source(
            event,
            AuthorityOutput(f"ROOT-{index:02d}", event.source_object_commitment),
        )
        assert admitted.admitted
    for root_id, descendant_id in (
        ("ROOT-01", "DESC-01"),
        ("ROOT-02", "DESC-02"),
        ("ROOT-03", "DESC-03"),
        ("ROOT-04", "DESC-04"),
    ):
        admitted = gate.admit_registered(
            TransformRef(REGISTERED),
            (root_id,),
            AuthorityOutput.from_text(record_id=descendant_id, text=descendant_id),
        )
        assert admitted.admitted
    mixed = gate.admit_registered(
        TransformRef(REGISTERED),
        ("DESC-01", "DESC-03"),
        AuthorityOutput.from_text(record_id="MIXED-13", text="mixed"),
    )
    assert mixed.admitted
    return events, store, gate, AuthorityGateway(store), RevocationController(store)


def _root_key(event: SourceAuthorityEvent, record_id: str) -> ReceiptRootKey:
    return ReceiptRootKey.from_receipt(event.receipt, custody_root_record_id=record_id)


def _action(request_id: str) -> AuthorityAction:
    return AuthorityAction(
        request_id,
        "export.send",
        {"destination": "processor", "record": request_id},
    )


class StaticRootFixturesStayLabelFree(unittest.TestCase):
    def test_new_events_are_byte_pinned_and_have_no_private_key(self) -> None:
        expected = {
            "source_event_002.json": "47f4e41e2e18b629876d473229578ab118952c62fc66a5790854aab73ec150af",
            "source_event_003.json": "554ff5e385fe3ee5c6223fcf727ebeaefa94a1f44be2e2d1a71424ce42325c6e",
            "source_event_004.json": "59615603c229eef9d33b56d557ebabca2a8d92bd1e2ccb3326f05840a968be37",
        }
        for name, digest in expected.items():
            payload = (FIXTURES / name).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
            keys = _nested_keys(json.loads(payload))
            self.assertTrue(FORBIDDEN_RUNTIME_FIELDS.isdisjoint(keys))
        self.assertEqual(
            sorted(path.name for path in FIXTURES.iterdir() if "private" in path.name),
            [],
        )


class ReceiptRootRevocationIsSelective(unittest.TestCase):
    def test_control_plane_accepts_only_explicit_root_key_values(self) -> None:
        events, _, _, _, controller = _world()
        key = _root_key(events[0], "ROOT-01")
        plane = ControlPlane(b7_revocation=controller)

        result = plane.revoke_receipt_roots(
            {"revocation_id": "control-001", "root_keys": [key.as_list()]}
        )

        self.assertTrue(result["applied"])
        self.assertEqual(result["root_key_digests"], [key.digest])
        self.assertIn("ROOT-01", result["affected_record_ids"])
        self.assertEqual(
            ControlPlane().revoke_receipt_roots(
                {"revocation_id": "none", "root_keys": [key.as_list()]}
            ),
            {"applied": False, "reason": "B7_AUTHORITY_NOT_CONFIGURED"},
        )

    def test_selected_roots_and_every_descendant_deny_while_others_allow(self) -> None:
        events, store, _, gateway, controller = _world()
        before = {
            envelope.record_id: envelope.canonical_bytes()
            for envelope in store.records()
        }
        result = controller.revoke_receipt_roots(
            revocation_id="revocation-001",
            root_keys=(
                _root_key(events[0], "ROOT-01"),
                _root_key(events[1], "ROOT-02"),
            ),
        )

        self.assertEqual(
            result.affected_record_ids,
            ("DESC-01", "DESC-02", "MIXED-13", "ROOT-01", "ROOT-02"),
        )
        dispatcher = _Dispatcher()
        outcomes = {
            record_id: gateway.execute(
                _action(f"act-{record_id}"), (record_id,), dispatcher
            ).decision
            for record_id in (
                "DESC-01",
                "DESC-02",
                "MIXED-13",
                "DESC-03",
                "DESC-04",
            )
        }
        for record_id in ("DESC-01", "DESC-02", "MIXED-13"):
            self.assertFalse(outcomes[record_id].allowed)
            self.assertEqual(outcomes[record_id].reason, "REVOKED_AUTHORITY_ROOT")
        for record_id in ("DESC-03", "DESC-04"):
            self.assertTrue(outcomes[record_id].allowed)
        self.assertEqual(dispatcher.calls, ["act-DESC-03", "act-DESC-04"])
        self.assertEqual(
            {
                envelope.record_id: envelope.canonical_bytes()
                for envelope in store.records()
            },
            before,
        )

    def test_exact_replay_is_idempotent_and_conflicting_event_id_is_rejected(
        self,
    ) -> None:
        events, store, _, _, controller = _world()
        key_1 = _root_key(events[0], "ROOT-01")
        key_2 = _root_key(events[1], "ROOT-02")

        first = controller.revoke_receipt_roots(
            revocation_id="revocation-001", root_keys=(key_1,)
        )
        replay = controller.revoke_receipt_roots(
            revocation_id="revocation-001", root_keys=(key_1,)
        )

        self.assertEqual(replay, first)
        self.assertEqual(len(store.root_revocations()), 1)
        with self.assertRaises(AuthorityConflict):
            controller.revoke_receipt_roots(
                revocation_id="revocation-001", root_keys=(key_2,)
            )

    def test_fabricated_or_non_root_selectors_are_rejected(self) -> None:
        events, store, _, _, controller = _world()
        key = _root_key(events[0], "ROOT-01")
        fabricated = dataclasses.replace(key, receipt_id="other-receipt")
        non_root = dataclasses.replace(key, custody_root_record_id="DESC-01")

        for selector in (fabricated, non_root):
            with self.subTest(selector=selector):
                with self.assertRaises(AuthorityDataError):
                    controller.revoke_receipt_roots(
                        revocation_id=f"reject-{selector.receipt_id}",
                        root_keys=(selector,),
                    )
        self.assertEqual(store.root_revocations(), ())

    def test_receipt_copy_cannot_escape_the_original_root_binding(self) -> None:
        events, _, gate, _, controller = _world()
        controller.revoke_receipt_roots(
            revocation_id="revocation-001",
            root_keys=(_root_key(events[0], "ROOT-01"),),
        )

        copied = gate.admit_source(
            events[0],
            AuthorityOutput("ROOT-COPY", events[0].source_object_commitment),
        )

        self.assertFalse(copied.admitted)
        self.assertEqual(copied.reason, "UNRELATED_RECEIPT_REPLAY")

    def test_stale_policy_does_not_prevent_retroactive_root_selection(self) -> None:
        events, store, _, _, controller = _world()
        current = store.policy(events[0].receipt.policy_key)
        assert current is not None
        store.put_policy(
            dataclasses.replace(current, version="v8", generation=8),
            expected_generation=7,
        )

        result = controller.revoke_receipt_roots(
            revocation_id="revocation-after-generation",
            root_keys=(_root_key(events[0], "ROOT-01"),),
        )

        self.assertIn("ROOT-01", result.affected_record_ids)


class RevocationWinsBeforeTheFinalActionCheck(unittest.TestCase):
    def test_candidate_read_then_committed_revocation_cannot_dispatch(self) -> None:
        store = _BarrierStore()
        events, _, _, gateway, controller = _world(store)
        store.barrier_enabled = True
        dispatcher = _Dispatcher()
        executions = []

        thread = threading.Thread(
            target=lambda: executions.append(
                gateway.execute(_action("raced"), ("DESC-01",), dispatcher)
            )
        )
        thread.start()
        self.assertTrue(store.candidate_read.wait(timeout=2))
        controller.revoke_receipt_roots(
            revocation_id="revocation-race",
            root_keys=(_root_key(events[0], "ROOT-01"),),
        )
        store.continue_action.set()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(executions), 1)
        self.assertFalse(executions[0].decision.allowed)
        self.assertEqual(executions[0].decision.reason, "REVOKED_AUTHORITY_ROOT")
        self.assertEqual(dispatcher.calls, [])


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value))
    return set()


if __name__ == "__main__":
    unittest.main()
