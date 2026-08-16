"""Evaluate a program into a state, and explain any state by walking back.

Evaluation is a single pass in a fixed order: assumptions, then hypotheses, then
planned experiments. The order is not an optimisation, it is the guarantee. Each
layer reads only layers already computed, so there is no fixpoint to iterate, no
convergence to hope for, and no path by which two runs over the same events can
disagree.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    EVIDENCE_RELATIONS,
    AssumptionState,
    Edge,
    HypothesisState,
    Program,
    Relation,
    digest,
)
from .policy import (
    Justification,
    assumption_state,
    experiment_state,
    hypothesis_state,
    propagating,
)

DECIDED = frozenset({AssumptionState.SUPPORTED, AssumptionState.INVALIDATED})


@dataclass(frozen=True, slots=True)
class NodeState:
    kind: str
    state: str
    because: Justification


@dataclass(frozen=True, slots=True)
class GraphState:
    nodes: dict[str, NodeState]

    def state_of(self, node: str) -> str:
        return self.nodes[node].state

    def as_dict(self) -> dict[str, dict[str, object]]:
        return {
            node: {"kind": s.kind, "state": s.state, "because": list(s.because)}
            for node, s in sorted(self.nodes.items())
        }

    def digest(self) -> str:
        return digest(self.as_dict())


def _origin_experiment(program: Program, edge: Edge) -> str | None:
    """Which experiment produced this evidence, if any produced it at all."""
    claim = program.claims.get(edge.source)
    if claim is None:
        return None
    source = program.sources.get(claim.source)
    return None if source is None else source.produced_by


def _settled_elsewhere(
    program: Program,
    states: dict[str, AssumptionState],
    reasons: dict[str, Justification],
    experiment: str,
) -> frozenset[str]:
    """Assumptions already decided by evidence this experiment did not produce.

    The exclusion matters. Without it an experiment that answered its own
    question would mark itself redundant, which is both wrong and the kind of
    wrong that only shows up in a demo, on stage.
    """
    settled = set()
    for node, state in states.items():
        if state not in DECIDED:
            continue
        for edge_ref in reasons[node]:
            edge = program.edges.get(edge_ref)
            if edge is None:
                continue
            if _origin_experiment(program, edge) != experiment:
                settled.add(node)
                break
    return frozenset(settled)


def _retirement(program: Program, hypothesis: str) -> str | None:
    for decision in sorted(program.decisions.values(), key=lambda d: d.id):
        if decision.kind == "retire_hypothesis" and decision.target == hypothesis:
            return decision.id
    return None


def evaluate(program: Program) -> GraphState:
    nodes: dict[str, NodeState] = {}
    a_states: dict[str, AssumptionState] = {}
    a_reasons: dict[str, Justification] = {}
    for node in sorted(program.assumptions):
        state, because = assumption_state(
            program.edges_into(node, EVIDENCE_RELATIONS)
        )
        a_states[node], a_reasons[node] = state, because
        nodes[node] = NodeState("assumption", str(state), because)

    h_states: dict[str, HypothesisState] = {}
    for node in sorted(program.hypotheses):
        state, because = hypothesis_state(
            program.edges_from(node, Relation.DEPENDS_ON),
            a_states,
            program.edges_into(node, EVIDENCE_RELATIONS),
            _retirement(program, node),
        )
        h_states[node] = state
        nodes[node] = NodeState("hypothesis", str(state), because)

    for node in sorted(program.experiments):
        experiment = program.experiments[node]
        state, because = experiment_state(
            experiment.lifecycle,
            program.edges_from(node, Relation.REQUIRES),
            program.edges_from(node, Relation.TESTS),
            program.edges_from(node, Relation.ESTABLISHES),
            a_states,
            h_states,
            _settled_elsewhere(program, a_states, a_reasons, node),
        )
        nodes[node] = NodeState("experiment", str(state), because)
    return GraphState(nodes)


@dataclass(frozen=True, slots=True)
class Change:
    node: str
    kind: str
    was: str
    now: str
    because: Justification


def diff(before: GraphState, after: GraphState) -> tuple[list[Change], list[str]]:
    """Changed nodes and, just as importantly, the ones that held still."""
    changed: list[Change] = []
    unchanged: list[str] = []
    for node in sorted(after.nodes):
        new = after.nodes[node]
        old = before.nodes.get(node)
        if old is not None and old.state == new.state:
            unchanged.append(node)
            continue
        changed.append(
            Change(node, new.kind, "" if old is None else old.state,
                   new.state, new.because)
        )
    return changed, unchanged


def _evidence_step(program: Program, edge: Edge) -> dict[str, object]:
    claim = program.claims.get(edge.source)
    source = None if claim is None else program.sources.get(claim.source)
    return {
        "edge": edge.id,
        "relation": str(edge.relation),
        "from": edge.source,
        "to": edge.target,
        "asserted_by": edge.created_by,
        "status": str(edge.status),
        "confidence": edge.confidence,
        "strength": None if edge.strength is None else str(edge.strength),
        "claim": None if claim is None else claim.text,
        "excerpt": None if claim is None else claim.excerpt,
        "source": None if source is None else source.id,
        "source_title": None if source is None else source.title,
    }


def explain(
    program: Program, state: GraphState, node: str, seen: frozenset[str] = frozenset()
) -> dict[str, object]:
    """The chain a reader can follow from a state back to a quoted sentence.

    Rendered from the justifications recorded during evaluation, so the chain is
    the reason the state holds rather than a plausible story about it.
    """
    current = state.nodes[node]
    step: dict[str, object] = {
        "node": node,
        "kind": current.kind,
        "state": current.state,
        "because": [],
    }
    if node in seen:
        return step
    chain: list[dict[str, object]] = []
    for ref in current.because:
        edge = program.edges.get(ref)
        if edge is None:
            chain.append(_decision_step(program, ref))
            continue
        link = _evidence_step(program, edge)
        if edge.relation not in EVIDENCE_RELATIONS:
            link["then"] = explain(program, state, edge.target, seen | {node})
        chain.append(link)
    step["because"] = chain
    return step


def _decision_step(program: Program, ref: str) -> dict[str, object]:
    decision = program.decisions.get(ref)
    if decision is None:
        return {"unknown_justification": ref}
    return {
        "decision": decision.id,
        "kind": decision.kind,
        "actor": decision.actor,
        "target": decision.target,
        "rationale": decision.rationale,
    }


def open_evidence(program: Program, node: str) -> list[Edge]:
    """Admitted evidence into a node, for reports that show both sides."""
    return propagating(program.edges_into(node, EVIDENCE_RELATIONS))
