"""Judge the acceptance gates from evidence on disk, not from prose.

Two phases, deliberately separated. First each gate's scenario runs and writes
what happened to `proof-out/`. Then the gates are judged by **reading those
files back**. Nothing here asserts a gate passed because the code that just ran
believes it did, which is the failure this project's predecessor was killed for.

A gate that needs the cloud account reports BLOCKED with the reason and the
command that will settle it. BLOCKED is not FAIL and must never be printed as
PASS.

    make gates
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.action import Export, ExportGateway  # noqa: E402
from custody.catalog import TrustCatalog, Vouch  # noqa: E402
from custody.service import CustodyMemoryService, InMemoryQuarantine  # noqa: E402

from scripts.demo import (  # noqa: E402
    ATTACKER,
    PAYLOAD,
    PlainMemory,
    instruction_carrying,
    texts,
    week_one,
)
from scripts.isolate import grant  # noqa: E402
from scripts.revoke import (  # noqa: E402
    COMPROMISED_TOOL,
    sales_session,
    support_session,
)

OUT = REPO_ROOT / "proof-out"


@dataclass(frozen=True)
class Verdict:
    gate: str
    title: str
    state: str
    detail: str

    def line(self) -> str:
        mark = {"PASS": "[PASS   ]", "FAIL": "[FAIL   ]", "BLOCKED": "[BLOCKED]"}
        return f"  {mark[self.state]} {self.gate} {self.title}\n            {self.detail}"


# -- phase one: run the scenarios, write what happened -----------------------


async def evidence_for_g2() -> dict:
    """Enforcement, with and without Custody, plus the recall cost it charged."""
    plain = PlainMemory()
    await plain.add_session_to_memory(week_one())
    ungoverned = texts(
        await plain.search_memory(
            app_name="fleet", user_id="platform-team", query="customer summaries"
        )
    )

    guarded = CustodyMemoryService(PlainMemory(), InMemoryQuarantine())
    await guarded.add_session_to_memory(week_one())
    governed = texts(
        await guarded.search_memory(
            app_name="fleet", user_id="platform-team", query="customer summaries"
        )
    )
    withheld, total = guarded.recall_cost()
    held = guarded.quarantine.held(app_name="fleet", user_id="platform-team")

    gateway = ExportGateway()
    decision = gateway.request(
        Export(ATTACKER, PAYLOAD, cited=tuple(h.record for h in held))
    )
    return {
        "ungoverned_carrying_instruction": len(instruction_carrying(ungoverned)),
        "governed_carrying_instruction": len(instruction_carrying(governed)),
        "export_allowed": decision.allowed,
        "export_reason": decision.reason(),
        "recall_withheld": withheld,
        "recall_total": total,
    }


async def evidence_for_g3() -> dict:
    """Revocation across departments and derivation hops, and its replay."""
    service = CustodyMemoryService(PlainMemory(), InMemoryQuarantine())
    service.tools = service.tools.__class__(frozenset({COMPROMISED_TOOL}))
    await service.add_session_to_memory(sales_session())
    await service.add_session_to_memory(support_session())

    before = len(service.graph)
    departments_before = {r.invocation_id.split("-")[0] for r in service.graph.records()}
    revocation = service.graph.revoke(tool=COMPROMISED_TOOL, revocation_id="rev-1")
    after = len(service.graph)

    replay_before = len(service.graph)
    service.graph.revoke(tool=COMPROMISED_TOOL, revocation_id="rev-1")
    return {
        "records_before": before,
        "records_after": after,
        "removed": len(revocation.removed),
        "departments_spanned": len(departments_before),
        "replay_removed_further": replay_before - len(service.graph),
        "revocation_records": len(service.graph.revocations()),
        "survivor_origins": [r.origin.value for r in service.graph.records()],
    }


async def evidence_for_g4() -> dict:
    """Cross-department isolation, on both the write side and the read side."""
    catalog = TrustCatalog()
    cross = catalog.request(
        Vouch("sales", grant("support", "their_tool"))
    )
    own = catalog.request(
        Vouch("sales", grant("sales", COMPROMISED_TOOL))
    )
    return {
        "cross_department_vouch_allowed": cross.allowed,
        "cross_department_reason": cross.reason(),
        "own_department_vouch_allowed": own.allowed,
        "sales_trusts": sorted(catalog.trust_for("sales").trusted),
        "support_trusts": sorted(catalog.trust_for("support").trusted),
    }


# -- phase two: judge by reading the files back ------------------------------


def judge_g1(_: dict | None) -> Verdict:
    return Verdict(
        "G1",
        "deployment and live substrate",
        "BLOCKED",
        "needs a Cloud Run service, a Vertex Gemini 3.5+ call, and live Memory "
        "Bank. No cloud account yet. Settled by: gcloud run services describe.",
    )


def judge_g2(e: dict) -> Verdict:
    structural = (
        e["ungoverned_carrying_instruction"] > 0
        and e["governed_carrying_instruction"] == 0
        and not e["export_allowed"]
    )
    return Verdict(
        "G2",
        "enforcement is structural, and reports its cost",
        "PASS" if structural else "FAIL",
        f"ungoverned retrieved {e['ungoverned_carrying_instruction']} instruction"
        f"-carrying memories, governed retrieved "
        f"{e['governed_carrying_instruction']}; export refused because "
        f"{e['export_reason']}; recall cost {e['recall_withheld']} of "
        f"{e['recall_total']} events withheld",
    )


def judge_g3(e: dict) -> Verdict:
    correct = (
        e["removed"] >= 4
        and e["records_after"] == e["records_before"] - e["removed"]
        and e["replay_removed_further"] == 0
        and e["revocation_records"] == 1
        and e["departments_spanned"] >= 2
        and e["survivor_origins"] == ["user"]
    )
    return Verdict(
        "G3",
        "retroactive revocation across the graph",
        "PASS" if correct else "FAIL",
        f"{e['removed']} of {e['records_before']} records removed across "
        f"{e['departments_spanned']} departments; survivors "
        f"{e['survivor_origins']}; replay removed "
        f"{e['replay_removed_further']} further and left "
        f"{e['revocation_records']} revocation record(s)",
    )


def judge_g4(e: dict) -> Verdict:
    isolated = (
        not e["cross_department_vouch_allowed"]
        and e["own_department_vouch_allowed"]
        and COMPROMISED_TOOL in e["sales_trusts"]
        and COMPROMISED_TOOL not in e["support_trusts"]
    )
    return Verdict(
        "G4",
        "cross-department isolation",
        "PASS" if isolated else "FAIL",
        f"cross-department vouch refused ({e['cross_department_reason']}); "
        f"sales trusts {e['sales_trusts']}, support trusts {e['support_trusts']}",
    )


def judge_g5(_: dict | None) -> Verdict:
    return Verdict(
        "G5",
        "four capability groups, with real elapsed time",
        "BLOCKED",
        "needs Agent Registry, Runtime, Identity, Gateway, Model Armor and "
        "Observability on a live project, plus Cloud Scheduler running daily "
        "from first deploy to filming. 0 of 4 groups demonstrable today.",
    )


async def main() -> int:
    OUT.mkdir(exist_ok=True)
    produced = {
        "g2": await evidence_for_g2(),
        "g3": await evidence_for_g3(),
        "g4": await evidence_for_g4(),
    }
    for name, evidence in produced.items():
        (OUT / f"{name}.json").write_text(json.dumps(evidence, indent=2))

    # Read it back. The judgement must not see the objects that made it.
    read = {
        name: json.loads((OUT / f"{name}.json").read_text()) for name in produced
    }

    verdicts = [
        judge_g1(None),
        judge_g2(read["g2"]),
        judge_g3(read["g3"]),
        judge_g4(read["g4"]),
        judge_g5(None),
    ]

    print(f"\nAcceptance gates, judged from {OUT.name}/\n")
    for verdict in verdicts:
        print(verdict.line())
        print()

    passed = sum(1 for v in verdicts if v.state == "PASS")
    failed = sum(1 for v in verdicts if v.state == "FAIL")
    blocked = sum(1 for v in verdicts if v.state == "BLOCKED")
    print(f"  {passed} passed, {failed} failed, {blocked} blocked")
    if failed:
        print("  a gate FAILED; this is a regression, not a missing account\n")
        return 1
    print("  blocked gates need the cloud account, not more code\n")
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
