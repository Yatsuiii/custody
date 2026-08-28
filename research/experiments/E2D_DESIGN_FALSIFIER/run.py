"""E2D: run Architecture A (the structural-envelope authority mechanism)
against the fixed scenario in PLAN.md and score it against the
preregistered gates in research/design/DESIGN_FALSIFIER.md.

No LLM, network service, embedding, fuzzy match, or content classifier
participates anywhere in this file. That is a preregistered KILL
condition if violated, not a style preference.

Run: python3 research/experiments/E2D_DESIGN_FALSIFIER/run.py
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional

OUT_DIR = Path(__file__).parent
BASELINE_COMMIT = "040c28c36d10a6c89144a19e01b0eae77a88ec64"


# ---------------------------------------------------------------------------
# Authority algebra (research/design/AUTHORITY_MODEL.md)
# ---------------------------------------------------------------------------


class Tier(IntEnum):
    NONE = 0
    INFORM = 1
    ACT = 2


def meet(*tiers: Tier) -> Tier:
    return min(tiers)


SCOPE = "export.send"
UNKNOWN_CONTEXT = "UNKNOWN_CONTEXT"


class Role(IntEnum):
    ORIGIN = 0
    RELAY = 1


class TransformClass(IntEnum):
    IDENTITY = 0
    REGISTERED = 1
    FREEFORM = 2
    INCOMPLETE = 3


# Policy: per-(source, operation) cap for ORIGIN roots, and per-transform cap.
ORIGIN_POLICY_CAP = {
    ("vendor_portal", "vendor_portal.lookup"): Tier.ACT,
}
REGISTERED_TRANSFORM_CAP = {
    "merge_v1": Tier.ACT,
}


@dataclass(frozen=True)
class AdmissionEnvelope:
    output_id: str
    admitted_at: str
    direct_parent_ids: tuple[str, ...]
    transform_class: TransformClass
    transform_revision: str
    context_complete: bool
    role: Optional[Role]  # only set for roots (direct_parent_ids == ())
    source_id: Optional[str] = None
    operation_id: Optional[str] = None
    # Computed, not caller-submitted, but stored on the record once bound.
    caps: dict[str, Tier] = field(default_factory=dict)
    support: tuple[str, ...] = field(default_factory=tuple)


class Graph:
    """The admitted-record store plus the meet-based authority computation.

    Deliberately separate from custody/graph.py: this is Architecture A,
    an experimental alternative mechanism, not a modification of production
    code (see .claude/SESSION_CONTRACT.md non-goals).
    """

    def __init__(self) -> None:
        self.records: dict[str, AdmissionEnvelope] = {}

    def admit_root(
        self,
        output_id: str,
        admitted_at: str,
        role: Role,
        source_id: str,
        operation_id: str,
        vouched_cap: Optional[Tier] = None,
        observable_upstream: bool = True,
    ) -> AdmissionEnvelope:
        support: tuple[str, ...]
        if role is Role.ORIGIN:
            cap = ORIGIN_POLICY_CAP.get((source_id, operation_id), Tier.NONE)
            support = (output_id,)
            context_complete = True
        else:  # RELAY
            if observable_upstream:
                # Not exercised by this fixture's relay case, kept for
                # completeness of the mechanism per TOOL_RELAY_MODEL.md.
                cap = vouched_cap if vouched_cap is not None else Tier.INFORM
                support = (output_id,)
                context_complete = True
            else:
                cap = Tier.INFORM
                support = (output_id, UNKNOWN_CONTEXT)
                context_complete = False
        env = AdmissionEnvelope(
            output_id=output_id,
            admitted_at=admitted_at,
            direct_parent_ids=(),
            transform_class=TransformClass.INCOMPLETE
            if not context_complete
            else TransformClass.IDENTITY,
            transform_revision="root-v1",
            context_complete=context_complete,
            role=role,
            source_id=source_id,
            operation_id=operation_id,
            caps={SCOPE: cap},
            support=tuple(sorted(support)),
        )
        self.records[output_id] = env
        return env

    def admit_derived(
        self,
        output_id: str,
        admitted_at: str,
        direct_parent_ids: tuple[str, ...],
        transform_class: TransformClass,
        transform_revision: str,
    ) -> AdmissionEnvelope:
        missing = [p for p in direct_parent_ids if p not in self.records]
        if missing:
            # Receipt validation failure -> INCOMPLETE, never a fresh root.
            env = AdmissionEnvelope(
                output_id=output_id,
                admitted_at=admitted_at,
                direct_parent_ids=direct_parent_ids,
                transform_class=TransformClass.INCOMPLETE,
                transform_revision=transform_revision,
                context_complete=False,
                role=None,
                caps={SCOPE: Tier.INFORM},
                support=tuple(sorted(set(direct_parent_ids) | {UNKNOWN_CONTEXT})),
            )
            self.records[output_id] = env
            return env

        parents = [self.records[p] for p in direct_parent_ids]
        parent_caps = [p.caps[SCOPE] for p in parents]

        if transform_class is TransformClass.IDENTITY:
            transform_cap = Tier.ACT
        elif transform_class is TransformClass.REGISTERED:
            transform_cap = REGISTERED_TRANSFORM_CAP.get(transform_revision, Tier.NONE)
        elif transform_class is TransformClass.FREEFORM:
            transform_cap = Tier.INFORM
        else:
            transform_cap = Tier.INFORM

        cap = meet(transform_cap, *parent_caps)
        support = set()
        for p in parents:
            support.update(p.support)

        env = AdmissionEnvelope(
            output_id=output_id,
            admitted_at=admitted_at,
            direct_parent_ids=direct_parent_ids,
            transform_class=transform_class,
            transform_revision=transform_revision,
            context_complete=True,
            role=None,
            caps={SCOPE: cap},
            support=tuple(sorted(support)),
        )
        self.records[output_id] = env
        return env

    def bound_caps(self, record_id: str) -> Tier:
        """Historical, immutable cap — never mutated by a revocation."""
        return self.records[record_id].caps[SCOPE]


# ---------------------------------------------------------------------------
# Revocation window and repair (research/design/DYNAMIC_TRUST_MODEL.md,
# REPAIR_SEMANTICS.md)
# ---------------------------------------------------------------------------


@dataclass
class RevocationWindow:
    id: str
    source_id: str
    operation_id: str
    start: str
    end: str
    reported_at: str
    state: str = "ACTIVE"
    generation: int = 1


@dataclass
class RepairPlan:
    window_id: str
    generation: int
    graph_high_watermark: int
    root_ids: tuple[str, ...] = ()
    affected_ids: tuple[str, ...] = ()
    per_record_outcome: dict[str, str] = field(default_factory=dict)
    phase: str = "INTENT"  # INTENT -> PLANNED -> APPLYING -> COMPLETE


class RevocationController:
    """Implements the ordering in DYNAMIC_TRUST_MODEL.md's
    "Write and revocation ordering" section, with explicit snapshot points
    for the crash/replay probes.
    """

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.windows: dict[str, RevocationWindow] = {}
        self.plans: dict[str, RepairPlan] = {}

    def select_roots(self, window: RevocationWindow) -> tuple[str, ...]:
        roots = []
        for rid, rec in self.graph.records.items():
            if rec.direct_parent_ids:
                continue  # only direct source roots qualify
            if rec.source_id != window.source_id:
                continue
            if rec.operation_id != window.operation_id:
                continue
            if window.start <= rec.admitted_at < window.end:
                roots.append(rid)
        return tuple(sorted(roots))

    def closure(self, root_ids: tuple[str, ...]) -> tuple[str, ...]:
        root_set = set(root_ids)
        affected = set()
        for rid, rec in self.graph.records.items():
            if root_set & set(rec.support):
                affected.add(rid)
        return tuple(sorted(affected))

    def activate(self, window: RevocationWindow) -> RepairPlan:
        """Step 1-4: intent -> high-watermark -> plan, persisted before any
        mutation. Returns the plan at phase PLANNED.
        """
        self.windows[window.id] = window
        roots = self.select_roots(window)
        affected = self.closure(roots)
        plan = RepairPlan(
            window_id=window.id,
            generation=window.generation,
            graph_high_watermark=len(self.graph.records),
            root_ids=roots,
            affected_ids=affected,
            per_record_outcome={},
            phase="PLANNED",
        )
        self.plans[window.id] = plan
        return plan

    def effective_cap(self, record_id: str) -> Tier:
        """EffectiveCaps: NONE if support intersects any ACTIVE window's
        affected closure, else the bound historical cap. Consulted live by
        the action gateway — this is the safety boundary, independent of
        whether physical deletion has happened yet.

        DYNAMIC_TRUST_MODEL.md step 2 ("close the action race") requires
        this to fail closed the moment a window's intent is active, even
        before its plan/closure is computed -- a stale or unavailable
        generation must deny, not default-allow. So an ACTIVE window with
        no plan yet (or a plan not past INTENT) blocks every record, not
        just the ones a not-yet-computed closure would name.
        """
        rec = self.graph.records[record_id]
        for window in self.windows.values():
            if window.state != "ACTIVE":
                continue
            plan = self.plans.get(window.id)
            if plan is None or plan.phase == "INTENT":
                return Tier.NONE  # generation unavailable: fail closed
            if record_id in plan.affected_ids:
                return Tier.NONE
        return rec.caps[SCOPE]

    def apply_repair(self, window_id: str, stop_after_index: Optional[int] = None) -> RepairPlan:
        """Step 5: apply idempotently, one outcome per affected id, in a
        fixed order. `stop_after_index` simulates a crash after N outcomes
        are applied, for the replay probes.
        """
        plan = self.plans[window_id]
        plan.phase = "APPLYING"
        for i, rid in enumerate(plan.affected_ids):
            if stop_after_index is not None and i > stop_after_index:
                break
            if rid in plan.per_record_outcome:
                continue  # idempotent: duplicate delivery is a no-op
            rec = self.graph.records[rid]
            if rec.direct_parent_ids == () and rid in plan.root_ids:
                plan.per_record_outcome[rid] = "DELETED"
            else:
                plan.per_record_outcome[rid] = "DELETED"
        if stop_after_index is None or stop_after_index >= len(plan.affected_ids) - 1:
            plan.phase = "COMPLETE"
        return plan

    def snapshot(self) -> dict:
        return {
            "windows": copy.deepcopy(self.windows),
            "plans": copy.deepcopy(self.plans),
        }

    def restore(self, snap: dict) -> None:
        self.windows = copy.deepcopy(snap["windows"])
        self.plans = copy.deepcopy(snap["plans"])


# ---------------------------------------------------------------------------
# Fixture (PLAN.md, "Six required elements")
# ---------------------------------------------------------------------------


def build_fixture() -> Graph:
    g = Graph()

    g.admit_root(
        "E-RELAY-1", "2026-08-10T09:00:00Z", Role.RELAY,
        source_id="relay_proxy", operation_id="relay_proxy.fetch",
        observable_upstream=False,
    )

    g.admit_root(
        "E-BENIGN-1", "2026-08-05T09:00:00Z", Role.ORIGIN,
        source_id="vendor_portal", operation_id="vendor_portal.lookup",
    )
    g.admit_derived(
        "E-BENIGN-PARA-1", "2026-08-05T09:05:00Z", ("E-BENIGN-1",),
        TransformClass.FREEFORM, "summarize_v1",
    )
    g.admit_derived(
        "E-BENIGN-IDENTITY-1", "2026-08-06T09:00:00Z", ("E-BENIGN-1",),
        TransformClass.IDENTITY, "identity-v1",
    )

    g.admit_root(
        "E-MAL-1", "2026-08-15T09:00:00Z", Role.ORIGIN,
        source_id="unvouched_source", operation_id="unvouched.op",
    )
    g.admit_derived(
        "E-MAL-PARA-1", "2026-08-15T09:05:00Z", ("E-MAL-1",),
        TransformClass.FREEFORM, "summarize_v1",
    )

    g.admit_root(
        "E-VENDOR-2", "2026-08-15T10:00:00Z", Role.ORIGIN,
        source_id="vendor_portal", operation_id="vendor_portal.lookup",
    )
    g.admit_derived(
        "E-SYN-ACT-ACT", "2026-08-15T10:05:00Z", ("E-BENIGN-1", "E-VENDOR-2"),
        TransformClass.REGISTERED, "merge_v1",
    )
    g.admit_derived(
        "E-SYN-ACT-NONE", "2026-08-15T10:10:00Z", ("E-BENIGN-1", "E-MAL-1"),
        TransformClass.REGISTERED, "merge_v1",
    )

    return g


GROUND_TRUTH_PARENTS = {
    "E-RELAY-1": (),
    "E-BENIGN-1": (),
    "E-BENIGN-PARA-1": ("E-BENIGN-1",),
    "E-BENIGN-IDENTITY-1": ("E-BENIGN-1",),
    "E-MAL-1": (),
    "E-MAL-PARA-1": ("E-MAL-1",),
    "E-VENDOR-2": (),
    "E-SYN-ACT-ACT": ("E-BENIGN-1", "E-VENDOR-2"),
    "E-SYN-ACT-NONE": ("E-BENIGN-1", "E-MAL-1"),
}

GROUND_TRUTH_AFFECTED = {"E-VENDOR-2", "E-SYN-ACT-ACT"}

EXPECTED_CAPS_BEFORE = {
    "E-RELAY-1": Tier.INFORM,
    "E-BENIGN-1": Tier.ACT,
    "E-BENIGN-PARA-1": Tier.INFORM,
    "E-BENIGN-IDENTITY-1": Tier.ACT,
    "E-MAL-1": Tier.NONE,
    "E-MAL-PARA-1": Tier.NONE,
    "E-VENDOR-2": Tier.ACT,
    "E-SYN-ACT-ACT": Tier.ACT,
    "E-SYN-ACT-NONE": Tier.NONE,
}


# ---------------------------------------------------------------------------
# Falsifier: metrics + crash/replay probes
# ---------------------------------------------------------------------------


def digest_state(graph: Graph, controller: RevocationController) -> str:
    payload = {
        "records": {
            rid: {
                "caps": {k: int(v) for k, v in rec.caps.items()},
                "support": rec.support,
                "direct_parent_ids": rec.direct_parent_ids,
            }
            for rid, rec in sorted(graph.records.items())
        },
        "windows": {
            wid: {"state": w.state, "generation": w.generation}
            for wid, w in sorted(controller.windows.items())
        },
        "plans": {
            pid: {
                "phase": p.phase,
                "affected_ids": p.affected_ids,
                "outcomes": dict(sorted(p.per_record_outcome.items())),
            }
            for pid, p in sorted(controller.plans.items())
        },
    }
    blob = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def run_full(with_window: bool) -> tuple[Graph, RevocationController]:
    g = build_fixture()
    c = RevocationController(g)
    if with_window:
        w = RevocationWindow(
            id="W1", source_id="vendor_portal", operation_id="vendor_portal.lookup",
            start="2026-08-12T00:00:00Z", end="2026-08-19T00:00:00Z",
            reported_at="2026-08-20T00:00:00Z",
        )
        c.activate(w)
        c.apply_repair("W1")
    return g, c


def compute_parent_and_caps_metrics(g0: Graph) -> dict:
    parent_ok = sum(
        1
        for rid, expected in GROUND_TRUTH_PARENTS.items()
        if tuple(sorted(g0.records[rid].direct_parent_ids)) == tuple(sorted(expected))
    )
    caps_before_ok = all(
        g0.records[rid].caps[SCOPE] == expected
        for rid, expected in EXPECTED_CAPS_BEFORE.items()
    )
    return {
        "direct_parent_recall": parent_ok / len(GROUND_TRUTH_PARENTS),
        "caps_before_window_match_plan": caps_before_ok,
    }


def compute_affected_metrics(g1: Graph, c1: RevocationController, plan: RepairPlan) -> dict:
    affected_found = set(plan.affected_ids)

    false_act_permits = 0
    for rid in g1.records:
        eff = c1.effective_cap(rid)
        should_be_none = rid in GROUND_TRUTH_AFFECTED
        expected = EXPECTED_CAPS_BEFORE[rid]
        if should_be_none and eff is Tier.ACT:
            false_act_permits += 1
        elif not should_be_none and expected is not Tier.ACT and eff is Tier.ACT:
            false_act_permits += 1

    same_record_increases = sum(
        1
        for rid in g1.records
        if g1.bound_caps(rid) != EXPECTED_CAPS_BEFORE[rid]
    )

    benign_para = g1.records["E-BENIGN-PARA-1"]
    benign_inform_retained = (
        benign_para.caps[SCOPE] == Tier.INFORM
        and "E-BENIGN-PARA-1" not in plan.affected_ids
    )

    outside_sibling_preserved = (
        c1.effective_cap("E-BENIGN-1") == Tier.ACT
        and c1.effective_cap("E-BENIGN-IDENTITY-1") == Tier.ACT
        and "E-BENIGN-1" not in plan.affected_ids
        and "E-BENIGN-IDENTITY-1" not in plan.affected_ids
    )

    syn_act_none_unaffected = (
        "E-SYN-ACT-NONE" not in plan.affected_ids
        and g1.records["E-SYN-ACT-NONE"].caps[SCOPE] == Tier.NONE
    )

    return {
        "affected_recall": len(GROUND_TRUTH_AFFECTED & affected_found) / len(GROUND_TRUTH_AFFECTED),
        "affected_set_exact_match": affected_found == GROUND_TRUTH_AFFECTED,
        "false_act_permits": false_act_permits,
        "same_record_authority_increases": same_record_increases,
        "benign_inform_retained": benign_inform_retained,
        "outside_sibling_preserved": outside_sibling_preserved,
        "syn_act_none_unaffected_by_window": syn_act_none_unaffected,
    }


def _run_probe(name: str, stop_index: Optional[int]) -> tuple[Graph, RevocationController, bool]:
    """Returns (graph, controller-after-resume, unsafe_during_crash).

    `unsafe_during_crash` is checked at the actual crash point, before any
    resume/replay happens -- checking only the post-resume state (as an
    earlier version of this probe did) never exercises the real race and
    would silently pass a mechanism that fails open mid-crash.
    """
    g = build_fixture()
    c = RevocationController(g)
    w = RevocationWindow(
        id="W1", source_id="vendor_portal", operation_id="vendor_portal.lookup",
        start="2026-08-12T00:00:00Z", end="2026-08-19T00:00:00Z",
        reported_at="2026-08-20T00:00:00Z",
    )
    if name == "after_intent_before_plan":
        c.windows["W1"] = w  # intent only: no plan exists yet
        unsafe = any(c.effective_cap(rid) == Tier.ACT for rid in GROUND_TRUTH_AFFECTED)
        c.activate(w)
        c.apply_repair("W1")
    elif stop_index == -1:
        c.activate(w)  # plan exists, phase=PLANNED, no outcomes applied yet
        unsafe = any(c.effective_cap(rid) == Tier.ACT for rid in GROUND_TRUTH_AFFECTED)
        c.apply_repair("W1")
    else:
        c.activate(w)
        c.apply_repair("W1", stop_after_index=stop_index)  # crash mid-repair
        unsafe = any(c.effective_cap(rid) == Tier.ACT for rid in GROUND_TRUTH_AFFECTED)
        c.apply_repair("W1")  # resume: idempotent completion
    return g, c, unsafe


def compute_replay_metrics(no_fault_digest: str) -> dict:
    probe_points = [
        ("after_intent_before_plan", None),
        ("after_plan_before_first_outcome", -1),
        ("midway_repair", 0),
        ("after_outcomes_before_complete", 1),
    ]
    replay_results = {}
    fault_windows: list[str] = []
    for name, stop_index in probe_points:
        g, c, unsafe = _run_probe(name, stop_index)
        if unsafe:
            fault_windows.append(name)
        replay_results[name] = digest_state(g, c) == no_fault_digest
    return {
        "replay_digest_stable": all(replay_results.values()),
        "replay_probe_detail": replay_results,
        "unsafe_fault_windows": len(fault_windows),
        "unsafe_fault_window_names": fault_windows,
    }


def compute_verdict(metrics: dict) -> tuple[str, str]:
    pass_conditions = [
        metrics["direct_parent_recall"] == 1.0,
        metrics["affected_recall"] == 1.0,
        metrics["false_act_permits"] == 0,
        metrics["same_record_authority_increases"] == 0,
        metrics["benign_inform_retained"] is True,
        metrics["outside_sibling_preserved"] is True,
        metrics["replay_digest_stable"] is True,
        metrics["unsafe_fault_windows"] == 0,
    ]
    security_conditions = [
        metrics["affected_recall"] == 1.0,
        metrics["false_act_permits"] == 0,
        metrics["same_record_authority_increases"] == 0,
        metrics["unsafe_fault_windows"] == 0,
    ]

    if all(pass_conditions):
        return "PASS", "all nine PASS conditions satisfied"

    if all(security_conditions):
        failed = [
            name
            for name, ok in [
                ("benign_inform_retained", metrics["benign_inform_retained"] is True),
                ("outside_sibling_preserved", metrics["outside_sibling_preserved"] is True),
                ("replay_digest_stable", metrics["replay_digest_stable"] is True),
                ("direct_parent_recall", metrics["direct_parent_recall"] == 1.0),
            ]
            if not ok
        ]
        return "CAUTION", f"security conditions hold; failed utility/selectivity property(ies): {failed}"

    killed = [
        reason
        for ok, reason in [
            (metrics["false_act_permits"] == 0, "an INFORM/NONE/incomplete/affected record authorized an action"),
            (metrics["affected_recall"] == 1.0, "a ground-truth affected descendant was missed"),
            (metrics["same_record_authority_increases"] == 0, "unchanged content gained authority after pruning/repair"),
            (metrics["unsafe_fault_windows"] == 0, "a crash/retry opened an action-authority window"),
        ]
        if not ok
    ]
    return "KILL", f"KILL condition(s) triggered: {killed}"


def main() -> dict:
    g0 = build_fixture()
    metrics: dict = compute_parent_and_caps_metrics(g0)

    g1, c1 = run_full(with_window=True)
    plan = c1.plans["W1"]
    metrics.update(compute_affected_metrics(g1, c1, plan))

    no_fault_g, no_fault_c = run_full(with_window=True)
    no_fault_digest = digest_state(no_fault_g, no_fault_c)
    metrics.update(compute_replay_metrics(no_fault_digest))

    # This mechanism never imports an LLM/embedding/network client -- a
    # preregistered KILL condition if it did. Stated as an explicit,
    # auditable claim rather than left implicit.
    metrics["mechanism_uses_no_semantic_inference"] = True

    verdict, verdict_reason = compute_verdict(metrics)

    result = {
        "baseline_commit": BASELINE_COMMIT,
        "experiment_source_digest": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "fixture_digest": hashlib.sha256(
            json.dumps(GROUND_TRUTH_PARENTS, sort_keys=True).encode()
        ).hexdigest(),
        "mechanism_mode": "STRUCTURAL_ENVELOPE_A",
        "metrics": {
            k: (v if not isinstance(v, dict) else v) for k, v in metrics.items()
        },
        "per_record": {
            rid: {
                "direct_parent_ids": list(rec.direct_parent_ids),
                "caps": {k: int(v) for k, v in rec.caps.items()},
                "support": list(rec.support),
                "effective_cap_after_w1": int(c1.effective_cap(rid)),
            }
            for rid, rec in g1.records.items()
        },
        "window": {
            "id": "W1",
            "root_ids": list(plan.root_ids),
            "affected_ids": list(plan.affected_ids),
            "phase": plan.phase,
        },
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2, default=str))
    print(f"Verdict: {result['verdict']}")
    print(f"Reason: {result['verdict_reason']}")
    print(json.dumps(result["metrics"], indent=2, default=str))
