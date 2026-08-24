"""P7 live proof for the production B7 authority implementation.

The treatment is deliberately split across independent operating-system
processes.  Every stateful role constructs a fresh production
``FirestoreAuthorityStore`` and calls production admission, revocation, or
gateway APIs.  The only adapter prefixes Firestore collection names so this
proof cannot address shipping collections.

This module contains treatment orchestration only.  Outcome rules live in the
separate gate program and are not imported until after the raw trace is frozen.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from google.cloud import firestore
from google.cloud.firestore_v1.transaction import Transaction

from custody.action import AuthorityAction, AuthorityExecution, AuthorityGateway
from custody.authority import (
    AdmissionGate,
    AdmissionResult,
    AuthorityOutput,
    AuthorityReceipt,
    Capability,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
    TransformRef,
    canonical_json_bytes,
)
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


EXPERIMENT_ID = "P7_LIVE_PRODUCTION_B7_INTEGRATION_PROOF"
PRODUCTION_B7_SHA = "cb9761dc63a78e29cd366fca7cbaba5f5399c6da"
PROJECT_ID = "project-988bc9fe-092c-4b32-90c"
DATABASE_ID = "(default)"
REGION = "us-central1"
RUN_ID = "p7-b7-20260824-ec32e4e31d21"
COLLECTION_PREFIX = "custody_p7_b7_20260824_ec32e4e31d21"
SOURCE_PRODUCER = "TEST-OWNED"
ACTION_SCOPE = "export.send"
RECOVERY_BOUND_SECONDS = 90.0
MAX_RUNTIME_SECONDS = 600.0
ESTIMATED_READS = 1_500
ESTIMATED_WRITES = 200
ESTIMATED_DELETES = 200
COST_CEILING_USD = 0.01
ESTIMATED_COST_USD = 0.00065

ROOT = Path(__file__).resolve().parent.parent
RAW_TRACE_PATH = ROOT / "proof-out" / "b7-production-live-equivalence.raw.json"
RESULT_PATH = ROOT / "proof-out" / "b7-production-live-equivalence.json"
CLEANUP_PATH = ROOT / "proof-out" / "b7-production-live-equivalence.cleanup.json"
GATE_SCRIPT = ROOT / "scripts" / "b7_production_equivalence_gates.py"
GATE_MODULE = ROOT / "live" / "b7_production_equivalence_gates.py"

B7_COLLECTIONS = (
    CUSTODY_COLLECTION,
    AUTHORITY_DEPENDENCIES_COLLECTION,
    AUTHORITY_POLICIES_COLLECTION,
    AUTHORITY_ISSUER_KEYS_COLLECTION,
    AUTHORITY_RECEIPT_ROOTS_COLLECTION,
    AUTHORITY_REVOCATIONS_COLLECTION,
    AUTHORITY_REVOKED_ROOTS_COLLECTION,
    AUTHORITY_ACTION_DECISIONS_COLLECTION,
)

MAIN_SOURCE = PolicyKey(
    "p7-fixture", "custody-test-source", "record.fetch", "R1", ACTION_SCOPE
)
STALE_SOURCE = PolicyKey(
    "p7-fixture", "custody-test-source", "stale.fetch", "R1", ACTION_SCOPE
)
IDENTITY = PolicyKey("p7-fixture", "custody", "identity", "R1", ACTION_SCOPE)
REGISTERED = PolicyKey(
    "p7-fixture", "custody", "registered_projection", "R1", ACTION_SCOPE
)
FREEFORM = PolicyKey("p7-fixture", "model", "freeform", "R1", ACTION_SCOPE)

ISSUER_ID = "custody-p7-test-source"
ISSUER_KEY_ID = "ephemeral-ed25519-20260824"

FORBIDDEN_SCORER_FIELDS = frozenset(
    {
        "true_origin",
        "scorer_truth",
        "attack_label",
        "attack_type",
        "adversarial_goal",
        "expected_memory",
        "expected_allow",
        "expected_deny",
        "expected_outcome",
        "expected_result",
        "malicious",
        "benign",
        "compromised",
    }
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"P7_MANIFEST_VALUE_NOT_JSON_SAFE:{type(value).__name__}")


def _write_json(path: Path, value: object) -> None:
    """Atomically freeze one JSON artifact and force its bytes to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prefixed_collection(name: str) -> str:
    if name not in B7_COLLECTIONS:
        raise RuntimeError(f"P7_COLLECTION_NOT_AUTHORIZED:{name}")
    return f"{COLLECTION_PREFIX}__{name}"


def _collection_plan() -> dict[str, str]:
    return {name: _prefixed_collection(name) for name in B7_COLLECTIONS}


