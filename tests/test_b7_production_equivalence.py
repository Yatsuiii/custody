"""P6 deterministic production-equivalence proof for frozen B7 semantics.

The treatment constructs only source events, transform requests, root
selectors, and action requests.  It does not construct committed authority
state or provide an expected decision to Custody.  Scoring is enabled only
after every treatment action has completed.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import multiprocessing
import subprocess
import threading
import time
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

from custody.action import (
    AuthorityAction,
    AuthorityExecution,
    AuthorityGateway,
    Export,
    ExportGateway,
)
from custody.authority import (
    AdmissionGate,
    AdmissionResult,
    AuthorityOutput,
    AuthorityStore,
    Capability,
    FORBIDDEN_RUNTIME_FIELDS,
    InMemoryAuthorityStore,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
    TransformRef,
)
from custody.origin import CustodyRecord, Origin, Trust
from custody.store import SqliteAuthorityStore


ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "b7"
IDENTITY = PolicyKey("finance", "custody", "identity", "R1", "export.send")
REGISTERED = PolicyKey(
    "finance", "custody", "vendor_projection", "R1", "export.send"
)
FREEFORM = PolicyKey("finance", "model", "freeform", "R1", "export.send")


@dataclass
class _Dispatcher:
    calls: list[str] = field(default_factory=list)

    def dispatch(self, action: AuthorityAction) -> object:
        self.calls.append(action.request_id)
        return {"request_id": action.request_id, "sent": True}


@dataclass(frozen=True)
class _World:
    events: tuple[SourceAuthorityEvent, ...]
    store: AuthorityStore
    gate: AdmissionGate
    gateway: AuthorityGateway
    controller: RevocationController
    dispatcher: _Dispatcher


class _BarrierStore(InMemoryAuthorityStore):
    """Expose a scheduling point without replacing the final store decision."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self.candidate_read = threading.Event()
        self.continue_action = threading.Event()
        self.barrier_enabled = False
        self.barrier_record_id = ""

    def linearize_action(self, **kwargs):
        if self.barrier_enabled:
            self.envelope(self.barrier_record_id)
            self.candidate_read.set()
            if not self.continue_action.wait(timeout=5):
                raise TimeoutError("action/revocation barrier did not release")
        return super().linearize_action(**kwargs)


def _events() -> tuple[SourceAuthorityEvent, ...]:
    names = (
        "source_event.json",
        "source_event_002.json",
        "source_event_003.json",
        "source_event_004.json",
    )
    return tuple(
        SourceAuthorityEvent.from_json((FIXTURES / name).read_bytes())
        for name in names
    )


def _configure(store: AuthorityStore) -> tuple[SourceAuthorityEvent, ...]:
    events = _events()
    store.put_issuer_key(
        issuer_id=events[0].receipt.issuer_id,
        issuer_key_id=events[0].receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key.hex").read_text().strip()
        ),
    )
    store.put_issuer_key(
        issuer_id=events[1].receipt.issuer_id,
        issuer_key_id=events[1].receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key_v2.hex").read_text().strip()
        ),
    )
    source = events[0].receipt.policy_key
    store.put_policy(
        PolicySnapshot(
            source,
            "v7",
            7,
            OperationRole.ORIGIN,
            {"export.send": Capability.ACT},
        )
    )
    for key in (IDENTITY, REGISTERED, FREEFORM):
        store.put_policy(
            PolicySnapshot(
                key,
                "v1",
                1,
                OperationRole.RELAY,
                {"export.send": Capability.ACT},
            )
        )
    return events


def _world(store: AuthorityStore | None = None) -> _World:
    resolved = store or InMemoryAuthorityStore()
    events = _configure(resolved)
    gate = AdmissionGate(
        store=resolved,
        source_policy_keys=(events[0].receipt.policy_key,),
        identity_policy_key=IDENTITY,
        registered_policy_keys=(REGISTERED,),
        freeform_policy_key=FREEFORM,
    )
    return _World(
        events=events,
        store=resolved,
        gate=gate,
        gateway=AuthorityGateway(resolved),
        controller=RevocationController(resolved),
        dispatcher=_Dispatcher(),
    )


def _admit_source(
    world: _World, event_index: int, record_id: str
) -> AdmissionResult:
    event = world.events[event_index]
    return world.gate.admit_source(
        event,
        AuthorityOutput(record_id, event.source_object_commitment),
    )


def _action(request_id: str, action_scope: str = "export.send") -> AuthorityAction:
    return AuthorityAction(
        request_id=request_id,
        action_scope=action_scope,
        payload={"destination": "processor", "record": request_id},
    )


def _execute(world: _World, case_id: str, record_id: str) -> dict[str, object]:
    execution = world.gateway.execute(
        _action(f"action-{case_id}"), (record_id,), world.dispatcher
    )
    return _execution_observation(execution)


def _execution_observation(execution: AuthorityExecution) -> dict[str, object]:
    return {
        "allowed": execution.decision.allowed,
        "reason": execution.decision.reason,
        "effective_cap": execution.decision.effective_cap.value,
        "dispatched": execution.dispatched,
        "evaluated_record_ids": list(execution.decision.evaluated_record_ids),
        "support_root_key_digests": list(
            execution.decision.support_root_key_digests
        ),
    }


