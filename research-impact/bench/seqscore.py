"""Longitudinal metrics. Raw classification accuracy is not among them.

The question here is not whether a document was read correctly, it is whether
the program is still right after seven interacting changes and one human
correction. So these measure the things that only show up over a sequence:
whether a correction stays made, whether an unrelated document quietly breaks
something that was right, how long a mistake survives once it is in, and whether
the same evidence in a different order lands in the same place.
"""

from __future__ import annotations

import re

from .harness import base_program
from .sequence import ADJUDICATION, AMBIGUOUS, PROGRAM, steps

REFERENCE = re.compile(r"^(D\d+:S\d+|e-[0-9a-f]+|d-[\w-]+)$")


def _correction_step(order: str) -> int:
    return next(s.index for s in steps(order) if s.correction is not None)


def ambiguity_shadow(order: str) -> list[frozenset[str]]:
    """Nodes to leave out of the headline once an ambiguous document lands.

    The adjudication marks two document x assumption pairs as genuinely
    debatable. Scoring a system as wrong for taking one of those readings is the
    defect the third label exists to prevent, so from the step such a document
    arrives, that assumption is dropped from the headline, along with any node
    structurally attached to it, since its state moves with the assumption's.
    Applied identically to every system, and the dropped nodes are recorded in
    the artifact so a reader can see exactly what was excluded.
    """
    program = base_program(PROGRAM)
    debatable = {assumption for (_, assumption), entry in ADJUDICATION.items()
                 if entry[0] == AMBIGUOUS}
    attached = {
        edge["source"] for edge in program["edges"]
        if edge.get("target") in debatable
        and edge["relation"] in ("DEPENDS_ON", "REQUIRES", "ESTABLISHES")
    }
    shadowed, running = [], set()
    for step in steps(order):
        for (document, assumption), entry in sorted(ADJUDICATION.items()):
            if entry[0] == AMBIGUOUS and document == step.document.id:
                running |= {assumption} | attached
        shadowed.append(frozenset(running))
    return shadowed


def _visible(states: dict[str, str], hidden: frozenset[str]) -> dict[str, str]:
    return {k: v for k, v in states.items() if k not in hidden}


def accuracy(states: dict[str, str], truth: dict[str, str]) -> float:
    if not truth:
        return 0.0
    right = sum(1 for node, value in truth.items() if states.get(node) == value)
    return right / len(truth)


def wrong_nodes(states: dict[str, str], truth: dict[str, str]) -> set[str]:
    return {node for node, value in truth.items() if states.get(node) != value}


def score_trail(trail, truth, order: str) -> dict:
    """Everything measurable about one run of one system over one order."""
    hidden = ambiguity_shadow(order)
    per_step = [
        accuracy(_visible(s.states, h), _visible(t.states, h))
        for s, t, h in zip(trail, truth, hidden, strict=True)
    ]
    wrong = [
        wrong_nodes(_visible(s.states, h), _visible(t.states, h))
        for s, t, h in zip(trail, truth, hidden, strict=True)
    ]
    correction_at = _correction_step(order)
    after = range(correction_at, len(trail))
    # The registered criterion is whether the rejected relation stays rejected,
    # which is a property of each system's own record, not of a node's state.
    held = [trail[i].corrected_present is False for i in after]
    knows = trail[-1].corrected_present is not None
    return {
        "order": order,
        "excluded_from_headline": sorted(hidden[-1]),
        "per_step_accuracy": [round(value, 4) for value in per_step],
        "end_accuracy": round(per_step[-1], 4),
        "steps_exactly_right": sum(1 for value in per_step if value == 1.0),
        "steps": len(trail),
        "end_state": dict(trail[-1].states),
        "correction_persistence": (round(sum(held) / len(held), 4)
                                  if knows else None),
        "correction_breaks": [i for i, ok in zip(after, held, strict=True)
                              if not ok] if knows else [],
        "ambiguous_opinions": _ambiguous_opinions(trail, truth, hidden),
        "regressions": _regressions(trail, truth, wrong),
        "unnecessary_changes": _churn(trail, truth, hidden),
        "wrong_node_steps": sum(len(w) for w in wrong),
        "longest_error_survival": _survival(wrong),
        "auditable_justifications": _auditable(trail),
        "prompt_tokens": sum(c["prompt_tokens"] for s in trail for c in s.calls),
        "output_tokens": sum(c["output_tokens"] for s in trail for c in s.calls),
        "calls": sum(len(s.calls) for s in trail),
        "seconds": round(sum(c["seconds"] for s in trail for c in s.calls), 2),
    }


