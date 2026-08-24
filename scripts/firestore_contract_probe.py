#!/usr/bin/env python3
"""Non-security real Firestore contract probe for the Custody adapter.

This script exercises only storage mechanics with one legitimate source event.
It does not run P7, inspect scorer fields, calculate efficacy metrics, or
construct malicious controls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from google.cloud import firestore

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from custody.action import AuthorityAction, AuthorityGateway  # noqa: E402
from custody.authority import (  # noqa: E402
    AdmissionGate,
    AuthorityOutput,
    Capability,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
)
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


DEFAULT_PROJECT = "project-988bc9fe-092c-4b32-90c"
DEFAULT_DATABASE = "(default)"
DEFAULT_REGION = "us-central1"
DEFAULT_PREFIX = "custody_firestore_contract_20260824_adapter01"
DEFAULT_OUTPUT = ROOT / "proof-out" / "firestore-contract-probe-adapter01.json"
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


class _NamespacedClient:
    """Expose only the client surface used by FirestoreAuthorityStore."""

    def __init__(self, raw: firestore.Client, prefix: str) -> None:
        self._raw = raw
        self._prefix = prefix

    def collection(self, name: str):
        return self._raw.collection(f"{self._prefix}__{name}")

    def transaction(self):
        return self._raw.transaction()


class _ProbeDispatcher:
    def dispatch(self, action: AuthorityAction) -> str:
        return f"stored:{action.request_id}"


class _ProbePreflightFailure(RuntimeError):
    """The namespace was not fresh; never clean it under this identity."""


def _exception_record(error: BaseException) -> dict[str, object]:
    chain = []
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(
            {
                "type": type(current).__name__,
                "module": type(current).__module__,
                "message": str(current),
            }
        )
        current = current.__cause__ or current.__context__
    return {
        "type": type(error).__name__,
        "module": type(error).__module__,
        "message": str(error),
        "chain": chain,
        "traceback": traceback.format_exc(),
    }


def _snapshot_summary(snapshot) -> dict[str, object]:
    return {
        "exists": bool(snapshot.exists),
        "has_to_dict": callable(getattr(snapshot, "to_dict", None)),
        "create_time_present": snapshot.create_time is not None,
    }


def _collection_counts(client: _NamespacedClient) -> dict[str, int]:
    return {
        name: sum(1 for _ in client.collection(name).stream()) for name in COLLECTIONS
    }


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    """Publish a complete probe artifact or leave the previous one intact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            json.dump(value, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _cleanup(client: _NamespacedClient) -> dict[str, object]:
    deleted: dict[str, int] = {}
    for name in COLLECTIONS:
        snapshots = tuple(client.collection(name).stream())
        for snapshot in snapshots:
            snapshot.reference.delete()
        deleted[name] = len(snapshots)
    final_counts = _collection_counts(client)
    return {
        "deleted_documents": deleted,
        "final_collection_counts": final_counts,
        "complete": all(count == 0 for count in final_counts.values()),
    }


def _run_step(
    operations: list[dict[str, object]],
    name: str,
    sdk_call: str,
    operation: Callable[[], object],
) -> object:
    entry: dict[str, object] = {"name": name, "sdk_call": sdk_call, "ok": False}
    operations.append(entry)
    try:
        result = operation()
    except BaseException as error:
        entry["exception"] = _exception_record(error)
        raise
    entry["ok"] = True
    return result


def run_probe(*, project: str, prefix: str, output: Path) -> dict[str, object]:
    operations: list[dict[str, object]] = []
    cleanup: dict[str, object] | None = None
    failure: dict[str, object] | None = None
    client: _NamespacedClient | None = None
    initial_counts: dict[str, int] | None = None
    preflight_failed = False
    try:
        raw_client = firestore.Client(project=project, database=DEFAULT_DATABASE)
        client = _NamespacedClient(raw_client, prefix)
        initial_counts = _run_step(
            operations,
            "namespace_preflight_counts",
            "CollectionReference.stream() -> snapshots",
            lambda: _collection_counts(client),
        )
        if any(initial_counts.values()):
            preflight_failed = True
            raise _ProbePreflightFailure("fresh probe namespace contains documents")

        store = FirestoreAuthorityStore(client)  # type: ignore[arg-type]
        event = SourceAuthorityEvent.from_json(
            (ROOT / "tests" / "fixtures" / "b7" / "source_event.json").read_bytes()
        )
        source_key = event.receipt.policy_key
        issuer_public_key = bytes.fromhex(
            (ROOT / "tests" / "fixtures" / "b7" / "issuer_public_key.hex")
            .read_text()
            .strip()
        )
        identity_key = PolicyKey("probe", "custody", "identity", "R1", "export.send")
        registered_key = PolicyKey(
            "probe", "custody", "registered", "R1", "export.send"
        )
        freeform_key = PolicyKey("probe", "model", "freeform", "R1", "export.send")
        root_id = "PROBE-ROOT"

        missing_ref = client.collection(AUTHORITY_POLICIES_COLLECTION).document(
            "missing-outside"
        )
        outside = _run_step(
            operations,
            "missing_document_outside_transaction",
            "DocumentReference.get() -> DocumentSnapshot",
            missing_ref.get,
        )
        operations[-1]["observation"] = _snapshot_summary(outside)

        missing_in_transaction = _run_step(
            operations,
            "missing_document_inside_transaction",
            "DocumentReference.get(transaction=transaction) -> DocumentSnapshot",
            lambda: store._run_transaction(
                lambda transaction: transaction.get(
                    client.collection(AUTHORITY_POLICIES_COLLECTION).document(
                        "missing-inside"
                    )
                )
            ),
        )
        operations[-1]["observation"] = _snapshot_summary(missing_in_transaction)

        _run_step(
            operations,
            "issuer_key_transactional_create",
            "Transaction.create(DocumentReference, dict) -> None",
            lambda: store.put_issuer_key(
                issuer_id=event.receipt.issuer_id,
                issuer_key_id=event.receipt.issuer_key_id,
                public_key=issuer_public_key,
            ),
        )
        key_read = _run_step(
            operations,
            "issuer_key_read_reconstruction",
            "DocumentReference.get() -> DocumentSnapshot",
            lambda: store.public_key_for(
                issuer_id=event.receipt.issuer_id,
                issuer_key_id=event.receipt.issuer_key_id,
            ),
        )
        operations[-1]["matches"] = key_read == issuer_public_key

        _run_step(
            operations,
            "issuer_key_idempotent_existing_transaction_path",
            "DocumentReference.get(transaction=transaction) then Transaction.create",
            lambda: store.put_issuer_key(
                issuer_id=event.receipt.issuer_id,
                issuer_key_id=event.receipt.issuer_key_id,
                public_key=issuer_public_key,
            ),
        )

        source_policy = PolicySnapshot(
            source_key,
            "probe-v1",
            event.receipt.granting_generation,
            OperationRole.ORIGIN,
            {event.receipt.action_scope: Capability.ACT},
        )
        _run_step(
            operations,
            "policy_transactional_create",
            "Transaction.get(DocumentReference) translated via document.get(transaction=transaction), then Transaction.create",
            lambda: store.put_policy(source_policy),
        )
        _run_step(
            operations,
            "policy_idempotent_existing_transaction_path",
            "DocumentReference.get(transaction=transaction) then no-op",
            lambda: store.put_policy(source_policy),
        )
        policy_read = _run_step(
            operations,
            "policy_read_reconstruction",
            "DocumentReference.get() -> DocumentSnapshot",
            lambda: store.policy(source_key),
        )
        operations[-1]["matches"] = policy_read == source_policy

        gate = AdmissionGate(
            store=store,
            source_policy_keys=(source_key,),
            identity_policy_key=identity_key,
            registered_policy_keys=(registered_key,),
            freeform_policy_key=freeform_key,
        )
        admission = _run_step(
            operations,
            "admission_transactional_create",
            "transactional B7 admission reads plus Transaction.create writes",
            lambda: gate.admit_source(
                event,
                AuthorityOutput(root_id, event.source_object_commitment),
            ),
        )
        operations[-1]["admitted"] = admission.admitted
        if not admission.admitted:
            raise RuntimeError(
                f"legitimate admission unexpectedly failed: {admission.reason}"
            )

        replay = _run_step(
            operations,
            "admission_idempotent_existing_transaction_path",
            "transactional existing-record read and side-document verification",
            lambda: gate.admit_source(
                event,
                AuthorityOutput(root_id, event.source_object_commitment),
            ),
        )
        operations[-1]["admitted"] = replay.admitted
        envelope = _run_step(
            operations,
            "admission_read_reconstruction",
            "DocumentReference.get() -> DocumentSnapshot",
            lambda: store.envelope(root_id),
        )
        operations[-1]["matches_record"] = (
            envelope is not None and envelope.record_id == root_id
        )
        dependencies = store.dependencies(root_id)
        operations.append(
            {
                "name": "admission_dependency_read_reconstruction",
                "sdk_call": "DocumentReference.get() -> DocumentSnapshot",
                "ok": True,
                "dependency_count": len(dependencies),
            }
        )

        action = AuthorityAction(
            "probe-action",
            event.receipt.action_scope,
            {"destination": "probe", "value": "legitimate"},
        )
        execution = _run_step(
            operations,
            "action_decision_transactional_create",
            "transactional current-state reads plus Transaction.create",
            lambda: AuthorityGateway(store).execute(
                action, (root_id,), _ProbeDispatcher()
            ),
        )
        operations[-1]["dispatched"] = execution.dispatched
        decisions = store.action_decisions()
        operations.append(
            {
                "name": "action_decision_read_reconstruction",
                "sdk_call": "CollectionReference.stream() -> snapshots",
                "ok": True,
                "decision_count": len(decisions),
            }
        )

        root_key = ReceiptRootKey.from_receipt(
            event.receipt, custody_root_record_id=root_id
        )
        revocation = _run_step(
            operations,
            "root_revocation_transactional_create",
            "transactional root-event and marker reads plus Transaction.create",
            lambda: RevocationController(store).revoke_receipt_roots(
                revocation_id="probe-revocation", root_keys=(root_key,)
            ),
        )
        operations[-1]["affected_record_ids"] = list(revocation.affected_record_ids)
        revocations = store.root_revocations()
        operations.append(
            {
                "name": "root_revocation_read_reconstruction",
                "sdk_call": "CollectionReference.stream() -> snapshots",
                "ok": True,
                "revocation_count": len(revocations),
            }
        )
        affected = _run_step(
            operations,
            "affected_dependency_query",
            "CollectionReference.stream() over authority_dependencies",
            lambda: store.affected_record_ids((root_key.digest,)),
        )
        operations[-1]["contains_root"] = root_id in affected
    except BaseException as error:
        failure = {
            "failed_operation": operations[-1]["name"] if operations else None,
            "classification": (
                "INVALID-PREFLIGHT"
                if isinstance(error, _ProbePreflightFailure)
                else "PROBE-OPERATION-FAILURE"
            ),
            "exception": _exception_record(error),
        }
    finally:
        if not preflight_failed and client is not None and initial_counts is not None:
            try:
                cleanup = _cleanup(client)
            except BaseException as error:
                cleanup = {
                    "complete": False,
                    "exception": _exception_record(error),
                }

    return _probe_result(
        project=project,
        prefix=prefix,
        initial_counts=initial_counts,
        operations=operations,
        cleanup=cleanup,
        failure=failure,
        output=output,
    )


def _probe_result(
    *,
    project: str,
    prefix: str,
    initial_counts: dict[str, int] | None,
    operations: list[dict[str, object]],
    cleanup: dict[str, object] | None,
    failure: dict[str, object] | None,
    output: Path,
) -> dict[str, object]:
    result = {
        "status": "FAIL" if failure is not None else "PASS",
        "project": project,
        "database": DEFAULT_DATABASE,
        "region": DEFAULT_REGION,
        "namespace_prefix": prefix,
        "initial_collection_counts": initial_counts,
        "operations": operations,
        "failure": failure,
        "cleanup": cleanup,
        "security_metrics": False,
        "scorer_reads": 0,
        "model_calls": 0,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    _write_json_atomic(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    try:
        result = run_probe(
            project=arguments.project,
            prefix=arguments.prefix,
            output=arguments.output,
        )
    except BaseException as error:
        result = {
            "status": "FAIL",
            "classification": "PROBE-HARNESS-FAIL",
            "project": arguments.project,
            "database": DEFAULT_DATABASE,
            "region": DEFAULT_REGION,
            "namespace_prefix": arguments.prefix,
            "operations": [],
            "failure": {"exception": _exception_record(error)},
            "cleanup": None,
            "security_metrics": False,
            "scorer_reads": 0,
            "model_calls": 0,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        _write_json_atomic(arguments.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    cleanup = result.get("cleanup") or {}
    return 0 if result["status"] == "PASS" and cleanup.get("complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
