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
import os
import sys
import threading
import time
import traceback
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
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
# Fresh identity. This revision must not reuse run01, whose behavior was tied
# to the pre-fix read-barrier implementation.
# ---------------------------------------------------------------------------
RUN_ID = "p7-b7-20260825-run03"
NAMESPACE_PREFIX = "custody_p7_b7_20260825_run03"
DEFAULT_PROJECT = "project-988bc9fe-092c-4b32-90c"
DEFAULT_DATABASE = "(default)"
DEFAULT_REGION = "us-central1"

PROOF_DIR = ROOT / "research" / "production_b7"
RAW_TRACE_PATH = PROOF_DIR / "P7_RUN03_RAW_TRACE.json"
RESULT_PATH = PROOF_DIR / "P7_RUN03_RESULT.json"
CLEANUP_PATH = PROOF_DIR / "P7_RUN03_CLEANUP.json"

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


def _document_path(project: str, database: str, collection: str, document_id: str) -> str:
    """Return the Firestore API path used by transaction telemetry and barriers."""

    return (
        f"projects/{project}/databases/{database}/documents/"
        f"{collection}/{document_id}"
    )


def _reference_document_path(reference) -> str:
    """Read the installed SDK's canonical document path without an RPC."""

    path = getattr(reference, "_document_path", None)
    if not isinstance(path, str) or not path:
        raise RuntimeError("Firestore reference did not expose _document_path")
    return path


@dataclass
class _TransactionAttempt:
    process_role: str
    pid: int
    callback_attempt: int
    transaction_start_monotonic: float
    transaction_id: str | None = None
    document_reads: list[str] = field(default_factory=list)
    document_creates: list[str] = field(default_factory=list)
    document_sets: list[str] = field(default_factory=list)
    document_deletes: list[str] = field(default_factory=list)
    barrier_matched: bool = False
    exact_matched_path: str | None = None
    commit_attempted: bool = False
    commit_result: str | None = None
    retry_reason: str | None = None
    callback_end_monotonic: float | None = None
    transaction_end_monotonic: float | None = None

    def as_dict(self) -> dict[str, object]:
        paths = (
            self.document_reads
            + self.document_creates
            + self.document_sets
            + self.document_deletes
        )
        if any("/authority_issuer_keys/" in path for path in paths):
            purpose = "issuer-key-setup"
        elif any("/authority_policies/" in path for path in paths):
            purpose = "policy-setup"
        elif any(path.endswith("/custody/P-ROOT") for path in paths):
            purpose = "P-ROOT-admission"
        elif "/authority_action_decisions/" in " ".join(paths):
            purpose = "action-decision"
        else:
            purpose = "unknown"
        return {
            "process_role": self.process_role,
            "pid": self.pid,
            "transaction_purpose": purpose,
            "callback_attempt": self.callback_attempt,
            "transaction_start_monotonic": self.transaction_start_monotonic,
            "transaction_id": self.transaction_id,
            "document_reads": list(self.document_reads),
            "document_creates": list(self.document_creates),
            "document_sets": list(self.document_sets),
            "document_deletes": list(self.document_deletes),
            "barrier_matched": self.barrier_matched,
            "exact_matched_path": self.exact_matched_path,
            "commit_attempted": self.commit_attempted,
            "commit_result": self.commit_result,
            "retry_reason": self.retry_reason,
            "callback_end_monotonic": self.callback_end_monotonic,
            "transaction_end_monotonic": self.transaction_end_monotonic,
        }


