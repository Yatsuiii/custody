#!/usr/bin/env python3
"""Independent real-Firestore validation of the redesigned Case P lifecycle.

This probe does not execute the P7 treatment, import the P7 scorer, or create a
P7 run identity. It validates only setup separation, exact P-ROOT barrier
placement, killed-writer state, and recovery using the shared harness lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import firestore

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.p7_run as harness  # noqa: E402


VALIDATION_ID = "p7-casep-lifecycle-validation-03"
NAMESPACE_PREFIX = "custody_p7_casep_lifecycle_validation_03"
PROJECT = "project-988bc9fe-092c-4b32-90c"
DATABASE = "(default)"
PROOF_DIR = Path(__file__).resolve().parent.parent / "research" / "production_b7"
RAW_TRACE_PATH = PROOF_DIR / "CASEP_LIFECYCLE_VALIDATION_03_RAW_TRACE.json"
RESULT_PATH = PROOF_DIR / "CASEP_LIFECYCLE_VALIDATION_03_RESULT.json"
CLEANUP_PATH = PROOF_DIR / "CASEP_LIFECYCLE_VALIDATION_03_CLEANUP.json"


def _sha256_json(value: object) -> str:
    normalized = json.loads(json.dumps(value, sort_keys=True, default=str))
    return hashlib.sha256(
        (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def _validation_checks(lifecycle: dict[str, object]) -> dict[str, object]:
    setup = lifecycle["setup"]
    startup = lifecycle["startup"]
    barrier = lifecycle["barrier_report"]
    current = barrier["current_transaction"]
    expected_path = lifecycle["expected_p_root_path"]
    recovery = lifecycle["recovery_telemetry"]
    checks = {
        "setup_completed_before_child": (
            setup["setup_complete_monotonic"]
            < lifecycle["child_start_monotonic"]
        ),
        "issuer_key_present_before_child": all(
            item["present_and_exact"] for item in setup["verification"]["issuer_checks"]
        ),
        "policy_present_before_child": all(
            item["present_and_exact"] for item in setup["verification"]["policy_checks"]
        ),
        "child_performed_no_provisioning": (
            startup["provisioning_transactions"] == 0
        ),
        "barrier_disarmed_during_startup": (
            startup["barrier"]["armed"] is False
            and startup["barrier"]["reached"] is False
        ),
        "barrier_reached": barrier["barrier"]["reached"] is True,
        "parent_observed_barrier": True,
        "exact_path_intercepted": (
            barrier["barrier"]["matched_path"] == expected_path
            and current["exact_matched_path"] == expected_path
        ),
        "commit_not_started_at_kill_gate": current["commit_attempted"] is False,
        "child_sigkill": lifecycle["killed_exitcode"] == -9,
        "no_partial_authoritative_state": (
            lifecycle["partial_authoritative_state_after_kill"] is False
        ),
        "recovery_did_not_provision": (
            lifecycle["recovery_repeated_provisioning"] is False
        ),
        "retry_follows_frozen_admission": lifecycle["retry"]["admitted"] is True,
        "exactly_one_final_envelope": lifecycle["final_record_ids"] == ["P-ROOT"],
        "issuer_key_contention_absent": (
            lifecycle["issuer_key_contention_observed"] is False
        ),
        "recovery_time_recorded": isinstance(lifecycle["recovery_seconds"], float),
        "recovery_within_90_seconds": (
            lifecycle["recovery_completed_within_90_seconds"] == 1
        ),
        "recovery_transaction_attempts_recorded": bool(recovery["attempts"]),
        "no_post_kill_issuer_create": not any(
            "/authority_issuer_keys/" in path
            for attempt in recovery["attempts"]
            for path in attempt["document_creates"]
        ),
    }
    return {"checks": checks, "all_pass": all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--prefix", default=NAMESPACE_PREFIX)
    parser.add_argument(
        "--i-understand-this-spends-real-firestore-quota", action="store_true"
    )
    arguments = parser.parse_args()
    if not arguments.i_understand_this_spends_real_firestore_quota:
        print("Refusing to run without explicit Firestore quota authorization.")
        return 2
    if any(path.exists() for path in (RAW_TRACE_PATH, RESULT_PATH, CLEANUP_PATH)):
        print("Refusing to overwrite existing validation evidence.")
        return 2

    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    raw = firestore.Client(project=arguments.project, database=DATABASE)
    started_at = datetime.now(UTC).isoformat()
    started_monotonic = time.monotonic()
    raw_trace: dict[str, object] = {
        "validation_id": VALIDATION_ID,
        "namespace_prefix": arguments.prefix,
        "project": arguments.project,
        "database": DATABASE,
        "started_at": started_at,
        "production_sha_required": "16d34593dbc765e4ce3c34f03a0625783127f205",
    }
    verdict = "CASEP-LIFECYCLE-HARNESS-FAIL"
    try:
        preflight = harness._collection_counts(raw, arguments.prefix)
        if any(preflight.values()):
            raise RuntimeError(f"validation namespace is not fresh: {preflight}")
        lifecycle = harness._run_case_p_lifecycle(
            raw,
            arguments.project,
            DATABASE,
            arguments.prefix,
            harness._Counters(),
        )
        validation = _validation_checks(lifecycle)
        raw_trace["lifecycle"] = lifecycle
        raw_trace["validation"] = validation
        raw_trace["runtime_seconds"] = time.monotonic() - started_monotonic
        if validation["all_pass"]:
            verdict = "CASEP-LIFECYCLE-SUPPORTED"
    except BaseException as error:  # noqa: BLE001
        raw_trace["failure"] = harness._exception_record(error)
        raw_trace["runtime_seconds"] = time.monotonic() - started_monotonic
    raw_trace["verdict"] = verdict
    raw_trace["completed_at"] = datetime.now(UTC).isoformat()
    RAW_TRACE_PATH.write_text(
        json.dumps(raw_trace, indent=2, sort_keys=True, default=str) + "\n"
    )
    raw_trace_digest = _sha256_json(raw_trace)
    result = {
        "validation_id": VALIDATION_ID,
        "raw_trace_path": str(RAW_TRACE_PATH.relative_to(PROOF_DIR.parent.parent)),
        "raw_trace_digest": raw_trace_digest,
        "verdict": verdict,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result_digest = _sha256_json(result)
    cleanup = harness._cleanup(raw, arguments.prefix)
    cleanup_record = {
        "validation_id": VALIDATION_ID,
        "result_digest": result_digest,
        "cleanup": cleanup,
    }
    CLEANUP_PATH.write_text(json.dumps(cleanup_record, indent=2, sort_keys=True) + "\n")
    raw.close()
    print(
        json.dumps(
            {
                "validation_id": VALIDATION_ID,
                "verdict": verdict,
                "raw_trace_digest": raw_trace_digest,
                "result_digest": result_digest,
                "cleanup_complete": cleanup["complete"],
            },
            indent=2,
        )
    )
    return 0 if verdict == "CASEP-LIFECYCLE-SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
