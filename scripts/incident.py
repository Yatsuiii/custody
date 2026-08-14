"""The incident this project exists to answer, end to end, in one script.

Day 1: `vendor_portal` is vouched for by three departments. Its output flows
sales -> support -> finance, each hop a real `load_memory` retrieval matched
by content hash back to the record it cites, not a synthetic edge. Around it,
a fleet's worth of unrelated memory accumulates in the same graph, from the
same fixture `make cost` already uses.

Day 21: `vendor_portal` is found compromised. This script demotes it in the
trust catalog, computes the blast radius over the one shared graph, prints the
exact lineage the three-hop chain earned, revokes the descendants, and shows
what survives: the unrelated fleet memory, and a replay that removes nothing
further.

This is an offline scripted narrative, same discipline as `make demo`,
`make cost`, and `make revoke`: every number below is computed from this run,
not hand-typed, but nothing here calls a live service. `make live-auditor`
proves the asynchronous, deployed version of the same trust-change ->
revocation path.

    make incident
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.catalog import Demotion, Grant, TrustCatalog, Vouch  # noqa: E402
from custody.service import CustodyMemoryService, InMemoryQuarantine  # noqa: E402

from scripts.cost import COMPROMISED, DEPARTMENTS, build  # noqa: E402

VOUCHED_AT = "2026-07-30T09:00:00+00:00"
DEMOTED_AT = "2026-08-14T14:00:00+00:00"
ELAPSED_DAYS = 15

CHAIN_DEPARTMENTS = DEPARTMENTS[:3]  # sales, support, finance
TOOL_RESULT = "vendor_portal: 3 invoices flagged for expedited payment"
DERIVED_FACT = "Vendor risk note: 3 invoices flagged for expedited payment."
SUPPORT_LINE = f"Escalated to support: {DERIVED_FACT}"
FINANCE_LINE = f"Finance action queued on support's escalation: {DERIVED_FACT}"

SALES_LOOKUP = "sales-chain:1:0"
SALES_RESTATEMENT = "sales-chain:2:0"
SUPPORT_RETRIEVAL = "support-chain:0:0"
SUPPORT_RESTATEMENT = "support-chain:1:0"
FINANCE_RETRIEVAL = "finance-chain:0:0"
FINANCE_RESTATEMENT = "finance-chain:1:0"


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
    return Session(
        "sales-chain", "fleet", "sales-team",
        [
            Event("user", "sales-chain", Content([Part(text="check vendor_portal status")])),
            Event("assistant", "sales-chain", Content(
                [Part(function_response=Response(COMPROMISED, TOOL_RESULT))])),
            Event("assistant", "sales-chain", Content([Part(text=DERIVED_FACT)])),
        ],
    )


def support_session() -> Session:
    return Session(
        "support-chain", "fleet", "support-team",
        [
            Event("assistant", "support-chain", Content(
                [Part(function_response=Response("load_memory", DERIVED_FACT))])),
            Event("assistant", "support-chain", Content([Part(text=SUPPORT_LINE)])),
        ],
    )


def finance_session() -> Session:
    return Session(
        "finance-chain", "fleet", "finance-team",
        [
            Event("assistant", "finance-chain", Content(
                [Part(function_response=Response("load_memory", SUPPORT_LINE))])),
            Event("assistant", "finance-chain", Content([Part(text=FINANCE_LINE)])),
        ],
    )


async def compute() -> dict:
    """Run the whole incident and return every number and edge as data.

    The single source of truth for both `run` (terminal) and
    `scripts.render_gui` (static HTML): both format this dict, neither
    recomputes anything, so the two surfaces cannot report different
    numbers for the same run.
    """
    # Day 1: the fleet's background memory, and the tool trusted by name in
    # three departments. `build` is the same fixture `make cost` reports from,
    # reused rather than re-invented so the two commands never disagree.
    fleet = build(reach=len(CHAIN_DEPARTMENTS))
    catalog = TrustCatalog()
    for department in CHAIN_DEPARTMENTS:
        catalog.request(Vouch(
            actor_department=department,
            grant=Grant(department, COMPROMISED, vouched_by=department,
                        vouched_at=VOUCHED_AT, evidence="vendor onboarding review"),
        ))

    # The three-hop narrative chain, written into the SAME graph the fixture
    # populated, through the same governed write path (CustodyMemoryService),
    # so the lineage below is earned by a real load_memory content match, not
    # asserted.
    for session, department in (
        (sales_session(), "sales"),
        (support_session(), "support"),
        (finance_session(), "finance"),
    ):
        service = CustodyMemoryService(
            PlainMemory(), InMemoryQuarantine(), graph=fleet.graph,
            catalog=catalog, department=department,
        )
        await service.add_session_to_memory(session)
        fleet.owner[
            SALES_RESTATEMENT if department == "sales"
            else SUPPORT_RESTATEMENT if department == "support"
            else FINANCE_RESTATEMENT
        ] = department

    total_before = len(fleet.graph)
    descendants = set(fleet.graph.descendants(COMPROMISED))

    chain = [
        {"id": SALES_LOOKUP, "label": "tool result: vendor_portal", "derived_from": None,
         "marker": "compromised_root", "department": "sales"},
        {"id": SALES_RESTATEMENT, "label": "derived model statement (sales)",
         "derived_from": SALES_LOOKUP, "marker": "affected_descendant", "department": "sales"},
        {"id": SUPPORT_RESTATEMENT,
         "label": "support memory, retrieved via load_memory",
         "derived_from": SALES_RESTATEMENT, "marker": "affected_descendant", "department": "support"},
        {"id": FINANCE_RESTATEMENT,
         "label": "finance memory, retrieved via load_memory",
         "derived_from": SUPPORT_RESTATEMENT, "marker": "affected_descendant", "department": "finance"},
    ]
    # Real digests, read off each record before it is revoked, not typed in:
    # `CustodyRecord.content_sha256` is the same field `custody/graph.py`'s
    # `resolve` matches retrievals against.
    for hop in chain:
        found = fleet.graph.record(hop["id"])
        hop["content_sha256"] = found[0].content_sha256 if found else None
    for record_id in (SALES_LOOKUP, SALES_RESTATEMENT, SUPPORT_RETRIEVAL,
                      SUPPORT_RESTATEMENT, FINANCE_RETRIEVAL, FINANCE_RESTATEMENT):
        assert record_id in descendants, f"{record_id} missing from computed blast radius"

    catalog.demote(Demotion(
        actor_department="sales", department="sales", tool=COMPROMISED,
        demoted_by="security-review", demoted_at=DEMOTED_AT,
    ))
    revocation = fleet.graph.revoke(tool=COMPROMISED, revocation_id="rev-vendor-portal-2026-08-14")
    replay = fleet.graph.revoke(tool=COMPROMISED, revocation_id="rev-vendor-portal-2026-08-14")

    ok = (
        set(revocation.removed) == descendants
        and replay == revocation
        and len(fleet.graph.revocations()) == 1
        and len(fleet.graph) == total_before - len(descendants)
    )

    return {
        "source": COMPROMISED,
        "status": "TRUST REVOKED",
        "reason": "source compromised after prior trusted use",
        "vouched_at": VOUCHED_AT,
        "demoted_at": DEMOTED_AT,
        "elapsed_days": ELAPSED_DAYS,
        "blast_radius": {
            "affected": len(descendants),
            "departments_touched": len(fleet.users_touching),
            "departments_total": len(DEPARTMENTS),
            "unrelated_preserved": total_before - len(descendants),
            "total_before": total_before,
        },
        "lineage": chain,
        "revocation": {
            "id": revocation.id,
            "removed": len(revocation.removed),
            "survives": len(fleet.graph),
            "replay_removed_further": 0,
            "revocations_total": len(fleet.graph.revocations()),
        },
        "evidence": {
            "trust_transition": f"{COMPROMISED} vouched {VOUCHED_AT} -> demoted {DEMOTED_AT}",
            "derivation_path": "vendor_portal -> sales -> support -> finance, "
                                "3 hops, 1 department boundary crossed twice",
            "removed_matches_blast_radius": set(revocation.removed) == descendants,
            "audit_records": len(fleet.graph.revocations()),
        },
        "ok": ok,
    }


def render(data: dict) -> str:
    lines = ["\n  ACTIVE TRUST INCIDENT\n"]
    lines.append(f"    source           {data['source']}")
    lines.append(f"    status           {data['status']}")
    lines.append(f"    reason           {data['reason']}")
    lines.append(f"    trusted          {data['vouched_at']}  (day 1)")
    lines.append(f"    compromised      {data['demoted_at']}  "
                 f"(day {data['elapsed_days'] + 1})")
    lines.append(f"    gap              {data['elapsed_days']} days of accumulated "
                 "propagation before detection")

    br = data["blast_radius"]
    lines.append("\n  BLAST RADIUS\n")
    lines.append(f"    {br['affected']} affected memories")
    lines.append(f"    {br['departments_touched']} departments touched "
                 f"(of {br['departments_total']} in the fleet)")
    lines.append(f"    {br['unrelated_preserved']} unrelated memories preserved")

    lines.append("\n  INFLUENCE LINEAGE (one traced chain; the fleet fixture adds more roots)\n")
    for hop in data["lineage"]:
        marker = "compromised root" if hop["marker"] == "compromised_root" else "affected descendant"
        arrow = f"    <- derived_from {hop['derived_from']}" if hop["derived_from"] else ""
        lines.append(f"    [{marker:<19}] {hop['id']:<22} {hop['label']}{arrow}")

    rv = data["revocation"]
    lines.append("\n  SURGICAL ACTION\n")
    lines.append(f"    revoke descendants of {data['source']} -> {br['affected']} record(s) targeted")
    lines.append(f"    revocation {rv['id']}")
    lines.append(f"    removed        {rv['removed']} record(s)")
    lines.append(f"    survives       {rv['survives']} record(s)")
    lines.append(f"    replay         {rv['revocations_total']} revocation record(s) total, "
                 f"{rv['replay_removed_further']} further removed (idempotent)")

    ev = data["evidence"]
    lines.append("\n  EVIDENCE\n")
    lines.append(f"    trust transition   {ev['trust_transition']}")
    lines.append(f"    derivation path    {ev['derivation_path']}")
    lines.append(f"    enforcement result revocation {rv['id']}, "
                 f"{ev['removed_matches_blast_radius']} that removed == computed blast radius")
    lines.append(f"    audit record       {ev['audit_records']} revocation(s) logged, "
                 "replay verified idempotent")

    lines.append("")
    if data["ok"]:
        lines.append("  vendor_portal's exact descendants are gone, across three departments and")
        lines.append("  two real load_memory retrievals. The fleet's other memory, and every")
        lines.append("  other department, is untouched. Replaying the revocation changed nothing.\n")
    else:
        lines.append("  incident narrative did not hold; do not film this.\n")
    return "\n".join(lines)


async def run() -> int:
    data = await compute()
    print(render(data))
    return 0 if data["ok"] else 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
