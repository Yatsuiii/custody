#!/usr/bin/env python3
"""Execute the frozen E2F ACTION-CURRENT policy-admission gate.

The mechanism is a deterministic SQLite model of the S3 contract.  It knows
only policy snapshots and actual ordered events; scorer ground truth is kept in
a separate vault and released after all six variants complete.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


OUT = Path(__file__).resolve().parent
EXPERIMENT_ID = "E2F_POLICY_ADMISSION_TOCTOU"
PREREGISTRATION_COMMIT = "5527f3190dc0b4180c1fbdd3f91d13237104e809"
E2D_COMMIT = "d5b671ba1c09f7ac70b08d9ad54ba9b8eccf69c3"
E2E_COMMIT = "4b99bfab58ae292892c32e472841aaf6952d3ce6"
PLAN_SHA256 = "ff08835a29c8f7a9ec15f6ad0a2ac7a55cb2bae3de4de709a3f44bc275048f29"
OUTPUT_ID = "e2f-r1-root"
PAYLOAD = "Acme settlement account: ACCT-TEST-22."
OPERATION = "vendor_lookup"
REVISION = "R1"
SCOPE = "export.send"
FORBIDDEN_KEYS = {
    "race_case", "expected_allow", "stale_is_bad", "expected_failed_invariant",
    "expected_verdict", "should_deny", "scorer_only",
}
TIER_RANK = {"NONE": 0, "INFORM": 1, "ACT": 2}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {key: plain(item) for key, item in dataclasses.asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


@dataclass(frozen=True)
class PolicySnapshot:
    version: str
    generation: int
    role: str
    caps: tuple[tuple[str, str], ...]

    def cap(self) -> str:
        return dict(self.caps)[SCOPE]

    def semantic(self) -> dict[str, Any]:
        return {"role": self.role, "caps": dict(self.caps)}

    def semantic_hash(self) -> str:
        return digest(self.semantic())


@dataclass(frozen=True)
class RuntimeOperation:
    output_id: str
    payload: str
    operation: str
    revision: str
    scope: str


@dataclass(frozen=True)
class RuntimeFixture:
    initial_policy: PolicySnapshot
    v2: PolicySnapshot
    v3: PolicySnapshot
    operation: RuntimeOperation


@dataclass(frozen=True)
class OperationStart:
    output_id: str
    start_policy_version: str
    start_policy_generation: int
    start_role: str
    start_caps: tuple[tuple[str, str], ...]
    logical_step: int


@dataclass(frozen=True)
class AdmissionEnvelope:
    output_id: str
    payload_digest: str
    start_policy_version: str
    start_policy_generation: int
    bound_policy_version: str
    bound_policy_generation: int
    bound_role: str
    bound_caps: tuple[tuple[str, str], ...]
    state: str
    admitted_at_logical_step: int

    def immutable(self) -> dict[str, Any]:
        return {
            "output_id": self.output_id,
            "payload_digest": self.payload_digest,
            "start_policy_version": self.start_policy_version,
            "start_policy_generation": self.start_policy_generation,
            "bound_policy_version": self.bound_policy_version,
            "bound_policy_generation": self.bound_policy_generation,
            "bound_role": self.bound_role,
            "bound_caps": dict(self.bound_caps),
            "admitted_at_logical_step": self.admitted_at_logical_step,
        }

    def policy_identity(self) -> dict[str, Any]:
        identity = self.immutable()
        identity.pop("admitted_at_logical_step")
        return identity


@dataclass(frozen=True)
class ActionRead:
    output_id: str
    bound_generation: int
    bound_version: str
    bound_caps: tuple[tuple[str, str], ...]
    observed_current_generation: int
    observed_current_version: str
    read_step: int


@dataclass(frozen=True)
class ActionDecision:
    output_id: str
    bound_policy_version: str
    current_policy_version: str
    bound_generation: int
    current_generation: int
    effective_cap: str
    allowed: bool
    freshness: str
    reason: str


@dataclass(frozen=True)
class AdmissionResult:
    outcome: str
    envelope: AdmissionEnvelope
    current_policy_version: str
    current_generation: int
    conflict: dict[str, Any] | None


@dataclass(frozen=True)
class ScorerGroundTruth:
    expected_action_allowed: tuple[tuple[str, bool], ...]
    expected_stale_admission: tuple[tuple[str, bool], ...]
    expected_retry_conflict: bool
    expected_aba_reject: bool


class GroundTruthVault:
    def __init__(self, truth: ScorerGroundTruth) -> None:
        self._truth = truth
        self.reads = 0

    def release_for_scoring(self) -> ScorerGroundTruth:
        self.reads += 1
        return self._truth


def fixture() -> RuntimeFixture:
    return RuntimeFixture(
        initial_policy=PolicySnapshot("v1", 1, "ORIGIN", ((SCOPE, "ACT"),)),
        v2=PolicySnapshot("v2", 2, "RELAY", ((SCOPE, "INFORM"),)),
        v3=PolicySnapshot("v3", 3, "ORIGIN", ((SCOPE, "ACT"),)),
        operation=RuntimeOperation(OUTPUT_ID, PAYLOAD, OPERATION, REVISION, SCOPE),
    )


def ground_truth() -> ScorerGroundTruth:
    return ScorerGroundTruth(
        expected_action_allowed=(("E2F_A", True), ("E2F_B", False), ("E2F_C", False), ("E2F_D", False), ("E2F_E", False), ("E2F_F", False)),
        expected_stale_admission=(("E2F_A", False), ("E2F_B", True), ("E2F_C", False), ("E2F_D", True), ("E2F_E", True), ("E2F_F", False)),
        expected_retry_conflict=True,
        expected_aba_reject=True,
    )


class PolicyAdmissionMechanism:
    """Deep module for durable policy generations, admission identity, and gateway freshness."""

    def __init__(self, db_path: Path, runtime: RuntimeFixture) -> None:
        self.db_path = db_path
        self.runtime = runtime
        self.connection = sqlite3.connect(str(db_path))
        self.connection.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS envelopes(output_id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conflicts(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(step INTEGER PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL);
            """
        )
        if self.connection.execute("SELECT 1 FROM meta WHERE key='current_policy'").fetchone() is None:
            with self.connection:
                self.connection.execute("INSERT INTO meta(key,value) VALUES('logical_step','0')")
                self.connection.execute("INSERT INTO meta(key,value) VALUES('current_policy',?)", (json.dumps(plain(self.runtime.initial_policy), sort_keys=True),))

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "PolicyAdmissionMechanism":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _step(self, kind: str, data: Mapping[str, Any] | None = None) -> int:
        step = int(self.connection.execute("SELECT value FROM meta WHERE key='logical_step'").fetchone()[0]) + 1
        payload = dict(data or {})
        with self.connection:
            self.connection.execute("UPDATE meta SET value=? WHERE key='logical_step'", (str(step),))
            self.connection.execute("INSERT INTO events(step,kind,data) VALUES(?,?,?)", (step, kind, json.dumps(payload, sort_keys=True)))
        return step

    def current_policy(self) -> PolicySnapshot:
        raw = json.loads(self.connection.execute("SELECT value FROM meta WHERE key='current_policy'").fetchone()[0])
        return PolicySnapshot(raw["version"], int(raw["generation"]), raw["role"], tuple(tuple(pair) for pair in raw["caps"]))

    def advance_policy(self, snapshot: PolicySnapshot) -> None:
        if snapshot.generation <= self.current_policy().generation:
            raise ValueError("policy generations must increase")
        self._step("policy_advance", {"version": snapshot.version, "generation": snapshot.generation})
        with self.connection:
            self.connection.execute("UPDATE meta SET value=? WHERE key='current_policy'", (json.dumps(plain(snapshot), sort_keys=True),))

    def capture_start(self) -> OperationStart:
        policy = self.current_policy()
        step = self._step("operation_start", {"version": policy.version, "generation": policy.generation})
        return OperationStart(self.runtime.operation.output_id, policy.version, policy.generation, policy.role, policy.caps, step)

    def produce(self) -> int:
        return self._step("output_produced", {"output_id": self.runtime.operation.output_id, "payload_digest": hashlib.sha256(self.runtime.operation.payload.encode()).hexdigest()})

    def _load_envelope(self, output_id: str) -> AdmissionEnvelope:
        row = self.connection.execute("SELECT data FROM envelopes WHERE output_id=?", (output_id,)).fetchone()
        if row is None:
            raise KeyError(output_id)
        raw = json.loads(row[0])
        return AdmissionEnvelope(
            output_id=raw["output_id"], payload_digest=raw["payload_digest"],
            start_policy_version=raw["start_policy_version"], start_policy_generation=int(raw["start_policy_generation"]),
            bound_policy_version=raw["bound_policy_version"], bound_policy_generation=int(raw["bound_policy_generation"]),
            bound_role=raw["bound_role"], bound_caps=tuple(tuple(pair) for pair in raw["bound_caps"]),
            state=raw["state"], admitted_at_logical_step=int(raw["admitted_at_logical_step"]),
        )

    def envelope(self, output_id: str = OUTPUT_ID) -> AdmissionEnvelope:
        return self._load_envelope(output_id)

    @staticmethod
    def envelope_record(envelope: AdmissionEnvelope) -> dict[str, Any]:
        return {**envelope.immutable(), "state": envelope.state}

    def admit(self, start: OperationStart) -> AdmissionResult:
        current = self.current_policy()
        step = self._step("admission_attempt", {"output_id": start.output_id, "start_version": start.start_policy_version, "start_generation": start.start_policy_generation, "current_version": current.version, "current_generation": current.generation})
        existing_row = self.connection.execute("SELECT data FROM envelopes WHERE output_id=?", (start.output_id,)).fetchone()
        proposed = AdmissionEnvelope(
            output_id=start.output_id,
            payload_digest=hashlib.sha256(self.runtime.operation.payload.encode()).hexdigest(),
            start_policy_version=start.start_policy_version,
            start_policy_generation=start.start_policy_generation,
            bound_policy_version=start.start_policy_version,
            bound_policy_generation=start.start_policy_generation,
            bound_role=start.start_role,
            bound_caps=start.start_caps,
            state="LIVE" if start.start_policy_generation == current.generation else "STALE_AT_ADMISSION",
            admitted_at_logical_step=step,
        )
        if existing_row is None:
            with self.connection:
                self.connection.execute("INSERT INTO envelopes(output_id,data) VALUES(?,?)", (start.output_id, json.dumps(plain(proposed), sort_keys=True)))
            return AdmissionResult("ADMITTED", proposed, current.version, current.generation, None)
        existing = self._load_envelope(start.output_id)
        if existing.policy_identity() == proposed.policy_identity():
            return AdmissionResult("IDEMPOTENT_REPLAY", existing, current.version, current.generation, None)
        conflict = {
            "output_id": start.output_id,
            "existing_envelope_digest": digest(existing.immutable()),
            "retry_policy_version": start.start_policy_version,
            "retry_generation": start.start_policy_generation,
            "conflict_reason": "RETRY_POLICY_CONFLICT",
        }
        with self.connection:
            self.connection.execute("INSERT INTO conflicts(data) VALUES(?)", (json.dumps(conflict, sort_keys=True),))
        return AdmissionResult("RETRY_POLICY_CONFLICT", existing, current.version, current.generation, conflict)

    def begin_action(self, output_id: str = OUTPUT_ID) -> ActionRead:
        envelope = self._load_envelope(output_id)
        current = self.current_policy()
        step = self._step("action_gateway_read", {"output_id": output_id, "bound_generation": envelope.bound_policy_generation, "current_generation": current.generation})
        return ActionRead(output_id, envelope.bound_policy_generation, envelope.bound_policy_version, envelope.bound_caps, current.generation, current.version, step)

    def finalize_action(self, read: ActionRead) -> ActionDecision:
        envelope = self._load_envelope(read.output_id)
        current = self.current_policy()
        generation_match = envelope.bound_policy_generation == current.generation
        allowed = generation_match and dict(envelope.bound_caps).get(SCOPE) == "ACT"
        effective = dict(envelope.bound_caps).get(SCOPE, "NONE") if generation_match else "NONE"
        decision = ActionDecision(
            output_id=read.output_id,
            bound_policy_version=envelope.bound_policy_version,
            current_policy_version=current.version,
            bound_generation=envelope.bound_policy_generation,
            current_generation=current.generation,
            effective_cap=effective,
            allowed=allowed,
            freshness="CURRENT_GENERATION_MATCH" if generation_match else "STALE_GENERATION",
            reason="CURRENT_GENERATION_MATCH" if allowed else "POLICY_GENERATION_MISMATCH",
        )
        step = self._step("action_gateway_final", plain(decision))
        with self.connection:
            self.connection.execute("INSERT INTO audit(data) VALUES(?)", (json.dumps({"logical_step": step, **plain(decision)}, sort_keys=True),))
        return decision

    def authorize_action(self, output_id: str = OUTPUT_ID) -> ActionDecision:
        return self.finalize_action(self.begin_action(output_id))

    def conflicts(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.connection.execute("SELECT data FROM conflicts ORDER BY id")]

    def event_log(self) -> list[dict[str, Any]]:
        return [{"step": row[0], "kind": row[1], "data": json.loads(row[2])} for row in self.connection.execute("SELECT step,kind,data FROM events ORDER BY step")]

    def state_digest(self) -> str:
        state = {
            "meta": [{"key": row[0], "value": row[1]} for row in self.connection.execute("SELECT key,value FROM meta ORDER BY key")],
            "envelopes": [{"output_id": row[0], "data": json.loads(row[1])} for row in self.connection.execute("SELECT output_id,data FROM envelopes ORDER BY output_id")],
            "conflicts": [{"id": row[0], "data": json.loads(row[1])} for row in self.connection.execute("SELECT id,data FROM conflicts ORDER BY id")],
            "audit": [{"id": row[0], "data": json.loads(row[1])} for row in self.connection.execute("SELECT id,data FROM audit ORDER BY id")],
            "events": self.event_log(),
        }
        return digest(state)


