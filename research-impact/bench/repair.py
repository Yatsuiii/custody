"""Correction locality: what it costs a human to get back to the right state.

Accuracy is not the only thing that matters when a system is wrong, and for a
research tool it may not be the thing that matters most. What matters is whether
a mistake can be found, corrected once, and have every consequence of it follow.

So this measures, for each wrong answer: how many corrections a researcher must
make, how many downstream nodes each one repairs, and how many nodes are still
wrong afterwards. The two systems are corrected in the way each actually admits:
System B's relations are rejected or restated one at a time and propagation
reruns, which is verified here rather than assumed. The monolithic baseline
exposes no intermediate object to correct, so its answer is edited node by node,
and nothing is learned that would carry to the next document.
"""

from __future__ import annotations

from keel import ledger
from keel.propagate import evaluate

from .harness import admit, confirm_new_edges
from .systems import relation_for


def _relations(outcome) -> dict:
    return {
        item["target"]: relation_for(item["target"], item["answer"],
                                     outcome.boundary)
        for item in outcome.raw
    }


def _state_after(scenario, relations: list) -> dict:
    log, admission = admit(scenario.log, scenario.variant.document, relations,
                           "model:judge")
    if scenario.variant.confirmed:
        log = confirm_new_edges(log, admission)
    after = evaluate(ledger.replay(log))
    return {
        node: after.state_of(node) for node in after.nodes
        if scenario.before.state_of(node) != after.state_of(node)
    }


def _wrong(predicted: dict, truth: dict) -> set[str]:
    return {
        node for node in set(predicted) | set(truth)
        if predicted.get(node) != truth.get(node)
    }


def repair_cost(scenario, outcome) -> dict:
    truth = scenario.truth_changed
    wrong_before = _wrong(outcome.changed, truth)
    if outcome.system != "B":
        # Nothing intermediate exists to correct, so every wrong node is its own
        # edit and the next document starts from the same place.
        return {
            "corrections_required": len(wrong_before),
            "wrong_nodes_before": len(wrong_before),
            "residual_wrong_nodes": 0,
            "nodes_per_correction": 1.0 if wrong_before else None,
            "correction_target": "final states, one node at a time",
        }

    said = _relations(outcome)
    wanted = {item.target: item for item in scenario.variant.truth}
    corrected, touched = [], 0
    for target in sorted(set(said) | set(wanted)):
        mine, theirs = said.get(target), wanted.get(target)
        if _same(mine, theirs):
            if mine is not None:
                corrected.append(mine)
            continue
        touched += 1
        if theirs is not None:
            corrected.append(theirs)
    residual = _wrong(_state_after(scenario, corrected), truth)
    return {
        "corrections_required": touched,
        "wrong_nodes_before": len(wrong_before),
        "residual_wrong_nodes": len(residual),
        "nodes_per_correction": (round(len(wrong_before) / touched, 3)
                                 if touched else None),
        "correction_target": "one relation, with its quoted sentence",
    }


def _same(mine, theirs) -> bool:
    """Two relations agree if they would propagate identically."""
    if mine is None or theirs is None:
        return mine is None and theirs is None
    counts = {"MODERATE", "STRONG"}
    return (mine.relation == theirs.relation
            and (mine.strength in counts) == (theirs.strength in counts))


def aggregate_repair(rows: list[dict]) -> dict:
    wrong = sum(r["repair"]["wrong_nodes_before"] for r in rows)
    corrections = sum(r["repair"]["corrections_required"] for r in rows)
    residual = sum(r["repair"]["residual_wrong_nodes"] for r in rows)
    return {
        "wrong_nodes": wrong,
        "corrections_required": corrections,
        "nodes_repaired_per_correction": (round(wrong / corrections, 3)
                                          if corrections else None),
        "residual_wrong_nodes_after_correction": residual,
        "rows_needing_no_correction": sum(
            1 for r in rows if r["repair"]["corrections_required"] == 0
        ),
    }
