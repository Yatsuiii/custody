"""The typed research program: what a program is made of, and what it can hold.

Two rules shape everything here.

Dependencies are edges, never fields. An experiment does not carry a list of
assumptions it requires, because a dependency without provenance is an opinion:
every edge records who asserted it, from what excerpt, with what confidence.

Evidence always arrives as a claim from a source, whether that source is an
external paper or one of the program's own experiment results. The propagation
layer therefore has no special case for internal versus external evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum


class Relation(StrEnum):
    """Edge types. The first four are structural, the last three evidential."""

    DEPENDS_ON = "DEPENDS_ON"
    REQUIRES = "REQUIRES"
    TESTS = "TESTS"
    ESTABLISHES = "ESTABLISHES"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    UNRELATED = "UNRELATED"


EVIDENCE_RELATIONS = frozenset({Relation.SUPPORTS, Relation.CONTRADICTS})
STRUCTURAL_RELATIONS = frozenset(
    {Relation.DEPENDS_ON, Relation.REQUIRES, Relation.TESTS, Relation.ESTABLISHES}
)


class Strength(StrEnum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


STRENGTH_RANK = {Strength.WEAK: 1, Strength.MODERATE: 2, Strength.STRONG: 3}


class EdgeStatus(StrEnum):
    """Machine-proposed edges propagate; a human can confirm or reject one."""

    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class AssumptionState(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    INVALIDATED = "INVALIDATED"
    UNKNOWN = "UNKNOWN"


class HypothesisState(StrEnum):
    ACTIVE = "ACTIVE"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    WEAKENED = "WEAKENED"
    RETIRED = "RETIRED"


class ExperimentState(StrEnum):
    """PLANNED, RUNNING and COMPLETED are lifecycle; the rest are derived."""

    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    STALE = "STALE"
    REDUNDANT = "REDUNDANT"
    INVALIDATED = "INVALIDATED"


LIFECYCLE_STATES = frozenset(
    {ExperimentState.PLANNED, ExperimentState.RUNNING, ExperimentState.COMPLETED}
)


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    text: str


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: str
    text: str
    question: str


@dataclass(frozen=True, slots=True)
class Assumption:
    id: str
    text: str


@dataclass(frozen=True, slots=True)
class Experiment:
    id: str
    text: str
    lifecycle: ExperimentState
    cost_days: int = 0


@dataclass(frozen=True, slots=True)
class Source:
    """A document evidence can be quoted from: a paper, a result, a note.

    `produced_by` names the experiment that generated an internal result, and is
    what lets the engine tell "this question is already answered elsewhere" from
    "this question is answered by the very experiment being judged".
    """

    id: str
    title: str
    text: str
    kind: str = "paper"
    produced_by: str | None = None


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    source: str
    text: str
    excerpt: str


@dataclass(frozen=True, slots=True)
class Edge:
    id: str
    relation: Relation
    source: str
    target: str
    status: EdgeStatus = EdgeStatus.CONFIRMED
    strength: Strength | None = None
    confidence: float = 1.0
    created_by: str = "human"
    created_at: str = ""


@dataclass(frozen=True, slots=True)
class Decision:
    """A human act with downstream consequences. No model may author one."""

    id: str
    actor: str
    kind: str
    target: str
    rationale: str
    at: str = ""


@dataclass(frozen=True, slots=True)
class Program:
    questions: dict[str, Question] = field(default_factory=dict)
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    assumptions: dict[str, Assumption] = field(default_factory=dict)
    experiments: dict[str, Experiment] = field(default_factory=dict)
    sources: dict[str, Source] = field(default_factory=dict)
    claims: dict[str, Claim] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)

    def edges_from(self, node: str, relation: Relation) -> list[Edge]:
        return sorted(
            (e for e in self.edges.values()
             if e.source == node and e.relation is relation),
            key=lambda e: e.id,
        )

    def edges_into(self, node: str, relations: frozenset[Relation]) -> list[Edge]:
        return sorted(
            (e for e in self.edges.values()
             if e.target == node and e.relation in relations),
            key=lambda e: e.id,
        )


def canonical(payload: object) -> str:
    """One JSON spelling, so a digest means the same thing on every machine."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def digest(payload: object) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def edge_id(relation: Relation, source: str, target: str, excerpt: str = "") -> str:
    """Identity is what the edge asserts, so the same assertion is one edge.

    Ingesting the same evidence twice therefore cannot produce a second edge,
    which is where idempotency comes from rather than from a dedup table.
    """
    return "e-" + digest([str(relation), source, target, normalize(excerpt)])[:16]


def claim_id(source: str, excerpt: str) -> str:
    return "c-" + digest([source, normalize(excerpt)])[:16]


def normalize(text: str) -> str:
    """Whitespace and case are formatting, not content, for excerpt matching."""
    return " ".join(text.split()).casefold()
