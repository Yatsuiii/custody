"""Frozen real-Firestore diagnostic for the P7 policy CAS failure.

This invokes the production FirestoreAuthorityStore from independent processes
and records the complete wrapped exception chain. It does not evaluate B7
security behavior and must not be interpreted as a P7 rerun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from google.cloud import firestore

from custody.authority import Capability, OperationRole, PolicyKey, PolicySnapshot
from custody.firestore_store import (
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

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_B7_SHA = "cb9761dc63a78e29cd366fca7cbaba5f5399c6da"
INVALID_P7_EVIDENCE_SHA = "1e19684a9ffac83f82ec47367067568ecabc9f21"
PROJECT_ID = "project-988bc9fe-092c-4b32-90c"
DATABASE_ID = "(default)"
REGION = "us-central1"
DIAGNOSTIC_ID = "P7D_FIRESTORE_POLICY_CAS_20260824_01"
NAMESPACE = "custody_p7d_policy_cas_20260824_01"
MAX_RUNTIME_SECONDS = 180.0
COST_CEILING_USD = 0.001
ESTIMATED_COST_USD = 0.00002
PROOF_DIR = ROOT / "proof-out"
RAW_PATH = PROOF_DIR / "p7-firestore-policy-cas-diagnostic.raw.json"
RESULT_PATH = PROOF_DIR / "p7-firestore-policy-cas-diagnostic.json"

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
POLICY_KEY = PolicyKey(
    "p7d-fixture",
    "custody-test-source",
    "policy-cas",
    "R1",
    "external.send",
)


class _NamespacedClient:
    """Restrict the production store to this diagnostic's collections."""

    def __init__(self, client: firestore.Client) -> None:
        self._client = client

    def collection(self, name: str):
        if name not in COLLECTIONS:
            raise RuntimeError(f"P7D_COLLECTION_NOT_AUTHORIZED:{name}")
        return self._client.collection(f"{NAMESPACE}__{name}")

    def transaction(self):
        return self._client.transaction()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT}", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def _store(client: firestore.Client) -> FirestoreAuthorityStore:
    return FirestoreAuthorityStore(_NamespacedClient(client))  # type: ignore[arg-type]


def _snapshot(generation: int) -> PolicySnapshot:
    return PolicySnapshot(
        POLICY_KEY,
        f"p7d-v{generation}",
        generation,
        OperationRole.ORIGIN,
        {POLICY_KEY.action_scope: Capability.ACT},
    )


def _exception_chain(error: BaseException) -> list[dict[str, object]]:
    chain: list[dict[str, object]] = []
    current: BaseException | None = error
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        code = getattr(current, "code", None)
        if callable(code):
            try:
                code = code()
            except BaseException:  # diagnostic metadata must not mask the error
                code = "UNREADABLE"
        chain.append(
            {
                "module": type(current).__module__,
                "type": type(current).__name__,
                "message": str(current),
                "code": None if code is None else str(code),
            }
        )
        current = current.__cause__ or current.__context__
    return chain


def _policy_view(snapshot: PolicySnapshot | None) -> dict[str, object] | None:
    if snapshot is None:
        return None
    return {
        "generation": snapshot.generation,
        "version": snapshot.version,
        "policy_key_digest": snapshot.policy_key.digest,
    }


def _role(role: str) -> int:
    client = _client()
    try:
        store = _store(client)
        if role == "CREATE":
            store.put_policy(_snapshot(1))
        elif role == "CAS":
            store.put_policy(_snapshot(2), expected_generation=1)
        elif role != "READ":
            raise RuntimeError(f"UNKNOWN_P7D_ROLE:{role}")
        result = {
            "ok": True,
            "role": role,
            "pid": os.getpid(),
            "policy": _policy_view(store.policy(POLICY_KEY)),
        }
    except BaseException as error:
        result = {
            "ok": False,
            "role": role,
            "pid": os.getpid(),
            "exception_chain": _exception_chain(error),
        }
    finally:
        client.close()
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["ok"] else 2


