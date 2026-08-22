#!/usr/bin/env python3
"""Execute the frozen E2E operation-role misclassification experiment.

This is an isolated logical prototype of Architecture A.  It uses only the
runtime fixture and a small durable SQLite state machine; the scorer's hidden
ground truth is constructed separately and is released only after both arms
finish.  No production Custody module is imported or changed.
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
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
EXPERIMENT_ID = "E2E_POLICY_MISCLASSIFICATION"
PREREGISTRATION_COMMIT = "baba4f8fb54a7573d7882cfeda2283e4cc50347f"
DESIGN_COMMIT = "3192ec84e6bcaaa39d25d49c8a4056a4ab6e2fbf"
E2D_COMMIT = "d5b671ba1c09f7ac70b08d9ad54ba9b8eccf69c3"
DEPARTMENT = "finance"
TOOL = "vendor_lookup"
OPERATION = "lookup"
R1 = "sha256/2:e2e-vendor-lookup-r1"
R2 = "sha256/2:e2e-vendor-lookup-r2"
SOURCE = TOOL
SCOPES = ("export.send", "payroll.read")
WINDOW_ID = "window-e2e-r1"
WINDOW_START = "2026-08-12T00:00:00Z"
WINDOW_END = "2026-08-19T00:00:00Z"
CORRECTION_TIME = "2026-08-20T00:00:00Z"
TIER_RANK = {"NONE": 0, "INFORM": 1, "ACT": 2}
TRANSFORM_CAP = {"REGISTERED": "ACT", "IDENTITY": "ACT", "FREEFORM": "INFORM"}
UNKNOWN_CONTEXT = "UNKNOWN_CONTEXT"

R1_ROOT = "e2e-r1-root"
R1_REGISTERED = "e2e-r1-registered"
R1_FREEFORM = "e2e-r1-freeform"
R1_CROSS = "e2e-r1-cross-agent"
CLEAN_EXPORT = "e2e-clean-export-root"
CLEAN_PAYROLL = "e2e-clean-payroll-root"
R1_MIXED = "e2e-r1-mixed"
R2_ROOT = "e2e-r2-root"
R2_REGISTERED = "e2e-r2-registered"
R1_POST = "e2e-r1-post-correction"
R1_AFFECTED = (R1_ROOT, R1_REGISTERED, R1_FREEFORM, R1_CROSS, R1_MIXED)
R2_CONTROLS = (R2_ROOT, R2_REGISTERED)
SAFE_CONTROLS = (R2_ROOT, R2_REGISTERED, CLEAN_EXPORT, CLEAN_PAYROLL, R1_POST)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {k: plain(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def cap_min(values: Iterable[str]) -> str:
    values = tuple(values)
    return min(values, key=TIER_RANK.__getitem__) if values else "NONE"


def policy_caps(export: str, payroll: str) -> tuple[tuple[str, str], ...]:
    return (("export.send", export), ("payroll.read", payroll))


@dataclass(frozen=True)
class RuntimePolicy:
    key: str
    operation: str
    revision: str
    role: str
    caps: tuple[tuple[str, str], ...]
    version: str

    def cap_map(self) -> dict[str, str]:
        return dict(self.caps)


@dataclass(frozen=True)
class RuntimeRecord:
    output_id: str
    payload: str
    operation: str
    revision: str
    department: str
    source: str
    admitted_at: str
    direct_parent_ids: tuple[str, ...]
    transform_class: str | None
    policy_key: str
    operation_role: str
    configured_caps: tuple[tuple[str, str], ...]
    producer: str

    def cap_map(self) -> dict[str, str]:
        return dict(self.configured_caps)


@dataclass(frozen=True)
class RuntimeAction:
    request_id: str
    phase: str
    scope: str
    citations: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeWindow:
    window_id: str
    department: str
    source: str
    operation: str
    revision: str
    start: str
    end: str
    generation: int


@dataclass(frozen=True)
class RuntimeFixture:
    policies: tuple[RuntimePolicy, ...]
    records: tuple[RuntimeRecord, ...]
    initial_record_ids: tuple[str, ...]
    actions: tuple[RuntimeAction, ...]
    window: RuntimeWindow
    correction_time: str

    def record(self, output_id: str) -> RuntimeRecord:
        for record in self.records:
            if record.output_id == output_id:
                return record
        raise KeyError(output_id)

    def policy(self, key: str) -> RuntimePolicy:
        for policy in self.policies:
            if policy.key == key:
                return policy
        raise KeyError(key)


@dataclass(frozen=True)
class ScorerGroundTruth:
    attacker_controlled: tuple[str, ...]
    misclassified: tuple[str, ...]
    expected_affected: tuple[str, ...]
    expected_safe: tuple[str, ...]
    expected_scope: tuple[str, ...]
    expected_revision: tuple[str, ...]
    expected_outcome: tuple[tuple[str, str, bool], ...]
    expected_history_digest: str


class GroundTruthVault:
    def __init__(self, truth: ScorerGroundTruth) -> None:
        self._truth = truth
        self.reads = 0

    def release_for_scoring(self) -> ScorerGroundTruth:
        self.reads += 1
        return self._truth


def _policy(arm: str) -> tuple[RuntimePolicy, ...]:
    r1_role = "RELAY" if arm == "CONTROL" else "ORIGIN"
    r1_caps = policy_caps("INFORM", "INFORM") if arm == "CONTROL" else policy_caps("ACT", "INFORM")
    return (
        RuntimePolicy("vendor_lookup/R1", TOOL, R1, r1_role, r1_caps, "policy-v1"),
        RuntimePolicy("vendor_lookup/R2", TOOL, R2, "RELAY", policy_caps("INFORM", "INFORM"), "policy-v1"),
        RuntimePolicy("clean_export/lookup/R1", "clean_export", "clean-r1", "ORIGIN", policy_caps("ACT", "NONE"), "policy-v1"),
        RuntimePolicy("clean_payroll/lookup/R1", "clean_payroll", "clean-r1", "ORIGIN", policy_caps("NONE", "ACT"), "policy-v1"),
    )


def _rows() -> tuple[dict[str, Any], ...]:
    """Fixed corpus without arm-dependent policy labels."""
    return (
        {"id": R1_ROOT, "payload": "Account for Acme settlement: ACCT-EVIL-22.", "operation": OPERATION, "revision": R1, "source": SOURCE, "at": "2026-08-15T00:00:00Z", "parents": (), "class": None, "policy": "vendor_lookup/R1", "producer": TOOL},
        {"id": R1_REGISTERED, "payload": "Registered ledger join: ACCT-EVIL-22.", "operation": "registered/synthesis", "revision": "registered-v1", "source": "registered/synthesis", "at": "2026-08-15T00:00:01Z", "parents": (R1_ROOT,), "class": "REGISTERED", "policy": "transform/registered-v1", "producer": "registered/synthesis"},
        {"id": R1_FREEFORM, "payload": "For records: use ACCT-EVIL-22 for Acme settlement.", "operation": "model/freeform", "revision": "freeform-v1", "source": "model/freeform", "at": "2026-08-15T00:00:02Z", "parents": (R1_ROOT,), "class": "FREEFORM", "policy": "transform/freeform-v1", "producer": "model/freeform"},
        {"id": R1_CROSS, "payload": "Registered ledger join: ACCT-EVIL-22.", "operation": "cross-agent/relay", "revision": "identity-v1", "source": "cross-agent/relay", "at": "2026-08-15T00:00:03Z", "parents": (R1_REGISTERED,), "class": "IDENTITY", "policy": "transform/identity-v1", "producer": "cross-agent/relay"},
        {"id": CLEAN_EXPORT, "payload": "Clean export authority: CLEAN-EXPORT-2026.", "operation": "clean_export", "revision": "clean-r1", "source": "clean_export", "at": "2026-08-10T00:00:00Z", "parents": (), "class": None, "policy": "clean_export/lookup/R1", "producer": "clean_export"},
        {"id": CLEAN_PAYROLL, "payload": "Payroll read authority: PAYROLL-2026.", "operation": "clean_payroll", "revision": "clean-r1", "source": "clean_payroll", "at": "2026-08-10T00:00:01Z", "parents": (), "class": None, "policy": "clean_payroll/lookup/R1", "producer": "clean_payroll"},
        {"id": R1_MIXED, "payload": "Mixed synthesis: clean export plus ACCT-EVIL-22.", "operation": "registered/synthesis", "revision": "registered-v1", "source": "registered/synthesis", "at": "2026-08-15T00:00:04Z", "parents": (R1_ROOT, CLEAN_EXPORT), "class": "REGISTERED", "policy": "transform/registered-v1", "producer": "registered/synthesis"},
        {"id": R2_ROOT, "payload": "Account for Acme settlement: ACCT-EVIL-22.", "operation": OPERATION, "revision": R2, "source": SOURCE, "at": "2026-08-15T00:00:05Z", "parents": (), "class": None, "policy": "vendor_lookup/R2", "producer": TOOL},
        {"id": R2_REGISTERED, "payload": "R2 registered ledger join: ACCT-EVIL-22.", "operation": "registered/synthesis", "revision": "registered-v1", "source": "registered/synthesis", "at": "2026-08-15T00:00:06Z", "parents": (R2_ROOT,), "class": "REGISTERED", "policy": "transform/registered-v1", "producer": "registered/synthesis"},
        {"id": R1_POST, "payload": "Late vendor lookup: ACCT-EVIL-22.", "operation": TOOL, "revision": R1, "source": SOURCE, "at": "2026-08-21T00:00:00Z", "parents": (), "class": None, "policy": "vendor_lookup/R1", "producer": TOOL},
    )


def _actions() -> tuple[RuntimeAction, ...]:
    actions: list[RuntimeAction] = [
        RuntimeAction("a-direct-export", "BEFORE_CORRECTION", "export.send", (R1_ROOT,)),
        RuntimeAction("a-direct-payroll", "BEFORE_CORRECTION", "payroll.read", (R1_ROOT,)),
        RuntimeAction("b-registered-export", "BEFORE_CORRECTION", "export.send", (R1_REGISTERED,)),
        RuntimeAction("b-freeform-export", "BEFORE_CORRECTION", "export.send", (R1_FREEFORM,)),
        RuntimeAction("b-cross-export", "BEFORE_CORRECTION", "export.send", (R1_CROSS,)),
        RuntimeAction("b-mixed-export", "BEFORE_CORRECTION", "export.send", (R1_MIXED,)),
    ]
    for record_id in R1_AFFECTED:
        actions.append(RuntimeAction(f"b-{record_id}-payroll", "BEFORE_CORRECTION", "payroll.read", (record_id,)))
    actions.extend(
        (
            RuntimeAction("b-clean-export", "BEFORE_CORRECTION", "export.send", (CLEAN_EXPORT,)),
            RuntimeAction("b-clean-payroll", "BEFORE_CORRECTION", "payroll.read", (CLEAN_PAYROLL,)),
            RuntimeAction("b-r2-root", "BEFORE_CORRECTION", "export.send", (R2_ROOT,)),
            RuntimeAction("b-r2-registered", "BEFORE_CORRECTION", "export.send", (R2_REGISTERED,)),
            RuntimeAction("c-old-registered-before-revoke", "AFTER_CORRECTION", "export.send", (R1_REGISTERED,)),
            RuntimeAction("c-post-correction-root", "AFTER_CORRECTION", "export.send", (R1_POST,)),
        )
    )
    for record_id in R1_AFFECTED:
        actions.append(RuntimeAction(f"c-{record_id}-after-revoke", "AFTER_REVOKE", "export.send", (record_id,)))
    actions.extend(
        (
            RuntimeAction("c-r2-root-after-revoke", "AFTER_REVOKE", "export.send", (R2_ROOT,)),
            RuntimeAction("c-r2-registered-after-revoke", "AFTER_REVOKE", "export.send", (R2_REGISTERED,)),
            RuntimeAction("c-clean-export-after-revoke", "AFTER_REVOKE", "export.send", (CLEAN_EXPORT,)),
            RuntimeAction("c-clean-payroll-after-revoke", "AFTER_REVOKE", "payroll.read", (CLEAN_PAYROLL,)),
            RuntimeAction("c-post-correction-after-revoke", "AFTER_REVOKE", "export.send", (R1_POST,)),
        )
    )
    return tuple(actions)


def runtime_fixture(arm: str) -> RuntimeFixture:
    policies = _policy(arm)
    policy_map = {p.key: p for p in policies}
    records: list[RuntimeRecord] = []
    for row in _rows():
        policy = policy_map.get(row["policy"])
        if row["id"] == R1_POST:
            # This row is admitted after the fixed correction in E2E-C.
            role, caps = "RELAY", policy_caps("INFORM", "INFORM")
        elif policy is None:
            role, caps = "RELAY", policy_caps("ACT", "ACT")
        else:
            role, caps = policy.role, policy.caps
        records.append(
            RuntimeRecord(
                output_id=row["id"], payload=row["payload"], operation=row["operation"],
                revision=row["revision"], department=DEPARTMENT, source=row["source"],
                admitted_at=row["at"], direct_parent_ids=tuple(row["parents"]),
                transform_class=row["class"], policy_key=row["policy"],
                operation_role=role, configured_caps=tuple(caps), producer=row["producer"],
            )
        )
    return RuntimeFixture(
        policies=tuple(policies), records=tuple(records),
        initial_record_ids=tuple(row["id"] for row in _rows() if row["id"] != R1_POST),
        actions=_actions(),
        window=RuntimeWindow(WINDOW_ID, DEPARTMENT, SOURCE, OPERATION, R1, WINDOW_START, WINDOW_END, 1),
        correction_time=CORRECTION_TIME,
    )


def ground_truth() -> ScorerGroundTruth:
    expected = []
    for arm in ("CONTROL", "TREATMENT"):
        expected.extend(
            (
                (arm, "a-direct-export", arm == "TREATMENT"),
                (arm, "a-direct-payroll", False),
                (arm, "b-registered-export", arm == "TREATMENT"),
                (arm, "b-freeform-export", False),
                (arm, "b-cross-export", arm == "TREATMENT"),
                (arm, "b-mixed-export", arm == "TREATMENT"),
                (arm, "b-clean-export", True),
                (arm, "b-clean-payroll", True),
                (arm, "b-r2-root", False),
                (arm, "b-r2-registered", False),
                (arm, "c-old-registered-before-revoke", arm == "TREATMENT"),
                (arm, "c-post-correction-root", False),
            )
        )
        for record_id in R1_AFFECTED:
            expected.append((arm, f"b-{record_id}-payroll", False))
        for record_id in R1_AFFECTED:
            expected.append((arm, f"c-{record_id}-after-revoke", False))
        expected.extend(
            (
                (arm, "c-r2-root-after-revoke", False),
                (arm, "c-r2-registered-after-revoke", False),
                (arm, "c-clean-export-after-revoke", True),
                (arm, "c-clean-payroll-after-revoke", True),
                (arm, "c-post-correction-after-revoke", False),
            )
        )
    history = {record_id: {"id": record_id, "revision": next(r.revision for r in runtime_fixture("CONTROL").records if r.output_id == record_id)} for record_id in R1_AFFECTED}
    return ScorerGroundTruth(
        attacker_controlled=(R1_ROOT,), misclassified=(R1_ROOT,),
        expected_affected=R1_AFFECTED, expected_safe=SAFE_CONTROLS,
        expected_scope=R1_AFFECTED, expected_revision=R2_CONTROLS,
        expected_outcome=tuple(expected), expected_history_digest=digest(history),
    )


@dataclass(frozen=True)
class RootRef:
    record_id: str
    source: str
    revision: str
    admitted_at: str | None


@dataclass(frozen=True)
class AdmissionEnvelope:
    output_id: str
    direct_parent_ids: tuple[str, ...]
    support_roots: tuple[RootRef, ...]
    bound_caps: tuple[tuple[str, str], ...]
    transform_class: str | None
    operation_role: str
    source: str
    revision: str
    admitted_at: str
    payload_sha256: str
    policy_version: str
    generation: int
    replacement_of: str | None = None

    def caps(self) -> dict[str, str]:
        return dict(self.bound_caps)


class StructuralEnvelopeA:
    """Deep module for admission, lineage, scoped gateway, and overlay state."""

    def __init__(self, db_path: Path, fixture: RuntimeFixture) -> None:
        self.db_path = db_path
        self.fixture = fixture
        self.connection = sqlite3.connect(str(db_path))
        self.connection.row_factory = sqlite3.Row
        self._init_db()
        self._load_policy()

    def _init_db(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS envelopes (id TEXT PRIMARY KEY, data TEXT NOT NULL, published INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS policies (key TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS windows (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            """
        )
        if self.connection.execute("SELECT 1 FROM meta WHERE key='generation'").fetchone() is None:
            self.connection.execute("INSERT INTO meta(key,value) VALUES('generation','0')")
            self.connection.execute("INSERT INTO meta(key,value) VALUES('blocked','[]')")
            self.connection.execute("INSERT INTO meta(key,value) VALUES('repair_plan','[]')")
        self.connection.commit()

    def _load_policy(self) -> None:
        if self.connection.execute("SELECT 1 FROM policies LIMIT 1").fetchone() is None:
            with self.connection:
                for policy in self.fixture.policies:
                    self.connection.execute("INSERT INTO policies(key,data) VALUES(?,?)", (policy.key, json.dumps(plain(policy), sort_keys=True)))

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "StructuralEnvelopeA":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _blocked(self) -> set[str]:
        row = self.connection.execute("SELECT value FROM meta WHERE key='blocked'").fetchone()
        return set(json.loads(row[0]))

    def _generation(self) -> int:
        return int(self.connection.execute("SELECT value FROM meta WHERE key='generation'").fetchone()[0])

    def _save_envelope(self, envelope: AdmissionEnvelope) -> None:
        data = plain(envelope)
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO envelopes(id,data,published) VALUES(?,?,0)",
                (envelope.output_id, json.dumps(data, sort_keys=True)),
            )
            self.connection.execute("UPDATE envelopes SET published=1 WHERE id=?", (envelope.output_id,))

    def _load_envelope(self, output_id: str) -> AdmissionEnvelope:
        row = self.connection.execute("SELECT data,published FROM envelopes WHERE id=?", (output_id,)).fetchone()
        if row is None or not row[1]:
            raise KeyError(output_id)
        data = json.loads(row[0])
        return AdmissionEnvelope(
            output_id=data["output_id"], direct_parent_ids=tuple(data["direct_parent_ids"]),
            support_roots=tuple(RootRef(**root) for root in data["support_roots"]),
            bound_caps=tuple(tuple(pair) for pair in data["bound_caps"]),
            transform_class=data["transform_class"], operation_role=data["operation_role"],
            source=data["source"], revision=data["revision"], admitted_at=data["admitted_at"],
            payload_sha256=data["payload_sha256"], policy_version=data["policy_version"],
            generation=int(data["generation"]), replacement_of=data.get("replacement_of"),
        )

    def _policy_version(self, policy_key: str) -> str:
        row = self.connection.execute("SELECT data FROM policies WHERE key=?", (policy_key,)).fetchone()
        if row is None:
            return "policy-v1"
        return json.loads(row[0])["version"]

    def _derive(self, record: RuntimeRecord, cache: dict[str, AdmissionEnvelope]) -> AdmissionEnvelope:
        if record.output_id in cache:
            return cache[record.output_id]
        parents = [self._derive(self.fixture.record(parent_id), cache) for parent_id in record.direct_parent_ids]
        if not parents:
            if record.operation_role == "RELAY":
                support = (RootRef(UNKNOWN_CONTEXT, "", "", None),)
                caps = {scope: "INFORM" for scope in SCOPES}
            else:
                support = (RootRef(record.output_id, record.source, record.revision, record.admitted_at),)
                caps = record.cap_map()
        else:
            transform_cap = TRANSFORM_CAP[record.transform_class or "REGISTERED"]
            caps = {scope: cap_min((transform_cap,) + tuple(parent.caps()[scope] for parent in parents)) for scope in SCOPES}
            roots: dict[str, RootRef] = {}
            for parent in parents:
                for root in parent.support_roots:
                    roots[root.record_id] = root
            support = tuple(roots[key] for key in sorted(roots))
        envelope = AdmissionEnvelope(
            output_id=record.output_id, direct_parent_ids=record.direct_parent_ids,
            support_roots=support, bound_caps=tuple((scope, caps[scope]) for scope in SCOPES),
            transform_class=record.transform_class, operation_role=record.operation_role,
            source=record.source, revision=record.revision, admitted_at=record.admitted_at,
            payload_sha256=sha256_text(record.payload), policy_version=self._policy_version(record.policy_key),
            generation=self._generation(),
        )
        self._save_envelope(envelope)
        cache[record.output_id] = envelope
        return envelope

    def admit_initial(self) -> None:
        cache: dict[str, AdmissionEnvelope] = {}
        for record_id in self.fixture.initial_record_ids:
            self._derive(self.fixture.record(record_id), cache)

    def admit_record(self, output_id: str) -> None:
        self._derive(self.fixture.record(output_id), {})

    def correct_policy(self) -> None:
        policy = RuntimePolicy("vendor_lookup/R1", TOOL, R1, "RELAY", policy_caps("INFORM", "INFORM"), "policy-v2")
        with self.connection:
            self.connection.execute("UPDATE policies SET data=? WHERE key=?", (json.dumps(plain(policy), sort_keys=True), policy.key))
            self.connection.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('policy_correction','ORIGIN->RELAY')")

    def activate_window(self) -> dict[str, Any]:
        window = self.fixture.window
        selected = []
        for record in self.fixture.records:
            if record.direct_parent_ids:
                continue
            if (record.department, record.source, record.operation, record.revision) != (window.department, window.source, window.operation, window.revision):
                continue
            if window.start <= record.admitted_at < window.end:
                selected.append(record.output_id)
        closure = set(selected)
        changed = True
        while changed:
            changed = False
            for record in self.fixture.records:
                if record.output_id in closure or not record.direct_parent_ids:
                    continue
                if any(parent in closure for parent in record.direct_parent_ids):
                    closure.add(record.output_id)
                    changed = True
        blocked = [record.output_id for record in self.fixture.records if record.output_id in closure]
        generation = window.generation
        with self.connection:
            self.connection.execute("UPDATE meta SET value=? WHERE key='generation'", (str(generation),))
            self.connection.execute("UPDATE meta SET value=? WHERE key='blocked'", (json.dumps(blocked),))
            self.connection.execute("UPDATE meta SET value=? WHERE key='repair_plan'", (json.dumps([{"target_id": item, "mode": "BLOCK"} for item in blocked], sort_keys=True),))
            self.connection.execute("INSERT OR REPLACE INTO windows(id,data) VALUES(?,?)", (window.window_id, json.dumps(plain(window), sort_keys=True)))
        return {"selector": plain(window), "selected_roots": selected, "closure": blocked, "generation": generation}

    def _snapshot(self, record_id: str) -> dict[str, Any]:
        record = self.fixture.record(record_id)
        envelope = self._load_envelope(record_id)
        blocked = record_id in self._blocked()
        effective = {scope: ("NONE" if blocked else cap) for scope, cap in envelope.bound_caps}
        return {
            "id": record.output_id, "payload_sha256": envelope.payload_sha256,
            "direct_parent_ids": list(envelope.direct_parent_ids),
            "support_roots": [plain(root) for root in envelope.support_roots],
            "bound_caps": dict(envelope.bound_caps), "effective_caps": effective,
            "transform_class": envelope.transform_class, "operation_role": envelope.operation_role,
            "source": envelope.source, "revision": envelope.revision,
            "admitted_at": envelope.admitted_at, "policy_version": envelope.policy_version,
            "state": "BLOCKED" if blocked else "LIVE", "published": True,
            "generation": envelope.generation, "replacement_of": envelope.replacement_of,
        }

    def snapshots(self, ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
        ids = tuple(ids or (record.output_id for record in self.fixture.records if record.output_id != R1_POST))
        return [self._snapshot(record_id) for record_id in ids]

    def action(self, action: RuntimeAction) -> dict[str, Any]:
        cited = [self._snapshot(record_id) for record_id in action.citations]
        effective = cap_min(snapshot["effective_caps"].get(action.scope, "NONE") for snapshot in cited)
        allowed = bool(cited) and all(snapshot["state"] == "LIVE" for snapshot in cited) and effective == "ACT"
        if not cited:
            reason = "NO_CITATION"
        elif any(snapshot["state"] != "LIVE" for snapshot in cited):
            reason = "EFFECTIVE_BLOCKED_BY_REVOCATION"
        elif effective != "ACT":
            reason = f"EFFECTIVE_TIER_{effective}_BELOW_ACT"
        else:
            reason = "ACT_AUTHORITY"
        return {"request_id": action.request_id, "phase": action.phase, "scope": action.scope, "citations": list(action.citations), "actual_outcome": "ALLOW" if allowed else "DENY", "allowed": allowed, "reason": reason}

    def actions(self, phase: str) -> list[dict[str, Any]]:
        return [self.action(action) for action in self.fixture.actions if action.phase == phase]

    def authority_trace(self, record_id: str, scope: str) -> list[dict[str, Any]]:
        record = self.fixture.record(record_id)
        envelope = self._load_envelope(record_id)
        parent_meet = []
        for parent_id in record.direct_parent_ids:
            parent = self._snapshot(parent_id)
            parent_meet.append({"parent_id": parent_id, "bound_cap": parent["bound_caps"][scope]})
        return [
            {"step": "root_policy_assignment", "role": envelope.operation_role, "bound_cap": envelope.bound_caps and dict(envelope.bound_caps).get(scope)},
            {"step": "transformation_cap", "transform_class": record.transform_class, "cap": TRANSFORM_CAP.get(record.transform_class or "ROOT", dict(envelope.bound_caps).get(scope))},
            {"step": "parent_meet", "parents": parent_meet, "result": dict(envelope.bound_caps).get(scope)},
            {"step": "support_closure", "support_roots": [plain(root) for root in envelope.support_roots]},
            {"step": "current_revocation_generation", "generation": self._generation()},
            {"step": "effective_cap", "cap": self._snapshot(record_id)["effective_caps"].get(scope)},
            {"step": "action_gateway_decision", "scope": scope, "decision": "ALLOW" if self._snapshot(record_id)["effective_caps"].get(scope) == "ACT" else "DENY"},
        ]

    def state_digest(self) -> str:
        rows = {
            "envelopes": [{"id": row[0], "data": json.loads(row[1]), "published": row[2]} for row in self.connection.execute("SELECT id,data,published FROM envelopes ORDER BY id")],
            "policies": [{"key": row[0], "data": json.loads(row[1])} for row in self.connection.execute("SELECT key,data FROM policies ORDER BY key")],
            "meta": [{"key": row[0], "value": row[1]} for row in self.connection.execute("SELECT key,value FROM meta ORDER BY key")],
            "windows": [{"id": row[0], "data": json.loads(row[1])} for row in self.connection.execute("SELECT id,data FROM windows ORDER BY id")],
        }
        return digest(rows)


def forbidden_runtime_keys(value: Any) -> list[str]:
    forbidden = {"attacker_controlled", "misclassified", "expected_affected", "expected_outcome", "malicious", "scorer_only"}
    found: set[str] = set()
    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_lower = str(key).lower()
                if key_lower in forbidden or any(token in key_lower for token in ("attacker", "misclass", "expected", "malicious", "scorer_only")):
                    found.add(str(key))
                walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
    walk(value)
    return sorted(found)


def leakage_guard(fixtures: Mapping[str, RuntimeFixture], vault: GroundTruthVault) -> dict[str, Any]:
    runtime_keys = []
    for arm, fixture in fixtures.items():
        runtime_keys.extend(forbidden_runtime_keys(plain(fixture)))
    constructor_parameters = set(inspect.signature(StructuralEnvelopeA).parameters)
    assert "ground_truth" not in constructor_parameters
    mech_attrs: list[str] = []
    with tempfile.TemporaryDirectory(prefix="e2e-guard-") as directory:
        with StructuralEnvelopeA(Path(directory) / "guard.sqlite", fixtures["CONTROL"]) as mechanism:
            mech_attrs = sorted(vars(mechanism))
    assert not any("truth" in key.lower() or "scorer" in key.lower() for key in mech_attrs)
    assert not runtime_keys
    assert vault.reads == 0
    return {"runtime_forbidden_keys": [], "constructor_has_ground_truth": False, "mechanism_hidden_truth_attributes": [], "scorer_reads_before_execution": 0, "passed": True}


def record_map(snapshot: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in snapshot}


def action_map(actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {action["request_id"]: action for action in actions}


def annotate_expected(observation: dict[str, Any], arm: str, truth: ScorerGroundTruth) -> None:
    expected = {(truth_arm, request_id): allowed for truth_arm, request_id, allowed in truth.expected_outcome}
    for field in ("actions_before_correction", "actions_before_explicit_revoke", "actions_after_recovery"):
        for action in observation[field]:
            action["expected_outcome"] = "ALLOW" if expected[(arm, action["request_id"])] else "DENY"


def run_arm(arm: str, fixture: RuntimeFixture) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"e2e-{arm.lower()}-") as directory:
        db_path = Path(directory) / "state.sqlite"
        with StructuralEnvelopeA(db_path, fixture) as mechanism:
            mechanism.admit_initial()
            before = mechanism.snapshots()
            actions_before = mechanism.actions("BEFORE_CORRECTION")
            mechanism.correct_policy()
            mechanism.admit_record(R1_POST)
            after_correction = mechanism.snapshots(tuple(record_id for record_id in fixture.initial_record_ids) + (R1_POST,))
            correction_actions = mechanism.actions("AFTER_CORRECTION")
            revocation = mechanism.activate_window()
            after_revoke = mechanism.snapshots(tuple(record_id for record_id in fixture.initial_record_ids) + (R1_POST,))
            after_revoke_actions = mechanism.actions("AFTER_REVOKE")
            traces = {}
            if arm == "TREATMENT":
                for record_id in (R1_ROOT, R1_REGISTERED, R1_CROSS, R1_MIXED):
                    traces[record_id] = mechanism.authority_trace(record_id, "export.send")
            state_digest = mechanism.state_digest()
        return {
            "arm": arm, "policy_initial": [plain(policy) for policy in fixture.policies],
            "policy_after_correction": [{**plain(policy), "role": "RELAY" if policy.key == "vendor_lookup/R1" else policy.role, "caps": list(policy_caps("INFORM", "INFORM") if policy.key == "vendor_lookup/R1" else policy.caps), "version": "policy-v2" if policy.key == "vendor_lookup/R1" else policy.version} for policy in fixture.policies],
            "records_before_correction": before, "records_after_correction": after_correction,
            "records_after_recovery": after_revoke, "actions_before_correction": actions_before,
            "actions_before_explicit_revoke": correction_actions, "actions_after_recovery": after_revoke_actions,
            "authority_traces": traces, "revocation": revocation, "final_state_digest": state_digest,
        }


def historical_rewrite_count(observation: dict[str, Any], fixture: RuntimeFixture) -> tuple[int, int]:
    before = record_map(observation["records_before_correction"])
    after = record_map(observation["records_after_correction"])
    fields = ("operation_role", "bound_caps", "direct_parent_ids", "support_roots", "revision", "admitted_at", "payload_sha256")
    changed = sum(any(before[record_id][field] != after[record_id][field] for field in fields) for record_id in fixture.initial_record_ids)
    return changed, len(fixture.initial_record_ids)


def metric(numerator: int, denominator: int, value: Any | None = None) -> dict[str, Any]:
    if value is None:
        value = numerator / denominator if denominator else None
    return {"numerator": numerator, "denominator": denominator, "value": value}


def score(control: dict[str, Any], treatment: dict[str, Any], fixture: RuntimeFixture, truth: ScorerGroundTruth) -> tuple[dict[str, Any], dict[str, Any]]:
    c_before = action_map(control["actions_before_correction"])
    t_before = action_map(treatment["actions_before_correction"])
    t_after = action_map(treatment["actions_after_recovery"])
    c_after = action_map(control["actions_after_recovery"])
    t_correction = action_map(treatment["actions_before_explicit_revoke"])
    c_correction = action_map(control["actions_before_explicit_revoke"])
    t_pre_records = record_map(treatment["records_before_correction"])
    t_post_records = record_map(treatment["records_after_recovery"])
    c_pre_records = record_map(control["records_before_correction"])
    c_post_records = record_map(control["records_after_recovery"])

    def common(arm: str, before_actions: dict[str, dict[str, Any]], after_actions: dict[str, dict[str, Any]], before_records: dict[str, dict[str, Any]], after_records: dict[str, dict[str, Any]], correction_actions: dict[str, dict[str, Any]], observation: dict[str, Any]) -> dict[str, Any]:
        root_act = int(before_actions["a-direct-export"]["allowed"])
        propagated = sum(int(before_actions[f"b-{request}"]["allowed"]) for request in ("registered-export", "cross-export", "mixed-export"))
        freeform = int(before_records[R1_FREEFORM]["effective_caps"]["export.send"] == "INFORM" and not before_actions["b-freeform-export"]["allowed"])
        affected = sum(int(after_records[record_id]["state"] == "BLOCKED" and not after_actions[f"c-{record_id}-after-revoke"]["allowed"]) for record_id in R1_AFFECTED)
        correction_records = record_map(observation["records_after_correction"])
        revision = sum(int(after_records[record_id]["state"] == correction_records[record_id]["state"] and after_records[record_id]["effective_caps"] == correction_records[record_id]["effective_caps"]) for record_id in R2_CONTROLS)
        scope = sum(int(not before_actions[f"b-{record_id}-payroll"]["allowed"]) for record_id in R1_AFFECTED)
        rewrite, rewrite_denominator = historical_rewrite_count(observation, fixture)
        post_revoke_false = sum(int(after_actions[f"c-{record_id}-after-revoke"]["allowed"]) for record_id in R1_AFFECTED)
        collateral = 0
        control_actions = {
            R2_ROOT: ("b-r2-root", "c-r2-root-after-revoke"),
            R2_REGISTERED: ("b-r2-registered", "c-r2-registered-after-revoke"),
            CLEAN_EXPORT: ("b-clean-export", "c-clean-export-after-revoke"),
            CLEAN_PAYROLL: ("b-clean-payroll", "c-clean-payroll-after-revoke"),
            R1_POST: ("c-post-correction-root", "c-post-correction-after-revoke"),
        }
        correction_action_map = action_map(observation["actions_before_explicit_revoke"])
        pre_action_map = {**before_actions, **correction_action_map}
        post_action_map = after_actions
        for record_id in SAFE_CONTROLS:
            if record_id not in correction_records or record_id not in after_records:
                collateral += 1
                continue
            before_request, after_request = control_actions[record_id]
            if (
                correction_records[record_id]["state"] != after_records[record_id]["state"]
                or correction_records[record_id]["effective_caps"] != after_records[record_id]["effective_caps"]
                or correction_records[record_id]["published"] != after_records[record_id]["published"]
                or pre_action_map[before_request]["allowed"] != post_action_map[after_request]["allowed"]
            ):
                collateral += 1
        return {
            "misclassified_root_act_permit": metric(root_act, 1),
            "propagated_false_act_permits": metric(propagated, 3),
            "affected_descendant_recall_after_revoke": metric(affected, 5),
            "unaffected_revision_preserved": metric(revision, 2),
            "unaffected_scope_preserved": metric(scope, 5),
            "freeform_cap_contained": metric(freeform, 1),
            "historical_policy_rewrite_count": metric(rewrite, rewrite_denominator, rewrite),
            "post_revoke_false_act_permits": metric(post_revoke_false, 5, post_revoke_false),
            "repair_collateral_count": metric(collateral, 5, collateral),
        }

    # The scorer checks action results against hidden expectations only after both arms ran.
    expected_lookup = {(arm, request_id): expected for arm, request_id, expected in truth.expected_outcome}
    leakage_mismatches = []
    for arm, observation in (("CONTROL", control), ("TREATMENT", treatment)):
        for action in observation["actions_before_correction"] + observation["actions_before_explicit_revoke"] + observation["actions_after_recovery"]:
            key = (arm, action["request_id"])
            if key in expected_lookup and action["allowed"] != expected_lookup[key]:
                leakage_mismatches.append({"arm": arm, "request_id": action["request_id"]})
    control_metrics = common("CONTROL", c_before, c_after, c_pre_records, c_post_records, c_correction, control)
    treatment_metrics = common("TREATMENT", t_before, t_after, t_pre_records, t_post_records, t_correction, treatment)
    return control_metrics, treatment_metrics | {"scorer_expected_outcome_mismatches": leakage_mismatches}


def mechanical_verdict(metrics: Mapping[str, Mapping[str, Any]], control: dict[str, Any], treatment: dict[str, Any]) -> tuple[str, str | None, str | None]:
    # Frozen gate order from PLAN.md.  A root ACT permit is a policy failure,
    # not a design contradiction; it is reported as the first failed property.
    control_records = record_map(control["records_before_correction"])
    treatment_records = record_map(treatment["records_before_correction"])
    treatment_after_correction = record_map(treatment["records_after_correction"])
    treatment_after_recovery = record_map(treatment["records_after_recovery"])
    design_kill_checks = (
        (control_records[R1_ROOT]["effective_caps"]["export.send"] == "ACT", "BASE_RELAY_RECEIVED_ACT"),
        (treatment_records[R1_FREEFORM]["effective_caps"]["export.send"] not in ("NONE", "INFORM"), "FREEFORM_EXCEEDED_INFORM"),
        (metrics["historical_policy_rewrite_count"]["numerator"] != 0, "CORRECTION_REWROTE_ENVELOPE"),
        (any(treatment_after_recovery[record_id]["state"] != treatment_after_correction[record_id]["state"] or treatment_after_recovery[record_id]["effective_caps"] != treatment_after_correction[record_id]["effective_caps"] for record_id in SAFE_CONTROLS), "SELECTOR_BOUNDARY_VIOLATION"),
    )
    for failed, name in design_kill_checks:
        if failed:
            return "DESIGN-KILL", name, name
    first_security_failure = None
    if metrics["misclassified_root_act_permit"]["value"] != 0:
        first_security_failure = "misclassified_root_act_permit"
    contained = (
        metrics["misclassified_root_act_permit"]["value"] == 1
        and metrics["propagated_false_act_permits"]["value"] == 1
        and metrics["freeform_cap_contained"]["value"] == 1
        and metrics["unaffected_scope_preserved"]["value"] == 1
        and metrics["unaffected_revision_preserved"]["value"] == 1
        and metrics["affected_descendant_recall_after_revoke"]["value"] == 1
        and metrics["post_revoke_false_act_permits"]["value"] == 0
        and metrics["historical_policy_rewrite_count"]["value"] == 0
        and metrics["repair_collateral_count"]["value"] == 0
        and treatment["revocation"]["closure"] == list(R1_AFFECTED)
    )
    if metrics["misclassified_root_act_permit"]["value"] == 0:
        return "POLICY-ROBUST", first_security_failure, first_security_failure
    if contained:
        return "POLICY-FAIL-CONTAINED", first_security_failure, first_security_failure
    return "POLICY-FAIL-UNBOUNDED", first_security_failure or "containment_gate", first_security_failure or "containment_gate"


def fixture_digest(fixture: RuntimeFixture) -> str:
    fixed = {
        "records": [
            {"id": record.output_id, "payload": record.payload, "operation": record.operation, "revision": record.revision, "department": record.department, "source": record.source, "admitted_at": record.admitted_at, "direct_parent_ids": list(record.direct_parent_ids), "transform_class": record.transform_class, "policy_key": record.policy_key, "producer": record.producer}
            for record in fixture.records
        ],
        "actions": [plain(action) for action in fixture.actions],
        "window": plain(fixture.window), "correction_time": fixture.correction_time,
    }
    return digest(fixed)


def render_result(result: Mapping[str, Any], result_digest: str) -> str:
    verdict = result["verdict"]
    lines = [
        f"# E2E Policy-Misclassification Result\n\nFinal verdict: **{verdict}**.",
        f"Canonical result digest: `{result_digest}`.",
        "\nThe result is generated from `result.json`; the report does not select the verdict.",
        "\n## Control and treatment",
        "\nControl uses RELAY; treatment changes only vendor_lookup/R1 to ORIGIN.",
        f"\nTreatment direct export result: `{result['treatment_pre_recovery']['actions'][0]['actual_outcome']}`.",
        f"\nTreatment post-recovery false ACT permits: `{result['metrics']['post_revoke_false_act_permits']['numerator']}/{result['metrics']['post_revoke_false_act_permits']['denominator']}`.",
        "\n## Metrics",
    ]
    for name, value in result["metrics"].items():
        if isinstance(value, Mapping) and "numerator" in value:
            lines.append(f"- `{name}`: {value['numerator']}/{value['denominator']} (value `{value['value']}`)")
    lines.extend(
        (
            "\n## Recovery",
            f"\nSelected roots: `{result['revocation']['selected_roots']}`.",
            f"\nAffected closure: `{result['revocation']['closure']}`.",
            f"\nHistorical rewrite count: `{result['policy_correction']['historical_rewrite_count']['numerator']}`.",
            "\n## First failed security property",
            f"\n`{result['first_failed_security_property']}`.",
            "\n## Leakage and limitations",
            f"\nGround-truth leakage check passed: `{result['ground_truth_leakage']['passed']}`.",
            "\nThis is a logical Architecture A experiment, not a production-readiness or memory-poisoning claim.",
            "\n## Next gate",
            "\nOnly an explicitly authorized follow-up research experiment may proceed; no mitigation or production integration is authorized by this result.",
        )
    )
    return "\n".join(lines) + "\n"


def build_result() -> dict[str, Any]:
    control_fixture = runtime_fixture("CONTROL")
    treatment_fixture = runtime_fixture("TREATMENT")
    vault = GroundTruthVault(ground_truth())
    leakage = leakage_guard({"CONTROL": control_fixture, "TREATMENT": treatment_fixture}, vault)
    control = run_arm("CONTROL", control_fixture)
    treatment = run_arm("TREATMENT", treatment_fixture)
    assert vault.reads == 0
    truth = vault.release_for_scoring()
    annotate_expected(control, "CONTROL", truth)
    annotate_expected(treatment, "TREATMENT", truth)
    control_metrics, treatment_metrics = score(control, treatment, treatment_fixture, truth)
    expected_lookup = {(arm, request_id): allowed for arm, request_id, allowed in truth.expected_outcome}
    outcome_mismatches = []
    for arm, observation in (("CONTROL", control), ("TREATMENT", treatment)):
        for field in ("actions_before_correction", "actions_before_explicit_revoke", "actions_after_recovery"):
            for action in observation[field]:
                if action["allowed"] != expected_lookup[(arm, action["request_id"])]:
                    outcome_mismatches.append({"arm": arm, "request_id": action["request_id"]})
    treatment_metrics.pop("scorer_expected_outcome_mismatches", None)
    verdict, first_gate, first_security_failure = mechanical_verdict(treatment_metrics, control, treatment)
    source_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    policy_correction = {
        "historical_rewrite_count": treatment_metrics["historical_policy_rewrite_count"],
        "actions_before_explicit_revoke": {"control": control["actions_before_explicit_revoke"], "treatment": treatment["actions_before_explicit_revoke"]},
    }
    before_caps = record_map(treatment["records_before_correction"])
    after_caps = record_map(treatment["records_after_recovery"])
    same_record_increases = sum(int(any(TIER_RANK[after_caps[record_id]["bound_caps"][scope]] > TIER_RANK[before_caps[record_id]["bound_caps"][scope]] for scope in SCOPES)) for record_id in treatment_fixture.initial_record_ids)
    result = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "design_commit": DESIGN_COMMIT,
        "e2d_commit": E2D_COMMIT,
        "experiment_source_digest": source_digest,
        "fixture_digest": fixture_digest(control_fixture),
        "ground_truth_digest": digest(plain(truth)),
        "control": {"policy": {"initial": control["policy_initial"], "after_correction": control["policy_after_correction"]}, "records": control["records_before_correction"], "records_after_correction": control["records_after_correction"], "records_after_recovery": control["records_after_recovery"], "actions": control["actions_before_correction"] + control["actions_before_explicit_revoke"] + control["actions_after_recovery"], "metrics": control_metrics},
        "treatment_pre_recovery": {"policy": {"initial": treatment["policy_initial"], "after_correction": treatment["policy_after_correction"]}, "records": treatment["records_before_correction"], "authority_traces": treatment["authority_traces"], "actions": treatment["actions_before_correction"], "metrics": {name: treatment_metrics[name] for name in ("misclassified_root_act_permit", "propagated_false_act_permits", "unaffected_scope_preserved", "unaffected_revision_preserved", "freeform_cap_contained")}},
        "policy_correction": policy_correction,
        "revocation": {**treatment["revocation"], "same_record_authority_increases": metric(same_record_increases, len(treatment_fixture.initial_record_ids), same_record_increases)},
        "treatment_post_recovery": {"records": treatment["records_after_recovery"], "actions": treatment["actions_after_recovery"], "metrics": treatment_metrics},
        "metrics": treatment_metrics,
        "ground_truth_leakage": leakage,
        "ground_truth_comparison": {"action_outcome_mismatches": outcome_mismatches, "passed": not outcome_mismatches},
        "determinism": {"run_digest_comparison": "performed externally by two clean invocations"},
        "verdict": verdict,
        "first_failed_gate": first_gate,
        "first_failed_security_property": first_security_failure,
        "limitations": ["Configured operation role remains a trusted policy input.", "SQLite logical state does not prove Firestore/Cloud Run production atomicity."],
    }
    return result


def main() -> int:
    result = build_result()
    encoded = canonical_bytes(result)
    result_digest = hashlib.sha256(encoded).hexdigest()
    (OUT / "result.json").write_bytes(encoded)
    (OUT / "RESULT.md").write_text(render_result(result, result_digest), encoding="utf-8")
    print(f"E2E VERDICT: {result['verdict']}")
    print(f"result.json sha256: {result_digest}")
    print(f"preregistration commit: {PREREGISTRATION_COMMIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