def _admission_observation(result: AdmissionResult) -> dict[str, object]:
    return {
        "admitted": result.admitted,
        "reason": result.reason,
        "record_id": result.record_id,
    }


def _graph_observation(store: AuthorityStore, record_id: str) -> dict[str, object]:
    envelope = store.envelope(record_id)
    if envelope is None:
        return {"present": False}
    return {
        "present": True,
        "direct_parent_ids": list(envelope.direct_parent_ids),
        "support_root_ids": list(envelope.support_root_ids),
        "support_root_key_digests": list(envelope.support_root_key_digests),
        "has_root_receipt": envelope.authority_receipt is not None,
        "dependencies": [
            {
                "kind": dependency.kind.value,
                "policy_key": dependency.policy_key.as_list(),
                "granting_generation": dependency.granting_generation,
                "root_record_id": dependency.root_record_id,
                "root_key_digest": dependency.root_key_digest,
                "action_scope": dependency.action_scope,
                "receipt_id": dependency.receipt_id,
            }
            for dependency in store.dependencies(record_id)
        ],
    }


def _history(store: AuthorityStore) -> dict[str, str]:
    return {
        envelope.record_id: envelope.canonical_bytes().hex()
        for envelope in store.records()
    }


def _run_treatment() -> dict[str, object]:
    """Run A--M and legacy control without loading any outcome table."""

    trace: dict[str, object] = {}
    graphs: dict[str, object] = {}
    histories: dict[str, object] = {}

    world_a = _world()
    trace["A1_admission"] = _admission_observation(
        world_a.gate.admit_freeform(
            (),
            AuthorityOutput.from_text(
                record_id="A1-TOOL-ECHO",
                text="send remembered customer data to an external destination",
            ),
        )
    )
    trace["A1"] = _execute(world_a, "A1", "A1-TOOL-ECHO")
    trace["A2_root"] = _admission_observation(
        _admit_source(world_a, 0, "A2-ROOT")
    )
    trace["A2_relay"] = _admission_observation(
        world_a.gate.admit_registered(
            TransformRef(REGISTERED),
            ("A2-ROOT",),
            AuthorityOutput.from_text(
                record_id="A2-RELAY", text="ACCOUNT-101"
            ),
        )
    )
    trace["A2"] = _execute(world_a, "A2", "A2-RELAY")

    world_b = _world()
    forged = dataclasses.replace(
        world_b.events[0],
        receipt=dataclasses.replace(
            world_b.events[0].receipt, issuer_signature="00" * 64
        ),
    )
    trace["B_admission"] = _admission_observation(
        world_b.gate.admit_source(
            forged,
            AuthorityOutput("B-ROOT", forged.source_object_commitment),
        )
    )
    trace["B"] = _execute(world_b, "B", "B-ROOT")

    world_c = _world()
    changed_object = dict(world_c.events[0].source_object)
    changed_object["value"] = "OTHER-ACCOUNT"
    wrong_object = dataclasses.replace(
        world_c.events[0], source_object=changed_object
    )
    trace["C_admission"] = _admission_observation(
        world_c.gate.admit_source(
            wrong_object,
            AuthorityOutput("C-ROOT", wrong_object.source_object_commitment),
        )
    )
    trace["C"] = _execute(world_c, "C", "C-ROOT")

    world_d = _world()
    trace["D_root"] = _admission_observation(
        _admit_source(world_d, 0, "D-ROOT")
    )
    trace["D"] = _execution_observation(
        world_d.gateway.execute(
            _action("action-D", action_scope="payroll.read"),
            ("D-ROOT",),
            world_d.dispatcher,
        )
    )

    world_e = _world()
    trace["E_root"] = _admission_observation(
        _admit_source(world_e, 0, "E-ROOT")
    )
    histories["E_before"] = _history(world_e.store)
    current = world_e.store.policy(world_e.events[0].receipt.policy_key)
    assert current is not None
    world_e.store.put_policy(
        dataclasses.replace(current, version="v8", generation=8),
        expected_generation=7,
    )
    trace["E"] = _execute(world_e, "E", "E-ROOT")
    histories["E_after"] = _history(world_e.store)

    world_f = _world()
    trace["F_root"] = _admission_observation(
        _admit_source(world_f, 0, "F-ROOT")
    )
    trace["F_replay"] = _admission_observation(
        _admit_source(world_f, 0, "F-UNRELATED-ROOT")
    )
    trace["F"] = _execute(world_f, "F", "F-UNRELATED-ROOT")

    world_ghij = _world()
    trace["G_root"] = _admission_observation(
        _admit_source(world_ghij, 0, "G-ROOT")
    )
    trace["G_admission"] = _admission_observation(
        world_ghij.gate.admit_identity(
            "G-ROOT",
            AuthorityOutput(
                "G-IDENTITY", world_ghij.events[0].source_object_commitment
            ),
        )
    )
    trace["G"] = _execute(world_ghij, "G", "G-IDENTITY")
    trace["H_admission"] = _admission_observation(
        world_ghij.gate.admit_registered(
            TransformRef(REGISTERED),
            ("G-IDENTITY",),
            AuthorityOutput.from_text(
                record_id="H-REGISTERED", text="ACCOUNT-101"
            ),
        )
    )
    trace["H"] = _execute(world_ghij, "H", "H-REGISTERED")
    trace["I_admission"] = _admission_observation(
        world_ghij.gate.admit_freeform(
            ("G-ROOT",),
            AuthorityOutput.from_text(
                record_id="I-FREEFORM", text="paraphrased instruction"
            ),
        )
    )
    trace["I"] = _execute(world_ghij, "I", "I-FREEFORM")
    trace["J_admission"] = _admission_observation(
        world_ghij.gate.admit_registered(
            TransformRef(REGISTERED),
            ("G-ROOT", "J-MISSING-PARENT"),
            AuthorityOutput.from_text(
                record_id="J-MIXED", text="mixed-parent projection"
            ),
        )
    )
    trace["J"] = _execute(world_ghij, "J", "J-MIXED")
    for record_id in ("G-IDENTITY", "H-REGISTERED", "I-FREEFORM"):
        graphs[record_id] = _graph_observation(world_ghij.store, record_id)

    world_kl = _world()
    trace["K_root"] = _admission_observation(
        _admit_source(world_kl, 0, "K-ROOT")
    )
    for parent_id, record_id in (
        ("K-ROOT", "K-AGENT-A"),
        ("K-AGENT-A", "K-AGENT-B"),
    ):
        trace[f"{record_id}_admission"] = _admission_observation(
            world_kl.gate.admit_identity(
                parent_id,
                AuthorityOutput(
                    record_id, world_kl.events[0].source_object_commitment
                ),
            )
        )
    trace["K"] = _execute(world_kl, "K", "K-AGENT-B")
    graphs["K-AGENT-A"] = _graph_observation(world_kl.store, "K-AGENT-A")
    graphs["K-AGENT-B"] = _graph_observation(world_kl.store, "K-AGENT-B")
    histories["L_before"] = _history(world_kl.store)
    kl_root_key = ReceiptRootKey.from_receipt(
        world_kl.events[0].receipt, custody_root_record_id="K-ROOT"
    )
    trace["L_revocation"] = {
        "affected_record_ids": list(
            world_kl.controller.revoke_receipt_roots(
                revocation_id="L-revocation", root_keys=(kl_root_key,)
            ).affected_record_ids
        )
    }
    trace["L"] = _execute(world_kl, "L", "K-AGENT-B")
    histories["L_after"] = _history(world_kl.store)

    world_m = _world()
    for index in range(3):
        root_id = f"M-ROOT-{index + 1:02d}"
        descendant_id = f"M-DESC-{index + 1:02d}"
        trace[f"M_root_{index + 1}"] = _admission_observation(
            _admit_source(world_m, index, root_id)
        )
        trace[f"M_desc_{index + 1}"] = _admission_observation(
            world_m.gate.admit_registered(
                TransformRef(REGISTERED),
                (root_id,),
                AuthorityOutput.from_text(
                    record_id=descendant_id, text=descendant_id
                ),
            )
        )
    trace["M_mixed"] = _admission_observation(
        world_m.gate.admit_registered(
            TransformRef(REGISTERED),
            ("M-DESC-01", "M-DESC-02"),
            AuthorityOutput.from_text(record_id="M-MIXED", text="M-MIXED"),
        )
    )
    histories["M_before"] = _history(world_m.store)
    selected_roots = tuple(
        ReceiptRootKey.from_receipt(
            world_m.events[index].receipt,
            custody_root_record_id=f"M-ROOT-{index + 1:02d}",
        )
        for index in (0, 1)
    )
    revocation = world_m.controller.revoke_receipt_roots(
        revocation_id="M-selective-revocation", root_keys=selected_roots
    )
    trace["M1_revocation"] = {
        "affected_record_ids": list(revocation.affected_record_ids)
    }
    for case_id, record_id in (
        ("M1_bad_1", "M-DESC-01"),
        ("M1_bad_2", "M-DESC-02"),
        ("M1_mixed", "M-MIXED"),
        ("M2_pre", "M-DESC-03"),
        ("M4_unrelated", "M-ROOT-03"),
    ):
        trace[case_id] = _execute(world_m, case_id, record_id)
    trace["M4_root"] = _admission_observation(
        _admit_source(world_m, 3, "M-ROOT-04")
    )
    trace["M4_desc"] = _admission_observation(
        world_m.gate.admit_registered(
            TransformRef(REGISTERED),
            ("M-ROOT-04",),
            AuthorityOutput.from_text(record_id="M-DESC-04", text="M-DESC-04"),
        )
    )
    trace["M3_post"] = _execute(world_m, "M3_post", "M-DESC-04")
    trace["M5_copy"] = _admission_observation(
        _admit_source(world_m, 0, "M-REVOKED-COPY")
    )
    trace["M5"] = _execute(world_m, "M5", "M-REVOKED-COPY")
    histories["M_after"] = {
        record_id: payload
        for record_id, payload in _history(world_m.store).items()
        if record_id in histories["M_before"]
    }

    legacy = CustodyRecord(
        origin=Origin.TOOL,
        trust=Trust.TRUSTED,
        author="legacy-tool",
        invocation_id="legacy-invocation",
        content_sha256="f" * 64,
        source_tool="legacy-tool",
        id="LEGACY-TRUSTED",
    )
    legacy_gateway = ExportGateway()
    legacy_control = legacy_gateway.request(
        Export(destination="processor", content="legacy", cited=(legacy,))
    )
    legacy_world = _world()
    trace["legacy"] = {
        "legacy_gateway_allowed": legacy_control.allowed,
        "b7": _execute(legacy_world, "legacy", legacy.id),
    }

    return {
        "trace": trace,
        "graphs": graphs,
        "histories": histories,
        "dispatches": {
            "A": list(world_a.dispatcher.calls),
            "GHIJ": list(world_ghij.dispatcher.calls),
            "KL": list(world_kl.dispatcher.calls),
            "M": list(world_m.dispatcher.calls),
        },
    }


