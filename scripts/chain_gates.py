"""Independently judge the live cross-department derivation-chain artifact.

Same two-layer discipline as `fleet_gates.py`: offline structural checks
against the producer's own JSON (the chain's derived_from edges, the exact
six-record removed set), then a live reread of Vertex AI Memory Bank itself
-- `memories.get` by a `{engine_name}/memories/<id>}` name this script
recomputes from `memory_id_for`, not the producer's claim -- confirming the
six chain-hop memories are actually gone and the sibling's own memory
actually still exists.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplatform import Client  # noqa: E402
from google.genai.errors import ClientError  # noqa: E402

from custody.memory_bank import memory_id_for  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-chain.json"

CHAIN_RECORD_FIELDS = {
    "sales": ("tool_record_id", "restatement_record_id"),
    "support": ("citation_record_id", "restatement_record_id"),
    "finance": ("citation_record_id", "restatement_record_id"),
}


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    departments = evidence["departments"]
    sibling = evidence["sibling"]
    revocation = evidence["revocation"]

    expected_removed = sorted(
        departments[dept][field]
        for dept, fields in CHAIN_RECORD_FIELDS.items()
        for field in fields
    )

    support = departments["support"]
    finance = departments["finance"]
    sales = departments["sales"]

    return {
        "fresh_live_evidence": fresh,
        "three_chain_departments_ran": len(departments) == 3,
        "sales_restatement_derived_from_its_own_tool_root": (
            sales["restatement_derived_from"] == [sales["tool_record_id"]]
        ),
        "support_citation_content_hash_matched_sales_restatement": (
            support["citation_derived_from"] == [sales["restatement_record_id"]]
        ),
        "support_restatement_derived_from_its_own_citation": (
            support["restatement_derived_from"] == [support["citation_record_id"]]
        ),
        "finance_citation_content_hash_matched_support_restatement": (
            finance["citation_derived_from"] == [support["restatement_record_id"]]
        ),
        "finance_restatement_derived_from_its_own_citation": (
            finance["restatement_derived_from"] == [finance["citation_record_id"]]
        ),
        "every_department_wrote_and_retrieved_its_own_chain_fact": all(
            departments[d]["restatement"] in departments[d]["before_revoke_facts"]
            for d in departments
        ),
        "revocation_named_the_chain_tool": (
            revocation["tool"] == evidence["chain_tool"]
        ),
        "revocation_removed_exactly_the_six_chain_hop_records": (
            sorted(revocation["removed"]) == expected_removed
        ),
        "chain_facts_gone_from_all_three_departments_after_revoke": all(
            departments[d]["restatement"] not in departments[d]["after_revoke_facts"]
            for d in departments
        ),
        "each_departments_own_unrelated_memory_survived_the_revocation": all(
            any(
                departments[d]["conversational_fact_contains"] in f
                for f in departments[d]["conversational_after_revoke_facts"]
            )
            for d in departments
        ),
        "sibling_department_untouched_by_the_chain_revocation": (
            sibling["tool_fact"] in sibling["after_revoke_facts"]
        ),
        "claim_boundary_names_what_this_does_not_prove": (
            "TrustCatalog" in evidence.get("claim_boundary", "")
        ),
    }


async def _memory_exists(client: Client, name: str) -> bool:
    try:
        await client.aio.agent_engines.memories.get(name=name)
        return True
    except ClientError as error:
        if error.code == 404:
            return False
        raise


async def judge_live(evidence: dict) -> dict[str, bool]:
    """Reread Memory Bank directly, not the producer's before/after facts."""
    client = Client(project=evidence["project"], location=evidence["location"])
    engine_name = evidence["agent_engine"]
    departments = evidence["departments"]
    sibling = evidence["sibling"]

    results: dict[str, bool] = {}
    for department, fields in CHAIN_RECORD_FIELDS.items():
        for field in fields:
            record_id = departments[department][field]
            name = f"{engine_name}/memories/{memory_id_for(record_id)}"
            exists = await _memory_exists(client, name)
            results[f"live_reread_confirms_{department}_{field}_is_gone"] = not exists

    sibling_name = f"{engine_name}/memories/{memory_id_for(sibling['tool_record_id'])}"
    sibling_exists = await _memory_exists(client, sibling_name)
    results["live_reread_confirms_sibling_memory_still_exists"] = sibling_exists
    return results


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-chain.json")
        print("          run make live-chain")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live chain evidence: {error}")
        return 1

    if all(gates.values()):
        try:
            gates.update(asyncio.run(judge_live(evidence)))
        except Exception as error:  # noqa: BLE001 - report as a failed gate, not a crash
            gates["live_reread_of_memory_bank_succeeded"] = False
            print(f"[FAIL] live reread failed: {error}")

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