def _private_material_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).casefold()
            child = f"{path}.{key}"
            if "private_key" in key_text or "signing_key" in key_text:
                found.append(child)
            found.extend(_private_material_paths(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_private_material_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str) and "BEGIN PRIVATE KEY" in value:
        found.append(path)
    return found


def _forbidden_scorer_paths(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_SCORER_FIELDS:
                found.append(child)
            found.extend(_forbidden_scorer_paths(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_forbidden_scorer_paths(item, f"{path}[{index}]"))
    return found


class _CommitBarrierTransaction(Transaction):
    """Fault injector below the production store's transaction boundary.

    Production code stages every admission write.  This subclass reports that
    point immediately before the Firestore commit RPC and waits.  P7 kills the
    process there; no production admission or authority decision is replaced.
    """

    def __init__(
        self,
        client: firestore.Client,
        on_staged: Callable[[int], None],
    ) -> None:
        super().__init__(client, max_attempts=5)
        self._on_staged = on_staged

    def _commit(self) -> list:
        self._on_staged(len(self._write_pbs))
        control = sys.stdin.readline()
        if not control:
            raise RuntimeError("P7_COMMIT_BARRIER_CONTROL_CLOSED")
        if json.loads(control).get("op") != "release_staged_commit":
            raise RuntimeError("P7_COMMIT_BARRIER_NOT_RELEASED")
        return super()._commit()


class _NamespacedFirestoreClient:
    """Expose only P7-prefixed B7 collections to the production store."""

    def __init__(
        self,
        raw: firestore.Client,
        *,
        on_staged: Callable[[int], None] | None = None,
    ) -> None:
        self._raw = raw
        self._on_staged = on_staged

    def collection(self, name: str):
        return self._raw.collection(_prefixed_collection(name))

    def transaction(self):
        if self._on_staged is None:
            return self._raw.transaction()
        return _CommitBarrierTransaction(self._raw, self._on_staged)


def _client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def _store(
    raw: firestore.Client,
    *,
    on_staged: Callable[[int], None] | None = None,
) -> FirestoreAuthorityStore:
    return FirestoreAuthorityStore(
        _NamespacedFirestoreClient(raw, on_staged=on_staged)  # type: ignore[arg-type]
    )


def _policies() -> tuple[PolicySnapshot, ...]:
    return (
        PolicySnapshot(
            MAIN_SOURCE,
            "source-v1",
            1,
            OperationRole.ORIGIN,
            {ACTION_SCOPE: Capability.ACT},
        ),
        PolicySnapshot(
            STALE_SOURCE,
            "stale-v1",
            1,
            OperationRole.ORIGIN,
            {ACTION_SCOPE: Capability.ACT},
        ),
        PolicySnapshot(
            IDENTITY,
            "identity-v1",
            1,
            OperationRole.RELAY,
            {ACTION_SCOPE: Capability.ACT},
        ),
        PolicySnapshot(
            REGISTERED,
            "registered-v1",
            1,
            OperationRole.RELAY,
            {ACTION_SCOPE: Capability.ACT},
        ),
        PolicySnapshot(
            FREEFORM,
            "freeform-v1",
            1,
            OperationRole.RELAY,
            {ACTION_SCOPE: Capability.ACT},
        ),
    )


def _gate(store: FirestoreAuthorityStore) -> AdmissionGate:
    return AdmissionGate(
        store=store,
        source_policy_keys=(MAIN_SOURCE, STALE_SOURCE),
        identity_policy_key=IDENTITY,
        registered_policy_keys=(REGISTERED,),
        freeform_policy_key=FREEFORM,
    )


def _source_specs() -> tuple[tuple[str, PolicyKey], ...]:
    return (
        ("event-001", MAIN_SOURCE),
        ("event-002", MAIN_SOURCE),
        ("event-003", MAIN_SOURCE),
        ("event-004", MAIN_SOURCE),
        ("event-005", MAIN_SOURCE),
        ("event-006", MAIN_SOURCE),
        ("event-007", STALE_SOURCE),
        ("event-008", MAIN_SOURCE),
        ("event-009", MAIN_SOURCE),
        ("event-010", MAIN_SOURCE),
    )


def _issue_event(
    signing_key: Ed25519PrivateKey,
    *,
    event_id: str,
    policy_key: PolicyKey,
) -> SourceAuthorityEvent:
    ordinal = int(event_id.rsplit("-", 1)[1])
    source_object = {
        "record_id": f"source-record-{ordinal:03d}",
        "department": policy_key.department,
        "source": policy_key.source,
        "operation": policy_key.operation,
        "revision": policy_key.revision,
        "action_scope": policy_key.action_scope,
        "value": f"fixture-value-{ordinal:03d}",
    }
    commitment = hashlib.sha256(canonical_json_bytes(source_object)).hexdigest()
    unsigned = AuthorityReceipt(
        receipt_version="1",
        receipt_id=f"p7-receipt-{ordinal:03d}",
        issuer_id=ISSUER_ID,
        issuer_key_id=ISSUER_KEY_ID,
        policy_key=policy_key,
        granting_generation=1,
        granted_cap=Capability.ACT,
        action_scope=policy_key.action_scope,
        source_revision=policy_key.revision,
        upstream_record_id=str(source_object["record_id"]),
        upstream_object_commitment=commitment,
        issuer_signature="0" * 128,
    )
    receipt = dataclasses.replace(
        unsigned,
        issuer_signature=signing_key.sign(unsigned.canonical_bytes()).hex(),
    )
    return SourceAuthorityEvent(source_object, receipt)


def _admission_observation(result: AdmissionResult) -> dict[str, object]:
    return {
        "record_id": result.record_id,
        "admitted": result.admitted,
        "reason": result.reason,
    }


def _execution_observation(execution: AuthorityExecution) -> dict[str, object]:
    return {
        "allowed": execution.decision.allowed,
        "reason": execution.decision.reason,
        "effective_cap": execution.decision.effective_cap.value,
        "dispatched": execution.dispatched,
        "evaluated_record_ids": list(execution.decision.evaluated_record_ids),
        "support_root_key_digests": list(execution.decision.support_root_key_digests),
    }


def _graph_observation(
    store: FirestoreAuthorityStore, record_ids: Sequence[str]
) -> dict[str, object]:
    records: dict[str, object] = {}
    for record_id in record_ids:
        envelope = store.envelope(record_id)
        if envelope is None:
            records[record_id] = {"present": False, "dependencies": []}
            continue
        records[record_id] = {
            "present": True,
            "envelope_sha256": hashlib.sha256(envelope.canonical_bytes()).hexdigest(),
            "transform_class": envelope.transform_class.value,
            "direct_parent_ids": list(envelope.direct_parent_ids),
            "support_root_ids": list(envelope.support_root_ids),
            "support_root_key_digests": list(envelope.support_root_key_digests),
            "authority_receipt_present": envelope.authority_receipt is not None,
            "dependencies": [
                dependency.as_dict() for dependency in store.dependencies(record_id)
            ],
        }
    return records


def _history(store: FirestoreAuthorityStore) -> dict[str, str]:
    return {
        envelope.record_id: hashlib.sha256(envelope.canonical_bytes()).hexdigest()
        for envelope in store.records()
    }


def _role_integrity(role: str, command: object) -> dict[str, object]:
    return {
        "role": role,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "private_key_input_paths": _private_material_paths(command),
        "scorer_field_paths": _forbidden_scorer_paths(command),
    }


def _reply(
    *,
    role: str,
    command: object,
    result: object | None = None,
    error: BaseException | None = None,
) -> None:
    response: dict[str, object] = {
        "ok": error is None,
        "role": role,
        "integrity": _role_integrity(role, command),
    }
    if error is None:
        response["result"] = result
    else:
        chain: list[str] = []
        current: BaseException | None = error
        while current is not None and len(chain) < 8:
            chain.append(f"{type(current).__name__}:{current}")
            current = current.__cause__ or current.__context__
        response.update(
            {
                "error_type": type(error).__name__,
                "error": str(error)[:1_000],
                "error_chain": chain,
            }
        )
    print(json.dumps(response, sort_keys=True), flush=True)


def _source_handler() -> Callable[[Mapping[str, object]], object]:
    signing_key = Ed25519PrivateKey.generate()
    public_key = signing_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    def handle(command: Mapping[str, object]) -> object:
        operation = command.get("op")
        if operation == "describe":
            return {
                "source_producer": SOURCE_PRODUCER,
                "issuer_private_key_process_local": True,
                "issuer_private_key_exported": False,
            }
        if operation == "issue":
            events = {
                event_id: _issue_event(
                    signing_key, event_id=event_id, policy_key=policy_key
                ).as_dict()
                for event_id, policy_key in _source_specs()
            }
            return {
                "issuer_id": ISSUER_ID,
                "issuer_key_id": ISSUER_KEY_ID,
                "public_key_hex": public_key.hex(),
                "events": events,
                "event_set_sha256": _sha256(events),
                "issuer_private_key_exported": False,
            }
        raise RuntimeError(f"UNKNOWN_SOURCE_OPERATION:{operation}")

    return handle


def _policy_handler(
    store: FirestoreAuthorityStore,
) -> Callable[[Mapping[str, object]], object]:
    def handle(command: Mapping[str, object]) -> object:
        operation = command.get("op")
        if operation == "describe":
            return {"authoritative_store": "FirestoreAuthorityStore"}
        if operation == "bootstrap":
            store.put_issuer_key(
                issuer_id=ISSUER_ID,
                issuer_key_id=ISSUER_KEY_ID,
                public_key=bytes.fromhex(str(command["public_key_hex"])),
            )
            for snapshot in _policies():
                store.put_policy(snapshot)
            return {
                "issuer_key_stored": True,
                "policy_digests": [item.policy_key.digest for item in _policies()],
            }
        if operation == "advance_stale_generation":
            store.put_policy(
                PolicySnapshot(
                    STALE_SOURCE,
                    "stale-v2",
                    2,
                    OperationRole.ORIGIN,
                    {ACTION_SCOPE: Capability.ACT},
                ),
                expected_generation=1,
            )
            return {"policy_key_digest": STALE_SOURCE.digest, "generation": 2}
        if operation == "revoke":
            root_keys: list[ReceiptRootKey] = []
            for root_id in command["root_ids"]:  # type: ignore[index]
                envelope = store.envelope(str(root_id))
                if envelope is None or envelope.authority_receipt is None:
                    raise RuntimeError(f"MISSING_AUTHENTICATED_ROOT:{root_id}")
                root_keys.append(
                    ReceiptRootKey.from_receipt(
                        envelope.authority_receipt,
                        custody_root_record_id=envelope.record_id,
                    )
                )
            result = RevocationController(store).revoke_receipt_roots(
                revocation_id=str(command["revocation_id"]),
                root_keys=tuple(root_keys),
            )
            return {
                "revocation": result.revocation.as_dict(),
                "affected_record_ids": list(result.affected_record_ids),
            }
        raise RuntimeError(f"UNKNOWN_POLICY_OPERATION:{operation}")

    return handle


def _memory_handler(
    store: FirestoreAuthorityStore,
) -> Callable[[Mapping[str, object]], object]:
    gate = _gate(store)

    def handle(command: Mapping[str, object]) -> object:
        operation = command.get("op")
        if operation == "describe":
            return {"admission_api": "AdmissionGate"}
        if operation == "admit_sources":
            observations: dict[str, object] = {}
            for item in command["items"]:  # type: ignore[index]
                event = SourceAuthorityEvent.from_mapping(item["event"])
                record_id = str(item["record_id"])
                result = gate.admit_source(
                    event,
                    AuthorityOutput(record_id, event.source_object_commitment),
                )
                observations[record_id] = _admission_observation(result)
            return observations
        if operation == "derive":
            observations = {}
            for item in command["items"]:  # type: ignore[index]
                kind = str(item["kind"])
                record_id = str(item["record_id"])
                parent_ids = tuple(str(value) for value in item["parent_ids"])
                if kind == "IDENTITY":
                    parent = store.envelope(parent_ids[0])
                    if parent is None:
                        raise RuntimeError(f"MISSING_IDENTITY_PARENT:{parent_ids[0]}")
                    result = gate.admit_identity(
                        parent_ids[0],
                        AuthorityOutput(record_id, parent.payload_digest),
                    )
                elif kind == "REGISTERED":
                    result = gate.admit_registered(
                        TransformRef(REGISTERED),
                        parent_ids,
                        AuthorityOutput.from_text(
                            record_id=record_id, text=str(item["output_text"])
                        ),
                    )
                elif kind == "FREEFORM":
                    result = gate.admit_freeform(
                        parent_ids,
                        AuthorityOutput.from_text(
                            record_id=record_id, text=str(item["output_text"])
                        ),
                    )
                else:
                    raise RuntimeError(f"UNKNOWN_TRANSFORM_CLASS:{kind}")
                observations[record_id] = _admission_observation(result)
            return observations
        if operation == "snapshot":
            record_ids = tuple(str(value) for value in command["record_ids"])
            return {
                "records": _graph_observation(store, record_ids),
                "history": _history(store),
            }
        if operation == "probe_receipt":
            event = SourceAuthorityEvent.from_mapping(command["event"])
            record_id = str(command["record_id"])
            return {
                "record": _graph_observation(store, (record_id,))[record_id],
                "receipt_bound_root": store.root_record_id_for_receipt(event.receipt),
            }
        raise RuntimeError(f"UNKNOWN_MEMORY_OPERATION:{operation}")

    return handle


class _TraceDispatcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def dispatch(self, action: AuthorityAction) -> object:
        self.calls.append(action.request_id)
        return {"request_id": action.request_id, "test_sink": "dispatched"}


def _gateway_handler(
    store: FirestoreAuthorityStore,
) -> Callable[[Mapping[str, object]], object]:
    gateway = AuthorityGateway(store)
    dispatcher = _TraceDispatcher()
    prepared: dict[str, tuple[AuthorityAction, tuple[str, ...]]] = {}

    def action_from(command: Mapping[str, object]) -> AuthorityAction:
        return AuthorityAction(
            request_id=str(command["request_id"]),
            action_scope=str(command.get("action_scope", ACTION_SCOPE)),
            payload={
                "destination": "p7-test-sink",
                "request_ref": str(command["request_id"]),
            },
        )

    def execute(
        action: AuthorityAction, citations: tuple[str, ...]
    ) -> dict[str, object]:
        observation = _execution_observation(
            gateway.execute(action, citations, dispatcher)
        )
        observation["dispatch_calls"] = list(dispatcher.calls)
        return observation

    def handle(command: Mapping[str, object]) -> object:
        operation = command.get("op")
        if operation == "describe":
            return {"gateway_api": "AuthorityGateway"}
        if operation == "action":
            citations = tuple(str(value) for value in command["record_ids"])
            return execute(action_from(command), citations)
        if operation == "prepare_action":
            token = str(command["token"])
            if token in prepared:
                raise RuntimeError("PREPARED_ACTION_TOKEN_REUSED")
            prepared[token] = (
                action_from(command),
                tuple(str(value) for value in command["record_ids"]),
            )
            return {"token": token, "prepared": True, "state_read": False}
        if operation == "execute_prepared":
            token = str(command["token"])
            action, citations = prepared.pop(token)
            return execute(action, citations)
        raise RuntimeError(f"UNKNOWN_GATEWAY_OPERATION:{operation}")

    return handle


def _role_main(role: str, *, commit_barrier: bool) -> int:
    if role == "SOURCE":
        handler = _source_handler()
        raw_client = None
    else:
        raw_client = _client()

        def on_staged(write_count: int) -> None:
            _reply(
                role=role,
                command={"op": "crash_admission"},
                result={
                    "status": "TRANSACTION_STAGED_BEFORE_COMMIT_RPC",
                    "staged_write_count": write_count,
                },
            )

        store = _store(
            raw_client,
            on_staged=on_staged if commit_barrier else None,
        )
        handlers = {
            "MEMORY": _memory_handler,
            "POLICY": _policy_handler,
            "GATEWAY": _gateway_handler,
        }
        handler = handlers[role](store)

    try:
        for line in sys.stdin:
            command: object = {}
            try:
                parsed = json.loads(line)
                if not isinstance(parsed, Mapping):
                    raise RuntimeError("ROLE_COMMAND_MUST_BE_OBJECT")
                command = parsed
                if parsed.get("op") == "shutdown":
                    _reply(role=role, command=command, result={"shutdown": True})
                    return 0
                forbidden = _forbidden_scorer_paths(command)
                if forbidden:
                    raise RuntimeError(
                        f"SCORER_FIELD_ENTERED_ROLE:{','.join(forbidden)}"
                    )
                private_paths = _private_material_paths(command)
                if role != "SOURCE" and private_paths:
                    raise RuntimeError(
                        f"PRIVATE_KEY_ENTERED_ROLE:{','.join(private_paths)}"
                    )
                _reply(role=role, command=command, result=handler(parsed))
            except BaseException as error:  # role boundary must report exact failure
                _reply(role=role, command=command, error=error)
    finally:
        if raw_client is not None:
            raw_client.close()
    return 0


class _RoleProcess:
    """Line protocol for one independently started P7 role process."""

    def __init__(self, role: str, *, commit_barrier: bool = False) -> None:
        command = [
            sys.executable,
            "-m",
            "live.b7_production_equivalence",
            "--role",
            role,
        ]
        if commit_barrier:
            command.append("--commit-barrier")
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        self.role = role
        self.trace_entry: dict[str, object] | None = None
        self.process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        _ACTIVE_ROLE_PROCESSES.append(self)
        self.responses: list[dict[str, object]] = []
        self.startup = self.request({"op": "describe"}, timeout=30)

    @property
    def pid(self) -> int:
        return self.process.pid

    def send(self, command: Mapping[str, object]) -> None:
        if self.process.poll() is not None:
            raise RuntimeError(f"ROLE_EXITED:{self.role}:{self._stderr_tail()}")
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(command, sort_keys=True) + "\n")
        self.process.stdin.flush()

    def receive(
        self, *, timeout: float, permit_error: bool = False
    ) -> dict[str, object]:
        assert self.process.stdout is not None
        ready, _, _ = select.select([self.process.stdout], [], [], max(0.0, timeout))
        if not ready:
            raise TimeoutError(f"ROLE_RESPONSE_TIMEOUT:{self.role}")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f"ROLE_NO_RESPONSE:{self.role}:{self._stderr_tail()}")
        response = json.loads(line)
        self.responses.append(response)
        if self.trace_entry is not None:
            audits = self.trace_entry.setdefault("command_audits", [])
            assert isinstance(audits, list)
            audits.append(response.get("integrity", {}))
        if not response.get("ok") and not permit_error:
            raise RuntimeError(
                f"ROLE_COMMAND_FAILED:{self.role}:"
                f"{response.get('error_type')}:{response.get('error')}"
            )
        return response

    def request(
        self,
        command: Mapping[str, object],
        *,
        timeout: float = 60,
        permit_error: bool = False,
    ) -> dict[str, object]:
        self.send(command)
        return self.receive(timeout=timeout, permit_error=permit_error)

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.request({"op": "shutdown"}, timeout=10, permit_error=True)
            except (RuntimeError, TimeoutError):
                self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        if self in _ACTIVE_ROLE_PROCESSES:
            _ACTIVE_ROLE_PROCESSES.remove(self)

    def kill_at_barrier(self) -> dict[str, object]:
        response = self.receive(timeout=60)
        self.process.send_signal(signal.SIGKILL)
        self.process.wait(timeout=10)
        return {
            "barrier": response,
            "return_code": self.process.returncode,
            "killed": self.process.returncode == -signal.SIGKILL,
        }

    def _stderr_tail(self) -> str:
        if self.process.stderr is None:
            return ""
        return self.process.stderr.read()[-2_000:]


_ACTIVE_ROLE_PROCESSES: list[_RoleProcess] = []


def _close_all_roles() -> None:
    for process in tuple(_ACTIVE_ROLE_PROCESSES):
        process.close()


def _result(response: Mapping[str, object]) -> Any:
    if not response.get("ok"):
        raise RuntimeError(
            f"ROLE_ERROR:{response.get('role')}:"
            f"{response.get('error_type')}:{response.get('error')}"
        )
    return response["result"]


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _production_hashes() -> dict[str, str]:
    paths = (
        "custody/authority.py",
        "custody/action.py",
        "custody/store.py",
        "custody/firestore_store.py",
    )
    return {path: _file_sha256(ROOT / path) for path in paths}


def _git_preflight() -> dict[str, object]:
    head = _git("rev-parse", "HEAD")
    ancestor = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", PRODUCTION_B7_SHA, head],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )
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
    return {
        "head": head,
        "production_sha_is_ancestor": ancestor,
        "production_file_commit_diff": production_diff.splitlines()
        if production_diff
        else [],
        "tracked_worktree_dirty": tracked_dirty.splitlines() if tracked_dirty else [],
        "production_hashes": _production_hashes(),
    }


def _namespace_counts(client: firestore.Client) -> dict[str, int]:
    return {
        name: sum(1 for _ in client.collection(prefixed).stream())
        for name, prefixed in _collection_plan().items()
    }


def _namespace_manifest(client: firestore.Client) -> dict[str, object]:
    manifest: dict[str, object] = {}
    for logical, collection_name in _collection_plan().items():
        documents = []
        for snapshot in client.collection(collection_name).stream():
            documents.append(
                {
                    "id": snapshot.id,
                    "data_sha256": _sha256(_json_safe(snapshot.to_dict())),
                }
            )
        manifest[logical] = sorted(documents, key=lambda item: item["id"])
    return manifest


def _preflight(*, require_empty: bool) -> dict[str, object]:
    client = _client()
    try:
        counts = _namespace_counts(client)
    finally:
        client.close()
    git = _git_preflight()
    valid = (
        git["production_sha_is_ancestor"]
        and not git["production_file_commit_diff"]
        and not git["tracked_worktree_dirty"]
        and (not require_empty or all(count == 0 for count in counts.values()))
    )
    return {
        "valid": valid,
        "project": PROJECT_ID,
        "database": DATABASE_ID,
        "database_class": "FIRESTORE_NATIVE",
        "region": REGION,
        "run_id": RUN_ID,
        "namespace_prefix": COLLECTION_PREFIX,
        "collection_plan": _collection_plan(),
        "initial_collection_counts": counts,
        "source_producer": SOURCE_PRODUCER,
        "estimated_reads": ESTIMATED_READS,
        "estimated_writes": ESTIMATED_WRITES,
        "estimated_deletes": ESTIMATED_DELETES,
        "estimated_monetary_cost_usd": ESTIMATED_COST_USD,
        "cost_ceiling_usd": COST_CEILING_USD,
        "max_runtime_seconds": MAX_RUNTIME_SECONDS,
        "recovery_bound_seconds": RECOVERY_BOUND_SECONDS,
        "pricing_basis": {
            "reads_per_100k_usd": 0.03,
            "writes_per_100k_usd": 0.09,
            "deletes_per_100k_usd": 0.01,
            "source": "https://cloud.google.com/firestore/pricing",
        },
        "git": git,
    }


def _record_process(
    trace: dict[str, object], process: _RoleProcess, phase: str
) -> None:
    processes = trace.setdefault("processes", [])
    assert isinstance(processes, list)
    entry: dict[str, object] = {
        "phase": phase,
        "role": process.role,
        "pid": process.pid,
        "startup": process.startup,
        "command_audits": [process.startup.get("integrity", {})],
    }
    process.trace_entry = entry
    processes.append(entry)


def _event(trace: dict[str, object], name: str, **details: object) -> None:
    events = trace.setdefault("ordering_events", [])
    assert isinstance(events, list)
    events.append(
        {
            "sequence": len(events) + 1,
            "name": name,
            "observed_at": _utc_now(),
            **details,
        }
    )


def _tampered_events(events: Mapping[str, object]) -> tuple[dict, dict]:
    forged = json.loads(json.dumps(events["event-009"]))
    signature = forged["receipt"]["issuer_signature"]
    forged["receipt"]["issuer_signature"] = (
        "1" if signature[0] != "1" else "2"
    ) + signature[1:]
    wrong_object = json.loads(json.dumps(events["event-010"]))
    wrong_object["source_object"]["value"] = "fixture-value-object-mismatch"
    return forged, wrong_object


def _action_command(
    request_id: str,
    record_id: str,
    *,
    action_scope: str = ACTION_SCOPE,
) -> dict[str, object]:
    return {
        "op": "action",
        "request_id": request_id,
        "action_scope": action_scope,
        "record_ids": [record_id],
    }


def _run_actions(
    gateway: _RoleProcess,
    cases: Mapping[str, tuple[str, str]],
) -> dict[str, object]:
    observations = {}
    for case_id, (record_id, scope) in cases.items():
        observations[case_id] = _result(
            gateway.request(
                _action_command(f"p7-{case_id}", record_id, action_scope=scope),
                timeout=90,
            )
        )
    return observations


def _execute_treatment(preflight: Mapping[str, object]) -> dict[str, object]:
    started = time.monotonic()
    trace: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "production_b7_sha": PRODUCTION_B7_SHA,
        "runner_commit": _git("rev-parse", "HEAD"),
        "source_producer": SOURCE_PRODUCER,
        "preflight": preflight,
        "treatment_started_at": _utc_now(),
        "treatment_scorer_reads": 0,
        "raw_trace_frozen_before_scoring": True,
        "model_api_calls": 0,
        "runner_source_sha256_before_treatment": _file_sha256(Path(__file__)),
        "gate_source_sha256_before_treatment": _file_sha256(GATE_MODULE),
    }

    source = _RoleProcess("SOURCE")
    _record_process(trace, source, "SOURCE_ISSUANCE")
    issued = _result(source.request({"op": "issue"}))
    source.close()
    events = issued["events"]
    trace["source"] = issued
    _event(trace, "SOURCE_EVENTS_ISSUED", producer_pid=source.pid)

    policy = _RoleProcess("POLICY")
    _record_process(trace, policy, "POLICY_BOOTSTRAP")
    bootstrap = _result(
        policy.request(
            {"op": "bootstrap", "public_key_hex": issued["public_key_hex"]},
            timeout=90,
        )
    )
    policy.close()
    trace["bootstrap"] = bootstrap
    _event(trace, "TRUST_AND_POLICIES_AUTHORITATIVE")

    forged, wrong_object = _tampered_events(events)
    source_items = (
        ("R_PRE", "event-001"),
        ("R_BAD_1", "event-002"),
        ("R_BAD_2", "event-003"),
        ("R_POST", "event-004"),
        ("R_OTHER", "event-005"),
        ("R_REPLAY", "event-006"),
        ("R_STALE", "event-007"),
    )
    memory = _RoleProcess("MEMORY")
    _record_process(trace, memory, "ADMISSION")
    admissions = _result(
        memory.request(
            {
                "op": "admit_sources",
                "items": [
                    {"record_id": record_id, "event": events[event_id]}
                    for record_id, event_id in source_items
                ],
            },
            timeout=180,
        )
    )
    controls = _result(
        memory.request(
            {
                "op": "admit_sources",
                "items": [
                    {"record_id": "FORGED_ROOT", "event": forged},
                    {"record_id": "WRONG_OBJECT_ROOT", "event": wrong_object},
                    {
                        "record_id": "R_REPLAY_ALIAS",
                        "event": events["event-006"],
                    },
                ],
            },
            timeout=120,
        )
    )
    derivations = _result(
        memory.request(
            {
                "op": "derive",
                "items": [
                    {
                        "kind": "IDENTITY",
                        "record_id": "D_PRE",
                        "parent_ids": ["R_PRE"],
                    },
                    {
                        "kind": "REGISTERED",
                        "record_id": "D_BAD1",
                        "parent_ids": ["R_BAD_1"],
                        "output_text": "registered-output-001",
                    },
                    {
                        "kind": "IDENTITY",
                        "record_id": "D_BAD2",
                        "parent_ids": ["R_BAD_2"],
                    },
                    {
                        "kind": "IDENTITY",
                        "record_id": "D_POST",
                        "parent_ids": ["R_POST"],
                    },
                    {
                        "kind": "REGISTERED",
                        "record_id": "D_OTHER",
                        "parent_ids": ["R_OTHER"],
                        "output_text": "registered-output-002",
                    },
                    {
                        "kind": "REGISTERED",
                        "record_id": "D_MIX",
                        "parent_ids": ["R_BAD_1", "R_OTHER"],
                        "output_text": "registered-output-003",
                    },
                    {
                        "kind": "IDENTITY",
                        "record_id": "AGENT_A_BAD_CHILD",
                        "parent_ids": ["R_BAD_1"],
                    },
                    {
                        "kind": "IDENTITY",
                        "record_id": "AGENT_B_BAD_CHILD",
                        "parent_ids": ["AGENT_A_BAD_CHILD"],
                    },
                    {
                        "kind": "FREEFORM",
                        "record_id": "D_FREEFORM",
                        "parent_ids": ["R_OTHER"],
                        "output_text": "freeform-output-001",
                    },
                    {
                        "kind": "REGISTERED",
                        "record_id": "D_MIX_INVALID",
                        "parent_ids": ["R_OTHER", "D_FREEFORM"],
                        "output_text": "registered-output-004",
                    },
                ],
            },
            timeout=240,
        )
    )
    memory.close()
    trace["admissions"] = admissions
    trace["control_admissions"] = controls
    trace["derivations"] = derivations
    _event(trace, "ADMISSION_AND_DERIVATION_COMPLETE")

    stale_policy = _RoleProcess("POLICY")
    _record_process(trace, stale_policy, "GENERATION_ADVANCE")
    trace["stale_generation_advance"] = _result(
        stale_policy.request({"op": "advance_stale_generation"}, timeout=90)
    )
    stale_policy.close()
    _event(trace, "STALE_CONTROL_POLICY_ADVANCED")

    graph_reader = _RoleProcess("MEMORY")
    _record_process(trace, graph_reader, "DURABLE_RECONSTRUCTION_BEFORE")
    graph_ids = (
        "R_PRE",
        "R_BAD_1",
        "R_BAD_2",
        "R_POST",
        "R_OTHER",
        "D_PRE",
        "D_BAD1",
        "D_BAD2",
        "D_POST",
        "D_OTHER",
        "D_MIX",
        "AGENT_A_BAD_CHILD",
        "AGENT_B_BAD_CHILD",
        "D_FREEFORM",
        "D_MIX_INVALID",
    )
    before_snapshot = _result(
        graph_reader.request(
            {"op": "snapshot", "record_ids": list(graph_ids)}, timeout=180
        )
    )
    graph_reader.close()
    trace["before_snapshot"] = before_snapshot
    _event(trace, "FRESH_PROCESS_RECONSTRUCTED_DURABLE_GRAPH")

    gateway = _RoleProcess("GATEWAY")
    _record_process(trace, gateway, "GATEWAY_BEFORE_REVOCATION")
    before_cases = {
        "before_pre": ("D_PRE", ACTION_SCOPE),
        "before_bad1": ("D_BAD1", ACTION_SCOPE),
        "before_bad2": ("D_BAD2", ACTION_SCOPE),
        "before_post": ("D_POST", ACTION_SCOPE),
        "before_other": ("D_OTHER", ACTION_SCOPE),
        "before_mix": ("D_MIX", ACTION_SCOPE),
        "identity_legitimate": ("D_PRE", ACTION_SCOPE),
        "registered_legitimate": ("D_OTHER", ACTION_SCOPE),
        "freeform_laundering": ("D_FREEFORM", ACTION_SCOPE),
        "mixed_invalid_support": ("D_MIX_INVALID", ACTION_SCOPE),
        "cross_agent_before": ("AGENT_B_BAD_CHILD", ACTION_SCOPE),
        "forged_receipt": ("FORGED_ROOT", ACTION_SCOPE),
        "wrong_object": ("WRONG_OBJECT_ROOT", ACTION_SCOPE),
        "wrong_scope": ("D_OTHER", "payroll.read"),
        "stale_generation": ("R_STALE", ACTION_SCOPE),
        "unrelated_replay": ("R_REPLAY_ALIAS", ACTION_SCOPE),
    }
    before_actions = _run_actions(gateway, before_cases)
    gateway.close()
    trace["before_actions"] = before_actions
    _event(trace, "PRE_REVOCATION_ACTIONS_COMPLETE")

    stale_gateway = _RoleProcess("GATEWAY")
    _record_process(trace, stale_gateway, "ACTION_REVOCATION_RACE")
    prepared = _result(
        stale_gateway.request(
            {
                "op": "prepare_action",
                "token": "race-token-001",
                "request_id": "p7-race-after-authoritative-revocation",
                "action_scope": ACTION_SCOPE,
                "record_ids": ["AGENT_B_BAD_CHILD"],
            }
        )
    )
    trace["race_prepared"] = prepared
    _event(
        trace,
        "STALE_GATEWAY_PREPARED_ACTION",
        gateway_pid=stale_gateway.pid,
        authoritative_state_read=False,
    )

    revoker = _RoleProcess("POLICY")
    _record_process(trace, revoker, "SELECTIVE_REVOCATION")
    revocation = _result(
        revoker.request(
            {
                "op": "revoke",
                "revocation_id": "p7-selective-revocation-001",
                "root_ids": ["R_BAD_1", "R_BAD_2"],
            },
            timeout=180,
        )
    )
    revoker.close()
    trace["revocation"] = revocation
    _event(trace, "SELECTIVE_REVOCATION_AUTHORITATIVE")

    fresh_gateway = _RoleProcess("GATEWAY")
    _record_process(trace, fresh_gateway, "GATEWAY_AFTER_REVOCATION")
    after_cases = {
        "after_bad1": ("D_BAD1", ACTION_SCOPE),
        "after_bad2": ("D_BAD2", ACTION_SCOPE),
        "after_mix": ("D_MIX", ACTION_SCOPE),
        "after_cross_agent": ("AGENT_B_BAD_CHILD", ACTION_SCOPE),
        "after_pre": ("D_PRE", ACTION_SCOPE),
        "after_post": ("D_POST", ACTION_SCOPE),
        "after_other": ("D_OTHER", ACTION_SCOPE),
    }
    after_actions = _run_actions(fresh_gateway, after_cases)
    fresh_gateway.close()
    trace["after_actions"] = after_actions
    _event(trace, "FRESH_GATEWAY_POST_REVOCATION_ACTIONS_COMPLETE")

    race_action = _result(
        stale_gateway.request(
            {"op": "execute_prepared", "token": "race-token-001"}, timeout=90
        )
    )
    stale_gateway.close()
    trace["race_action"] = race_action
    _event(
        trace,
        "STALE_GATEWAY_EXECUTED_AFTER_REVOCATION_COMMIT",
        gateway_pid=stale_gateway.pid,
    )

    after_reader = _RoleProcess("MEMORY")
    _record_process(trace, after_reader, "DURABLE_RECONSTRUCTION_AFTER")
    after_snapshot = _result(
        after_reader.request(
            {"op": "snapshot", "record_ids": list(graph_ids)}, timeout=180
        )
    )
    after_reader.close()
    trace["after_snapshot"] = after_snapshot
    _event(trace, "POST_REVOCATION_HISTORY_REREAD")

    crash_writer = _RoleProcess("MEMORY", commit_barrier=True)
    _record_process(trace, crash_writer, "CRASH_BEFORE_COMMIT")
    crash_writer.send(
        {
            "op": "admit_sources",
            "items": [{"record_id": "R_CRASH", "event": events["event-008"]}],
        }
    )
    crash = crash_writer.kill_at_barrier()
    killed_at = time.monotonic()
    trace["crash"] = crash
    _event(trace, "WRITER_KILLED_BEFORE_COMMIT_RPC", writer_pid=crash_writer.pid)

    crash_reader = _RoleProcess("MEMORY")
    _record_process(trace, crash_reader, "POST_KILL_RECONSTRUCTION")
    post_kill_probe = _result(
        crash_reader.request(
            {
                "op": "probe_receipt",
                "record_id": "R_CRASH",
                "event": events["event-008"],
            },
            timeout=90,
        )
    )
    crash_reader.close()
    trace["post_kill_probe"] = post_kill_probe

    crash_gateway = _RoleProcess("GATEWAY")
    _record_process(trace, crash_gateway, "POST_KILL_GATEWAY")
    immediate_action = _result(
        crash_gateway.request(
            _action_command("p7-immediate-post-kill", "R_CRASH"), timeout=90
        )
    )
    crash_gateway.close()
    trace["immediate_post_kill_action"] = immediate_action
    _event(trace, "IMMEDIATE_POST_KILL_CHECK_COMPLETE")

    recovery_started = time.monotonic()
    crash["post_kill_inspection_seconds"] = recovery_started - killed_at
    recovery = _RoleProcess("MEMORY")
    _record_process(trace, recovery, "RECOVERY")
    remaining = max(
        0.001,
        RECOVERY_BOUND_SECONDS - (time.monotonic() - recovery_started),
    )
    recovery.send(
        {
            "op": "admit_sources",
            "items": [{"record_id": "R_CRASH", "event": events["event-008"]}],
        }
    )
    recovery_response: dict[str, object]
    recovery_timed_out = False
    try:
        recovery_response = recovery.receive(timeout=remaining, permit_error=True)
    except TimeoutError as error:
        recovery_timed_out = True
        recovery_response = {
            "ok": False,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    recovery_elapsed = time.monotonic() - recovery_started
    recovery.close()
    trace["recovery"] = {
        "response": recovery_response,
        "timed_out": recovery_timed_out,
        "elapsed_seconds": recovery_elapsed,
        "bound_seconds": RECOVERY_BOUND_SECONDS,
    }
    _event(trace, "RECOVERY_ATTEMPT_COMPLETE")

    final_reader = _RoleProcess("MEMORY")
    _record_process(trace, final_reader, "FINAL_RECONSTRUCTION")
    final_snapshot = _result(
        final_reader.request(
            {
                "op": "snapshot",
                "record_ids": [*graph_ids, "R_CRASH"],
            },
            timeout=180,
        )
    )
    final_probe = _result(
        final_reader.request(
            {
                "op": "probe_receipt",
                "record_id": "R_CRASH",
                "event": events["event-008"],
            },
            timeout=90,
        )
    )
    final_reader.close()
    trace["final_snapshot"] = final_snapshot
    trace["final_crash_probe"] = final_probe

    final_gateway = _RoleProcess("GATEWAY")
    _record_process(trace, final_gateway, "FINAL_GATEWAY")
    recovery_action = _result(
        final_gateway.request(
            _action_command("p7-recovery-action", "R_CRASH"), timeout=90
        )
    )
    final_gateway.close()
    trace["recovery_action"] = recovery_action

    raw_client = _client()
    try:
        trace["namespace_manifest_before_cleanup"] = _namespace_manifest(raw_client)
    finally:
        raw_client.close()
    trace["treatment_completed_at"] = _utc_now()
    trace["runtime_seconds"] = time.monotonic() - started
    trace["production_hashes_after_treatment"] = _production_hashes()
    trace["runner_source_sha256_after_treatment"] = _file_sha256(Path(__file__))
    trace["gate_source_sha256_after_treatment"] = _file_sha256(GATE_MODULE)
    trace["payload_semantic_authority_inspection"] = False
    trace["scorer_leakage"] = False
    _event(trace, "RAW_TREATMENT_COMPLETE")
    return trace


def _cleanup_namespace() -> dict[str, object]:
    client = _client()
    deleted: dict[str, int] = {}
    try:
        for logical, collection_name in _collection_plan().items():
            count = 0
            for snapshot in client.collection(collection_name).stream():
                snapshot.reference.delete()
                count += 1
            deleted[logical] = count
        final_counts = _namespace_counts(client)
    finally:
        client.close()
    return {
        "run_id": RUN_ID,
        "namespace_prefix": COLLECTION_PREFIX,
        "deleted_documents": deleted,
        "final_collection_counts": final_counts,
        "cleanup_complete": all(count == 0 for count in final_counts.values()),
        "cleaned_at": _utc_now(),
    }


def _score_raw_trace(raw_path: Path, output_path: Path, *extra: str) -> None:
    subprocess.run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--raw",
            str(raw_path),
            "--out",
            str(output_path),
            *extra,
        ],
        cwd=ROOT,
        check=True,
    )


