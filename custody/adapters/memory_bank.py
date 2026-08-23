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

import hashlib
from dataclasses import dataclass
from typing import Mapping, Protocol

from google.genai.errors import ClientError

from custody.authority import (
    AdmissionState,
    AuthorityConflict,
    AuthorityDataError,
    AuthorityStateReader,
)
from custody.graph import Revocation
from custody.memory_bank import memory_id_for
from custody.origin import Admitted


class AgentEngineMemoriesClient(Protocol):
    """The narrow slice of `agent_engines.memories` this module needs."""

    async def create(self, *, name: str, fact: str, scope: dict, config: dict): ...

    async def retrieve(self, *, name: str, scope: dict, similarity_search_params: dict): ...

    async def get(self, *, name: str): ...

    async def delete(self, *, name: str) -> None: ...


@dataclass(frozen=True)
class RetrievedAuthorityMemory:
    """A Memory Bank fact whose exact B7 record identity survived retrieval."""

    record_id: str
    fact: str
    memory_name: str
    envelope_version: str


@dataclass
class AgentEngineMemoryBank:
    """The `RecordWriter` downstream: one `memories.create` call per trusted
    record, named so it is later deletable by id alone.
    """

    memories: AgentEngineMemoriesClient
    engine_name: str
    authority_state: AuthorityStateReader | None = None

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
        """Legacy informational search.

        Facts returned here carry no B7 citation identity and therefore cannot
        be submitted to the B7 action gateway. Eligible callers use
        :meth:`search_authority_memory` instead.
        """
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

    async def write_authority_record(
        self,
        *,
        app_name: str,
        user_id: str,
        record_id: str,
        text: str,
    ) -> None:
        """Publish one already-committed B7 record with recoverable identity."""

        envelope = self._authority_envelope(record_id, text)
        memory_id = memory_id_for(record_id)
        config = {
            "memory_id": memory_id,
            "metadata": {
                "custody_record_id": {"string_value": record_id},
                "custody_envelope_version": {
                    "string_value": envelope.schema_version
                },
            },
            "wait_for_completion": True,
        }
        try:
            await self.memories.create(
                name=self.engine_name,
                fact=text,
                scope={"app_name": app_name, "user_id": user_id},
                config=config,
            )
        except ClientError as error:
            if error.code != 409:
                raise
            memory = await self.memories.get(
                name=f"{self.engine_name}/memories/{memory_id}"
            )
            if not self._matches_authority_memory(memory, record_id, text):
                raise AuthorityConflict(
                    "Memory Bank ID already has different B7 bytes"
                ) from error

    async def search_authority_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> tuple[RetrievedAuthorityMemory, ...]:
        """Return only facts whose B7 ID, metadata, and payload all agree."""

        if self.authority_state is None:
            raise AuthorityDataError(
                "B7 Memory Bank retrieval requires authoritative state"
            )
        pager = await self.memories.retrieve(
            name=self.engine_name,
            scope={"app_name": app_name, "user_id": user_id},
            similarity_search_params={"search_query": query, "top_k": 10},
        )
        results: list[RetrievedAuthorityMemory] = []
        async for retrieved in pager:
            memory = retrieved.memory
            if memory is None or not getattr(memory, "fact", None):
                continue
            record_id = _metadata_string(memory, "custody_record_id")
            version = _metadata_string(memory, "custody_envelope_version")
            if record_id is None or version is None:
                continue
            if not self._matches_authority_memory(memory, record_id, memory.fact):
                continue
            results.append(
                RetrievedAuthorityMemory(
                    record_id=record_id,
                    fact=memory.fact,
                    memory_name=memory.name,
                    envelope_version=version,
                )
            )
        return tuple(results)

    def _authority_envelope(self, record_id: str, text: str):
        if self.authority_state is None:
            raise AuthorityDataError(
                "B7 Memory Bank publication requires authoritative state"
            )
        if not isinstance(text, str):
            raise AuthorityDataError("B7 Memory Bank text must be a string")
        envelope = self.authority_state.envelope(record_id)
        if envelope is None or envelope.admission_state is not AdmissionState.COMMITTED:
            raise AuthorityDataError("B7 record is missing or not committed")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != envelope.payload_digest:
            raise AuthorityDataError("B7 Memory Bank payload does not match envelope")
        return envelope

    def _matches_authority_memory(
        self, memory: object, record_id: str, text: str
    ) -> bool:
        try:
            envelope = self._authority_envelope(record_id, text)
        except AuthorityDataError:
            return False
        name = getattr(memory, "name", None)
        if (
            not isinstance(name, str)
            or name.rsplit("/", 1)[-1] != memory_id_for(record_id)
            or getattr(memory, "fact", None) != text
        ):
            return False
        return (
            _metadata_string(memory, "custody_record_id") == record_id
            and _metadata_string(memory, "custody_envelope_version")
            == envelope.schema_version
        )


def _metadata_string(memory: object, key: str) -> str | None:
    metadata = getattr(memory, "metadata", None)
    if not isinstance(metadata, Mapping):
        return None
    raw = metadata.get(key)
    if isinstance(raw, Mapping):
        value = raw.get("string_value")
    else:
        value = getattr(raw, "string_value", None)
    return value if isinstance(value, str) and value else None


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