def forbidden_keys(value: Any) -> list[str]:
    found: set[str] = set()
    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                lowered = str(key).lower()
                if lowered in FORBIDDEN_KEYS or any(token in lowered for token in ("race_case", "expected", "stale_is_bad", "scorer")):
                    found.add(str(key))
                walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
    walk(value)
    return sorted(found)


def mechanism_guard(runtime: RuntimeFixture, vault: GroundTruthVault) -> dict[str, Any]:
    runtime_forbidden = forbidden_keys(plain(runtime))
    constructor_rejects = False
    with tempfile.TemporaryDirectory(prefix="e2f-guard-") as directory:
        try:
            PolicyAdmissionMechanism(Path(directory) / "guard.sqlite", runtime, ground_truth=object())  # type: ignore[call-arg]
        except TypeError:
            constructor_rejects = True
        with PolicyAdmissionMechanism(Path(directory) / "guard2.sqlite", runtime) as mechanism:
            attrs = sorted(vars(mechanism))
            no_scorer_attr = not any("truth" in key.lower() or "scorer" in key.lower() for key in attrs)
    assert not runtime_forbidden
    assert constructor_rejects
    assert no_scorer_attr
    assert vault.reads == 0
    return {"runtime_forbidden_keys": runtime_forbidden, "constructor_rejects_ground_truth": constructor_rejects, "mechanism_has_scorer_reference": not no_scorer_attr, "scorer_reads_before_all_variants": vault.reads, "passed": not runtime_forbidden and constructor_rejects and no_scorer_attr and vault.reads == 0}


