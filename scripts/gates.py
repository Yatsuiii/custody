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
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.action import Export, ExportGateway  # noqa: E402
from custody.catalog import TrustCatalog, Vouch  # noqa: E402
from custody.memory_bank import memory_id_for  # noqa: E402
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
from scripts.gateway_gates import judge as judge_gateway  # noqa: E402
from scripts.observability_gates import judge as judge_observability  # noqa: E402
from scripts.registry_gates import judge as judge_registry  # noqa: E402
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
        return (
            f"  {mark[self.state]} {self.gate} {self.title}\n            {self.detail}"
        )


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
    departments_before = {
        r.invocation_id.split("-")[0] for r in service.graph.records()
    }
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
    cross = catalog.request(Vouch("sales", grant("support", "their_tool")))
    own = catalog.request(Vouch("sales", grant("sales", COMPROMISED_TOOL)))
    return {
        "cross_department_vouch_allowed": cross.allowed,
        "cross_department_reason": cross.reason(),
        "own_department_vouch_allowed": own.allowed,
        "sales_trusts": sorted(catalog.trust_for("sales").trusted),
        "support_trusts": sorted(catalog.trust_for("support").trusted),
    }


# -- phase two: judge by reading the files back ------------------------------


def _model_at_least_3_5(model: object) -> bool:
    match = re.search(r"gemini-(\d+)\.(\d+)", str(model or ""))
    return bool(match and tuple(map(int, match.groups())) >= (3, 5))


def _expected_memory(fact: object) -> bool:
    normalized = str(fact or "").lower()
    return "sales export" in normalized and "signed approval" in normalized


def _g1_cloud_run_errors(cloud: dict, *, expected_scope: str) -> list[str]:
    errors: list[str] = []
    trigger = cloud.get("trigger", {})
    if not cloud.get("ready"):
        errors.append("Cloud Run is not Ready")
    if cloud.get("traffic_percent") != 100:
        errors.append("Cloud Run does not serve 100% traffic")
    if not cloud.get("revision") or not cloud.get("url"):
        errors.append("Cloud Run revision or URL is absent")
    if cloud.get("health", {}).get("status") != "ok":
        errors.append("Cloud Run health is not ok")
    if (
        trigger.get("department") != expected_scope
        or not trigger.get("run_id")
        or trigger.get("seen") != 1
        or trigger.get("admitted") != 1
        or trigger.get("quarantined") != 0
        or trigger.get("refused") != 0
    ):
        errors.append("Cloud Run trigger is incomplete or belongs to another proof")
    return errors


def _g1_gemini_errors(gemini: dict, *, proof_id: str) -> list[str]:
    errors: list[str] = []
    expected_response = f"CUSTODY_G1_OK:{proof_id}"
    if not gemini.get("vertex"):
        errors.append("Gemini call is not marked as Vertex AI")
    if not _model_at_least_3_5(gemini.get("requested_model")):
        errors.append("requested Gemini model is older than 3.5")
    if not _model_at_least_3_5(gemini.get("model_version")):
        errors.append("served Gemini model is older than 3.5")
    if (
        gemini.get("response") != expected_response
        or gemini.get("expected_response") != expected_response
    ):
        errors.append("Gemini response is not bound to this proof id")
    return errors


def _g1_adk_run_errors(memory: dict, *, proof_id: str) -> list[str]:
    errors: list[str] = []
    if memory.get("framework") != "google-adk":
        errors.append("the live run did not identify google-adk")
    if not memory.get("agent_run_completed") or memory.get("runner_event_count", 0) < 1:
        errors.append("the ADK Runner did not complete with an event")
    if proof_id not in memory.get("agent_text", ""):
        errors.append("the ADK agent response is not bound to this proof id")
    if not _model_at_least_3_5(memory.get("configured_model")):
        errors.append("the ADK agent is not configured for Gemini 3.5+")
    return errors