class _TransactionTelemetry:
    """Capture transaction attempts without changing production code."""

    def __init__(self, process_role: str) -> None:
        self.process_role = process_role
        self.pid = os.getpid()
        self._states: dict[int, dict[str, object]] = {}
        self._attempts: list[_TransactionAttempt] = []
        self._by_transaction_id: dict[str, _TransactionAttempt] = {}

    @staticmethod
    def _transaction_key(value: object) -> str:
        if isinstance(value, bytes):
            return value.hex()
        return str(value)

    def attach(self, transaction) -> None:
        self._states[id(transaction)] = {"attempt": 0, "current": None}

    def begin(self, transaction, original_begin, *args, **kwargs):
        state = self._states.setdefault(id(transaction), {"attempt": 0, "current": None})
        state["attempt"] = int(state["attempt"]) + 1
        attempt = _TransactionAttempt(
            process_role=self.process_role,
            pid=self.pid,
            callback_attempt=int(state["attempt"]),
            transaction_start_monotonic=time.monotonic(),
        )
        self._attempts.append(attempt)
        state["current"] = attempt
        try:
            result = original_begin(*args, **kwargs)
            transaction_id = getattr(transaction, "id", None)
            if transaction_id is not None:
                attempt.transaction_id = self._transaction_key(transaction_id)
                self._by_transaction_id[attempt.transaction_id] = attempt
            return result
        except BaseException as error:
            self.finish(attempt, commit_result=f"begin-error:{type(error).__name__}")
            raise

    def current(self, transaction) -> _TransactionAttempt | None:
        state = self._states.get(id(transaction))
        if state is None:
            return None
        current = state.get("current")
        return current if isinstance(current, _TransactionAttempt) else None

    def by_transaction_id(self, transaction_id: object) -> _TransactionAttempt | None:
        return self._by_transaction_id.get(self._transaction_key(transaction_id))

    def finish(self, attempt: _TransactionAttempt, *, commit_result: str) -> None:
        if attempt.transaction_end_monotonic is not None:
            return
        attempt.callback_end_monotonic = time.monotonic()
        attempt.transaction_end_monotonic = attempt.callback_end_monotonic
        attempt.commit_result = commit_result

    def commit(self, transaction, original_commit, *args, **kwargs):
        attempt = self.current(transaction)
        if attempt is not None:
            attempt.commit_attempted = True
        try:
            result = original_commit(*args, **kwargs)
        except BaseException as error:
            if attempt is not None:
                attempt.retry_reason = f"{type(error).__module__}.{type(error).__name__}: {error}"
                self.finish(attempt, commit_result=f"failure:{type(error).__name__}")
            raise
        else:
            if attempt is not None:
                self.finish(attempt, commit_result="success")
            return result

    def rollback(self, transaction, original_rollback, *args, **kwargs):
        attempt = self.current(transaction)
        try:
            return original_rollback(*args, **kwargs)
        finally:
            if attempt is not None:
                self.finish(attempt, commit_result=attempt.commit_result or "rollback")

    def record_read(self, transaction_id: object, document: str) -> None:
        attempt = self.by_transaction_id(transaction_id)
        if attempt is not None and document not in attempt.document_reads:
            attempt.document_reads.append(document)

    def record_write(self, transaction, operation: str, reference) -> _TransactionAttempt | None:
        attempt = self.current(transaction)
        if attempt is None:
            return None
        document = _reference_document_path(reference)
        targets = {
            "create": attempt.document_creates,
            "set": attempt.document_sets,
            "delete": attempt.document_deletes,
        }
        if document not in targets[operation]:
            targets[operation].append(document)
        return attempt

    def attempts(self) -> list[dict[str, object]]:
        return [attempt.as_dict() for attempt in self._attempts]

    def current_snapshot(self) -> dict[str, object] | None:
        current = next(
            (
                attempt
                for attempt in reversed(self._attempts)
                if attempt.transaction_end_monotonic is None
            ),
            None,
        )
        return None if current is None else current.as_dict()

    def has_provisioning_writes(self) -> bool:
        return any(
            "/authority_issuer_keys/" in path or "/authority_policies/" in path
            for attempt in self._attempts
            for path in (
                attempt.document_creates
                + attempt.document_sets
                + attempt.document_deletes
            )
        )

    def as_dict(self) -> dict[str, object]:
        return {"process_role": self.process_role, "pid": self.pid, "attempts": self.attempts()}


