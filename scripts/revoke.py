"""G3: a tool trusted on day one, demoted on day N, offline.

Two departments, one `CustodyMemoryService`, one graph. Sales looks a
customer up through `crm_lookup`, trusted on day one, and restates the
balance. Support later retrieves that exact restatement through
`load_memory`, ADK's own retrieval tool, and confirms it to the customer.
Neither department ever quarantined anything: both writes were trusted at
the time they happened.

Day N, `crm_lookup` is found compromised. This script demotes it and shows
the graph before, the revocation record, the graph after, and a replay that
removes nothing further and creates no duplicate record. The removed set
reaches three hops deep across both departments, because the retrieval
carries a real `derived_from` edge back to the sales record it cited, earned
by an exact content match through `CustodyMemoryService`, not written in by
hand for the demo.

    make revoke
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.origin import ToolTrust  # noqa: E402
from custody.service import CustodyMemoryService, InMemoryQuarantine  # noqa: E402

COMPROMISED_TOOL = "crm_lookup"
BALANCE = "Acme's outstanding balance is 5000."

# The deterministic ids `take_custody` assigns: "{invocation}:{event index}:
# {part index}". Named here rather than discovered, so the script asserts
# exactly what it claims to demonstrate.
SALES_USER_TURN = "sales-inv-1:0:0"
SALES_LOOKUP = "sales-inv-1:1:0"
SALES_RESTATEMENT = "sales-inv-1:2:0"
SUPPORT_RETRIEVAL = "support-inv-1:0:0"
SUPPORT_CONFIRMATION = "support-inv-1:1:0"


@dataclass
class Response:
    name: str
    response: object


@dataclass
class Part:
    text: str | None = None
    function_response: Response | None = None


@dataclass
class Content:
    parts: list = field(default_factory=list)


@dataclass
class Event:
    author: str
    invocation_id: str
    content: Content | None


@dataclass
class Session:
    id: str
    app_name: str
    user_id: str
    events: list


@dataclass
class PlainMemory:
    written: list = field(default_factory=list)

    async def add_session_to_memory(self, session) -> None:
        self.written.extend(session.events)

    async def search_memory(self, *, app_name, user_id, query):
        del app_name, user_id, query
        return list(self.written)


def sales_session() -> Session:
    """Day one: `crm_lookup` is trusted, so the lookup and the restatement are
    both admitted as TRUSTED. Nothing here is quarantined."""
    return Session(
        id="sales-1",
        app_name="fleet",
        user_id="sales-team",
        events=[
            Event("user", "sales-inv-1", Content([Part(text="what does Acme owe?")])),
            Event(
                "assistant",
                "sales-inv-1",
                Content([Part(function_response=Response(COMPROMISED_TOOL, "5000"))]),
            ),
            Event("assistant", "sales-inv-1", Content([Part(text=BALANCE)])),
        ],
    )


def support_session() -> Session:
    """Day three: a different department retrieves the sales restatement
    through `load_memory`, word for word, and confirms it to the customer."""
    return Session(
        id="support-1",
        app_name="fleet",
        user_id="support-team",
        events=[
            Event(
                "assistant",
                "support-inv-1",
                Content([Part(function_response=Response("load_memory", BALANCE))]),
            ),
            Event(
                "assistant",
                "support-inv-1",
                Content([Part(text=f"Confirmed with the customer: {BALANCE}")]),
            ),
        ],
    )


def show(service: CustodyMemoryService, label: str) -> None:
    print(f"    {label}: {len(service.graph)} record(s)")
    for record in service.graph.records():
        edges = f" <- {record.derived_from}" if record.derived_from else ""
        print(
            f"        {record.id:<24} {record.origin.value:<8} "
            f"{record.trust.value}{edges}"
        )


async def run() -> int:
    print("\n  A tool trusted on day one, demoted on day N.\n")

    tools = ToolTrust(trusted=frozenset({COMPROMISED_TOOL}))
    service = CustodyMemoryService(PlainMemory(), InMemoryQuarantine(), tools)

    for session, label in ((sales_session(), "sales"), (support_session(), "support")):
        split = await service.add_session_to_memory(session)
        print(f"    {label:<8} {split.total} event(s) seen, {split.withheld} withheld")

    print()
    show(service, "before revocation")

    print(f"\n    demoting {COMPROMISED_TOOL}\n")
    revocation = service.graph.revoke(
        tool=COMPROMISED_TOOL, revocation_id="rev-2026-08-N"
    )
    print(f"    revocation {revocation.id}: removed {len(revocation.removed)} record(s)")
    for record_id in revocation.removed:
        print(f"        {record_id}")

    show(service, "after revocation")

    before_replay = len(service.graph)
    replay = service.graph.revoke(
        tool=COMPROMISED_TOOL, revocation_id="rev-2026-08-N"
    )
    # Report what the replay *did*, not what the stored revocation says it did
    # once. Printing len(replay.removed) here reads as though four more records
    # were deleted, which is the opposite of the property being demonstrated,
    # and this line is a candidate for the demo video.
    print(
        f"\n    replay: {before_replay - len(service.graph)} further record(s) "
        f"removed, {len(service.graph.revocations())} revocation record(s) total"
    )

    expected_removed = {
        SALES_LOOKUP,
        SALES_RESTATEMENT,
        SUPPORT_RETRIEVAL,
        SUPPORT_CONFIRMATION,
    }
    surviving = {r.id for r in service.graph.records()}

    ok = (
        set(revocation.removed) == expected_removed
        and surviving == {SALES_USER_TURN}
        and replay == revocation
        and len(service.graph.revocations()) == 1
    )
    print()
    if ok:
        print("  Every record descended from the compromised tool is gone, across")
        print("  two departments and a real load_memory retrieval, not a synthetic")
        print("  edge. The user's own question, unrelated to the tool, survives.")
        print("  The replay removed nothing further and left exactly one")
        print("  revocation record.\n")
        return 0
    print("  G3 did not hold; do not film this.\n")
    return 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
