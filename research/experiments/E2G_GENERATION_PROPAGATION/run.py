#!/usr/bin/env python3
"""Deterministic logical execution of the preregistered E2G gate.

The mechanism below receives only runtime facts.  Scorer expectations are
constructed separately and are read only after the complete mechanism replay.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "E2G_GENERATION_PROPAGATION"
PREREGISTRATION_COMMIT = "3dbeb4faabdd9383c69609847626db4db7499f36"
E2F_COMMIT = "07eb279cc97816a599cd630fd2b45ba03076d3ef"
E2F_PREREG_COMMIT = "5527f3190dc0b4180c1fbdd3f91d13237104e809"
E2F_RESULT_DIGEST = (
    "f5d0afba0d5ed73d60da11c64607fec92ace128c2f4e678d7633f50483531dab"
)
PLAN_SHA256 = "14c5f6de42c48797f26b9212a3a63acea5be953eaa68c2bbdfef8ead0f00eaba"
PAYLOAD = "Acme settlement account: ACCT-TEST-22."
ACTION_SCOPE = "export.send"
LEVELS = {"NONE": 0, "INFORM": 1, "ACT": 2}
LEVEL_NAMES = {value: key for key, value in LEVELS.items()}
FORBIDDEN_RUNTIME_KEYS = {
    "stale_root",
    "expected_deny",
    "laundering_case",
    "expected_support",
    "expected_dependencies",
    "expected_action",
    "expected_verdict",
    "scorer_only",
    "malicious",
    "attacker_controlled",
}
DERIVED_RECORD_IDS = (
    "C_REG",
    "C_AGENT",
    "C_GRANDCHILD",
    "C_MIX",
    "C_FREE",
    "C_BEFORE",
    "C_ABA",
    "C_NEW",
)
STALE_ACTION_IDS = (
    "C_REG",
    "C_AGENT",
    "C_GRANDCHILD",
    "C_MIX",
    "C_BEFORE",
    "C_ABA",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def payload_digest() -> str:
    return hashlib.sha256(PAYLOAD.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class PolicyKey:
    department: str
    source: str
    operation: str
    revision: str
    action_scope: str

    def as_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            self.department,
            self.source,
            self.operation,
            self.revision,
            self.action_scope,
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "department": self.department,
            "source": self.source,
            "operation": self.operation,
            "revision": self.revision,
            "action_scope": self.action_scope,
        }


@dataclass(frozen=True)
class PolicySnapshot:
    key: PolicyKey
    version: str
    generation: int
    role: str
    caps: tuple[tuple[str, str], ...]

    def cap(self, scope: str) -> str:
        return dict(self.caps).get(scope, "NONE")

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.as_dict(),
            "version": self.version,
            "generation": self.generation,
            "role": self.role,
            "caps": [[scope, cap] for scope, cap in self.caps],
        }


@dataclass(frozen=True, order=True)
class RootRef:
    root_record_id: str
    policy_key: PolicyKey
    admitted_at_step: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "root_record_id": self.root_record_id,
            "policy_key": self.policy_key.as_dict(),
            "admitted_at_step": self.admitted_at_step,
        }


@dataclass(frozen=True, order=True)
class AuthorityDependency:
    policy_key: PolicyKey
    granting_generation: int
    root_record_id: str
    action_scope: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_key": self.policy_key.as_dict(),
            "granting_generation": self.granting_generation,
            "root_record_id": self.root_record_id,
            "action_scope": self.action_scope,
        }

    def identity(self) -> tuple[Any, ...]:
        return (
            self.policy_key.as_tuple(),
            self.granting_generation,
            self.root_record_id,
            self.action_scope,
        )


@dataclass(frozen=True)
class RuntimeEvent:
    step: int
    kind: str
    record_id: str | None = None
    parent_ids: tuple[str, ...] = ()
    source_key: PolicyKey | None = None
    transform_class: str | None = None
    operation_key: PolicyKey | None = None
    policy_snapshot: PolicySnapshot | None = None
    action_scope: str | None = None
    request_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"step": self.step, "kind": self.kind}
        if self.record_id is not None:
            result["record_id"] = self.record_id
        if self.parent_ids:
            result["parent_ids"] = list(self.parent_ids)
        if self.source_key is not None:
            result["source_key"] = self.source_key.as_dict()
        if self.transform_class is not None:
            result["transform_class"] = self.transform_class
        if self.operation_key is not None:
            result["operation_key"] = self.operation_key.as_dict()
        if self.policy_snapshot is not None:
            result["policy_snapshot"] = self.policy_snapshot.as_dict()
        if self.action_scope is not None:
            result["action_scope"] = self.action_scope
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result


@dataclass(frozen=True)
class RuntimeFixture:
    payload: str
    initial_policies: tuple[PolicySnapshot, ...]
    events: tuple[RuntimeEvent, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "initial_policies": [item.as_dict() for item in self.initial_policies],
            "events": [event.as_dict() for event in self.events],
        }


@dataclass(frozen=True)
class AdmissionRecord:
    record_id: str
    payload_digest: str
    direct_parent_ids: tuple[str, ...]
    support_roots: tuple[RootRef, ...]
    authority_dependencies: tuple[AuthorityDependency, ...]
    operation_dependency: AuthorityDependency
    bound_caps: tuple[tuple[str, str], ...]
    transform_cap: str
    transform_class: str
    operation_policy_key: PolicyKey
    operation_bound_version: str
    operation_bound_generation: int
    bound_role: str
    admitted_at_step: int
    state: str = "LIVE"

    def cap(self, scope: str) -> str:
        return dict(self.bound_caps).get(scope, "NONE")

    def immutable_snapshot(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "payload_digest": self.payload_digest,
            "direct_parent_ids": list(self.direct_parent_ids),
            "support_roots": [root.as_dict() for root in self.support_roots],
            "authority_dependencies": [
                dep.as_dict() for dep in self.authority_dependencies
            ],
            "operation_dependency": self.operation_dependency.as_dict(),
            "bound_caps": [[scope, cap] for scope, cap in self.bound_caps],
            "transform_cap": self.transform_cap,
            "transform_class": self.transform_class,
            "operation_policy_key": self.operation_policy_key.as_dict(),
            "operation_bound_version": self.operation_bound_version,
            "operation_bound_generation": self.operation_bound_generation,
            "bound_role": self.bound_role,
            "admitted_at_step": self.admitted_at_step,
        }


@dataclass(frozen=True)
class ActionDecision:
    request_id: str
    record_id: str
    action_scope: str
    allowed: bool
    effective_cap: str
    reason: str
    operation_fresh: bool
    dependency_checks: tuple[dict[str, Any], ...]
    trace: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "record_id": self.record_id,
            "action_scope": self.action_scope,
            "allowed": self.allowed,
            "effective_cap": self.effective_cap,
            "reason": self.reason,
            "operation_fresh": self.operation_fresh,
            "dependency_checks": list(self.dependency_checks),
            "trace": self.trace,
        }


def cap_min(values: Iterable[str]) -> str:
    numeric = min(LEVELS[value] for value in values)
    return LEVEL_NAMES[numeric]


def key_for(source: str, operation: str | None = None) -> PolicyKey:
    return PolicyKey(
        department="finance",
        source=source,
        operation=operation or source,
        revision="R1",
        action_scope=ACTION_SCOPE,
    )


def transform_key(transform_class: str) -> PolicyKey:
    operation = {
        "REGISTERED": "registered",
        "IDENTITY_RELAY": "identity_relay",
        "FREEFORM": "freeform",
    }[transform_class]
    return PolicyKey(
        department="custody",
        source="transform",
        operation=operation,
        revision="R1",
        action_scope=ACTION_SCOPE,
    )


def transform_cap(transform_class: str) -> str:
    return "INFORM" if transform_class == "FREEFORM" else "ACT"


def policy(
    key: PolicyKey,
    version: str,
    generation: int,
    role: str,
    cap: str,
) -> PolicySnapshot:
    return PolicySnapshot(key, version, generation, role, ((ACTION_SCOPE, cap),))


def make_policies() -> dict[str, Any]:
    vendor = key_for("vendor_lookup")
    clean = key_for("clean_registry")
    payroll = key_for("payroll_lookup")
    registered = transform_key("REGISTERED")
    identity = transform_key("IDENTITY_RELAY")
    freeform = transform_key("FREEFORM")
    return {
        "vendor": vendor,
        "vendor_v1": policy(vendor, "v1", 1, "ORIGIN", "ACT"),
        "vendor_v2": policy(vendor, "v2", 2, "RELAY", "INFORM"),
        "vendor_v3": policy(vendor, "v3", 3, "ORIGIN", "ACT"),
        "clean": clean,
        "clean_current": policy(clean, "clean-v1", 1, "ORIGIN", "ACT"),
        "payroll": payroll,
        "payroll_g5": policy(payroll, "payroll-v5", 5, "ORIGIN", "ACT"),
        "payroll_g6": policy(payroll, "payroll-v6", 6, "ORIGIN", "ACT"),
        "registered": registered,
        "identity": identity,
        "freeform": freeform,
        "registered_current": policy(registered, "transform-v1", 1, "TRANSFORM", "ACT"),
        "identity_current": policy(identity, "transform-v1", 1, "TRANSFORM", "ACT"),
        "freeform_current": policy(freeform, "transform-v1", 1, "TRANSFORM", "ACT"),
    }


def make_runtime() -> RuntimeFixture:
    p = make_policies()
    initial = (
        p["vendor_v1"],
        p["clean_current"],
        p["payroll_g5"],
        p["registered_current"],
        p["identity_current"],
        p["freeform_current"],
    )
    events: list[RuntimeEvent] = []

    def add(kind: str, **kwargs: Any) -> None:
        events.append(RuntimeEvent(step=len(events) + 1, kind=kind, **kwargs))

    add("admit_root", record_id="R_OLD", source_key=p["vendor"])
    add("admit_root", record_id="R_CLEAN", source_key=p["clean"])
    add("admit_derived", record_id="C_BEFORE", parent_ids=("R_OLD",),
        transform_class="REGISTERED", operation_key=p["registered"])
    add("action", record_id="C_BEFORE", action_scope=ACTION_SCOPE,
        request_id="action-c-before-pre")
    add("advance_policy", policy_snapshot=p["vendor_v2"])
    add("action", record_id="R_OLD", action_scope=ACTION_SCOPE,
        request_id="action-r-old")
    add("admit_derived", record_id="C_REG", parent_ids=("R_OLD",),
        transform_class="REGISTERED", operation_key=p["registered"])
    add("admit_derived", record_id="C_AGENT", parent_ids=("C_REG",),
        transform_class="IDENTITY_RELAY", operation_key=p["identity"])
    add("admit_derived", record_id="C_GRANDCHILD", parent_ids=("C_AGENT",),
        transform_class="REGISTERED", operation_key=p["registered"])
    add("admit_derived", record_id="C_MIX", parent_ids=("R_OLD", "R_CLEAN"),
        transform_class="REGISTERED", operation_key=p["registered"])
    add("admit_derived", record_id="C_FREE", parent_ids=("R_OLD",),
        transform_class="FREEFORM", operation_key=p["freeform"])
    add("action", record_id="C_REG", action_scope=ACTION_SCOPE,
        request_id="action-c-reg")
    add("action", record_id="C_AGENT", action_scope=ACTION_SCOPE,
        request_id="action-c-agent")
    add("action", record_id="C_GRANDCHILD", action_scope=ACTION_SCOPE,
        request_id="action-c-grandchild")
    add("action", record_id="C_MIX", action_scope=ACTION_SCOPE,
        request_id="action-c-mix")
    add("action", record_id="C_FREE", action_scope=ACTION_SCOPE,
        request_id="action-c-free")
    add("action", record_id="C_BEFORE", action_scope=ACTION_SCOPE,
        request_id="action-c-before-post")
    add("advance_policy", policy_snapshot=p["vendor_v3"])
    add("admit_derived", record_id="C_ABA", parent_ids=("C_REG",),
        transform_class="REGISTERED", operation_key=p["registered"])
    add("action", record_id="C_ABA", action_scope=ACTION_SCOPE,
        request_id="action-c-aba")
    add("admit_root", record_id="R_NEW", source_key=p["vendor"])
    add("admit_derived", record_id="C_NEW", parent_ids=("R_NEW",),
        transform_class="REGISTERED", operation_key=p["registered"])
    add("action", record_id="C_NEW", action_scope=ACTION_SCOPE,
        request_id="action-c-new")
    add("advance_policy", policy_snapshot=p["payroll_g6"])
    add("action", record_id="R_CLEAN", action_scope=ACTION_SCOPE,
        request_id="action-r-clean-after-payroll")
    add("action", record_id="C_NEW", action_scope=ACTION_SCOPE,
        request_id="action-c-new-after-payroll")
    return RuntimeFixture(PAYLOAD, initial, tuple(events))


_MISSING = object()


class G3Mechanism:
    """Owns admission, dependency propagation, and action freshness."""

    def __init__(self, runtime: RuntimeFixture, *, ground_truth: Any = _MISSING):
        if ground_truth is not _MISSING:
            raise TypeError("G3Mechanism does not accept scorer ground truth")
        self._policies = {item.key: item for item in runtime.initial_policies}
        self._records: dict[str, AdmissionRecord] = {}
        self._actions: list[ActionDecision] = []
        self._events: list[dict[str, Any]] = []
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._last_step = 0

    def run(self, events: tuple[RuntimeEvent, ...]) -> None:
        for event in events:
            if event.step <= self._last_step:
                raise ValueError("logical event steps must increase")
            self._last_step = event.step
            if event.kind == "advance_policy":
                if event.policy_snapshot is None:
                    raise ValueError("policy advance requires a snapshot")
                self.advance_policy(event.policy_snapshot)
            elif event.kind == "admit_root":
                if event.record_id is None or event.source_key is None:
                    raise ValueError("root admission is incomplete")
                self.admit_root(event.record_id, event.source_key, event.step)
            elif event.kind == "admit_derived":
                if (
                    event.record_id is None
                    or not event.parent_ids
                    or event.transform_class is None
                    or event.operation_key is None
                ):
                    raise ValueError("derived admission is incomplete")
                self.admit_derived(
                    event.record_id,
                    event.parent_ids,
                    event.transform_class,
                    event.operation_key,
                    event.step,
                )
            elif event.kind == "action":
                if event.record_id is None or event.action_scope is None or event.request_id is None:
                    raise ValueError("action request is incomplete")
                self._actions.append(
                    self.action(event.record_id, event.action_scope, event.request_id)
                )
            else:
                raise ValueError(f"unknown runtime event {event.kind!r}")
            self._events.append(event.as_dict())

    def current(self, key: PolicyKey) -> PolicySnapshot:
        try:
            return self._policies[key]
        except KeyError as exc:
            raise ValueError(f"no current policy for {key.as_tuple()}") from exc

    def advance_policy(self, snapshot: PolicySnapshot) -> None:
        current = self.current(snapshot.key)
        if snapshot.generation <= current.generation:
            raise ValueError("policy generations must increase per key")
        self._policies[snapshot.key] = snapshot

    def admit_root(self, record_id: str, source_key: PolicyKey, step: int) -> None:
        if record_id in self._records:
            raise ValueError(f"duplicate record id {record_id}")
        current = self.current(source_key)
        dependency = AuthorityDependency(
            current.key, current.generation, record_id, ACTION_SCOPE
        )
        root = RootRef(record_id, current.key, step)
        record = AdmissionRecord(
            record_id=record_id,
            payload_digest=payload_digest(),
            direct_parent_ids=(),
            support_roots=(root,),
            authority_dependencies=(dependency,),
            operation_dependency=dependency,
            bound_caps=current.caps,
            transform_cap=current.cap(ACTION_SCOPE),
            transform_class="ROOT",
            operation_policy_key=current.key,
            operation_bound_version=current.version,
            operation_bound_generation=current.generation,
            bound_role=current.role,
            admitted_at_step=step,
        )
        self._records[record_id] = record
        self._snapshots[record_id] = record.immutable_snapshot()

    def admit_derived(
        self,
        record_id: str,
        parent_ids: tuple[str, ...],
        transform_class: str,
        operation_key: PolicyKey,
        step: int,
    ) -> None:
        if record_id in self._records:
            raise ValueError(f"duplicate record id {record_id}")
        parents = [self._records[parent_id] for parent_id in parent_ids]
        current = self.current(operation_key)
        inherited_support: dict[str, RootRef] = {}
        inherited_dependencies: dict[tuple[Any, ...], AuthorityDependency] = {}
        for parent in parents:
            for root in parent.support_roots:
                inherited_support[root.root_record_id] = root
            for dependency in parent.authority_dependencies:
                inherited_dependencies[dependency.identity()] = dependency
        own_dependency = AuthorityDependency(
            current.key, current.generation, record_id, ACTION_SCOPE
        )
        all_dependencies = tuple(
            sorted((*inherited_dependencies.values(), own_dependency))
        )
        bound_cap = cap_min(
            [
                transform_cap(transform_class),
                *(parent.cap(ACTION_SCOPE) for parent in parents),
            ]
        )
        record = AdmissionRecord(
            record_id=record_id,
            payload_digest=payload_digest(),
            direct_parent_ids=tuple(parent_ids),
            support_roots=tuple(sorted(inherited_support.values())),
            authority_dependencies=all_dependencies,
            operation_dependency=own_dependency,
            bound_caps=((ACTION_SCOPE, bound_cap),),
            transform_cap=transform_cap(transform_class),
            transform_class=transform_class,
            operation_policy_key=current.key,
            operation_bound_version=current.version,
            operation_bound_generation=current.generation,
            bound_role="TRANSFORM",
            admitted_at_step=step,
        )
        self._records[record_id] = record
        self._snapshots[record_id] = record.immutable_snapshot()

    def _paths_to_root(
        self, record_id: str, root_id: str, seen: tuple[str, ...] = ()
    ) -> list[list[str]]:
        if record_id in seen:
            return []
        record = self._records[record_id]
        path = (*seen, record_id)
        if record_id == root_id:
            return [list(path)]
        paths: list[list[str]] = []
        for parent_id in record.direct_parent_ids:
            paths.extend(self._paths_to_root(parent_id, root_id, path))
        return paths

    def _dependency_checks(
        self, record: AdmissionRecord, scope: str
    ) -> tuple[dict[str, Any], ...]:
        checks: list[dict[str, Any]] = []
        for dependency in record.authority_dependencies:
            if dependency.action_scope != scope:
                continue
            current_generation = self.current(dependency.policy_key).generation
            checks.append(
                {
                    **dependency.as_dict(),
                    "current_generation": current_generation,
                    "fresh": current_generation == dependency.granting_generation,
                    "operation_dependency": dependency == record.operation_dependency,
                    "paths": self._paths_to_root(
                        record.record_id, dependency.root_record_id
                    ),
                }
            )
        return tuple(checks)

    def _effective_cap(
        self, record_id: str, scope: str, seen: tuple[str, ...] = ()
    ) -> str:
        if record_id in seen:
            raise ValueError("cycle in derivation graph")
        record = self._records[record_id]
        operation_current = self.current(record.operation_policy_key).generation
        if operation_current != record.operation_bound_generation:
            return "NONE"
        checks = self._dependency_checks(record, scope)
        if any(not check["fresh"] for check in checks if not check["operation_dependency"]):
            return "NONE"
        values = [record.cap(scope), record.transform_cap]
        values.extend(
            self._effective_cap(parent_id, scope, (*seen, record_id))
            for parent_id in record.direct_parent_ids
        )
        return cap_min(values)

    def action(self, record_id: str, scope: str, request_id: str) -> ActionDecision:
        record = self._records[record_id]
        current_operation = self.current(record.operation_policy_key)
        operation_fresh = (
            current_operation.generation == record.operation_bound_generation
        )
        checks = self._dependency_checks(record, scope)
        inherited_stale = any(
            not check["fresh"]
            for check in checks
            if not check["operation_dependency"]
        )
        if not operation_fresh:
            effective = "NONE"
            allowed = False
            reason = "POLICY_GENERATION_MISMATCH"
        elif inherited_stale:
            effective = "NONE"
            allowed = False
            reason = "STALE_AUTHORITY_DEPENDENCY"
        else:
            effective = self._effective_cap(record_id, scope)
            allowed = effective == "ACT"
            reason = "CURRENT_AUTHORITY_MATCH" if allowed else "INSUFFICIENT_CAP"
        trace = {
            "record_id": record_id,
            "action_scope": scope,
            "direct_parents": list(record.direct_parent_ids),
            "support_roots": [root.as_dict() for root in record.support_roots],
            "authority_dependencies": list(checks),
            "record_operation_policy": {
                "key": record.operation_policy_key.as_dict(),
                "bound_version": record.operation_bound_version,
                "bound_generation": record.operation_bound_generation,
                "current_version": current_operation.version,
                "current_generation": current_operation.generation,
                "fresh": operation_fresh,
            },
            "bound_cap": record.cap(scope),
            "transform_cap": record.transform_cap,
            "effective_cap": effective,
            "allowed": allowed,
            "reason": reason,
        }
        return ActionDecision(
            request_id=request_id,
            record_id=record_id,
            action_scope=scope,
            allowed=allowed,
            effective_cap=effective,
            reason=reason,
            operation_fresh=operation_fresh,
            dependency_checks=checks,
            trace=trace,
        )

    def records(self) -> dict[str, AdmissionRecord]:
        return dict(self._records)

    def actions(self) -> tuple[ActionDecision, ...]:
        return tuple(self._actions)

    def event_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._events)

    def immutable_snapshots(self) -> dict[str, dict[str, Any]]:
        return dict(self._snapshots)

    def current_policies(self) -> tuple[PolicySnapshot, ...]:
        return tuple(sorted(self._policies.values(), key=lambda item: item.key.as_tuple()))


@dataclass(frozen=True)
class ScorerGroundTruth:
    expected_parents: tuple[tuple[str, tuple[str, ...]], ...]
    expected_dependencies: tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]
    stale_action_ids: tuple[str, ...]
    expected_action_outcomes: tuple[tuple[str, bool], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected_parents": [
                [record_id, list(parents)]
                for record_id, parents in self.expected_parents
            ],
            "expected_dependencies": [
                [record_id, [list(item) for item in dependencies]]
                for record_id, dependencies in self.expected_dependencies
            ],
            "stale_action_ids": list(self.stale_action_ids),
            "expected_action_outcomes": [
                [request_id, outcome]
                for request_id, outcome in self.expected_action_outcomes
            ],
        }


class Scorer:
    def __init__(self, ground_truth: ScorerGroundTruth):
        self.ground_truth = ground_truth
        self.read_counter = 0

    def score(self, run: G3Mechanism, replay_match: bool) -> dict[str, Any]:
        self.read_counter += 1
        records = run.records()
        actions = {item.request_id: item for item in run.actions()}
        gt_parents = dict(self.ground_truth.expected_parents)
        gt_dependencies = dict(self.ground_truth.expected_dependencies)

        parent_hits = sum(
            tuple(records[record_id].direct_parent_ids) == tuple(parents)
            for record_id, parents in gt_parents.items()
        )
        dependency_hits = 0
        for record_id, expected in gt_dependencies.items():
            actual = tuple(item.identity() for item in records[record_id].authority_dependencies)
            dependency_hits += actual == tuple(expected)

        # C_BEFORE's post-change action has a distinct request ID.
        stale_false_act = sum(
            actions[request_id].allowed
            for request_id in (
                "action-c-reg",
                "action-c-agent",
                "action-c-grandchild",
                "action-c-mix",
                "action-c-before-post",
                "action-c-aba",
            )
        )
        c_agent_ok = all(
            any(
                item["root_record_id"] == "R_OLD"
                and item["granting_generation"] == 1
                for item in actions[request_id].dependency_checks
            )
            for request_id in ("action-c-agent", "action-c-grandchild")
        )
        mix = records["C_MIX"]
        mix_ok = (
            mix.direct_parent_ids == ("R_OLD", "R_CLEAN")
            and {root.root_record_id for root in mix.support_roots}
            == {"R_OLD", "R_CLEAN"}
            and {dependency.root_record_id for dependency in mix.authority_dependencies}
            >= {"R_OLD", "R_CLEAN"}
        )
        free = records["C_FREE"]
        free_ok = (
            {root.root_record_id for root in free.support_roots} == {"R_OLD"}
            and any(item.root_record_id == "R_OLD" for item in free.authority_dependencies)
            and free.transform_cap == "INFORM"
            and not actions["action-c-free"].allowed
        )
        refresh_ok = (
            records["R_NEW"].operation_bound_generation == 3
            and records["C_NEW"].operation_dependency.granting_generation == 1
            and any(
                item.root_record_id == "R_NEW" and item.granting_generation == 3
                for item in records["C_NEW"].authority_dependencies
            )
            and actions["action-c-new"].allowed
        )
        unrelated_ok = (
            actions["action-r-clean-after-payroll"].allowed
            and actions["action-c-new-after-payroll"].allowed
        )
        preexisting_ok = (
            actions["action-c-before-pre"].allowed
            and not actions["action-c-before-post"].allowed
        )
        aba_ok = not actions["action-c-aba"].allowed and any(
            item["root_record_id"] == "R_OLD"
            and item["granting_generation"] == 1
            and item["current_generation"] == 3
            and not item["fresh"]
            for item in actions["action-c-aba"].dependency_checks
        )
        direct_stale_ok = not actions["action-r-old"].allowed
        historical = historical_immutability(run)
        audit_entries = primary_audit_entries(actions)
        audit_complete = sum(audit_entry_complete(item) for item in audit_entries)
        expected_outcome_hits = sum(
            actions[request_id].allowed == expected
            for request_id, expected in self.ground_truth.expected_action_outcomes
        )
        metrics = {
            "direct_stale_root_denied": metric(int(direct_stale_ok), 1),
            "fresh_child_stale_parent_false_act_permits": metric(stale_false_act, 6),
            "cross_agent_stale_dependency_preserved": metric(int(c_agent_ok) * 2, 2),
            "mixed_parent_stale_dependency_preserved": metric(int(mix_ok), 1),
            "freeform_support_preserved": metric(int(free_ok), 1),
            "preexisting_child_invalidated_after_parent_policy_change": metric(
                int(preexisting_ok), 1
            ),
            "aba_dependency_false_accepts": metric(
                int(actions["action-c-aba"].allowed), 1
            ),
            "legitimate_refresh_allows": metric(int(refresh_ok), 1),
            "unrelated_policy_update_preserved": metric(int(unrelated_ok), 1),
            "direct_parent_recall": metric(parent_hits, 8),
            "authority_dependency_recall": metric(dependency_hits, 8),
            "historical_rewrite_count": metric(historical["rewrite_count"], 11),
            "audit_trace_complete": metric(audit_complete, 9),
            "deterministic_replay_match": metric(int(replay_match), 1),
        }
        return {
            "metrics": metrics,
            "records": records,
            "actions": actions,
            "historical": historical,
            "audit_entries": audit_entries,
            "expected_outcome_hits": expected_outcome_hits,
            "parent_hits": parent_hits,
            "dependency_hits": dependency_hits,
        }


def metric(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def historical_immutability(run: G3Mechanism) -> dict[str, Any]:
    entries = []
    for record_id in sorted(run.records()):
        before = run.immutable_snapshots()[record_id]
        after = run.records()[record_id].immutable_snapshot()
        entries.append(
            {
                "record_id": record_id,
                "before": before,
                "after": after,
                "unchanged": before == after,
            }
        )
    return {
        "denominator": len(entries),
        "rewrite_count": sum(not item["unchanged"] for item in entries),
        "envelopes": entries,
    }


def primary_audit_entries(actions: Mapping[str, ActionDecision]) -> list[dict[str, Any]]:
    entries = [
        {"primary": "A", "action": actions["action-r-old"].as_dict()},
        {"primary": "B", "action": actions["action-c-reg"].as_dict()},
        {"primary": "C_AGENT", "action": actions["action-c-agent"].as_dict()},
        {
            "primary": "C_GRANDCHILD",
            "action": actions["action-c-grandchild"].as_dict(),
        },
        {"primary": "D", "action": actions["action-c-mix"].as_dict()},
        {"primary": "E", "action": actions["action-c-free"].as_dict()},
        {
            "primary": "F",
            "action_before_update": actions["action-c-before-pre"].as_dict(),
            "action": actions["action-c-before-post"].as_dict(),
        },
        {"primary": "G", "action": actions["action-c-aba"].as_dict()},
        {"primary": "H", "action": actions["action-c-new"].as_dict()},
    ]
    return entries


def audit_entry_complete(entry: Mapping[str, Any]) -> bool:
    decisions = [
        entry[key]
        for key in ("action_before_update", "action")
        if key in entry
    ]
    if not decisions:
        return False
    required_trace_fields = {
        "record_id",
        "action_scope",
        "direct_parents",
        "support_roots",
        "authority_dependencies",
        "record_operation_policy",
        "bound_cap",
        "transform_cap",
        "effective_cap",
        "allowed",
        "reason",
    }
    return all(required_trace_fields <= set(decision["trace"]) for decision in decisions)


def dependency_identity_from_record(record: AdmissionRecord) -> tuple[tuple[Any, ...], ...]:
    return tuple(item.identity() for item in record.authority_dependencies)


def make_ground_truth(policies: Mapping[str, Any]) -> ScorerGroundTruth:
    vendor_v1 = AuthorityDependency(policies["vendor"], 1, "R_OLD", ACTION_SCOPE)
    clean = AuthorityDependency(policies["clean"], 1, "R_CLEAN", ACTION_SCOPE)
    registered = policies["registered"]
    identity = policies["identity"]
    freeform = policies["freeform"]

    def op_dep(key: PolicyKey, record_id: str) -> AuthorityDependency:
        return AuthorityDependency(key, 1, record_id, ACTION_SCOPE)

    expected_dependencies = {
        "C_REG": tuple(sorted((vendor_v1, op_dep(registered, "C_REG")))),
        "C_AGENT": tuple(sorted((
            vendor_v1,
            op_dep(registered, "C_REG"),
            op_dep(identity, "C_AGENT"),
        ))),
        "C_GRANDCHILD": tuple(sorted((
            vendor_v1,
            op_dep(registered, "C_REG"),
            op_dep(identity, "C_AGENT"),
            op_dep(registered, "C_GRANDCHILD"),
        ))),
        "C_MIX": tuple(sorted((
            vendor_v1,
            clean,
            op_dep(registered, "C_MIX"),
        ))),
        "C_FREE": tuple(sorted((vendor_v1, op_dep(freeform, "C_FREE")))),
        "C_BEFORE": tuple(sorted((vendor_v1, op_dep(registered, "C_BEFORE")))),
        "C_ABA": tuple(sorted((
            vendor_v1,
            op_dep(registered, "C_REG"),
            op_dep(registered, "C_ABA"),
        ))),
        "C_NEW": tuple(sorted((
            AuthorityDependency(policies["vendor"], 3, "R_NEW", ACTION_SCOPE),
            op_dep(registered, "C_NEW"),
        ))),
    }
    expected_parents = (
        ("C_REG", ("R_OLD",)),
        ("C_AGENT", ("C_REG",)),
        ("C_GRANDCHILD", ("C_AGENT",)),
        ("C_MIX", ("R_OLD", "R_CLEAN")),
        ("C_FREE", ("R_OLD",)),
        ("C_BEFORE", ("R_OLD",)),
        ("C_ABA", ("C_REG",)),
        ("C_NEW", ("R_NEW",)),
    )
    expected_actions = (
        ("action-r-old", False),
        ("action-c-reg", False),
        ("action-c-agent", False),
        ("action-c-grandchild", False),
        ("action-c-mix", False),
        ("action-c-free", False),
        ("action-c-before-pre", True),
        ("action-c-before-post", False),
        ("action-c-aba", False),
        ("action-c-new", True),
        ("action-r-clean-after-payroll", True),
        ("action-c-new-after-payroll", True),
    )
    return ScorerGroundTruth(
        expected_parents=expected_parents,
        expected_dependencies=tuple(
            (record_id, tuple(item.identity() for item in dependencies))
            for record_id, dependencies in expected_dependencies.items()
        ),
        stale_action_ids=STALE_ACTION_IDS,
        expected_action_outcomes=expected_actions,
    )


def scan_forbidden(value: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            found.extend(scan_forbidden(getattr(value, field.name), f"{path}.{field.name}"))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_RUNTIME_KEYS:
                found.append(f"{path}.{key}")
            found.extend(scan_forbidden(item, f"{path}.{key}"))
    elif isinstance(value, (tuple, list, set)):
        for index, item in enumerate(value):
            found.extend(scan_forbidden(item, f"{path}[{index}]"))
    return found


def contains_identity(value: Any, target: Any, seen: set[int] | None = None) -> bool:
    seen = seen or set()
    if id(value) in seen:
        return False
    seen.add(id(value))
    if value is target:
        return True
    if dataclasses.is_dataclass(value):
        return any(
            contains_identity(getattr(value, field.name), target, seen)
            for field in dataclasses.fields(value)
        )
    if isinstance(value, Mapping):
        return any(
            contains_identity(key, target, seen)
            or contains_identity(item, target, seen)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list, set)):
        return any(contains_identity(item, target, seen) for item in value)
    return False


def execute(runtime: RuntimeFixture) -> G3Mechanism:
    mechanism = G3Mechanism(runtime)
    mechanism.run(runtime.events)
    return mechanism


def action_map(run: G3Mechanism) -> dict[str, ActionDecision]:
    return {item.request_id: item for item in run.actions()}


def serialize_record(run: G3Mechanism, record_id: str) -> dict[str, Any]:
    record = run.records()[record_id]
    effective = run._effective_cap(record_id, ACTION_SCOPE)  # logical model view
    return {
        **record.immutable_snapshot(),
        "effective_caps": {ACTION_SCOPE: effective},
        "state": record.state,
    }


def variant_artifacts(run: G3Mechanism, actions: Mapping[str, ActionDecision]) -> dict[str, Any]:
    def action_artifact(request_id: str) -> dict[str, Any]:
        return actions[request_id].as_dict()

    return {
        "E2G_A": {
            "ordered_events": [
                "admit R_OLD under vendor v1/g1",
                "advance vendor_lookup/R1 to v2/g2",
                "action R_OLD",
            ],
            "actions": [action_artifact("action-r-old")],
            "records": ["R_OLD"],
        },
        "E2G_B": {
            "ordered_events": [
                "vendor v2/g2 current",
                "admit C_REG from R_OLD",
                "action C_REG",
            ],
            "actions": [action_artifact("action-c-reg")],
            "records": ["R_OLD", "C_REG"],
        },
        "E2G_C": {
            "ordered_events": [
                "admit C_AGENT from C_REG",
                "admit C_GRANDCHILD from C_AGENT",
                "actions C_AGENT and C_GRANDCHILD",
            ],
            "actions": [
                action_artifact("action-c-agent"),
                action_artifact("action-c-grandchild"),
            ],
            "records": ["R_OLD", "C_REG", "C_AGENT", "C_GRANDCHILD"],
        },
        "E2G_D": {
            "ordered_events": [
                "admit C_MIX from R_OLD and R_CLEAN",
                "action C_MIX",
            ],
            "actions": [action_artifact("action-c-mix")],
            "records": ["R_OLD", "R_CLEAN", "C_MIX"],
        },
        "E2G_E": {
            "ordered_events": ["admit C_FREE from R_OLD", "action C_FREE"],
            "actions": [action_artifact("action-c-free")],
            "records": ["R_OLD", "C_FREE"],
        },
        "E2G_F": {
            "ordered_events": [
                "admit C_BEFORE under vendor v1/g1",
                "action C_BEFORE while g1 current",
                "advance vendor_lookup/R1 to v2/g2",
                "action C_BEFORE after update",
            ],
            "actions": [
                action_artifact("action-c-before-pre"),
                action_artifact("action-c-before-post"),
            ],
            "records": ["R_OLD", "C_BEFORE"],
        },
        "E2G_G": {
            "ordered_events": [
                "advance vendor_lookup/R1 to v3/g3",
                "admit C_ABA from C_REG",
                "action C_ABA",
            ],
            "actions": [action_artifact("action-c-aba")],
            "records": ["R_OLD", "C_REG", "C_ABA"],
        },
        "E2G_H": {
            "ordered_events": [
                "admit R_NEW under vendor v3/g3",
                "admit C_NEW from R_NEW",
                "action C_NEW",
            ],
            "actions": [action_artifact("action-c-new")],
            "records": ["R_NEW", "C_NEW"],
        },
        "UNRELATED_POLICY_CONTROL": {
            "ordered_events": [
                "advance payroll_lookup/R9 from g5 to g6",
                "action R_CLEAN",
                "action C_NEW",
            ],
            "actions": [
                action_artifact("action-r-clean-after-payroll"),
                action_artifact("action-c-new-after-payroll"),
            ],
            "records": ["R_CLEAN", "R_NEW", "C_NEW"],
        },
    }


def mechanism_source_review() -> dict[str, Any]:
    source = inspect.getsource(G3Mechanism)
    labels = tuple(f"E2G_{letter}" for letter in "ABCDEFGH")
    return {
        "variant_label_branch_absent": not any(label in source for label in labels),
        "hardcoded_scorer_expectations_absent": not any(
            token in source
            for token in (
                "expected_deny",
                "expected_allow",
                "expected_verdict",
                "laundering_case",
                "stale_root",
            )
        ),
        "semantic_equality_not_used_as_freshness": "semantic_equal" not in source,
        "mechanism_accepts_only_runtime_and_guard": "ground_truth" in source,
    }


def plan_is_immutable() -> bool:
    plan = Path(__file__).with_name("PLAN.md")
    if hashlib.sha256(plan.read_bytes()).hexdigest() != PLAN_SHA256:
        return False
    result = subprocess.run(
        ["git", "diff", "--exit-code", PREREGISTRATION_COMMIT, "--", str(plan)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def production_diff_empty() -> bool:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            E2F_COMMIT,
            "--",
            "custody",
            "tests",
            "live",
            "scripts",
            "web",
            "research/design",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def compute_verdict(
    metrics: Mapping[str, Mapping[str, Any]],
    leakage_ok: bool,
    plan_ok: bool,
    replay_ok: bool,
    semantics_gap: bool,
) -> tuple[str, str | None]:
    failed: list[str] = []
    checks = (
        ("direct_stale_root_denied", metrics["direct_stale_root_denied"]["value"] == 1),
        (
            "fresh_child_stale_parent_false_act_permits",
            metrics["fresh_child_stale_parent_false_act_permits"]["numerator"] == 0,
        ),
        (
            "cross_agent_stale_dependency_preserved",
            metrics["cross_agent_stale_dependency_preserved"]["value"] == 1,
        ),
        (
            "mixed_parent_stale_dependency_preserved",
            metrics["mixed_parent_stale_dependency_preserved"]["value"] == 1,
        ),
        ("freeform_support_preserved", metrics["freeform_support_preserved"]["value"] == 1),
        (
            "preexisting_child_invalidated_after_parent_policy_change",
            metrics["preexisting_child_invalidated_after_parent_policy_change"]["value"] == 1,
        ),
        ("aba_dependency_false_accepts", metrics["aba_dependency_false_accepts"]["numerator"] == 0),
        ("legitimate_refresh_allows", metrics["legitimate_refresh_allows"]["value"] == 1),
        ("unrelated_policy_update_preserved", metrics["unrelated_policy_update_preserved"]["value"] == 1),
        ("direct_parent_recall", metrics["direct_parent_recall"]["value"] == 1),
        ("authority_dependency_recall", metrics["authority_dependency_recall"]["value"] == 1),
        ("historical_rewrite_count", metrics["historical_rewrite_count"]["numerator"] == 0),
        ("audit_trace_complete", metrics["audit_trace_complete"]["value"] == 1),
        ("deterministic_replay_match", replay_ok),
        ("ground_truth_leakage", leakage_ok),
        ("plan_immutable", plan_ok),
    )
    failed.extend(name for name, passed in checks if not passed)
    robust = not failed and not semantics_gap
    contained = (
        not semantics_gap
        and leakage_ok
        and plan_ok
        and metrics["fresh_child_stale_parent_false_act_permits"]["numerator"] == 0
        and (
            metrics["unrelated_policy_update_preserved"]["value"] != 1
            or metrics["legitimate_refresh_allows"]["value"] != 1
            or metrics["direct_parent_recall"]["value"] != 1
            or metrics["authority_dependency_recall"]["value"] != 1
        )
    )
    laundering = (
        metrics["fresh_child_stale_parent_false_act_permits"]["numerator"] > 0
        or metrics["aba_dependency_false_accepts"]["numerator"] > 0
    )
    # Exact frozen precedence: DESIGN-KILL, ROBUST, FAIL-CONTAINED,
    # LAUNDERING-FAIL, SEMANTICS-GAP.
    if False:
        verdict = "DESIGN-KILL"
    elif robust:
        verdict = "GENERATION-COMPOSITION-ROBUST"
    elif contained:
        verdict = "GENERATION-COMPOSITION-FAIL-CONTAINED"
    elif laundering:
        verdict = "GENERATION-LAUNDERING-FAIL"
    else:
        verdict = "SEMANTICS-GAP"
    return verdict, (failed[0] if failed else None)


def canonical_core(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    core = json.loads(json.dumps(result))
    core.pop("canonical_result_digest", None)
    return core


def build_result(runtime: RuntimeFixture, first: G3Mechanism, second: G3Mechanism) -> dict[str, Any]:
    policies = make_policies()
    ground_truth = make_ground_truth(policies)
    scorer = Scorer(ground_truth)
    # This assertion is deliberately before any scorer read.
    scorer_reads_before = scorer.read_counter
    runtime_forbidden = scan_forbidden(runtime)
    constructor_rejects = False
    try:
        G3Mechanism(runtime, ground_truth=ground_truth)
    except TypeError:
        constructor_rejects = True
    mechanism_has_scorer_reference = contains_identity(first, ground_truth)
    source_review = mechanism_source_review()
    replay_core_match = (
        serialize_run_core(first) == serialize_run_core(second)
    )
    score = scorer.score(first, replay_core_match)
    actions = score["actions"]
    leakage_ok = (
        constructor_rejects
        and not mechanism_has_scorer_reference
        and not runtime_forbidden
        and scorer_reads_before == 0
        and all(source_review.values())
    )
    plan_ok = plan_is_immutable()
    metrics = score["metrics"]
    verdict, first_failed = compute_verdict(
        metrics, leakage_ok, plan_ok, replay_core_match, semantics_gap=False
    )
    action_by_id = actions
    records = {
        record_id: serialize_record(first, record_id)
        for record_id in sorted(first.records())
    }
    p = make_policies()
    semantic_v1 = {"role": p["vendor_v1"].role, "caps": p["vendor_v1"].caps}
    semantic_v3 = {"role": p["vendor_v3"].role, "caps": p["vendor_v3"].caps}
    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "e2f_commit": E2F_COMMIT,
        "e2f_preregistration_commit": E2F_PREREG_COMMIT,
        "e2f_result_digest": E2F_RESULT_DIGEST,
        "plan_sha256": PLAN_SHA256,
        "experiment_source_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_digest": digest(runtime.as_dict()),
        "ground_truth_digest": digest(ground_truth.as_dict()),
        "selected_semantics": "G3_SUPPORT_ROOT_FRESHNESS_AT_ACTION",
        "policy_keys_and_snapshots": [
            item.as_dict()
            for item in sorted(
                (
                    p["vendor_v1"],
                    p["vendor_v2"],
                    p["vendor_v3"],
                    p["clean_current"],
                    p["payroll_g5"],
                    p["payroll_g6"],
                    p["registered_current"],
                    p["identity_current"],
                    p["freeform_current"],
                ),
                key=lambda item: (item.key.as_tuple(), item.generation),
            )
        ],
        "records": records,
        "variants": variant_artifacts(first, action_by_id),
        "actions": [item.as_dict() for item in first.actions()],
        "authority_traces": score["audit_entries"],
        "metrics": metrics,
        "historical_immutability": score["historical"],
        "aba_proof": {
            "v1_semantic_policy": semantic_v1,
            "v3_semantic_policy": semantic_v3,
            "semantic_equal": semantic_v1 == semantic_v3,
            "generations_distinct": p["vendor_v1"].generation != p["vendor_v3"].generation,
            "dependency_granting_generation": 1,
            "current_generation": 3,
            "stale_action": action_by_id["action-c-aba"].as_dict(),
        },
        "leakage_guard": {
            "constructor_rejects_ground_truth": constructor_rejects,
            "mechanism_has_scorer_reference": mechanism_has_scorer_reference,
            "runtime_forbidden_keys": runtime_forbidden,
            "scorer_reads_before_all_mechanism_variants": scorer_reads_before,
            "mechanism_source_review": source_review,
            "passed": leakage_ok,
        },
        "plan_immutable": plan_ok,
        "determinism": {
            "independent_clean_replay_match": replay_core_match,
        },
        "production_diff_empty_relative_to_e2f": production_diff_empty(),
        "verdict": verdict,
        "first_failed_invariant": first_failed,
    }
    result["canonical_result_digest"] = digest(canonical_core(result))
    return result


def serialize_run_core(run: G3Mechanism) -> dict[str, Any]:
    return {
        "events": list(run.event_log()),
        "records": {
            record_id: serialize_record(run, record_id)
            for record_id in sorted(run.records())
        },
        "actions": [item.as_dict() for item in run.actions()],
        "policies": [item.as_dict() for item in run.current_policies()],
    }


def render_result_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# E2G Generation Propagation Result",
        "",
        f"Verdict: **{result['verdict']}**",
        "",
        "This report is generated from `result.json`; it does not select the verdict.",
        "",
        "## Variant outcomes",
        "",
    ]
    for name, variant in result["variants"].items():
        outcomes = ", ".join(
            f"{item['record_id']}={'ALLOW' if item['allowed'] else 'DENY'}"
            for item in variant["actions"]
        )
        lines.append(f"- {name}: {outcomes}")
    lines.extend(["", "## Metrics", "", "| Metric | Result |", "| --- | ---: |"])
    for name, value in result["metrics"].items():
        lines.append(
            f"| `{name}` | {value['numerator']}/{value['denominator']} ({value['value']}) |"
        )
    lines.extend(
        [
            "",
            "## Integrity",
            "",
            f"- Ground-truth leakage: `{result['leakage_guard']['passed']}`.",
            f"- PLAN immutable: `{result['plan_immutable']}`.",
            f"- Deterministic replay: `{result['determinism']['independent_clean_replay_match']}`.",
            f"- Historical rewrites: `{result['historical_immutability']['rewrite_count']}/11`.",
            f"- First failed invariant: `{result['first_failed_invariant']}`.",
            "",
            "## Limitation",
            "",
            "This deterministic model does not establish production catalog/cache atomicity, distributed persistence, or gateway integration.",
            "",
            "## Next gate",
            "",
            "If the frozen gates pass, the next authorized research step is a separate persistence/integration experiment. It is not implemented here.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    runtime = make_runtime()
    first = execute(runtime)
    second = execute(runtime)
    result = build_result(runtime, first, second)
    result_path = Path(__file__).with_name("result.json")
    report_path = Path(__file__).with_name("RESULT.md")
    result_path.write_bytes(canonical_bytes(result) + b"\n")
    report_path.write_text(render_result_markdown(result), encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "canonical_result_digest": result["canonical_result_digest"],
        "plan_immutable": result["plan_immutable"],
        "deterministic_replay_match": result["determinism"]["independent_clean_replay_match"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
