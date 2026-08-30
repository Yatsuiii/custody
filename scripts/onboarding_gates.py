"""Independently judge the live Onboarding Agent artifact.

The first layer checks the producer's JSON and the structurally limited
VouchDraft schema. The second layer issues a fresh Gemini call through
Vertex AI under the project's credentials; it does not reread the producer's
response.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.onboarding import VouchDraft  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-onboarding.json"

DISALLOWED_DRAFT_KEYS = {"trust", "origin", "label", "decision"}


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    marker = evidence["marker"]
    draft = evidence["draft"]
    request = evidence["request_text"]
    draft_fields = set(VouchDraft.__dataclass_fields__)

    return {
        "fresh_live_evidence": fresh,
        "marker_present_in_the_request": marker in request,
        "marker_present_in_the_drafted_evidence": marker in draft.get("evidence", ""),
        "draft_carries_no_trust_or_origin_key": not (
            set(draft) & DISALLOWED_DRAFT_KEYS
        ),
        "draft_schema_matches_the_structurally_limited_dataclass": (
            set(draft) == draft_fields
        ),
        "draft_department_and_tool_match_the_request": (
            draft.get("department") == evidence["department"]
            and draft.get("tool") == evidence["tool"]
        ),
        "gemini_call_used_vertex_ai": evidence.get("gemini", {}).get("vertex") is True,
        "requested_model_is_gemini_3_5_flash": (
            evidence.get("gemini", {}).get("requested_model") == "gemini-3.5-flash"
        ),
        "claim_boundary_names_human_submission_as_a_non_goal": (
            "/vouch" in evidence.get("claim_boundary", "")
            and "does not prove" in evidence.get("claim_boundary", "")
        ),
    }


def judge_live(evidence: dict) -> dict[str, bool]:
    """Issue a new Vertex AI call rather than trusting the producer's text."""
    from google import genai
    from google.genai import types

    project = evidence["project"]
    check_marker = f"onboarding-gate-check-{evidence['proof_id'][:12]}"
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
        print("[BLOCKED] no proof-out/live-onboarding.json")
        print("          run make live-onboarding")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live onboarding evidence: {error}")
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
