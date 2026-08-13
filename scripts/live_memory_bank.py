"""Run a real ADK agent through Custody into live Memory Bank.

The proof needs a blocking downstream because ADK's stock Memory Bank service
queues ingestion and returns before memory generation. This adapter keeps that
latency policy behind the ``BaseMemoryService`` interface: when
``add_session_to_memory`` returns, the managed ingestion operation is complete.
The ADK Runner still sees only ``CustodyMemoryBank``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplatform import Client  # noqa: E402
from google.adk.agents import Agent, Context  # noqa: E402
from google.adk.memory import BaseMemoryService  # noqa: E402
from google.adk.memory.base_memory_service import (  # noqa: E402
    SearchMemoryResponse,
)
from google.adk.memory.memory_entry import MemoryEntry  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService, Session  # noqa: E402
from google.genai import types  # noqa: E402

from custody.adapters.adk import CustodyMemoryBank  # noqa: E402

APP_NAME = "custody-g1"
MODEL = "gemini-3.5-flash"
FACT = "Sales exports require a signed approval."
QUERY = "What approval do sales exports require?"


@dataclass
class BlockingAgentPlatformMemoryBank(BaseMemoryService):
    """A Memory Bank port whose write completes only after the ingestion LRO."""

    project: str
    location: str
    agent_engine_id: str
    operation_names: list[str] = field(default_factory=list)
    written_event_count: int = 0
    retrieved_memory_names: list[str] = field(default_factory=list)

    @property
    def engine_name(self) -> str:
        return (
            f"projects/{self.project}/locations/{self.location}/reasoningEngines/"
            f"{self.agent_engine_id}"
        )

    def _client(self) -> Client:
        return Client(project=self.project, location=self.location)

    async def add_session_to_memory(self, session: Session) -> None:
        events = [event for event in session.events if _has_content(event)]
        if not events:
            return

        operation = await self._client().aio.agent_engines.memories.ingest_events(
            name=self.engine_name,
            scope={"app_name": session.app_name, "user_id": session.user_id},
            stream_id=session.id,
            direct_contents_source={
                "events": [
                    {
                        "content": event.content,
                        "event_id": event.id or f"{session.id}-{index}",
                    }
                    for index, event in enumerate(events)
                ]
            },
            config={"force_flush": True, "wait_for_completion": True},
        )
        self.written_event_count += len(events)
        self.operation_names.append(operation.name or "completed-without-name")

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> SearchMemoryResponse:
        pager = await self._client().aio.agent_engines.memories.retrieve(
            name=self.engine_name,
            scope={"app_name": app_name, "user_id": user_id},
            similarity_search_params={"search_query": query, "top_k": 10},
        )
        entries: list[MemoryEntry] = []
        self.retrieved_memory_names.clear()
        async for retrieved in pager:
            memory = retrieved.memory
            if memory is None or not memory.fact:
                continue
            self.retrieved_memory_names.append(memory.name or "unnamed-memory")
            entries.append(
                MemoryEntry(
                    author="user",
                    content=types.Content(
                        role="user", parts=[types.Part(text=memory.fact)]
                    ),
                    timestamp=(
                        memory.update_time.isoformat() if memory.update_time else None
                    ),
                )
            )
        return SearchMemoryResponse(memories=entries)


def _has_content(event) -> bool:
    content = getattr(event, "content", None)
    return bool(content and content.parts)


def _texts(response: SearchMemoryResponse) -> list[str]:
    return [
        part.text
        for memory in response.memories
        for part in memory.content.parts
        if part.text
    ]


def _matches_expected_fact(fact: str) -> bool:
    """Memory Bank summarizes, so verify meaning inside a unique scope."""
    normalized = fact.lower()
    return "sales export" in normalized and "signed approval" in normalized


async def prove_adk_memory_bank(
    *, project: str, location: str, agent_engine_id: str, proof_id: str
) -> dict[str, object]:
    """Return evidence from one unique-scope ADK Runner invocation."""
    user_id = f"g1-{proof_id}"
    session_id = f"g1-{proof_id}"
    downstream = BlockingAgentPlatformMemoryBank(
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )
    custody = CustodyMemoryBank(downstream=downstream)

    async def persist_session(callback_context: Context) -> None:
        await callback_context.add_session_to_memory()

    model = Gemini(
        model=MODEL,
        client_kwargs={
            "vertexai": True,
            "project": project,
            "location": "global",
        },
    )
    agent = Agent(
        name="custody_g1_agent",
        model=model,
        instruction=(
            "Confirm the user's memory request in one sentence. Preserve the audit "
            "identifier exactly."
        ),
        generate_content_config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=128,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        after_agent_callback=persist_session,
    )
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    runner = Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
        memory_service=custody,
    )

    prompt = f"Remember this: {FACT} Audit identifier: {proof_id}."
    events = []
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user", parts=[types.Part(text=prompt)]
            ),
        ):
            events.append(event)
    finally:
        await runner.close()

    deadline = time.monotonic() + 90
    found_facts: list[str] = []
    matched: str | None = None
    while time.monotonic() < deadline:
        found = await custody.search_memory(
            app_name=APP_NAME, user_id=user_id, query=QUERY
        )
        found_facts = _texts(found)
        matched = next(
            (fact for fact in found_facts if _matches_expected_fact(fact)), None
        )
        if matched:
            break
        await asyncio.sleep(3)
    if matched is None:
        raise RuntimeError(
            "the ADK callback completed, but its unique Memory Bank scope did not "
            "return the submitted fact within 90 seconds"
        )

    splits = custody.splits()
    if len(splits) != 1 or len(downstream.operation_names) != 1:
        raise RuntimeError(
            "expected one ADK callback and one governed Memory Bank write, got "
            f"{len(splits)} split(s) and {len(downstream.operation_names)} write(s)"
        )
    split = splits[0]
    return {
        "framework": "google-adk",
        "agent_name": agent.name,
        "configured_model": MODEL,
        "agent_run_completed": True,
        "runner_event_count": len(events),
        "agent_text": " ".join(
            part.text
            for event in events
            if event.content
            for part in event.content.parts
            if part.text
        ),
        "agent_engine": downstream.engine_name,
        "scope": {"app_name": APP_NAME, "user_id": user_id},
        "submitted_fact": FACT,
        "retrieved_fact": matched,
        "retrieved_memory_count": len(found_facts),
        "retrieved_memory_names": downstream.retrieved_memory_names,
        "memory_write_count": len(downstream.operation_names),
        "memory_operation_names": downstream.operation_names,
        "written_event_count": downstream.written_event_count,
        "custody_split": {
            "total": split.total,
            "withheld": split.withheld,
            "refused": split.refused,
        },
        #: The exact digests of the admitted records this run produced. A
        #: quarantine later needs to name what it is quarantining; this is
        #: that name, and it is what the Observability proof (O1) binds to a
        #: trace, so a later revocation can be traced back to this run.
        "admitted_digests": [a.record.content_sha256 for a in split.trusted],
    }


def main() -> int:
    project = os.environ.get("CUSTODY_PROJECT")
    agent_engine_id = os.environ.get("CUSTODY_AGENT_ENGINE_ID")
    if not project or not agent_engine_id:
        raise SystemExit("CUSTODY_PROJECT and CUSTODY_AGENT_ENGINE_ID are required")
    result = asyncio.run(
        prove_adk_memory_bank(
            project=project,
            location=os.environ.get("CUSTODY_LOCATION", "us-central1"),
            agent_engine_id=agent_engine_id,
            proof_id=uuid.uuid4().hex,
        )
    )
    import json

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