class _Barrier:
    """One-shot pause inside a real Firestore transaction.

    Mirrors tests/test_b7_production_equivalence.py::_BarrierStore, but the
    hook points are the Firestore SDK RPC boundary for reads and the
    Transaction object for writes, rather than an AuthorityStore subclass,
    because production code must not be modified to add this hook.
    """

    def __init__(
        self,
        *,
        mode: str,
        match_record_id: str | None = None,
        match_document_path: str | None = None,
    ) -> None:
        self.mode = mode  # "get" or "create"
        self.match_record_id = match_record_id
        self.match_document_path = match_document_path
        self.armed = False
        self.reached = threading.Event()
        self.release = threading.Event()
        self.matched_path: str | None = None

    def arm(self) -> None:
        """Enable the one-shot pause after its caller has finished setup."""
        self.armed = True

    def before_get(self, document_id: str) -> None:
        if not self.armed or self.mode != "get":
            return
        if self.match_record_id is not None and document_id != self.match_record_id:
            return
        self.armed = False
        self.reached.set()
        if not self.release.wait(timeout=15):
            raise TimeoutError("O barrier release timed out")

    def before_create(self, reference, attempt: _TransactionAttempt | None = None) -> None:
        if not self.armed or self.mode != "create":
            return
        document_path = _reference_document_path(reference)
        if (
            self.match_document_path is not None
            and document_path != self.match_document_path
        ):
            return
        self.armed = False
        self.matched_path = document_path
        if attempt is not None:
            attempt.barrier_matched = True
            attempt.exact_matched_path = document_path
        self.reached.set()
        if not self.release.wait(timeout=30):
            raise TimeoutError("P barrier release timed out")

    def snapshot(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "armed": self.armed,
            "reached": self.reached.is_set(),
            "match_document_path": self.match_document_path,
            "matched_path": self.matched_path,
            "released": self.release.is_set(),
        }


@dataclass
class _Counters:
    reads: int = 0
    writes: int = 0
    deletes: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"reads": self.reads, "writes": self.writes, "deletes": self.deletes}


class _P7FirestoreApi:
    """Instrument the SDK RPC boundary used by transaction-aware reads.

    In the installed Firestore SDK, ``DocumentReference.get(transaction=...)``
    and ``Client.get_all(..., transaction=...)`` call
    ``client._firestore_api.batch_get_documents`` directly.  The public
    ``Transaction.get`` method delegates to ``Client.get_all`` and is therefore
    not a reliable interception point for the production-normalized read path.
    """

    def __init__(
        self,
        delegate,
        counters: _Counters,
        barrier: _Barrier | None,
        telemetry: _TransactionTelemetry | None,
    ) -> None:
        self._delegate = delegate
        self._counters = counters
        self._barrier = barrier
        self._telemetry = telemetry

    @staticmethod
    def _request_value(request, name: str):
        if isinstance(request, MappingABC):
            return request.get(name)
        return getattr(request, name, None)

    def batch_get_documents(self, *args, **kwargs):
        request = kwargs.get("request")
        if request is None and args:
            request = args[0]
        documents = tuple(self._request_value(request, "documents") or ())
        transaction_id = self._request_value(request, "transaction")
        self._counters.reads += len(documents)
        if self._barrier is not None and transaction_id:
            for document in documents:
                self._barrier.before_get(document.rsplit("/", 1)[-1])
        if self._telemetry is not None and transaction_id:
            for document in documents:
                self._telemetry.record_read(transaction_id, document)
        return self._delegate.batch_get_documents(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)