def action_trace(variant: str, envelope: AdmissionEnvelope, decision: ActionDecision) -> dict[str, Any]:
    return {
        "variant": variant,
        "output_id": decision.output_id,
        "bound_policy_version": decision.bound_policy_version,
        "current_policy_version": decision.current_policy_version,
        "bound_generation": decision.bound_generation,
        "current_generation": decision.current_generation,
        "bound_role": envelope.bound_role,
        "bound_caps": dict(envelope.bound_caps),
        "effective_cap": decision.effective_cap,
        "admission_state": envelope.state,
        "freshness_decision": decision.freshness,
        "action_allowed": decision.allowed,
        "reason": decision.reason,
    }


def execute_variant(variant: str, runtime: RuntimeFixture) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"e2f-{variant.lower()}-") as directory:
        with PolicyAdmissionMechanism(Path(directory) / "state.sqlite", runtime) as mechanism:
            events: list[str] = []
            start = mechanism.capture_start()
            events.append("operation_start:v1/g1")
            admission_result: AdmissionResult
            retry_results: list[dict[str, Any]] = []
            if variant == "E2F_A":
                mechanism.produce(); events.append("output_produced")
                admission_result = mechanism.admit(start); events.append("admit:v1/g1")
                decision = mechanism.authorize_action(); events.append("action:g1")
            elif variant == "E2F_B":
                mechanism.advance_policy(runtime.v2); events.append("policy:v2/g2")
                mechanism.produce(); events.append("output_produced")
                admission_result = mechanism.admit(start); events.append("stale_admit:v1/g1_under_v2/g2")
                decision = mechanism.authorize_action(); events.append("action:g2")
            elif variant == "E2F_C":
                mechanism.produce(); events.append("output_produced")
                admission_result = mechanism.admit(start); events.append("admit:v1/g1")
                mechanism.advance_policy(runtime.v2); events.append("policy:v2/g2")
                decision = mechanism.authorize_action(); events.append("action:g2")
            elif variant == "E2F_D":
                mechanism.advance_policy(runtime.v2); events.append("policy:v2/g2")
                mechanism.advance_policy(runtime.v3); events.append("policy:v3/g3")
                mechanism.produce(); events.append("output_produced")
                admission_result = mechanism.admit(start); events.append("stale_admit:v1/g1_under_v3/g3")
                decision = mechanism.authorize_action(); events.append("action:g3")
            elif variant == "E2F_E":
                mechanism.advance_policy(runtime.v2); events.append("policy:v2/g2")
                mechanism.produce(); events.append("output_produced")
                admission_result = mechanism.admit(start); events.append("stale_admit:v1/g1_under_v2/g2")
                decision = mechanism.authorize_action(); events.append("stale_action:g2")
                retry_start = mechanism.capture_start(); events.append("retry_start:v2/g2")
                retry = mechanism.admit(retry_start); events.append("retry_conflict:v2/g2")
                retry_again = mechanism.admit(retry_start); events.append("retry_conflict_replay:v2/g2")
                retry_results = [{"outcome": retry.outcome, "conflict": retry.conflict}, {"outcome": retry_again.outcome, "conflict": retry_again.conflict}]
            elif variant == "E2F_F":
                mechanism.produce(); events.append("output_produced")
                admission_result = mechanism.admit(start); events.append("admit:v1/g1")
                read = mechanism.begin_action(); events.append("gateway_read:g1")
                mechanism.advance_policy(runtime.v2); events.append("policy:v2/g2_between_read_and_final")
                decision = mechanism.finalize_action(read); events.append("gateway_final:g2")
            else:
                raise ValueError(variant)
            envelope = admission_result.envelope
            immutable_snapshot = envelope.immutable()
            final_envelope = mechanism.envelope()
            traces = [action_trace(variant, envelope, decision)]
            conflict_trace = retry_results[0]["conflict"] if retry_results else None
            return {
                "ordered_events": events,
                "policy_snapshots": [plain(runtime.initial_policy), plain(runtime.v2), plain(runtime.v3)],
                "start_policy": plain(start),
                "admission_attempt": {"outcome": admission_result.outcome, "envelope_state": envelope.state, "bound_generation": envelope.bound_policy_generation, "current_policy_version_at_admission": admission_result.current_policy_version, "current_generation_at_admission": admission_result.current_generation},
                "envelope": PolicyAdmissionMechanism.envelope_record(final_envelope),
                "envelope_immutable_snapshot": immutable_snapshot,
                "action": plain(decision),
                "retry_conflict": retry_results,
                "audit_trace": traces,
                "conflict_audit_trace": conflict_trace,
                "envelope_count": int(mechanism.connection.execute("SELECT COUNT(*) FROM envelopes").fetchone()[0]),
                "conflict_count": len(mechanism.conflicts()),
                "state_digest": mechanism.state_digest(),
            }