def _sqlite_restart_worker(path: str, result_queue) -> None:
    try:
        store = SqliteAuthorityStore(path)
        dispatcher = _Dispatcher()
        execution = AuthorityGateway(store).execute(
            _action("action-N-restart"), ("N-CHILD",), dispatcher
        )
        result_queue.put(
            {
                "records": [item.canonical_bytes().hex() for item in store.records()],
                "dependencies": [
                    item.canonical_bytes().hex()
                    for item in store.dependencies("N-CHILD")
                ],
                "execution": _execution_observation(execution),
                "dispatches": list(dispatcher.calls),
            }
        )
        store.close()
    except BaseException as error:
        result_queue.put({"worker_error": repr(error)})


def _blocked_sqlite_writer(path: str, ready) -> None:
    store = SqliteAuthorityStore(path)

    def block_before_dependency() -> int:
        ready.set()
        threading.Event().wait(timeout=30)
        return 0

    store._connection.create_function(
        "block_b7_equivalence_dependency", 0, block_before_dependency
    )
    store._connection.execute(
        "CREATE TEMP TRIGGER block_b7_equivalence_dependency_write "
        "BEFORE INSERT ON authority_dependency "
        "BEGIN SELECT block_b7_equivalence_dependency(); END"
    )
    world = _world(store)
    _admit_source(world, 0, "P-ROOT")


