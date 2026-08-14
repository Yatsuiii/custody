"""Prove the fleet claim at N>1: five live department worker agents, and the
one property N=1 could never exercise.

Every prior live proof ran one ADK Runner, once, one department per
invocation. The product's own one-sentence claim is that a compromised
tool revision is "identified and pulled ... across every department, agent
and session since" -- but `CustodyGraph.revoke` (`custody/graph.py`) has
never actually been exercised across more than one department, because
there has never been more than one. Checked in code before this was built:
`CustodyGraph.revoke` matches descendants by `tool` name alone, and
`CustodyRecord` carries no `department` field at all -- by design, not an
oversight (see `custody/graph.py`'s own docstring). This script is what
turns that design claim into live evidence.

Five departments (sales, legal, hr, finance, engineering) each run a real
ADK Runner/Gemini conversational turn plus one tool-origin write, through
the exact wiring G1 already proved (`CustodyMemoryBank` ->
`AgentEngineMemoryBank` via `write_record`), against one already-owned
Agent Engine. Two of the five (sales, finance) trust and invoke a tool with
the *same name*. All five write through one shared `CustodyMemoryBank`
instance -- one process-wide graph, mirroring production, not five
isolated ones -- so revoking the shared tool once is a single call that
must reach both departments' memories while leaving the other three
untouched.

    make live-fleet
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import UTC, datetime
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

OUT = REPO_ROOT / "proof-out" / "live-fleet.json"
FAILURE = REPO_ROOT / "proof-out" / "live-fleet.failure.json"

APP_NAME = "custody-fleet"
MODEL = "gemini-3.5-flash"

#: The shared tool two departments independently trust and invoke. Its
#: revocation is the one property N=1 structurally could not exercise.
SHARED_TOOL = "cross_dept_export_tool"
SHARED_TOOL_DEPARTMENTS = ("sales", "finance")
#: Each remaining department uses a distinct tool name, so a revocation
#: touching the shared tool has no name collision to accidentally ride on.
DEPARTMENT_TOOLS = {
    "sales": SHARED_TOOL,
    "finance": SHARED_TOOL,
    "legal": "legal_review_tool",
    "hr": "hr_disclosure_tool",
    "engineering": "engineering_deploy_tool",
}

CLAIM_BOUNDARY = (
    "Proves CustodyGraph.revoke reaches every department that used a "
    "revoked tool, not only the department that reported it, and that "
    "departments using a different tool are untouched by that revocation. "
    "Does not test TrustCatalog's per-department grant boundary (already "
    "proven offline and live in the Auditor sub-build) and does not stand "
    "up separate Cloud Run/Agent Engine identities per department -- "
    "Memory Bank's own {app_name, user_id} scoping is what separates them."
)


class RecordWritingMemoryBank:
    """The shared `RecordWriter` downstream all five departments write
    through. One instance, so `written_memory_ids` and the underlying
    Agent Engine client are shared, the same way `custody.graph()` is
    shared by the `CustodyMemoryBank` wrapping this.
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

    async def write_record(self, *, app_name: str, user_id: str, admitted) -> None:
        await self._writer.write_record(
            app_name=app_name, user_id=user_id, admitted=admitted
        )
        self.written_memory_ids.append(memory_id_for(admitted.record.id))

    async def search_memory(
        self, *, app_name: str, user_id: str, query: str
    ) -> list[str]:
        return await self._writer.search_memory(
            app_name=app_name, user_id=user_id, query=query
        )


async def _poll_search(
    custody: CustodyMemoryBank,
    *,
    user_id: str,
    query: str,
    contains: str,
    deadline: float,
) -> list[str]:
    facts: list[str] = []
    while time.monotonic() < deadline:
        facts = await custody.search_memory(
            app_name=APP_NAME, user_id=user_id, query=query
        )
        if any(contains in fact for fact in facts):
            return facts
        await asyncio.sleep(3)
    return facts


