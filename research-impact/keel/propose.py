"""What the next experiment has to satisfy, and whether a candidate does.

The graph writes the specification and the model writes the method. That split
is the point: an experiment proposal is only interesting if it targets the
question that actually came open and stands on premises that actually still
hold, and both of those are computable. A proposal that fails the check is not
shown to anyone with a note about its confidence. It is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import AssumptionState, ExperimentState, HypothesisState, Program, Relation
from .policy import UNSAFE_TO_RELY_ON
from .propagate import GraphState

SUPERSEDED = frozenset({ExperimentState.STALE, ExperimentState.REDUNDANT})
SHAKEN = frozenset({HypothesisState.REQUIRES_REVIEW, HypothesisState.WEAKENED})


@dataclass(frozen=True, slots=True)
class Slots:
    """The computed shape of the replacement, before any prose exists."""

    targets: tuple[str, ...]
    discriminates: tuple[str, ...]
    may_rely_on: tuple[str, ...]
    supersedes: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "targets": list(self.targets),
            "discriminates": list(self.discriminates),
            "may_rely_on": list(self.may_rely_on),
            "supersedes": list(self.supersedes),
        }


@dataclass(frozen=True, slots=True)
class Candidate:
    """A proposed experiment: structure to check, plus the method to read."""

    id: str
    requires: tuple[str, ...]
    tests: tuple[str, ...]
    establishes: tuple[str, ...]
    method: str = ""


def slots(program: Program, state: GraphState) -> Slots:
    superseded = tuple(
        node for node in sorted(program.experiments)
        if state.state_of(node) in {str(s) for s in SUPERSEDED}
    )
    shaken = tuple(
        node for node in sorted(program.hypotheses)
        if state.state_of(node) in {str(s) for s in SHAKEN}
    )
    unsafe = {str(s) for s in UNSAFE_TO_RELY_ON}
    targets = sorted(
        {edge.target
         for node in superseded
         for edge in program.edges_from(node, Relation.REQUIRES)
         if state.state_of(edge.target) in unsafe}
        | {edge.target
           for node in shaken
           for edge in program.edges_from(node, Relation.DEPENDS_ON)
           if state.state_of(edge.target) in unsafe}
    )
    safe = sorted(
        {edge.target
         for node in superseded
         for edge in program.edges_from(node, Relation.REQUIRES)
         if state.state_of(edge.target) == str(AssumptionState.SUPPORTED)}
    )
    return Slots(tuple(targets), shaken, tuple(safe), superseded)


def check(
    program: Program, state: GraphState, spec: Slots, candidate: Candidate
) -> tuple[bool, list[str]]:
    """Reasons a candidate is refused, in the order a reader would ask them."""
    problems = _unknown_nodes(program, candidate)
    if problems:
        return False, problems
    if not set(candidate.establishes) & set(spec.targets):
        problems.append("does_not_target_an_open_question")
    unsafe = {str(s) for s in UNSAFE_TO_RELY_ON}
    for node in sorted(candidate.requires):
        if state.state_of(node) in unsafe:
            problems.append(f"relies_on_unsafe_assumption:{node}")
    live = [h for h in candidate.tests
            if state.state_of(h) != str(HypothesisState.RETIRED)]
    if not live:
        problems.append("tests_no_live_hypothesis")
    return not problems, problems


def _unknown_nodes(program: Program, candidate: Candidate) -> list[str]:
    problems = []
    for node in (*candidate.requires, *candidate.establishes):
        if node not in program.assumptions:
            problems.append(f"unknown_assumption:{node}")
    for node in candidate.tests:
        if node not in program.hypotheses:
            problems.append(f"unknown_hypothesis:{node}")
    return problems


def draft(spec: Slots, identifier: str, method: str = "") -> Candidate:
    """The smallest candidate the slots allow: settle the open question only."""
    return Candidate(
        identifier, spec.may_rely_on, spec.discriminates, spec.targets[:1], method
    )
