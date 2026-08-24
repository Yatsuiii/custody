"""Produce the single live evidence artifact for acceptance gate G1."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from scripts.live_memory_bank import MODEL, prove_adk_memory_bank  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "g1.json"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def _json_request(url: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def _cloud_run_proof(
    *, project: str, region: str, service: str, proof_id: str
) -> dict[str, object]:
    command = [
        "gcloud",
        "run",
        "services",
        "describe",
        service,
        f"--project={project}",
        f"--region={region}",
        "--format=json",
    ]
    described = json.loads(
        subprocess.run(command, check=True, capture_output=True, text=True).stdout
    )
    status = described["status"]
    url = status["url"]
    ready = next(
        (
            condition.get("status") == "True"
            for condition in status.get("conditions", [])
            if condition.get("type") == "Ready"
        ),
        False,
    )
    traffic_percent = max(
        (entry.get("percent", 0) for entry in status.get("traffic", [])), default=0
    )
    department = f"g1-{proof_id}"
    trigger = _json_request(
        f"{url}/sessions",
        {
            "department": department,
            "app_name": "custody-g1",
            "session_id": department,
            "events": [
                {
                    "author": "user",
                    "invocation_id": department,
                    "parts": [{"text": f"Cloud Run G1 trigger {proof_id}"}],
                }
            ],
        },
    )
    return {
        "service": described["metadata"]["name"],
        "region": region,
        "url": url,
        "revision": status["latestReadyRevisionName"],
        "ready": ready,
        "traffic_percent": traffic_percent,
        "health": _json_request(f"{url}/health"),
        "trigger": trigger,
    }


def _gemini_proof(*, project: str, proof_id: str) -> dict[str, object]:
    expected = f"CUSTODY_G1_OK:{proof_id}"
    client = genai.Client(vertexai=True, project=project, location="global")
    response = client.models.generate_content(
        model=MODEL,
        contents=f"Return exactly {expected} and nothing else.",
        config=types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=128,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return {
        "api": "Vertex AI via google-genai",
        "vertex": True,
        "requested_model": MODEL,
        "model_version": response.model_version,
        "response": (response.text or "").strip(),
        "expected_response": expected,
        "traffic_type": str(response.usage_metadata.traffic_type),
        "total_tokens": response.usage_metadata.total_token_count,
    }


async def _prove() -> dict[str, object]:
    project = _required("CUSTODY_PROJECT")
    engine_id = _required("CUSTODY_AGENT_ENGINE_ID")
    location = os.environ.get("CUSTODY_LOCATION", "us-central1")
    region = os.environ.get("CUSTODY_RUN_REGION", "us-central1")
    service = os.environ.get("CUSTODY_RUN_SERVICE", "custody-control-plane")
    proof_id = uuid.uuid4().hex

    print("[1/3] Verifying Cloud Run health and trigger...", flush=True)
    cloud_run = await asyncio.to_thread(
        _cloud_run_proof,
        project=project,
        region=region,
        service=service,
        proof_id=proof_id,
    )
    print("[2/3] Calling Gemini 3.5 through Vertex AI...", flush=True)
    gemini = await asyncio.to_thread(_gemini_proof, project=project, proof_id=proof_id)
    print("[3/3] Running ADK -> Custody -> Memory Bank...", flush=True)
    adk_memory_bank = await prove_adk_memory_bank(
        project=project,
        location=location,
        agent_engine_id=engine_id,
        proof_id=proof_id,
    )
    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "cloud_run": cloud_run,
        "gemini": gemini,
        "adk_memory_bank": adk_memory_bank,
    }


def main() -> int:
    # A failed rerun must not leave an older artifact looking current.
    OUT.unlink(missing_ok=True)
    evidence = asyncio.run(_prove())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    print(f"G1 evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"live G1 proof failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
