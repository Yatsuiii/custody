"""Scoring. Pure functions over recorded outputs, so the judge can redo them.

Two of these metrics are asymmetric by construction and the write-up has to say
so rather than let a table imply a fair fight: System B cannot cite a wrong
justification, because its justifications are the engine's own, and it cannot
emit a state outside the vocabulary. Those columns measure whether the baseline
can do what the engine gets for free, which is the actual question.
"""

from __future__ import annotations

from itertools import combinations

from keel.model import AssumptionState, ExperimentState, HypothesisState

from .systems import relation_for

VOCABULARY = {
    "assumption": {str(s) for s in AssumptionState},
    "hypothesis": {str(s) for s in HypothesisState},
    "experiment": {str(s) for s in ExperimentState},
}
FROZEN_LIFECYCLE = {str(ExperimentState.COMPLETED), str(ExperimentState.RUNNING)}


def _kind(scenario, node: str) -> str | None:
    entry = scenario.before.nodes.get(node)
    return None if entry is None else entry.kind


def invalid_transitions(scenario, outcome) -> list[str]:
    """Outputs the rules forbid, whatever the affected set happens to be."""
    problems = []
    retired_by_human = {
        step["hypothesis"] for step in scenario.variant.prior
        if step["op"] == "retire"
    }
    for node, state in sorted(outcome.changed.items()):
        kind = _kind(scenario, node)
        if kind is None:
            problems.append(f"unknown_node:{node}")
            continue
        if state not in VOCABULARY[kind]:
            problems.append(f"impossible_state:{node}={state}")
        if state == str(HypothesisState.RETIRED) and node not in retired_by_human:
            problems.append(f"machine_retirement:{node}")
        if (kind == "experiment"
                and scenario.before.state_of(node) in FROZEN_LIFECYCLE):
            problems.append(f"finished_work_re_judged:{node}")
    return problems


def _cited(scenario, refs: list[str]) -> set[str]:
    """Sentence references become the edge id that sentence would create."""
    resolved = set()
    for ref in refs:
        if ref.startswith("S") and ref[1:].isdigit():
            edge = scenario.sentence_edges.get(int(ref[1:]))
            if edge is not None:
                resolved.add(edge)
        else:
            resolved.add(ref)
    return resolved


PROPAGATING = {"MODERATE", "STRONG"}


def edge_errors(scenario, outcome) -> list[str]:
    """Where System B's mistakes actually happen: one judgment at a time.

    A node-level count double-counts a single wrong judgment, because correct
    propagation faithfully carries a wrong edge to every true descendant. That
    amplification is real and belongs in the results, but so does the number a
    reviewer would act on: how many relations a human would have had to correct.
    Only System B has this number; the monolithic baseline never exposes one.
    """
    if outcome.system != "B":
        return []
    wanted = {
        item.target: (item.relation, item.strength in PROPAGATING)
        for item in scenario.variant.truth
    }
    said = {}
    for item in outcome.raw:
        relation = relation_for(item["target"], item["answer"], outcome.boundary)
        if relation is not None:
            said[relation.target] = (relation.relation,
                                     relation.strength in PROPAGATING)
    problems = []
    for target in sorted(set(wanted) | set(said)):
        truth_relation, truth_counts = wanted.get(target, ("UNRELATED", False))
        said_relation, said_counts = said.get(target, ("UNRELATED", False))
        if truth_relation != said_relation:
            problems.append(f"relation:{target}:{truth_relation}->{said_relation}")
        elif truth_counts != said_counts:
            direction = "inflated" if said_counts else "deflated"
            problems.append(f"strength_{direction}:{target}")
    return problems


def score_outcome(scenario, outcome) -> dict:
    predicted = set(outcome.changed)
    truth = set(scenario.truth_changed)
    hits = sorted(predicted & truth)
    exact = [n for n in hits
             if outcome.changed[n] == scenario.truth_changed[n]]
    untouched = set(scenario.before.nodes) - truth
    contains, precise = 0, 0
    for node in exact:
        cited = _cited(scenario, outcome.because.get(node, []))
        wanted = set(scenario.truth_because[node])
        contains += bool(cited & wanted)
        precise += cited == wanted
    return {
        "variant": scenario.variant.id,
        "system": outcome.system,
        "true_changed": sorted(truth),
        "predicted_changed": sorted(predicted),
        "tp": len(hits),
        "fp": len(predicted - truth),
        "fn": len(truth - predicted),
        "state_exact": len(exact),
        "untouched_total": len(untouched),
        "untouched_disturbed": len(predicted & untouched),
        "provenance_contains_cause": contains,
        "provenance_exact": precise,
        "invalid_transitions": invalid_transitions(scenario, outcome),
        "edge_errors": edge_errors(scenario, outcome),
        "edge_judgments": len(outcome.raw) if outcome.system == "B" else 0,
        "failures": list(outcome.failures),
        "prompt_tokens": sum(c["prompt_tokens"] for c in outcome.calls),
        "output_tokens": sum(c["output_tokens"] for c in outcome.calls),
        "seconds": round(sum(c["seconds"] for c in outcome.calls), 3),
        "calls": len(outcome.calls),
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 4)


def aggregate(rows: list[dict]) -> dict:
    """Micro-averaged: every node counts once, whatever variant it came from."""
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and precision + recall > 0:
        f1 = round(2 * precision * recall / (precision + recall), 4)
    disturbed = sum(r["untouched_disturbed"] for r in rows)
    untouched = sum(r["untouched_total"] for r in rows)
    return {
        "runs": len(rows),
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "state_exact_of_hits": _ratio(sum(r["state_exact"] for r in rows), tp),
        "unrelated_preserved": _ratio(untouched - disturbed, untouched),
        "unrelated_disturbed": disturbed,
        "provenance_contains_cause": _ratio(
            sum(r["provenance_contains_cause"] for r in rows),
            sum(r["state_exact"] for r in rows),
        ),
        "provenance_exact": _ratio(
            sum(r["provenance_exact"] for r in rows),
            sum(r["state_exact"] for r in rows),
        ),
        "invalid_transitions": sum(len(r["invalid_transitions"]) for r in rows),
        "edge_errors": sum(len(r["edge_errors"]) for r in rows),
        "edge_judgments": sum(r["edge_judgments"] for r in rows),
        "call_failures": sum(len(r["failures"]) for r in rows),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "output_tokens": sum(r["output_tokens"] for r in rows),
        "calls": sum(r["calls"] for r in rows),
        "seconds": round(sum(r["seconds"] for r in rows), 2),
    }


def stability(rows: list[dict]) -> dict:
    """How often two runs of the same system on the same variant agree."""
    by_variant: dict[str, list[frozenset]] = {}
    for row in rows:
        by_variant.setdefault(row["variant"], []).append(
            frozenset(row["predicted_changed"])
        )
    identical, pairs, jaccards = 0, 0, []
    for sets in by_variant.values():
        for left, right in combinations(sets, 2):
            pairs += 1
            identical += left == right
            union = left | right
            jaccards.append(1.0 if not union else len(left & right) / len(union))
    return {
        "pairs_compared": pairs,
        "identical_rate": _ratio(identical, pairs),
        "mean_jaccard": None if not jaccards
        else round(sum(jaccards) / len(jaccards), 4),
        "variants_never_stable": sorted(
            variant for variant, sets in by_variant.items()
            if len(set(sets)) > 1
        ),
    }
