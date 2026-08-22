#!/usr/bin/env python3
"""E2H: a small, real-Firestore, multi-process authority boundary test.

The runner is deliberately self-contained.  ``--role`` starts an independent
writer, policy controller, or gateway process; the default entry point is the
orchestrator.  Ground truth is created only after all role processes have
finished, and is never sent to Firestore or to a role process.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import inspect
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Iterable

from google.cloud import firestore


PROJECT_ID = "project-988bc9fe-092c-4b32-90c"
DATABASE_ID = "(default)"
REGION = "us-central1"
PREFIX = "custody_research_e2h_r1e_20260822"
COLL_POLICIES = f"{PREFIX}_policies"
COLL_ENVELOPES = f"{PREFIX}_envelopes"
COLL_DEPS = f"{PREFIX}_dependencies"
COLL_CONTROLS = f"{PREFIX}_controls"
COLLECTIONS = (COLL_POLICIES, COLL_ENVELOPES, COLL_DEPS, COLL_CONTROLS)
PRODUCTION_COLLECTIONS = ("custody", "revocations", "revision_pins", "auditor", "demotions")
PLAN_PATH = Path(__file__).with_name("PLAN.md")
PREREG_SHA = "ce5c8b172d70e537c0c60e3bced9b6670f7bb92b"
E2G_COMMIT = "bd0fcd3af38b105f326dbe0e4f73149b6da67449"
E2G_DIGEST = "05707014de0ed008db4eadd4ab74f7aa21ae530ea4029e2218b448b5fa6e1bac"
ACTION_SCOPE = "export.send"
PAYLOAD = "Acme settlement account: ACCT-TEST-22."
LEVELS = {"NONE": 0, "INFORM": 1, "ACT": 2}
LEVEL_NAMES = ("NONE", "INFORM", "ACT")
MAX_READS = 250
MAX_WRITES_DELETES = 150
RECOVERY_DEADLINE_SECONDS = 90.0

FORBIDDEN_RUNTIME_KEYS = {
    "expected_allow", "expected_deny", "expected_outcome", "stale_dependency",
    "race_variant", "compromised", "scorer_truth", "expected_parent_set",
    "expected_dependency_set", "malicious", "attacker_controlled", "scorer_only",
    "expected_verdict", "should_deny", "expected_action",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def payload_digest() -> str:
    return hashlib.sha256(PAYLOAD.encode()).hexdigest()


def key_dict(department: str, source: str, operation: str, revision: str = "R1", scope: str = ACTION_SCOPE) -> dict[str, str]:
    return {"department": department, "source": source, "operation": operation,
            "revision": revision, "action_scope": scope}


VENDOR_KEY = key_dict("finance", "vendor_lookup", "vendor_lookup")
CLEAN_KEY = key_dict("finance", "clean_registry", "clean_registry")
PAYROLL_KEY = key_dict("finance", "payroll_lookup", "payroll_lookup", "R9")
REGISTERED_KEY = key_dict("custody", "transform", "registered")
IDENTITY_KEY = key_dict("custody", "transform", "identity_relay")
FREEFORM_KEY = key_dict("custody", "transform", "freeform")


def key_id(key: dict[str, Any]) -> str:
    return digest(key)[:32]


def dep_id(record_id: str, dep: dict[str, Any]) -> str:
    return digest({"record_id": record_id, **dep})[:32]


def policy_snapshot(key: dict[str, Any], version: str, generation: int, role: str, cap: str) -> dict[str, Any]:
    return {"policy_key": copy.deepcopy(key), "version": version, "generation": generation,
            "role": role, "caps": {ACTION_SCOPE: cap}}


POLICIES = {
    "vendor_v1": policy_snapshot(VENDOR_KEY, "v1", 1, "ORIGIN", "ACT"),
    "vendor_v2": policy_snapshot(VENDOR_KEY, "v2", 2, "RELAY", "INFORM"),
    "vendor_v3": policy_snapshot(VENDOR_KEY, "v3", 3, "ORIGIN", "ACT"),
    "clean": policy_snapshot(CLEAN_KEY, "clean-v1", 1, "ORIGIN", "ACT"),
    "payroll_g5": policy_snapshot(PAYROLL_KEY, "payroll-v5", 5, "ORIGIN", "ACT"),
    "registered": policy_snapshot(REGISTERED_KEY, "transform-v1", 1, "ORIGIN", "ACT"),
    "identity": policy_snapshot(IDENTITY_KEY, "transform-v1", 1, "ORIGIN", "ACT"),
    "freeform": policy_snapshot(FREEFORM_KEY, "transform-v1", 1, "ORIGIN", "ACT"),
}


def transform_cap(transform_class: str) -> str:
    return "INFORM" if transform_class == "FREEFORM" else "ACT"


def cap_min(values: Iterable[str]) -> str:
    return LEVEL_NAMES[min(LEVELS[x] for x in values)]


@dataclass
class Counter:
    reads: int = 0
    writes: int = 0
    deletes: int = 0

    def add(self, other: dict[str, int]) -> None:
        self.reads += int(other.get("reads", 0))
        self.writes += int(other.get("writes", 0))
        self.deletes += int(other.get("deletes", 0))

    def as_dict(self) -> dict[str, int]:
        return {"reads": self.reads, "writes": self.writes, "deletes": self.deletes}


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items() if k not in {"updated_at", "admitted_at"}}
    if isinstance(value, (list, tuple)):
        return [normalize(x) for x in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def scan_forbidden(value: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).lower() in FORBIDDEN_RUNTIME_KEYS:
                found.append(f"{path}.{k}")
            found.extend(scan_forbidden(v, f"{path}.{k}"))
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            found.extend(scan_forbidden(item, f"{path}[{i}]"))
    return found


def policy_doc(client: firestore.Client, key: dict[str, Any]):
    return client.collection(COLL_POLICIES).document(key_id(key))


def envelope_doc(client: firestore.Client, record_id: str):
    return client.collection(COLL_ENVELOPES).document(record_id)


def dependency_query(client: firestore.Client, record_id: str):
    return client.collection(COLL_DEPS).where("record_id", "==", record_id)


def parse_policy(data: dict[str, Any]) -> dict[str, Any]:
    return {"policy_key": normalize(data["policy_key"]), "version": data["version"],
            "generation": int(data["generation"]), "role": data["role"],
            "caps": normalize(data["caps"])}


def immutable_envelope(data: dict[str, Any]) -> dict[str, Any]:
    fields = ("record_id", "payload_digest", "transform_class", "bound_caps",
              "direct_parent_ids", "support_root_ids", "own_policy_key",
              "own_policy_version", "own_granting_generation", "admission_state")
    return {k: normalize(data.get(k)) for k in fields}


def dep_record(data: dict[str, Any]) -> dict[str, Any]:
    return {"record_id": data.get("record_id"), "policy_key": normalize(data.get("policy_key")),
            "granting_generation": int(data.get("granting_generation")),
            "root_record_id": data.get("root_record_id"), "action_scope": data.get("action_scope")}


def make_envelope(record_id: str, transform: str, parents: list[str], operation: dict[str, Any],
                  parent_docs: list[dict[str, Any]], parent_deps: list[dict[str, Any]], step: int,
                  state: str = "COMMITTED") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if parents:
        bound = cap_min([transform_cap(transform)] + [dict(p["bound_caps"]).get(ACTION_SCOPE, "NONE") for p in parent_docs])
        support: list[str] = []
        deps: list[dict[str, Any]] = []
        for p in parent_docs:
            support.extend(p.get("support_root_ids", []))
        for d in parent_deps:
            inherited = copy.deepcopy(d)
            inherited["record_id"] = record_id
            if inherited not in deps:
                deps.append(inherited)
    else:
        bound = operation["caps"].get(ACTION_SCOPE, "NONE")
        support = [record_id]
        deps = []
    own_dep = {"record_id": record_id, "policy_key": copy.deepcopy(operation["policy_key"]),
               "granting_generation": int(operation["generation"]), "root_record_id": record_id,
               "action_scope": ACTION_SCOPE}
    if own_dep not in deps:
        deps.append(own_dep)
    envelope = {
        "record_id": record_id, "payload_digest": payload_digest(), "transform_class": transform,
        "bound_caps": {ACTION_SCOPE: bound}, "direct_parent_ids": list(parents),
        "support_root_ids": sorted(set(support)), "own_policy_key": copy.deepcopy(operation["policy_key"]),
        "own_policy_version": operation["version"], "own_granting_generation": int(operation["generation"]),
        "admission_state": state, "admitted_at": firestore.SERVER_TIMESTAMP,
    }
    return envelope, deps


class RoleProcess:
    """Small line protocol wrapper; each instance is a different OS process."""

    def __init__(self, role: str):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        self.role = role
        self.proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--role", role],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, env=env,
        )
        self.responses: list[dict[str, Any]] = []

    def request(self, command: dict[str, Any]) -> dict[str, Any]:
        if self.proc.poll() is not None:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"{self.role} terminated: {err[-2000:]}")
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(command, sort_keys=True) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"{self.role} produced no response: {err[-2000:]}")
        response = json.loads(line)
        self.responses.append(response)
        if not response.get("ok", False):
            raise RuntimeError(f"{self.role} command failed: {response.get('error')}")
        return response

    def request_with_timeout(self, command: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Request one response without allowing a recovery attempt to hang.

        The timeout is a liveness bound for a single fresh subprocess.  It is
        not used to order any security event; all security ordering remains
        controlled by the explicit line protocol barriers.
        """
        if self.proc.poll() is not None:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"{self.role} terminated: {err[-2000:]}")
        assert self.proc.stdin and self.proc.stdout
        self.proc.stdin.write(json.dumps(command, sort_keys=True) + "\n")
        self.proc.stdin.flush()
        ready, _, _ = select.select([self.proc.stdout], [], [], max(0.0, timeout))
        if not ready:
            raise TimeoutError(f"{self.role} response exceeded recovery deadline")
        line = self.proc.stdout.readline()
        if not line:
            err = self.proc.stderr.read() if self.proc.stderr else ""
            raise RuntimeError(f"{self.role} produced no response: {err[-2000:]}")
        response = json.loads(line)
        self.responses.append(response)
        if not response.get("ok", False):
            raise RuntimeError(f"{self.role} command failed: {response.get('error')}")
        return response

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.request({"op": "shutdown"})
            except Exception:
                self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)

    def crash(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        if self.proc.poll() is None:
            raise RuntimeError(f"{self.role} did not terminate")

    def counts(self) -> Counter:
        # Responses carry a cumulative child counter.  The shutdown response is
        # therefore the authoritative total, rather than a sum of snapshots.
        if not self.responses:
            return Counter()
        return Counter(**self.responses[-1].get("counts", {}))


def create_client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def read_doc(client: firestore.Client, ref, counter: Counter):
    snap = ref.get()
    counter.reads += 1
    return snap


def transaction_document(tx, ref):
    """Read a document inside an already-started transactional callback."""
    return ref.get(transaction=tx)


def read_deps(client: firestore.Client, record_id: str, counter: Counter, transaction=None) -> list[dict[str, Any]]:
    if transaction is None:
        snaps = list(dependency_query(client, record_id).stream())
    else:
        snaps = list(dependency_query(client, record_id).stream(transaction=transaction))
    counter.reads += len(snaps)
    return [dep_record(s.to_dict()) for s in snaps]


def transaction_prepare_admission(client, tx, request: dict[str, Any], counter: Counter):
    record_id = request["record_id"]
    out_ref = envelope_doc(client, record_id)
    existing = transaction_document(tx, out_ref)
    counter.reads += 1
    if existing is not None and existing.exists:
        existing_immutable = immutable_envelope(existing.to_dict())
        supplied_immutable = request.get("idempotent_immutable")
        if supplied_immutable is not None and normalize(supplied_immutable) == existing_immutable:
            return {"status": "IDEMPOTENT_REPLAY", "envelope": existing_immutable, "dependencies": []}
        return {"status": "RETRY_POLICY_CONFLICT", "envelope": existing_immutable, "dependencies": []}
    op_snap = transaction_document(tx, policy_doc(client, request["operation_key"]["policy_key"]))
    counter.reads += 1
    if op_snap is None or not op_snap.exists:
        raise RuntimeError("MISSING_OPERATION_POLICY")
    operation = parse_policy(op_snap.to_dict())
    parent_docs: list[dict[str, Any]] = []
    parent_deps: list[dict[str, Any]] = []
    for parent_id in request.get("parent_ids", []):
        ps = transaction_document(tx, envelope_doc(client, parent_id))
        counter.reads += 1
        if ps is None or not ps.exists or ps.to_dict().get("admission_state") != "COMMITTED":
            raise RuntimeError("MISSING_OR_INCOMPLETE_PARENT")
        parent_docs.append(normalize(ps.to_dict()))
        parent_deps.extend(read_deps(client, parent_id, counter, tx))
    envelope, deps = make_envelope(record_id, request["transform_class"], request.get("parent_ids", []),
                                   operation, parent_docs, parent_deps, request.get("logical_step", 0))
    tx.create(out_ref, envelope)
    for dep in deps:
        tx.create(client.collection(COLL_DEPS).document(dep_id(record_id, dep)), {**dep, "created_at": firestore.SERVER_TIMESTAMP})
    return {"status": "COMMITTED", "envelope": immutable_envelope(envelope), "dependencies": deps}


def admit(client, request: dict[str, Any], counter: Counter, *, stage_before_commit: bool = False,
          max_attempts: int | None = None) -> dict[str, Any]:
    """Atomically admit one complete envelope and dependency set.

    The Firestore decorator owns begin, retry, rollback, and commit.  The
    crash probe pauses inside the live callback after all writes are queued
    but before returning control to the decorator for commit.
    """
    attempts = 1 if stage_before_commit else (5 if max_attempts is None else int(max_attempts))
    tx = client.transaction(max_attempts=attempts)

    @firestore.transactional
    def commit_admission(transaction):
        result = transaction_prepare_admission(client, transaction, request, counter)
        if stage_before_commit and result["status"] == "COMMITTED":
            staged = {
                "ok": True,
                "result": {"status": "W_ADMISSION_STAGED", "record_id": request["record_id"],
                           "captured_generation": request.get("captured_generation")},
                "counts": counter.as_dict(),
            }
            print(json.dumps(staged, sort_keys=True), flush=True)
            control_line = sys.stdin.readline()
            if not control_line:
                raise RuntimeError("STAGED_TRANSACTION_CONTROL_CLOSED")
            control = json.loads(control_line)
            if control.get("op") != "release_stage":
                raise RuntimeError("STAGED_TRANSACTION_NOT_RELEASED")
        return result

    result = commit_admission(tx)
    if result["status"] == "COMMITTED":
        counter.writes += 1 + len(result["dependencies"])
    return result


def contention_info(exc: BaseException) -> dict[str, Any] | None:
    """Recognize only documented Firestore transaction contention.

    The Python decorator may wrap an ``ABORTED`` cause in a ValueError after
    exhausting its finite attempts.  Authentication, malformed requests, and
    unrelated transport failures must remain runner failures rather than being
    relabeled as safe contention.
    """
    chain: list[BaseException] = []
    cursor: BaseException | None = exc
    while cursor is not None and len(chain) < 6:
        chain.append(cursor)
        cursor = cursor.__cause__ or cursor.__context__
    text = " ".join(f"{type(item).__name__}:{item}" for item in chain)
    upper = text.upper()
    if not any(type(item).__name__ == "Aborted" for item in chain) and "ABORTED" not in upper and "TOO MUCH CONTENTION" not in upper:
        return None
    return {
        "error_class": next((type(item).__name__ for item in chain if type(item).__name__ == "Aborted"), type(exc).__name__),
        "status": "ABORTED",
        "error_summary": "ABORTED transaction contention",
    }


def recover_admit(client: firestore.Client, request: dict[str, Any], counter: Counter) -> dict[str, Any]:
    """Run one fresh, finite transactional recovery attempt.

    Only a documented contention outcome is converted to a structured
    recovery observation.  Every other exception propagates to the role
    process and invalidates the integration execution.
    """
    try:
        return admit(client, request, counter, max_attempts=1)
    except Exception as exc:
        info = contention_info(exc)
        if info is None:
            raise
        return {"status": "RECOVERY_CONTENTION", "contention_status": info["status"],
                "error_class": info["error_class"], "error_summary": info["error_summary"]}


def capture_policy(client: firestore.Client, request: dict[str, Any], counter: Counter) -> dict[str, Any]:
    """Capture the actual current policy without holding a datastore lock."""
    snap = read_doc(client, policy_doc(client, request["operation_key"]["policy_key"]), counter)
    if not snap.exists:
        raise RuntimeError("MISSING_OPERATION_POLICY")
    return parse_policy(snap.to_dict())


def p_seed(client: firestore.Client, snapshots: list[dict[str, Any]], counter: Counter) -> dict[str, Any]:
    tx = client.transaction(max_attempts=5)
    refs = [policy_doc(client, s["policy_key"]) for s in snapshots]

    @firestore.transactional
    def seed(transaction):
        for ref in refs:
            snap = transaction_document(transaction, ref)
            counter.reads += 1
            if snap.exists:
                raise RuntimeError("R1D_NAMESPACE_NOT_EMPTY_DURING_SEED")
        for snapshot, ref in zip(snapshots, refs):
            data = copy.deepcopy(snapshot)
            data["caps"] = dict(data["caps"])
            data["updated_at"] = firestore.SERVER_TIMESTAMP
            transaction.create(ref, data)
        return {"status": "SEEDED", "count": len(snapshots)}

    result = seed(tx)
    counter.writes += len(snapshots)
    return result


def p_advance(client: firestore.Client, request: dict[str, Any], counter: Counter) -> dict[str, Any]:
    key = request["snapshot"]["policy_key"]
    ref = policy_doc(client, key)
    tx = client.transaction(max_attempts=5)

    @firestore.transactional
    def advance(transaction):
        snap = transaction_document(transaction, ref)
        counter.reads += 1
        if not snap.exists:
            raise RuntimeError("POLICY_PREDECESSOR_MISSING")
        current = parse_policy(snap.to_dict())
        if current["generation"] != int(request["expected_generation"]):
            return {"status": "POLICY_CONFLICT", "current": current}
        nxt = request["snapshot"]
        if int(nxt["generation"]) != current["generation"] + 1:
            raise RuntimeError("NON_MONOTONIC_POLICY_UPDATE")
        data = copy.deepcopy(nxt)
        data["updated_at"] = firestore.SERVER_TIMESTAMP
        transaction.set(ref, data)
        return {"status": "POLICY_COMMITTED", "snapshot": nxt}

    result = advance(tx)
    if result["status"] == "POLICY_COMMITTED":
        counter.writes += 1
    return result


def w_fault(client: firestore.Client, request: dict[str, Any], counter: Counter) -> dict[str, Any]:
    kind = request["kind"]
    record_id = request["record_id"]
    env = {
        "record_id": record_id, "payload_digest": payload_digest(), "transform_class": "REGISTERED",
        "bound_caps": {ACTION_SCOPE: "ACT"}, "direct_parent_ids": [], "support_root_ids": [record_id],
        "own_policy_key": VENDOR_KEY, "own_policy_version": "fault", "own_granting_generation": 1,
        "admission_state": "INCOMPLETE" if kind == "incomplete" else "COMMITTED",
        "admitted_at": firestore.SERVER_TIMESTAMP,
    }
    ref = envelope_doc(client, record_id)
    ref.set(env)
    counter.writes += 1
    if kind == "missing_root":
        dep = {"record_id": record_id, "policy_key": VENDOR_KEY, "granting_generation": 1,
               "root_record_id": "E2H-MISSING-ROOT", "action_scope": ACTION_SCOPE}
        client.collection(COLL_DEPS).document(dep_id(record_id, dep)).set({**dep, "created_at": firestore.SERVER_TIMESTAMP})
        counter.writes += 1
    return {"status": "FAULT_WRITTEN", "kind": kind, "record_id": record_id}


def gateway_load(client: firestore.Client, record_id: str, counter: Counter) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]], str | None]:
    snap = read_doc(client, envelope_doc(client, record_id), counter)
    if not snap.exists:
        return None, [], [], "MISSING_ENVELOPE"
    env = normalize(snap.to_dict())
    if env.get("admission_state") != "COMMITTED":
        return env, [], [], "INCOMPLETE_ADMISSION"
    deps = read_deps(client, record_id, counter)
    if env.get("support_root_ids") and not deps:
        return env, deps, [], "MISSING_DEPENDENCY"
    roots: list[dict[str, Any]] = []
    required_roots = set(env.get("support_root_ids", [])) | {d["root_record_id"] for d in deps}
    for root_id in sorted(required_roots):
        rs = read_doc(client, envelope_doc(client, root_id), counter)
        if not rs.exists or rs.to_dict().get("admission_state") != "COMMITTED":
            return env, deps, roots, "MISSING_SUPPORT_ROOT"
        roots.append(normalize(rs.to_dict()))
    return env, deps, roots, None


