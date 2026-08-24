#!/usr/bin/env python3
"""Corrected O-BARRIER contract probe (probe 02).

NOT P7. Not a security experiment. Not a B7 efficacy test.

Probe 01 (probe/p7-barrier-contract-20260824-01, evidence 21e23a9) crashed
its own txn_body with AttributeError because it called
``transaction.get(doc_ref).to_dict()`` directly, and installed
google-cloud-firestore 2.28.1 returns iterator semantics from
``Transaction.get``. This probe corrects ONLY that read call: it uses
``custody.firestore_store._FirestoreTransactionPort`` (imported unmodified)
so the read exercises the exact call path FirestoreAuthorityStore uses --
``document.get(transaction=transaction)`` -- rather than a raw
``transaction.get(document)`` call.

_Barrier, _P7Client, the interception strategy, the pause point, and release
semantics are imported unmodified from the frozen scripts/p7_run.py
(085c4d5a9a89d0ae932f5a4814af5620f0223306). Their source digests are checked
against probe 01's recorded values before any Firestore call is made; if
either differs this script stops with BARRIER-CODE-DRIFT and performs no
treatment.
"""

from __future__ import annotations

import hashlib
import inspect
import json
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
from custody.firestore_store import _FirestoreTransactionPort  # noqa: E402

PROBE_ID = "p7-barrier-contract-20260824-02"
NAMESPACE_PREFIX = "custody_p7_barrier_contract_20260824_02"
PROBE_COLLECTION = "probe_docs"
DEFAULT_PROJECT = p7.DEFAULT_PROJECT
DEFAULT_DATABASE = p7.DEFAULT_DATABASE
HARNESS_SHA = "085c4d5a9a89d0ae932f5a4814af5620f0223306"

# Digests recorded in probe 01's frozen evidence
# (research/production_b7/P7_BARRIER_CONTRACT_PROBE_RESULT.json, commit
# 21e23a9), for the same _Barrier / _P7Client source imported from
# scripts.p7_run at the same harness SHA.
EXPECTED_DIGESTS = {
    "_Barrier": "868ef667a59967747b7313d86cfaea211bfdc03472711cdc4afc16455b36ca93",
    "_P7Client": "0b1a3ecbf06a7af4d4597749ba44a55781c022c3a626414696b3e144c9917191",
    "_Counters": "1b59c78f70f8ece6664c9c32bd71b53452c04c804563baa13bdd787a8abe817f",
    "scripts/p7_run.py_whole_file": (
        "7ed5b262a8e06578216814d464ebfef162b26468e3ae58c15293afe91a893ccb"
    ),
}

PROOF_DIR = ROOT / "research" / "production_b7"
RESULT_PATH = PROOF_DIR / "P7_BARRIER_CONTRACT_PROBE_O2_RESULT.json"


def _current_digests() -> dict[str, str]:
    digests = {}
    for name in ("_Barrier", "_P7Client", "_Counters"):
        source = inspect.getsource(getattr(p7, name))
        digests[name] = hashlib.sha256(source.encode()).hexdigest()
    digests["scripts/p7_run.py_whole_file"] = hashlib.sha256(
        (ROOT / "scripts" / "p7_run.py").read_bytes()
    ).hexdigest()
    return digests


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _exception_record(error: BaseException) -> dict[str, object]:
    return {
        "type": type(error).__name__,
        "module": type(error).__module__,
        "message": str(error),
        "traceback": traceback.format_exc(),
    }


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


