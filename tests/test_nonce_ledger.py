"""Offline tests for the Firestore-backed durable nonce ledger.

Same fake-client pattern as ``tests/test_firestore_store.py``: a document
create-fails-if-exists, shared across instances, standing in for two live
processes (or one process before and after a restart) sharing one Firestore
project.
"""

from __future__ import annotations

import unittest

from google.api_core.exceptions import AlreadyExists

from custody.nonce_ledger import FirestoreNonceLedger


class _FakeSnapshot:
    def __init__(self, exists: bool) -> None:
        self.exists = exists


class _FakeDocument:
    def __init__(self, collection: "_FakeCollection", doc_id: str) -> None:
        self._collection = collection
        self.id = doc_id

    def create(self, data: dict) -> None:
        if self.id in self._collection.docs:
            raise AlreadyExists(f"{self.id} already exists")
        self._collection.docs[self.id] = dict(data)

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self.id in self._collection.docs)


class _FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self, doc_id)


class FakeFirestoreClient:
    """Backing store that survives across ``FirestoreNonceLedger`` instances,
    mirroring the point of the real thing: two ledgers against the same
    client must agree on which nonces are spent."""

    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollection] = {}

    def collection(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())


class FirestoreNonceLedgerTests(unittest.TestCase):
    def test_an_unmarked_nonce_is_not_seen(self) -> None:
        ledger = FirestoreNonceLedger(FakeFirestoreClient())
        self.assertFalse(ledger.seen("nonce-1"))

    def test_a_marked_nonce_is_seen_by_the_same_instance(self) -> None:
        ledger = FirestoreNonceLedger(FakeFirestoreClient())
        ledger.mark("nonce-1")
        self.assertTrue(ledger.seen("nonce-1"))

    def test_a_second_instance_against_the_same_client_sees_the_mark(self) -> None:
        """The actual durability property: this is what a fresh Cloud Run
        process (after a restart, or a second instance) needs to correctly
        refuse a replayed token it never personally minted or consumed."""
        client = FakeFirestoreClient()
        first_process = FirestoreNonceLedger(client)
        second_process = FirestoreNonceLedger(client)

        first_process.mark("nonce-1")

        self.assertTrue(second_process.seen("nonce-1"))

    def test_marking_the_same_nonce_twice_is_a_no_op_not_an_error(self) -> None:
        ledger = FirestoreNonceLedger(FakeFirestoreClient())
        ledger.mark("nonce-1")
        ledger.mark("nonce-1")
        self.assertTrue(ledger.seen("nonce-1"))

    def test_two_unrelated_clients_do_not_share_state(self) -> None:
        first_client = FakeFirestoreClient()
        second_client = FakeFirestoreClient()
        FirestoreNonceLedger(first_client).mark("nonce-1")

        self.assertFalse(FirestoreNonceLedger(second_client).seen("nonce-1"))


if __name__ == "__main__":
    unittest.main()