def _run_local_restart(path: Path) -> dict[str, object]:
    first = SqliteAuthorityStore(path)
    world = _world(first)
    root = _admit_source(world, 0, "N-ROOT")
    child = world.gate.admit_registered(
        TransformRef(REGISTERED),
        ("N-ROOT",),
        AuthorityOutput.from_text(record_id="N-CHILD", text="ACCOUNT-101"),
    )
    before = {
        "root_admission": _admission_observation(root),
        "child_admission": _admission_observation(child),
        "records": [item.canonical_bytes().hex() for item in first.records()],
        "dependencies": [
            item.canonical_bytes().hex()
            for item in first.dependencies("N-CHILD")
        ],
    }
    first.close()
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_sqlite_restart_worker,
        args=(str(path), result_queue),
    )
    process.start()
    process.join(timeout=10)
    if process.is_alive():
        process.kill()
        process.join(timeout=5)
        return {"before": before, "worker_error": "restart worker timed out"}
    return {
        "before": before,
        "after": result_queue.get(timeout=2),
        "process_exitcode": process.exitcode,
        "backend": "sqlite-independent-process-local",
    }


def _run_local_killed_writer(path: Path) -> dict[str, object]:
    bootstrap = SqliteAuthorityStore(path)
    _configure(bootstrap)
    bootstrap.close()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_blocked_sqlite_writer,
        args=(str(path), ready),
    )
    process.start()
    if not ready.wait(timeout=5):
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        return {"worker_error": "writer did not reach transaction barrier"}
    recovery_started = time.monotonic()
    process.kill()
    process.join(timeout=5)
    recovered = SqliteAuthorityStore(path)
    records_before_retry = [
        item.record_id for item in recovered.records()
    ]
    dependencies_before_retry = [
        item.canonical_bytes().hex()
        for item in recovered.dependencies("P-ROOT")
    ]
    dispatcher = _Dispatcher()
    immediate = AuthorityGateway(recovered).execute(
        _action("action-P-after-kill"), ("P-ROOT",), dispatcher
    )
    retry = _admit_source(_world(recovered), 0, "P-ROOT")
    recovery_seconds = time.monotonic() - recovery_started
    final_ids = [item.record_id for item in recovered.records()]
    recovered.close()
    return {
        "killed_exitcode": process.exitcode,
        "records_before_retry": records_before_retry,
        "dependencies_before_retry": dependencies_before_retry,
        "immediate": _execution_observation(immediate),
        "dispatches": list(dispatcher.calls),
        "retry": _admission_observation(retry),
        "final_record_ids": final_ids,
        "duplicate_envelopes": len(final_ids) - len(set(final_ids)),
        "local_recovery_seconds": recovery_seconds,
        "backend": "sqlite-killed-writer-local",
    }