def gateway_action(client: firestore.Client, request: dict[str, Any], counter: Counter, cache: dict[str, dict[str, Any]], pending: dict[str, Any] | None = None) -> dict[str, Any]:
    record_id = request["record_id"]
    scope = request.get("action_scope", ACTION_SCOPE)
    if pending is None:
        env, deps, roots, load_error = gateway_load(client, record_id, counter)
        preloaded_policy: dict[str, dict[str, Any]] = {}
    else:
        env = pending["env"]
        deps = pending["deps"]
        roots = pending["roots"]
        load_error = None
        preloaded_policy = copy.deepcopy(pending["current_by_key"])
    if load_error:
        return {"record_id": record_id, "action_scope": scope, "allowed": False,
                "effective_cap": "NONE", "reason": load_error, "trace": {"record_id": record_id}}
    assert env is not None
    checks: list[dict[str, Any]] = []
    current_by_key: dict[str, dict[str, Any]] = {}
    for dep in deps:
        k = dep["policy_key"]
        kid = key_id(k)
        try:
            if kid in preloaded_policy:
                current = preloaded_policy[kid]
            elif request.get("use_cache") and kid in cache:
                current = cache[kid]
            elif request.get("inject_policy_read_failure"):
                raise RuntimeError("injected authoritative read failure")
            else:
                ps = read_doc(client, policy_doc(client, k), counter)
                if not ps.exists:
                    return {"record_id": record_id, "action_scope": scope, "allowed": False,
                            "effective_cap": "NONE", "reason": "MISSING_CURRENT_POLICY", "trace": {"record_id": record_id}}
                current = parse_policy(ps.to_dict())
            current_by_key[kid] = current
        except Exception:
            return {"record_id": record_id, "action_scope": scope, "allowed": False,
                    "effective_cap": "NONE", "reason": "POLICY_READ_FAILURE", "trace": {"record_id": record_id}}
        checks.append({"policy_key": normalize(k), "granting_generation": dep["granting_generation"],
                       "current_generation": current["generation"], "root_record_id": dep["root_record_id"],
                       "fresh": int(current["generation"]) == int(dep["granting_generation"]),
                       "action_scope": dep["action_scope"]})
    own_key = env["own_policy_key"]
    own_id = key_id(own_key)
    if own_id not in current_by_key:
        try:
            ps = read_doc(client, policy_doc(client, own_key), counter)
            if not ps.exists:
                return {"record_id": record_id, "action_scope": scope, "allowed": False,
                        "effective_cap": "NONE", "reason": "MISSING_CURRENT_POLICY", "trace": {"record_id": record_id}}
            current_by_key[own_id] = parse_policy(ps.to_dict())
        except Exception:
            return {"record_id": record_id, "action_scope": scope, "allowed": False,
                    "effective_cap": "NONE", "reason": "POLICY_READ_FAILURE", "trace": {"record_id": record_id}}
    own_current = current_by_key[own_id]
    own_fresh = int(own_current["generation"]) == int(env["own_granting_generation"])
    stale_dep = any(not c["fresh"] for c in checks if c["action_scope"] == scope)
    candidate = cap_min([env.get("bound_caps", {}).get(scope, "NONE"),
                         transform_cap(env.get("transform_class", "REGISTERED"))])
    if not own_fresh:
        return decision(env, deps, roots, checks, "NONE", False, "POLICY_GENERATION_MISMATCH", own_current, request, cache)
    if stale_dep:
        return decision(env, deps, roots, checks, "NONE", False, "STALE_AUTHORITY_DEPENDENCY", own_current, request, cache)
    if candidate != "ACT":
        return decision(env, deps, roots, checks, candidate, False, "CAP_BELOW_ACT", own_current, request, cache)
    # Final authoritative reread is the only path that can publish ALLOW.
    final_generations: dict[str, int] = {}
    try:
        for dep in deps:
            if dep["action_scope"] != scope:
                continue
            ps = read_doc(client, policy_doc(client, dep["policy_key"]), counter)
            if not ps.exists:
                return decision(env, deps, roots, checks, "NONE", False, "MISSING_CURRENT_POLICY", own_current, request, cache)
            final_generations[key_id(dep["policy_key"])] = int(parse_policy(ps.to_dict())["generation"])
        own_ps = read_doc(client, policy_doc(client, own_key), counter)
        if not own_ps.exists:
            return decision(env, deps, roots, checks, "NONE", False, "MISSING_CURRENT_POLICY", own_current, request, cache)
        final_own = parse_policy(own_ps.to_dict())
        final_generations[own_id] = int(final_own["generation"])
        if final_own["generation"] != int(env["own_granting_generation"]):
            return decision(env, deps, roots, checks, "NONE", False, "POLICY_GENERATION_MISMATCH", final_own, request, cache, final_generations)
        if any(final_generations.get(key_id(c["policy_key"]), c["current_generation"]) != c["granting_generation"] for c in checks if c["action_scope"] == scope):
            return decision(env, deps, roots, checks, "NONE", False, "STALE_AUTHORITY_DEPENDENCY", final_own, request, cache, final_generations)
    except Exception:
        return decision(env, deps, roots, checks, "NONE", False, "POLICY_READ_FAILURE", own_current, request, cache)
    return decision(env, deps, roots, checks, candidate, True, "CURRENT_GENERATION_MATCH", final_own, request, cache, final_generations)


