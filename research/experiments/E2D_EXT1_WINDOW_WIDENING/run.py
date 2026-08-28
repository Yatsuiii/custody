"""E2D-EXT1: window widening, on top of E2D's mechanism unmodified.

Imports Graph/RevocationController/Tier etc. from the frozen E2D run.py
rather than duplicating them -- the mechanism under test does not change,
only the scenario. E2D's own run.py is left untouched by this file; the
widening capability it doesn't have is added here via a subclass, not by
editing the artifact E2D's PASS verdict was recorded against.

Run: python3 research/experiments/E2D_EXT1_WINDOW_WIDENING/run.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "E2D_DESIGN_FALSIFIER"))
from run import (  # noqa: E402
    Graph,
    Role,
    RevocationController,
    RevocationWindow,
    Tier,
    TransformClass,
    build_fixture as e2d_build_fixture,
)

OUT_DIR = Path(__file__).parent


@dataclass
class RepairPlanG:
    """Generation-aware repair plan: same shape as E2D's RepairPlan, plus a
    `generation` field and `superseded_from` for audit."""

    window_id: str
    generation: int
    graph_high_watermark: int
    root_ids: tuple[str, ...] = ()
    affected_ids: tuple[str, ...] = ()
    per_record_outcome: dict[str, str] = field(default_factory=dict)
    phase: str = "PLANNED"


class WideningController(RevocationController):
    """Extends E2D's RevocationController with widen(), which E2D's frozen
    mechanism does not implement. Everything else (select_roots, closure,
    effective_cap, apply_repair) is reused unmodified.
    """

    def __init__(self, graph: Graph) -> None:
        super().__init__(graph)
        self.window_history: dict[str, list[RevocationWindow]] = {}
        self.plan_history: dict[str, list[RepairPlanG]] = {}

    def widen(self, window_id: str, new_end: str, reported_at: str) -> RepairPlanG:
        old_window = self.windows[window_id]
        old_plan = self.plans[window_id]

        superseded = RevocationWindow(
            id=old_window.id,
            source_id=old_window.source_id,
            operation_id=old_window.operation_id,
            start=old_window.start,
            end=old_window.end,
            reported_at=old_window.reported_at,
            state="SUPERSEDED",
            generation=old_window.generation,
        )
        self.window_history.setdefault(window_id, []).append(superseded)
        self.plan_history.setdefault(window_id, []).append(old_plan)

        new_window = RevocationWindow(
            id=window_id,
            source_id=old_window.source_id,
            operation_id=old_window.operation_id,
            start=old_window.start,
            end=new_end,
            reported_at=reported_at,
            state="ACTIVE",
            generation=old_window.generation + 1,
        )
        self.windows[window_id] = new_window

        new_roots = self.select_roots(new_window)
        new_affected = self.closure(new_roots)

        # Carry forward every completed outcome unchanged; only new
        # affected ids get a fresh (still-pending) outcome slot.
        carried_outcomes = dict(old_plan.per_record_outcome)

        new_plan = RepairPlanG(
            window_id=window_id,
            generation=new_window.generation,
            graph_high_watermark=len(self.graph.records),
            root_ids=new_roots,
            affected_ids=new_affected,
            per_record_outcome=carried_outcomes,
            phase="PLANNED",
        )
        self.plans[window_id] = new_plan
        return new_plan

    def apply_repair_g(self, window_id: str) -> RepairPlanG:
        plan = self.plans[window_id]
        plan.phase = "APPLYING"
        for rid in plan.affected_ids:
            if rid in plan.per_record_outcome:
                continue  # already applied in a prior generation: no-op
            plan.per_record_outcome[rid] = "DELETED"
        plan.phase = "COMPLETE"
        return plan


def build_fixture() -> Graph:
    g = e2d_build_fixture()
    g.admit_root(
        "E-VENDOR-3", "2026-08-20T09:00:00Z", Role.ORIGIN,
        source_id="vendor_portal", operation_id="vendor_portal.lookup",
    )
    g.admit_derived(
        "E-VENDOR-3-PARA", "2026-08-20T09:05:00Z", ("E-VENDOR-3",),
        TransformClass.FREEFORM, "summarize_v1",
    )
    return g


def digest_outcomes(plan) -> str:
    payload = json.dumps(dict(sorted(plan.per_record_outcome.items())), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> dict:
    g = build_fixture()
    c = WideningController(g)

    # Generation 1: exactly E2D's window.
    w1 = RevocationWindow(
        id="W1", source_id="vendor_portal", operation_id="vendor_portal.lookup",
        start="2026-08-12T00:00:00Z", end="2026-08-19T00:00:00Z",
        reported_at="2026-08-20T00:00:00Z",
    )
    c.activate(w1)
    c.apply_repair("W1")
    gen1_plan = c.plans["W1"]
    gen1_affected = set(gen1_plan.affected_ids)

    # Generation 2: widen to include E-VENDOR-3.
    gen2_plan = c.widen("W1", new_end="2026-08-22T00:00:00Z", reported_at="2026-08-25T00:00:00Z")
    c.apply_repair_g("W1")
    gen2_affected = set(gen2_plan.affected_ids)

    checks = {
        "superset": gen2_affected.issuperset(gen1_affected),
        "vendor_3_newly_affected": "E-VENDOR-3" in gen2_affected and "E-VENDOR-3" not in gen1_affected,
        "gen1_outcomes_preserved_unchanged": all(
            gen2_plan.per_record_outcome.get(rid) == gen1_plan.per_record_outcome.get(rid)
            for rid in gen1_affected
        ),
        "gen1_record_superseded_not_erased": (
            c.window_history["W1"][-1].state == "SUPERSEDED"
            and c.window_history["W1"][-1].end == "2026-08-19T00:00:00Z"
        ),
        "gen2_record_active": c.windows["W1"].state == "ACTIVE" and c.windows["W1"].generation == 2,
        "outside_sibling_still_unaffected": (
            "E-BENIGN-1" not in gen2_affected
            and "E-BENIGN-IDENTITY-1" not in gen2_affected
            and c.effective_cap("E-BENIGN-1") == Tier.ACT
            and c.effective_cap("E-BENIGN-IDENTITY-1") == Tier.ACT
        ),
        "no_narrowing_side_effect": gen1_affected.issubset(gen2_affected),
        "vendor_3_para_support_correct": tuple(g.records["E-VENDOR-3-PARA"].support) == ("E-VENDOR-3",),
    }

    verdict = "PASS" if all(checks.values()) else "FAIL"
    failed = [k for k, v in checks.items() if not v]

    result = {
        "checks": checks,
        "gen1_affected": sorted(gen1_affected),
        "gen2_affected": sorted(gen2_affected),
        "newly_affected_by_widening": sorted(gen2_affected - gen1_affected),
        "verdict": verdict,
        "verdict_reason": "all checks passed" if verdict == "PASS" else f"failed: {failed}",
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2, default=str))
    print(f"Verdict: {result['verdict']}")
    print(f"Reason: {result['verdict_reason']}")
    print(json.dumps(result["checks"], indent=2))
