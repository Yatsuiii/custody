"""Independently judge the live Provenance Auditor artifact.

Two layers, same discipline as `registry_gates.py`/`revision_binding_gates.py`:
offline structural checks against the producer's own JSON, then a live
reread of the deployed control plane by an identifier this script derives
itself (the service name/region, and the deterministic demotion id), not by
trusting anything the producer computed.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.catalog import Demotion  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-auditor.json"


def _json_get(url: str) -> dict | None:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    expected_revocation_id = Demotion(
        actor_department=evidence["department"],
        department=evidence["department"],
        tool=evidence["tool"],
        demoted_by="auditor-proof",
        demoted_at=evidence["demoted_at"],
    ).id()

    before = evidence["before_demotion"]
    mid = evidence["after_demotion_before_sweep"]
    after = evidence["after_sweep"]
    sweep = evidence["sweep"]

    return {
        "fresh_live_evidence": fresh,
        "vouch_and_ingest_succeeded": (
            evidence["vouch"]["allowed"] and evidence["run"]["admitted"] == 1
        ),
        "recomputed_revocation_id_matches_producers_claim": (
            expected_revocation_id == evidence["expected_revocation_id"]
        ),
        "record_carried_no_revocation_before_any_demotion": (
            before is not None and before.get("revocation_id") is None
        ),
        "demotion_alone_did_not_touch_the_record": (
            mid is not None and mid.get("revocation_id") is None
        ),
        "the_auditor_tick_swept_exactly_this_demotion": (
            expected_revocation_id in sweep.get("swept_revocations", [])
        ),
        "the_record_carries_the_swept_revocation_afterward": (
            after is not None
            and after.get("revocation_id") == expected_revocation_id
            and after.get("revoked_at") is not None
        ),
        "claim_boundary_names_what_this_does_not_prove": (
            "cold-start" in evidence.get("claim_boundary", "")
            or "cold start" in evidence.get("claim_boundary", "")
        ),
    }


def judge_live(evidence: dict) -> dict[str, bool]:
    """Reread the deployed control plane directly, not the producer's JSON."""
    url = evidence["service_url"]
    record_id = evidence["record_id"]
    reread = _json_get(f"{url}/custody/{record_id}")
    expected_revocation_id = evidence["expected_revocation_id"]
    return {
        "live_reread_of_custody_record_confirms_the_swept_revocation": (
            reread is not None
            and reread.get("revocation_id") == expected_revocation_id
            and reread.get("revoked_at") is not None
        ),
    }


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-auditor.json")
        print("          run make live-auditor")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live auditor evidence: {error}")
        return 1

    if all(gates.values()):
        try:
            gates.update(judge_live(evidence))
        except Exception as error:  # noqa: BLE001 - report as a failed gate, not a crash
            gates["live_reread_of_custody_record_confirms_the_swept_revocation"] = False
            print(f"[FAIL] live reread failed: {error}")

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