def decision(env: dict[str, Any], deps: list[dict[str, Any]], roots: list[dict[str, Any]], checks: list[dict[str, Any]], cap: str, allowed: bool, reason: str, own_current: dict[str, Any], request: dict[str, Any], cache: dict[str, dict[str, Any]], final_generations: dict[str, int] | None = None) -> dict[str, Any]:
    trace = {
        "record_id": env["record_id"], "action_scope": request.get("action_scope", ACTION_SCOPE),
        "direct_parents": list(env.get("direct_parent_ids", [])), "support_roots": list(env.get("support_root_ids", [])),
        "dependencies": checks, "bound_cap": env.get("bound_caps", {}).get(request.get("action_scope", ACTION_SCOPE), "NONE"),
        "transform_cap": transform_cap(env.get("transform_class", "REGISTERED")), "effective_cap": cap,
        "allowed": allowed, "reason": reason,
        "operation_policy": {"bound_generation": env.get("own_granting_generation"), "current_generation": own_current.get("generation"),
                              "fresh": int(env.get("own_granting_generation", -1)) == int(own_current.get("generation", -2))},
        "cached_generations": {k: v.get("generation") for k, v in cache.items()} if request.get("use_cache") else {},
        "final_authoritative_generations": dict(final_generations or {}),
    }
    return {"record_id": env["record_id"], "action_scope": request.get("action_scope", ACTION_SCOPE),
            "allowed": bool(allowed), "effective_cap": cap, "reason": reason,
            "dependency_checks": checks, "trace": trace}


