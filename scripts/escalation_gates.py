"""Independently judge the live Escalation Agent artifact.

The first layer checks the producer's JSON, recomputes the demotion id, and
confirms a record was actually removed by the deterministic Auditor sweep.
The second layer issues a fresh Gemini call through Vertex AI; it does not
reread the producer's response.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.catalog import Demotion  # noqa: E402
from custody.escalation import Notice  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-escalation.json"

DISALLOWED_NOTICE_KEYS = {"trust", "origin", "label", "decision"}


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    marker = evidence["marker"]
    demotion = evidence["demotion"]
    setup = evidence["setup"]
    revocation = setup["revocation"]
    notice = evidence["notice"]
    expected_id = Demotion(
        actor_department=demotion["actor_department"],
        department=demotion["department"],
        tool=demotion["tool"],
        demoted_by=demotion["demoted_by"],
        demoted_at=demotion["demoted_at"],
    ).id()
    notice_fields = set(Notice.__dataclass_fields__)

    return {
        "fresh_live_evidence": fresh,
        "probe_vouch_and_ingest_succeeded": (
            setup["vouch"]["allowed"] and setup["run"]["admitted"] == 1
        ),
        "auditor_sweep_removed_a_probe_record": (
            setup["record_id"] in revocation.get("removed", [])
            and setup["after_sweep_record"] is None
        ),
        "recomputed_demotion_id_matches_the_revocation": (
            expected_id == revocation.get("id")
            and expected_id in setup["sweep"].get("swept_revocations", [])
        ),
        "notice_marker_matches_the_demotion_context": (
            marker in demotion["demoted_by"]
            and marker in notice.get("summary", "")
        ),
        "notice_carries_no_trust_or_origin_key": not (
            set(notice) & DISALLOWED_NOTICE_KEYS
        ),
        "notice_schema_matches_the_structurally_limited_dataclass": (
            set(notice) == notice_fields
        ),
        "notice_department_and_tool_match_the_demotion": (
            notice.get("department") == demotion["department"]
            and notice.get("tool") == demotion["tool"]
        ),
        "gemini_call_used_vertex_ai": evidence.get("gemini", {}).get("vertex") is True,
        "requested_model_is_gemini_3_5_flash": (
            evidence.get("gemini", {}).get("requested_model") == "gemini-3.5-flash"
        ),
        "claim_boundary_names_deployed_auditor_as_a_non_goal": (
            "does not claim" in evidence.get("claim_boundary", "")
            and "Cloud Run" in evidence.get("claim_boundary", "")
        ),
    }


def judge_live(evidence: dict) -> dict[str, bool]:
    """Issue a new Vertex AI call rather than trusting the producer's text."""
    from google import genai
    from google.genai import types

    project = evidence["project"]
    check_marker = f"escalation-gate-check-{evidence['proof_id'][:12]}"
    client = genai.Client(vertexai=True, project=project, location="global")
    response = client.models.generate_content(
        model=evidence["gemini"]["requested_model"],
        contents=(
            "Return the following marker verbatim in one short sentence: "
            f"{check_marker}"
        ),
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=64,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return {
        "vertex_ai_independently_reachable_under_project_credentials_now": (
            check_marker in (response.text or "")
        ),
    }


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-escalation.json")
        print("          run make live-escalation")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live escalation evidence: {error}")
        return 1

    if all(gates.values()):
        try:
            gates.update(judge_live(evidence))
        except Exception as error:  # noqa: BLE001 - report a failed live gate
            gates[
                "vertex_ai_independently_reachable_under_project_credentials_now"
            ] = False
            print(f"[FAIL] independent live Gemini call failed: {error}")

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