class _P7Client:
    """Namespaced, instrumented, optionally-barriered Firestore client."""

    def __init__(
        self,
        raw: firestore.Client,
        prefix: str,
        counters: _Counters,
        barrier: _Barrier | None = None,
        telemetry: _TransactionTelemetry | None = None,
        process_role: str = "unspecified",
    ) -> None:
        self._raw = raw
        self._prefix = prefix
        self.counters = counters
        self.barrier = barrier
        self.telemetry = telemetry
        self.process_role = process_role
        api = self._raw._firestore_api
        if isinstance(api, _P7FirestoreApi):
            api = api._delegate
        self._raw._firestore_api_internal = _P7FirestoreApi(
            api, self.counters, self.barrier, self.telemetry
        )

    def collection(self, name: str):
        return self._raw.collection(f"{self._prefix}__{name}")

    def transaction(self):
        transaction = self._raw.transaction()
        original_create = transaction.create
        original_set = transaction.set
        original_delete = transaction.delete
        original_begin = transaction._begin
        original_commit = transaction._commit
        original_rollback = transaction._rollback

        if self.telemetry is not None:
            self.telemetry.attach(transaction)

            def tracked_begin(*args, **kwargs):
                return self.telemetry.begin(
                    transaction, original_begin, *args, **kwargs
                )

            def tracked_commit(*args, **kwargs):
                return self.telemetry.commit(
                    transaction, original_commit, *args, **kwargs
                )

            def tracked_rollback(*args, **kwargs):
                return self.telemetry.rollback(
                    transaction, original_rollback, *args, **kwargs
                )

            transaction._begin = tracked_begin
            transaction._commit = tracked_commit
            transaction._rollback = tracked_rollback

        def counted_create(reference, data, *args, **kwargs):
            self.counters.writes += 1
            attempt = (
                None
                if self.telemetry is None
                else self.telemetry.record_write(transaction, "create", reference)
            )
            if self.barrier is not None:
                self.barrier.before_create(reference, attempt)
            return original_create(reference, data, *args, **kwargs)

        def counted_set(reference, data, *args, **kwargs):
            self.counters.writes += 1
            if self.telemetry is not None:
                self.telemetry.record_write(transaction, "set", reference)
            return original_set(reference, data, *args, **kwargs)

        def counted_delete(reference, *args, **kwargs):
            self.counters.deletes += 1
            if self.telemetry is not None:
                self.telemetry.record_write(transaction, "delete", reference)
            return original_delete(reference, *args, **kwargs)

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
    barrier.arm()

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


def _configured_world(store) -> object:
    """Build the frozen world wiring without provisioning any Firestore state."""

    events = p6._events()
    return p6._World(
        events=events,
        store=store,
        gate=p6.AdmissionGate(
            store=store,
            source_policy_keys=(events[0].receipt.policy_key,),
            identity_policy_key=p6.IDENTITY,
            registered_policy_keys=(p6.REGISTERED,),
            freeform_policy_key=p6.FREEFORM,
        ),
        gateway=p6.AuthorityGateway(store),
        controller=p6.RevocationController(store),
        dispatcher=p6._Dispatcher(),
    )


def _verify_case_p_setup(
    raw: firestore.Client,
    project: str,
    database: str,
    prefix: str,
) -> dict[str, object]:
    """Verify setup through an independent client after all setup commits."""

    verify_raw = firestore.Client(project=project, database=database)
    verify_client = _P7Client(
        verify_raw,
        prefix,
        _Counters(),
        process_role="setup-verifier",
    )
    verify_store = FirestoreAuthorityStore(verify_client)
    events = p6._events()
    expected_issuers = (
        (
            events[0].receipt.issuer_id,
            events[0].receipt.issuer_key_id,
            bytes.fromhex((p6.FIXTURES / "issuer_public_key.hex").read_text().strip()),
        ),
        (
            events[1].receipt.issuer_id,
            events[1].receipt.issuer_key_id,
            bytes.fromhex(
                (p6.FIXTURES / "issuer_public_key_v2.hex").read_text().strip()
            ),
        ),
    )
    issuer_checks = [
        {
            "issuer_id": issuer_id,
            "issuer_key_id": issuer_key_id,
            "present_and_exact": verify_store.public_key_for(
                issuer_id=issuer_id, issuer_key_id=issuer_key_id
            )
            == public_key,
        }
        for issuer_id, issuer_key_id, public_key in expected_issuers
    ]
    expected_policies = (
        p6.PolicySnapshot(
            events[0].receipt.policy_key,
            "v7",
            7,
            p6.OperationRole.ORIGIN,
            {"export.send": p6.Capability.ACT},
        ),
        *(
            p6.PolicySnapshot(
                key,
                "v1",
                1,
                p6.OperationRole.RELAY,
                {"export.send": p6.Capability.ACT},
            )
            for key in (p6.IDENTITY, p6.REGISTERED, p6.FREEFORM)
        ),
    )
    policy_checks = [
        {
            "policy_key": snapshot.policy_key.as_list(),
            "present_and_exact": verify_store.policy(snapshot.policy_key) == snapshot,
        }
        for snapshot in expected_policies
    ]
    if hasattr(verify_raw, "close"):
        verify_raw.close()
    return {
        "issuer_checks": issuer_checks,
        "policy_checks": policy_checks,
        "complete": all(item["present_and_exact"] for item in issuer_checks)
        and all(item["present_and_exact"] for item in policy_checks),
    }


