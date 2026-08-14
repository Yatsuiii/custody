"""A durable, cross-process record of which dispatch nonces have been spent.

Deliberately its own module rather than a class in ``custody/firestore_store.py``:
that module already imports ``custody.catalog`` and ``custody.graph`` for its
other collaborators, and this is the one durable backend that gets vendored
into the live MCP export server's Docker build context
(``live/registry_attack/server/``). Vendoring ``firestore_store.py`` there
would drag that whole unrelated dependency graph into the deployed image for
a class that needs none of it. ``FirestoreNonceLedger`` satisfies
``custody.revision.NonceLedger`` structurally (no import of ``revision.py``
required) and depends on nothing beyond ``google.cloud.firestore``.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

DISPATCH_NONCES_COLLECTION = "dispatch_nonces"


@dataclass
class FirestoreNonceLedger:
    """One document per nonce, keyed by the nonce itself.

    ``mark`` is create-fails-if-exists, the same idempotent-write pattern
    every other durable writer in this project uses: a retried mark for a
    nonce already spent is a no-op, not an error. Unbounded growth (spent
    nonces are never pruned) is a known limitation shared with the in-memory
    set it replaces, not a regression introduced here.
    """

    _client: firestore.Client

    def _collection(self):
        return self._client.collection(DISPATCH_NONCES_COLLECTION)

    def seen(self, nonce: str) -> bool:
        return self._collection().document(nonce).get().exists

    def mark(self, nonce: str) -> None:
        try:
            self._collection().document(nonce).create({"nonce": nonce})
        except AlreadyExists:
            pass