def _run_role(role: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.diagnose_b7_firestore_policy_cas",
            "--role",
            role,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return {
            "ok": False,
            "role": role,
            "runner_error": type(error).__name__,
            "stdout": completed.stdout[-2_000:],
            "stderr": completed.stderr[-2_000:],
            "return_code": completed.returncode,
        }
    result["return_code"] = completed.returncode
    result["stderr"] = completed.stderr[-2_000:]
    return result


def _collection_counts(client: firestore.Client) -> dict[str, int]:
    return {
        name: sum(1 for _ in client.collection(f"{NAMESPACE}__{name}").stream())
        for name in COLLECTIONS
    }


def _cleanup() -> dict[str, object]:
    client = _client()
    deleted: dict[str, int] = {}
    try:
        for name in COLLECTIONS:
            count = 0
            for document in client.collection(f"{NAMESPACE}__{name}").stream():
                document.reference.delete()
                count += 1
            deleted[name] = count
        final_counts = _collection_counts(client)
    finally:
        client.close()
    return {
        "deleted_documents": deleted,
        "final_collection_counts": final_counts,
        "complete": all(value == 0 for value in final_counts.values()),
        "cleaned_at": _utc_now(),
    }


def _preflight() -> dict[str, object]:
    client = _client()
    try:
        counts = _collection_counts(client)
    finally:
        client.close()
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    production_diff = _git(
        "diff",
        "--name-only",
        f"{PRODUCTION_B7_SHA}..{head}",
        "--",
        "custody/authority.py",
        "custody/action.py",
        "custody/store.py",
        "custody/firestore_store.py",
    )
    tracked_dirty = _git("status", "--porcelain", "--untracked-files=no")
    valid = (
        head == upstream
        and not production_diff
        and not tracked_dirty
        and all(value == 0 for value in counts.values())
    )
    return {
        "valid": valid,
        "head": head,
        "upstream": upstream,
        "production_b7_sha": PRODUCTION_B7_SHA,
        "invalid_p7_evidence_sha": INVALID_P7_EVIDENCE_SHA,
        "production_diff": production_diff.splitlines(),
        "tracked_dirty": tracked_dirty.splitlines(),
        "initial_collection_counts": counts,
        "project": PROJECT_ID,
        "database": DATABASE_ID,
        "region": REGION,
        "namespace": NAMESPACE,
        "estimated_cost_usd": ESTIMATED_COST_USD,
        "cost_ceiling_usd": COST_CEILING_USD,
        "maximum_runtime_seconds": MAX_RUNTIME_SECONDS,
    }


def _execute() -> int:
    preflight = _preflight()
    print(json.dumps({"preflight": preflight}, sort_keys=True, indent=2), flush=True)
    if not preflight["valid"]:
        return 2

    started_at = _utc_now()
    started = time.monotonic()
    create = _run_role("CREATE")
    cas = _run_role("CAS") if create.get("ok") else None
    reread = _run_role("READ") if cas and cas.get("ok") else None
    raw = {
        "diagnostic_id": DIAGNOSTIC_ID,
        "started_at": started_at,
        "preflight": preflight,
        "create": create,
        "cas": cas,
        "reread": reread,
        "runtime_seconds_before_cleanup": time.monotonic() - started,
        "model_api_calls": 0,
        "scorer_fields": 0,
        "production_security_decisions": 0,
    }
    _write_json(RAW_PATH, raw)
    raw_digest = _sha256(RAW_PATH)
    cleanup = _cleanup()

    expected = {"generation": 2, "version": "p7d-v2"}
    observed = None if reread is None else reread.get("policy")
    supported = bool(
        create.get("ok")
        and cas is not None
        and cas.get("ok")
        and reread is not None
        and reread.get("ok")
        and isinstance(observed, Mapping)
        and observed.get("generation") == expected["generation"]
        and observed.get("version") == expected["version"]
        and cleanup["complete"]
    )
    if supported:
        verdict = "P7D-POLICY-CAS-SUPPORTED"
    elif create.get("ok") and cas is not None and not cas.get("ok"):
        verdict = "P7D-PRODUCTION-FIRESTORE-POLICY-CAS-FAIL"
    else:
        verdict = "P7D-INVALID-DIAGNOSTIC"
    result = {
        "diagnostic_id": DIAGNOSTIC_ID,
        "verdict": verdict,
        "raw_trace_digest": raw_digest,
        "create": create,
        "cas": cas,
        "reread": reread,
        "cleanup": cleanup,
        "runtime_seconds": time.monotonic() - started,
        "production_b7_changed": False,
    }
    _write_json(RESULT_PATH, result)
    print(json.dumps(result, sort_keys=True, indent=2), flush=True)
    return 0 if supported else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("CREATE", "CAS", "READ"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.role:
        return _role(arguments.role)
    if arguments.cleanup:
        print(json.dumps(_cleanup(), sort_keys=True, indent=2))
        return 0
    if arguments.execute:
        return _execute()
    parser.error("choose exactly one of --role, --execute, or --cleanup")


if __name__ == "__main__":
    raise SystemExit(main())
