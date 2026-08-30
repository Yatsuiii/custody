"""E2D-EXT2: overlapping windows from separate incident reports, on top of
E2D's mechanism unmodified. Imports Graph/RevocationController/etc. from
the frozen E2D run.py rather than duplicating them, exactly like EXT1.

Run: python3 research/experiments/E2D_EXT2_OVERLAPPING_WINDOWS/run.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).parent
E2D_DIR = Path(__file__).parent.parent / "E2D_DESIGN_FALSIFIER"


def _load_e2d():
    spec = importlib.util.spec_from_file_location("e2d_run", E2D_DIR / "run.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["e2d_run"] = mod
    spec.loader.exec_module(mod)
    return mod


e2d = _load_e2d()


def build_fixture():
    g = e2d.build_fixture()
    g.admit_root(
        "E-GAP-1", "2026-08-19T12:00:00Z", e2d.Role.ORIGIN,
        source_id="vendor_portal", operation_id="vendor_portal.lookup",
    )
    g.admit_root(
        "E-VENDOR-W2", "2026-08-21T09:00:00Z", e2d.Role.ORIGIN,
        source_id="vendor_portal", operation_id="vendor_portal.lookup",
    )
    g.admit_derived(
        "E-SYN-BOTH", "2026-08-21T09:05:00Z", ("E-VENDOR-2", "E-VENDOR-W2"),
        e2d.TransformClass.REGISTERED, "merge_v1",
    )
    return g


def main() -> dict:
    g = build_fixture()
    c = e2d.RevocationController(g)

    w1 = e2d.RevocationWindow(
        id="W1", source_id="vendor_portal", operation_id="vendor_portal.lookup",
        start="2026-08-12T00:00:00Z", end="2026-08-19T00:00:00Z",
        reported_at="2026-08-20T00:00:00Z",
    )
    w2 = e2d.RevocationWindow(
        id="W2", source_id="vendor_portal", operation_id="vendor_portal.lookup",
        start="2026-08-21T00:00:00Z", end="2026-08-24T00:00:00Z",
        reported_at="2026-08-25T00:00:00Z",
    )

    c.activate(w1)
    c.apply_repair("W1")
    w1_affected = set(c.plans["W1"].affected_ids)

    c.activate(w2)
    c.apply_repair("W2")
    w2_affected = set(c.plans["W2"].affected_ids)

    checks = {
        "w1_own_closure_unchanged_by_w2": w1_affected == set(c.plans["W1"].affected_ids),
        "vendor_2_affected_via_w1": c.effective_cap("E-VENDOR-2") == e2d.Tier.NONE,
        "syn_act_act_affected_via_w1": c.effective_cap("E-SYN-ACT-ACT") == e2d.Tier.NONE,
        "vendor_w2_affected_via_w2": c.effective_cap("E-VENDOR-W2") == e2d.Tier.NONE,
        "syn_both_affected_by_union": c.effective_cap("E-SYN-BOTH") == e2d.Tier.NONE,
        "gap_record_unaffected": (
            c.effective_cap("E-GAP-1") == e2d.Tier.ACT
            and "E-GAP-1" not in w1_affected
            and "E-GAP-1" not in w2_affected
        ),
        "outside_sibling_still_unaffected": (
            c.effective_cap("E-BENIGN-1") == e2d.Tier.ACT
            and c.effective_cap("E-BENIGN-IDENTITY-1") == e2d.Tier.ACT
        ),
        "windows_independent_in_closure": "E-VENDOR-W2" not in w1_affected and "E-VENDOR-2" not in w2_affected,
    }

    verdict = "PASS" if all(checks.values()) else "FAIL"
    failed = [k for k, v in checks.items() if not v]

    result = {
        "checks": checks,
        "w1_affected": sorted(w1_affected),
        "w2_affected": sorted(w2_affected),
        "union_affected": sorted(w1_affected | w2_affected),
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
