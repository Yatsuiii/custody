"""P5 local Firestore-adapter tests; no cloud project or credentials used.

The fake transaction boundary models only the properties Custody requires:
read-before-write, create-only identity, and all-or-nothing commit.  Prior
E2H-R1E is the real-Firestore/process evidence; these tests prove the B7
adapter's deterministic contract without claiming a new cloud result.
"""

from __future__ import annotations

import os
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

from custody.action import AuthorityAction, AuthorityGateway
from custody.authority import (
    AdmissionGate,
    AuthorityOutput,
    AuthorityUnavailable,
    Capability,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
    TransformRef,
)
from custody.firestore_store import (
    AUTHORITY_DEPENDENCIES_COLLECTION,
    AUTHORITY_RECEIPT_ROOTS_COLLECTION,
    CUSTODY_COLLECTION,
    FirestoreAuthorityStore,
    FirestoreCustodyGraph,
)
from custody.control_plane import _default_plane
from tests.test_firestore_store import FakeFirestoreClient, _record


FIXTURES = Path(__file__).parent / "fixtures" / "b7"
IDENTITY = PolicyKey("finance", "custody", "identity", "R1", "export.send")
REGISTERED = PolicyKey(
    "finance", "custody", "vendor_projection", "R1", "export.send"
)
FREEFORM = PolicyKey("finance", "model", "freeform", "R1", "export.send")


@dataclass
class _Dispatcher:
    calls: list[str] = field(default_factory=list)

    def dispatch(self, action: AuthorityAction) -> object:
        self.calls.append(action.request_id)
        return action.request_id


def _event() -> SourceAuthorityEvent:
    return SourceAuthorityEvent.from_json(
        (FIXTURES / "source_event.json").read_bytes()
    )


def _configure(store: FirestoreAuthorityStore) -> SourceAuthorityEvent:
    event = _event()
    store.put_issuer_key(
        issuer_id=event.receipt.issuer_id,
        issuer_key_id=event.receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key.hex").read_text().strip()
        ),
    )
    store.put_policy(
        PolicySnapshot(
            event.receipt.policy_key,
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
    return event


def _gate(store: FirestoreAuthorityStore) -> AdmissionGate:
    return AdmissionGate(
        store=store,
        source_policy_keys=(_event().receipt.policy_key,),
        identity_policy_key=IDENTITY,
        registered_policy_keys=(REGISTERED,),
        freeform_policy_key=FREEFORM,
    )


def _admit_root(store: FirestoreAuthorityStore, record_id: str = "ROOT-01"):
    event = _event()
    return _gate(store).admit_source(
        event,
        AuthorityOutput(record_id, event.source_object_commitment),
    )


def _action(request_id: str) -> AuthorityAction:
    return AuthorityAction(
        request_id,
        "export.send",
        {"destination": "processor", "value": "ACCOUNT-101"},
    )


class FirestoreAuthorityDurabilityTests(unittest.TestCase):
    def test_fresh_store_reconstructs_graph_and_allows_current_authority(self) -> None:
        client = FakeFirestoreClient()
        first = FirestoreAuthorityStore(client)
        _configure(first)
        self.assertTrue(_admit_root(first).admitted)
        child = _gate(first).admit_registered(
            TransformRef(REGISTERED),
            ("ROOT-01",),
            AuthorityOutput.from_text(
                record_id="CHILD-01", text="ACCOUNT-101"
            ),
        )
        self.assertTrue(child.admitted)
        expected_records = first.records()
        expected_dependencies = first.dependencies("CHILD-01")

        restarted = FirestoreAuthorityStore(client)
        dispatcher = _Dispatcher()
        execution = AuthorityGateway(restarted).execute(
            _action("after-restart"), ("CHILD-01",), dispatcher
        )

        self.assertEqual(restarted.records(), expected_records)
        self.assertEqual(
            restarted.dependencies("CHILD-01"), expected_dependencies
        )
        self.assertTrue(execution.decision.allowed)
        self.assertEqual(dispatcher.calls, ["after-restart"])

    def test_revocation_and_action_linearization_survive_new_instances(self) -> None:
        client = FakeFirestoreClient()
        first = FirestoreAuthorityStore(client)
        event = _configure(first)
        self.assertTrue(_admit_root(first).admitted)
        dispatcher = _Dispatcher()
        allowed = AuthorityGateway(first).execute(
            _action("once"), ("ROOT-01",), dispatcher
        )
        self.assertTrue(allowed.dispatched)
        root_key = ReceiptRootKey.from_receipt(
            event.receipt, custody_root_record_id="ROOT-01"
        )
        RevocationController(FirestoreAuthorityStore(client)).revoke_receipt_roots(
            revocation_id="rev-1", root_keys=(root_key,)
        )

        restarted = FirestoreAuthorityStore(client)
        replay = AuthorityGateway(restarted).execute(
            _action("once"), ("ROOT-01",), dispatcher
        )
        denied = AuthorityGateway(restarted).execute(
            _action("after-revoke"), ("ROOT-01",), dispatcher
        )

        self.assertFalse(replay.dispatched)
        self.assertTrue(replay.decision.allowed)
        self.assertFalse(denied.decision.allowed)
        self.assertEqual(denied.decision.reason, "REVOKED_AUTHORITY_ROOT")
        self.assertEqual(dispatcher.calls, ["once"])
        self.assertEqual(len(restarted.root_revocations()), 1)


class FirestoreAuthorityAtomicityTests(unittest.TestCase):
    def test_failed_multi_document_admission_commits_no_partial_state(self) -> None:
        client = FakeFirestoreClient()
        store = FirestoreAuthorityStore(client)
        _configure(store)
        client.fail_transaction_after_writes = 1

        with self.assertRaises(AuthorityUnavailable):
            _admit_root(store)

        client.fail_transaction_after_writes = None
        restarted = FirestoreAuthorityStore(client)
        self.assertIsNone(restarted.envelope("ROOT-01"))
        self.assertEqual(restarted.dependencies("ROOT-01"), ())
        self.assertEqual(len(client.collection(CUSTODY_COLLECTION).docs), 0)
        self.assertEqual(
            len(client.collection(AUTHORITY_DEPENDENCIES_COLLECTION).docs), 0
        )
        self.assertEqual(
            len(client.collection(AUTHORITY_RECEIPT_ROOTS_COLLECTION).docs), 0
        )
        dispatcher = _Dispatcher()
        denied = AuthorityGateway(restarted).execute(
            _action("after-failure"), ("ROOT-01",), dispatcher
        )
        self.assertFalse(denied.decision.allowed)
        self.assertEqual(dispatcher.calls, [])
        self.assertTrue(_admit_root(restarted).admitted)

    def test_exact_replay_is_idempotent_and_changed_record_is_rejected(self) -> None:
        client = FakeFirestoreClient()
        store = FirestoreAuthorityStore(client)
        _configure(store)

        first = _admit_root(store)
        replay = _admit_root(FirestoreAuthorityStore(client))
        child = _gate(store).admit_registered(
            TransformRef(REGISTERED),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="CHILD-01", text="first"),
        )
        conflict = _gate(FirestoreAuthorityStore(client)).admit_registered(
            TransformRef(REGISTERED),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="CHILD-01", text="second"),
        )

        self.assertEqual(replay, first)
        self.assertTrue(child.admitted)
        self.assertFalse(conflict.admitted)
        self.assertEqual(conflict.reason, "ADMISSION_CONFLICT")
        self.assertEqual(len(store.records()), 2)

    def test_malformed_authoritative_state_denies_instead_of_dispatching(self) -> None:
        client = FakeFirestoreClient()
        store = FirestoreAuthorityStore(client)
        event = _configure(store)
        self.assertTrue(_admit_root(store).admitted)
        policy_document = client.collection("authority_policies").document(
            event.receipt.policy_key.digest
        )
        data, created = policy_document._collection.docs[policy_document.id]
        malformed = dict(data)
        malformed["snapshot"] = {"generation": 7}
        policy_document._collection.docs[policy_document.id] = (
            malformed,
            created,
        )
        dispatcher = _Dispatcher()

        result = AuthorityGateway(FirestoreAuthorityStore(client)).execute(
            _action("corrupt-state"), ("ROOT-01",), dispatcher
        )

        self.assertFalse(result.decision.allowed)
        self.assertEqual(result.decision.reason, "AUTHORITY_STATE_UNAVAILABLE")
        self.assertEqual(dispatcher.calls, [])


