"""Prove the product's own headline claim live: a genuine cross-department
`derived_from` chain, earned through real `load_memory` content-hash
matches against live Vertex AI Memory Bank, then removed end to end by one
revocation.

`scripts/incident.py` dramatizes this exact story -- a tool-origin fact
hopping sales -> support -> finance, each hop a `derived_from` edge -- but
it is 100% offline (`PlainMemory`, not live Memory Bank). `scripts/
live_fleet.py` proves something narrower and live: N departments each
independently write once, and two of them happen to trust a tool with the
same name. No department in that script ever retrieves another
department's memory, so no live cross-department `derived_from` edge has
ever existed anywhere in this codebase's live proofs, until this script.

The edge is earned the same way `custody/origin.py`'s `_attribute` earns it
offline: a session event whose `function_response.name` is `load_memory`
and whose response text content-hashes to a record already in the shared
`CustodyGraph` is attributed as a citation, not new content, and inherits
that record's lineage. Doing this live means retrieving the *exact* text
Memory Bank handed back via `search_memory`, not typing the fact twice.

Shape, three departments plus one negative control:

1. Sales: a real ADK Runner/Gemini conversational turn (proves live
   ADK/Gemini engagement), then a real tool-origin write plus its own
   model restatement, sharing one invocation so the restatement is
   `derived_from` the tool record -- the same two-hop shape
   `incident.py`'s `sales_session()` uses offline.
2. Support: a real ADK Runner/Gemini turn produces a genuine restatement
   reply; a `load_memory` citation event carrying the *exact* text
   `search_memory` just returned for sales's restatement is spliced in
   ahead of it, sharing that reply's own invocation id, then both are fed
   through `custody` together -- earning a live, content-hash-matched
   `derived_from` edge into sales's record.
3. Finance: same pattern, citing support's restatement.
4. Engineering: one independent tool-origin write, unrelated tool, the
   live negative control -- "does revocation touch things it shouldn't."

Revoking the chain tool must remove all six chain-hop records (sales's
tool root and restatement, support's citation and restatement, finance's
citation and restatement) from live Memory Bank, while leaving engineering's
record and every department's own unrelated conversational memory alone.

    make live-chain
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

from google.adk.agents import Agent, Context  # noqa: E402
from google.adk.events import Event as AdkEvent  # noqa: E402
from google.adk.models import Gemini  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService, Session  # noqa: E402
from google.genai import types  # noqa: E402

from custody.adapters.adk import CustodyMemoryBank  # noqa: E402
from custody.adapters.memory_bank import RevokingMemoryBankGraph  # noqa: E402
from custody.origin import ToolTrust  # noqa: E402

from scripts.live_fleet import RecordWritingMemoryBank  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-chain.json"
FAILURE = REPO_ROOT / "proof-out" / "live-chain.failure.json"

APP_NAME = "custody-chain"
MODEL = "gemini-3.5-flash"

#: The tool whose revocation must cascade across three departments and two
#: real load_memory-earned derivation hops.
CHAIN_TOOL = "vendor_audit_export_tool"
CHAIN_DEPARTMENTS = ("sales", "support", "finance")
#: One independent department, one independent tool -- the negative
#: control proving the chain revocation does not touch what it shouldn't.
SIBLING_DEPARTMENT = "engineering"
SIBLING_TOOL = "engineering_pipeline_tool"

CLAIM_BOUNDARY = (
    "Proves a genuine live derived_from chain: two cross-department "
    "load_memory retrievals, each earning its edge by a real content-hash "
    "match against live Vertex AI Memory Bank text, not an asserted edge. "
    "One revocation removes all six chain-hop records; each department's "
    "own unrelated conversational memory and the sibling department's "
    "independent tool-origin memory are confirmed untouched. Does not test "
    "TrustCatalog's per-department grant boundary (already proven "
    "elsewhere) and does not stand up separate Cloud Run/Agent Engine "
    "identities per department, same scope live_fleet.py already accepts."
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


def _agent(name: str, model: Gemini, *, after_agent_callback=None) -> Agent:
    return Agent(
        name=name,
        model=model,
        instruction=(
            "Reply in exactly one sentence. Preserve any audit identifier "
            "or quoted note text exactly, verbatim."
        ),
        generate_content_config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=128,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        after_agent_callback=after_agent_callback,
    )


async def _run_turn(
    custody: CustodyMemoryBank,
    *,
    project: str,
    agent_name: str,
    user_id: str,
    prompt: str,
    persist: bool,
) -> list[AdkEvent]:
    """One real ADK Runner/Gemini turn. Persists to `custody` when `persist`
    is set, mirroring `live_fleet.py`'s conversational leg; otherwise the
    caller takes the returned events and folds them into a hand-built
    session itself (support's and finance's citation splice).
    """
    model = Gemini(
        model=MODEL,
        client_kwargs={"vertexai": True, "project": project, "location": "global"},
    )

    async def persist_session(callback_context: Context) -> None:
        if persist:
            await callback_context.add_session_to_memory()

    agent = _agent(agent_name, model, after_agent_callback=persist_session)
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=user_id
    )
    runner = Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
        memory_service=custody,
    )
    events: list[AdkEvent] = []
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=user_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            events.append(event)
    finally:
        await runner.close()
    return events


def _last_text_event(events: list[AdkEvent], *, author: str) -> AdkEvent:
    for event in reversed(events):
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue
        if event.author != author:
            continue
        if any(getattr(p, "text", None) for p in parts):
            return event
    raise RuntimeError(f"no text-bearing event authored by {author} in this turn")


async def _sales_leg(
    custody: CustodyMemoryBank, *, project: str, proof_id: str
) -> dict[str, object]:
    user_id = f"chain-sales-{proof_id[:12]}"
    conversational_marker = f"vendor onboarding memo {proof_id[:8]}"

    conversational_events = await _run_turn(
        custody,
        project=project,
        agent_name="custody_chain_sales_agent",
        user_id=user_id,
        prompt=f"Remember this: {conversational_marker} is on file for sales.",
        persist=True,
    )
    conversational_facts = await _poll_search(
        custody,
        user_id=user_id,
        query="vendor onboarding memo",
        contains=proof_id[:8],
        deadline=time.monotonic() + 90,
    )
    if not any(proof_id[:8] in f for f in conversational_facts):
        raise RuntimeError("sales: conversational write not retrievable within 90s")

    tool_fact = (
        f"Vendor audit note {proof_id[:8]}: contract renewal requires signed approval."
    )
    restatement = (
        f"Sales confirms vendor audit note {proof_id[:8]} and flags it for "
        "cross-department review."
    )
    invocation = f"chain-sales-tool-{proof_id[:12]}"
    author = "custody_chain_sales_agent"
    events = [
        AdkEvent(
            invocation_id=invocation,
            author=author,
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=f"{invocation}-fr",
                            name=CHAIN_TOOL,
                            response={"result": tool_fact},
                        )
                    )
                ],
            ),
        ),
        AdkEvent(
            invocation_id=invocation,
            author=author,
            content=types.Content(role="model", parts=[types.Part(text=restatement)]),
        ),
    ]
    session = Session(
        id=f"{user_id}-tool", app_name=APP_NAME, user_id=user_id, events=events
    )
    splits_before = len(custody.splits())
    await custody.add_session_to_memory(session)
    split = custody.splits()[splits_before]
    if len(split.trusted) != 2:
        raise RuntimeError(f"sales: expected 2 trusted records, got {len(split.trusted)}")
    tool_record = split.trusted[0].record
    restatement_record = split.trusted[1].record
    if restatement_record.derived_from != (tool_record.id,):
        raise RuntimeError("sales: restatement did not earn a derived_from edge into the tool root")

    before = await _poll_search(
        custody,
        user_id=user_id,
        query="vendor audit note",
        contains=restatement,
        deadline=time.monotonic() + 90,
    )
    if restatement not in before:
        raise RuntimeError("sales: restatement not retrievable within 90s")

    return {
        "user_id": user_id,
        "conversational_fact_contains": proof_id[:8],
        "conversational_agent_run_completed": True,
        "conversational_runner_event_count": len(conversational_events),
        "tool_record_id": tool_record.id,
        "tool_fact": tool_fact,
        "restatement_record_id": restatement_record.id,
        "restatement_derived_from": list(restatement_record.derived_from),
        "restatement": restatement,
        "before_revoke_facts": before,
        "after_revoke_facts": None,
        "conversational_after_revoke_facts": None,
    }


async def _derived_leg(
    custody: CustodyMemoryBank,
    *,
    project: str,
    department: str,
    proof_id: str,
    cited_text: str,
    cited_record_id: str,
) -> dict[str, object]:
    """Support's and finance's leg: a real Gemini reply, with a load_memory
    citation of the exact upstream text spliced ahead of it in the same
    invocation, so the reply earns a live derived_from edge.
    """
    user_id = f"chain-{department}-{proof_id[:12]}"
    conversational_marker = f"{department} intake note {proof_id[:8]}"

    conversational_events = await _run_turn(
        custody,
        project=project,
        agent_name=f"custody_chain_{department}_agent",
        user_id=user_id,
        prompt=f"Remember this: {conversational_marker} is on file for {department}.",
        persist=True,
    )
    conversational_facts = await _poll_search(
        custody,
        user_id=user_id,
        query=f"{department} intake note",
        contains=proof_id[:8],
        deadline=time.monotonic() + 90,
    )
    if not any(proof_id[:8] in f for f in conversational_facts):
        raise RuntimeError(f"{department}: conversational write not retrievable within 90s")

    reply_events = await _run_turn(
        custody,
        project=project,
        agent_name=f"custody_chain_{department}_agent",
        user_id=user_id,
        prompt=(
            f"During an audit, {department} just retrieved this note from "
            f"memory: \"{cited_text}\" Reply confirming escalation to the "
            "next department, preserving the audit identifier exactly."
        ),
        persist=False,
    )
    model_event = _last_text_event(
        reply_events, author=f"custody_chain_{department}_agent"
    )
    citation_event = AdkEvent(
        invocation_id=model_event.invocation_id,
        author=model_event.author,
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=f"{model_event.invocation_id}-lm",
                        name="load_memory",
                        response={"result": cited_text},
                    )
                )
            ],
        ),
    )
    session = Session(
        id=f"{user_id}-derive",
        app_name=APP_NAME,
        user_id=user_id,
        events=[citation_event, model_event],
    )
    splits_before = len(custody.splits())
    await custody.add_session_to_memory(session)
    split = custody.splits()[splits_before]
    if len(split.trusted) != 2:
        raise RuntimeError(
            f"{department}: expected 2 trusted records, got {len(split.trusted)}"
        )
    citation_record = split.trusted[0].record
    restatement_record = split.trusted[1].record
    if citation_record.derived_from != (cited_record_id,):
        raise RuntimeError(
            f"{department}: load_memory citation did not resolve to the "
            "expected upstream record -- the retrieved text did not "
            "content-hash match"
        )
    if restatement_record.derived_from != (citation_record.id,):
        raise RuntimeError(
            f"{department}: reply did not earn a derived_from edge into its own citation"
        )

    restatement_text = None
    for part in model_event.content.parts:
        if getattr(part, "text", None):
            restatement_text = part.text
            break
    if not restatement_text:
        raise RuntimeError(f"{department}: reply event carried no text")

    before = await _poll_search(
        custody,
        user_id=user_id,
        query=f"{department} escalation",
        contains=restatement_text,
        deadline=time.monotonic() + 90,
    )
    if restatement_text not in before:
        raise RuntimeError(f"{department}: restatement not retrievable within 90s")

    return {
        "user_id": user_id,
        "conversational_fact_contains": proof_id[:8],
        "conversational_agent_run_completed": True,
        "conversational_runner_event_count": len(conversational_events),
        "citation_record_id": citation_record.id,
        "citation_derived_from": list(citation_record.derived_from),
        "cited_text": cited_text,
        "restatement_record_id": restatement_record.id,
        "restatement_derived_from": list(restatement_record.derived_from),
        "restatement": restatement_text,
        "before_revoke_facts": before,
        "after_revoke_facts": None,
        "conversational_after_revoke_facts": None,
    }


async def _sibling_leg(
    custody: CustodyMemoryBank, *, proof_id: str
) -> dict[str, object]:
    user_id = f"chain-{SIBLING_DEPARTMENT}-{proof_id[:12]}"
    fact = f"Engineering pipeline note {proof_id[:8]}: release greenlit after review."
    invocation = f"chain-{SIBLING_DEPARTMENT}-tool-{proof_id[:12]}"
    event = AdkEvent(
        invocation_id=invocation,
        author=f"custody_chain_{SIBLING_DEPARTMENT}_agent",
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=f"{invocation}-fr",
                        name=SIBLING_TOOL,
                        response={"result": fact},
                    )
                )
            ],
        ),
    )
    session = Session(
        id=f"{user_id}-tool",
        app_name=APP_NAME,
        user_id=user_id,
        events=[event],
    )
    splits_before = len(custody.splits())
    await custody.add_session_to_memory(session)
    split = custody.splits()[splits_before]
    if len(split.trusted) != 1:
        raise RuntimeError(
            f"{SIBLING_DEPARTMENT}: expected 1 trusted record, got {len(split.trusted)}"
        )
    record = split.trusted[0].record

    before = await _poll_search(
        custody,
        user_id=user_id,
        query="engineering pipeline note",
        contains=fact,
        deadline=time.monotonic() + 90,
    )
    if fact not in before:
        raise RuntimeError(f"{SIBLING_DEPARTMENT}: tool fact not retrievable within 90s")

    return {
        "user_id": user_id,
        "tool": SIBLING_TOOL,
        "tool_record_id": record.id,
        "tool_fact": fact,
        "before_revoke_facts": before,
        "after_revoke_facts": None,
    }


async def _confirm_chain_removed(
    custody: CustodyMemoryBank, *, department: str, record: dict[str, object]
) -> None:
    """Post-revocation: the chain restatement is gone, but this department's
    own unrelated conversational memory survives untouched.
    """
    query = {
        "sales": "vendor audit note",
        "support": "support escalation",
        "finance": "finance escalation",
    }[department]
    target = record["restatement"]
    deadline = time.monotonic() + 90
    facts = record["before_revoke_facts"]
    while time.monotonic() < deadline:
        facts = await custody.search_memory(
            app_name=APP_NAME, user_id=record["user_id"], query=query
        )
        if target not in facts:
            break
        await asyncio.sleep(3)
    record["after_revoke_facts"] = facts
    if target in facts:
        raise RuntimeError(
            f"{department}: chain restatement still retrievable 90s after revocation"
        )

    conv_query = "vendor onboarding memo" if department == "sales" else "intake note"
    conv_deadline = time.monotonic() + 20
    conv_facts: list[str] = []
    while time.monotonic() < conv_deadline:
        conv_facts = await custody.search_memory(
            app_name=APP_NAME, user_id=record["user_id"], query=conv_query
        )
        if any(record["conversational_fact_contains"] in f for f in conv_facts):
            break
        await asyncio.sleep(3)
    record["conversational_after_revoke_facts"] = conv_facts
    if not any(record["conversational_fact_contains"] in f for f in conv_facts):
        raise RuntimeError(
            f"{department}: unrelated conversational memory was also removed "
            "by the chain-tool revocation, which should not have touched it"
        )


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
    tools = ToolTrust(trusted=frozenset({CHAIN_TOOL, SIBLING_TOOL}))
    #: One shared instance, one shared graph -- required for support's and
    #: finance's load_memory citations to resolve against records an
    #: earlier department wrote.
    custody = CustodyMemoryBank(downstream=downstream, tools=tools)

    sales = await _sales_leg(custody, project=project, proof_id=proof_id)
    support = await _derived_leg(
        custody,
        project=project,
        department="support",
        proof_id=proof_id,
        cited_text=sales["restatement"],
        cited_record_id=sales["restatement_record_id"],
    )
    finance = await _derived_leg(
        custody,
        project=project,
        department="finance",
        proof_id=proof_id,
        cited_text=support["restatement"],
        cited_record_id=support["restatement_record_id"],
    )
    engineering = await _sibling_leg(custody, proof_id=proof_id)

    departments = {"sales": sales, "support": support, "finance": finance}

    revoking_graph = RevokingMemoryBankGraph(
        graph=custody.graph(),
        memories=downstream.memories,
        engine_name=downstream.engine_name,
    )
    revocation = await revoking_graph.revoke(
        tool=CHAIN_TOOL, revocation_id=f"chain-revoke-{proof_id}"
    )

    expected_removed = sorted(
        [
            sales["tool_record_id"],
            sales["restatement_record_id"],
            support["citation_record_id"],
            support["restatement_record_id"],
            finance["citation_record_id"],
            finance["restatement_record_id"],
        ]
    )
    if sorted(revocation.removed) != expected_removed:
        raise RuntimeError(
            "revocation did not remove exactly the six expected chain-hop "
            f"records: got {sorted(revocation.removed)}, expected {expected_removed}"
        )

    for department, record in departments.items():
        await _confirm_chain_removed(custody, department=department, record=record)

    engineering_after = await custody.search_memory(
        app_name=APP_NAME, user_id=engineering["user_id"], query="engineering pipeline note"
    )
    engineering["after_revoke_facts"] = engineering_after
    if engineering["tool_fact"] not in engineering_after:
        raise RuntimeError(
            "engineering: the chain-tool revocation also removed the "
            "sibling department's own, unrelated tool-origin memory"
        )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "location": location,
        "agent_engine": downstream.engine_name,
        "claim_boundary": CLAIM_BOUNDARY,
        "chain_tool": CHAIN_TOOL,
        "chain_departments": list(CHAIN_DEPARTMENTS),
        "sibling_department": SIBLING_DEPARTMENT,
        "sibling_tool": SIBLING_TOOL,
        "departments": departments,
        "sibling": engineering,
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
        print(f"live chain proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live chain evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