def _g1_memory_bank_errors(
    memory: dict, *, expected_scope: str, project: str
) -> list[str]:
    """Migrated 2026-08-14 to D2's `write_record` path (`HANDOFF.md` "G1
    migration"): one `memories.create` per admitted record instead of one
    `ingest_events` call per session, so a written memory now carries an id
    a later revocation can target. Checks below match that shape and add the
    selective-deletion proof `ingest_events` could never offer.
    """
    errors: list[str] = []
    split = memory.get("custody_split", {})
    scope = memory.get("scope", {})
    if memory.get("write_path") != "write_record":
        errors.append("G1 is not on the write_record path")
    if scope.get("user_id") != expected_scope or scope.get("app_name") != "custody-g1":
        errors.append("Memory Bank scope is not unique to this proof")
    if memory.get("conversational_memory_write_count", 0) < 2:
        errors.append("Memory Bank did not receive both user and model events")
    if (
        split.get("total", 0) < 2
        or split.get("withheld") != 0
        or split.get("refused") != 0
    ):
        errors.append("Custody did not admit the complete clean ADK session")
    if memory.get("retrieved_memory_count", 0) < 1:
        errors.append("Memory Bank returned no memory")
    if not any(_expected_memory(fact) for fact in memory.get("retrieved_facts", [])):
        errors.append("retrieved memory does not preserve the submitted invariant")
    if project not in str(memory.get("agent_engine", "")):
        errors.append("Agent Engine belongs to another project")
    errors.extend(_g1_written_memory_id_errors(memory))
    errors.extend(_g1_revocation_errors(memory.get("revocation_proof", {})))
    return errors


def _g1_written_memory_id_errors(memory: dict) -> list[str]:
    """Every written id must both look like `memory_id_for`'s own output and
    include the independently recomputed id for the record the revocation
    proof below claims to have written and later deleted.
    """
    errors: list[str] = []
    written_ids = memory.get("written_memory_ids", [])
    if memory.get("memory_write_count") != len(written_ids) or not written_ids:
        errors.append("write_record call count does not match written memory ids")
    if any(not str(name).startswith("cr-") for name in written_ids):
        errors.append("a written memory id does not match memory_id_for's own mapping")
    tool_record_id = memory.get("revocation_proof", {}).get("tool_record_id")
    if tool_record_id and memory_id_for(tool_record_id) not in written_ids:
        errors.append(
            "the tool record's independently recomputed memory_id was never written"
        )
    return errors


def _g1_revocation_errors(revocation: dict) -> list[str]:
    """G1's own selective-deletion proof: a tool-origin record this run
    wrote is confirmed retrievable, then confirmed gone after its tool is
    revoked, while the conversational memories (no source_tool) survive.
    """
    errors: list[str] = []
    tool_fact = revocation.get("tool_fact")
    before = revocation.get("before_revoke_facts", [])
    after = revocation.get("after_revoke_facts", [])
    if not str(revocation.get("tool_memory_id", "")).startswith("cr-"):
        errors.append("revoked memory id does not match memory_id_for's own mapping")
    if not tool_fact or tool_fact not in before:
        errors.append("the tool-origin memory was not retrievable before revocation")
    if tool_fact and tool_fact in after:
        errors.append("the tool-origin memory is still retrievable after revocation")
    if not any(_expected_memory(fact) for fact in after):
        errors.append("revocation removed the untooled conversational memory too")
    if not revocation.get("revocation_id"):
        errors.append("revocation produced no revocation id")
    return errors


def _g1_memory_errors(
    memory: dict, *, proof_id: str, expected_scope: str, project: str
) -> list[str]:
    return _g1_adk_run_errors(memory, proof_id=proof_id) + _g1_memory_bank_errors(
        memory, expected_scope=expected_scope, project=project
    )