class LegacyAndB7FirestoreDocumentsStaySeparate(unittest.TestCase):
    def test_legacy_reload_ignores_b7_records_and_preserves_legacy_records(self) -> None:
        client = FakeFirestoreClient()
        legacy = FirestoreCustodyGraph(client)
        legacy.add(_record(id="LEGACY-01"))
        authority = FirestoreAuthorityStore(client)
        _configure(authority)
        self.assertTrue(_admit_root(authority).admitted)

        restarted_legacy = FirestoreCustodyGraph(client)

        self.assertEqual(
            tuple(record.id for record in restarted_legacy.records()),
            ("LEGACY-01",),
        )
        self.assertEqual(
            tuple(record.record_id for record in authority.records()),
            ("ROOT-01",),
        )

    def test_deployed_default_plane_wires_the_durable_root_controller(self) -> None:
        client = FakeFirestoreClient()
        with (
            patch.dict(
                os.environ,
                {"CUSTODY_FIRESTORE_PROJECT": "b7-local-fixture"},
            ),
            patch("google.cloud.firestore.Client", return_value=client),
            patch("google.cloud.logging.Client", return_value=object()),
        ):
            plane = _default_plane()
        store = FirestoreAuthorityStore(client)
        event = _configure(store)
        self.assertTrue(_admit_root(store).admitted)
        root_key = ReceiptRootKey.from_receipt(
            event.receipt, custody_root_record_id="ROOT-01"
        )

        result = plane.revoke_receipt_roots(
            {
                "revocation_id": "control-plane-revocation",
                "root_keys": [root_key.as_list()],
            }
        )

        self.assertTrue(result["applied"])
        self.assertTrue(store.is_root_revoked(root_key.digest))


if __name__ == "__main__":
    unittest.main()
