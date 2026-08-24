"""Tests for the installed google-cloud-firestore adapter boundary."""

from __future__ import annotations

import inspect
import unittest

from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.transaction import Transaction

from custody.firestore_store import _FirestoreTransactionPort


class _Snapshot:
    exists = True


class _SdkShapeDocument:
    def __init__(self) -> None:
        self.snapshot = _Snapshot()
        self.transaction = None

    def get(self, *, transaction):
        self.transaction = transaction
        return self.snapshot


class _SdkShapeTransaction:
    def __init__(self) -> None:
        self.get_called = False

    def get(self, document):
        self.get_called = True
        return iter((document.snapshot,))


class FirestoreAdapterContractTests(unittest.TestCase):
    def test_installed_sdk_distinguishes_document_and_transaction_reads(self) -> None:
        document_return = str(
            inspect.signature(DocumentReference.get).return_annotation
        )
        transaction_return = str(inspect.signature(Transaction.get).return_annotation)

        self.assertIn("DocumentSnapshot", document_return)
        self.assertIn("Generator", transaction_return)

    def test_transaction_port_returns_one_snapshot_from_real_sdk_shape(self) -> None:
        transaction = _SdkShapeTransaction()
        document = _SdkShapeDocument()

        snapshot = _FirestoreTransactionPort(transaction).get(document)

        self.assertIs(snapshot, document.snapshot)
        self.assertIs(document.transaction, transaction)
        self.assertFalse(transaction.get_called)