def annotate_expected(variants: dict[str, dict[str, Any]], truth: ScorerGroundTruth) -> None:
    expected = dict(truth.expected_action_allowed)
    for variant, observation in variants.items():
        observation["action"]["expected_outcome"] = "ALLOW" if expected[variant] else "DENY"


def audit_complete(variant: str, observation: dict[str, Any]) -> bool:
    required = {"variant", "output_id", "bound_policy_version", "current_policy_version", "bound_generation", "current_generation", "bound_role", "bound_caps", "effective_cap", "admission_state", "freshness_decision", "action_allowed", "reason"}
    return len(observation["audit_trace"]) == 1 and required.issubset(observation["audit_trace"][0])


def score_variants(variants: dict[str, dict[str, Any]], truth: ScorerGroundTruth) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    annotate_expected(variants, truth)
    stale_attempts = sum(int(variants[name]["admission_attempt"]["envelope_state"] == "STALE_AT_ADMISSION") for name in ("E2F_B", "E2F_D", "E2F_E"))
    stale_accepted = sum(int(variants[name]["admission_attempt"]["outcome"] == "ADMITTED" and variants[name]["admission_attempt"]["envelope_state"] == "STALE_AT_ADMISSION") for name in ("E2F_B", "E2F_D", "E2F_E"))
    stale_action_names = ("E2F_B", "E2F_C", "E2F_D", "E2F_E", "E2F_F")
    stale_act = sum(int(variants[name]["action"]["allowed"]) for name in stale_action_names)
    aba_false = int(variants["E2F_D"]["action"]["allowed"])
    retry_ok = int(bool(variants["E2F_E"]["retry_conflict"]) and all(item["outcome"] == "RETRY_POLICY_CONFLICT" for item in variants["E2F_E"]["retry_conflict"]))
    duplicate = int(variants["E2F_E"]["envelope_count"] != 1)
    generation_mismatch = int(not variants["E2F_F"]["action"]["allowed"] and variants["E2F_F"]["action"]["reason"] == "POLICY_GENERATION_MISMATCH")
    rewrite_count = 0
    historical_count = len(variants)
    for observation in variants.values():
        if observation["envelope"] != observation["envelope_immutable_snapshot"] and any(observation["envelope"].get(field) != observation["envelope_immutable_snapshot"].get(field) for field in ("payload_digest", "start_policy_version", "start_policy_generation", "bound_policy_version", "bound_policy_generation", "bound_role", "bound_caps", "admitted_at_logical_step")):
            rewrite_count += 1
    audit = sum(int(audit_complete(name, observation)) for name, observation in variants.items())
    action_mismatches = sum(int(observation["action"]["allowed"] != dict(truth.expected_action_allowed)[name]) for name, observation in variants.items())
    invariant_results = {
        name: {
            "F1_immutable_history": all(observation["envelope"].get(field) == observation["envelope_immutable_snapshot"].get(field) for field in ("payload_digest", "start_policy_version", "start_policy_generation", "bound_policy_version", "bound_policy_generation", "bound_role", "bound_caps", "admitted_at_logical_step")),
            "F2_stale_admission_explicit": observation["admission_attempt"]["envelope_state"] in ("LIVE", "STALE_AT_ADMISSION"),
            "F3_no_aba_confusion": name != "E2F_D" or not observation["action"]["allowed"],
            "F4_retry_consistency": name != "E2F_E" or (observation["envelope_count"] == 1 and retry_ok == 1),
            "F5_action_freshness": not observation["action"]["allowed"] if name != "E2F_A" else observation["action"]["allowed"],
            "F6_auditability": audit_complete(name, observation),
        }
        for name, observation in variants.items()
    }
    for name, observation in variants.items():
        observation["invariant_results"] = invariant_results[name]
    metrics = {
        "stale_admission_attempts": {"numerator": stale_attempts, "denominator": 3, "value": stale_attempts / 3},
        "stale_admissions_accepted": {"numerator": stale_accepted, "denominator": stale_attempts, "value": stale_accepted / stale_attempts if stale_attempts else None},
        "stale_act_permits": {"numerator": stale_act, "denominator": 5, "value": stale_act},
        "aba_false_accepts": {"numerator": aba_false, "denominator": 1, "value": aba_false},
        "retry_policy_conflicts": {"numerator": retry_ok, "denominator": 1, "value": retry_ok},
        "duplicate_envelope_count": {"numerator": duplicate, "denominator": 1, "value": duplicate},
        "action_generation_mismatches": {"numerator": generation_mismatch, "denominator": 1, "value": generation_mismatch},
        "historical_rewrite_count": {"numerator": rewrite_count, "denominator": historical_count, "value": rewrite_count},
        "audit_trace_complete": {"numerator": audit, "denominator": 6, "value": audit / 6},
        "deterministic_replay_match": {"numerator": 0, "denominator": 1, "value": 0},
    }
    return invariant_results, {"metrics": metrics, "action_mismatches": action_mismatches}