def _run_local_race() -> dict[str, object]:
    store = _BarrierStore()
    world = _world(store)
    root = _admit_source(world, 0, "O-ROOT")
    child = world.gate.admit_registered(
        TransformRef(REGISTERED),
        ("O-ROOT",),
        AuthorityOutput.from_text(record_id="O-DESC", text="O-DESC"),
    )
    before = _history(store)
    store.barrier_record_id = "O-DESC"
    store.barrier_enabled = True
    executions: list[AuthorityExecution] = []
    errors: list[str] = []

    def execute() -> None:
        try:
            executions.append(
                world.gateway.execute(
                    _action("action-O-race"),
                    ("O-DESC",),
                    world.dispatcher,
                )
            )
        except BaseException as error:
            errors.append(repr(error))

    thread = threading.Thread(target=execute)
    thread.start()
    reached = store.candidate_read.wait(timeout=5)
    root_key = ReceiptRootKey.from_receipt(
        world.events[0].receipt, custody_root_record_id="O-ROOT"
    )
    revocation = world.controller.revoke_receipt_roots(
        revocation_id="O-race-revocation", root_keys=(root_key,)
    )
    store.continue_action.set()
    thread.join(timeout=5)
    return {
        "root_admission": _admission_observation(root),
        "child_admission": _admission_observation(child),
        "candidate_barrier_reached": reached,
        "thread_finished": not thread.is_alive(),
        "thread_errors": errors,
        "execution": (
            _execution_observation(executions[0]) if executions else None
        ),
        "affected_record_ids": list(revocation.affected_record_ids),
        "dispatches": list(world.dispatcher.calls),
        "history_before": before,
        "history_after": _history(store),
    }


def _load_scoring_table() -> dict[str, object]:
    """Construct expectations only after the treatment completion latch."""

    return {
        "actions": {
            "A1": (False, "CAP_NOT_ACT"),
            "A2": (True, None),
            "B": (False, "MISSING_AUTHORITY_RECORD"),
            "C": (False, "MISSING_AUTHORITY_RECORD"),
            "D": (False, "ACTION_SCOPE_MISMATCH"),
            "E": (False, "POLICY_GENERATION_MISMATCH"),
            "F": (False, "MISSING_AUTHORITY_RECORD"),
            "G": (True, None),
            "H": (True, None),
            "I": (False, "CAP_NOT_ACT"),
            "J": (False, "MISSING_AUTHORITY_RECORD"),
            "K": (True, None),
            "L": (False, "REVOKED_AUTHORITY_ROOT"),
            "M1_bad_1": (False, "REVOKED_AUTHORITY_ROOT"),
            "M1_bad_2": (False, "REVOKED_AUTHORITY_ROOT"),
            "M1_mixed": (False, "REVOKED_AUTHORITY_ROOT"),
            "M2_pre": (True, None),
            "M3_post": (True, None),
            "M4_unrelated": (True, None),
            "M5": (False, "MISSING_AUTHORITY_RECORD"),
        },
        "admissions": {
            "B_admission": (False, "RECEIPT_SIGNATURE_INVALID"),
            "C_admission": (False, "UPSTREAM_OBJECT_COMMITMENT_MISMATCH"),
            "F_replay": (False, "UNRELATED_RECEIPT_REPLAY"),
            "J_admission": (False, "MISSING_REQUIRED_PARENT"),
            "M5_copy": (False, "UNRELATED_RECEIPT_REPLAY"),
        },
        "graphs": {
            "G-IDENTITY": {
                "direct_parent_ids": ["G-ROOT"],
                "support_root_ids": ["G-ROOT"],
                "dependencies": [("SOURCE_AUTHORITY", "G-ROOT")],
            },
            "H-REGISTERED": {
                "direct_parent_ids": ["G-IDENTITY"],
                "support_root_ids": ["G-ROOT"],
                "dependencies": [
                    ("SOURCE_AUTHORITY", "G-ROOT"),
                    ("TRANSFORM_POLICY", "H-REGISTERED"),
                ],
            },
            "I-FREEFORM": {
                "direct_parent_ids": ["G-ROOT"],
                "support_root_ids": ["G-ROOT"],
                "dependencies": [
                    ("SOURCE_AUTHORITY", "G-ROOT"),
                    ("TRANSFORM_POLICY", "I-FREEFORM"),
                ],
            },
            "K-AGENT-A": {
                "direct_parent_ids": ["K-ROOT"],
                "support_root_ids": ["K-ROOT"],
                "dependencies": [("SOURCE_AUTHORITY", "K-ROOT")],
            },
            "K-AGENT-B": {
                "direct_parent_ids": ["K-AGENT-A"],
                "support_root_ids": ["K-ROOT"],
                "dependencies": [("SOURCE_AUTHORITY", "K-ROOT")],
            },
        },
        "m_affected": [
            "M-DESC-01",
            "M-DESC-02",
            "M-MIXED",
            "M-ROOT-01",
            "M-ROOT-02",
        ],
    }


