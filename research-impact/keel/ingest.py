"""The boundary where a judgment becomes a fact the graph will act on.

Everything upstream of this module is allowed to be a language model. Nothing
downstream of it is. A proposal crosses only if it names a node that exists,
carries a strength and enough confidence, and quotes text that actually occurs
in the document it claims to quote. The last check is the cheap one and the
important one: a fabricated citation stops being a trust problem and becomes a
string that is either present or absent.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ledger import (
    CLAIM_ADDED,
    EDGE_PROPOSED,
    SOURCE_ADDED,
    Event,
    event,
)
from .model import (
    EVIDENCE_RELATIONS,
    EdgeStatus,
    Program,
    Relation,
    Source,
    Strength,
    claim_id,
    edge_id,
    normalize,
)
from .policy import MIN_CONFIDENCE


@dataclass(frozen=True, slots=True)
class Proposal:
    """The entire vocabulary a model is given: one relation to one node."""

    target: str
    relation: Relation
    strength: Strength | None
    confidence: float
    excerpt: str
    claim: str
    proposed_by: str


@dataclass(frozen=True, slots=True)
class Admission:
    events: tuple[Event, ...]
    admitted: tuple[dict, ...]
    refused: tuple[dict, ...]

    def as_dict(self) -> dict:
        return {
            "admitted": list(self.admitted),
            "refused": list(self.refused),
            "event_ids": [item.id for item in self.events],
        }


def ingest(
    program: Program, source: Source, proposals: list[Proposal], at: str = ""
) -> Admission:
    """Judge each proposal on its own. One bad proposal never sinks a batch."""
    stored = program.sources.get(source.id)
    if stored is not None and normalize(stored.text) != normalize(source.text):
        return Admission(
            (), (),
            tuple(_refusal(p, "source_text_conflict") for p in proposals),
        )
    events: list[Event] = []
    if stored is None:
        events.append(event(SOURCE_ADDED, _source_payload(source), at))
    admitted: list[dict] = []
    refused: list[dict] = []
    for proposal in proposals:
        reason = _refuse_because(program, source, proposal)
        if reason is not None:
            refused.append(_refusal(proposal, reason))
            continue
        events.extend(_admit(source, proposal, at))
        admitted.append(_record(proposal, source))
    return Admission(tuple(events), tuple(admitted), tuple(refused))


def _refuse_because(
    program: Program, source: Source, proposal: Proposal
) -> str | None:
    if proposal.relation not in EVIDENCE_RELATIONS:
        return "not_evidence"
    if proposal.target not in program.assumptions | program.hypotheses:
        return "unknown_target"
    if proposal.strength is None:
        return "strength_missing"
    if proposal.confidence < MIN_CONFIDENCE:
        return "below_confidence"
    if normalize(proposal.excerpt) not in normalize(source.text):
        return "excerpt_not_found"
    if _edge_of(proposal, source) in program.edges:
        return "already_present"
    return None


def _admit(source: Source, proposal: Proposal, at: str) -> list[Event]:
    identifier = claim_id(source.id, proposal.excerpt)
    claim_payload = {
        "source": source.id, "text": proposal.claim, "excerpt": proposal.excerpt,
    }
    edge_payload = {
        "id": _edge_of(proposal, source),
        "relation": str(proposal.relation),
        "source": identifier,
        "target": proposal.target,
        "status": str(EdgeStatus.PROPOSED),
        "strength": str(proposal.strength),
        "confidence": proposal.confidence,
        "created_by": proposal.proposed_by,
        "created_at": at,
    }
    return [
        event(CLAIM_ADDED, claim_payload, at),
        event(EDGE_PROPOSED, edge_payload, at),
    ]


def _edge_of(proposal: Proposal, source: Source) -> str:
    return edge_id(
        proposal.relation, claim_id(source.id, proposal.excerpt),
        proposal.target, proposal.excerpt,
    )


def _record(proposal: Proposal, source: Source) -> dict:
    return {
        "edge": _edge_of(proposal, source),
        "target": proposal.target,
        "relation": str(proposal.relation),
        "strength": str(proposal.strength),
        "confidence": proposal.confidence,
        "excerpt": proposal.excerpt,
        "source": source.id,
        "proposed_by": proposal.proposed_by,
    }


def _refusal(proposal: Proposal, reason: str) -> dict:
    return {
        "target": proposal.target,
        "relation": str(proposal.relation),
        "excerpt": proposal.excerpt,
        "proposed_by": proposal.proposed_by,
        "refused": reason,
    }


def _source_payload(source: Source) -> dict:
    return {
        "id": source.id, "title": source.title, "text": source.text,
        "kind": source.kind, "produced_by": source.produced_by,
    }


def proposals_from(raw: list[dict], proposed_by: str) -> list[Proposal]:
    """Parse what a judge returned. Unknown relations survive as UNRELATED.

    A model that answers with a word outside the vocabulary is not an exception
    to handle at every call site; it is a proposal that will be refused with a
    reason, like any other.
    """
    parsed = []
    for item in raw:
        relation = _relation(item.get("relation", ""))
        strength = _strength(item.get("strength"))
        parsed.append(
            Proposal(
                item.get("target", ""), relation, strength,
                float(item.get("confidence", 0.0)), item.get("excerpt", ""),
                item.get("claim", ""), item.get("proposed_by", proposed_by),
            )
        )
    return parsed


def _relation(value: str) -> Relation:
    try:
        return Relation(value)
    except ValueError:
        return Relation.UNRELATED


def _strength(value: str | None) -> Strength | None:
    try:
        return Strength(value)
    except ValueError:
        return None