def execute_once(runtime: RuntimeFixture, vault: GroundTruthVault) -> dict[str, Any]:
    leakage = mechanism_guard(runtime, vault)
    variants = {name: execute_variant(name, runtime) for name in ("E2F_A", "E2F_B", "E2F_C", "E2F_D", "E2F_E", "E2F_F")}
    control = variants["E2F_A"]
    if not (control["envelope"]["state"] == "LIVE" and control["envelope"]["bound_caps"][SCOPE] == "ACT" and control["action"]["allowed"] and control["action"]["reason"] == "CURRENT_GENERATION_MATCH"):
        raise RuntimeError("E2F-A positive control did not authorize under current generation")
    assert vault.reads == 0
    truth = vault.release_for_scoring()
    invariant_results, score = score_variants(variants, truth)
    return {"variants": variants, "truth": truth, "leakage": leakage, "score": score, "invariant_results": invariant_results}


def mechanical_verdict(run: dict[str, Any], replay_match: bool) -> tuple[str, str | None]:
    metrics = run["score"]["metrics"]
    aba = run["variants"]["E2F_D"]
    semantic_equal = digest(aba["policy_snapshots"][0]["caps"]) == digest(aba["policy_snapshots"][2]["caps"]) and aba["policy_snapshots"][0]["role"] == aba["policy_snapshots"][2]["role"]
    generations_distinct = aba["policy_snapshots"][0]["generation"] != aba["policy_snapshots"][2]["generation"]
    design_kill = not semantic_equal or not generations_distinct
    if design_kill:
        return "DESIGN-KILL", "ABA semantic/generation distinction is not representable"
    robust = (
        all(run["variants"][name]["invariant_results"].values() for name in run["variants"])
        and metrics["stale_act_permits"]["value"] == 0
        and metrics["aba_false_accepts"]["value"] == 0
        and metrics["retry_policy_conflicts"]["value"] == 1
        and metrics["duplicate_envelope_count"]["value"] == 0
        and metrics["action_generation_mismatches"]["value"] == 1
        and metrics["historical_rewrite_count"]["value"] == 0
        and metrics["audit_trace_complete"]["value"] == 1
        and replay_match
    )
    if robust:
        return "TOCTOU-ROBUST", None
    contained = (
        metrics["stale_act_permits"]["value"] == 0
        and metrics["aba_false_accepts"]["value"] == 0
        and metrics["duplicate_envelope_count"]["value"] == 0
        and metrics["retry_policy_conflicts"]["value"] == 1
        and metrics["historical_rewrite_count"]["value"] == 0
    )
    if contained:
        return "TOCTOU-FAIL-CONTAINED", "non-safety S3 observability/state-label gate"
    return "TOCTOU-FAIL", "stale_act_permits" if metrics["stale_act_permits"]["value"] else "first_failed_invariant"