def _probe_o(raw: firestore.Client) -> dict[str, object]:
    events: list[dict[str, object]] = []

    def log(name: str, **fields: object) -> None:
        events.append({"name": name, "at": _now(), "monotonic": time.monotonic(), **fields})

    counters = p7._Counters()
    barrier = p7._Barrier(mode="get", match_record_id="O-TARGET")
    client = p7._P7Client(raw, NAMESPACE_PREFIX, counters, barrier=barrier)

    doc_ref = raw.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}").document("O-TARGET")
    doc_ref.create({"value": "before", "written_at": _now()})
    log("T1_seed_document_created", value="before")

    invocation_count = {"n": 0}
    observed_values: list[object] = []
    errors: list[str] = []

    transaction = client.transaction()  # frozen _P7Client.transaction(), unmodified

    @firestore.transactional
    def txn_body(transaction) -> object:
        invocation_count["n"] += 1
        log("T1_txn_invocation_started", attempt=invocation_count["n"])
        # Production-normalized read: exactly what FirestoreAuthorityStore
        # does via self._get -> transaction.get(reference) is NOT called;
        # _FirestoreTransactionPort.get() calls document.get(transaction=...).
        port = _FirestoreTransactionPort(transaction)
        snapshot = port.get(doc_ref)
        value = snapshot.to_dict().get("value") if snapshot.exists else None
        observed_values.append(value)
        log("T6_production_normalized_read_completed", attempt=invocation_count["n"], observed_value=value)
        transaction.set(doc_ref, {"value": f"txn_saw_{value}", "written_at": _now()})
        log("T7_txn_write_staged", attempt=invocation_count["n"])
        return value

    errors_holder: dict[str, object] = {}

    def run_txn() -> None:
        try:
            errors_holder["value"] = txn_body(transaction)
        except BaseException as error:  # noqa: BLE001
            errors.append(repr(error))
            errors_holder["exception"] = _exception_record(error)

    log("main_thread_launching_transaction")
    thread = threading.Thread(target=run_txn)
    thread.start()

    reached = barrier.reached.wait(timeout=20)
    log("T2_T3_barrier_reached_observed_by_parent", reached=reached)

    if not reached:
        thread.join(timeout=5)
        return {
            "events": events,
            "verdict": "FAIL",
            "reason": "O barrier was never reached within 20s. The production-"
            "normalized read path (_FirestoreTransactionPort.get -> "
            "document.get(transaction=...)) does not route through the "
            "transaction.get() method that _P7Client's barrier intercepts, so "
            "the interception point does not match the real production call "
            "site.",
            "invocation_count": invocation_count["n"],
            "thread_still_alive_after_timeout": thread.is_alive(),
        }

    external = firestore.Client(project=DEFAULT_PROJECT, database=DEFAULT_DATABASE)
    external_doc_ref = external.collection(
        f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}"
    ).document("O-TARGET")
    external_doc_ref.set({"value": "external_write", "written_at": _now()})
    log("T4_independent_client_committed_external_write", value="external_write")

    barrier.release.set()
    log("T5_main_thread_released_barrier")
    thread.join(timeout=20)
    log("transaction_thread_finished", still_alive=thread.is_alive())

    final_snapshot = raw.collection(f"{NAMESPACE_PREFIX}__{PROBE_COLLECTION}").document(
        "O-TARGET"
    ).get()
    final_value = final_snapshot.to_dict().get("value") if final_snapshot.exists else None
    log("T8_final_state_reread_by_fresh_call", value=final_value)

    retry_observed = invocation_count["n"] > 1
    no_deadlock = not thread.is_alive()
    saw_external_write = bool(observed_values) and observed_values[0] == "external_write"

    verdict = "FAIL"
    reason = ""
    if not no_deadlock:
        reason = "transaction thread did not finish (deadlock)"
    elif errors:
        reason = f"transaction raised: {errors}"
    elif not saw_external_write:
        reason = (
            f"delayed production-normalized read did not observe the external "
            f"write (observed={observed_values}, retry_observed={retry_observed})"
        )
    else:
        verdict = "PASS"
        reason = (
            "production-normalized read was correctly delayed until after "
            "release and observed the externally committed value"
        )

    return {
        "events": events,
        "invocation_count": invocation_count["n"],
        "retry_observed": retry_observed,
        "observed_values_by_attempt": observed_values,
        "errors": errors,
        "final_document_value": final_value,
        "no_deadlock": no_deadlock,
        "saw_external_write_on_delayed_read": saw_external_write,
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
        "classification": "P7_TRANSACTION_BARRIER_CONTRACT_PROBE_CORRECTED_O",
        "not_p7": True,
        "not_security_evidence": True,
        "harness_sha_tested": HARNESS_SHA,
        "prior_p_verdict_carried_forward": "PASS",
        "prior_p_evidence_commit": "21e23a9e6d1fd4f775f17ebc18d064c56a229e06",
        "namespace_prefix": NAMESPACE_PREFIX,
        "project": DEFAULT_PROJECT,
        "database": DEFAULT_DATABASE,
        "started_at": started_at,
    }

    current_digests = _current_digests()
    digest_matches = {name: current_digests[name] == value for name, value in EXPECTED_DIGESTS.items()}
    result["digest_check"] = {
        "expected": EXPECTED_DIGESTS,
        "actual": current_digests,
        "matches": digest_matches,
    }

    if not all(digest_matches.values()):
        result["outcome"] = "BARRIER-CODE-DRIFT"
        result["completed_at"] = _now()
        RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
        print(json.dumps({"outcome": result["outcome"]}, indent=2))
        return 2

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
            result["o_barrier"] = o_result
            cleanup = _cleanup(raw)
            result["cleanup"] = cleanup

            if o_result["verdict"] == "PASS":
                overall = "P7-BARRIER-INFRASTRUCTURE-SUPPORTED"
            else:
                overall = "P7-BARRIER-INFRASTRUCTURE-FAIL"
            result["outcome"] = overall
    except BaseException as error:  # noqa: BLE001
        result["outcome"] = "PROBE-HARNESS-FAIL"
        result["exception"] = _exception_record(error)

    result["completed_at"] = _now()
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"outcome": result["outcome"]}, indent=2))
    return 0 if result["outcome"] == "P7-BARRIER-INFRASTRUCTURE-SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