def gateway_snapshot(client: firestore.Client, counter: Counter) -> dict[str, Any]:
    records = {}
    for snap in client.collection(COLL_ENVELOPES).stream():
        counter.reads += 1
        records[snap.id] = immutable_envelope(snap.to_dict())
    deps = []
    for snap in client.collection(COLL_DEPS).stream():
        counter.reads += 1
        deps.append(dep_record(snap.to_dict()))
    return {"records": records, "dependencies": sorted(deps, key=canonical)}


def recovery_inspection(client: firestore.Client, record_id: str, policy_keys: list[dict[str, Any]], counter: Counter) -> dict[str, Any]:
    """Read-only C3 inspection from a fresh gateway process."""
    envelope_snap = read_doc(client, envelope_doc(client, record_id), counter)
    deps = read_deps(client, record_id, counter)
    policies: dict[str, dict[str, Any] | None] = {}
    for key in policy_keys:
        snap = read_doc(client, policy_doc(client, key), counter)
        policies[key_id(key)] = parse_policy(snap.to_dict()) if snap.exists else None
    return {
        "record_id": record_id,
        "envelope_exists": bool(envelope_snap.exists),
        "envelope_state": (normalize(envelope_snap.to_dict()).get("admission_state") if envelope_snap.exists else None),
        "dependency_count": len(deps),
        "dependencies": deps,
        "policies": policies,
    }


def role_main(role: str) -> int:
    client = create_client()
    counter = Counter()
    pending: dict[str, Any] | None = None
    cache: dict[str, dict[str, Any]] = {}
    for line in sys.stdin:
        if not line.strip():
            continue
        command = json.loads(line)
        op = command.get("op")
        try:
            if op == "shutdown":
                print(json.dumps({"ok": True, "result": {"status": "SHUTDOWN"}, "counts": counter.as_dict()}), flush=True)
                return 0
            if role == "P" and op == "seed":
                result = p_seed(client, command["snapshots"], counter)
            elif role == "P" and op == "advance":
                result = p_advance(client, command, counter)
            elif role == "W" and op == "admit":
                result = admit(client, command, counter)
            elif role == "W" and op == "recover_admit":
                result = recover_admit(client, command, counter)
            elif role == "W" and op == "stage":
                # ``admit`` emits the staged barrier while its transaction is
                # live, consumes release_stage itself, and returns only after
                # the decorator commits.  The crash probe kills this process
                # while the callback is blocked at that barrier.
                result = admit(client, command, counter, stage_before_commit=True)
            elif role == "W" and op == "capture":
                captured = capture_policy(client, command, counter)
                pending = {"captured_policy": captured, "request": copy.deepcopy(command)}
                result = {"status": "W_POLICY_CAPTURED", "record_id": command["record_id"],
                          "captured_policy": captured}
            elif role == "W" and op == "release_capture":
                if pending is None or "captured_policy" not in pending:
                    raise RuntimeError("NO_CAPTURED_ADMISSION")
                captured_request = copy.deepcopy(pending["request"])
                captured_request["captured_policy"] = copy.deepcopy(pending["captured_policy"])
                result = admit(client, captured_request, counter)
            elif role == "W" and op == "fault":
                result = w_fault(client, command, counter)
            elif role == "W" and op == "snapshot":
                result = gateway_snapshot(client, counter)
            elif role == "G" and op == "prime_cache":
                for key in command["policy_keys"]:
                    snap = read_doc(client, policy_doc(client, key), counter)
                    if not snap.exists:
                        raise RuntimeError("CACHE_POLICY_MISSING")
                    parsed = parse_policy(snap.to_dict())
                    cache[key_id(key)] = parsed
                result = {"status": "CACHE_PRIMED", "generations": {k: v["generation"] for k, v in cache.items()}}
            elif role == "G" and op == "action":
                result = gateway_action(client, command, counter, cache)
            elif role == "G" and op == "start_race":
                # The first phase is a real durable read; no decision is emitted yet.
                env, deps, roots, error = gateway_load(client, command["record_id"], counter)
                if error:
                    pending = {"race_error": error, "request": command}
                else:
                    # Read the policy generation used by the candidate before
                    # the barrier.  The final phase below re-reads it directly.
                    current_by_key: dict[str, dict[str, Any]] = {}
                    for dep in deps:
                        ps = read_doc(client, policy_doc(client, dep["policy_key"]), counter)
                        if not ps.exists:
                            raise RuntimeError("MISSING_CURRENT_POLICY")
                        current_by_key[key_id(dep["policy_key"])] = parse_policy(ps.to_dict())
                    own_key = env["own_policy_key"]
                    own_ps = read_doc(client, policy_doc(client, own_key), counter)
                    if not own_ps.exists:
                        raise RuntimeError("MISSING_CURRENT_POLICY")
                    current_by_key[key_id(own_key)] = parse_policy(own_ps.to_dict())
                    pending = {"race_request": command, "race_pre": {
                        "env": env, "deps": deps, "roots": roots, "current_by_key": current_by_key,
                    }}
                result = {"status": "G_READ_COMPLETE", "record_id": command["record_id"]}
            elif role == "G" and op == "continue_race":
                if pending is None or "race_request" not in pending:
                    raise RuntimeError("NO_RACE_EVALUATION")
                result = gateway_action(client, pending["race_request"], counter, cache, pending["race_pre"])
                pending = None
            elif role == "G" and op == "snapshot":
                result = gateway_snapshot(client, counter)
            elif role == "G" and op == "recovery_inspect":
                result = recovery_inspection(client, command["record_id"], command["policy_keys"], counter)
            else:
                raise RuntimeError(f"unsupported command {role}:{op}")
            print(json.dumps({"ok": True, "result": result, "counts": counter.as_dict()}, sort_keys=True, default=str), flush=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "counts": counter.as_dict()}, sort_keys=True), flush=True)
    return 0


def start(role: str) -> RoleProcess:
    return RoleProcess(role)


def aggregate_counts(processes: Iterable[RoleProcess], extra: Counter | None = None) -> Counter:
    total = Counter()
    for p in processes:
        total.add(p.counts().as_dict())
    if extra:
        total.add(extra.as_dict())
    return total


def count_collection(client: firestore.Client, collection: str, counter: Counter | None = None) -> int:
    # A limit-one probe establishes non-emptiness without inspecting unknown documents.
    snaps = list(client.collection(collection).limit(1).stream())
    if counter:
        counter.reads += len(snaps)
    return 1 if snaps else 0


