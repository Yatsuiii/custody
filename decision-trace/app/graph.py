"""Deterministic active-decision resolution — BUILD_SCOPE.md §7.

This is code, not an LLM judgment call: the demo's correctness depends on
never presenting a reverted/superseded decision as current guidance, so
that one behavior has to be a graph traversal with a fixed, checkable
answer, not a probabilistic one.

Model: within a decision's lifecycle lineage (the decisions connected to it
by SUPERSEDES/REVERTS/REAFFIRMS edges), events are replayed in a stable
topological order. A lifecycle edge points from a later event to the earlier
event it changes, so the target is always replayed first even when a store
returns records in a different order. Timestamps and stable IDs order
independent events. This keeps the resolver deterministic without making
storage iteration order part of the domain model.
Ambiguity is flagged, not silently resolved, when a deactivating edge
targets something other than the currently active decision (e.g. two
decisions both claim to supersede the same predecessor) — BUILD_SCOPE.md
§16's safeguard against ambiguous chains.

Cycles are not a valid lifecycle history. They are retained for inspection
but resolve to an explicitly ambiguous result rather than a last-writer
guess.
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
    explanation: str = ""
    # Every lifecycle edge replayed to reach `active_id`, chronological order,
    # each as "{source_id} {relationship} {target_id}" — the structured form
    # of `explanation`, kept so callers (authority.py's proof object) can cite
    # individual transitions without reparsing a sentence.
    lifecycle_events: tuple[str, ...] = ()


class DecisionGraph:
    def __init__(self, decisions: list[Decision]):
        self.by_id: dict[str, Decision] = {d.id: d for d in decisions}
        self._undirected_lineage_edges: dict[str, set[str]] = {d.id: set() for d in decisions}
        # A lifecycle edge is encoded on the newer node and points at the
        # earlier node it changes. Replay needs the reverse dependency:
        # target first, source second.
        dependencies: dict[str, set[str]] = {d.id: set() for d in decisions}
        indegree: dict[str, int] = {d.id: 0 for d in decisions}
        for d in decisions:
            for target_id, rel in d.related_decisions:
                if rel.value in _LINEAGE_RELATIONSHIPS and target_id in self.by_id:
                    self._undirected_lineage_edges[d.id].add(target_id)
                    self._undirected_lineage_edges[target_id].add(d.id)

                    if d.id not in dependencies[target_id]:
                        dependencies[target_id].add(d.id)
                        indegree[d.id] += 1

        ready = sorted(
            (node_id for node_id, degree in indegree.items() if degree == 0),
            key=lambda node_id: self._sort_key(self.by_id[node_id]),
        )
        order: list[str] = []
        while ready:
            node_id = ready.pop(0)
            order.append(node_id)
            for successor_id in sorted(
                dependencies[node_id],
                key=lambda candidate: self._sort_key(self.by_id[candidate]),
            ):
                indegree[successor_id] -= 1
                if indegree[successor_id] == 0:
                    ready.append(successor_id)
                    ready.sort(
                        key=lambda candidate: self._sort_key(self.by_id[candidate])
                    )

        self._cyclic_ids = set(indegree) - set(order)
        # Preserve every record in a deterministic order for inspection even
        # when a cyclic component cannot be topologically sorted.
        order.extend(
            sorted(
                self._cyclic_ids,
                key=lambda node_id: self._sort_key(self.by_id[node_id]),
            )
        )
        self.order = order

    @staticmethod
    def _sort_key(decision: Decision) -> tuple[bool, str, str]:
        """Order independent events by timestamp, then stable ID.

        Missing timestamps sort after known timestamps. Lifecycle dependencies
        still dominate this key, which lets a revert with no timestamp follow
        the original decision it explicitly reverts.
        """
        return (
            decision.introduced_at is None,
            decision.introduced_at or "",
            decision.id,
        )

    def lineage(self, start_id: str) -> list[str]:
        """The connected component reachable from `start_id` via lifecycle
        edges only (SUPERSEDES/REVERTS/REAFFIRMS) — IMPLEMENTS/RECONSIDERS/
        DEPENDS_ON/RELATED_TO edges don't affect activity, so they don't
        pull unrelated decisions into this lineage. Returned in the
        deterministic lifecycle order."""
        seen = {start_id}
        stack = [start_id]
        while stack:
            cur = stack.pop()
            for neighbor in self._undirected_lineage_edges[cur]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        return [did for did in self.order if did in seen]


class _AmbiguousLineage(Exception):
    """Raised internally when a lifecycle edge deactivates something other
    than the currently active node — e.g. two decisions both claiming to
    supersede the same predecessor. Caught by `resolve_active` to build the
    ambiguous `ActiveResolution`; never escapes this module."""

    def __init__(self, target_id: str, events: list[str]):
        self.target_id = target_id
        self.events = events


def _replay_lineage(
    graph: DecisionGraph,
    lineage: list[str],
    deactivating_values: frozenset[str],
    reactivating_values: frozenset[str],
) -> tuple[str | None, list[str]]:
    """Replay lifecycle edges across `lineage` in order. Returns the final
    active id and every edge replayed, as "{source} {relationship} {target}"
    strings. Raises `_AmbiguousLineage` if two later decisions claim the
    same active predecessor."""
    active: str | None = None
    events: list[str] = []
    for node_id in lineage:
        node = graph.by_id[node_id]
        for target_id, rel in node.related_decisions:
            if target_id not in graph.by_id:
                continue
            if rel.value in deactivating_values:
                events.append(f"{node_id} {rel.value} {target_id}")
                if active is None or target_id == active:
                    active = node_id
                else:
                    raise _AmbiguousLineage(target_id, events)
            elif rel.value in reactivating_values:
                events.append(f"{node_id} {rel.value} {target_id}")
                active = target_id
        if active is None:
            active = node_id  # earliest node in the lineage establishes the baseline
    return active, events


def resolve_active(graph: DecisionGraph, decision_id: str) -> ActiveResolution:
    if decision_id not in graph.by_id:
        raise KeyError(f"unknown decision id: {decision_id}")

    deactivating_values = frozenset(r.value for r in DEACTIVATING_RELATIONSHIPS)
    reactivating_values = frozenset(r.value for r in REACTIVATING_RELATIONSHIPS)

    lineage = graph.lineage(decision_id)
    if graph._cyclic_ids.intersection(lineage):
        return ActiveResolution(
            active_id=None,
            history=lineage,
            ambiguous=True,
            explanation=(
                "Lifecycle is ambiguous because the lineage contains a cycle: "
                + " -> ".join(lineage)
            ),
        )

    try:
        active, lifecycle_events = _replay_lineage(
            graph, lineage, deactivating_values, reactivating_values
        )
    except _AmbiguousLineage as exc:
        return ActiveResolution(
            active_id=None,
            history=lineage,
            ambiguous=True,
            explanation=(
                "Lifecycle is ambiguous because multiple later decisions "
                f"claim the active predecessor {exc.target_id}: "
                + "; ".join(exc.events)
            ),
            lifecycle_events=tuple(exc.events),
        )

    if lifecycle_events:
        explanation = (
            f"{active} is active after replaying: " + "; ".join(lifecycle_events)
        )
    else:
        explanation = (
            f"{active} is the only governing decision in this lineage; "
            "no supersession, revert, or reaffirmation edge changes it."
        )
    return ActiveResolution(
        active_id=active,
        history=lineage,
        ambiguous=False,
        explanation=explanation,
        lifecycle_events=tuple(lifecycle_events),
    )
