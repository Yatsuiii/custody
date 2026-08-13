"""Prove D2: selective deletion from live Memory Bank, via a new opt-in
write path additive to G1's own (`agent_engines.memories.create`, pinned to
a deterministic `memory_id`, never `ingest_events`).

This does not touch G1's Cloud Run control plane, its ADK Runner flow, or
its existing evidence. One session writes two trusted, different-tool
records through `AgentEngineMemoryBank`; both are confirmed retrievable;
revoking one tool via `RevokingMemoryBankGraph` deletes exactly its memory
and a subsequent `search_memory` no longer returns it, while the other
tool's memory is untouched. Non-goal, stated once because it matters:
memories already written through `ingest_events` (including G1's own) are
not covered by this mechanism; see `DECISIONS.md` #2.

    make live-memory-deletion
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplatform import Client  # noqa: E402

from custody.adapters.memory_bank import (  # noqa: E402
    AgentEngineMemoryBank,
    RevokingMemoryBankGraph,
)
from custody.graph import CustodyGraph  # noqa: E402
from custody.memory_bank import memory_id_for  # noqa: E402
from custody.origin import ToolTrust  # noqa: E402
from custody.service import CustodyMemoryService, InMemoryQuarantine  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-memory-deletion.json"
FAILURE = REPO_ROOT / "proof-out" / "live-memory-deletion.failure.json"

CLAIM_BOUNDARY = (
    "Proves a CustodyRecord admitted through the new write_record path can "
    "be deleted from live Memory Bank by name alone, with no search and no "
    "content matching, and that revoking one tool removes exactly its "
    "memory while a sibling tool's memory is untouched. This is a new, "
    "additive, opt-in write path (agent_engines.memories.create, "
    "memory_id-pinned), not G1's ingest_events path: memories G1 or ADK's "
    "own add_session_to_memory already wrote are not covered by this "
    "mechanism."
)


@dataclass
class FakePart:
    text: str | None = None
    function_response: object | None = None


@dataclass
class FakeResponse:
    name: str
    response: object


@dataclass
class FakeContent:
    parts: list


@dataclass
class FakeEvent:
    author: str
    invocation_id: str
    content: FakeContent


@dataclass
class FakeSession:
    id: str
    app_name: str
    user_id: str
    events: list = field(default_factory=list)


def _tool_event(name: str, fact: str, *, invocation: str) -> FakeEvent:
    part = FakePart(function_response=FakeResponse(name=name, response=fact))
    return FakeEvent("assistant", invocation, FakeContent([part]))


async def _poll(condition, *, attempts: int = 20, interval: float = 3.0):
    for _ in range(attempts):
        result = await condition()
        if result is not None:
            return result
        await asyncio.sleep(interval)
    raise RuntimeError("condition did not become true within the polling window")


async def _prove() -> dict[str, Any]:
    proof_id = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT")
    engine_id = os.environ.get("CUSTODY_AGENT_ENGINE_ID")
    if not project or not engine_id:
        raise SystemExit("CUSTODY_PROJECT and CUSTODY_AGENT_ENGINE_ID are required")
    location = os.environ.get("CUSTODY_LOCATION", "us-central1")
    engine_name = (
        f"projects/{project}/locations/{location}/reasoningEngines/{engine_id}"
    )

    client = Client(project=project, location=location)
    memories = client.aio.agent_engines.memories
    downstream = AgentEngineMemoryBank(memories=memories, engine_name=engine_name)
    graph = CustodyGraph()
    revoking_graph = RevokingMemoryBankGraph(
        graph=graph, memories=memories, engine_name=engine_name
    )

    sales_tool, finance_tool = "sales/lookup", "finance/lookup"
    tools = ToolTrust(frozenset({sales_tool, finance_tool}))
    service = CustodyMemoryService(
        downstream=downstream,
        quarantine=InMemoryQuarantine(),
        tools=tools,
        graph=graph,
    )

    app_name = "custody-d2-probe"
    user_id = f"d2-{proof_id[:12]}"
    sales_fact = f"The sales export policy audit tag is ALPHA-{proof_id[:8]}."
    finance_fact = f"The finance export policy audit tag is BRAVO-{proof_id[:8]}."

    session = FakeSession(
        id=f"d2-{proof_id[:12]}",
        app_name=app_name,
        user_id=user_id,
        events=[
            _tool_event(sales_tool, sales_fact, invocation="inv-sales"),
            _tool_event(finance_tool, finance_fact, invocation="inv-finance"),
        ],
    )

    split = await service.add_session_to_memory(session)
    if len(split.trusted) != 2:
        raise RuntimeError(
            f"expected 2 trusted records written, got {len(split.trusted)}"
        )
    sales_record = next(
        a.record for a in split.trusted if a.record.source_tool == sales_tool
    )
    finance_record = next(
        a.record for a in split.trusted if a.record.source_tool == finance_tool
    )

    async def both_present():
        facts = await downstream.search_memory(
            app_name=app_name, user_id=user_id, query="export policy audit tag"
        )
        if sales_fact in facts and finance_fact in facts:
            return facts
        return None

    before_facts = await _poll(both_present)

    revocation = await revoking_graph.revoke(
        tool=sales_tool, revocation_id=f"d2-{proof_id}"
    )

    async def sales_gone_finance_present():
        facts = await downstream.search_memory(
            app_name=app_name, user_id=user_id, query="export policy audit tag"
        )
        if sales_fact not in facts and finance_fact in facts:
            return facts
        return None

    after_facts = await _poll(sales_gone_finance_present)

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "claim_boundary": CLAIM_BOUNDARY,
        "engine_name": engine_name,
        "scope": {"app_name": app_name, "user_id": user_id},
        "sales_record_id": sales_record.id,
        "finance_record_id": finance_record.id,
        "sales_fact": sales_fact,
        "finance_fact": finance_fact,
        "before_facts": before_facts,
        "after_facts": after_facts,
        "revocation": {
            "id": revocation.id,
            "tool": revocation.tool,
            "removed": list(revocation.removed),
        },
        "deleted_memory_name": (
            f"{engine_name}/memories/{memory_id_for(sales_record.id)}"
        ),
        "surviving_memory_name": (
            f"{engine_name}/memories/{memory_id_for(finance_record.id)}"
        ),
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
        print(f"live memory deletion proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live memory deletion evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
