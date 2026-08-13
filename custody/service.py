"""The enforcement point: a memory service that splits by origin before writing.

Enforcing at retrieval was the obvious design and it is wrong. Memory Bank
derives memories server-side from the event stream, so a stored memory is not
byte-identical to any event and cannot be matched back to a custody record after
the fact. Worse, a memory derived from a mix of trusted and untrusted events has
no single origin at all: the provenance is destroyed by the derivation itself.

So the split happens *before* the write. Untrusted content never reaches the
memory service, which means retrieval needs no filter, which is fortunate
because `search_memory(app_name, user_id, query)` does not offer one.

The conservative direction is deliberate. An event carrying any untrusted part
is withheld whole, because parts of one event are derived from each other and
splitting inside an event would let a laundered fragment through. That costs
recall, and the cost is reported rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from custody.catalog import TrustCatalog
from custody.graph import CustodyGraph
from custody.origin import Admitted, CustodyRecord, ToolTrust, Trust, take_custody


class Session(Protocol):
    """Structural view of `google.adk.sessions.Session`."""

    id: str
    app_name: str
    user_id: str
    events: Sequence[object]


class MemoryService(Protocol):
    """The downstream service being governed, e.g. Vertex AI Memory Bank."""

    async def add_session_to_memory(self, session: Session) -> None: ...

    async def search_memory(self, *, app_name: str, user_id: str, query: str): ...


class RecordWriter(Protocol):
    """A downstream that can write one custody record as one deletable
    memory, keyed by the record's own id (`custody/memory_bank.py`).

    Optional and additive: `add_session_to_memory` only ever received raw
    session events, never a record boundary, because that is all
    `ingest_events` needs. A `memory_id`-pinned write needs the boundary
    `add_session_to_memory` doesn't carry, so a downstream that wants
    per-record deletion offers this instead.
    """

    async def write_record(
        self, *, app_name: str, user_id: str, admitted: Admitted
    ) -> None: ...


@dataclass(frozen=True)
class Quarantined:
    """An event withheld from memory, with the reason it was withheld."""

    app_name: str
    user_id: str
    session_id: str
    text: str
    record: CustodyRecord


class QuarantineStore(Protocol):
    def hold(self, item: Quarantined) -> None: ...

    def held(self, *, app_name: str, user_id: str) -> Sequence[Quarantined]: ...


@dataclass
class InMemoryQuarantine:
    """Reference implementation. The Firestore one serves the same port."""

    items: list[Quarantined] = field(default_factory=list)

    def hold(self, item: Quarantined) -> None:
        self.items.append(item)

    def held(self, *, app_name: str, user_id: str) -> Sequence[Quarantined]:
        return [
            i for i in self.items if i.app_name == app_name and i.user_id == user_id
        ]


@dataclass(frozen=True)
class Split:
    """What one session contributed, and what it cost.

    `withheld` is the number G4 asks about: quarantine buys safety with recall,
    and a gate that hides its own price is the thing this project argues against.
    """

    admitted_events: tuple[object, ...] = ()
    withheld_events: tuple[object, ...] = ()
    quarantined: tuple[Quarantined, ...] = ()
    #: The admitted records actually written downstream, trust and all. This is
    #: what a `CustodyGraph` needs to add after the write, so a later session's
    #: retrieval of this content can be attributed back to it.
    trusted: tuple[Admitted, ...] = ()
    refused: int = 0

    @property
    def withheld(self) -> int:
        return len(self.withheld_events)

    @property
    def total(self) -> int:
        return len(self.admitted_events) + len(self.withheld_events)


def split_session(
    session: Session,
    tools: ToolTrust | None = None,
    graph: CustodyGraph | None = None,
) -> Split:
    """Partition a session's events into what may be remembered and what may not.

    Pure with `graph` omitted, so the enforcement rule is testable without a
    memory service at all. With a graph, a `load_memory` response that matches
    content the graph already holds is attributed as a citation, inheriting
    that record's trust and lineage, rather than judged as new, unvouched
    content: see `take_custody`.
    """
    events = list(session.events)
    # Custody is taken over the whole session in one pass, never per event.
    # Taint crosses event boundaries by design: the hostile tool response and
    # the model turn that launders it are different events, and evaluating
    # each alone would clear the laundered copy.
    custody = take_custody(events, tools, resolver=graph)

    untrusted_at = {
        a.event_index
        for a in custody.admitted
        if a.record.trust is Trust.UNTRUSTED
    }
    unattributable_at = {r.event_index for r in custody.refused}

    admitted: list[object] = []
    withheld: list[object] = []
    for index, event in enumerate(events):
        if index in untrusted_at or index in unattributable_at:
            withheld.append(event)
        else:
            admitted.append(event)

    held = [
        Quarantined(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
            text=a.text,
            record=a.record,
        )
        for a in custody.admitted
        if a.record.trust is Trust.UNTRUSTED
    ]
    refused = len(custody.refused)
    trusted = tuple(a for a in custody.admitted if a.record.trust is Trust.TRUSTED)

    return Split(
        admitted_events=tuple(admitted),
        withheld_events=tuple(withheld),
        quarantined=tuple(held),
        trusted=trusted,
        refused=refused,
    )


@dataclass
class _AdmittedSession:
    """A session carrying only the events cleared for memory."""

    id: str
    app_name: str
    user_id: str
    events: Sequence[object]


@dataclass
class CustodyMemoryService:
    """Wraps a memory service so untrusted content never reaches it.

    Deliberately not a subclass of ADK's `BaseMemoryService`: composing over the
    port rather than inheriting from it keeps this testable with a two-method
    stand-in and lets the same object govern any implementation.
    """

    downstream: MemoryService
    quarantine: QuarantineStore
    tools: ToolTrust = field(default_factory=ToolTrust)
    #: The derivation graph. Every trusted record this service writes is added
    #: to it, and every session it splits is checked against it first, so a
    #: `load_memory` retrieval of content this service wrote earlier, in this
    #: session or another, carries a `derived_from` edge back to the original.
    graph: CustodyGraph = field(default_factory=CustodyGraph)
    #: If set with `department`, trust is read fresh from the catalog on every
    #: call instead of from the static `tools` above. This is what makes G4
    #: real rather than assumed: a grant recorded for another department is
    #: structurally invisible here, because `trust_for` never looks at it.
    catalog: TrustCatalog | None = None
    department: str | None = None
    splits: list[Split] = field(default_factory=list)

    def _tools(self) -> ToolTrust:
        if self.catalog is not None and self.department is not None:
            return self.catalog.trust_for(self.department)
        return self.tools

    async def add_session_to_memory(self, session: Session) -> Split:
        split = split_session(session, self._tools(), self.graph)
        for item in split.quarantined:
            self.quarantine.hold(item)
        self.splits.append(split)
        self.graph.extend(a.record for a in split.trusted)

        writer = getattr(self.downstream, "write_record", None)
        if writer is not None:
            # A per-record write, not a session write: only this shape gives
            # each memory the record boundary `memory_id`-pinned deletion
            # needs, which the raw events below never carried.
            for admitted in split.trusted:
                await writer(
                    app_name=session.app_name,
                    user_id=session.user_id,
                    admitted=admitted,
                )
        elif split.admitted_events:
            await self.downstream.add_session_to_memory(
                _AdmittedSession(
                    id=session.id,
                    app_name=session.app_name,
                    user_id=session.user_id,
                    events=split.admitted_events,
                )
            )
        return split

    async def search_memory(self, *, app_name: str, user_id: str, query: str):
        """Delegated unchanged.

        No filtering happens here and none is needed: nothing untrusted was ever
        written, so there is nothing to filter out.
        """
        return await self.downstream.search_memory(
            app_name=app_name, user_id=user_id, query=query
        )

    def recall_cost(self) -> tuple[int, int]:
        """Events withheld, and events seen. The G4 number, always available."""
        withheld = sum(s.withheld for s in self.splits)
        total = sum(s.total for s in self.splits)
        return withheld, total