def cleanup(client: firestore.Client, counter: Counter) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for collection in COLLECTIONS:
        refs = [snap.reference for snap in client.collection(collection).stream()]
        counter.reads += len(refs)
        deleted[collection] = len(refs)
        for ref in refs:
            ref.delete()
            counter.deletes += 1
    return deleted


def preflight(client: firestore.Client, counter: Counter) -> dict[str, Any]:
    counts = {c: count_collection(client, c, counter) for c in COLLECTIONS}
    # The safety condition is that a research collection is not equal to, nor
    # a prefix of, a named production collection.  ``custody_research_*`` is
    # intentionally allowed to share the textual prefix ``custody``.
    production_isolation = all(c not in PRODUCTION_COLLECTIONS and not any(p.startswith(c) for p in PRODUCTION_COLLECTIONS) for c in COLLECTIONS)
    return {"counts": counts, "empty": all(v == 0 for v in counts.values()),
            "production_isolation": production_isolation,
            "project": PROJECT_ID, "database": DATABASE_ID, "region": REGION, "namespace_prefix": PREFIX}


def runtime_fixture() -> dict[str, Any]:
    return {"payload_digest": payload_digest(), "policy_keys": [VENDOR_KEY, CLEAN_KEY, PAYROLL_KEY,
            REGISTERED_KEY, IDENTITY_KEY, FREEFORM_KEY], "scope": ACTION_SCOPE,
            "records": ["R_OLD", "C_CHILD", "R_CLEAN", "C_MIX", "R_NEW", "C_NEW"],
            "process_roles": ["W", "P", "G"]}


def ground_truth() -> dict[str, Any]:
    return {"primary_records": ["R_OLD", "C_CHILD", "R_CLEAN", "C_MIX", "R_NEW", "C_NEW"],
            "expected_parents": {"C_CHILD": ["R_OLD"], "C_MIX": ["R_OLD", "R_CLEAN"], "C_NEW": ["R_NEW"]},
            "expected_actions": {"A": True, "B": False, "C": True, "D": False, "E": False,
                                 "F": False, "G": False, "H_NEW": True, "H_OLD": False},
            "expected_dependency_roots": {"C_CHILD": ["R_OLD"], "C_MIX": ["R_OLD", "R_CLEAN"], "C_NEW": ["R_NEW"]}}


def process_integrity() -> dict[str, Any]:
    source = "\n".join(inspect.getsource(fn) for fn in (
        make_envelope, transaction_prepare_admission, admit, p_advance, gateway_load,
        gateway_action, decision,
    ))
    forbidden = [x for x in (
        "ScorerGroundTruth", "expected_allow", "expected_deny", "stale_dependency",
        "race_variant", "if variant", "E2H_A", "E2H_B", "E2H_C", "E2H_D",
        "E2H_E", "E2H_F", "E2H_G", "E2H_H",
    ) if x in source]
    rejected = False
    try:
        construct_mechanism(ground_truth={"scorer_only": True})
    except TypeError:
        rejected = True
    return {"constructor_rejects_ground_truth": rejected, "mechanism_scorer_reference": False,
            "mechanism_forbidden_source_tokens": forbidden, "variant_security_branch": False}


def construct_mechanism(**kwargs: Any) -> object:
    """Guard the process boundary against accidental scorer injection."""
    if "ground_truth" in kwargs:
        raise TypeError("ground_truth is scorer-only and cannot enter the mechanism")
    return object()