def _freeze_score_cleanup(trace: dict[str, object]) -> dict[str, object]:
    _write_json(RAW_TRACE_PATH, trace)
    raw_digest = _file_sha256(RAW_TRACE_PATH)
    first = RESULT_PATH.with_name(f".{RESULT_PATH.name}.score-a")
    second = RESULT_PATH.with_name(f".{RESULT_PATH.name}.score-b")
    _score_raw_trace(RAW_TRACE_PATH, first)
    _score_raw_trace(RAW_TRACE_PATH, second)
    score_a_digest = _file_sha256(first)
    score_b_digest = _file_sha256(second)
    recomputation_match = score_a_digest == score_b_digest

    cleanup = _cleanup_namespace()
    _write_json(CLEANUP_PATH, cleanup)
    _score_raw_trace(
        RAW_TRACE_PATH,
        RESULT_PATH,
        "--cleanup",
        str(CLEANUP_PATH),
        "--recomputation-match",
        "true" if recomputation_match else "false",
        "--score-digest",
        score_a_digest,
    )
    first.unlink()
    second.unlink()
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if result.get("raw_trace_digest") != raw_digest:
        raise RuntimeError("FINAL_RESULT_RAW_TRACE_DIGEST_MISMATCH")
    return result


def _print_plan(preflight: Mapping[str, object]) -> None:
    print(
        json.dumps(
            {
                "gcp_project": PROJECT_ID,
                "firestore_database": DATABASE_ID,
                "region": REGION,
                "collection_namespace_plan": _collection_plan(),
                "estimated_reads": ESTIMATED_READS,
                "estimated_writes": ESTIMATED_WRITES,
                "estimated_deletes": ESTIMATED_DELETES,
                "estimated_monetary_cost_usd": ESTIMATED_COST_USD,
                "cost_ceiling_usd": COST_CEILING_USD,
                "preflight_valid": preflight["valid"],
            },
            sort_keys=True,
            indent=2,
        ),
        flush=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("SOURCE", "MEMORY", "POLICY", "GATEWAY"))
    parser.add_argument("--commit-barrier", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    arguments = parser.parse_args(argv)

    if arguments.role:
        if arguments.commit_barrier and arguments.role != "MEMORY":
            parser.error("--commit-barrier is valid only for MEMORY")
        return _role_main(arguments.role, commit_barrier=arguments.commit_barrier)
    if sum((arguments.preflight, arguments.execute, arguments.cleanup)) != 1:
        parser.error("choose exactly one of --preflight, --execute, --cleanup")
    if arguments.cleanup:
        cleanup = _cleanup_namespace()
        print(json.dumps(cleanup, sort_keys=True, indent=2))
        return 0 if cleanup["cleanup_complete"] else 2

    preflight = _preflight(require_empty=True)
    _print_plan(preflight)
    if arguments.preflight:
        return 0 if preflight["valid"] else 2
    if not preflight["valid"]:
        print("P7_PREFLIGHT_BLOCKED", file=sys.stderr)
        return 2

    def runtime_expired(_signum: int, _frame: object) -> None:
        raise TimeoutError("P7_MAX_RUNTIME_EXCEEDED")

    previous_alarm_handler = signal.signal(signal.SIGALRM, runtime_expired)
    signal.setitimer(signal.ITIMER_REAL, MAX_RUNTIME_SECONDS)
    try:
        trace = _execute_treatment(preflight)
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_alarm_handler)
        _close_all_roles()
        failure = {
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "production_b7_sha": PRODUCTION_B7_SHA,
            "runner_commit": _git("rev-parse", "HEAD"),
            "preflight": preflight,
            "execution_status": "INVALID_RUNNER_ATTEMPT",
            "error_type": type(error).__name__,
            "error": str(error)[:2_000],
            "failed_at": _utc_now(),
            "raw_trace_frozen_before_scoring": True,
            "treatment_scorer_reads": 0,
            "production_hashes_after_treatment": _production_hashes(),
        }
        result = _freeze_score_cleanup(failure)
        print(json.dumps(result, sort_keys=True, indent=2), file=sys.stderr)
        return 2

    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous_alarm_handler)
    _close_all_roles()
    result = _freeze_score_cleanup(trace)
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "raw_trace_digest": result["raw_trace_digest"],
                "canonical_result_digest": result["canonical_result_digest"],
                "cleanup_complete": result["cleanup"]["cleanup_complete"],
            },
            sort_keys=True,
            indent=2,
        )
    )
    return (
        0
        if result["verdict"]
        in {
            "PRODUCTION-B7-LIVE-EQUIVALENCE-SUPPORTED",
            "PRODUCTION-B7-SECURITY-SUPPORTED-LIVENESS-LIMITATION",
            "PRODUCTION-B7-SECURITY-FAIL",
            "PRODUCTION-B7-UTILITY-FAIL",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
