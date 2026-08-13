"""Judge the live D2 selective-deletion artifact, offline, same shape G1's
own gate uses (`scripts/gates.py` reads `proof-out/g1.json` back rather than
independently rereading Google Cloud): the artifact's own before/after
`search_memory` results are read back and cross-checked against the
independently recomputed `memory_id_for` mapping, not trusted narration.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.memory_bank import memory_id_for  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-memory-deletion.json"


def judge(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    if captured.tzinfo is None or captured > current + timedelta(minutes=5):
        return {"fresh_live_evidence": False}

    sales_fact = evidence["sales_fact"]
    finance_fact = evidence["finance_fact"]
    before = evidence["before_facts"]
    after = evidence["after_facts"]
    revocation = evidence["revocation"]

    expected_deleted_name = (
        f"{evidence['engine_name']}/memories/"
        f"{memory_id_for(evidence['sales_record_id'])}"
    )
    expected_surviving_name = (
        f"{evidence['engine_name']}/memories/"
        f"{memory_id_for(evidence['finance_record_id'])}"
    )

    return {
        "fresh_live_evidence": current - captured <= timedelta(hours=24),
        "both_facts_retrievable_before_revoke": (
            sales_fact in before and finance_fact in before
        ),
        "only_sales_tool_revoked": (
            revocation["tool"] == "sales/lookup"
            and revocation["removed"] == [evidence["sales_record_id"]]
        ),
        "sales_fact_gone_finance_fact_present_after_revoke": (
            sales_fact not in after and finance_fact in after
        ),
        "deleted_memory_name_matches_the_recomputed_mapping": (
            evidence["deleted_memory_name"] == expected_deleted_name
        ),
        "surviving_memory_name_is_the_other_record_untouched": (
            evidence["surviving_memory_name"] == expected_surviving_name
            and evidence["surviving_memory_name"] != evidence["deleted_memory_name"]
        ),
        "claim_boundary_names_ingest_events_as_out_of_scope": (
            "ingest_events" in evidence.get("claim_boundary", "")
        ),
    }


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-memory-deletion.json")
        print("          run make live-memory-deletion")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live memory-deletion evidence: {error}")
        return 1
    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
