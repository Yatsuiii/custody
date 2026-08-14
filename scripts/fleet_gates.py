"""Independently judge the live N-department fleet artifact.

Two layers, same discipline as `auditor_gates.py`: offline structural
checks against the producer's own JSON (department count, the shared-tool
revocation's recomputed record-id set), then a live reread of Vertex AI
Memory Bank itself -- `memories.get` by a `{engine_name}/memories/<id>}`
name this script recomputes from `memory_id_for`, not the producer's claim
-- confirming the two shared-tool memories are actually gone and one
sibling department's own memory actually still exists.
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
from scripts.live_fleet import DEPARTMENT_TOOLS, SHARED_TOOL_DEPARTMENTS  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-fleet.json"


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    departments = evidence["departments"]
    shared = evidence["shared_tool_departments"]
    untouched = evidence["untouched_departments"]
    revocation = evidence["revocation"]

    expected_removed_ids = sorted(departments[d]["tool_record_id"] for d in shared)

    expected_untouched = set(DEPARTMENT_TOOLS) - set(SHARED_TOOL_DEPARTMENTS)

    return {
        "fresh_live_evidence": fresh,
        "every_expected_department_ran": set(departments) == set(DEPARTMENT_TOOLS),
        "shared_tool_used_by_exactly_the_expected_departments": (
            set(shared) == set(SHARED_TOOL_DEPARTMENTS)
        ),
        "remaining_departments_left_untouched": set(untouched) == expected_untouched,
        "every_department_wrote_and_retrieved_its_own_tool_fact": all(
            d["tool_fact"] in d["before_revoke_facts"] for d in departments.values()
        ),
        "revocation_named_the_shared_tool": (
            revocation["tool"] == evidence["shared_tool"]
        ),
        "revocation_removed_exactly_the_two_sharing_departments_records": (
            sorted(revocation["removed"]) == expected_removed_ids
        ),
        "shared_tool_fact_gone_from_both_sharing_departments_after_revoke": all(
            departments[d]["tool_fact"] not in departments[d]["after_revoke_facts"]
            for d in shared
        ),
        "unrelated_departments_kept_their_own_tool_fact_after_revoke": all(
            v["tool_fact_still_present"] for v in untouched.values()
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
    shared = evidence["shared_tool_departments"]
    untouched = evidence["untouched_departments"]

    results: dict[str, bool] = {}
    for department in shared:
        record_id = departments[department]["tool_record_id"]
        name = f"{engine_name}/memories/{memory_id_for(record_id)}"
        exists = await _memory_exists(client, name)
        results[f"live_reread_confirms_{department}_shared_memory_is_gone"] = (
            not exists
        )
    for department in untouched:
        record_id = departments[department]["tool_record_id"]
        name = f"{engine_name}/memories/{memory_id_for(record_id)}"
        exists = await _memory_exists(client, name)
        results[f"live_reread_confirms_{department}_own_memory_still_exists"] = exists
    return results


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-fleet.json")
        print("          run make live-fleet")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live fleet evidence: {error}")
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
