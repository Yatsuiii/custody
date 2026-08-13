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

    async def search_memory(self, *, app_name: str, user_id: str, query: str):
        pager = await self.memories.retrieve(
            name=self.engine_name,
            scope={"app_name": app_name, "user_id": user_id},
            similarity_search_params={"search_query": query, "top_k": 10},
        )
        facts = []
        async for retrieved in pager:
            memory = retrieved.memory
            if memory is not None and memory.fact:
                facts.append(memory.fact)
        return facts


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