def fixture_digest(runtime: RuntimeFixture) -> str:
    return digest({"operation": plain(runtime.operation), "policies": [plain(runtime.initial_policy), plain(runtime.v2), plain(runtime.v3)], "selected_semantics": "S3_ACTION_CURRENT"})


def result_core(run: dict[str, Any], runtime: RuntimeFixture, replay_match: bool) -> dict[str, Any]:
    return {"variants": run["variants"], "metrics": run["score"]["metrics"], "ground_truth_digest": digest(plain(run["truth"])), "replay_match": replay_match, "fixture_digest": fixture_digest(runtime)}


def render_result(result: Mapping[str, Any], canonical_digest: str) -> str:
    lines = [
        f"# E2F Policy Admission TOCTOU\n\nVerdict: **{result['verdict']}**.",
        f"\nCanonical result digest: `{canonical_digest}`.",
        "\nSelected semantics: `S3_ACTION_CURRENT`.",
        "\n## Variant outcomes",
    ]
    for name, variant in result["variants"].items():
        lines.append(f"- `{name}`: `{variant['action']['actual_outcome'] if 'actual_outcome' in variant['action'] else ('ALLOW' if variant['action']['allowed'] else 'DENY')}`; reason `{variant['action']['reason']}`")
    lines.append("\n## Metrics")
    for name, value in result["metrics"].items():
        lines.append(f"- `{name}`: {value['numerator']}/{value['denominator']} (value `{value['value']}`)")
    lines.extend((
        "\n## Integrity",
        f"\nPLAN immutable: `{result['plan_immutable']}`.",
        f"\nGround-truth leakage guard passed: `{result['leakage_guard']['passed']}`.",
        f"\nHistorical rewrite count: `{result['historical_immutability']['historical_rewrite_count']}`.",
        "\nThis logical SQLite experiment makes no production atomicity or readiness claim.",
        "\n## Next gate",
        "\nAny further experiment requires separate preregistration and authorization.",
    ))
    return "\n".join(lines) + "\n"


