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
from datetime import datetime

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from custody.catalog import Demotion
from custody.graph import CustodyGraph, Revocation
from custody.origin import CustodyRecord, Origin, Trust
from custody.revision import Admission, ApprovedTool, RevisionCatalog, RuntimeBinding, ToolSurface

CUSTODY_COLLECTION = "custody"
REVOCATIONS_COLLECTION = "revocations"
AUDITOR_COLLECTION = "auditor"
DEMOTIONS_COLLECTION = "demotions"
REVISION_PINS_COLLECTION = "revision_pins"


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
            self._graph.add(_load_record(doc.to_dict(), admitted_at=doc.create_time))
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
            pass
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
            pass
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