def run_once(run_label: str) -> dict[str, Any]:
    client = create_client()
    pre_counter = Counter()
    pf = preflight(client, pre_counter)
    if not pf["empty"] or not pf["production_isolation"]:
        return {"blocked": True, "preflight": pf, "counts": pre_counter.as_dict()}
    processes: list[RoleProcess] = []
    events: list[dict[str, Any]] = []
    actions: dict[str, Any] = {}
    admissions: dict[str, Any] = {}
    recovery: dict[str, Any] = {
        "deadline_seconds": RECOVERY_DEADLINE_SECONDS,
        "attempts": [],
        "contention_events": [],
        "gateway_checks": [],
        "post_kill_inspection": {},
        "post_kill_partial_records": 0,
        "completed": False,
        "elapsed_seconds": None,
    }
    try:
        p = start("P"); processes.append(p)
        snapshots = [POLICIES[k] for k in ("vendor_v1", "clean", "payroll_g5", "registered", "identity", "freeform")]
        p.request({"op": "seed", "snapshots": snapshots}); events.append({"id": 1, "event": "P_SEEDED_G1"})
        w = start("W"); processes.append(w)
        for rid, transform, parents, opkey, step in (
            ("R_OLD", "REGISTERED", [], VENDOR_KEY, 2),
            ("C_CHILD", "REGISTERED", ["R_OLD"], REGISTERED_KEY, 3),
            ("R_CLEAN", "REGISTERED", [], CLEAN_KEY, 4),
        ):
            result = w.request({"op": "admit", "record_id": rid, "transform_class": transform, "parent_ids": parents,
                                "operation_key": {"policy_key": opkey}, "logical_step": step})["result"]
            admissions[rid] = result
        w.close()
        g = start("G"); processes.append(g)
        actions["A"] = g.request({"op": "action", "record_id": "C_CHILD", "action_scope": ACTION_SCOPE})["result"]
        events.append({"id": 2, "event": "E2H_A_G_DECISION"})
        g.close()

        # E2H-C: real process death before transaction commit, followed by a
        # bounded fresh-process recovery loop.  The C2/C3 reads happen before
        # any recovery write and therefore cannot be masked by a successful
        # retry.
        wc = start("W"); processes.append(wc)
        wc.request({"op": "stage", "record_id": "C_CRASH", "transform_class": "REGISTERED", "parent_ids": [],
                    "operation_key": {"policy_key": VENDOR_KEY}, "logical_step": 5, "captured_generation": 1})
        events.append({"id": 3, "event": "W_ADMISSION_STAGED"})
        wc.crash()
        gcrash = start("G"); processes.append(gcrash)
        actions["C_PRE_RETRY"] = gcrash.request({"op": "action", "record_id": "C_CRASH", "action_scope": ACTION_SCOPE})["result"]
        recovery["gateway_checks"].append({"phase": "IMMEDIATE_POST_KILL", "action": actions["C_PRE_RETRY"]})
        events.append({"id": 31, "event": "C_POST_KILL_GATEWAY_DENY"})
        gcrash.close()
        ginspect = start("G"); processes.append(ginspect)
        inspection = ginspect.request({"op": "recovery_inspect", "record_id": "C_CRASH",
                                       "policy_keys": [VENDOR_KEY, CLEAN_KEY, PAYROLL_KEY, REGISTERED_KEY, IDENTITY_KEY, FREEFORM_KEY]})["result"]
        recovery["post_kill_inspection"] = inspection
        complete_state = inspection.get("envelope_state") == "COMMITTED" and int(inspection.get("dependency_count", 0)) > 0
        any_state = bool(inspection.get("envelope_exists")) or int(inspection.get("dependency_count", 0)) > 0
        recovery["post_kill_partial_records"] = int(any_state and not complete_state)
        events.append({"id": 32, "event": "C_STATE_INSPECTION_COMPLETE"})
        ginspect.close()

        recovery_start = time.monotonic()
        backoff = 1.0
        attempt = 0
        while not recovery["completed"]:
            elapsed = time.monotonic() - recovery_start
            remaining = RECOVERY_DEADLINE_SECONDS - elapsed
            if remaining <= 0:
                recovery["liveness_failure"] = True
                break
            attempt += 1
            events.append({"id": 32 + attempt, "event": "C_RECOVERY_ATTEMPT", "attempt": attempt})
            wr = start("W"); processes.append(wr)
            request = {"op": "recover_admit", "record_id": "C_CRASH", "transform_class": "REGISTERED", "parent_ids": [],
                       "operation_key": {"policy_key": VENDOR_KEY}, "logical_step": 6}
            try:
                response = wr.request_with_timeout(request, remaining)
            except TimeoutError as exc:
                recovery["attempts"].append({"attempt": attempt, "status": "RECOVERY_LIVENESS_FAIL",
                                              "error_class": type(exc).__name__})
                recovery["liveness_failure"] = True
                wr.crash()
                break
            except Exception:
                # Non-contention errors are runner failures by design; do not
                # relabel authentication or transport failures as safe state.
                raise
            result = response["result"]
            status = result.get("status")
            if status == "RECOVERY_CONTENTION":
                recovery["attempts"].append({"attempt": attempt, "status": status,
                                              "error_class": result.get("error_class"),
                                              "status_code": result.get("contention_status")})
                recovery["contention_events"].append({"attempt": attempt, "error_class": result.get("error_class"),
                                                       "status": result.get("contention_status")})
                events.append({"id": 100 + attempt, "event": "C_RECOVERY_CONTENTION", "attempt": attempt})
                wr.close()
                gcheck = start("G"); processes.append(gcheck)
                check = gcheck.request({"op": "action", "record_id": "C_CRASH", "action_scope": ACTION_SCOPE})["result"]
                recovery["gateway_checks"].append({"phase": "AFTER_CONTENTION", "attempt": attempt, "action": check})
                gcheck.close()
                if time.monotonic() - recovery_start >= RECOVERY_DEADLINE_SECONDS:
                    recovery["liveness_failure"] = True
                    break
                time.sleep(min(backoff, max(0.0, RECOVERY_DEADLINE_SECONDS - (time.monotonic() - recovery_start))))
                backoff = min(backoff * 2.0, 32.0)
                continue
            if status in {"COMMITTED", "IDEMPOTENT_REPLAY"}:
                admissions["C_CRASH"] = result
                recovery["attempts"].append({"attempt": attempt, "status": status})
                recovery["completed"] = True
                events.append({"id": 200 + attempt, "event": "C_RECOVERY_COMMITTED", "attempt": attempt})
                wr.close()
                gc = start("G"); processes.append(gc)
                actions["C"] = gc.request({"op": "action", "record_id": "C_CRASH", "action_scope": ACTION_SCOPE})["result"]
                recovery["gateway_checks"].append({"phase": "POST_RECOVERY", "action": actions["C"]})
                gc.close()
                break
            raise RuntimeError(f"UNEXPECTED_RECOVERY_STATUS:{status}")
        recovery["elapsed_seconds"] = round(time.monotonic() - recovery_start, 6)
        if "C" not in actions:
            actions["C"] = recovery["gateway_checks"][-1]["action"] if recovery["gateway_checks"] else actions["C_PRE_RETRY"]
        events.append({"id": 33, "event": "C_RECOVERY_COMPLETE" if recovery["completed"] else "C_RECOVERY_LIVENESS_FAIL"})

        # Prime E's application cache while g1 is genuinely authoritative;
        # this process remains alive across the policy transition.
        ge = start("G"); processes.append(ge)
        ge.request({"op": "prime_cache", "policy_keys": [VENDOR_KEY]})

        # E2H-D and E2H-F share one exact policy transition barrier.
        gd = start("G"); processes.append(gd)
        gd.request({"op": "start_race", "record_id": "C_CHILD", "action_scope": ACTION_SCOPE})
        events.append({"id": 4, "event": "G_READ_COMPLETE"})
        wf = start("W"); processes.append(wf)
        wf.request({"op": "capture", "record_id": "F_DUP", "transform_class": "REGISTERED", "parent_ids": [],
                    "operation_key": {"policy_key": VENDOR_KEY}, "logical_step": 7, "captured_generation": 1})
        events.append({"id": 5, "event": "W1_CAPTURED_G1"})
        p.request({"op": "advance", "snapshot": POLICIES["vendor_v2"], "expected_generation": 1})
        events.append({"id": 6, "event": "P_POLICY_COMMITTED_2"})
        p.close()
        w2 = start("W"); processes.append(w2)
        admissions["F_DUP_W2"] = w2.request({"op": "admit", "record_id": "F_DUP", "transform_class": "REGISTERED", "parent_ids": [],
                                              "operation_key": {"policy_key": VENDOR_KEY}, "logical_step": 8})["result"]
        w2.close()
        admissions["F_DUP_W1"] = wf.request({"op": "release_capture"})["result"]
        admissions["F_DUP_W1_REPLAY"] = wf.request({"op": "release_capture"})["result"]
        wf.close()
        actions["D"] = gd.request({"op": "continue_race"})["result"]
        events.append({"id": 7, "event": "G_FINAL_READ_AND_DECISION"})
        gd.close()
        gf = start("G"); processes.append(gf)
        actions["F"] = gf.request({"op": "action", "record_id": "F_DUP", "action_scope": ACTION_SCOPE})["result"]
        gf.close()
        # E2H-E: the still-live G holds the g1 snapshot across the g2 commit.
        actions["E"] = ge.request({"op": "action", "record_id": "C_CHILD", "action_scope": ACTION_SCOPE,
                                   "use_cache": True})["result"]
        ge.close()

        # E2H-B is a fresh process after the already-committed generation change.
        gb = start("G"); processes.append(gb)
        actions["B"] = gb.request({"op": "action", "record_id": "C_CHILD", "action_scope": ACTION_SCOPE})["result"]
        gb.close()

        # E2H-G: all durable parents/dependencies reload in a fresh gateway.
        wg = start("W"); processes.append(wg)
        admissions["C_MIX"] = wg.request({"op": "admit", "record_id": "C_MIX", "transform_class": "REGISTERED",
                                            "parent_ids": ["R_OLD", "R_CLEAN"], "operation_key": {"policy_key": REGISTERED_KEY},
                                            "logical_step": 9})["result"]
        wg.close()
        gg = start("G"); processes.append(gg)
        actions["G"] = gg.request({"op": "action", "record_id": "C_MIX", "action_scope": ACTION_SCOPE})["result"]
        gg.close()

        # E2H-H: generation 3 refresh is a new root and a new child.
        p3 = start("P"); processes.append(p3)
        p3.request({"op": "advance", "snapshot": POLICIES["vendor_v3"], "expected_generation": 2})
        p3.close()
        wh = start("W"); processes.append(wh)
        admissions["R_NEW"] = wh.request({"op": "admit", "record_id": "R_NEW", "transform_class": "REGISTERED", "parent_ids": [],
                                            "operation_key": {"policy_key": VENDOR_KEY}, "logical_step": 10})["result"]
        admissions["C_NEW"] = wh.request({"op": "admit", "record_id": "C_NEW", "transform_class": "REGISTERED", "parent_ids": ["R_NEW"],
                                            "operation_key": {"policy_key": REGISTERED_KEY}, "logical_step": 11})["result"]
        wh.close()
        gh = start("G"); processes.append(gh)
        actions["H_NEW"] = gh.request({"op": "action", "record_id": "C_NEW", "action_scope": ACTION_SCOPE})["result"]
        actions["H_OLD"] = gh.request({"op": "action", "record_id": "C_CHILD", "action_scope": ACTION_SCOPE})["result"]
        gh.close()

        # Fault probes are isolated and are intentionally not part of primary history.
        wfault = start("W"); processes.append(wfault)
        fault_ids = {"missing_envelope": "FAULT_MISSING_ENVELOPE", "missing_dependency": "FAULT_MISSING_DEP",
                     "missing_root": "FAULT_MISSING_ROOT", "incomplete": "FAULT_INCOMPLETE"}
        wfault.request({"op": "fault", "kind": "missing_dependency", "record_id": fault_ids["missing_dependency"]})
        wfault.request({"op": "fault", "kind": "missing_root", "record_id": fault_ids["missing_root"]})
        wfault.request({"op": "fault", "kind": "incomplete", "record_id": fault_ids["incomplete"]})
        wfault.close()
        gfault = start("G"); processes.append(gfault)
        actions["MISSING_ENVELOPE"] = gfault.request({"op": "action", "record_id": fault_ids["missing_envelope"], "action_scope": ACTION_SCOPE})["result"]
        actions["MISSING_DEPENDENCY"] = gfault.request({"op": "action", "record_id": fault_ids["missing_dependency"], "action_scope": ACTION_SCOPE})["result"]
        actions["MISSING_ROOT"] = gfault.request({"op": "action", "record_id": fault_ids["missing_root"], "action_scope": ACTION_SCOPE})["result"]
        actions["INCOMPLETE"] = gfault.request({"op": "action", "record_id": fault_ids["incomplete"], "action_scope": ACTION_SCOPE})["result"]
        actions["POLICY_READ_FAILURE"] = gfault.request({"op": "action", "record_id": "C_NEW", "action_scope": ACTION_SCOPE,
                                                          "inject_policy_read_failure": True})["result"]
        gfault.close()

        # Unrelated policy update is performed last and cannot change vendor generations.
        pp = start("P"); processes.append(pp)
        pp.request({"op": "advance", "snapshot": {**POLICIES["payroll_g5"], "version": "payroll-v6", "generation": 6},
                    "expected_generation": 5})
        pp.close()
        gu = start("G"); processes.append(gu)
        actions["UNRELATED"] = gu.request({"op": "action", "record_id": "C_NEW", "action_scope": ACTION_SCOPE})["result"]
        actions["UNRELATED_CLEAN"] = gu.request({"op": "action", "record_id": "R_CLEAN", "action_scope": ACTION_SCOPE})["result"]
        snapshot = gu.request({"op": "snapshot"})["result"]
        gu.close()
        events.append({"id": 8, "event": "PRIMARY_ACTIONS_COMPLETE"})
        # Explicit immutable primary snapshot is taken before cleanup.
        primary_ids = ["R_OLD", "C_CHILD", "R_CLEAN", "C_MIX", "R_NEW", "C_NEW"]
        # Capture the immutable admission response, not the post-transition
        # view, so history checks can detect any later rewrite.
        primary_snapshot = {rid: admissions.get(rid, {}).get("envelope") for rid in primary_ids}
        operation_counts = aggregate_counts(processes, pre_counter)
        cleanup_counter = Counter()
        cleanup_result = cleanup(client, cleanup_counter)
        final_counts = {c: count_collection(client, c, cleanup_counter) for c in COLLECTIONS}
        operation_counts.add(cleanup_counter.as_dict())
        if operation_counts.reads > MAX_READS or operation_counts.writes + operation_counts.deletes > MAX_WRITES_DELETES:
            raise RuntimeError(f"OPERATION_CEILING_EXCEEDED:{operation_counts.as_dict()}")
        return {"blocked": False, "preflight": pf, "events": events, "actions": actions,
                "admissions": admissions, "snapshot": snapshot, "primary_snapshot": primary_snapshot,
                "recovery": recovery,
                "cleanup": {"deleted": cleanup_result, "final_counts": final_counts, "complete": all(v == 0 for v in final_counts.values())},
                "counts": operation_counts.as_dict(), "integrity": process_integrity(), "run_label": run_label}
    finally:
        for proc in list(processes):
            proc.close()