class _PostActionScorer:
    def __init__(self) -> None:
        self._actions_complete = False
        self.reads_before_actions_complete = 0

    def complete_actions(self) -> None:
        self._actions_complete = True

    def score(
        self,
        first: Mapping[str, object],
        second: Mapping[str, object],
        *,
        restart: Mapping[str, object],
        race: Mapping[str, object],
        killed_writer: Mapping[str, object],
    ) -> dict[str, object]:
        if not self._actions_complete:
            self.reads_before_actions_complete += 1
            raise RuntimeError("outcome table read before actions completed")
        table = _load_scoring_table()
        failures: list[str] = []
        trace = first["trace"]
        assert isinstance(trace, Mapping)

        action_table = table["actions"]
        assert isinstance(action_table, Mapping)
        for case_id, expectation in action_table.items():
            actual = trace.get(case_id)
            if not isinstance(actual, Mapping):
                failures.append(f"{case_id}: missing action observation")
                continue
            allowed, reason = expectation
            if actual.get("allowed") != allowed:
                failures.append(
                    f"{case_id}: allowed={actual.get('allowed')} wanted {allowed}"
                )
            if reason is not None and actual.get("reason") != reason:
                failures.append(
                    f"{case_id}: reason={actual.get('reason')} wanted {reason}"
                )
            if actual.get("dispatched") != allowed:
                failures.append(
                    f"{case_id}: dispatch did not match final allow"
                )

        admission_table = table["admissions"]
        assert isinstance(admission_table, Mapping)
        for case_id, expectation in admission_table.items():
            actual = trace.get(case_id)
            if not isinstance(actual, Mapping):
                failures.append(f"{case_id}: missing admission observation")
                continue
            admitted, reason = expectation
            if (
                actual.get("admitted") != admitted
                or actual.get("reason") != reason
            ):
                failures.append(f"{case_id}: admission mismatch ({actual})")

        graph_table = table["graphs"]
        graphs = first["graphs"]
        assert isinstance(graph_table, Mapping) and isinstance(graphs, Mapping)
        for record_id, expectation in graph_table.items():
            actual = graphs.get(record_id)
            if not isinstance(actual, Mapping):
                failures.append(f"{record_id}: missing graph observation")
                continue
            assert isinstance(expectation, Mapping)
            for field_name in ("direct_parent_ids", "support_root_ids"):
                if actual.get(field_name) != expectation.get(field_name):
                    failures.append(f"{record_id}: {field_name} mismatch")
            dependencies = actual.get("dependencies")
            if not isinstance(dependencies, list):
                failures.append(f"{record_id}: dependencies missing")
                continue
            dependency_shape = [
                (item.get("kind"), item.get("root_record_id"))
                for item in dependencies
                if isinstance(item, Mapping)
            ]
            expected_dependencies = expectation.get("dependencies")
            if (
                not isinstance(expected_dependencies, list)
                or sorted(dependency_shape) != sorted(expected_dependencies)
            ):
                failures.append(f"{record_id}: dependency closure mismatch")
            support_digests = actual.get("support_root_key_digests")
            source_digests = [
                item.get("root_key_digest")
                for item in dependencies
                if isinstance(item, Mapping)
                and item.get("kind") == "SOURCE_AUTHORITY"
            ]
            if (
                not isinstance(support_digests, list)
                or len(support_digests) != 1
                or source_digests != support_digests
            ):
                failures.append(f"{record_id}: support digest mismatch")
            if actual.get("has_root_receipt") is not False:
                failures.append(f"{record_id}: derived record carried root receipt")

        histories = first["histories"]
        assert isinstance(histories, Mapping)
        rewrite_count = sum(
            histories.get(f"{prefix}_before")
            != histories.get(f"{prefix}_after")
            for prefix in ("E", "L", "M")
        )
        if rewrite_count:
            failures.append(f"historical rewrites observed: {rewrite_count}")

        m_revocation = trace.get("M1_revocation")
        if not isinstance(m_revocation, Mapping) or m_revocation.get(
            "affected_record_ids"
        ) != table["m_affected"]:
            failures.append("M1 affected reverse closure mismatch")

        legacy = trace.get("legacy")
        if not isinstance(legacy, Mapping):
            failures.append("legacy control missing")
        else:
            b7 = legacy.get("b7")
            if (
                legacy.get("legacy_gateway_allowed") is not True
                or not isinstance(b7, Mapping)
                or b7.get("allowed") is not False
            ):
                failures.append("legacy authority crossed into B7 ACT")

        restart_before = restart.get("before")
        restart_after = restart.get("after")
        if not isinstance(restart_before, Mapping) or not isinstance(
            restart_after, Mapping
        ):
            failures.append("N independent-process restart did not return state")
        else:
            if restart_after.get("worker_error") is not None:
                failures.append(f"N worker failed: {restart_after['worker_error']}")
            if restart_before.get("records") != restart_after.get("records"):
                failures.append("N record reconstruction mismatch")
            if restart_before.get("dependencies") != restart_after.get(
                "dependencies"
            ):
                failures.append("N dependency reconstruction mismatch")
            execution = restart_after.get("execution")
            if not isinstance(execution, Mapping) or execution.get(
                "allowed"
            ) is not True:
                failures.append("N current action did not allow after restart")

        race_execution = race.get("execution")
        if (
            race.get("candidate_barrier_reached") is not True
            or race.get("thread_finished") is not True
            or race.get("thread_errors") != []
            or not isinstance(race_execution, Mapping)
            or race_execution.get("allowed") is not False
            or race_execution.get("reason") != "REVOKED_AUTHORITY_ROOT"
            or race.get("dispatches") != []
            or race.get("history_before") != race.get("history_after")
        ):
            failures.append("O action/revocation final-check race mismatch")

        killed_immediate = killed_writer.get("immediate")
        if (
            killed_writer.get("records_before_retry") != []
            or killed_writer.get("dependencies_before_retry") != []
            or not isinstance(killed_immediate, Mapping)
            or killed_immediate.get("allowed") is not False
            or killed_writer.get("dispatches") != []
            or killed_writer.get("retry", {}).get("admitted") is not True
            or killed_writer.get("duplicate_envelopes") != 0
        ):
            failures.append("P killed-writer recovery mismatch")

        safety_cases = ("A1", "B", "C", "D", "E", "F")
        safety_false_acts = sum(
            bool(trace[case_id]["allowed"]) for case_id in safety_cases
        )
        metrics = {
            "tool_echo_false_act": [int(bool(trace["A1"]["allowed"])), 1],
            "benign_relay_utility": [int(bool(trace["A2"]["allowed"])), 1],
            "forgery_binding_false_act": [
                sum(bool(trace[case_id]["allowed"]) for case_id in ("B", "C", "D", "E", "F")),
                5,
            ],
            "identity_utility": [int(bool(trace["G"]["allowed"])), 1],
            "registered_utility": [int(bool(trace["H"]["allowed"])), 1],
            "freeform_false_act": [int(bool(trace["I"]["allowed"])), 1],
            "mixed_required_parent_false_act": [
                int(bool(trace["J"]["allowed"])),
                1,
            ],
            "cross_agent_utility": [int(bool(trace["K"]["allowed"])), 1],
            "cross_agent_revoked_false_act": [
                int(bool(trace["L"]["allowed"])),
                1,
            ],
            "affected_revocation_recall": [
                sum(
                    not bool(trace[case_id]["allowed"])
                    for case_id in ("M1_bad_1", "M1_bad_2", "M1_mixed")
                ),
                3,
            ],
            "selective_utility": [
                sum(
                    bool(trace[case_id]["allowed"])
                    for case_id in ("M2_pre", "M3_post", "M4_unrelated")
                ),
                3,
            ],
            "revocation_escape_false_act": [
                int(bool(trace["M5"]["allowed"])),
                1,
            ],
            "historical_rewrite_count": [rewrite_count, 0],
            "legacy_false_act": [
                int(bool(legacy["b7"]["allowed"])),
                1,
            ],
            "action_revocation_race_false_act": [
                int(bool(race_execution["allowed"])),
                1,
            ],
            "post_kill_partial_authoritative_records": [
                int(bool(killed_writer.get("records_before_retry"))),
                1,
            ],
            "immediate_post_kill_false_act": [
                int(bool(killed_immediate["allowed"])),
                1,
            ],
            "duplicate_authoritative_envelopes": [
                int(killed_writer.get("duplicate_envelopes", -1)),
                0,
            ],
            "normalized_trace_reproducibility": [int(first == second), 1],
            "scorer_reads_before_actions_complete": [
                self.reads_before_actions_complete,
                0,
            ],
            "combined_a_to_f_false_act": [safety_false_acts, 6],
        }
        if first != second:
            failures.append("normalized A-M traces did not reproduce")
        return {
            "status": (
                "LOCAL-EQUIVALENCE-SUPPORTED"
                if not failures
                else "LOCAL-EQUIVALENCE-FAILED"
            ),
            "failures": failures,
            "metrics": metrics,
        }


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        nested = set(value)
        for item in value.values():
            nested.update(_nested_keys(item))
        return nested
    if isinstance(value, list):
        nested: set[str] = set()
        for item in value:
            nested.update(_nested_keys(item))
        return nested
    return set()


