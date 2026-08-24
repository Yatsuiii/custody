#!/usr/bin/env python3
"""P7_TRANSACTION_BARRIER_CONTRACT_PROBE.

This is NOT P7. It is not a security experiment, not a B7 efficacy test, and
it does not import or run the P7 scorer or any frozen case. It proves only
that the transaction-barrier primitive used by frozen P7 cases O and P
(scripts/p7_run.py::_Barrier / _P7Client, commit
085c4d5a9a89d0ae932f5a4814af5620f0223306) behaves as that harness assumes
against the actually installed google-cloud-firestore SDK and the actual
Firestore service.

It imports _Barrier, _P7Client, and _Counters directly from scripts.p7_run
so this probe tests the identical code, not a reimplementation. It uses a
separate scratch namespace and writes no P7 identity, run_id, or output
file recognized by scripts/p7_run.py.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import multiprocessing
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import firestore

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.p7_run as p7  # noqa: E402  (reuse frozen barrier code, unmodified)

PROBE_ID = "p7-barrier-contract-20260824-01"
NAMESPACE_PREFIX = "custody_p7_barrier_contract_20260824_01"
PROBE_COLLECTION = "probe_docs"
DEFAULT_PROJECT = p7.DEFAULT_PROJECT
DEFAULT_DATABASE = p7.DEFAULT_DATABASE

PROOF_DIR = ROOT / "research" / "production_b7"
RESULT_PATH = PROOF_DIR / "P7_BARRIER_CONTRACT_PROBE_RESULT.json"

HARNESS_SHA = "085c4d5a9a89d0ae932f5a4814af5620f0223306"


def _barrier_code_digests() -> dict[str, str]:
    digests = {}
    for name in ("_Barrier", "_P7Client", "_Counters"):
        source = inspect.getsource(getattr(p7, name))
        digests[name] = hashlib.sha256(source.encode()).hexdigest()
    digests["scripts/p7_run.py_whole_file"] = hashlib.sha256(
        (ROOT / "scripts" / "p7_run.py").read_bytes()
    ).hexdigest()
    return digests


def _exception_record(error: BaseException) -> dict[str, object]:
    return {
        "type": type(error).__name__,
        "module": type(error).__module__,
        "message": str(error),
        "traceback": traceback.format_exc(),
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _collection_ref(raw: firestore.Client, name: str):
    return raw.collection(f"{NAMESPACE_PREFIX}__{name}")


def _preflight(raw: firestore.Client) -> dict[str, int]:
    return {PROBE_COLLECTION: sum(1 for _ in _collection_ref(raw, PROBE_COLLECTION).stream())}


def _cleanup(raw: firestore.Client) -> dict[str, object]:
    ref = _collection_ref(raw, PROBE_COLLECTION)
    snapshots = tuple(ref.stream())
    for snapshot in snapshots:
        snapshot.reference.delete()
    remaining = sum(1 for _ in ref.stream())
    return {"deleted": len(snapshots), "remaining": remaining, "complete": remaining == 0}


# ---------------------------------------------------------------------------
# Phase 2: O-BARRIER (action-read / external-commit ordering)
# ---------------------------------------------------------------------------


def _probe_o(raw: firestore.Client) -> dict[str, object]:
    events: list[dict[str, object]] = []

    def log(name: str, **fields: object) -> None:
        events.append({"name": name, "at": _now(), "monotonic": time.monotonic(), **fields})

    counters = p7._Counters()
    barrier = p7._Barrier(mode="get", match_record_id="O-TARGET")
    client = p7._P7Client(raw, NAMESPACE_PREFIX, counters, barrier=barrier)

    doc_ref = raw.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}").document("O-TARGET")
    doc_ref.create({"value": "before", "written_at": _now()})
    log("seed_document_created", value="before")

    invocation_count = {"n": 0}
    observed_values: list[object] = []
    errors: list[str] = []

    transaction = client.transaction()  # this is the intercepted, real Transaction

    @firestore.transactional
    def txn_body(transaction) -> object:
        invocation_count["n"] += 1
        log("txn_invocation_started", attempt=invocation_count["n"])
        snapshot = transaction.get(doc_ref)  # routed through _P7Client's barrier hook
        value = snapshot.to_dict().get("value") if snapshot.exists else None
        observed_values.append(value)
        log("txn_read_completed", attempt=invocation_count["n"], observed_value=value)
        transaction.set(doc_ref, {"value": f"txn_saw_{value}", "written_at": _now()})
        log("txn_write_staged", attempt=invocation_count["n"])
        return value

    result_holder: dict[str, object] = {}

    def run_txn() -> None:
        try:
            result_holder["value"] = txn_body(transaction)
        except BaseException as error:  # noqa: BLE001
            errors.append(repr(error))
            result_holder["exception"] = _exception_record(error)

    log("main_thread_launching_transaction")
    thread = threading.Thread(target=run_txn)
    thread.start()

    reached = barrier.reached.wait(timeout=20)
    log("barrier_reached_observed_by_parent", reached=reached)
    if not reached:
        thread.join(timeout=5)
        return {
            "events": events,
            "verdict": "FAIL",
            "reason": "O barrier was never reached; transaction.get was not intercepted "
            "at the expected call site.",
            "invocation_count": invocation_count["n"],
        }

    # Independent second client commits a change to the SAME document while
    # the first transaction is paused mid-read.
    external = firestore.Client(project=DEFAULT_PROJECT, database=DEFAULT_DATABASE)
    external_doc_ref = external.collection(
        f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}"
    ).document("O-TARGET")
    external_doc_ref.set({"value": "external_write", "written_at": _now()})
    log("independent_client_committed_external_write", value="external_write")

    barrier.release.set()
    log("main_thread_released_barrier")
    thread.join(timeout=20)
    log("transaction_thread_finished", still_alive=thread.is_alive())

    final_snapshot = raw.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}").document(
        "O-TARGET"
    ).get()
    final_value = final_snapshot.to_dict().get("value") if final_snapshot.exists else None
    log("final_state_read", value=final_value)

    barrier_reached_before_first_original_get = reached
    saw_external_write = bool(observed_values) and observed_values[0] == "external_write"
    no_deadlock = not thread.is_alive()

    verdict = "FAIL"
    reason = ""
    if not barrier_reached_before_first_original_get:
        reason = "barrier not reached"
    elif not no_deadlock:
        reason = "transaction thread did not finish (deadlock)"
    elif errors:
        reason = f"transaction raised: {errors}"
    elif not saw_external_write:
        reason = (
            f"transaction's delayed read did not observe the external write "
            f"(observed={observed_values})"
        )
    else:
        verdict = "PASS"
        reason = (
            "transaction's read was correctly delayed until after the release, "
            "and observed the externally committed value with no retry needed "
            "since the real read RPC had not yet been issued at pause time"
        )

    return {
        "events": events,
        "invocation_count": invocation_count["n"],
        "observed_values_by_attempt": observed_values,
        "errors": errors,
        "final_document_value": final_value,
        "no_deadlock": no_deadlock,
        "saw_external_write_on_delayed_read": saw_external_write,
        "verdict": verdict,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Phase 3: P-BARRIER (pre-commit killed-writer atomicity)
# ---------------------------------------------------------------------------


def _p_worker(project: str, database: str, prefix: str, ready, events_queue) -> None:
    def log(name: str, **fields: object) -> None:
        events_queue.put(
            {"name": name, "at": datetime.now(UTC).isoformat(), **fields}
        )

    raw = firestore.Client(project=project, database=database)
    counters = p7._Counters()
    barrier = p7._Barrier(mode="create")
    client = p7._P7Client(raw, prefix, counters, barrier=barrier)
    doc_ref = raw.collection(f"{prefix}__{PROBE_COLLECTION}").document("P-TARGET")

    def watch() -> None:
        if barrier.reached.wait(timeout=25):
            log("child_barrier_reached")
            ready.set()

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    transaction = client.transaction()

    @firestore.transactional
    def txn_body(transaction) -> None:
        log("child_txn_started")
        transaction.create(doc_ref, {"value": "should-never-commit", "written_at": _now()})

    log("child_process_started")
    try:
        txn_body(transaction)
        log("child_txn_committed_unexpectedly")
    except BaseException as error:  # noqa: BLE001
        log("child_txn_ended", detail=repr(error))


def _probe_p(raw: firestore.Client) -> dict[str, object]:
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    events_queue = context.Queue()
    process = context.Process(
        target=_p_worker,
        args=(DEFAULT_PROJECT, DEFAULT_DATABASE, NAMESPACE_PREFIX, ready, events_queue),
    )
    started_at = _now()
    process.start()
    reached = ready.wait(timeout=25)
    barrier_seen_at = _now()
    if not reached:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        return {
            "verdict": "FAIL",
            "reason": "P barrier was never reached; transaction.create was not "
            "intercepted at the expected call site, or the child process failed "
            "before reaching it.",
            "child_exitcode": process.exitcode,
        }

    kill_issued_at = _now()
    process.kill()
    process.join(timeout=10)
    kill_confirmed_dead_at = _now()
    child_exitcode = process.exitcode

    child_events: list[dict[str, object]] = []
    while True:
        try:
            child_events.append(events_queue.get(timeout=1))
        except Exception:  # noqa: BLE001
            break

    fresh_client = firestore.Client(project=DEFAULT_PROJECT, database=DEFAULT_DATABASE)
    target_ref = fresh_client.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}").document(
        "P-TARGET"
    )
    fresh_snapshot = target_ref.get()
    target_exists = fresh_snapshot.exists
    all_probe_docs = list(
        fresh_client.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}").stream()
    )
    unexpected_docs = [item.id for item in all_probe_docs if item.id not in ("O-TARGET",)]

    child_killed = child_exitcode is not None and child_exitcode != 0

    verdict = "FAIL"
    reason = ""
    if not reached:
        reason = "barrier not reached"
    elif not child_killed:
        reason = f"child did not report a killed exit status (exitcode={child_exitcode})"
    elif target_exists or unexpected_docs:
        reason = (
            f"partial write found after kill: target_exists={target_exists}, "
            f"unexpected_docs={unexpected_docs}"
        )
    else:
        verdict = "PASS"
        reason = (
            "barrier reached before commit, child confirmed killed, and a fresh "
            "client found zero partial authoritative state"
        )

    return {
        "started_at": started_at,
        "barrier_seen_at": barrier_seen_at,
        "kill_issued_at": kill_issued_at,
        "kill_confirmed_dead_at": kill_confirmed_dead_at,
        "child_exitcode": child_exitcode,
        "child_killed": child_killed,
        "child_events": child_events,
        "target_exists_after_kill": target_exists,
        "unexpected_docs": unexpected_docs,
        "verdict": verdict,
        "reason": reason,
    }


def main() -> int:
    if not RESULT_PATH.parent.exists():
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if RESULT_PATH.exists():
        print(f"Refusing to run: {RESULT_PATH} already exists.", file=sys.stderr)
        return 2

    started_at = _now()
    result: dict[str, object] = {
        "probe_id": PROBE_ID,
        "classification": "P7_TRANSACTION_BARRIER_CONTRACT_PROBE",
        "not_p7": True,
        "not_security_evidence": True,
        "harness_sha_tested": HARNESS_SHA,
        "barrier_code_digests": _barrier_code_digests(),
        "namespace_prefix": NAMESPACE_PREFIX,
        "project": DEFAULT_PROJECT,
        "database": DEFAULT_DATABASE,
        "started_at": started_at,
    }

    try:
        raw = firestore.Client(project=DEFAULT_PROJECT, database=DEFAULT_DATABASE)
        preflight = _preflight(raw)
        if any(preflight.values()):
            result["outcome"] = "BLOCKED"
            result["reason"] = "scratch namespace was not fresh"
            result["preflight"] = preflight
        else:
            result["preflight"] = preflight
            o_result = _probe_o(raw)
            p_result = _probe_p(raw)
            result["o_barrier"] = o_result
            result["p_barrier"] = p_result
            cleanup = _cleanup(raw)
            result["cleanup"] = cleanup

            if o_result["verdict"] == "PASS" and p_result["verdict"] == "PASS":
                overall = "P7-BARRIER-INFRASTRUCTURE-SUPPORTED"
            else:
                overall = "P7-BARRIER-INFRASTRUCTURE-FAIL"
            result["outcome"] = overall
    except BaseException as error:  # noqa: BLE001
        result["outcome"] = "BLOCKED"
        result["exception"] = _exception_record(error)

    result["completed_at"] = _now()
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"outcome": result["outcome"]}, indent=2))
    return 0 if result["outcome"] == "P7-BARRIER-INFRASTRUCTURE-SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