async def _run_department(
    custody: CustodyMemoryBank,
    *,
    project: str,
    department: str,
    proof_id: str,
) -> dict[str, object]:
    """One department's live turn: a real ADK Runner/Gemini conversational
    write, plus one direct tool-origin write, both through the one shared
    `custody` instance so all five land in the same derivation graph.
    """
    tool_name = DEPARTMENT_TOOLS[department]
    user_id = f"fleet-{department}-{proof_id[:12]}"
    session_id = user_id
    fact = f"{department.title()} audit identifier {proof_id[:8]} is on file."

    async def persist_session(callback_context: Context) -> None:
        await callback_context.add_session_to_memory()

    model = Gemini(
        model=MODEL,
        client_kwargs={"vertexai": True, "project": project, "location": "global"},
    )
    agent = Agent(
        name=f"custody_fleet_{department}_agent",
        model=model,
        instruction=(
            "Confirm the user's memory request in one sentence. Preserve the "
            "audit identifier exactly."
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

    prompt = f"Remember this: {fact} Audit identifier: {proof_id}."
    events = []
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            events.append(event)
    finally:
        await runner.close()

    conversational_facts = await _poll_search(
        custody,
        user_id=user_id,
        query=f"{department} audit identifier",
        contains=proof_id[:8],
        deadline=time.monotonic() + 90,
    )
    if not any(proof_id[:8] in f for f in conversational_facts):
        raise RuntimeError(
            f"{department}: conversational write not retrievable within 90s"
        )

    tool_fact = f"{department.title()} export control TOOL-{proof_id[:8]} requires review."
    tool_invocation = f"fleet-{department}-tool-{proof_id[:12]}"
    tool_event = AdkEvent(
        invocation_id=tool_invocation,
        author=agent.name,
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=tool_invocation,
                        name=tool_name,
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
    tool_split = custody.splits()[splits_before]
    if len(tool_split.trusted) != 1:
        raise RuntimeError(
            f"{department}: expected one trusted tool-origin record, got "
            f"{len(tool_split.trusted)}"
        )
    tool_record = tool_split.trusted[0].record

    before_revoke = await _poll_search(
        custody,
        user_id=user_id,
        query=f"{department} export control",
        contains=tool_fact,
        deadline=time.monotonic() + 90,
    )
    if tool_fact not in before_revoke:
        raise RuntimeError(
            f"{department}: tool-origin write not retrievable within 90s"
        )

    return {
        "user_id": user_id,
        "tool": tool_name,
        "tool_record_id": tool_record.id,
        "tool_fact": tool_fact,
        "agent_run_completed": True,
        "runner_event_count": len(events),
        "before_revoke_facts": before_revoke,
        #: filled in after the shared-tool revocation below
        "after_revoke_facts": None,
    }


async def _prove() -> dict[str, object]:
    proof_id = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT")
    agent_engine_id = os.environ.get("CUSTODY_AGENT_ENGINE_ID")
    if not project or not agent_engine_id:
        raise SystemExit("CUSTODY_PROJECT and CUSTODY_AGENT_ENGINE_ID are required")
    location = os.environ.get("CUSTODY_LOCATION", "us-central1")

    downstream = RecordWritingMemoryBank(
        project=project, location=location, agent_engine_id=agent_engine_id
    )
    tools = ToolTrust(trusted=frozenset(DEPARTMENT_TOOLS.values()))
    #: One shared instance -- one graph, one derivation history across all
    #: five departments -- is the point. Five separate `CustodyMemoryBank`
    #: instances would each get their own graph and could never exercise
    #: the cross-department claim this script exists to prove.
    custody = CustodyMemoryBank(downstream=downstream, tools=tools)

    departments: dict[str, dict[str, object]] = {}
    for department in DEPARTMENT_TOOLS:
        departments[department] = await _run_department(
            custody, project=project, department=department, proof_id=proof_id
        )

    revoking_graph = RevokingMemoryBankGraph(
        graph=custody.graph(),
        memories=downstream.memories,
        engine_name=downstream.engine_name,
    )
    revocation = await revoking_graph.revoke(
        tool=SHARED_TOOL, revocation_id=f"fleet-revoke-{proof_id}"
    )

    untouched_departments = [
        d for d in DEPARTMENT_TOOLS if d not in SHARED_TOOL_DEPARTMENTS
    ]
    for department in DEPARTMENT_TOOLS:
        record = departments[department]
        deadline = time.monotonic() + 90
        facts = record["before_revoke_facts"]
        while time.monotonic() < deadline:
            facts = await custody.search_memory(
                app_name=APP_NAME,
                user_id=record["user_id"],
                query=f"{department} export control",
            )
            gone = record["tool_fact"] not in facts
            settled = gone if department in SHARED_TOOL_DEPARTMENTS else not gone
            if settled:
                break
            await asyncio.sleep(3)
        record["after_revoke_facts"] = facts

    for department in SHARED_TOOL_DEPARTMENTS:
        record = departments[department]
        if record["tool_fact"] in record["after_revoke_facts"]:
            raise RuntimeError(
                f"{department}: shared tool revocation did not remove its "
                "memory within 90 seconds"
            )
    for department in untouched_departments:
        record = departments[department]
        if record["tool_fact"] not in record["after_revoke_facts"]:
            raise RuntimeError(
                f"{department}: the shared-tool revocation also removed an "
                "unrelated department's own memory, which should be untouched"
            )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "location": location,
        "agent_engine": downstream.engine_name,
        "claim_boundary": CLAIM_BOUNDARY,
        "shared_tool": SHARED_TOOL,
        "shared_tool_departments": list(SHARED_TOOL_DEPARTMENTS),
        "untouched_departments": {
            d: {
                "tool_fact_still_present": (
                    departments[d]["tool_fact"] in departments[d]["after_revoke_facts"]
                )
            }
            for d in untouched_departments
        },
        "departments": departments,
        "revocation": {
            "id": revocation.id,
            "tool": revocation.tool,
            "removed": list(revocation.removed),
        },
        "written_memory_ids": downstream.written_memory_ids,
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    try:
        evidence = asyncio.run(_prove())
    except Exception as error:
        FAILURE.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now(UTC).isoformat(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"live fleet proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live fleet evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
