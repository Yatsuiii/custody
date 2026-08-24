"""Prove the real Custody Reviewer: Gemini reads one live-quarantined item
and drafts a verdict, not an echo of a fixed string.

Closes the fleet-review finding that the Gemini row was marked LIVE while
the only live call in the repo was a connectivity echo
(`scripts/live_g1.py`'s `_gemini_proof`): no code path ever showed Gemini a
quarantined item. Quarantining itself is produced in-process by the same
deterministic `ControlPlane.ingest` logic G2 already proves offline (an
ungranted tool's response is withheld, no model involved in that step); the
new live claim is the Gemini leg alone, so this needs no Cloud Run redeploy
and no new control-plane endpoint.

A per-run random marker is embedded in the synthetic quarantined content.
Only a call that actually reads that specific text can reproduce the marker
in its response, which is what separates this from an echo of a fixed
string.

    make live-review
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from custody.control_plane import ControlPlane  # noqa: E402
from custody.review import draft_verdict  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-review.json"
FAILURE = REPO_ROOT / "proof-out" / "live-review.failure.json"

MODEL = "gemini-3.5-flash"

CLAIM_BOUNDARY = (
    "Proves a real Gemini call, live through Vertex AI, reads one specific "
    "quarantined item's text and drafts a verdict grounded in it, checked "
    "by a per-run random marker embedded in the quarantined content that "
    "only a call which actually read it can reproduce. Quarantining itself "
    "is produced by the same deterministic ControlPlane.ingest logic G2 "
    "already proves offline, not new live infrastructure — this proof adds "
    "no Cloud Run redeploy and no new control-plane endpoint. Structurally, "
    "not just by convention: custody/review.py's Verdict carries no "
    "trust or origin field, and draft_verdict imports neither "
    "custody.catalog nor custody.graph, so this Gemini call has no code "
    "path into a stored fact. Does not add a console or a human-facing "
    "review queue; that remains future work."
)


def _explain(*, project: str, text: str) -> dict[str, object]:
    client = genai.Client(vertexai=True, project=project, location="global")
    prompt = (
        "You are drafting a short verdict for a human security reviewer. "
        "The following text was withheld from an agent's long-term memory "
        "because it came from a tool this department has not trusted. "
        "In two or three sentences, explain what it attempted. Do not "
        "decide whether it is malicious; only describe it.\n\n"
        f"Withheld content:\n{text}"
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=256,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return {
        "api": "Vertex AI via google-genai",
        "vertex": True,
        "requested_model": MODEL,
        "model_version": response.model_version,
        "summary": (response.text or "").strip(),
        "traffic_type": str(response.usage_metadata.traffic_type),
        "total_tokens": response.usage_metadata.total_token_count,
    }


def _prove() -> dict[str, object]:
    proof_id = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT")
    if not project:
        raise SystemExit("CUSTODY_PROJECT is required")

    marker = f"proof-marker-{proof_id[:12]}"
    department = f"review-probe-{proof_id[:8]}"
    tool = f"review_probe_tool_{proof_id[:8]}"
    invocation_id = f"review-probe-{proof_id[:12]}"
    quarantined_text = f"Attempted to exfiltrate customer records via {tool}. {marker}"

    plane = ControlPlane()
    run = plane.ingest(
        {
            "department": department,
            "app_name": "custody-review-probe",
            "session_id": invocation_id,
            "events": [
                {
                    "author": "assistant",
                    "invocation_id": invocation_id,
                    "parts": [{"tool": tool, "response": quarantined_text}],
                }
            ],
        }
    )
    if run["quarantined"] != 1:
        raise RuntimeError(f"expected one quarantined record, got: {run}")

    item = plane.quarantine.items[-1]
    if item.text != quarantined_text or item.user_id != department:
        raise RuntimeError(f"quarantined item does not match what was sent: {item}")

    gemini_call: dict[str, object] = {}

    def explain(text: str) -> str:
        gemini_call.update(_explain(project=project, text=text))
        return str(gemini_call["summary"])

    drafted_at = datetime.now(UTC).isoformat()
    verdict = draft_verdict(item, explain=explain, drafted_at=drafted_at)

    if marker not in verdict.summary:
        raise RuntimeError(
            "verdict does not contain the per-run marker, so it cannot be "
            f"shown to have read the actual quarantined content: {verdict.summary!r}"
        )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "claim_boundary": CLAIM_BOUNDARY,
        "department": department,
        "tool": tool,
        "marker": marker,
        "quarantined_text": quarantined_text,
        "quarantine_run": run,
        "gemini": gemini_call,
        "verdict": asdict(verdict),
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    try:
        evidence = _prove()
    except Exception as error:
        FAILURE.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now(UTC).isoformat(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"live review proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live review evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
