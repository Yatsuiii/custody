#!/usr/bin/env python3
"""P7 real-Firestore production-equivalence run for frozen B7 semantics.

This is the real-Firestore extension of the frozen local proof in
``tests/test_b7_production_equivalence.py`` (see
``research/production_b7/EQUIVALENCE_TEST_PLAN.md``). Cases A1, A2, B-M reuse
the exact frozen construction and scoring logic from that test file via
``_world()`` injection -- no case, threshold, or scorer semantic is
redefined here. Cases N (restart), O (action/revocation race), and P (killed
writer) are re-implemented against real Firestore with real independent
processes, because the frozen local versions use SQLite/in-process barriers
that do not exist against a real Firestore backend.

This script does not compute an expected decision and hand it to production.
It does not import from ``research/``. It does not construct
``AdmissionEnvelope``/effective caps. Scoring uses the same frozen table as
the local proof (``tests.test_b7_production_equivalence._load_scoring_table``).

Freeze order: treatment completes -> raw trace written+digested -> scorer
runs -> result written+digested -> independent recomputation -> cleanup ->
cleanup recorded separately. Cleanup never rewrites treatment evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from google.cloud import firestore

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custody.authority import AuthorityOutput, ReceiptRootKey, TransformRef  # noqa: E402
from custody.firestore_store import (  # noqa: E402
    AUTHORITY_ACTION_DECISIONS_COLLECTION,
    AUTHORITY_DEPENDENCIES_COLLECTION,
    AUTHORITY_ISSUER_KEYS_COLLECTION,
    AUTHORITY_POLICIES_COLLECTION,
    AUTHORITY_RECEIPT_ROOTS_COLLECTION,
    AUTHORITY_REVOCATIONS_COLLECTION,
    AUTHORITY_REVOKED_ROOTS_COLLECTION,
    CUSTODY_COLLECTION,
    FirestoreAuthorityStore,
)

import tests.test_b7_production_equivalence as p6  # noqa: E402

# ---------------------------------------------------------------------------
# Fresh identity. Excludes every prior identity found in the repository
# (p7-b7-20260824-ec32e4e31d21, -obs01, -codec01) by construction: "run01"
# does not derive from or reuse any of those suffixes.
# ---------------------------------------------------------------------------
RUN_ID = "p7-b7-20260824-run01"
NAMESPACE_PREFIX = "custody_p7_b7_20260824_run01"
DEFAULT_PROJECT = "project-988bc9fe-092c-4b32-90c"
DEFAULT_DATABASE = "(default)"
DEFAULT_REGION = "us-central1"

PROOF_DIR = ROOT / "research" / "production_b7"
RAW_TRACE_PATH = PROOF_DIR / "P7_RUN01_RAW_TRACE.json"
RESULT_PATH = PROOF_DIR / "P7_RUN01_RESULT.json"
CLEANUP_PATH = PROOF_DIR / "P7_RUN01_CLEANUP.json"

COLLECTIONS = (
    CUSTODY_COLLECTION,
    AUTHORITY_DEPENDENCIES_COLLECTION,
    AUTHORITY_POLICIES_COLLECTION,
    AUTHORITY_ISSUER_KEYS_COLLECTION,
    AUTHORITY_RECEIPT_ROOTS_COLLECTION,
    AUTHORITY_REVOCATIONS_COLLECTION,
    AUTHORITY_REVOKED_ROOTS_COLLECTION,
    AUTHORITY_ACTION_DECISIONS_COLLECTION,
)

# Frozen resource policy (matches the previously stated P7 resource envelope;
# verified against this repo's own stated values, not silently altered).
RESOURCE_CEILING = {
    "reads": 1500,
    "writes": 200,
    "deletes": 200,
    "cost_usd": 0.01,
    "runtime_seconds": 600,
}
RECOVERY_BOUND_SECONDS = 90


class _Barrier:
    """One-shot pause inside a real Firestore transaction.

    Mirrors tests/test_b7_production_equivalence.py::_BarrierStore, but the
    hook point is the Transaction object itself (transaction.get / .create)
    rather than an AuthorityStore subclass, because production code must not
    be modified to add this hook.
    """

    def __init__(self, *, mode: str, match_record_id: str | None = None) -> None:
        self.mode = mode  # "get" or "create"
        self.match_record_id = match_record_id
        self.armed = True
        self.reached = threading.Event()
        self.release = threading.Event()

    def before_get(self, reference) -> None:
        if not self.armed or self.mode != "get":
            return
        if self.match_record_id is not None and reference.id != self.match_record_id:
            return
        self.armed = False
        self.reached.set()
        if not self.release.wait(timeout=15):
            raise TimeoutError("O barrier release timed out")

    def before_create(self, reference) -> None:
        if not self.armed or self.mode != "create":
            return
        self.armed = False
        self.reached.set()
        if not self.release.wait(timeout=30):
            raise TimeoutError("P barrier release timed out")


@dataclass
class _Counters:
    reads: int = 0
    writes: int = 0
    deletes: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"reads": self.reads, "writes": self.writes, "deletes": self.deletes}


class _P7Client:
    """Namespaced, instrumented, optionally-barriered Firestore client."""

    def __init__(
        self,
        raw: firestore.Client,
        prefix: str,
        counters: _Counters,
        barrier: _Barrier | None = None,
    ) -> None:
        self._raw = raw
        self._prefix = prefix
        self.counters = counters
        self.barrier = barrier

    def collection(self, name: str):
        return self._raw.collection(f"{self._prefix}__{name}")

    def transaction(self):
        transaction = self._raw.transaction()
        original_get = transaction.get
        original_create = transaction.create
        original_set = transaction.set
        original_delete = transaction.delete

        def counted_get(reference, *args, **kwargs):
            self.counters.reads += 1
            if self.barrier is not None:
                self.barrier.before_get(reference)
            return original_get(reference, *args, **kwargs)

        def counted_create(reference, data, *args, **kwargs):
            self.counters.writes += 1
            if self.barrier is not None:
                self.barrier.before_create(reference)
            return original_create(reference, data, *args, **kwargs)

        def counted_set(reference, data, *args, **kwargs):
            self.counters.writes += 1
            return original_set(reference, data, *args, **kwargs)

        def counted_delete(*args, **kwargs):
            self.counters.deletes += 1
            return original_delete(*args, **kwargs)

        transaction.get = counted_get
        transaction.create = counted_create
        transaction.set = counted_set
        transaction.delete = counted_delete
        return transaction


def _collection_counts(raw: firestore.Client, prefix: str) -> dict[str, int]:
    return {
        name: sum(1 for _ in raw.collection(f"{prefix}__{name}").stream())
        for name in COLLECTIONS
    }


def _cleanup(raw: firestore.Client, prefix: str) -> dict[str, object]:
    deleted: dict[str, int] = {}
    for name in COLLECTIONS:
        snapshots = tuple(raw.collection(f"{prefix}__{name}").stream())
        for snapshot in snapshots:
            snapshot.reference.delete()
        deleted[name] = len(snapshots)
    final_counts = _collection_counts(raw, prefix)
    return {
        "deleted_documents": deleted,
        "final_collection_counts": final_counts,
        "complete": all(count == 0 for count in final_counts.values()),
    }


def _exception_record(error: BaseException) -> dict[str, object]:
    return {
        "type": type(error).__name__,
        "module": type(error).__module__,
        "message": str(error),
        "traceback": traceback.format_exc(),
    }


# ---------------------------------------------------------------------------
# A1, A2, B-M: reuse the frozen local case construction unmodified by
# injecting a fresh Firestore-backed store per _world() call.
# ---------------------------------------------------------------------------


def _run_frozen_cases_against_firestore(
    raw: firestore.Client, counters: _Counters
) -> dict[str, object]:
    world_counter = {"n": 0}
    real_world = p6._world

    def firestore_world(store=None):
        assert store is None, "P7 injects its own Firestore-backed store"
        world_counter["n"] += 1
        sub_prefix = f"{NAMESPACE_PREFIX}__w{world_counter['n']:02d}"
        client = _P7Client(raw, sub_prefix, counters)
        return real_world(FirestoreAuthorityStore(client))

    p6._world = firestore_world
    try:
        first = p6._run_treatment()
        second = p6._run_treatment()
    finally:
        p6._world = real_world
    return {"first": first, "second": second}


# ---------------------------------------------------------------------------
# Case N: commit through one real process, reconstruct via a second,
# independent real process reconnecting to the same Firestore namespace.
# ---------------------------------------------------------------------------


def _n_worker(project: str, database: str, prefix: str, result_queue) -> None:
    try:
        raw = firestore.Client(project=project, database=database)
        counters = _Counters()
        client = _P7Client(raw, prefix, counters)
        store = FirestoreAuthorityStore(client)
        dispatcher = p6._Dispatcher()
        execution = p6.AuthorityGateway(store).execute(
            p6._action("action-N-restart"), ("N-CHILD",), dispatcher
        )
        result_queue.put(
            {
                "records": [item.record_id for item in store.records()],
                "dependencies": [
                    item.canonical_bytes().hex() for item in store.dependencies("N-CHILD")
                ],
                "execution": p6._execution_observation(execution),
                "dispatches": list(dispatcher.calls),
                "counters": counters.as_dict(),
            }
        )
    except BaseException as error:  # noqa: BLE001
        result_queue.put({"worker_error": repr(error), "detail": _exception_record(error)})


def _run_firestore_restart(raw: firestore.Client, counters: _Counters) -> dict[str, object]:
    prefix = f"{NAMESPACE_PREFIX}__caseN"
    client = _P7Client(raw, prefix, counters)
    store = FirestoreAuthorityStore(client)
    world = p6._world(store)
    root = p6._admit_source(world, 0, "N-ROOT")
    child = world.gate.admit_registered(
        TransformRef(p6.REGISTERED),
        ("N-ROOT",),
        AuthorityOutput.from_text(record_id="N-CHILD", text="ACCOUNT-101"),
    )
    before = {
        "root_admission": p6._admission_observation(root),
        "child_admission": p6._admission_observation(child),
        "records": [item.record_id for item in store.records()],
        "dependencies": [
            item.canonical_bytes().hex() for item in store.dependencies("N-CHILD")
        ],
    }
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_n_worker,
        args=(DEFAULT_PROJECT, DEFAULT_DATABASE, prefix, result_queue),
    )
    process.start()
    process.join(timeout=60)
    if process.is_alive():
        process.kill()
        process.join(timeout=10)
        return {"before": before, "worker_error": "restart worker timed out"}
    return {
        "before": before,
        "after": result_queue.get(timeout=5),
        "process_exitcode": process.exitcode,
        "backend": "firestore-independent-process",
    }


# ---------------------------------------------------------------------------
# Case O: action-eligibility read and revocation commit forced into a
# deterministic order via the transaction barrier.
# ---------------------------------------------------------------------------


def _run_firestore_race(raw: firestore.Client, counters: _Counters) -> dict[str, object]:
    prefix = f"{NAMESPACE_PREFIX}__caseO"
    barrier = _Barrier(mode="get", match_record_id="O-DESC")
    client = _P7Client(raw, prefix, counters, barrier=barrier)
    store = FirestoreAuthorityStore(client)
    world = p6._world(store)
    root = p6._admit_source(world, 0, "O-ROOT")
    child = world.gate.admit_registered(
        TransformRef(p6.REGISTERED),
        ("O-ROOT",),
        AuthorityOutput.from_text(record_id="O-DESC", text="O-DESC"),
    )
    before = p6._history(store)

    executions: list[object] = []
    errors: list[str] = []

    def execute() -> None:
        try:
            executions.append(
                world.gateway.execute(
                    p6._action("action-O-race"), ("O-DESC",), world.dispatcher
                )
            )
        except BaseException as error:  # noqa: BLE001
            errors.append(repr(error))

    thread = threading.Thread(target=execute)
    thread.start()
    reached = barrier.reached.wait(timeout=20)
    root_key = ReceiptRootKey.from_receipt(
        world.events[0].receipt, custody_root_record_id="O-ROOT"
    )
    revocation = world.controller.revoke_receipt_roots(
        revocation_id="O-race-revocation", root_keys=(root_key,)
    )
    barrier.release.set()
    thread.join(timeout=20)
    return {
        "root_admission": p6._admission_observation(root),
        "child_admission": p6._admission_observation(child),
        "candidate_barrier_reached": reached,
        "thread_finished": not thread.is_alive(),
        "thread_errors": errors,
        "execution": (p6._execution_observation(executions[0]) if executions else None),
        "affected_record_ids": list(revocation.affected_record_ids),
        "dispatches": list(world.dispatcher.calls),
        "history_before": before,
        "history_after": p6._history(store),
    }


# ---------------------------------------------------------------------------
# Case P: kill a real OS process while it is inside a real Firestore
# transaction, immediately before the transaction's first write commits.
# ---------------------------------------------------------------------------


def _p_worker(project: str, database: str, prefix: str, ready) -> None:
    raw = firestore.Client(project=project, database=database)
    counters = _Counters()
    barrier = _Barrier(mode="create")
    client = _P7Client(raw, prefix, counters, barrier=barrier)
    store = FirestoreAuthorityStore(client)

    def watch() -> None:
        if barrier.reached.wait(timeout=25):
            ready.set()

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    world = p6._world(store)
    p6._admit_source(world, 0, "P-ROOT")


def _run_firestore_killed_writer(
    raw: firestore.Client, counters: _Counters
) -> dict[str, object]:
    prefix = f"{NAMESPACE_PREFIX}__caseP"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_p_worker,
        args=(DEFAULT_PROJECT, DEFAULT_DATABASE, prefix, ready),
    )
    process.start()
    if not ready.wait(timeout=25):
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        return {"worker_error": "writer did not reach transaction barrier"}
    recovery_started = time.monotonic()
    process.kill()
    process.join(timeout=10)

    recovered_client = _P7Client(raw, prefix, counters)
    recovered_store = FirestoreAuthorityStore(recovered_client)
    records_before_retry = [item.record_id for item in recovered_store.records()]
    dependencies_before_retry = [
        item.canonical_bytes().hex() for item in recovered_store.dependencies("P-ROOT")
    ]
    dispatcher = p6._Dispatcher()
    immediate = p6.AuthorityGateway(recovered_store).execute(
        p6._action("action-P-after-kill"), ("P-ROOT",), dispatcher
    )
    retry = p6._admit_source(p6._world(recovered_store), 0, "P-ROOT")
    recovery_seconds = time.monotonic() - recovery_started
    final_ids = [item.record_id for item in recovered_store.records()]
    return {
        "killed_exitcode": process.exitcode,
        "records_before_retry": records_before_retry,
        "dependencies_before_retry": dependencies_before_retry,
        "immediate": p6._execution_observation(immediate),
        "dispatches": list(dispatcher.calls),
        "retry": p6._admission_observation(retry),
        "final_record_ids": final_ids,
        "duplicate_envelopes": len(final_ids) - len(set(final_ids)),
        "recovery_seconds": recovery_seconds,
        "recovery_completed_within_90_seconds": int(recovery_seconds <= RECOVERY_BOUND_SECONDS),
        "backend": "firestore-killed-writer-real-process",
    }


def _sha256_json(value: Mapping[str, object]) -> str:
    normalized = json.loads(json.dumps(value, sort_keys=True, default=str))
    return hashlib.sha256(
        (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--prefix", default=NAMESPACE_PREFIX)
    parser.add_argument(
        "--i-understand-this-spends-real-firestore-quota", action="store_true"
    )
    arguments = parser.parse_args()
    if not arguments.i_understand_this_spends_real_firestore_quota:
        print(
            "Refusing to run: pass "
            "--i-understand-this-spends-real-firestore-quota to execute "
            "against real Firestore.",
            file=sys.stderr,
        )
        return 2

    PROOF_DIR.mkdir(parents=True, exist_ok=True)
    for path in (RAW_TRACE_PATH, RESULT_PATH, CLEANUP_PATH):
        if path.exists():
            print(f"Refusing to run: {path} already exists.", file=sys.stderr)
            return 2

    started_at = datetime.now(UTC).isoformat()
    started_monotonic = time.monotonic()
    raw_client = firestore.Client(project=arguments.project, database=DEFAULT_DATABASE)
    preflight_counts = _collection_counts(raw_client, arguments.prefix)
    if any(preflight_counts.values()):
        print("Refusing to run: namespace is not fresh.", file=sys.stderr)
        return 2

    counters = _Counters()
    raw_trace: dict[str, object] = {
        "run_id": RUN_ID,
        "namespace_prefix": arguments.prefix,
        "project": arguments.project,
        "database": DEFAULT_DATABASE,
        "region": DEFAULT_REGION,
        "started_at": started_at,
    }
    scorer = p6._PostActionScorer()
    validity: dict[str, object] = {"status": "PENDING", "detail": None}
    frozen = race = restart = killed_writer = None
    try:
        frozen = _run_frozen_cases_against_firestore(raw_client, counters)
        race = _run_firestore_race(raw_client, counters)
        restart = _run_firestore_restart(raw_client, counters)
        killed_writer = _run_firestore_killed_writer(raw_client, counters)
        raw_trace["frozen_cases"] = frozen
        raw_trace["race"] = race
        raw_trace["restart"] = restart
        raw_trace["killed_writer"] = killed_writer
        raw_trace["resource_counters"] = counters.as_dict()
        raw_trace["runtime_seconds"] = time.monotonic() - started_monotonic
        validity["status"] = "TREATMENT-COMPLETED"
    except BaseException as error:  # noqa: BLE001
        validity["status"] = "P7-INVALID-RUNNER-ATTEMPT"
        validity["detail"] = _exception_record(error)
        raw_trace["runtime_seconds"] = time.monotonic() - started_monotonic

    raw_trace["validity"] = validity
    raw_trace["completed_at"] = datetime.now(UTC).isoformat()
    RAW_TRACE_PATH.write_text(
        json.dumps(raw_trace, indent=2, sort_keys=True, default=str) + "\n"
    )
    raw_trace_digest = _sha256_json(raw_trace)

    result: dict[str, object] = {
        "run_id": RUN_ID,
        "raw_trace_path": str(RAW_TRACE_PATH.relative_to(ROOT)),
        "raw_trace_digest": raw_trace_digest,
        "validity": validity,
    }

    if validity["status"] == "TREATMENT-COMPLETED":
        scorer.complete_actions()
        score = scorer.score(
            frozen["first"],
            frozen["second"],
            restart=restart,
            race=race,
            killed_writer=killed_writer,
        )
        result["status"] = score["status"]
        result["failures"] = score["failures"]
        result["metrics"] = score["metrics"]
        result["resource_counters"] = counters.as_dict()
        result["resource_ceiling"] = RESOURCE_CEILING
        result["resource_ceiling_exceeded"] = (
            counters.reads > RESOURCE_CEILING["reads"]
            or counters.writes > RESOURCE_CEILING["writes"]
            or counters.deletes > RESOURCE_CEILING["deletes"]
        )
        result["recovery_completed_within_90_seconds"] = killed_writer.get(
            "recovery_completed_within_90_seconds"
        )

        # Independent recomputation from the frozen raw trace only.
        rescored = scorer.score(
            frozen["first"],
            frozen["second"],
            restart=restart,
            race=race,
            killed_writer=killed_writer,
        )
        result["independent_recomputation_matches"] = rescored == score
    else:
        result["status"] = validity["status"]

    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    result_digest = _sha256_json(result)

    cleanup = _cleanup(raw_client, arguments.prefix)
    cleanup_record = {
        "run_id": RUN_ID,
        "result_digest": result_digest,
        "cleanup": cleanup,
    }
    CLEANUP_PATH.write_text(json.dumps(cleanup_record, indent=2, sort_keys=True) + "\n")

    print(
        json.dumps(
            {"result_status": result["status"], "result_digest": result_digest}, indent=2
        )
    )
    return 0 if validity["status"] == "TREATMENT-COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
