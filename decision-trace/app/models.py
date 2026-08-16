"""Decision domain model — BUILD_SCOPE.md §6.

The one rule that matters most here: a `Decision`'s `rationale` and
`rejected_alternatives` are claims, and every claim this product makes must
trace to a verbatim `Evidence.quote` — never an invented summary. That
discipline already exists in the falsifier's `mine_decisions.pick_quote()`
(reject rather than fabricate); this is the same rule expressed as a type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DecisionStatus(Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    IMPLEMENTED = "IMPLEMENTED"
    REVERTED = "REVERTED"
    SUPERSEDED = "SUPERSEDED"
    REAFFIRMED = "REAFFIRMED"


class RelationshipType(Enum):
    IMPLEMENTS = "IMPLEMENTS"
    SUPERSEDES = "SUPERSEDES"
    REVERTS = "REVERTS"
    RECONSIDERS = "RECONSIDERS"
    REAFFIRMS = "REAFFIRMS"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"


# Edge types whose *target* becomes inactive when the edge exists.
DEACTIVATING_RELATIONSHIPS = frozenset({
    RelationshipType.SUPERSEDES,
    RelationshipType.REVERTS,
})

# Edge types whose *target* becomes active again, overriding a prior
# deactivation — e.g. a later REAFFIRMS edge reviving a reverted decision.
REACTIVATING_RELATIONSHIPS = frozenset({RelationshipType.REAFFIRMS})


@dataclass(frozen=True)
class Evidence:
    type: str  # "pr" | "issue" | "proposal" | "revert_pr"
    url: str
    quote: str  # must be a verbatim excerpt of the source, never invented


@dataclass
class Decision:
    id: str
    subject: str
    current_status: DecisionStatus
    context: str | None = None
    chosen_approach: str | None = None
    rejected_alternatives: list[str] = field(default_factory=list)
    rationale: str | None = None
    constraints: list[str] = field(default_factory=list)
    introduced_at: str | None = None  # ISO timestamp
    superseded_at: str | None = None  # ISO timestamp
    evidence: list[Evidence] = field(default_factory=list)
    related_components: list[str] = field(default_factory=list)
    # Outgoing edges from this decision: (target_decision_id, relationship).
    related_decisions: list[tuple[str, RelationshipType]] = field(default_factory=list)
