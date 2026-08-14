"""Independently judge the live Custody Reviewer artifact.

Two layers, same discipline as `auditor_gates.py`: offline structural
checks against the producer's own JSON (including the schema check that
proves the Reviewer cannot decide a fact), then a live, independently
issued Gemini call under the project's own credentials, not a reread of the
producer's response — there is no durable Cloud resource to reread here,
the live claim is the call itself, so the independent check re-makes it
rather than re-reading it.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json  # noqa: E402

from custody.review import Verdict  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-review.json"

#: Fields a fact-deciding output would need. None may appear on the
#: producer's verdict, structurally, not just by review.
DISALLOWED_VERDICT_KEYS = {"trust", "origin", "label", "verdict_trust", "decision"}


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    marker = evidence["marker"]
    verdict = evidence["verdict"]
    run = evidence["quarantine_run"]

    verdict_fields = {f for f in Verdict.__dataclass_fields__}

    return {
        "fresh_live_evidence": fresh,
        "exactly_one_record_was_quarantined": run.get("quarantined") == 1,
        "marker_present_in_the_quarantined_content": (
            marker in evidence["quarantined_text"]
        ),
        "marker_present_in_the_drafted_verdict": marker in verdict.get("summary", ""),
        "verdict_carries_no_trust_or_origin_key": (
            not (set(verdict) & DISALLOWED_VERDICT_KEYS)
        ),
        "verdict_schema_matches_the_structurally_limited_dataclass": (
            set(verdict) == verdict_fields
        ),
        "verdict_department_and_tool_match_the_quarantined_item": (
            verdict.get("department") == evidence["department"]
            and verdict.get("source_tool") == evidence["tool"]
        ),
        "gemini_call_used_vertex_ai": evidence.get("gemini", {}).get("vertex") is True,
    }


def judge_live(evidence: dict) -> dict[str, bool]:
    """Independently call Vertex AI right now, under the project's own
    credentials, rather than trusting the producer's response — there is
    no durable resource here to reread, so the independent check re-makes
    the live call instead.
    """
    from google import genai
    from google.genai import types

    project = evidence["project"]
    client = genai.Client(vertexai=True, project=project, location="global")
    check_marker = f"review-gate-check-{evidence['proof_id'][:12]}"
    response = client.models.generate_content(
        model=evidence["gemini"]["requested_model"],
        contents=f"Return exactly {check_marker} and nothing else.",
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
        print("[BLOCKED] no proof-out/live-review.json")
        print("          run make live-review")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live review evidence: {error}")
        return 1

    if all(gates.values()):
        try:
            gates.update(judge_live(evidence))
        except Exception as error:  # noqa: BLE001 - report as a failed gate, not a crash
            gates["vertex_ai_independently_reachable_under_project_credentials_now"] = False
            print(f"[FAIL] independent live Gemini call failed: {error}")

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
