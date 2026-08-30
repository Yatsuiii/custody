"""Prove the real Onboarding Agent: Gemini reads a department request and
drafts evidence for a human, without submitting a grant.

A per-run marker is embedded in the request. The producer succeeds only when
the Gemini response contains that marker, which distinguishes reading this
request from returning a fixed canned response.

    make live-onboarding
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

from custody.onboarding import draft_vouch  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-onboarding.json"
FAILURE = REPO_ROOT / "proof-out" / "live-onboarding.failure.json"

MODEL = "gemini-3.5-flash"

CLAIM_BOUNDARY = (
    "Proves a real Gemini call through Vertex AI reads one specific, "
    "per-run department request and drafts its evidence, checked by a "
    "random marker embedded in the request that survives into the draft. "
    "The tool field is read from the requester's named tool; the model only "
    "drafts language and cannot set trust or origin because "
    "custody/onboarding.py returns no such field and imports neither "
    "custody.catalog nor custody.graph. The draft is not submitted to "
    "/vouch, so this does not prove human approval or a catalog write, and "
    "it does not add a new write path."
)


def _explain(*, project: str, text: str) -> dict[str, object]:
    client = genai.Client(vertexai=True, project=project, location="global")
    prompt = (
        "You are the Custody Onboarding Agent. Draft concise evidence for a "
        "human deciding whether to submit a tool vouch request. Describe "
        "the department's stated need and intended use. Do not approve the "
        "tool, decide trust, or claim that a grant exists. Repeat the exact "
        "tool identifier and every marker in the request verbatim. In two "
        "or three sentences, return only the evidence prose.\n\n"
        f"Department request:\n{text}"
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
        raise RuntimeError("CUSTODY_PROJECT is required")

    marker = f"proof-marker-{proof_id[:12]}"
    department = f"onboarding-probe-{proof_id[:8]}"
    tool = f"onboarding_probe_tool_{proof_id[:8]}"
    request_text = (
        f"We need the {tool} tool for the sales pipeline. "
        f"Preserve this request marker verbatim: {marker}."
    )

    gemini_call: dict[str, object] = {}

    def explain(text: str) -> str:
        gemini_call.update(_explain(project=project, text=text))
        return str(gemini_call["summary"])

    drafted_at = datetime.now(UTC).isoformat()
    draft = draft_vouch(
        request_text,
        department=department,
        explain=explain,
        drafted_at=drafted_at,
    )

    if draft.tool != tool:
        raise RuntimeError(
            f"tool was not read from the request as expected: {draft.tool!r}"
        )
    if marker not in draft.evidence:
        raise RuntimeError(
            "draft evidence does not contain the per-run marker, so it cannot "
            f"be shown to have read the actual request: {draft.evidence!r}"
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
        "request_text": request_text,
        "gemini": gemini_call,
        "draft": asdict(draft),
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    try:
        evidence = _prove()
    except Exception as error:  # noqa: BLE001 - turn live failure into evidence
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
        print(f"live onboarding proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live onboarding evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
