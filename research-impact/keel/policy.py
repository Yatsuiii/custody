"""State rules. Every node's state is a pure function of the edges into it.

This module is the whole reason the project exists, so it is deliberately dull:
no model call, no heuristics, no scoring, nothing that could return a different
answer tomorrow. A rule that cannot be written down here is a rule a researcher
cannot audit, and it does not belong in the system.

Each rule returns the state plus the minimal set of provenance ids that caused
it. That set is the justification, in the sense truth maintenance systems have
meant since Doyle: not an explanation written afterwards, but the actual reason,
recorded at the moment the state was computed.
"""

from __future__ import annotations

from .model import (
    STRENGTH_RANK,
    AssumptionState,
    Edge,
    EdgeStatus,
    ExperimentState,
    HypothesisState,
    Relation,
    Strength,
)

# Below this, a machine-proposed relation is not admitted and never propagates.
MIN_CONFIDENCE = 0.6

# Evidence weaker than this is recorded but does not move a state on its own.
MIN_STRENGTH = Strength.MODERATE

Justification = tuple[str, ...]


def counts(edges: list[Edge]) -> Justification:
    return tuple(sorted(e.id for e in edges))


def propagating(edges: list[Edge]) -> list[Edge]:
    """Evidence strong enough, confident enough, and not rejected by a human."""
    return [
        e for e in edges
        if e.status is not EdgeStatus.REJECTED
        and e.confidence >= MIN_CONFIDENCE
        and e.strength is not None
        and STRENGTH_RANK[e.strength] >= STRENGTH_RANK[MIN_STRENGTH]
    ]


def _decisive(edges: list[Edge]) -> list[Edge]:
    """Strong and human-confirmed. Only this can invalidate rather than contest."""
    return [
        e for e in edges
        if e.strength is Strength.STRONG and e.status is EdgeStatus.CONFIRMED
    ]


def assumption_state(evidence: list[Edge]) -> tuple[AssumptionState, Justification]:
    """Conflicting evidence contests an assumption; it does not settle it.

    An assumption that was believed for a reason keeps that reason on the record.
    So a new contradiction against standing support yields CONTESTED, and
    INVALIDATED is reserved for a strong, human-confirmed contradiction with no
    surviving support. This is the difference between "look at this again" and
    "this is false", and collapsing the two is how a system starts crying wolf.
    """
    active = propagating(evidence)
    against = [e for e in active if e.relation is Relation.CONTRADICTS]
    for_it = [e for e in active if e.relation is Relation.SUPPORTS]
    if against and for_it:
        return AssumptionState.CONTESTED, counts(against + for_it)
    if against:
        decisive = _decisive(against)
        if decisive:
            return AssumptionState.INVALIDATED, counts(decisive)
        return AssumptionState.CONTESTED, counts(against)
    if for_it:
        return AssumptionState.SUPPORTED, counts(for_it)
    return AssumptionState.UNKNOWN, ()


def hypothesis_state(
    depends_on: list[Edge],
    assumption_states: dict[str, AssumptionState],
    evidence: list[Edge],
    retirement: str | None,
) -> tuple[HypothesisState, Justification]:
    """RETIRED is reachable only through a human decision, by construction."""
    if retirement is not None:
        return HypothesisState.RETIRED, (retirement,)
    active = propagating(evidence)
    against = [e for e in active if e.relation is Relation.CONTRADICTS]
    broken = [d for d in depends_on
              if assumption_states[d.target] is AssumptionState.INVALIDATED]
    decisive = _decisive(against)
    if broken or decisive:
        return HypothesisState.WEAKENED, counts(broken + decisive)
    shaken = [d for d in depends_on
              if assumption_states[d.target] is AssumptionState.CONTESTED]
    if shaken or against:
        return HypothesisState.REQUIRES_REVIEW, counts(shaken + against)
    return HypothesisState.ACTIVE, ()


UNSAFE_TO_RELY_ON = frozenset(
    {AssumptionState.CONTESTED, AssumptionState.INVALIDATED}
)


def experiment_state(
    lifecycle: ExperimentState,
    requires: list[Edge],
    tests: list[Edge],
    establishes: list[Edge],
    assumption_states: dict[str, AssumptionState],
    hypothesis_states: dict[str, HypothesisState],
    settled_elsewhere: frozenset[str],
) -> tuple[ExperimentState, Justification]:
    """Only planned work is re-judged. Finished work keeps its history.

    A completed experiment cannot become stale: it already ran, and rewriting
    the past to look tidy is exactly what a research record must never do. What
    a new result changes is what is still worth doing.

    Precedence is stated rather than emergent: a broken premise beats a settled
    question, because an experiment whose premise no longer holds cannot answer
    anything, including the question that made it look redundant.
    """
    if lifecycle is not ExperimentState.PLANNED:
        return lifecycle, ()
    dead = [t for t in tests
            if hypothesis_states[t.target] is HypothesisState.RETIRED]
    if dead:
        return ExperimentState.INVALIDATED, counts(dead)
    broken = [r for r in requires
              if assumption_states[r.target] in UNSAFE_TO_RELY_ON]
    if broken:
        return ExperimentState.STALE, counts(broken)
    answered = [s for s in establishes if s.target in settled_elsewhere]
    if answered:
        return ExperimentState.REDUNDANT, counts(answered)
    return ExperimentState.PLANNED, ()
