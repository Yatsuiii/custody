"""Deterministic active-decision resolution — BUILD_SCOPE.md §7.

This is code, not an LLM judgment call: the demo's correctness depends on
never presenting a reverted/superseded decision as current guidance, so
that one behavior has to be a graph traversal with a fixed, checkable
answer, not a probabilistic one.

Model: within a decision's lifecycle lineage (the decisions connected to it
by SUPERSEDES/REVERTS/REAFFIRMS edges), events are replayed in the order
decisions are passed into `DecisionGraph` — a deterministic linear replay
rather than a general graph algorithm, which is enough for the
supersession/revert/reaffirm chains this product needs to represent.
Ambiguity is flagged, not silently resolved, when a deactivating edge
targets something other than the currently active decision (e.g. two
decisions both claim to supersede the same predecessor) — BUILD_SCOPE.md
§16's safeguard against ambiguous chains.

Stage 1 assumes callers pass decisions in roughly chronological order (the
ingestion pipeline discovers artifacts close to time order already); a
later stage can re-sort by `introduced_at` before construction if that
assumption ever breaks in practice.
"""

from __future__ import annotations

from dataclasses import dataclass

from models import DEACTIVATING_RELATIONSHIPS, REACTIVATING_RELATIONSHIPS, Decision

_LINEAGE_RELATIONSHIPS = frozenset(
    r.value for r in DEACTIVATING_RELATIONSHIPS | REACTIVATING_RELATIONSHIPS
)


@dataclass
class ActiveResolution:
    active_id: str | None
    history: list[str]  # decision ids in the lineage, chronological order
    ambiguous: bool = False


class DecisionGraph:
    def __init__(self, decisions: list[Decision]):
        self.order: list[str] = [d.id for d in decisions]
        self.by_id: dict[str, Decision] = {d.id: d for d in decisions}
        self._undirected_lineage_edges: dict[str, set[str]] = {d.id: set() for d in decisions}
        for d in decisions:
            for target_id, rel in d.related_decisions:
                if rel.value in _LINEAGE_RELATIONSHIPS and target_id in self.by_id:
                    self._undirected_lineage_edges[d.id].add(target_id)
                    self._undirected_lineage_edges[target_id].add(d.id)

    def lineage(self, start_id: str) -> list[str]:
        """The connected component reachable from `start_id` via lifecycle
        edges only (SUPERSEDES/REVERTS/REAFFIRMS) — IMPLEMENTS/RECONSIDERS/
        DEPENDS_ON/RELATED_TO edges don't affect activity, so they don't
        pull unrelated decisions into this lineage. Returned in the
        original chronological (input) order."""
        seen = {start_id}
        stack = [start_id]
        while stack:
            cur = stack.pop()
            for neighbor in self._undirected_lineage_edges[cur]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        return [did for did in self.order if did in seen]


def resolve_active(graph: DecisionGraph, decision_id: str) -> ActiveResolution:
    if decision_id not in graph.by_id:
        raise KeyError(f"unknown decision id: {decision_id}")

    deactivating_values = frozenset(r.value for r in DEACTIVATING_RELATIONSHIPS)
    reactivating_values = frozenset(r.value for r in REACTIVATING_RELATIONSHIPS)

    lineage = graph.lineage(decision_id)
    active: str | None = None

    for node_id in lineage:
        node = graph.by_id[node_id]
        for target_id, rel in node.related_decisions:
            if target_id not in graph.by_id:
                continue
            if rel.value in deactivating_values:
                if active is None or target_id == active:
                    active = node_id
                else:
                    # This node claims to deactivate something that isn't
                    # currently active — e.g. two decisions both claiming
                    # to supersede the same predecessor. Don't guess.
                    return ActiveResolution(active_id=None, history=lineage, ambiguous=True)
            elif rel.value in reactivating_values:
                active = target_id
        if active is None:
            active = node_id  # earliest node in the lineage establishes the baseline

    return ActiveResolution(active_id=active, history=lineage, ambiguous=False)
