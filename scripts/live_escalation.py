"""Prove the real Escalation Agent: after an Auditor sweep revokes a
record, Gemini reads the demotion context and drafts a notice for a human.

The revocation setup is deterministic and local; the drafting leg is a real
Vertex AI call. A per-run marker is embedded in the demotion context and must
survive into the notice, so a fixed response cannot pass.

    make live-escalation
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

from custody.catalog import Demotion  # noqa: E402
from custody.control_plane import ControlPlane  # noqa: E402
from custody.escalation import draft_notice  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-escalation.json"
FAILURE = REPO_ROOT / "proof-out" / "live-escalation.failure.json"

MODEL = "gemini-3.5-flash"

CLAIM_BOUNDARY = (
    "Proves a real Gemini call through Vertex AI reads one specific "
    "post-sweep demotion context and drafts a notice, checked by a random "
    "marker embedded in that context that survives into the notice. The "
    "deterministic local ControlPlane setup also proves that the Auditor "
    "sweep actually removed the probe record before drafting. "
    "custody/escalation.py receives only structural demotion fields, carries "
    "no trust or origin field, and imports neither custody.catalog nor "
    "custody.graph; it cannot revoke anything. This proof does not claim "
    "the deployed Cloud Run/Firestore Auditor was exercised, does not "
    "submit a new endpoint, and does not replace the existing revocation "
    "path."
)


def _explain(*, project: str, text: str) -> dict[str, object]:
    client = genai.Client(vertexai=True, project=project, location="global")
    prompt = (
        "You are the Custody Escalation Agent. Draft a short incident notice "
        "for a human operator after a deterministic Auditor completed a "
        "revocation. State the supplied department, tool, demotion actor, "
        "and timestamp. Do not make a new trust decision or claim facts not "
        "in the context. Repeat every identifier and marker verbatim. In two "
        "or three sentences, return only the notice prose.\n\n"
        f"Completed-revocation context:\n{text}"
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


def _revoked_probe(proof_id: str, marker: str) -> tuple[Demotion, dict[str, object]]:
    department = f"escalation-probe-{proof_id[:8]}"
    tool = f"escalation_probe_tool_{proof_id[:8]}"
    invocation_id = f"escalation-probe-{proof_id[:12]}"
    record_id = f"{invocation_id}:0:0"
    demoted_at = datetime.now(UTC).isoformat()
    demoted_by = f"escalation-proof-{marker}"

    plane = ControlPlane()
    vouch = plane.vouch(
        {
            "actor_department": department,
            "department": department,
            "tool": tool,
            "vouched_by": "escalation-proof",
            "vouched_at": datetime.now(UTC).isoformat(),
        }
    )
    if not vouch["allowed"]:
        raise RuntimeError(f"probe vouch was refused: {vouch}")

    run = plane.ingest(
        {
            "department": department,
            "app_name": "custody-escalation-probe",
            "session_id": invocation_id,
            "events": [
                {
                    "author": "assistant",
                    "invocation_id": invocation_id,
                    "parts": [{"tool": tool, "response": "probe fact"}],
                }
            ],
        }
    )
    if run["admitted"] != 1:
        raise RuntimeError(f"expected one admitted probe record, got: {run}")

    demotion = Demotion(
        actor_department=department,
        department=department,
        tool=tool,
        demoted_by=demoted_by,
        demoted_at=demoted_at,
    )
    demote = plane.demote(
        {
            "actor_department": demotion.actor_department,
            "department": demotion.department,
            "tool": demotion.tool,
            "demoted_by": demotion.demoted_by,
            "demoted_at": demotion.demoted_at,
        }
    )
    if not demote["allowed"]:
        raise RuntimeError(f"probe demotion was refused: {demote}")

    sweep = plane.auditor({})
    revocation = next(
        (item for item in plane.graph.revocations() if item.id == demotion.id()),
        None,
    )
    if revocation is None or record_id not in revocation.removed:
        raise RuntimeError(
            "Auditor sweep did not revoke the probe record: "
            f"sweep={sweep}, revocations={plane.graph.revocations()}"
        )
    if plane.graph.record(record_id) is not None:
        raise RuntimeError("probe record survived the Auditor revocation")

    return demotion, {
        "record_id": record_id,
        "vouch": vouch,
        "run": run,
        "demote": demote,
        "sweep": sweep,
        "revocation": asdict(revocation),
        "after_sweep_record": None,
    }


def _prove() -> dict[str, object]:
    proof_id = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT")
    if not project:
        raise RuntimeError("CUSTODY_PROJECT is required")

    marker = f"proof-marker-{proof_id[:12]}"
    demotion, setup = _revoked_probe(proof_id, marker)

    gemini_call: dict[str, object] = {}

    def explain(text: str) -> str:
        gemini_call.update(_explain(project=project, text=text))
        return str(gemini_call["summary"])

    drafted_at = datetime.now(UTC).isoformat()
    notice = draft_notice(
        demotion,
        explain=explain,
        drafted_at=drafted_at,
    )
    if marker not in notice.summary:
        raise RuntimeError(
            "notice does not contain the per-run marker, so it cannot be "
            f"shown to have read the actual demotion context: {notice.summary!r}"
        )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "claim_boundary": CLAIM_BOUNDARY,
        "marker": marker,
        "department": demotion.department,
        "tool": demotion.tool,
        "demotion": asdict(demotion),
        "setup": setup,
        "gemini": gemini_call,
        "notice": asdict(notice),
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
        print(f"live escalation proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live escalation evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