def _setup_case_p(
    raw: firestore.Client,
    project: str,
    database: str,
    prefix: str,
    counters: _Counters,
) -> dict[str, object]:
    """Provision Case P before the measured process exists."""

    telemetry = _TransactionTelemetry("setup-parent")
    client = _P7Client(
        raw,
        prefix,
        counters,
        process_role="setup-parent",
        telemetry=telemetry,
    )
    setup_store = FirestoreAuthorityStore(client)
    p6._world(setup_store)
    verification = _verify_case_p_setup(raw, project, database, prefix)
    if not verification["complete"]:
        raise RuntimeError("Case P setup verification failed")
    return {
        "setup_complete": True,
        "setup_completed_at": datetime.now(UTC).isoformat(),
        "setup_complete_monotonic": time.monotonic(),
        "setup_telemetry": telemetry.as_dict(),
        "verification": verification,
    }


def _p_worker(
    project: str,
    database: str,
    prefix: str,
    expected_path: str,
    startup_ready,
    startup_queue,
    barrier_ready,
    barrier_queue,
) -> None:
    raw = firestore.Client(project=project, database=database)
    counters = _Counters()
    telemetry = _TransactionTelemetry("measured-child")
    barrier = _Barrier(mode="create", match_document_path=expected_path)
    client = _P7Client(
        raw,
        prefix,
        counters,
        barrier=barrier,
        process_role="measured-child",
        telemetry=telemetry,
    )
    store = FirestoreAuthorityStore(client)

    world = _configured_world(store)
    startup_queue.put(
        {
            "process_role": "measured-child",
            "pid": os.getpid(),
            "barrier": barrier.snapshot(),
            "telemetry": telemetry.as_dict(),
            "provisioning_transactions": len(telemetry.attempts()),
        }
    )
    startup_ready.set()
    if telemetry.attempts():
        return

    def watch() -> None:
        if barrier.reached.wait(timeout=25):
            barrier_queue.put(
                {
                    "process_role": "measured-child",
                    "pid": os.getpid(),
                    "barrier": barrier.snapshot(),
                    "current_transaction": telemetry.current_snapshot(),
                    "telemetry": telemetry.as_dict(),
                }
            )
            barrier_ready.set()

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    barrier.arm()
    p6._admit_source(world, 0, "P-ROOT")


