"""Firestore-backed durability for the derivation graph (G5) and the
Provenance Auditor's demotion sweep.

Mirrors `custody.store.SqliteCustodyGraph`: every mutation is persisted to
Firestore as it happens, and the wrapped in-memory `CustodyGraph` is rebuilt
at construction by replaying the persisted log through that same class's own
`add`/`revoke` methods. The algorithm exists in exactly one place either way;
only the durability backend differs from the offline SQLite fake.

Every write is create-fails-if-exists (`AlreadyExists` swallowed as success),
so a replayed ingest or a retried Cloud Scheduler invocation is a no-op
rather than a second write. `admitted_at`/`revoked_at` are stamped from each
document's own server-assigned `create_time` after a successful write, never
from a client clock: a judge that trusts this dataclass field is trusting the
same fact Firestore itself would return on an independent reread, not a
client's claim about it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import threading
from datetime import datetime
from typing import Callable, Iterable, Mapping

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from google.cloud import firestore

from custody.authority import (
    AdmissionEnvelope,
    AdmissionState,
    AuthorityConflict,
    AuthorityDataError,
    AuthorityDecision,
    AuthorityDependency,
    AuthorityReceipt,
    AuthorityStateReader,
    AuthorityUnavailable,
    LinearizedAuthorityDecision,
    PolicyKey,
    PolicySnapshot,
    RootRevocation,
    canonical_json_bytes,
)
from custody.catalog import Demotion
from custody.graph import CustodyGraph, Revocation
from custody.origin import CustodyRecord, Origin, Trust
from custody.revision import Admission, ApprovedTool, RevisionCatalog, RuntimeBinding, ToolSurface

CUSTODY_COLLECTION = "custody"
REVOCATIONS_COLLECTION = "revocations"
AUDITOR_COLLECTION = "auditor"
DEMOTIONS_COLLECTION = "demotions"
REVISION_PINS_COLLECTION = "revision_pins"
AUTHORITY_DEPENDENCIES_COLLECTION = "authority_dependencies"
AUTHORITY_POLICIES_COLLECTION = "authority_policies"
AUTHORITY_ISSUER_KEYS_COLLECTION = "authority_issuer_keys"
AUTHORITY_RECEIPT_ROOTS_COLLECTION = "authority_receipt_roots"
AUTHORITY_REVOCATIONS_COLLECTION = "authority_revocations"
AUTHORITY_REVOKED_ROOTS_COLLECTION = "revoked_receipt_roots"
AUTHORITY_ACTION_DECISIONS_COLLECTION = "authority_action_decisions"


def _dump_record(record: CustodyRecord) -> dict:
    return {
        "origin": record.origin.value,
        "trust": record.trust.value,
        "author": record.author,
        "invocation_id": record.invocation_id,
        "content_sha256": record.content_sha256,
        "source_tool": record.source_tool,
        "source_revision": record.source_revision,
        "id": record.id,
        "derived_from": list(record.derived_from),
    }


def _load_record(data: dict, *, admitted_at: datetime | None) -> CustodyRecord:
    return CustodyRecord(
        origin=Origin(data["origin"]),
        trust=Trust(data["trust"]),
        author=data["author"],
        invocation_id=data["invocation_id"],
        content_sha256=data["content_sha256"],
        source_tool=data.get("source_tool"),
        source_revision=data.get("source_revision"),
        id=data["id"],
        derived_from=tuple(data.get("derived_from", ())),
        admitted_at=admitted_at.isoformat() if admitted_at is not None else None,
    )


def _dump_revocation(revocation: Revocation) -> dict:
    return {
        "id": revocation.id,
        "tool": revocation.tool,
        "removed": list(revocation.removed),
        "revision": revocation.revision,
    }


class FirestoreCustodyGraph:
    """Serves the same port `CustodyGraph` does, durable across cold starts.

    `add`, `revoke`, `records`, `resolve`, `descendants`, `revocations`,
    `__len__`, `__contains__`. Every record ever added is kept in Firestore
    even after a revocation removes it from the live traversal, because the
    log has to outlive the state it produced: a revocation is only provably
    correct if the record it removed is still on record as having existed.
    """

    def __init__(self, client: firestore.Client):
        self._client = client
        self._records_ref = client.collection(CUSTODY_COLLECTION)
        self._revocations_ref = client.collection(REVOCATIONS_COLLECTION)
        self._graph = CustodyGraph()
        self._reload()

    def _reload(self) -> None:
        # Firestore has no cross-document autoincrement; replay causal order
        # is each document's own server-assigned creation time.
        record_docs = sorted(
            self._records_ref.stream(), key=lambda doc: doc.create_time
        )
        for doc in record_docs:
            data = doc.to_dict()
            if "origin" in data:
                self._graph.add(_load_record(data, admitted_at=doc.create_time))
        revocation_docs = sorted(
            self._revocations_ref.stream(), key=lambda doc: doc.create_time
        )
        for doc in revocation_docs:
            data = doc.to_dict()
            self._graph.revoke(tool=data["tool"], revocation_id=data["id"])

    def add(self, record: CustodyRecord) -> None:
        document = self._records_ref.document(record.id)
        try:
            document.create(_dump_record(record))
        except AlreadyExists:
            snapshot = document.get()
            if snapshot.to_dict() != _dump_record(record):
                raise AuthorityConflict(
                    "custody record ID already has different stored bytes"
                )
        create_time = document.get().create_time
        self._graph.add(
            dataclasses.replace(
                record,
                admitted_at=create_time.isoformat() if create_time else None,
            )
        )

    def extend(self, records) -> None:
        for record in records:
            self.add(record)

    def __contains__(self, record_id: str) -> bool:
        return record_id in self._graph

    def __len__(self) -> int:
        return len(self._graph)

    def records(self) -> tuple[CustodyRecord, ...]:
        return self._graph.records()

    def descendants(self, tool: str) -> tuple[str, ...]:
        return self._graph.descendants(tool)

    def resolve(self, content_sha256: str) -> CustodyRecord | None:
        return self._graph.resolve(content_sha256)

    def revoke(self, *, tool: str, revocation_id: str) -> Revocation:
        revocation = self._graph.revoke(tool=tool, revocation_id=revocation_id)
        document = self._revocations_ref.document(revocation_id)
        try:
            document.create(_dump_revocation(revocation))
        except AlreadyExists:
            if document.get().to_dict() != _dump_revocation(revocation):
                raise AuthorityConflict(
                    "revocation ID already has different stored selectors"
                )
        create_time = document.get().create_time
        return dataclasses.replace(
            revocation,
            revoked_at=create_time.isoformat() if create_time else None,
        )

    def revocations(self) -> tuple[Revocation, ...]:
        return self._graph.revocations()

    def record(
        self, record_id: str
    ) -> tuple[CustodyRecord, Revocation | None] | None:
        """One record's durable view, paired with its revocation if any.

        Unlike `resolve`, this is not content-addressed and does not require
        the record to still be live: it reads the append-only log directly,
        because a revoked record must remain readable for G5's proof.
        """
        doc = self._records_ref.document(record_id).get()
        if not doc.exists:
            return None
        record = _load_record(doc.to_dict(), admitted_at=doc.create_time)
        revocation = next(
            (
                revocation
                for revocation in self._graph.revocations()
                if record_id in revocation.removed
            ),
            None,
        )
        if revocation is not None:
            revocation_doc = self._revocations_ref.document(revocation.id).get()
            create_time = revocation_doc.create_time
            revocation = dataclasses.replace(
                revocation,
                revoked_at=create_time.isoformat() if create_time else None,
            )
        return record, revocation


class _FirestoreTransactionPort:
    def __init__(self, transaction) -> None:
        self._transaction = transaction

    def get(self, document):
        return document.get(transaction=self._transaction)

    def create(self, document, data: dict) -> None:
        self._transaction.create(document, data)

    def set(self, document, data: dict) -> None:
        self._transaction.set(document, data)


class FirestoreAuthorityStore:
    """Transactional Firestore implementation of the production B7 port."""

    def __init__(self, client: firestore.Client) -> None:
        self._client = client
        self._custody = client.collection(CUSTODY_COLLECTION)
        self._dependencies = client.collection(AUTHORITY_DEPENDENCIES_COLLECTION)
        self._policies = client.collection(AUTHORITY_POLICIES_COLLECTION)
        self._issuer_keys = client.collection(AUTHORITY_ISSUER_KEYS_COLLECTION)
        self._receipt_roots = client.collection(AUTHORITY_RECEIPT_ROOTS_COLLECTION)
        self._revocations = client.collection(AUTHORITY_REVOCATIONS_COLLECTION)
        self._revoked_roots = client.collection(AUTHORITY_REVOKED_ROOTS_COLLECTION)
        self._decisions = client.collection(AUTHORITY_ACTION_DECISIONS_COLLECTION)
        self._local = threading.local()

    def put_issuer_key(
        self, *, issuer_id: str, issuer_key_id: str, public_key: bytes
    ) -> None:
        if not isinstance(issuer_id, str) or not issuer_id:
            raise AuthorityDataError("issuer_id must be a non-empty string")
        if not isinstance(issuer_key_id, str) or not issuer_key_id:
            raise AuthorityDataError("issuer_key_id must be a non-empty string")
        if not isinstance(public_key, bytes):
            raise AuthorityDataError("issuer public key must be bytes")
        reference = self._issuer_keys.document(
            _identity_digest([issuer_id, issuer_key_id])
        )
        expected = {
            "issuer_id": issuer_id,
            "issuer_key_id": issuer_key_id,
            "public_key_hex": public_key.hex(),
        }

        def write(transaction) -> None:
            snapshot = transaction.get(reference)
            if snapshot.exists:
                if snapshot.to_dict() != expected:
                    raise AuthorityConflict(
                        "issuer key identity already has other bytes"
                    )
                return
            transaction.create(reference, expected)

        self._run_transaction(write)

    def public_key_for(self, *, issuer_id: str, issuer_key_id: str) -> bytes | None:
        reference = self._issuer_keys.document(
            _identity_digest([issuer_id, issuer_key_id])
        )
        snapshot = self._get(reference)
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        if (
            data.get("issuer_id") != issuer_id
            or data.get("issuer_key_id") != issuer_key_id
            or not isinstance(data.get("public_key_hex"), str)
        ):
            raise AuthorityUnavailable("stored issuer key identity is malformed")
        try:
            return bytes.fromhex(data["public_key_hex"])
        except ValueError as error:
            raise AuthorityUnavailable("stored issuer key bytes are malformed") from error

    def put_policy(
        self,
        snapshot: PolicySnapshot,
        *,
        expected_generation: int | None = None,
    ) -> None:
        if not isinstance(snapshot, PolicySnapshot):
            raise AuthorityDataError("policy write requires a PolicySnapshot")
        reference = self._policies.document(snapshot.policy_key.digest)
        expected = {"snapshot": snapshot.as_dict()}

        def write(transaction) -> None:
            stored = transaction.get(reference)
            if not stored.exists:
                if expected_generation is not None:
                    raise AuthorityConflict("policy does not have expected generation")
                transaction.create(reference, expected)
                return
            current = _firestore_policy(stored.to_dict())
            if current == snapshot:
                return
            if (
                current.policy_key != snapshot.policy_key
                or expected_generation is None
                or current.generation != expected_generation
                or snapshot.generation != expected_generation + 1
            ):
                raise AuthorityConflict("policy generation compare-and-set failed")
            transaction.set(reference, expected)

        self._run_transaction(write)

    def policy(self, key: PolicyKey) -> PolicySnapshot | None:
        try:
            snapshot = self._get(self._policies.document(key.digest))
            if not snapshot.exists:
                return None
            policy = _firestore_policy(snapshot.to_dict())
            if policy.policy_key != key:
                raise AuthorityDataError(
                    "stored PolicyKey digest does not match fields"
                )
            return policy
        except AuthorityDataError as error:
            raise AuthorityUnavailable("stored B7 policy is malformed") from error

    def commit_admission(
        self,
        envelope: AdmissionEnvelope,
        dependencies: tuple[AuthorityDependency, ...],
        *,
        expected_policies: Mapping[PolicyKey, int],
        receipt_binding_digest: str | None = None,
    ) -> AdmissionEnvelope:
        _validate_firestore_admission(envelope, dependencies)
        if receipt_binding_digest is not None:
            _firestore_sha256(receipt_binding_digest, "receipt_binding_digest")
        record_ref = self._record_ref(envelope.record_id)
        canonical_dependencies = tuple(
            sorted(dependencies, key=lambda item: item.canonical_bytes())
        )
        dependency_refs = tuple(
            (
                self._dependencies.document(dependency.digest),
                dependency,
            )
            for dependency in canonical_dependencies
        )
        receipt_ref = (
            None
            if receipt_binding_digest is None
            else self._receipt_roots.document(receipt_binding_digest)
        )
        expected_document = {
            "record_kind": "b7",
            "b7_envelope": envelope.as_dict(),
            "b7_dependencies": [item.as_dict() for item in canonical_dependencies],
            "receipt_binding_digest": receipt_binding_digest,
            "b7_created_at": firestore.SERVER_TIMESTAMP,
        }

        def write(transaction) -> AdmissionEnvelope:
            stored_record = transaction.get(record_ref)
            policy_snapshots = {
                key: transaction.get(self._policies.document(key.digest))
                for key in expected_policies
            }
            parent_snapshots = {
                parent_id: transaction.get(self._record_ref(parent_id))
                for parent_id in envelope.direct_parent_ids
            }
            stored_dependencies = {
                dependency.digest: transaction.get(reference)
                for reference, dependency in dependency_refs
            }
            stored_receipt = (
                None if receipt_ref is None else transaction.get(receipt_ref)
            )

            if stored_record.exists:
                data = stored_record.to_dict()
                stored_envelope, stored_items, stored_binding = (
                    _firestore_envelope_document(data)
                )
                if (
                    stored_envelope != envelope
                    or stored_items != canonical_dependencies
                    or stored_binding != receipt_binding_digest
                ):
                    raise AuthorityConflict(
                        "record ID already has other authority bytes"
                    )
                self._require_replay_side_documents(
                    envelope,
                    canonical_dependencies,
                    stored_dependencies,
                    receipt_binding_digest,
                    stored_receipt,
                )
                return stored_envelope

            for key, generation in expected_policies.items():
                stored_policy = policy_snapshots[key]
                if (
                    not stored_policy.exists
                    or _firestore_policy(stored_policy.to_dict()).generation
                    != generation
                ):
                    raise AuthorityConflict("policy changed during admission")
            for parent_id, parent_snapshot in parent_snapshots.items():
                if not parent_snapshot.exists:
                    raise AuthorityConflict("required parent is missing")
                parent, _, _ = _firestore_envelope_document(
                    parent_snapshot.to_dict()
                )
                if parent.admission_state is not AdmissionState.COMMITTED:
                    raise AuthorityConflict("required parent is incomplete")
            for reference, dependency in dependency_refs:
                stored = stored_dependencies[dependency.digest]
                if stored.exists:
                    if _firestore_dependency(stored.to_dict()) != dependency:
                        raise AuthorityConflict(
                            "dependency identity already has other bytes"
                        )
                    raise AuthorityConflict(
                        "dependency exists without its authority envelope"
                    )
            if stored_receipt is not None and stored_receipt.exists:
                data = stored_receipt.to_dict()
                if data.get("root_record_id") != envelope.record_id:
                    raise AuthorityConflict(
                        "receipt is already bound to another root"
                    )
                raise AuthorityConflict("receipt root exists without its envelope")

            transaction.create(record_ref, expected_document)
            for reference, dependency in dependency_refs:
                transaction.create(
                    reference,
                    {
                        "record_id": dependency.record_id,
                        "root_key_digest": dependency.root_key_digest,
                        "dependency": dependency.as_dict(),
                    },
                )
            if receipt_ref is not None:
                transaction.create(
                    receipt_ref,
                    {
                        "receipt_binding_digest": receipt_binding_digest,
                        "root_record_id": envelope.record_id,
                    },
                )
            return envelope

        return self._run_transaction(write)

    def envelope(self, record_id: str) -> AdmissionEnvelope | None:
        try:
            snapshot = self._get(self._record_ref(record_id))
            if not snapshot.exists:
                return None
            envelope, _, _ = _firestore_envelope_document(snapshot.to_dict())
            if envelope.record_id != record_id:
                raise AuthorityDataError(
                    "stored record ID does not match envelope"
                )
            return envelope
        except AuthorityDataError as error:
            raise AuthorityUnavailable("stored B7 envelope is malformed") from error

    def dependencies(self, record_id: str) -> tuple[AuthorityDependency, ...]:
        try:
            snapshot = self._get(self._record_ref(record_id))
            if not snapshot.exists:
                return ()
            envelope, dependencies, _ = _firestore_envelope_document(
                snapshot.to_dict()
            )
            if envelope.record_id != record_id or any(
                dependency.record_id != record_id for dependency in dependencies
            ):
                raise AuthorityDataError(
                    "stored B7 dependency identity is malformed"
                )
            return dependencies
        except AuthorityDataError as error:
            raise AuthorityUnavailable(
                "stored B7 dependencies are malformed"
            ) from error

    def records(self) -> tuple[AdmissionEnvelope, ...]:
        try:
            records = []
            for snapshot in self._custody.stream():
                data = snapshot.to_dict()
                if data.get("record_kind") == "b7":
                    records.append(_firestore_envelope_document(data)[0])
            return tuple(sorted(records, key=lambda item: item.record_id))
        except (GoogleAPICallError, AuthorityDataError, KeyError, TypeError) as error:
            raise AuthorityUnavailable("B7 Firestore record scan failed") from error

    def root_record_id_for_receipt(
        self, receipt: AuthorityReceipt
    ) -> str | None:
        snapshot = self._get(self._receipt_roots.document(receipt.binding_digest))
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        if data.get("receipt_binding_digest") != receipt.binding_digest:
            raise AuthorityUnavailable("stored receipt binding digest is malformed")
        record_id = data.get("root_record_id")
        if not isinstance(record_id, str) or not record_id:
            raise AuthorityUnavailable("stored receipt root ID is malformed")
        return record_id

    def is_root_revoked(self, root_key_digest: str) -> bool:
        _firestore_sha256(root_key_digest, "root_key_digest")
        snapshot = self._get(self._revoked_roots.document(root_key_digest))
        if not snapshot.exists:
            return False
        data = snapshot.to_dict()
        if data.get("root_key_digest") != root_key_digest:
            raise AuthorityUnavailable("stored revoked-root marker is malformed")
        return True

    def linearize_action(
        self,
        *,
        request_id: str,
        request_digest: str,
        decide: Callable[[AuthorityStateReader], AuthorityDecision],
    ) -> LinearizedAuthorityDecision:
        reference = self._decisions.document(_identity_digest([request_id]))

        def write(transaction) -> LinearizedAuthorityDecision:
            stored = transaction.get(reference)
            if stored.exists:
                data = stored.to_dict()
                if (
                    data.get("request_id") != request_id
                    or data.get("request_digest") != request_digest
                ):
                    raise AuthorityConflict(
                        "action request ID already has different request bytes"
                    )
                try:
                    decision = _firestore_decision(data)
                except AuthorityDataError as error:
                    raise AuthorityUnavailable(
                        "stored B7 action decision is malformed"
                    ) from error
                return LinearizedAuthorityDecision(decision, False)
            self._local.transaction = transaction
            try:
                decision = decide(self)
            finally:
                del self._local.transaction
            if (
                not isinstance(decision, AuthorityDecision)
                or decision.request_id != request_id
                or decision.request_digest != request_digest
            ):
                raise AuthorityDataError(
                    "action decision does not match its linearization request"
                )
            transaction.create(
                reference,
                {
                    "request_id": request_id,
                    "request_digest": request_digest,
                    "decision": decision.as_dict(),
                    "decided_at": firestore.SERVER_TIMESTAMP,
                },
            )
            return LinearizedAuthorityDecision(decision, True)

        return self._run_transaction(write)

    def action_decisions(self) -> tuple[AuthorityDecision, ...]:
        try:
            return tuple(
                sorted(
                    (_firestore_decision(snapshot.to_dict()) for snapshot in self._decisions.stream()),
                    key=lambda decision: decision.request_id,
                )
            )
        except (GoogleAPICallError, AuthorityDataError, KeyError, TypeError) as error:
            raise AuthorityUnavailable("B7 Firestore decision scan failed") from error

    def commit_root_revocation(
        self, revocation: RootRevocation
    ) -> RootRevocation:
        if not isinstance(revocation, RootRevocation):
            raise AuthorityDataError(
                "root revocation write requires RootRevocation"
            )
        reference = self._revocations.document(
            _identity_digest([revocation.revocation_id])
        )
        marker_refs = tuple(
            (self._revoked_roots.document(root_key.digest), root_key)
            for root_key in revocation.root_keys
        )

        def write(transaction) -> RootRevocation:
            stored_event = transaction.get(reference)
            stored_markers = {
                root_key.digest: transaction.get(marker)
                for marker, root_key in marker_refs
            }
            if stored_event.exists:
                existing = _firestore_revocation(stored_event.to_dict())
                if existing.selector_bytes() != revocation.selector_bytes():
                    raise AuthorityConflict(
                        "revocation ID already has other receipt-root selectors"
                    )
                for _, root_key in marker_refs:
                    marker = stored_markers[root_key.digest]
                    if not marker.exists:
                        raise AuthorityConflict(
                            "revocation event is missing an authoritative marker"
                        )
                return existing
            transaction.create(
                reference,
                {
                    "revocation": revocation.as_dict(),
                    "revoked_at": firestore.SERVER_TIMESTAMP,
                },
            )
            for marker, root_key in marker_refs:
                stored = stored_markers[root_key.digest]
                if not stored.exists:
                    transaction.create(
                        marker,
                        {
                            "root_key_digest": root_key.digest,
                            "root_key": root_key.as_list(),
                            "first_revocation_id": revocation.revocation_id,
                            "revoked_at": firestore.SERVER_TIMESTAMP,
                        },
                    )
            return revocation

        return self._run_transaction(write)

    def affected_record_ids(
        self, root_key_digests: Iterable[str]
    ) -> tuple[str, ...]:
        digests = frozenset(root_key_digests)
        for digest in digests:
            _firestore_sha256(digest, "root_key_digest")
        try:
            affected: set[str] = set()
            for snapshot in self._dependencies.stream():
                data = snapshot.to_dict()
                dependency = _firestore_dependency(data)
                if dependency.root_key_digest in digests:
                    affected.add(dependency.record_id)
            return tuple(sorted(affected))
        except (
            GoogleAPICallError,
            AuthorityDataError,
            KeyError,
            TypeError,
        ) as error:
            raise AuthorityUnavailable(
                "B7 Firestore reverse dependency read failed"
            ) from error

    def root_revocations(self) -> tuple[RootRevocation, ...]:
        try:
            return tuple(
                sorted(
                    (
                        _firestore_revocation(snapshot.to_dict())
                        for snapshot in self._revocations.stream()
                    ),
                    key=lambda item: item.revocation_id,
                )
            )
        except (GoogleAPICallError, AuthorityDataError, KeyError, TypeError) as error:
            raise AuthorityUnavailable("B7 Firestore revocation scan failed") from error

    def _record_ref(self, record_id: str):
        if not isinstance(record_id, str) or not record_id or "/" in record_id:
            raise AuthorityDataError(
                "Firestore B7 record IDs must be non-empty document IDs"
            )
        return self._custody.document(record_id)

    def _get(self, reference):
        transaction = getattr(self._local, "transaction", None)
        try:
            return (
                reference.get()
                if transaction is None
                else transaction.get(reference)
            )
        except GoogleAPICallError as error:
            raise AuthorityUnavailable("B7 Firestore read failed") from error

    def _run_transaction(self, operation):
        try:
            fake_runner = getattr(self._client, "run_transaction", None)
            if fake_runner is not None:
                return fake_runner(operation)
            raw_transaction = self._client.transaction()

            @firestore.transactional
            def run(transaction):
                return operation(_FirestoreTransactionPort(transaction))

            return run(raw_transaction)
        except (AuthorityConflict, AuthorityDataError, AuthorityUnavailable):
            raise
        except (GoogleAPICallError, ValueError) as error:
            raise AuthorityUnavailable("B7 Firestore transaction failed") from error

    @staticmethod
    def _require_replay_side_documents(
        envelope: AdmissionEnvelope,
        dependencies: tuple[AuthorityDependency, ...],
        stored_dependencies: Mapping[str, object],
        receipt_binding_digest: str | None,
        stored_receipt: object | None,
    ) -> None:
        for dependency in dependencies:
            snapshot = stored_dependencies[dependency.digest]
            if not snapshot.exists or _firestore_dependency(snapshot.to_dict()) != dependency:
                raise AuthorityConflict(
                    "authority envelope is missing an exact dependency row"
                )
        if receipt_binding_digest is not None:
            if stored_receipt is None or not stored_receipt.exists:
                raise AuthorityConflict(
                    "authority root is missing its receipt binding row"
                )
            data = stored_receipt.to_dict()
            if (
                data.get("receipt_binding_digest") != receipt_binding_digest
                or data.get("root_record_id") != envelope.record_id
            ):
                raise AuthorityConflict("receipt binding row has different bytes")


def _identity_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _firestore_policy(data: Mapping[str, object]) -> PolicySnapshot:
    raw = data.get("snapshot")
    if not isinstance(raw, Mapping):
        raise AuthorityDataError("stored Firestore policy is malformed")
    return PolicySnapshot.from_mapping(raw)


def _firestore_envelope_document(
    data: Mapping[str, object],
) -> tuple[AdmissionEnvelope, tuple[AuthorityDependency, ...], str | None]:
    if data.get("record_kind") != "b7":
        raise AuthorityDataError("custody document is not a B7 authority record")
    raw_envelope = data.get("b7_envelope")
    raw_dependencies = data.get("b7_dependencies")
    binding = data.get("receipt_binding_digest")
    if not isinstance(raw_envelope, Mapping) or not isinstance(raw_dependencies, list):
        raise AuthorityDataError("stored Firestore envelope is malformed")
    if binding is not None and not isinstance(binding, str):
        raise AuthorityDataError("stored receipt binding is malformed")
    if binding is not None:
        _firestore_sha256(binding, "stored receipt binding")
    envelope = AdmissionEnvelope.from_mapping(raw_envelope)
    dependencies = tuple(
        sorted(
            (
                AuthorityDependency.from_mapping(item)
                for item in raw_dependencies
                if isinstance(item, Mapping)
            ),
            key=lambda item: item.canonical_bytes(),
        )
    )
    if len(dependencies) != len(raw_dependencies):
        raise AuthorityDataError("stored dependency list is malformed")
    return envelope, dependencies, binding


def _firestore_dependency(data: Mapping[str, object]) -> AuthorityDependency:
    raw = data.get("dependency")
    if not isinstance(raw, Mapping):
        raise AuthorityDataError("stored Firestore dependency is malformed")
    dependency = AuthorityDependency.from_mapping(raw)
    if (
        data.get("record_id") != dependency.record_id
        or data.get("root_key_digest") != dependency.root_key_digest
    ):
        raise AuthorityDataError(
            "stored Firestore dependency index does not match dependency"
        )
    return dependency


def _firestore_decision(data: Mapping[str, object]) -> AuthorityDecision:
    raw = data.get("decision")
    if not isinstance(raw, Mapping):
        raise AuthorityDataError("stored Firestore decision is malformed")
    return AuthorityDecision.from_mapping(raw)


def _firestore_revocation(data: Mapping[str, object]) -> RootRevocation:
    raw = data.get("revocation")
    if not isinstance(raw, Mapping):
        raise AuthorityDataError("stored Firestore revocation is malformed")
    return RootRevocation.from_mapping(raw)


def _validate_firestore_admission(
    envelope: AdmissionEnvelope,
    dependencies: tuple[AuthorityDependency, ...],
) -> None:
    if not isinstance(envelope, AdmissionEnvelope):
        raise AuthorityDataError("admission write requires an AdmissionEnvelope")
    if not isinstance(dependencies, tuple) or any(
        not isinstance(item, AuthorityDependency) for item in dependencies
    ):
        raise AuthorityDataError("admission dependencies must be a tuple")
    if any(item.record_id != envelope.record_id for item in dependencies):
        raise AuthorityDataError("dependency belongs to a different record")


def _firestore_sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AuthorityDataError(f"{field} must be lowercase SHA-256 hex")
    return value


def _dump_pin(tool: ApprovedTool) -> dict:
    return {
        "runtime_name": tool.runtime_name,
        "revision": tool.revision,
        "runtime_binding": (
            {
                "revision_name": tool.runtime_binding.revision_name,
                "image_digest": tool.runtime_binding.image_digest,
            }
            if tool.runtime_binding is not None
            else None
        ),
    }


def _load_pin(tool_id: str, data: dict) -> ApprovedTool:
    binding_data = data.get("runtime_binding")
    return ApprovedTool(
        tool_id=tool_id,
        runtime_name=data["runtime_name"],
        revision=data["revision"],
        runtime_binding=(
            RuntimeBinding(binding_data["revision_name"], binding_data["image_digest"])
            if binding_data
            else None
        ),
    )


class FirestoreRevisionCatalog:
    """Serves the same port ``RevisionCatalog`` does, durable across cold
    starts: approved pins survive a restart and are visible to every
    instance sharing this Firestore project.

    Unlike ``FirestoreCustodyGraph``, there is no in-memory replica to
    replay at construction. ``approve`` and ``admit`` each read or write
    straight through to Firestore, one document per department. Caching a
    local replica here would reintroduce exactly the stale-vs-live mismatch
    class the revision digest check itself exists to close, for the sake of
    a write path that is rare (department onboarding) serving a read path
    that is the actual security-relevant one (every admission decision).

    ``admit`` delegates the comparison itself to a throwaway in-memory
    ``RevisionCatalog`` loaded from the read pins, so the admission
    algorithm exists in exactly one place regardless of which durability
    backend is in use, the same discipline ``FirestoreCustodyGraph``
    documents for the derivation graph.
    """

    def __init__(self, client: firestore.Client):
        self._collection = client.collection(REVISION_PINS_COLLECTION)

    def approve(
        self,
        *,
        department: str,
        surface: ToolSurface,
        runtime_binding: RuntimeBinding | None = None,
    ) -> None:
        pins = {
            tool.tool_id: _dump_pin(
                ApprovedTool(tool.tool_id, tool.runtime_name, tool.revision, runtime_binding)
            )
            for tool in surface.tools
        }
        self._collection.document(department).set({"pins": pins}, merge=True)

    def admit(
        self,
        *,
        department: str,
        surface: ToolSurface,
        observed_runtime: RuntimeBinding | None = None,
    ) -> Admission:
        doc = self._collection.document(department).get()
        pins = (doc.to_dict() or {}).get("pins", {}) if doc.exists else {}
        catalog = RevisionCatalog()
        for tool_id, data in pins.items():
            catalog._approved[(department, tool_id)] = _load_pin(tool_id, data)
        return catalog.admit(
            department=department, surface=surface, observed_runtime=observed_runtime
        )


class FirestoreAuditorLog:
    """The durable heartbeat log behind `ControlPlane.auditor`.

    One document per UTC day, create-fails-if-exists, so a retried Cloud
    Scheduler invocation on the same day is a no-op rather than a second
    write. `first_run` is answered by whether any heartbeat document exists
    yet, read before the write that would make it non-empty.
    """

    def __init__(self, client: firestore.Client):
        self._collection = client.collection(AUDITOR_COLLECTION)

    def heartbeat(self, day: str) -> bool:
        first = next(self._collection.limit(1).stream(), None) is None
        try:
            self._collection.document(day).create({"day": day})
        except AlreadyExists:
            pass
        return first


class FirestoreDemotionLog:
    """The durable record of every applied demotion, behind the Auditor's
    sweep.

    `TrustCatalog` stays in-memory (it is `departments/grants`, deliberately
    still PLANNED); this collection exists only so a demotion survives a
    cold start between the `/demote` call that recorded it and the later
    Cloud Scheduler tick that sweeps it, the same "genuinely elapsed time"
    property G5 already proved for the seed record. One document per
    demotion, keyed by `Demotion.id()` (deterministic), so a retried
    `/demote` call is a no-op rather than a second entry.
    """

    def __init__(self, client: firestore.Client):
        self._collection = client.collection(DEMOTIONS_COLLECTION)

    def record(self, demotion: Demotion) -> None:
        try:
            self._collection.document(demotion.id()).create(
                {
                    "department": demotion.department,
                    "tool": demotion.tool,
                    "demoted_by": demotion.demoted_by,
                    "demoted_at": demotion.demoted_at,
                }
            )
        except AlreadyExists:
            pass

    def all(self) -> tuple[Demotion, ...]:
        return tuple(
            Demotion(
                actor_department=data["department"],
                department=data["department"],
                tool=data["tool"],
                demoted_by=data["demoted_by"],
                demoted_at=data["demoted_at"],
            )
            for data in (doc.to_dict() for doc in self._collection.stream())
        )
