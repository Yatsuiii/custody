"""Prove live Agent Observability: a trace carrying the custody digest (O1).

This producer is intentionally not the judge. It runs the same live ADK ->
Custody -> Memory Bank flow G1 already proves, wrapped in one OTel span
exported to Cloud Trace, and records that span's trace/span identifiers next
to the exact digest of the admitted custody record in one structured Cloud
Logging entry. ``scripts/observability_gates.py`` derives the verdict from
that entry.

Claim boundary, stated once here because it shapes the whole design: this
project's Cloud Trace read API (``cloudtrace.googleapis.com/v1``) returned
"_Trace bucket not found" for every trace this producer exported, and the v2
API has no read/list endpoint at all. The span export to Cloud Trace is
attempted and its failure would abort the proof, but its *storage* is not
independently verifiable here. What is independently verifiable, and is the
falsifiable claim, is that the exact trace ID, span ID, and admitted digest
were recorded together in one server-authored Cloud Logging entry, rereadable
the same way every other proof in this repo rereads Cloud Logging.

    make live-observability
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import google.auth  # noqa: E402
from google.cloud import logging as cloud_logging  # noqa: E402
from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402

from google.adk.telemetry.google_cloud import get_gcp_exporters  # noqa: E402

from scripts.live_memory_bank import prove_adk_memory_bank  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-observability.json"
FAILURE = REPO_ROOT / "proof-out" / "live-observability.failure.json"
CONFIG = REPO_ROOT / ".gcloud"

LOG_NAME = "custody-observability"
SPAN_NAME = "custody.g1.admission"
LOG_EVENT = "custody.observability.trace_bound_digest.v1"
LOG_POLL_ATTEMPTS = 18
LOG_POLL_INTERVAL_SECONDS = 5

CLAIM_BOUNDARY = (
    "Proves one live ADK admission produces an OTel span exported to Cloud "
    "Trace, and that the exact trace ID, span ID, and admitted custody "
    "digest are recorded together in one independently rereadable Cloud "
    "Logging entry, so a later quarantine can be traced back to this run. "
    "It does not independently verify Cloud Trace's own span storage: this "
    "project's Cloud Trace v1 read API returns no default trace bucket, and "
    "v2 has no read endpoint. It does not change G1's admitted/withheld "
    "counts or Memory Bank behavior."
)


def _gcloud_logging_read(*arguments: str) -> Any:
    environment = os.environ.copy()
    environment["CLOUDSDK_CONFIG"] = str(CONFIG)
    environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    completed = subprocess.run(
        ["gcloud", "logging", "read", *arguments, "--quiet", "--format=json"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )
    return json.loads(completed.stdout)


def _poll_for_log(*, project: str, trace_id: str, proof_id: str) -> dict[str, Any]:
    query = " AND ".join(
        (
            f'logName="projects/{project}/logs/{LOG_NAME}"',
            f'jsonPayload.event="{LOG_EVENT}"',
            f'jsonPayload.proof_id="{proof_id}"',
            f'trace="projects/{project}/traces/{trace_id}"',
        )
    )
    last: list[dict[str, Any]] = []
    for _ in range(LOG_POLL_ATTEMPTS):
        try:
            last = _gcloud_logging_read(
                query, "--freshness=1h", "--order=asc", "--limit=10"
            )
        except (
            json.JSONDecodeError,
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            time.sleep(LOG_POLL_INTERVAL_SECONDS)
            continue
        if isinstance(last, list) and len(last) == 1:
            return last[0]
        time.sleep(LOG_POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"no unique proof-bound observability log found: {last}")


async def _prove(proof_id: str) -> dict[str, Any]:
    project = os.environ.get("CUSTODY_PROJECT")
    engine_id = os.environ.get("CUSTODY_AGENT_ENGINE_ID")
    if not project or not engine_id:
        raise SystemExit("CUSTODY_PROJECT and CUSTODY_AGENT_ENGINE_ID are required")
    location = os.environ.get("CUSTODY_LOCATION", "us-central1")

    credentials, _ = google.auth.default()
    hooks = get_gcp_exporters(
        enable_cloud_tracing=True, google_auth=(credentials, project)
    )
    if not hooks.span_processors:
        raise RuntimeError("GCP Cloud Trace exporter did not initialize")
    resource = Resource.create(
        {"service.name": "custody-observability", "gcp.project_id": project}
    )
    provider = TracerProvider(resource=resource)
    for processor in hooks.span_processors:
        provider.add_span_processor(processor)
    tracer = provider.get_tracer("custody.observability")

    started_at = datetime.now(UTC).isoformat()
    with tracer.start_as_current_span(SPAN_NAME) as span:
        g1 = await prove_adk_memory_bank(
            project=project,
            location=location,
            agent_engine_id=engine_id,
            proof_id=proof_id,
        )
        digests = g1["admitted_digests"]
        if not digests:
            raise RuntimeError("the ADK run admitted no custody records to trace")
        span.set_attribute("custody.proof_id", proof_id)
        span.set_attribute("custody.digest", digests[0])
        span.set_attribute("custody.admitted_digest_count", len(digests))
        context = span.get_span_context()
        trace_id = format(context.trace_id, "032x")
        span_id = format(context.span_id, "016x")

    provider.force_flush(timeout_millis=10_000)
    provider.shutdown()

    log_client = cloud_logging.Client(project=project)
    log_client.logger(LOG_NAME).log_struct(
        {
            "event": LOG_EVENT,
            "proof_id": proof_id,
            "trace_id": trace_id,
            "span_id": span_id,
            "span_name": SPAN_NAME,
            "custody_digest": digests[0],
            "admitted_digest_count": len(digests),
        },
        trace=f"projects/{project}/traces/{trace_id}",
        span_id=span_id,
        severity="INFO",
    )

    log_entry = _poll_for_log(project=project, trace_id=trace_id, proof_id=proof_id)
    captured_at = datetime.now(UTC).isoformat()
    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "started_at": started_at,
        "captured_at": captured_at,
        "project": project,
        "region": location,
        "claim_boundary": CLAIM_BOUNDARY,
        "trace_id": trace_id,
        "span_id": span_id,
        "span_name": SPAN_NAME,
        "custody_digest": digests[0],
        "admitted_digest_count": len(digests),
        "g1_admission": g1,
        "log_entry": log_entry,
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    proof_id = uuid.uuid4().hex
    try:
        evidence = asyncio.run(_prove(proof_id))
    except Exception as error:
        failure = {
            "schema_version": 1,
            "proof_id": proof_id,
            "captured_at": datetime.now(UTC).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        FAILURE.write_text(json.dumps(failure, indent=2) + "\n")
        raise
    OUT.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    print(f"Observability evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
