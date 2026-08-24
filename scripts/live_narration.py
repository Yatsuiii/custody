"""Prove a real second modality on top of the Custody Reviewer: the same
live, Gemini-drafted verdict `scripts/live_review.py` proves is narrated as
speech through a real Google Cloud Text-to-Speech call, not a canned or
pre-recorded clip.

Closes `HANDOFF.md` section 4 (the Best Multimodal UX award, $5,000, 2
winners): the GUI built earlier this session is single-modality (HTML/SVG,
text and graph visuals only). This adds a genuine audio output modality
tied to real, already-live content — the Reviewer's own verdict text —
rather than a forced, unrelated use of an image/video model, which the
project's own contract explicitly warns against.

This is an independent live run, not a read of `proof-out/live-review.json`
— its own quarantine, its own marker, its own Gemini call, so it stands on
its own evidence the same way every other live proof in this project does.

    make live-narration
"""

from __future__ import annotations

import hashlib
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
from google.cloud import texttospeech  # noqa: E402
from google.genai import types  # noqa: E402

from custody.control_plane import ControlPlane  # noqa: E402
from custody.review import draft_verdict  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-narration.json"
AUDIO_OUT = REPO_ROOT / "proof-out" / "live-narration.mp3"
FAILURE = REPO_ROOT / "proof-out" / "live-narration.failure.json"

MODEL = "gemini-3.5-flash"
VOICE = "en-US-Chirp3-HD-Achernar"
LANGUAGE_CODE = "en-US"

CLAIM_BOUNDARY = (
    "Proves a genuine second modality on top of the Custody Reviewer: the "
    "same live, Gemini-drafted verdict scripts/live_review.py already "
    "proves is narrated as real speech through Google Cloud Text-to-Speech, "
    "checked by a per-run random marker embedded in the quarantined content "
    "that only a call which actually read it can reproduce, carried through "
    "into the synthesized audio's own transcript boundary via the verdict "
    "text itself. This is an independent live run with its own quarantine, "
    "marker, and Gemini call, not a read of live-review.json. Structurally, "
    "not just by convention: custody/review.py's Verdict carries no trust "
    "or origin field, and draft_verdict imports neither custody.catalog nor "
    "custody.graph, so this call has no code path into a stored fact; "
    "narration only ever reads Verdict.summary, a plain string. Does not "
    "add a console or human-facing review queue; that remains future work. "
    "No image or video generation is involved."
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


def _narrate(text: str) -> dict[str, object]:
    client = texttospeech.TextToSpeechClient()
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code=LANGUAGE_CODE, name=VOICE
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        ),
    )
    audio = response.audio_content
    if not audio or audio[:2] not in (b"\xff\xfb", b"\xff\xf3", b"\xff\xfa"):
        if audio[:3] != b"ID3":
            raise RuntimeError(
                "synthesized audio does not carry a recognizable MP3 header"
            )
    AUDIO_OUT.write_bytes(audio)
    return {
        "api": "Cloud Text-to-Speech",
        "voice": VOICE,
        "language_code": LANGUAGE_CODE,
        "audio_encoding": "MP3",
        "character_count": len(text),
        "audio_bytes": len(audio),
        "audio_sha256": hashlib.sha256(audio).hexdigest(),
        "audio_path": str(AUDIO_OUT.relative_to(REPO_ROOT)),
    }


def _prove() -> dict[str, object]:
    proof_id = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT")
    if not project:
        raise SystemExit("CUSTODY_PROJECT is required")

    marker = f"proof-marker-{proof_id[:12]}"
    department = f"narration-probe-{proof_id[:8]}"
    tool = f"narration_probe_tool_{proof_id[:8]}"
    invocation_id = f"narration-probe-{proof_id[:12]}"
    quarantined_text = f"Attempted to exfiltrate customer records via {tool}. {marker}"

    plane = ControlPlane()
    run = plane.ingest(
        {
            "department": department,
            "app_name": "custody-narration-probe",
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

    narration = _narrate(verdict.summary)

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
        "narration": narration,
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    AUDIO_OUT.unlink(missing_ok=True)
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
        print(f"live narration proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live narration evidence written to {OUT}")
    print(f"live narration audio written to {AUDIO_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