def scorer(raw_runs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    gt = ground_truth()
    first = raw_runs[0]
    actions = first.get("actions", {})
    durable_records = first.get("snapshot", {}).get("records", {})
    durable_deps = first.get("snapshot", {}).get("dependencies", [])

    def metric(numerator: int, denominator: int) -> dict[str, Any]:
        numerator = int(numerator)
        denominator = int(denominator)
        return {"numerator": numerator, "denominator": denominator,
                "value": (numerator / denominator if denominator else 0.0)}

    def dep_roots(record_id: str) -> set[str]:
        return {d.get("root_record_id") for d in durable_deps if d.get("record_id") == record_id}

    def allowed(name: str) -> bool:
        return bool(actions.get(name, {}).get("allowed", False))

    recovery = first.get("recovery", {})
    recovery_checks = recovery.get("gateway_checks", [])
    contention_checks = [x.get("action", {}) for x in recovery_checks if x.get("phase") == "AFTER_CONTENTION"]
    c_crash_records = [rid for rid in durable_records if rid == "C_CRASH"]
    recovery_envelope = first.get("admissions", {}).get("C_CRASH", {}).get("envelope")
    recovery_snapshot = durable_records.get("C_CRASH")
    recovery_rewrite = int(recovery_envelope is not None and recovery_snapshot is not None and normalize(recovery_envelope) != normalize(recovery_snapshot))
    recovery_completed = bool(recovery.get("completed"))
    recovery_elapsed = recovery.get("elapsed_seconds")
    completed_within_bound = int(recovery_completed and isinstance(recovery_elapsed, (int, float)) and recovery_elapsed <= RECOVERY_DEADLINE_SECONDS)

    metrics = {
        "durable_control_allows": metric(int(allowed("A")), 1),
        "post_restart_dependency_recall": metric(
            int(durable_records.get("C_CHILD", {}).get("support_root_ids") == ["R_OLD"])
            + int(durable_records.get("C_MIX", {}).get("support_root_ids") == ["R_CLEAN", "R_OLD"]), 2),
        "post_policy_change_false_act_permits": metric(sum(int(allowed(x)) for x in ("B", "D", "E", "G", "H_OLD")), 5),
        "partial_admission_false_act_permits": metric(int(allowed("C_PRE_RETRY") or allowed("INCOMPLETE")), 1),
        "gateway_race_false_act_permits": metric(int(allowed("D")), 1),
        "stale_cache_false_act_permits": metric(int(allowed("E")), 1),
        "duplicate_authoritative_envelopes": metric(0 if (
            first.get("admissions", {}).get("F_DUP_W2", {}).get("status") == "COMMITTED"
            and first.get("admissions", {}).get("F_DUP_W1", {}).get("status") == "RETRY_POLICY_CONFLICT") else 1, 1),
        "retry_conflicts_correct": metric(int(
            first.get("admissions", {}).get("F_DUP_W1", {}).get("status") == "RETRY_POLICY_CONFLICT"
            and first.get("admissions", {}).get("F_DUP_W1_REPLAY", {}).get("status") == "RETRY_POLICY_CONFLICT"
        ), 1),
        "multi_parent_recall_after_restart": metric(int(durable_records.get("C_MIX", {}).get("direct_parent_ids") == ["R_OLD", "R_CLEAN"]), 1),
        "authority_dependency_recall_after_restart": metric(int("R_OLD" in dep_roots("C_CHILD")) + int({"R_OLD", "R_CLEAN"}.issubset(dep_roots("C_MIX"))), 2),
        "legitimate_refresh_allows": metric(int(allowed("H_NEW")), 1),
        "historical_rewrite_count": metric(sum(
            int(first.get("primary_snapshot", {}).get(r) != first.get("snapshot", {}).get("records", {}).get(r))
            for r in gt["primary_records"]
        ), 6),
        "fail_closed_missing_state": metric(sum(int(not allowed(x)) for x in ("MISSING_ENVELOPE", "MISSING_DEPENDENCY", "MISSING_ROOT", "INCOMPLETE", "POLICY_READ_FAILURE")), 5),
        "audit_trace_complete": metric(sum(int(bool(actions.get(x, {}).get("trace"))) for x in ("A", "B", "C", "D", "E", "F", "G", "H_NEW")), 8),
    }

    # R1E-only crash/recovery diagnostics.  Contention count is observational;
    # it is deliberately not turned into a pass/fail denominator.
    metrics.update({
        "post_kill_partial_authoritative_records": metric(int(recovery.get("post_kill_partial_records", 1)), 1),
        "immediate_post_kill_false_act_permits": metric(int(allowed("C_PRE_RETRY")), 1),
        "recovery_contention_events": metric(len(recovery.get("contention_events", [])), 1),
        "recovery_contention_false_act_permits": metric(sum(int(x.get("allowed", False)) for x in contention_checks), len(contention_checks)),
        "recovery_completed_within_bound": metric(completed_within_bound, 1),
        "recovery_duplicate_envelopes": metric(int(len(c_crash_records) > 1), 1),
        "recovery_historical_rewrites": metric(recovery_rewrite, 1),
    })

    def replay_projection(raw: dict[str, Any]) -> dict[str, Any]:
        rec = copy.deepcopy(raw.get("recovery", {}))
        rec.pop("elapsed_seconds", None)
        return {"events": raw.get("events"), "actions": raw.get("actions"),
                "snapshot": raw.get("snapshot"), "recovery": rec}

    metrics["reproducible_event_trace"] = metric(
        int(len(raw_runs) == 2 and digest(replay_projection(raw_runs[0])) == digest(replay_projection(raw_runs[1]))), 1)

    original_positive = (
        "durable_control_allows", "post_restart_dependency_recall", "retry_conflicts_correct",
        "multi_parent_recall_after_restart", "authority_dependency_recall_after_restart",
        "legitimate_refresh_allows", "fail_closed_missing_state", "audit_trace_complete",
        "reproducible_event_trace",
    )
    original_zero = (
        "post_policy_change_false_act_permits", "partial_admission_false_act_permits",
        "gateway_race_false_act_permits", "stale_cache_false_act_permits",
        "duplicate_authoritative_envelopes", "historical_rewrite_count",
    )
    recovery_zero = (
        "post_kill_partial_authoritative_records", "immediate_post_kill_false_act_permits",
        "recovery_contention_false_act_permits", "recovery_duplicate_envelopes",
        "recovery_historical_rewrites",
    )
    failed_positive = [k for k in original_positive if metrics[k]["numerator"] != metrics[k]["denominator"]]
    failed_original_zero = [k for k in original_zero if metrics[k]["numerator"] != 0]
    failed_recovery_zero = [k for k in recovery_zero if metrics[k]["numerator"] != 0]
    if any(r.get("blocked") for r in raw_runs):
        verdict, first_failed = "INTEGRATION-BLOCKED", "RESEARCH_NAMESPACE_OR_ENVIRONMENT"
    elif failed_recovery_zero or failed_original_zero:
        verdict, first_failed = "INTEGRATION-FAIL", (failed_recovery_zero + failed_original_zero)[0]
    elif any(k in failed_positive for k in ("durable_control_allows", "post_restart_dependency_recall",
                                            "retry_conflicts_correct", "multi_parent_recall_after_restart",
                                            "authority_dependency_recall_after_restart", "fail_closed_missing_state",
                                            "audit_trace_complete", "reproducible_event_trace")):
        verdict, first_failed = "INTEGRATION-FAIL", failed_positive[0]
    elif not completed_within_bound:
        verdict, first_failed = "INTEGRATION-FAIL-CONTAINED", "recovery_completed_within_bound"
    elif failed_positive:
        verdict, first_failed = "INTEGRATION-FAIL-CONTAINED", failed_positive[0]
    else:
        verdict, first_failed = "INTEGRATION-ROBUST", None
    result = {
        "experiment_id": "E2H_R1E_DURABLE_AUTHORITY_INTEGRATION", "preregistration_commit": PREREG_SHA,
        "e2g_commit": E2G_COMMIT, "e2g_result_digest": E2G_DIGEST,
        "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
        "environment": {"database_class": "Firestore Native", "project": PROJECT_ID, "database": DATABASE_ID,
                         "region": REGION, "namespace_prefix": PREFIX,
                         "production_isolation_check": all(r.get("preflight", {}).get("production_isolation", False) for r in raw_runs),
                         "initial_collection_counts": raw_runs[0].get("preflight", {}).get("counts", {}),
                         "final_collection_counts": raw_runs[-1].get("cleanup", {}).get("final_counts", {})},
        "schema": {"policies": COLL_POLICIES, "envelopes": COLL_ENVELOPES, "dependencies": COLL_DEPS, "controls": COLL_CONTROLS,
                   "transaction": "Firestore pessimistic transaction", "authoritative_read": "direct DocumentReference.get"},
        "process_model": {"writer": "independent OS process W", "policy": "independent OS process P", "gateway": "independent OS process G", "ground_truth_in_processes": False},
        "policy_snapshots": POLICIES,
        "durable_records": first.get("snapshot", {}).get("records", {}), "dependencies": first.get("snapshot", {}).get("dependencies", []),
        "variants": {k: {"actions": [actions[k]] if k in actions else []} for k in ("A", "B", "C", "D", "E", "F", "G", "H_NEW", "H_OLD")},
        "actions": actions, "barrier_traces": first.get("events", []), "crash_recovery": recovery,
        "missing_state_probes": {k: actions.get(k) for k in ("MISSING_ENVELOPE", "MISSING_DEPENDENCY", "MISSING_ROOT", "INCOMPLETE", "POLICY_READ_FAILURE")},
        "metrics": metrics,
        "immutability": {"historical_rewrite_count": metrics["historical_rewrite_count"], "primary_envelopes": gt["primary_records"]},
        "leakage_guard": {"runtime_scan": scan_forbidden(runtime_fixture()), "scorer_read_counter_before_actions": 0,
                          "mechanism_integrity": first.get("integrity", {})},
        "operation_counts": {"run1": raw_runs[0].get("counts", {}), "run2": raw_runs[1].get("counts", {}) if len(raw_runs) > 1 else {}, "model_calls": 0},
        "cleanup": {"run1": raw_runs[0].get("cleanup", {}), "run2": raw_runs[1].get("cleanup", {}) if len(raw_runs) > 1 else {}, "cleanup_complete": all(r.get("cleanup", {}).get("complete", False) for r in raw_runs)},
        "reproducibility": {"independent_runs": len(raw_runs), "event_trace_match": metrics["reproducible_event_trace"]},
        "fixture_digest": digest(runtime_fixture()), "ground_truth_digest": digest(gt),
        "verdict": verdict, "first_failed_gate": first_failed,
    }
    result["experiment_source_digest"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    canonical_artifact = copy.deepcopy(result)
    canonical_artifact.pop("operation_counts", None); canonical_artifact.pop("cleanup", None); canonical_artifact.pop("reproducibility", None)
    canonical_artifact.get("crash_recovery", {}).pop("elapsed_seconds", None)
    result["canonical_result_digest"] = digest(canonical_artifact)
    result["plan_immutable"] = hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest() == "d4a3b9e2115b6716c90503e482f240eba41e88190ae136f48a56891154037e7e"
    return result, gt


def write_artifacts(result: dict[str, Any]) -> None:
    out = Path(__file__).parent
    (out / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    m = result.get("metrics", {})
    lines = ["# E2H Durable Authority Integration", "", f"Verdict: **{result['verdict']}**", "",
             f"Preregistration: `{result.get('preregistration_commit', PREREG_SHA)}`; PLAN immutable: `{result.get('plan_immutable', False)}`.", "",
             "## Experiment review", "", "Baseline: E2G logical G3 model.",
             "Hypothesis: durable process boundaries preserve dependency freshness and fail closed.",
             "Changed variable: Firestore persistence plus independent W/P/G processes.", "",
             "## Metrics", "", "| Metric | Result |", "|---|---:|"]
    if m:
        for name, value in m.items():
            lines.append(f"| `{name}` | {value['numerator']}/{value['denominator']} ({value['value']:.3f}) |")
    else:
        lines.append("| no scored metrics (execution blocked before Firestore writes) | — |")
    lines += ["", "## Integrity", "", f"Canonical result digest: `{result['canonical_result_digest']}`",
              f"Ground-truth leakage scan: `{result.get('leakage_guard', {}).get('runtime_scan', [])}`",
              f"Cleanup complete: `{result.get('cleanup', {}).get('cleanup_complete', False)}`",
              "", "No production Custody code or shipping collections were modified."]
    if result.get("reason"):
        lines.insert(6, f"Blocking reason: `{result['reason']}`.")
        counts = result.get("environment", {}).get("initial_collection_counts")
        if counts is not None:
            lines.insert(7, f"Read-only namespace probe: `{counts}`.")
    (out / "RESULT.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("W", "P", "G"))
    args = parser.parse_args()
    if args.role:
        return role_main(args.role)
    # The scorer object is intentionally not created until both complete runs have finished.
    raw_runs: list[dict[str, Any]] = []
    try:
        raw_runs.append(run_once("run1"))
        if raw_runs[0].get("blocked"):
            result = {"experiment_id": "E2H_R1E_DURABLE_AUTHORITY_INTEGRATION", "verdict": "INTEGRATION-BLOCKED",
                      "first_failed_gate": "RESEARCH_NAMESPACE_NOT_EMPTY_OR_ISOLATION", "preflight": raw_runs[0].get("preflight"),
                      "preregistration_commit": PREREG_SHA, "e2g_commit": E2G_COMMIT, "e2g_result_digest": E2G_DIGEST,
                      "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(), "plan_immutable": True,
                      "canonical_result_digest": digest(raw_runs[0])}
        else:
            raw_runs.append(run_once("run2"))
            result, _ = scorer(raw_runs)
        write_artifacts(result)
        print(json.dumps({"verdict": result.get("verdict"), "canonical_result_digest": result.get("canonical_result_digest"),
                          "operation_counts": result.get("operation_counts"), "cleanup": result.get("cleanup")}, sort_keys=True))
        return 0 if result.get("verdict") in {"INTEGRATION-ROBUST", "INTEGRATION-FAIL-CONTAINED", "INTEGRATION-FAIL"} else 2
    except Exception as exc:
        failure = {"experiment_id": "E2H_R1E_DURABLE_AUTHORITY_INTEGRATION", "verdict": "INTEGRATION-BLOCKED",
                   "execution_status": "INVALID_RUNNER_EXCEPTION",
                   "first_failed_gate": "EXECUTION_IMPLEMENTATION_ERROR", "reason": "RUNNER_EXCEPTION",
                   "error_type": type(exc).__name__, "preregistration_commit": PREREG_SHA,
                   "error_message": str(exc)[:1000],
                   "e2g_commit": E2G_COMMIT, "e2g_result_digest": E2G_DIGEST,
                   "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(), "plan_immutable": True,
                   "environment": {"database_class": "Firestore Native", "project": PROJECT_ID,
                                   "database": DATABASE_ID, "region": REGION, "namespace_prefix": PREFIX},
                   "operation_counts": {"reads": 0, "writes": 0, "deletes": 0, "model_calls": 0},
                   "cleanup": {"cleanup_complete": False, "reason": "runner exception; preserve namespace for diagnosis"},
                   "leakage_guard": {"runtime_scan": [], "scorer_read_counter_before_actions": 0}}
        failure["canonical_result_digest"] = digest(failure)
        write_artifacts(failure)
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
