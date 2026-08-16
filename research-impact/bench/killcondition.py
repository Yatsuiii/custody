"""The pre-registered kill condition, as code rather than as a judgement call.

These numbers were fixed in the session contract before the sequence existed and
before any system was run against it. Encoding them here means the verdict is
computed from the recorded metrics by a function anybody can read, rather than
argued for after the fact by whoever has an interest in the answer.

The thesis under test: when research changes repeatedly over time, explicit
state semantics prevent accumulated inconsistency that a model-maintained
research state cannot reliably prevent. The baseline that matters is A1, the
persistent monolithic model, not the stateless A0.
"""

from __future__ import annotations

REGISTERED = "2026-08-15, before the sequence was written"

END_ACCURACY_MARGIN = 0.05
PERSISTENCE_FLOOR = 0.95
PERSISTENCE_CEILING = 0.80
REGRESSION_RATIO = 0.5
OVERRIDE_ACCURACY = 0.95
OVERRIDE_PERSISTENCE = 0.95
CRITERIA_NEEDED = 2


def _rate(totals: dict) -> float:
    steps = totals.get("steps_total") or 1
    return totals["regressions"] / steps


def evaluate(a1: dict, b: dict) -> dict:
    """Returns each criterion, the count met, and the verdict. No opinions."""
    criteria = [
        {
            "name": "end-state accuracy",
            "requires": f"B >= A1 + {END_ACCURACY_MARGIN}",
            "a1": a1["mean_end_accuracy"], "b": b["mean_end_accuracy"],
            "met": b["mean_end_accuracy"]
            >= a1["mean_end_accuracy"] + END_ACCURACY_MARGIN,
        },
        {
            "name": "correction persistence",
            "requires": f"B >= {PERSISTENCE_FLOOR} and A1 <= "
                        f"{PERSISTENCE_CEILING}",
            "a1": a1["mean_correction_persistence"],
            "b": b["mean_correction_persistence"],
            "met": (b["mean_correction_persistence"] >= PERSISTENCE_FLOOR
                    and a1["mean_correction_persistence"]
                    <= PERSISTENCE_CEILING),
        },
        {
            "name": "regression rate",
            "requires": f"B <= A1 x {REGRESSION_RATIO}",
            "a1": round(_rate(a1), 4), "b": round(_rate(b), 4),
            "met": _rate(b) <= _rate(a1) * REGRESSION_RATIO,
        },
        {
            "name": "order convergence",
            "requires": "B identical across all three orders, A1 across none",
            "a1": a1["orders_agreeing"], "b": b["orders_agreeing"],
            "met": b["orders_agreeing"] == 3 and a1["orders_agreeing"] <= 1,
        },
    ]
    met = sum(1 for item in criteria if item["met"])
    override = (a1["mean_end_accuracy"] >= OVERRIDE_ACCURACY
                and a1["mean_correction_persistence"] >= OVERRIDE_PERSISTENCE)
    killed = override or met < CRITERIA_NEEDED
    return {
        "registered": REGISTERED,
        "criteria": criteria,
        "criteria_met": met,
        "criteria_needed": CRITERIA_NEEDED,
        "hard_override_triggered": override,
        "hard_override": (
            f"A1 end accuracy >= {OVERRIDE_ACCURACY} and correction "
            f"persistence >= {OVERRIDE_PERSISTENCE} kills the thesis whatever "
            f"the four criteria say"
        ),
        "verdict": "KILL" if killed else "CONTINUE",
        "meaning": (
            "KILL means a model-maintained research state was sufficient, so "
            "explicit dependency machinery is unnecessary for this product."
            if killed else
            "CONTINUE means explicit state prevented inconsistency the "
            "persistent baseline did not."
        ),
    }