def build_result() -> dict[str, Any]:
    plan_immutable = hashlib.sha256((OUT / "PLAN.md").read_bytes()).hexdigest() == PLAN_SHA256
    if not plan_immutable:
        raise RuntimeError("PLAN.md differs from the frozen preregistration")
    runtime = fixture()
    first_vault = GroundTruthVault(ground_truth())
    first = execute_once(runtime, first_vault)
    second_vault = GroundTruthVault(ground_truth())
    second = execute_once(runtime, second_vault)
    first_core = result_core(first, runtime, False)
    second_core = result_core(second, runtime, False)
    replay_match = digest(first_core) == digest(second_core)
    first["score"]["metrics"]["deterministic_replay_match"] = {"numerator": int(replay_match), "denominator": 1, "value": int(replay_match)}
    verdict, first_failed = mechanical_verdict(first, replay_match)
    aba = first["variants"]["E2F_D"]
    v1 = aba["policy_snapshots"][0]
    v3 = aba["policy_snapshots"][2]
    historical = []
    for name, variant in first["variants"].items():
        historical.append({"variant": name, "before": variant["envelope_immutable_snapshot"], "after": variant["envelope"], "unchanged": variant["envelope"] == variant["envelope_immutable_snapshot"]})
    source_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "e2d_commit": E2D_COMMIT,
        "e2e_commit": E2E_COMMIT,
        "plan_sha256": PLAN_SHA256,
        "experiment_source_digest": source_digest,
        "fixture_digest": fixture_digest(runtime),
        "ground_truth_digest": digest(plain(first["truth"])),
        "selected_semantics": "S3_ACTION_CURRENT",
        "candidate_semantics_summary": {"S1": "START_SNAPSHOT", "S2": "ADMISSION_CURRENT", "S3": "ACTION_CURRENT", "S4": "GENERATION_LEASE"},
        "variants": first["variants"],
        "metrics": first["score"]["metrics"],
        "aba_proof": {"v1_semantic_policy": {"role": v1["role"], "caps": v1["caps"]}, "v3_semantic_policy": {"role": v3["role"], "caps": v3["caps"]}, "semantic_equal": v1["role"] == v3["role"] and v1["caps"] == v3["caps"], "generations_distinct": v1["generation"] != v3["generation"], "v1_generation": v1["generation"], "v3_generation": v3["generation"], "stale_action_result": aba["action"]},
        "leakage_guard": first["leakage"],
        "historical_immutability": {"historical_rewrite_count": first["score"]["metrics"]["historical_rewrite_count"]["numerator"], "envelopes": historical},
        "plan_immutable": plan_immutable,
        "verdict": verdict,
        "first_failed_invariant": first_failed,
        "determinism": {"independent_core_replay_match": replay_match},
    }
    canonical_payload = {key: value for key, value in result.items() if key != "canonical_result_digest"}
    result["canonical_result_digest"] = digest(canonical_payload)
    return result


def main() -> int:
    result = build_result()
    canonical_digest = result["canonical_result_digest"]
    (OUT / "result.json").write_bytes(canonical_bytes(result))
    (OUT / "RESULT.md").write_text(render_result(result, canonical_digest), encoding="utf-8")
    print(f"E2F VERDICT: {result['verdict']}")
    print(f"canonical result digest: {canonical_digest}")
    print(f"preregistration commit: {PREREGISTRATION_COMMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
