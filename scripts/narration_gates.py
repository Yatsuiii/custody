"""Independently judge the live Reviewer-narration artifact.

Two layers, same discipline as `review_gates.py`: offline structural checks
against the producer's own JSON and its sibling audio file (including a
recomputed sha256 digest, which rejects a stale or forged claim), then a
live, independently issued Cloud Text-to-Speech call under the project's own
credentials, not a reread of the producer's audio — there is no durable
Cloud resource to reread here, the live claim is the call itself, so the
independent check re-makes it rather than re-reading it.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json  # noqa: E402

from custody.review import Verdict  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-narration.json"
AUDIO_OUT = REPO_ROOT / "proof-out" / "live-narration.mp3"

#: Fields a fact-deciding output would need. None may appear on the
#: producer's verdict, structurally, not just by review.
DISALLOWED_VERDICT_KEYS = {"trust", "origin", "label", "verdict_trust", "decision"}

MP3_HEADERS = (b"\xff\xfb", b"\xff\xf3", b"\xff\xfa", b"ID3")


def judge_offline(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    fresh = captured.tzinfo is not None and current - captured <= timedelta(hours=24)

    marker = evidence["marker"]
    verdict = evidence["verdict"]
    run = evidence["quarantine_run"]
    narration = evidence.get("narration", {})

    verdict_fields = {f for f in Verdict.__dataclass_fields__}

    audio_bytes = AUDIO_OUT.read_bytes() if AUDIO_OUT.exists() else b""
    recomputed_sha256 = hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else ""

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
        "audio_file_exists_on_disk": AUDIO_OUT.exists(),
        "audio_sha256_matches_the_recorded_digest": (
            bool(audio_bytes) and recomputed_sha256 == narration.get("audio_sha256")
        ),
        "audio_carries_a_recognizable_mp3_header": (
            bool(audio_bytes)
            and audio_bytes[:3] in MP3_HEADERS
            or audio_bytes[:2] in MP3_HEADERS
        ),
        "audio_byte_count_is_non_trivial": narration.get("audio_bytes", 0) > 1000,
        "narration_api_was_cloud_text_to_speech": (
            narration.get("api") == "Cloud Text-to-Speech"
        ),
    }


def judge_live(evidence: dict) -> dict[str, bool]:
    """Independently call Cloud Text-to-Speech right now, under the
    project's own credentials, rather than trusting the producer's audio —
    there is no durable resource here to reread, so the independent check
    re-makes the live call instead.
    """
    from google.cloud import texttospeech

    check_text = f"narration gate check {evidence['proof_id'][:12]}"
    client = texttospeech.TextToSpeechClient()
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=check_text),
        voice=texttospeech.VoiceSelectionParams(
            language_code=evidence["narration"]["language_code"],
            name=evidence["narration"]["voice"],
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        ),
    )
    audio = response.audio_content
    return {
        "cloud_text_to_speech_independently_reachable_under_project_credentials_now": (
            bool(audio)
            and len(audio) > 1000
            and (audio[:2] in MP3_HEADERS or audio[:3] in MP3_HEADERS)
        ),
    }


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-narration.json")
        print("          run make live-narration")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge_offline(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live narration evidence: {error}")
        return 1

    if all(gates.values()):
        try:
            gates.update(judge_live(evidence))
        except Exception as error:  # noqa: BLE001 - report as a failed gate, not a crash
            gates[
                "cloud_text_to_speech_independently_reachable_under_project_credentials_now"
            ] = False
            print(f"[FAIL] independent live Cloud Text-to-Speech call failed: {error}")

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
