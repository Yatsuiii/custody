"""G4: cross-department isolation, offline.

Two adversarial attempts: sales tries to vouch for a tool on support's
boundary, and support tries the reverse. Both are refused and both are
retained for audit. Then the positive case: sales genuinely vouches for its
own tool, support's own `CustodyMemoryService` still quarantines the exact
same tool call, because trust is read fresh from the catalog and the catalog
has no grant for support. Last, the read side: content quarantined under
sales' scope is invisible to support's quarantine view, and vice versa.

    make isolate
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.catalog import Grant, TrustCatalog, Vouch  # noqa: E402
from custody.service import CustodyMemoryService, InMemoryQuarantine  # noqa: E402

COMPROMISED_TOOL = "backdoor_tool"
SHARED_TOOL = "crm_lookup"


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


def lookup_session(department: str, invocation: str) -> Session:
    return Session(
        id=f"{department}-1",
        app_name="fleet",
        user_id=department,
        events=[
            Event(
                "assistant",
                invocation,
                Content([Part(function_response=Response(SHARED_TOOL, "500"))]),
            )
        ],
    )


def grant(department: str, tool: str) -> Grant:
    return Grant(
        department=department,
        tool=tool,
        vouched_by=f"{department}-admin",
        vouched_at="2026-08-10T00:00:00Z",
    )


async def main() -> int:
    print("\n  Two departments. One catalog. No shared trust unless earned.\n")
    catalog = TrustCatalog()

    print("  -- adversarial attempts --")
    first = catalog.request(Vouch("sales", grant("support", COMPROMISED_TOOL)))
    second = catalog.request(Vouch("support", grant("sales", COMPROMISED_TOOL)))
    for label, decision in (("sales -> support", first), ("support -> sales", second)):
        print(f"    {label}: {'ALLOWED' if decision.allowed else 'REFUSED'}")
        print(f"        {decision.reason()}")
    audited_ok = len(catalog.denials()) == 2

    print("\n  -- sales vouches for its own tool --")
    catalog.request(Vouch("sales", grant("sales", SHARED_TOOL)))
    print(f"    sales trusts {SHARED_TOOL}: "
          f"{SHARED_TOOL in catalog.trust_for('sales').trusted}")
    print(f"    support trusts {SHARED_TOOL}: "
          f"{SHARED_TOOL in catalog.trust_for('support').trusted}")

    sales = CustodyMemoryService(
        PlainMemory(), InMemoryQuarantine(), catalog=catalog, department="sales"
    )
    support = CustodyMemoryService(
        PlainMemory(), InMemoryQuarantine(), catalog=catalog, department="support"
    )

    sales_split = await sales.add_session_to_memory(
        lookup_session("sales", "sales-inv-1")
    )
    support_split = await support.add_session_to_memory(
        lookup_session("support", "support-inv-1")
    )
    print(f"\n    sales session withheld:   {sales_split.withheld} "
          f"(vouched, should be 0)")
    print(f"    support session withheld: {support_split.withheld} "
          f"(never vouched, should be 1)")
    enforcement_ok = sales_split.withheld == 0 and support_split.withheld == 1

    print("\n  -- quarantine, read side --")
    support_view = support.quarantine.held(app_name="fleet", user_id="support")
    sales_view = sales.quarantine.held(app_name="fleet", user_id="sales")
    print(f"    support's own quarantine: {len(support_view)} item(s)")
    print(f"    sales' own quarantine:    {len(sales_view)} item(s)")
    isolation_ok = len(support_view) == 1 and len(sales_view) == 0

    ok = audited_ok and enforcement_ok and isolation_ok
    print()
    if ok:
        print("  Neither department could write into the other's boundary, trust")
        print("  earned in one department did not leak into the other's writes,")
        print("  and nothing quarantined in one is visible from the other.\n")
        return 0
    print("  G4 did not hold; do not film this.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
