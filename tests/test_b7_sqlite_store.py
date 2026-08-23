"""P5 SQLite durability, process reconstruction, contention, and rollback."""

from __future__ import annotations

import dataclasses
import multiprocessing
import threading
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from custody.action import AuthorityAction, AuthorityGateway
from custody.authority import (
    AdmissionGate,
    AuthorityConflict,
    AuthorityOutput,
    Capability,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
    TransformRef,
)
from custody.store import SqliteAuthorityStore


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


def _configure(store: SqliteAuthorityStore) -> SourceAuthorityEvent:
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


def _gate(store: SqliteAuthorityStore) -> AdmissionGate:
    return AdmissionGate(
        store=store,
        source_policy_keys=(_event().receipt.policy_key,),
        identity_policy_key=IDENTITY,
        registered_policy_keys=(REGISTERED,),
        freeform_policy_key=FREEFORM,
    )


def _admit_root(store: SqliteAuthorityStore, record_id: str = "ROOT-01"):
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


def _blocked_writer(path: str, ready) -> None:
    store = SqliteAuthorityStore(path)

    def block_before_dependency() -> int:
        ready.set()
        threading.Event().wait(timeout=30)
        return 0

    store._connection.create_function("block_b7_dependency", 0, block_before_dependency)
    store._connection.execute(
        "CREATE TEMP TRIGGER block_b7_dependency_write "
        "BEFORE INSERT ON authority_dependency "
        "BEGIN SELECT block_b7_dependency(); END"
    )
    _admit_root(store)


class DurableAuthorityReconstructsInFreshProcesses(unittest.TestCase):
    def test_records_dependencies_keys_policies_and_allow_survive_restart(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "authority.db"
            first = SqliteAuthorityStore(path)
            event = _configure(first)
            root = _admit_root(first)
            self.assertTrue(root.admitted)
            child = _gate(first).admit_registered(
                TransformRef(REGISTERED),
                ("ROOT-01",),
                AuthorityOutput.from_text(record_id="CHILD-01", text="ACCOUNT-101"),
            )
            self.assertTrue(child.admitted)
            expected_envelopes = first.records()
            expected_dependencies = first.dependencies("CHILD-01")
            first.close()

            reopened = SqliteAuthorityStore(path)
            dispatcher = _Dispatcher()
            execution = AuthorityGateway(reopened).execute(
                _action("after-restart"), ("CHILD-01",), dispatcher
            )

            self.assertEqual(reopened.records(), expected_envelopes)
            self.assertEqual(
                reopened.dependencies("CHILD-01"), expected_dependencies
            )
            self.assertEqual(
                reopened.public_key_for(
                    issuer_id=event.receipt.issuer_id,
                    issuer_key_id=event.receipt.issuer_key_id,
                ),
                bytes.fromhex(
                    (FIXTURES / "issuer_public_key.hex").read_text().strip()
                ),
            )
            self.assertTrue(execution.decision.allowed)
            self.assertEqual(dispatcher.calls, ["after-restart"])
            reopened.close()

    def test_revocation_and_action_idempotency_survive_restart(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "authority.db"
            first = SqliteAuthorityStore(path)
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
            RevocationController(first).revoke_receipt_roots(
                revocation_id="rev-1", root_keys=(root_key,)
            )
            first.close()

            reopened = SqliteAuthorityStore(path)
            replay = AuthorityGateway(reopened).execute(
                _action("once"), ("ROOT-01",), dispatcher
            )
            denied = AuthorityGateway(reopened).execute(
                _action("after-revoke"), ("ROOT-01",), dispatcher
            )

            self.assertFalse(replay.dispatched)
            self.assertTrue(replay.decision.allowed)
            self.assertFalse(denied.decision.allowed)
            self.assertEqual(denied.decision.reason, "REVOKED_AUTHORITY_ROOT")
            self.assertEqual(dispatcher.calls, ["once"])
            self.assertEqual(len(reopened.root_revocations()), 1)
            reopened.close()


class DurableWritesAreImmutableAndAtomic(unittest.TestCase):
    def test_exact_replay_is_idempotent_and_changed_record_is_a_conflict(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "authority.db"
            store = SqliteAuthorityStore(path)
            _configure(store)
            first = _admit_root(store)
            replay = _admit_root(store)
            changed = _gate(store).admit_registered(
                TransformRef(REGISTERED),
                ("ROOT-01",),
                AuthorityOutput.from_text(record_id="CHILD-01", text="first"),
            )
            conflict = _gate(store).admit_registered(
                TransformRef(REGISTERED),
                ("ROOT-01",),
                AuthorityOutput.from_text(record_id="CHILD-01", text="second"),
            )

            self.assertEqual(replay, first)
            self.assertTrue(changed.admitted)
            self.assertFalse(conflict.admitted)
            self.assertEqual(conflict.reason, "ADMISSION_CONFLICT")
            self.assertEqual(len(store.records()), 2)
            store.close()

    def test_killed_writer_leaves_no_partial_authoritative_record(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "authority.db"
            bootstrap = SqliteAuthorityStore(path)
            _configure(bootstrap)
            bootstrap.close()
            context = multiprocessing.get_context("spawn")
            ready = context.Event()
            process = context.Process(
                target=_blocked_writer,
                args=(str(path), ready),
            )
            process.start()
            self.assertTrue(ready.wait(timeout=5))
            process.kill()
            process.join(timeout=5)
            self.assertFalse(process.is_alive())

            recovered = SqliteAuthorityStore(path)
            self.assertIsNone(recovered.envelope("ROOT-01"))
            self.assertEqual(recovered.dependencies("ROOT-01"), ())
            dispatcher = _Dispatcher()
            immediate = AuthorityGateway(recovered).execute(
                _action("after-kill"), ("ROOT-01",), dispatcher
            )
            self.assertFalse(immediate.decision.allowed)
            self.assertEqual(dispatcher.calls, [])
            retry = _admit_root(recovered)
            self.assertTrue(retry.admitted)
            self.assertEqual(len(recovered.records()), 1)
            recovered.close()

    def test_policy_compare_and_set_has_one_winner_under_contention(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "authority.db"
            bootstrap = SqliteAuthorityStore(path)
            event = _configure(bootstrap)
            current = bootstrap.policy(event.receipt.policy_key)
            assert current is not None
            bootstrap.close()
            stores = (SqliteAuthorityStore(path), SqliteAuthorityStore(path))
            snapshots = (
                dataclasses.replace(current, version="v8-act", generation=8),
                dataclasses.replace(
                    current,
                    version="v8-inform",
                    generation=8,
                    caps={"export.send": Capability.INFORM},
                ),
            )
            barrier = threading.Barrier(2)
            outcomes: list[str] = []

            def update(index: int) -> None:
                barrier.wait()
                try:
                    stores[index].put_policy(
                        snapshots[index], expected_generation=7
                    )
                    outcomes.append("committed")
                except AuthorityConflict:
                    outcomes.append("conflict")

            threads = [threading.Thread(target=update, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertEqual(sorted(outcomes), ["committed", "conflict"])
            final = stores[0].policy(event.receipt.policy_key)
            self.assertIn(final, snapshots)
            for store in stores:
                store.close()


if __name__ == "__main__":
    unittest.main()