def _ambiguous_opinions(trail, truth, hidden) -> int:
    """How often a system took a position on a pair adjudicated debatable.

    Reported rather than scored, which is what the third label is for.
    """
    count = 0
    for index in range(len(trail)):
        for node in hidden[index]:
            if trail[index].states.get(node) != truth[index].states.get(node):
                count += 1
    return count


def _regressions(trail, truth, wrong) -> int:
    """A node that was right, then a later document made it wrong."""
    count = 0
    for index in range(1, len(trail)):
        count += len(wrong[index] - wrong[index - 1])
    return count


def _churn(trail, truth, hidden) -> int:
    """State transitions the system made where the truth made none."""
    count = 0
    for index in range(1, len(trail)):
        for node, value in _visible(trail[index].states, hidden[index]).items():
            moved = trail[index - 1].states.get(node) != value
            should = truth[index - 1].states.get(node) != truth[index].states[node]
            count += moved and not should
    return count


def _survival(wrong) -> int:
    """The longest run of consecutive steps any one node stayed wrong."""
    longest, running = 0, {}
    for step in wrong:
        for node in step:
            running[node] = running.get(node, 0) + 1
            longest = max(longest, running[node])
        for node in list(running):
            if node not in step:
                del running[node]
    return longest


def _auditable(trail) -> float | None:
    """Can a reader follow every stated reason back to something real?"""
    cited, valid = 0, 0
    for snapshot in trail:
        for refs in snapshot.because.values():
            for ref in refs:
                cited += 1
                valid += bool(REFERENCE.match(ref))
    return None if not cited else round(valid / cited, 4)


def aggregate_trails(rows: list[dict]) -> dict:
    """Mean over runs, plus the order-convergence count across end states."""
    ends = {}
    for row in rows:
        ends.setdefault(row["order"], set()).add(
            tuple(sorted(row["end_state"].items()))
        )
    converged = sum(1 for values in ends.values() if len(values) == 1)
    unique_ends = {tuple(sorted(row["end_state"].items())) for row in rows}
    return {
        "runs": len(rows),
        "mean_end_accuracy": _mean(r["end_accuracy"] for r in rows),
        "mean_step_accuracy": _mean(
            value for r in rows for value in r["per_step_accuracy"]
        ),
        "steps_exactly_right": sum(r["steps_exactly_right"] for r in rows),
        "steps_total": sum(r["steps"] for r in rows),
        "mean_correction_persistence": _mean(
            r["correction_persistence"] for r in rows
            if r["correction_persistence"] is not None
        ),
        "ambiguous_opinions": sum(r["ambiguous_opinions"] for r in rows),
        "regressions": sum(r["regressions"] for r in rows),
        "unnecessary_changes": sum(r["unnecessary_changes"] for r in rows),
        "wrong_node_steps": sum(r["wrong_node_steps"] for r in rows),
        "longest_error_survival": max(r["longest_error_survival"] for r in rows),
        "orders_self_consistent": f"{converged}/{len(ends)}",
        "orders_agreeing": orders_agreeing(rows),
        "distinct_end_states": len(unique_ends),
        "auditable_justifications": _mean(
            r["auditable_justifications"] for r in rows
            if r["auditable_justifications"] is not None
        ),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "calls": sum(r["calls"] for r in rows),
        "seconds": round(sum(r["seconds"] for r in rows), 1),
    }


def _mean(values) -> float | None:
    collected = list(values)
    return None if not collected else round(sum(collected) / len(collected), 4)


def orders_agreeing(rows: list[dict]) -> int:
    """The largest group of orders that ended in the same state.

    Three means every order converged. One means all three disagreed. Only the
    first run of each order counts, so this measures order sensitivity rather
    than run-to-run sampling noise.
    """
    first = {}
    for row in sorted(rows, key=lambda r: (r["order"], r.get("run", 1))):
        first.setdefault(row["order"], tuple(sorted(row["end_state"].items())))
    counts: dict[tuple, int] = {}
    for state in first.values():
        counts[state] = counts.get(state, 0) + 1
    return max(counts.values()) if counts else 0
