"""Independently judge the live Agent Observability artifact (O1).

The producer is intentionally untrusted. This module first derives every
offline verdict from the raw evidence the artifact carries. If, and only if,
every offline gate passes, it independently rereads the one server-authored
Cloud Logging entry from Google Cloud using code-owned resource identifiers,
never ones the artifact supplies.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "proof-out" / "live-observability.json"
CONFIG = REPO_ROOT / ".gcloud"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Independent of the evidence producer: the trust anchor that prevents a
# coherent artifact from redirecting live attestation to another resource.
PROJECT = "project-988bc9fe-092c-4b32-90c"
REGION = "us-central1"
LOG_NAME = "custody-observability"
SPAN_NAME = "custody.g1.admission"
LOG_EVENT = "custody.observability.trace_bound_digest.v1"
_LOG_LOGNAME = f"projects/{PROJECT}/logs/{LOG_NAME}"

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

_HEX_ID = re.compile(r"[0-9a-f]{32}")
_TRACE_ID = re.compile(r"[0-9a-f]{32}")
_SPAN_ID = re.compile(r"[0-9a-f]{16}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_PROOF_DURATION = timedelta(minutes=10)

GATE_NAMES = (
    "fresh_bounded_live_evidence",
    "trace_and_span_ids_are_well_formed",
    "g1_admission_reached_memory_bank",
    "digest_is_one_of_the_admitted_records",
    "log_entry_binds_trace_span_and_digest",
)
LIVE_GATE_NAMES = (
    "live_attestation_available",
    "live_log_entry_matches",
)


def _aware_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(UTC)


def _log_entry_is_bound(
    entry: dict[str, Any],
    *,
    proof_id: str,
    trace_id: str,
    span_id: str,
    digest: str,
    started: datetime,
    captured: datetime,
) -> bool:
    payload = entry["jsonPayload"]
    timestamp = _aware_time(entry["timestamp"])
    received = _aware_time(entry["receiveTimestamp"])
    return (
        bool(entry.get("insertId"))
        and entry.get("logName") == _LOG_LOGNAME
        and entry.get("severity") == "INFO"
        and entry.get("trace") == f"projects/{PROJECT}/traces/{trace_id}"
        and entry.get("spanId") == span_id
        and payload.get("event") == LOG_EVENT
        and payload.get("proof_id") == proof_id
        and payload.get("trace_id") == trace_id
        and payload.get("span_id") == span_id
        and payload.get("span_name") == SPAN_NAME
        and payload.get("custody_digest") == digest
        and started <= timestamp <= received <= captured
    )


def _judge(evidence: dict[str, Any], *, now: datetime) -> dict[str, bool]:
    if evidence["schema_version"] != 1:
        raise ValueError("unsupported Observability evidence schema")
    proof_id = evidence["proof_id"]
    started = _aware_time(evidence["started_at"])
    captured = _aware_time(evidence["captured_at"])
    trace_id = evidence["trace_id"]
    span_id = evidence["span_id"]
    digest = evidence["custody_digest"]
    g1 = evidence["g1_admission"]
    digests = g1["admitted_digests"]

    fresh = (
        _HEX_ID.fullmatch(proof_id) is not None
        and evidence["project"] == PROJECT
        and evidence["region"] == REGION
        and evidence["claim_boundary"] == CLAIM_BOUNDARY
        and started <= captured
        and captured - started <= _MAX_PROOF_DURATION
        and captured <= now + timedelta(minutes=5)
        and now - captured <= timedelta(hours=24)
    )

    ids_well_formed = (
        _TRACE_ID.fullmatch(trace_id) is not None
        and trace_id != "0" * 32
        and _SPAN_ID.fullmatch(span_id) is not None
        and span_id != "0" * 16
        and _SHA256.fullmatch(digest) is not None
    )

    # `memory_write_count` was pinned to exactly 1 back when G1 wrote one
    # session-level memory via `ingest_events`. G1 migrated to `write_record`
    # (`HANDOFF.md`, "G1 migration"), which writes one raw memory per
    # admitted record, so the count is no longer a fixed literal. The
    # self-consistency invariant `scripts/gates.py`'s own `judge_g1` already
    # uses post-migration is reused here instead of inventing a second one:
    # every written id is accounted for, and there is at least one.
    written_ids = g1.get("written_memory_ids", [])
    g1_reached_memory_bank = (
        g1.get("framework") == "google-adk"
        and g1.get("agent_run_completed") is True
        and proof_id in g1.get("agent_text", "")
        and g1.get("memory_write_count") == len(written_ids)
        and bool(written_ids)
        and g1.get("custody_split", {}).get("withheld") == 0
        and g1.get("custody_split", {}).get("refused") == 0
        and g1.get("retrieved_memory_count", 0) >= 1
        and isinstance(digests, list)
        and len(digests) == evidence.get("admitted_digest_count")
        and all(_SHA256.fullmatch(str(item)) is not None for item in digests)
    )

    digest_is_admitted = digest in digests if isinstance(digests, list) else False

    log_bound = ids_well_formed and _log_entry_is_bound(
        evidence["log_entry"],
        proof_id=proof_id,
        trace_id=trace_id,
        span_id=span_id,
        digest=digest,
        started=started,
        captured=captured,
    )

    return {
        "fresh_bounded_live_evidence": fresh,
        "trace_and_span_ids_are_well_formed": ids_well_formed,
        "g1_admission_reached_memory_bank": g1_reached_memory_bank,
        "digest_is_one_of_the_admitted_records": digest_is_admitted,
        "log_entry_binds_trace_span_and_digest": log_bound,
    }


def judge(evidence: dict[str, Any], *, now: datetime | None = None) -> dict[str, bool]:
    """Return clean failure evidence for every malformed or incomplete artifact."""
    try:
        if not isinstance(evidence, dict):
            raise TypeError("Observability evidence must be an object")
        return _judge(evidence, now=now or datetime.now(UTC))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {"well_formed_evidence": False}


@dataclass(frozen=True)
class GcloudReadClient:
    """Use Custody's isolated gcloud configuration for read-only attestation."""

    def json(self, *arguments: str) -> Any:
        environment = os.environ.copy()
        environment["CLOUDSDK_CONFIG"] = str(CONFIG)
        environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
        completed = subprocess.run(
            ["gcloud", *arguments, f"--project={PROJECT}", "--quiet", "--format=json"],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
            timeout=60,
        )
        return json.loads(completed.stdout)


def attest_live(
    evidence: dict[str, Any], cloud: GcloudReadClient | None = None
) -> dict[str, bool]:
    """Independently reread the one log entry from Google Cloud by insert ID."""
    reader = cloud or GcloudReadClient()
    try:
        insert_id = evidence["log_entry"]["insertId"]
        query = " AND ".join((f'logName="{_LOG_LOGNAME}"', f'insertId="{insert_id}"'))
        entries = reader.json("logging", "read", query, "--freshness=24h", "--limit=2")
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        KeyError,
    ):
        return {"live_attestation_available": False}

    if not isinstance(entries, list) or len(entries) != 1:
        return {
            "live_attestation_available": True,
            "live_log_entry_matches": False,
        }
    return {
        "live_attestation_available": True,
        "live_log_entry_matches": entries[0] == evidence["log_entry"],
    }


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-observability.json")
        print("          run make live-observability")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live Observability evidence: {error}")
        return 1
    gates = judge(evidence)
    if gates and all(gates.values()):
        gates.update(attest_live(evidence))
    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