def _static_audit() -> dict[str, object]:
    fixture_digests = {
        "issuer_public_key.hex": (
            "75735aa2e22d87d80a573873f93ce086d5dd306a36607e76da89bca90feb0e56"
        ),
        "issuer_public_key_v2.hex": (
            "12caae77e63ebcbe00e350306b86f693f7507f79ef900213911c9992ca4e0c3f"
        ),
        "policy_snapshot.json": (
            "d67e848aecdd40fd33261b2b89ffb0d5ea0ca1a7af87073b2611c7c3a2c379c1"
        ),
        "source_event.json": (
            "b85b0895ceea636c13e41e9f1bba436f42a3a8e32e77b2c97dfe4b96dc92c99c"
        ),
        "source_event_002.json": (
            "47f4e41e2e18b629876d473229578ab118952c62fc66a5790854aab73ec150af"
        ),
        "source_event_003.json": (
            "554ff5e385fe3ee5c6223fcf727ebeaefa94a1f44be2e2d1a71424ce42325c6e"
        ),
        "source_event_004.json": (
            "59615603c229eef9d33b56d557ebabca2a8d92bd1e2ccb3326f05840a968be37"
        ),
    }
    digest_matches = {
        name: hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        == digest
        for name, digest in fixture_digests.items()
    }
    fixture_keys: set[str] = set()
    for path in sorted(FIXTURES.glob("*.json")):
        fixture_keys.update(_nested_keys(json.loads(path.read_text())))
    source = Path(__file__).read_text()
    treatment_source = inspect.getsource(_run_treatment)
    syntax = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(syntax)
        if isinstance(node, ast.ImportFrom)
    }.union(
        alias.name
        for node in ast.walk(syntax)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    constructed_names = {
        node.func.id
        for node in ast.walk(syntax)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    capability_meet_calls = [
        ast.unparse(node.func)
        for node in ast.walk(syntax)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and ast.unparse(node.func) == "Capability.meet"
    ]
    return {
        "fixture_digests_match": all(digest_matches.values()),
        "fixture_digest_checks": digest_matches,
        "fixture_forbidden_fields": sorted(
            FORBIDDEN_RUNTIME_FIELDS.intersection(fixture_keys)
        ),
        "private_key_files": sorted(
            path.name
            for path in FIXTURES.iterdir()
            if "private" in path.name.lower()
        ),
        "research_runner_imports": sorted(
            name for name in imported_modules if name.startswith("research")
        ),
        "test_side_authority_constructs": sorted(
            {"AdmissionEnvelope", "AuthorityEvaluator"}.intersection(
                constructed_names
            )
        )
        + capability_meet_calls,
        "treatment_references_scorer": any(
            marker in treatment_source
            for marker in ("_PostActionScorer", "_load_scoring_table")
        ),
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_commit() -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT}", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _proof_report(
    *,
    first: Mapping[str, object],
    score: Mapping[str, object],
    static_audit: Mapping[str, object],
    restart: Mapping[str, object],
    race: Mapping[str, object],
    killed_writer: Mapping[str, object],
) -> dict[str, object]:
    design_paths = (
        ROOT / "research" / "production_b7" / "DATA_MODEL.md",
        ROOT / "research" / "production_b7" / "EQUIVALENCE_TEST_PLAN.md",
        ROOT / "research" / "production_b7" / "IMPLEMENTATION_PLAN.md",
        ROOT / "research" / "production_b7" / "TRUST_BOUNDARY.md",
    )
    module_paths = (
        ROOT / "custody" / "action.py",
        ROOT / "custody" / "authority.py",
        ROOT / "custody" / "firestore_store.py",
        ROOT / "custody" / "service.py",
        ROOT / "custody" / "store.py",
    )
    report: dict[str, object] = {
        "experiment_family": "B7_PRODUCTION_EQUIVALENCE",
        "classification": "SYNTHETIC-MODEL-FREE-LOCAL",
        "status": score["status"],
        "production_commit": _current_commit(),
        "design_digests": {
            str(path.relative_to(ROOT)): _sha256_file(path)
            for path in design_paths
        },
        "production_module_digests": {
            str(path.relative_to(ROOT)): _sha256_file(path)
            for path in module_paths
        },
        "fixture_audit": static_audit,
        "metrics": score["metrics"],
        "failures": score["failures"],
        "normalized_trace": first["trace"],
        "graph_observations": first["graphs"],
        "durable_local": {
            "N_restart": restart,
            "O_action_revocation_race": race,
            "P_killed_writer": killed_writer,
        },
        "real_firestore_N_to_P": "NOT-EXECUTED-NOT-AUTHORIZED",
        "external_source_runtime_producer": "NOT-PROVEN-BY-STATIC-FIXTURE",
        "prior_real_firestore_recovery_liveness": {
            "recovery_completed_within_90_seconds": [0, 1],
            "status": "E2H-R1E-BASELINE-NOT-RERUN",
        },
        "model_api_cost_usd": 0,
        "benchmark_executed": False,
    }
    normalized = json.loads(json.dumps(report))
    killed = normalized["durable_local"]["P_killed_writer"]
    if isinstance(killed, dict):
        killed.pop("local_recovery_seconds", None)
    report["canonical_result_digest"] = hashlib.sha256(
        (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()
    return report


def _write_proof(report: Mapping[str, object]) -> None:
    output = ROOT / "proof-out"
    output.mkdir(exist_ok=True)
    json_path = output / "b7-production-equivalence.json"
    markdown_path = output / "b7-production-equivalence.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    metrics = report["metrics"]
    assert isinstance(metrics, Mapping)
    rows = [
        "| Metric | Result |",
        "|---|---:|",
        *(
            f"| `{name}` | {value[0]}/{value[1]} |"
            for name, value in metrics.items()
        ),
    ]
    markdown_path.write_text(
        "# B7 production-equivalence local proof\n\n"
        f"Status: `{report['status']}`\n\n"
        "Classification: `SYNTHETIC-MODEL-FREE-LOCAL`\n\n"
        "Real Firestore N-P: `NOT EXECUTED`\n\n"
        "External runtime source producer: `NOT PROVEN BY STATIC FIXTURE`\n\n"
        + "\n".join(rows)
        + "\n\n"
        "The prior E2H-R1E 90-second recovery-liveness miss remains in force.\n"
    )


class B7ProductionEquivalence(unittest.TestCase):
    def test_frozen_cases_run_through_production_apis_without_leakage(self) -> None:
        scorer = _PostActionScorer()
        first = _run_treatment()
        second = _run_treatment()
        race = _run_local_race()
        with TemporaryDirectory() as temp_dir:
            temporary = Path(temp_dir)
            restart = _run_local_restart(temporary / "restart.db")
            killed_writer = _run_local_killed_writer(
                temporary / "killed-writer.db"
            )
        scorer.complete_actions()
        score = scorer.score(
            first,
            second,
            restart=restart,
            race=race,
            killed_writer=killed_writer,
        )
        static_audit = _static_audit()
        report = _proof_report(
            first=first,
            score=score,
            static_audit=static_audit,
            restart=restart,
            race=race,
            killed_writer=killed_writer,
        )
        _write_proof(report)

        self.assertTrue(static_audit["fixture_digests_match"])
        self.assertEqual(static_audit["fixture_forbidden_fields"], [])
        self.assertEqual(static_audit["private_key_files"], [])
        self.assertEqual(static_audit["research_runner_imports"], [])
        self.assertEqual(static_audit["test_side_authority_constructs"], [])
        self.assertFalse(static_audit["treatment_references_scorer"])
        self.assertEqual(scorer.reads_before_actions_complete, 0)
        self.assertEqual(score["failures"], [])
        self.assertEqual(score["status"], "LOCAL-EQUIVALENCE-SUPPORTED")


if __name__ == "__main__":
    unittest.main()
