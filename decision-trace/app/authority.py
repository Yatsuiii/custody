"""Deterministic organizational-authority resolution.

``resolve_active`` answers activity inside one lifecycle lineage.  This module
owns the higher-level question callers actually ask: which eligible decision
governs one authority scope when several lineages, implementation records, and
terminal proposals coexist.  Generation is intentionally outside this module;
the returned ID is the fact an explanation layer must report.

Semantics are specified independently of this implementation in
AUTHORITY_SEMANTICS.md; this module exists to match that document, not the
other way around. The one invariant that matters most: authority in a scope
the caller did not ask about must never change the answer for the scope it
did ask about (parallel-scope independence). Every code path below filters
to the exact requested scope before it decides anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from graph import ActiveResolution, DecisionGraph, resolve_active
from models import Decision, DecisionStatus, RelationshipType

# Why a scoped candidate did not govern. Kept as plain strings (not an Enum)
# because the proof is meant to be trivially JSON-serializable for the UI,
# Gemini's explanation layer, and any future persisted record.
PROPOSED_NOT_ACCEPTED = "PROPOSED_NOT_ACCEPTED"
SUPERSEDED = "SUPERSEDED"
REVERTED = "REVERTED"
WITHDRAWN = "WITHDRAWN"
IMPLEMENTATION_NOT_POLICY_AUTHORITY = "IMPLEMENTATION_NOT_POLICY_AUTHORITY"
AMBIGUOUS_LINEAGE = "AMBIGUOUS_LINEAGE"
CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
PARTIAL_ACCEPTANCE = "PARTIAL_ACCEPTANCE"


@dataclass(frozen=True)
class AuthorityResolution:
    """Backward-compatible summary view. New callers should prefer
    `AuthorityProof` (see `resolve_authority_with_proof`); this shape is kept
    so existing callers of `resolve_authority` do not need to change."""

    state: str
    governing_decision_id: str | None
    evidence_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class CandidateAssessment:
    """What the resolver concluded about one exact-scope decision."""

    decision_id: str
    lifecycle_status: str
    role: str  # "policy" | "implementation"
    eligible_to_govern: bool
    active_resolution: bool  # True only for the decision that ended up governing
    exclusion_reason: str | None
    # Other decision ids that explain this assessment — e.g. the id that
    # superseded this one, or the id(s) it conflicts with. Empty when the
    # assessment needs no cross-reference (e.g. a bare PROPOSED record).
    witness_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityProof:
    """The complete, machine-readable answer to "what governs this scope,
    and why didn't the alternatives?" Deterministic: two calls with the same
    decisions (in any order) and the same scope produce structurally
    identical proofs — candidate lists are always sorted by decision id."""

    requested_scope: str
    authority_state: str
    governing_decision_id: str | None
    # Lifecycle edges ("{source} {relationship} {target}") that establish
    # the governing decision as active, in replay order. Empty when there is
    # no governing decision.
    governing_witnesses: tuple[str, ...]
    # Every lifecycle edge replayed across every exact-scope policy lineage
    # considered, including edges that only concern excluded candidates.
    transition_witnesses: tuple[str, ...]
    considered_candidates: tuple[CandidateAssessment, ...]
    excluded_candidates: tuple[CandidateAssessment, ...]
    # Only populated for UNRESOLVED: the specific in-scope facts that
    # prevented a unique conclusion (conflicting active ids, ambiguous
    # lineage explanations, partial-acceptance flags).
    ambiguity_witnesses: tuple[str, ...]
    explanation: str


def _is_rollback(decision: Decision) -> bool:
    return any(rel == RelationshipType.REVERTS for _, rel in decision.related_decisions)


def _can_govern(decision: Decision) -> bool:
    if decision.current_status in {DecisionStatus.PROPOSED, DecisionStatus.SUPERSEDED}:
        return False
    if decision.current_status == DecisionStatus.REVERTED:
        # A rollback decision is itself eligible; a withdrawn/rejected record
        # has the same legacy status but no outgoing REVERTS authority event.
        return _is_rollback(decision)
    return True


def _status_exclusion_reason(decision: Decision) -> str | None:
    """Why a status-ineligible decision cannot govern. None if it is
    status-eligible (it may still be excluded later for role or conflict)."""
    if decision.current_status == DecisionStatus.PROPOSED:
        return PROPOSED_NOT_ACCEPTED
    if decision.current_status == DecisionStatus.SUPERSEDED:
        return SUPERSEDED
    if decision.current_status == DecisionStatus.REVERTED and not _is_rollback(decision):
        return WITHDRAWN
    return None


def _implementation_lineage_ids(decisions: list[Decision], policy_ids: set[str]) -> set[str]:
    """Decision ids that are implementation, not policy authority: an
    explicit IMPLEMENTS edge into an eligible in-scope policy id, plus every
    id in that record's own lifecycle lineage (a superseded implementation
    record is still implementation). Lineage is walked over the full
    decision set because the structural edges — not each record's own
    scope tags — are what make something implementation; this does not
    leak cross-scope *authority* into the answer, it only classifies role."""
    graph = DecisionGraph(decisions)
    implementation_roots = {
        decision.id
        for decision in decisions
        if any(rel == RelationshipType.IMPLEMENTS and target in policy_ids
               for target, rel in decision.related_decisions)
    }
    excluded: set[str] = set()
    for root in implementation_roots:
        excluded.update(graph.lineage(root))
    return excluded


def _edges_targeting(events: tuple[str, ...], target_id: str) -> tuple[str, ...]:
    return tuple(e for e in events if e.split(" ", 2)[2] == target_id)


def _source_of_edge(event: str) -> str:
    return event.split(" ", 2)[0]


def _build_no_governing(requested_scope: str, explanation: str) -> AuthorityProof:
    return AuthorityProof(
        requested_scope=requested_scope,
        authority_state="NO_GOVERNING_DECISION",
        governing_decision_id=None,
        governing_witnesses=(),
        transition_witnesses=(),
        considered_candidates=(),
        excluded_candidates=(),
        ambiguity_witnesses=(),
        explanation=explanation,
    )


def _assess_status_excluded(scoped: list[Decision], excluded_impl_ids: set[str]) -> list[CandidateAssessment]:
    """Assessments for scoped decisions excluded before lineage replay:
    status-ineligible (proposed/superseded/withdrawn) or implementation."""
    assessments = []
    for d in scoped:
        if d.id in excluded_impl_ids:
            assessments.append(CandidateAssessment(
                decision_id=d.id, lifecycle_status=d.current_status.value,
                role="implementation", eligible_to_govern=_can_govern(d),
                active_resolution=False,
                exclusion_reason=IMPLEMENTATION_NOT_POLICY_AUTHORITY,
                witness_ids=(),
            ))
            continue
        reason = _status_exclusion_reason(d)
        if reason is not None:
            assessments.append(CandidateAssessment(
                decision_id=d.id, lifecycle_status=d.current_status.value,
                role="policy", eligible_to_govern=False,
                active_resolution=False, exclusion_reason=reason, witness_ids=(),
            ))
    return assessments


def _replay_authority_records(
    authority_records: list[Decision],
) -> tuple[dict[str, ActiveResolution], set[str], list[str]]:
    """Resolve each scoped policy record against its own lineage. Returns
    (resolution per decision id, active ids reached, ambiguity explanations)."""
    graph = DecisionGraph(authority_records)
    resolutions: dict[str, ActiveResolution] = {}
    active_ids: set[str] = set()
    ambiguous: list[str] = []
    for decision in authority_records:
        resolution = resolve_active(graph, decision.id)
        resolutions[decision.id] = resolution
        if resolution.ambiguous:
            ambiguous.append(resolution.explanation)
        elif resolution.active_id:
            active_ids.add(resolution.active_id)
    return resolutions, active_ids, ambiguous


def _governing_proof(
    requested_scope: str,
    governing: str,
    authority_records: list[Decision],
    resolutions: dict[str, ActiveResolution],
    excluded_assessments: list[CandidateAssessment],
) -> AuthorityProof:
    winner_resolution = resolutions[governing]
    considered: list[CandidateAssessment] = []
    for d in authority_records:
        events = resolutions[d.id].lifecycle_events
        if d.id == governing:
            considered.append(CandidateAssessment(
                decision_id=d.id, lifecycle_status=d.current_status.value,
                role="policy", eligible_to_govern=True, active_resolution=True,
                exclusion_reason=None, witness_ids=(),
            ))
            continue
        deactivating = _edges_targeting(events, d.id)
        witness_ids = tuple(sorted({_source_of_edge(e) for e in deactivating}))
        reason = SUPERSEDED
        if any(f" {RelationshipType.REVERTS.value} " in e for e in deactivating):
            reason = REVERTED
        considered.append(CandidateAssessment(
            decision_id=d.id, lifecycle_status=d.current_status.value,
            role="policy", eligible_to_govern=True, active_resolution=False,
            exclusion_reason=reason, witness_ids=witness_ids,
        ))
    considered.sort(key=lambda c: c.decision_id)
    excluded = sorted(
        [c for c in considered if c.decision_id != governing] + excluded_assessments,
        key=lambda c: c.decision_id,
    )
    all_events = sorted({e for r in resolutions.values() for e in r.lifecycle_events})
    return AuthorityProof(
        requested_scope=requested_scope,
        authority_state="GOVERNING",
        governing_decision_id=governing,
        governing_witnesses=winner_resolution.lifecycle_events,
        transition_witnesses=tuple(all_events),
        considered_candidates=tuple(considered) + tuple(sorted(excluded_assessments, key=lambda c: c.decision_id)),
        excluded_candidates=tuple(excluded),
        ambiguity_witnesses=(),
        explanation=(
            f"{governing} is the sole eligible active decision in scope {requested_scope!r}."
        ),
    )


def resolve_authority_with_proof(decisions: list[Decision], authority_scope: str) -> AuthorityProof:
    """Resolve one explicit authority scope and return the full proof: the
    state, the governing decision if any, every scoped candidate considered,
    why each excluded candidate lost, and the lifecycle edges that establish
    the winner. See AUTHORITY_SEMANTICS.md for the state definitions this
    implements."""
    scoped = sorted(
        (d for d in decisions if authority_scope in d.related_components),
        key=lambda d: d.id,
    )
    if not scoped:
        return _build_no_governing(
            authority_scope, f"No decision has scope {authority_scope!r}."
        )

    eligible_scoped = [d for d in scoped if _can_govern(d)]
    scoped_ids = {d.id for d in eligible_scoped}
    excluded_impl_ids = _implementation_lineage_ids(decisions, scoped_ids)
    excluded_assessments = _assess_status_excluded(scoped, excluded_impl_ids)
    authority_records = [
        d for d in eligible_scoped if d.id not in excluded_impl_ids
    ]

    if not authority_records:
        # Absence, not conflict: every exact-scope record was either
        # status-ineligible or implementation-only. Unrelated scopes are
        # never consulted here — this is the scope-locality fix.
        return AuthorityProof(
            requested_scope=authority_scope,
            authority_state="NO_GOVERNING_DECISION",
            governing_decision_id=None,
            governing_witnesses=(),
            transition_witnesses=(),
            considered_candidates=tuple(sorted(excluded_assessments, key=lambda c: c.decision_id)),
            excluded_candidates=tuple(sorted(excluded_assessments, key=lambda c: c.decision_id)),
            ambiguity_witnesses=(),
            explanation=(
                f"No eligible policy authority exists in scope {authority_scope!r}: "
                "every visible record there is a proposal, a superseded/withdrawn "
                "record, or implementation only."
            ),
        )

    resolutions, active_ids, ambiguous = _replay_authority_records(authority_records)

    if ambiguous or len(active_ids) != 1:
        detail = "; ".join(ambiguous) if ambiguous else f"eligible active ids: {sorted(active_ids)}"
        considered = sorted(
            [
                CandidateAssessment(
                    decision_id=d.id, lifecycle_status=d.current_status.value,
                    role="policy", eligible_to_govern=True, active_resolution=False,
                    exclusion_reason=(AMBIGUOUS_LINEAGE if ambiguous else CONFLICTING_EVIDENCE),
                    witness_ids=tuple(sorted(active_ids - {d.id})),
                )
                for d in authority_records
            ] + excluded_assessments,
            key=lambda c: c.decision_id,
        )
        return AuthorityProof(
            requested_scope=authority_scope,
            authority_state="UNRESOLVED",
            governing_decision_id=None,
            governing_witnesses=(),
            transition_witnesses=tuple(sorted({e for r in resolutions.values() for e in r.lifecycle_events})),
            considered_candidates=tuple(considered),
            excluded_candidates=tuple(considered),
            ambiguity_witnesses=tuple(sorted(ambiguous)) if ambiguous else (f"eligible active ids: {sorted(active_ids)}",),
            explanation="Authority cannot be reduced to one governing decision: " + detail,
        )

    governing = next(iter(active_ids))
    winner = next(d for d in authority_records if d.id == governing)
    if winner.partial_acceptance:
        considered = sorted(
            [
                CandidateAssessment(
                    decision_id=d.id, lifecycle_status=d.current_status.value,
                    role="policy", eligible_to_govern=True,
                    active_resolution=(d.id == governing),
                    exclusion_reason=PARTIAL_ACCEPTANCE, witness_ids=(),
                )
                for d in authority_records
            ] + excluded_assessments,
            key=lambda c: c.decision_id,
        )
        return AuthorityProof(
            requested_scope=authority_scope,
            authority_state="UNRESOLVED",
            governing_decision_id=None,
            governing_witnesses=(),
            transition_witnesses=tuple(sorted({e for r in resolutions.values() for e in r.lifecycle_events})),
            considered_candidates=tuple(considered),
            excluded_candidates=tuple(considered),
            ambiguity_witnesses=(
                f"{governing} is marked partial_acceptance: its current status does "
                "not cover the full scope of the record, so it cannot be promoted "
                "to sole governing authority.",
            ),
            explanation=(
                f"{governing} would otherwise govern scope {authority_scope!r}, but its "
                "acceptance is explicitly partial; refusing to assert full authority."
            ),
        )

    return _governing_proof(authority_scope, governing, authority_records, resolutions, excluded_assessments)


def resolve_authority(decisions: list[Decision], authority_scope: str) -> AuthorityResolution:
    """Resolve one explicit authority scope without semantic or recency
    guesses. Thin summary view over `resolve_authority_with_proof`; kept for
    existing callers that only need the final state and winner."""
    proof = resolve_authority_with_proof(decisions, authority_scope)
    return AuthorityResolution(
        state=proof.authority_state,
        governing_decision_id=proof.governing_decision_id,
        evidence_ids=(proof.governing_decision_id,) if proof.governing_decision_id else (),
        explanation=proof.explanation,
    )
