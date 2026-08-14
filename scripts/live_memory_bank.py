"""Run a real ADK agent through Custody into live Memory Bank, on D2's
`write_record` path rather than `ingest_events`.

Migrated 2026-08-14 (see `HANDOFF.md` "G1 migration", `DECISIONS.md` #2):
G1 previously wrote through ADK's stock `ingest_events` flow, which has no
reliable id, so nothing it wrote could be selectively deleted. `custody/
adapters/memory_bank.py`'s `AgentEngineMemoryBank` (D2) writes one
`memory_id`-pinned memory per admitted record instead, which is deletable
by id alone. `custody/adapters/adk.py`'s `_SessionRebuilding` now proxies
`write_record` when the wrapped downstream offers it, so `CustodyMemoryBank`
(the ADK-facing shell the real `Runner` sees) takes this path automatically;
no change to `custody/service.py`'s existing capability-detection branch.

The conversational leg below is unchanged from the prior `ingest_events`
proof: same agent, same prompt, same Gemini call, same
`after_agent_callback` shape. A second, tool-origin write proves selective
deletion the way D2 proved it standalone (`scripts/live_memory_deletion.py`),
but through `CustodyMemoryBank` this time, which is the integration gap this
migration closes: revoking that tool removes exactly its memory while the
conversational memory, which has no `source_tool`, is untouched.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplatform import Client  # noqa: E402
from google.adk.agents import Agent, Context  # noqa: E402
from google.adk.events import Event as AdkEvent  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService, Session  # noqa: E402
from google.genai import types  # noqa: E402

from custody.adapters.adk import CustodyMemoryBank  # noqa: E402
from custody.adapters.memory_bank import (  # noqa: E402
    AgentEngineMemoryBank,
    RevokingMemoryBankGraph,
)
from custody.memory_bank import memory_id_for  # noqa: E402
from custody.origin import ToolTrust  # noqa: E402

APP_NAME = "custody-g1"
MODEL = "gemini-3.5-flash"
FACT = "Sales exports require a signed approval."
QUERY = "What approval do sales exports require?"
#: Trusted so a second, tool-origin write exists to revoke and prove
#: selective deletion against, the way `live_memory_deletion.py` proves it
#: for a standalone session, here through `CustodyMemoryBank` instead.
TOOL_NAME = "sales_export_audit_tool"


class RecordWritingMemoryBank:
    """The `RecordWriter` downstream G1's live proof now writes through.

    Thin composition over D2's `AgentEngineMemoryBank`, plus the bookkeeping
    this proof's evidence needs: which `memory_id`s were actually written,
    and what a search returned, both otherwise invisible outside the client.
    """

    def __init__(self, *, project: str, location: str, agent_engine_id: str) -> None:
        self.engine_name = (
            f"projects/{project}/locations/{location}/reasoningEngines/"
            f"{agent_engine_id}"
        )
        client = Client(project=project, location=location)
        self.memories = client.aio.agent_engines.memories
        self._writer = AgentEngineMemoryBank(
            memories=self.memories, engine_name=self.engine_name
        )
        self.written_memory_ids: list[str] = []
        self.last_search_facts: list[str] = []

    async def write_record(self, *, app_name: str, user_id: str, admitted) -> None:
        await self._writer.write_record(
            app_name=app_name, user_id=user_id, admitted=admitted
        )
        self.written_memory_ids.append(memory_id_for(admitted.record.id))

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> list[str]:
        facts = await self._writer.search_memory(
            app_name=app_name, user_id=user_id, query=query
        )
        self.last_search_facts = facts
        return facts


def _matches_expected_fact(fact: str) -> bool:
    """Memory Bank summarizes, so verify meaning inside a unique scope."""
    normalized = fact.lower()
    return "sales export" in normalized and "signed approval" in normalized


async def _poll_search(
    custody: CustodyMemoryBank, *, user_id: str, contains: str, deadline: float
) -> list[str]:
    facts: list[str] = []
    while time.monotonic() < deadline:
        facts = await custody.search_memory(
            app_name=APP_NAME, user_id=user_id, query=QUERY
        )
        if any(contains in fact for fact in facts):
            return facts
        await asyncio.sleep(3)
    return facts


async def _prove_selective_deletion(
    custody: CustodyMemoryBank,
    downstream: RecordWritingMemoryBank,
    *,
    session_id: str,
    user_id: str,
    agent_name: str,
    proof_id: str,
) -> dict[str, object]:
    """One real ADK event carrying a trusted tool's function_response,
    admitted through the same `CustodyMemoryBank` instance as the
    conversational turn. That turn has no `source_tool` and so cannot be
    revoked by tool; this record can, which is what proves selective
    deletion works through G1's actual wiring, not just D2's standalone one.
    """
    tool_fact = f"Sales export audit control TOOL-{proof_id[:8]} requires dual sign-off."
    tool_invocation = f"g1-tool-{proof_id[:12]}"
    tool_event = AdkEvent(
        invocation_id=tool_invocation,
        author=agent_name,
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=tool_invocation,
                        name=TOOL_NAME,
                        response={"result": tool_fact},
                    )
                )
            ],
        ),
    )
    tool_session = Session(
        id=f"{session_id}-tool",
        app_name=APP_NAME,
        user_id=user_id,
        events=[tool_event],
    )
    splits_before = len(custody.splits())
    await custody.add_session_to_memory(tool_session)
    # `CustodyMemoryBank.add_session_to_memory` matches ADK's `-> None`
    # port and discards the `Split` `CustodyMemoryService` returns; read it
    # back from `splits()` instead, the same accessor the conversational
    # leg above already uses.
    tool_split = custody.splits()[splits_before]
    if len(tool_split.trusted) != 1:
        raise RuntimeError(
            f"expected one trusted tool-origin record, got {len(tool_split.trusted)}"
        )
    tool_record = tool_split.trusted[0].record

    before_revoke = await _poll_search(
        custody, user_id=user_id, contains=tool_fact, deadline=time.monotonic() + 90
    )
    if tool_fact not in before_revoke:
        raise RuntimeError(
            "the tool-origin write completed but was not retrievable within "
            "90 seconds"
        )

    revoking_graph = RevokingMemoryBankGraph(
        graph=custody.graph(),
        memories=downstream.memories,
        engine_name=downstream.engine_name,
    )
    revocation = await revoking_graph.revoke(
        tool=TOOL_NAME, revocation_id=f"g1-revoke-{proof_id}"
    )

    deadline = time.monotonic() + 90
    after_revoke = before_revoke
    while time.monotonic() < deadline:
        after_revoke = await custody.search_memory(
            app_name=APP_NAME, user_id=user_id, query=QUERY
        )
        if tool_fact not in after_revoke and any(
            _matches_expected_fact(f) for f in after_revoke
        ):
            break
        await asyncio.sleep(3)
    if tool_fact in after_revoke:
        raise RuntimeError(
            "revoking the tool did not remove its memory within 90 seconds"
        )
    if not any(_matches_expected_fact(f) for f in after_revoke):
        raise RuntimeError(
            "revoking the tool also removed the untooled conversational "
            "memory, which should be untouched"
        )

    return {
        "tool": TOOL_NAME,
        "tool_record_id": tool_record.id,
        "tool_memory_id": memory_id_for(tool_record.id),
        "tool_fact": tool_fact,
        "before_revoke_facts": before_revoke,
        "after_revoke_facts": after_revoke,
        "revocation_id": revocation.id,
        "removed": list(revocation.removed),
    }


async def prove_adk_memory_bank(
    *, project: str, location: str, agent_engine_id: str, proof_id: str
) -> dict[str, object]:
    """Return evidence from one unique-scope ADK Runner invocation.

    Two writes happen in this one scope: the real Runner's conversational
    turn (unchanged from before the migration), and one direct, tool-origin
    write proving the same `CustodyMemoryBank` instance can also admit and
    later revoke a tool's output, which the conversational turn alone
    cannot exercise (it carries no `source_tool`).
    """
    user_id = f"g1-{proof_id}"
    session_id = f"g1-{proof_id}"
    downstream = RecordWritingMemoryBank(
        project=project, location=location, agent_engine_id=agent_engine_id
    )
    tools = ToolTrust(trusted=frozenset({TOOL_NAME}))
    custody = CustodyMemoryBank(downstream=downstream, tools=tools)

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
    found_facts = await _poll_search(
        custody, user_id=user_id, contains="signed approval", deadline=deadline
    )
    matched = [f for f in found_facts if _matches_expected_fact(f)]
    if not matched:
        raise RuntimeError(
            "the ADK callback completed, but its unique Memory Bank scope did not "
            "return the submitted fact within 90 seconds"
        )

    conversational_splits = custody.splits()
    if len(conversational_splits) != 1:
        raise RuntimeError(
            "expected exactly one ADK callback split from the conversational "
            f"turn, got {len(conversational_splits)}"
        )
    conversational_split = conversational_splits[0]

    revocation_proof = await _prove_selective_deletion(
        custody,
        downstream,
        session_id=session_id,
        user_id=user_id,
        agent_name=agent.name,
        proof_id=proof_id,
    )

    return {
        "write_path": "write_record",
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
        "retrieved_facts": matched,
        "retrieved_memory_count": len(found_facts),
        "written_memory_ids": downstream.written_memory_ids,
        "memory_write_count": len(downstream.written_memory_ids),
        #: The conversational leg alone, one write_record call per trusted
        #: event, so a judge can tell it apart from the tool leg's one
        #: additional write below without recomputing the split.
        "conversational_memory_write_count": len(conversational_split.trusted),
        "custody_split": {
            "total": conversational_split.total,
            "withheld": conversational_split.withheld,
            "refused": conversational_split.refused,
        },
        #: The exact digests of the admitted records this run produced. A
        #: quarantine later needs to name what it is quarantining; this is
        #: that name, and it is what the Observability proof (O1) binds to a
        #: trace, so a later revocation can be traced back to this run.
        "admitted_digests": [
            a.record.content_sha256 for a in conversational_split.trusted
        ],
        #: The tool-origin write and its revocation, proving selective
        #: deletion through G1's own CustodyMemoryBank wiring rather than
        #: D2's standalone CustodyMemoryService usage.
        "revocation_proof": revocation_proof,
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
