"""Live Vertex AI Memory Bank, written and deleted per record (D2).

Where `custody/adapters/adk.py` shells the core to fit ADK's own memory
port, this shells it to fit the SDK Memory Bank's `agent_engines` client
actually exposes. Two collaborators: `AgentEngineMemoryBank` is the
`RecordWriter` downstream `CustodyMemoryService` writes through;
`RevokingMemoryBankGraph` is the thin wrapper the day-one findings asked
for, deleting each revoked record's memory alongside the graph's own
removal. Both are additive: neither changes `custody/service.py`'s existing
`ingest_events`-based path, which G1's live proof still uses unmodified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from google.genai.errors import ClientError

from custody.graph import Revocation
from custody.memory_bank import memory_id_for
from custody.origin import Admitted

#: The metadata key `write_record` embeds at admission time, and the one
#: `search_memory` reads back on retrieval. Round-trips through Vertex AI
#: Memory Bank's own `Memory.metadata` field -- not a self-declared parent
#: id from an arbitrary external tool, but Custody's own write recovered
#: on Custody's own read.
CUSTODY_RECORD_ID_KEY = "custody_record_id"


@dataclass(frozen=True)
class RetrievedFact:
    """One search result, with the custody record id if Custody wrote it.

    `record_id` is `None` when the memory carries no `custody_record_id`
    metadata -- a memory written before this field existed, or one written
    by something other than `AgentEngineMemoryBank.write_record`. Absence
    here must not become a guess: `custody.origin`'s resolver falls back to
    content-digest matching for exactly this case, never treats a missing
    id as license to invent one.
    """

    text: str
    record_id: str | None


class AgentEngineMemoriesClient(Protocol):
    """The narrow slice of `agent_engines.memories` this module needs."""

    async def create(self, *, name: str, fact: str, scope: dict, config: dict): ...

    async def retrieve(self, *, name: str, scope: dict, similarity_search_params: dict): ...

    async def delete(self, *, name: str) -> None: ...


@dataclass
class AgentEngineMemoryBank:
    """The `RecordWriter` downstream: one `memories.create` call per trusted
    record, named so it is later deletable by id alone.
    """

    memories: AgentEngineMemoriesClient
    engine_name: str

    async def write_record(
        self, *, app_name: str, user_id: str, admitted: Admitted
    ) -> None:
        memory_id = memory_id_for(admitted.record.id)
        try:
            await self.memories.create(
                name=self.engine_name,
                fact=admitted.text,
                scope={"app_name": app_name, "user_id": user_id},
                config={
                    "memory_id": memory_id,
                    "metadata": {
                        "custody_record_id": {"string_value": admitted.record.id}
                    },
                    "wait_for_completion": True,
                },
            )
        except ClientError as error:
            # A replayed write of the same record: the memory this record
            # maps to already exists, which is the write already having
            # happened, not a failure.
            if error.code != 409:
                raise

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> list[RetrievedFact]:
        pager = await self.memories.retrieve(
            name=self.engine_name,
            scope={"app_name": app_name, "user_id": user_id},
            similarity_search_params={"search_query": query, "top_k": 10},
        )
        results: list[RetrievedFact] = []
        async for retrieved in pager:
            memory = retrieved.memory
            if memory is None or not memory.fact:
                continue
            metadata = getattr(memory, "metadata", None) or {}
            value = metadata.get(CUSTODY_RECORD_ID_KEY)
            record_id = getattr(value, "string_value", None) if value is not None else None
            results.append(RetrievedFact(text=memory.fact, record_id=record_id))
        return results


class RevokableGraph(Protocol):
    """What `RevokingMemoryBankGraph` wraps: `CustodyGraph` and
    `FirestoreCustodyGraph` both already satisfy this."""

    def revoke(self, *, tool: str, revocation_id: str) -> Revocation: ...


@dataclass
class RevokingMemoryBankGraph:
    """Extends a graph's `revoke` to also delete each removed record's
    memory from live Memory Bank, per the mapping `memory_id_for` defines.

    Every id this ever sees was written through `AgentEngineMemoryBank`
    first (only trusted records ever enter a graph via that path), so every
    delete targets a memory that genuinely exists; a 404 is treated as
    already-gone rather than an error, the same idempotency discipline
    `write_record`'s own 409 handling uses.
    """

    graph: RevokableGraph
    memories: AgentEngineMemoriesClient
    engine_name: str

    async def revoke(self, *, tool: str, revocation_id: str) -> Revocation:
        revocation = self.graph.revoke(tool=tool, revocation_id=revocation_id)
        for record_id in revocation.removed:
            name = f"{self.engine_name}/memories/{memory_id_for(record_id)}"
            try:
                await self.memories.delete(name=name)
            except ClientError as error:
                if error.code != 404:
                    raise
        return revocation
