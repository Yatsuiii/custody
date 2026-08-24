#!/usr/bin/env python3
"""Fresh O/P contract probe for the run03 barrier lifecycle.

Infrastructure evidence only: not P7, a security experiment, or B7 efficacy
evidence. The probe imports the real barrier implementation from the run03
harness and checks both transaction-aware reads and Transaction.create.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import multiprocessing
import queue
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

import scripts.p7_run as p7  # noqa: E402  (reuse corrected harness code)
from custody.firestore_store import _FirestoreTransactionPort  # noqa: E402

PROBE_ID = "p7-barrier-contract-20260825-04"
NAMESPACE_PREFIX = "custody_p7_barrier_contract_20260825_04"
PROBE_COLLECTION = "probe_docs"
DEFAULT_PROJECT = p7.DEFAULT_PROJECT
DEFAULT_DATABASE = p7.DEFAULT_DATABASE
HARNESS_SHA = "d352c2edf0c0b08d6d3e9def6aaea106d6d0791e"

PROOF_DIR = ROOT / "research" / "production_b7"
RESULT_PATH = PROOF_DIR / "P7_BARRIER_CONTRACT_PROBE_04_RESULT.json"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _exception_record(error: BaseException) -> dict[str, object]:
    return {
        "type": type(error).__name__,
        "module": type(error).__module__,
        "message": str(error),
        "traceback": traceback.format_exc(),
    }


def _barrier_code_digests() -> dict[str, str]:
    names = ("_Barrier", "_Counters", "_P7FirestoreApi", "_P7Client")
    digests = {
        name: hashlib.sha256(inspect.getsource(getattr(p7, name)).encode()).hexdigest()
        for name in names
    }
    digests["scripts/p7_run.py_whole_file"] = hashlib.sha256(
        (ROOT / "scripts" / "p7_run.py").read_bytes()
    ).hexdigest()
    return digests


def _collection_ref(raw: firestore.Client):
    return raw.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}")


def _preflight(raw: firestore.Client) -> dict[str, int]:
    return {PROBE_COLLECTION: sum(1 for _ in _collection_ref(raw).stream())}


def _cleanup(raw: firestore.Client) -> dict[str, object]:
    snapshots = tuple(_collection_ref(raw).stream())
    for snapshot in snapshots:
        snapshot.reference.delete()
    remaining = sum(1 for _ in _collection_ref(raw).stream())
    return {"deleted": len(snapshots), "remaining": remaining, "complete": remaining == 0}


def _probe_o(raw: firestore.Client) -> dict[str, object]:
    events: list[dict[str, object]] = []

    def log(name: str, **fields: object) -> None:
        events.append({"name": name, "at": _now(), "monotonic": time.monotonic(), **fields})

    counters = p7._Counters()
    barrier = p7._Barrier(mode="get", match_record_id="O-TARGET")
    client = p7._P7Client(raw, NAMESPACE_PREFIX, counters, barrier=barrier)
    doc_ref = _collection_ref(raw).document("O-TARGET")
    doc_ref.create({"value": "before", "written_at": _now()})
    log("T1_seed_document_created", value="before")

    invocation_count = {"n": 0}
    observed_values: list[object] = []
    errors: list[dict[str, object]] = []
    transaction = client.transaction()
    barrier.arm()

    @firestore.transactional
    def txn_body(transaction) -> object:
        invocation_count["n"] += 1
        attempt = invocation_count["n"]
        log("T2_transaction_invocation_started", attempt=attempt)
        snapshot = _FirestoreTransactionPort(transaction).get(doc_ref)
        value = snapshot.to_dict().get("value") if snapshot.exists else None
        observed_values.append(value)
        log("T3_production_normalized_read_completed", attempt=attempt, value=value)
        transaction.set(doc_ref, {"value": f"txn_saw_{value}", "written_at": _now()})
        log("T7_transaction_write_staged", attempt=attempt)
        return value

    result_holder: dict[str, object] = {}

    def run_txn() -> None:
        try:
            result_holder["value"] = txn_body(transaction)
        except BaseException as error:  # noqa: BLE001
            errors.append(_exception_record(error))

    log("T1_transaction_thread_launched")
    thread = threading.Thread(target=run_txn)
    thread.start()
    reached = barrier.reached.wait(timeout=25)
    log("T4_barrier_reached_observed_by_parent", reached=reached)
    if not reached:
        barrier.release.set()
        thread.join(timeout=10)
        return {
            "events": events,
            "invocation_count": invocation_count["n"],
            "errors": errors,
            "thread_finished": not thread.is_alive(),
            "verdict": "FAIL",
            "reason": "transaction-aware read did not reach the armed RPC barrier",
        }

    external = firestore.Client(project=DEFAULT_PROJECT, database=DEFAULT_DATABASE)
    external_ref = external.collection(
        f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}"
    ).document("O-TARGET")
    external_ref.set({"value": "external_write", "written_at": _now()})
    log("T5_independent_client_committed_external_write", value="external_write")
    barrier.release.set()
    log("T6_parent_released_barrier")
    thread.join(timeout=25)
    log("T8_transaction_thread_finished", still_alive=thread.is_alive())

    final_snapshot = _collection_ref(raw).document("O-TARGET").get()
    final_value = final_snapshot.to_dict().get("value") if final_snapshot.exists else None
    log("T9_fresh_call_reread_final_state", value=final_value)
    no_deadlock = not thread.is_alive()
    saw_external_write = bool(observed_values) and observed_values[0] == "external_write"
    if not no_deadlock:
        reason = "transaction thread did not finish after barrier release"
    elif errors:
        reason = f"transaction raised: {errors}"
    elif not saw_external_write:
        reason = f"delayed read observed {observed_values!r}, not external_write"
    else:
        reason = "armed RPC barrier delayed the production-normalized read correctly"
    return {
        "events": events,
        "invocation_count": invocation_count["n"],
        "observed_values_by_attempt": observed_values,
        "errors": errors,
        "result": result_holder.get("value"),
        "final_document_value": final_value,
        "barrier_reached": reached,
        "no_deadlock": no_deadlock,
        "saw_external_write_on_delayed_read": saw_external_write,
        "verdict": "PASS" if not errors and no_deadlock and saw_external_write else "FAIL",
        "reason": reason,
    }


def _p_worker(project: str, database: str, prefix: str, ready, event_queue) -> None:
    def log(name: str, **fields: object) -> None:
        event_queue.put({"name": name, "at": _now(), **fields})

    raw = firestore.Client(project=project, database=database)
    barrier = p7._Barrier(mode="create")
    client = p7._P7Client(raw, prefix, p7._Counters(), barrier=barrier)
    doc_ref = raw.collection(f"{prefix}__{PROBE_COLLECTION}").document("P-TARGET")

    def watch() -> None:
        if barrier.reached.wait(timeout=30):
            log("P_barrier_reached_in_child")
            ready.set()

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    barrier.arm()
    transaction = client.transaction()

    @firestore.transactional
    def txn_body(transaction) -> None:
        log("P_transaction_started")
        transaction.create(doc_ref, {"value": "should_never_commit", "written_at": _now()})

    log("P_child_started")
    txn_body(transaction)
    log("P_unexpected_commit_completed")


def _drain_events(event_queue) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            events.append(event_queue.get(timeout=0.2))
        except queue.Empty:
            if events:
                break
    return events


def _probe_p(raw: firestore.Client) -> dict[str, object]:
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    event_queue = context.Queue()
    process = context.Process(
        target=_p_worker,
        args=(DEFAULT_PROJECT, DEFAULT_DATABASE, NAMESPACE_PREFIX, ready, event_queue),
    )
    started_at = _now()
    process.start()
    reached = ready.wait(timeout=35)
    barrier_seen_at = _now()
    kill_issued_at = _now()
    if process.is_alive():
        process.kill()
    process.join(timeout=15)
    child_exitcode = process.exitcode
    child_events = _drain_events(event_queue)

    target_exists = _collection_ref(raw).document("P-TARGET").get().exists
    all_probe_docs = list(_collection_ref(raw).stream())
    unexpected_docs = [item.id for item in all_probe_docs if item.id != "O-TARGET"]
    child_killed = child_exitcode is not None and child_exitcode != 0
    if not reached:
        reason = "P create barrier was not reached before timeout"
    elif not child_killed:
        reason = f"child did not have a killed exit status: {child_exitcode}"
    elif target_exists or unexpected_docs:
        reason = f"partial state found: target={target_exists}, unexpected={unexpected_docs}"
    else:
        reason = "create barrier reached before commit and fresh read found no partial document"
    return {
        "started_at": started_at,
        "barrier_seen_at": barrier_seen_at,
        "kill_issued_at": kill_issued_at,
        "child_exitcode": child_exitcode,
        "child_killed": child_killed,
        "child_events": child_events,
        "barrier_reached": reached,
        "target_exists_after_kill": target_exists,
        "unexpected_docs": unexpected_docs,
        "verdict": "PASS" if reached and child_killed and not target_exists and not unexpected_docs else "FAIL",
        "reason": reason,
    }


def main() -> int:
    if RESULT_PATH.exists():
        print(f"Refusing to run: {RESULT_PATH} already exists.", file=sys.stderr)
        return 2

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
        "started_at": _now(),
    }
    raw = None
    try:
        raw = firestore.Client(project=DEFAULT_PROJECT, database=DEFAULT_DATABASE)
        preflight = _preflight(raw)
        result["preflight"] = preflight
        if any(preflight.values()):
            result["outcome"] = "BLOCKED"
            result["reason"] = "fresh scratch namespace was not empty"
        else:
            o_result = _probe_o(raw)
            p_result = _probe_p(raw)
            result["o_barrier"] = o_result
            result["p_barrier"] = p_result
            result["outcome"] = (
                "P7-BARRIER-INFRASTRUCTURE-SUPPORTED"
                if o_result["verdict"] == "PASS" and p_result["verdict"] == "PASS"
                else "P7-BARRIER-INFRASTRUCTURE-FAIL"
            )
    except BaseException as error:  # noqa: BLE001
        result["outcome"] = "BLOCKED"
        result["exception"] = _exception_record(error)
    finally:
        if raw is not None:
            try:
                result["cleanup"] = _cleanup(raw)
            except BaseException as error:  # noqa: BLE001
                result["cleanup"] = {"complete": False, "exception": _exception_record(error)}

    result["completed_at"] = _now()
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"outcome": result["outcome"]}, indent=2))
    return 0 if result["outcome"] == "P7-BARRIER-INFRASTRUCTURE-SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