def _run_case_p_lifecycle(
    raw: firestore.Client,
    project: str,
    database: str,
    prefix: str,
    counters: _Counters,
) -> dict[str, object]:
    """Run the redesigned setup/measure/kill/recovery lifecycle once."""

    preflight_counts = _collection_counts(raw, prefix)
    if any(preflight_counts.values()):
        raise RuntimeError(f"Case P namespace is not fresh: {preflight_counts}")
    setup = _setup_case_p(raw, project, database, prefix, counters)
    expected_path = _document_path(
        project, database, f"{prefix}__{CUSTODY_COLLECTION}", "P-ROOT"
    )
    context = multiprocessing.get_context("spawn")
    startup_ready = context.Event()
    startup_queue = context.Queue()
    barrier_ready = context.Event()
    barrier_queue = context.Queue()
    process = context.Process(
        target=_p_worker,
        args=(
            project,
            database,
            prefix,
            expected_path,
            startup_ready,
            startup_queue,
            barrier_ready,
            barrier_queue,
        ),
    )
    parent_pid = os.getpid()
    child_start_at = datetime.now(UTC).isoformat()
    child_start_monotonic = time.monotonic()
    process.start()
    if not startup_ready.wait(timeout=25):
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        raise RuntimeError("Case P child did not complete startup")
    startup = startup_queue.get(timeout=5)
    if startup["provisioning_transactions"] != 0:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        raise RuntimeError("measured child performed provisioning transactions")
    if not barrier_ready.wait(timeout=25):
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        raise RuntimeError("Case P child did not reach the exact P-ROOT barrier")
    barrier_report = barrier_queue.get(timeout=5)
    current_transaction = barrier_report["current_transaction"]
    exact_match = (
        barrier_report["barrier"]["matched_path"] == expected_path
        and current_transaction["exact_matched_path"] == expected_path
        and current_transaction["commit_attempted"] is False
    )
    if not exact_match:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        raise RuntimeError("Case P barrier did not match the exact P-ROOT transaction")

    kill_at = datetime.now(UTC).isoformat()
    recovery_started = time.monotonic()
    process.kill()
    process.join(timeout=10)

    recovered_raw = firestore.Client(project=project, database=database)
    recovery_telemetry = _TransactionTelemetry("recovery-parent")
    recovered_client = _P7Client(
        recovered_raw,
        prefix,
        counters,
        process_role="recovery-parent",
        telemetry=recovery_telemetry,
    )
    recovered_store = FirestoreAuthorityStore(recovered_client)
    records_before_retry = [item.record_id for item in recovered_store.records()]
    dependencies_before_retry = [
        item.canonical_bytes().hex() for item in recovered_store.dependencies("P-ROOT")
    ]
    events = p6._events()
    receipt_root_before_retry = recovered_store.root_record_id_for_receipt(
        events[0].receipt
    )
    partial_state_after_kill = bool(
        records_before_retry or dependencies_before_retry or receipt_root_before_retry
    )
    dispatcher = p6._Dispatcher()
    immediate = p6.AuthorityGateway(recovered_store).execute(
        p6._action("action-P-after-kill"), ("P-ROOT",), dispatcher
    )
    retry = p6._admit_source(_configured_world(recovered_store), 0, "P-ROOT")
    recovery_seconds = time.monotonic() - recovery_started
    verify_raw = firestore.Client(project=project, database=database)
    verify_client = _P7Client(
        verify_raw,
        prefix,
        _Counters(),
        process_role="recovery-verifier",
    )
    verify_store = FirestoreAuthorityStore(verify_client)
    final_ids = [item.record_id for item in verify_store.records()]
    final_dependencies = [
        item.canonical_bytes().hex() for item in verify_store.dependencies("P-ROOT")
    ]
    final_receipt_root = verify_store.root_record_id_for_receipt(events[0].receipt)
    final_policy = verify_store.policy(events[0].receipt.policy_key)
    recovery_attempts = recovery_telemetry.attempts()
    issuer_contention = any(
        "/authority_issuer_keys/" in path
        and (attempt["commit_result"] or "").startswith("failure:")
        for attempt in recovery_attempts
        for path in attempt["document_reads"] + attempt["document_creates"]
    )
    if hasattr(verify_raw, "close"):
        verify_raw.close()
    if hasattr(recovered_raw, "close"):
        recovered_raw.close()
    return {
        "setup": setup,
        "expected_p_root_path": expected_path,
        "parent_pid": parent_pid,
        "child_start_at": child_start_at,
        "child_start_monotonic": child_start_monotonic,
        "child_pid": process.pid,
        "startup": startup,
        "barrier_report": barrier_report,
        "kill_at": kill_at,
        "killed_exitcode": process.exitcode,
        "records_before_retry": records_before_retry,
        "dependencies_before_retry": dependencies_before_retry,
        "receipt_root_before_retry": receipt_root_before_retry,
        "partial_authoritative_state_after_kill": partial_state_after_kill,
        "immediate": p6._execution_observation(immediate),
        "dispatches": list(dispatcher.calls),
        "retry": p6._admission_observation(retry),
        "final_record_ids": final_ids,
        "final_dependencies": final_dependencies,
        "final_receipt_root": final_receipt_root,
        "final_policy_generation": (
            None if final_policy is None else final_policy.generation
        ),
        "duplicate_envelopes": len(final_ids) - len(set(final_ids)),
        "recovery_seconds": recovery_seconds,
        "recovery_completed_within_90_seconds": int(recovery_seconds <= RECOVERY_BOUND_SECONDS),
        "recovery_telemetry": recovery_telemetry.as_dict(),
        "issuer_key_contention_observed": issuer_contention,
        "recovery_repeated_provisioning": recovery_telemetry.has_provisioning_writes(),
        "backend": "firestore-killed-writer-real-process",
    }


def _run_firestore_killed_writer(
    raw: firestore.Client, counters: _Counters
) -> dict[str, object]:
    prefix = f"{NAMESPACE_PREFIX}__caseP"
    return _run_case_p_lifecycle(
        raw, DEFAULT_PROJECT, DEFAULT_DATABASE, prefix, counters
    )


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