def judge_g1(e: dict | None, *, now: datetime | None = None) -> Verdict:
    if e is None:
        return Verdict(
            "G1",
            "deployment and live substrate",
            "BLOCKED",
            "no proof-out/g1.json; run make live-g1 with the project and Agent "
            "Engine environment configured",
        )

    errors: list[str] = []
    try:
        proof_id = e["proof_id"]
        captured = datetime.fromisoformat(e["captured_at"])
        project = e["project"]
        cloud = e["cloud_run"]
        gemini = e["gemini"]
        memory = e["adk_memory_bank"]
    except (KeyError, TypeError, ValueError) as error:
        return Verdict(
            "G1",
            "deployment and live substrate",
            "FAIL",
            f"malformed g1.json: {error}",
        )

    current = now or datetime.now(UTC)
    if captured.tzinfo is None:
        errors.append("captured_at has no timezone")
    elif captured > current + timedelta(minutes=5):
        errors.append("captured_at is in the future")
    elif current - captured > timedelta(hours=24):
        return Verdict(
            "G1",
            "deployment and live substrate",
            "BLOCKED",
            "g1.json is older than 24 hours; rerun make live-g1",
        )

    expected_scope = f"g1-{proof_id}"
    errors.extend(_g1_cloud_run_errors(cloud, expected_scope=expected_scope))
    errors.extend(_g1_gemini_errors(gemini, proof_id=proof_id))
    errors.extend(
        _g1_memory_errors(
            memory, proof_id=proof_id, expected_scope=expected_scope, project=project
        )
    )

    if errors:
        return Verdict(
            "G1",
            "deployment and live substrate",
            "FAIL",
            "; ".join(errors),
        )
    return Verdict(
        "G1",
        "deployment and live substrate",
        "PASS",
        f"Cloud Run {cloud['revision']} is Ready; {gemini['model_version']} served "
        f"through Vertex; one ADK callback wrote and retrieved live Memory Bank "
        f"scope {expected_scope}",
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


def _all_live_gates_pass(evidence: dict | None, judge) -> bool:
    if evidence is None:
        return False
    try:
        gates = judge(evidence)
    except (AttributeError, KeyError, IndexError, TypeError, ValueError):
        return False
    return bool(gates) and all(gates.values())


def still_outstanding(missing: list[str]) -> str:
    """Name what G5 is waiting on, including when it is only elapsed time.

    Every capability group can be demonstrable while G5 is still BLOCKED,
    because the Cloud Scheduler record is a separate requirement. That case
    is the expected end state, so it has to read as a sentence rather than
    print an empty list into a line a judge reads.
    """
    if not missing:
        return "missing only a Cloud Scheduler record"
    return f"missing {', '.join(missing)} and a Cloud Scheduler record"


def judge_g5(e: dict) -> Verdict:
    groups = {
        "discovery/lifecycle": _all_live_gates_pass(e.get("registry"), judge_registry),
        "execution/state": judge_g1(e.get("g1")).state == "PASS",
        "security/governance": _all_live_gates_pass(e.get("gateway"), judge_gateway),
        # Judged from O1's own artifact, never inferred from Gateway request
        # logs: the observability judge is what requires the real Agent
        # Observability integration and its custody trace fields, so reusing
        # it here is what keeps that requirement honest. This group was
        # hardcoded False while O1 was unbuilt; leaving it hardcoded after
        # O1 landed made G5 unpassable for a reason that had stopped being
        # true, which is the failure this file exists to prevent.
        "telemetry": _all_live_gates_pass(e.get("observability"), judge_observability),
    }
    passed = [name for name, complete in groups.items() if complete]
    missing = [name for name, complete in groups.items() if not complete]
    outstanding = still_outstanding(missing)
    return Verdict(
        "G5",
        "four capability groups, with real elapsed time",
        "BLOCKED",
        f"{len(passed)} of 4 groups independently demonstrable "
        f"({', '.join(passed) or 'none'}); {outstanding} "
        "proving real elapsed time. Model Armor "
        "(`make model-armor-gates`) is live-proven and folds into "
        "security/governance; it is not itself a required G5 group.",
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
    read = {name: json.loads((OUT / f"{name}.json").read_text()) for name in produced}
    g1_path = OUT / "g1.json"
    try:
        g1 = json.loads(g1_path.read_text()) if g1_path.exists() else None
    except json.JSONDecodeError as error:
        g1 = {"malformed": str(error)}

    def read_optional(name: str) -> dict | None:
        path = OUT / name
        try:
            return json.loads(path.read_text()) if path.exists() else None
        except (OSError, json.JSONDecodeError):
            return None

    fleet_evidence = {
        "g1": g1,
        "registry": read_optional("live-registry-attack.json"),
        "gateway": read_optional("live-gateway.json"),
        "observability": read_optional("live-observability.json"),
    }

    verdicts = [
        judge_g1(g1),
        judge_g2(read["g2"]),
        judge_g3(read["g3"]),
        judge_g4(read["g4"]),
        judge_g5(fleet_evidence),
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
    print("  blocked gates name missing proof; they are not regressions\n")
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
