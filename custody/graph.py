"""The derivation graph and retroactive revocation.

A custody record's `derived_from` is an edge into a record already in the
graph. Origin labelling gives one hop for free: a model turn derived from the
untrusted tool response that tainted its invocation. `resolve` gives
`take_custody` a second source of edges, a retrieval tool's response matched
by content back to a record this graph already holds, which is how a
restatement written in a later session, possibly a different department,
still ends up with a `derived_from` edge into the original. Nothing here
cares how many hops a record is from the tool that produced it, or which
department wrote it: revocation is graph traversal over `derived_from`, by
walking edges, not by asking who owns the record.

Deletion is preferred over post-filtering because it is also the
right-to-be-forgotten path an enterprise will ask for (`DECISIONS.md` #2).
This module deletes from its own store; wiring that to live Memory Bank
lives one layer up, in `custody/adapters/memory_bank.py`
(`RevokingMemoryBankGraph`), not here, because it needs a live client this
pure module deliberately does not import. Through G1's governed
`ingest_events` write path (ADK's own `add_session_to_memory`), no reliable
mapping exists and none was built: the API returns no created-memory name,
and a same-scope, same-topic second write was observed live overwriting an
earlier memory in place. A second, additive write path
(`custody/service.py`'s `RecordWriter`, backed by
`memories.create(config={"memory_id": memory_id_for(record.id)})`) gives a
real, deterministic mapping instead, live-verified end to end: write two
records, revoke one tool, watch exactly its memory disappear from
`search_memory` while the other's stays. G1's `ingest_events` path is
unchanged and unaffected; only records written through the new path are
deletable this way. See `DECISIONS.md` #2 for both findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from custody.origin import CustodyRecord
from custody.revision import RevisionAlgorithmMismatch, algorithm_of


@dataclass(frozen=True)
class Revocation:
    """A tool demoted, and every record pulled because of it.

    `removed` includes the direct culprits (records whose `source_tool` is the
    demoted tool) and every descendant reached by walking `derived_from`, roots
    included. Append-only once written: `CustodyGraph.revoke` never mutates an
    existing `Revocation`, only returns it again on replay.
    """

    id: str
    tool: str
    removed: tuple[str, ...]
    revision: str | None = None
    #: RFC 3339 revocation time. Same discipline as `CustodyRecord.admitted_at`:
    #: never set by this pure graph, filled in by a durable store from its own
    #: server-assigned write time, and never trusted from an artifact by a judge.
    revoked_at: str | None = None


@dataclass
class CustodyGraph:
    """Every admitted custody record, addressable by id, with derivation edges.

    Interface is three operations: add a record, ask what a tool's revocation
    would remove, and revoke. Everything else, the store, the traversal, the
    idempotency bookkeeping, is internal.
    """

    _records: dict[str, CustodyRecord] = field(default_factory=dict)
    _revocations: dict[str, Revocation] = field(default_factory=dict)

    def add(self, record: CustodyRecord) -> None:
        self._records[record.id] = record

    def extend(self, records: Sequence[CustodyRecord]) -> None:
        for record in records:
            self.add(record)

    def __contains__(self, record_id: str) -> bool:
        return record_id in self._records

    def __len__(self) -> int:
        return len(self._records)

    def records(self) -> tuple[CustodyRecord, ...]:
        return tuple(self._records.values())

    def record(self, record_id: str) -> tuple[CustodyRecord, None] | None:
        """One live record's view, paired with its revocation (always None here).

        This pure graph deletes a record's data on revocation, so it cannot
        answer for a revoked id; only a durable store retains that history.
        Same port as `custody.firestore_store.FirestoreCustodyGraph.record`,
        narrower answer.
        """
        found = self._records.get(record_id)
        return (found, None) if found is not None else None

    def descendants(self, tool: str) -> tuple[str, ...]:
        """Every record id that would be removed if `tool` were revoked now.

        Roots are records whose `source_tool` is `tool`. From there, breadth
        first over `derived_from`, so a restatement of a restatement is found
        regardless of hop count.
        """
        roots = {r.id for r in self._records.values() if r.source_tool == tool}
        return self._walk(roots)

    def descendants_for_revision(self, *, tool: str, revision: str) -> tuple[str, ...]:
        """Every record descended from one exact admitted tool definition.

        Raises if any record for `tool` exists but none was computed under
        `revision`'s digest algorithm: that is a version boundary, not an
        empty result, and returning `()` for it would let a revision-specific
        revocation report success while silently removing nothing.
        """
        stored = {
            r.source_revision
            for r in self._records.values()
            if r.source_tool == tool and r.source_revision
        }
        if stored and algorithm_of(revision) not in {algorithm_of(s) for s in stored}:
            raise RevisionAlgorithmMismatch(
                f"cannot compare revisions for {tool!r}: requested revision "
                f"uses algorithm {algorithm_of(revision)!r}, but stored "
                f"records use {sorted({algorithm_of(s) for s in stored})!r}"
            )
        roots = {
            r.id
            for r in self._records.values()
            if r.source_tool == tool and r.source_revision == revision
        }
        return self._walk(roots)

    def _walk(self, roots: set[str]) -> tuple[str, ...]:
        found = set(roots)
        frontier = roots
        while frontier:
            frontier = {
                r.id
                for r in self._records.values()
                if r.id not in found and set(r.derived_from) & frontier
            }
            found |= frontier
        return tuple(sorted(found))

    def revoke(self, *, tool: str, revocation_id: str) -> Revocation:
        """Demote `tool`, remove every descendant, and log the revocation once.

        Idempotent on `revocation_id`. Replaying it returns the stored
        `Revocation` unchanged: the removed records are already gone, so a
        second traversal finds nothing further, and the id lookup means a
        replay never appends a second audit entry for the same event.
        """
        return self._revoke(tool=tool, revision=None, revocation_id=revocation_id)

    def revoke_revision(
        self, *, tool: str, revision: str, revocation_id: str
    ) -> Revocation:
        """Remove descendants of one tool revision, preserving sibling revisions."""
        return self._revoke(tool=tool, revision=revision, revocation_id=revocation_id)

    def _revoke(
        self, *, tool: str, revision: str | None, revocation_id: str
    ) -> Revocation:
        existing = self._revocations.get(revocation_id)
        if existing is not None:
            return existing
        removed = (
            self.descendants(tool)
            if revision is None
            else self.descendants_for_revision(tool=tool, revision=revision)
        )
        for record_id in removed:
            del self._records[record_id]
        revocation = Revocation(
            id=revocation_id, tool=tool, removed=removed, revision=revision
        )
        self._revocations[revocation_id] = revocation
        return revocation

    def revocations(self) -> tuple[Revocation, ...]:
        return tuple(self._revocations.values())

    def resolve(self, content_sha256: str) -> CustodyRecord | None:
        """The record, if any, whose content this digest matches.

        Text is the only anchor that survives a session boundary: two records
        with the same hash are the same content, regardless of which session,
        invocation, or department produced the read.
        """
        for record in self._records.values():
            if record.content_sha256 == content_sha256:
                return record
        return None
