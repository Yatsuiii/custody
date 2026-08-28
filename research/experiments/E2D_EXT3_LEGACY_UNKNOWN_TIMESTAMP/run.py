"""E2D-EXT3: legacy/unclassifiable timestamp fallback (whole-source
quarantine), on top of E2D's mechanism. Imports Graph/RevocationController
etc. from the frozen E2D run.py rather than duplicating them.

Run: python3 research/experiments/E2D_EXT3_LEGACY_UNKNOWN_TIMESTAMP/run.py
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
        "E-LEGACY-1", None, e2d.Role.ORIGIN,
        source_id="vendor_portal", operation_id="vendor_portal.lookup",
    )
    return g


def baseline_crashes() -> tuple[bool, str]:
    """Confirms, honestly, what the unmodified E2D mechanism actually does
    -- reported in RESULT.md either way, not assumed."""
    g = build_fixture()
    c = e2d.RevocationController(g)
    w1 = e2d.RevocationWindow(
        id="W1", source_id="vendor_portal", operation_id="vendor_portal.lookup",
        start="2026-08-12T00:00:00Z", end="2026-08-19T00:00:00Z",
        reported_at="2026-08-20T00:00:00Z",
    )
    try:
        c.activate(w1)
        return False, "activate() succeeded without error"
    except TypeError as exc:
        return True, f"TypeError: {exc}"


class WholeSourceQuarantineController(e2d.RevocationController):
    """Implements DYNAMIC_TRUST_MODEL.md's fallback option 1: an
    unclassifiable record for the targeted source escalates root
    selection to the whole source/operation, not just the literal
    [start, end) range.
    """

    def _source_has_unclassifiable(self, window) -> bool:
        return any(
            rec.source_id == window.source_id
            and rec.operation_id == window.operation_id
            and not rec.direct_parent_ids
            and rec.admitted_at is None
            for rec in self.graph.records.values()
        )

    def select_roots(self, window):
        if not self._source_has_unclassifiable(window):
            return super().select_roots(window)
        return tuple(
            sorted(
                rid
                for rid, rec in self.graph.records.items()
                if not rec.direct_parent_ids
                and rec.source_id == window.source_id
                and rec.operation_id == window.operation_id
            )
        )


def main() -> dict:
    crashed, crash_detail = baseline_crashes()

    g = build_fixture()
    c = WholeSourceQuarantineController(g)
    w1 = e2d.RevocationWindow(
        id="W1", source_id="vendor_portal", operation_id="vendor_portal.lookup",
        start="2026-08-12T00:00:00Z", end="2026-08-19T00:00:00Z",
        reported_at="2026-08-20T00:00:00Z",
    )
    c.activate(w1)
    c.apply_repair("W1")
    affected = set(c.plans["W1"].affected_ids)

    checks = {
        "baseline_crashes_rather_than_silently_passes": crashed,
        "legacy_record_affected": "E-LEGACY-1" in affected,
        "escalation_cost_visible_benign_root": "E-BENIGN-1" in affected,
        "escalation_cost_visible_benign_identity": "E-BENIGN-IDENTITY-1" in affected,
        "no_leak_to_unvouched_source": "E-MAL-1" not in affected and "E-MAL-PARA-1" not in affected,
        "no_leak_to_relay_source": "E-RELAY-1" not in affected,
        "vendor_2_still_affected": "E-VENDOR-2" in affected,
        "no_crash_with_fallback": True,  # reaching here means apply_repair completed
    }

    verdict = "PASS" if all(checks.values()) else "FAIL"
    failed = [k for k, v in checks.items() if not v]

    result = {
        "baseline_crash_detail": crash_detail,
        "checks": checks,
        "affected_under_escalation": sorted(affected),
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
