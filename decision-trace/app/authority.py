"""Deterministic organizational-authority resolution.

``resolve_active`` answers activity inside one lifecycle lineage.  This module
owns the higher-level question callers actually ask: which eligible decision
governs one authority scope when several lineages, implementation records, and
terminal proposals coexist.  Generation is intentionally outside this module;
the returned ID is the fact an explanation layer must report.
"""

from __future__ import annotations

from dataclasses import dataclass

from graph import DecisionGraph, resolve_active
from models import Decision, DecisionStatus, RelationshipType


@dataclass(frozen=True)
class AuthorityResolution:
    state: str
    governing_decision_id: str | None
    evidence_ids: tuple[str, ...]
    explanation: str


def _can_govern(decision: Decision) -> bool:
    if decision.current_status in {DecisionStatus.PROPOSED, DecisionStatus.SUPERSEDED}:
        return False
    if decision.current_status == DecisionStatus.REVERTED:
        # A rollback decision is itself eligible; a withdrawn/rejected record
        # has the same legacy status but no outgoing REVERTS authority event.
        return any(rel == RelationshipType.REVERTS
                   for _, rel in decision.related_decisions)
    return True


def _implementation_lineage_ids(decisions: list[Decision], policy_ids: set[str]) -> set[str]:
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


def resolve_authority(decisions: list[Decision], authority_scope: str) -> AuthorityResolution:
    """Resolve one explicit authority scope without semantic or recency guesses."""
    scoped = [d for d in decisions if authority_scope in d.related_components]
    eligible_scoped = [d for d in scoped if _can_govern(d)]
    if not eligible_scoped:
        eligible_any = [d for d in decisions if _can_govern(d)]
        if not eligible_any:
            return AuthorityResolution(
                "NO_GOVERNING_DECISION", None, (),
                "No visible accepted or implemented decision is eligible to govern.",
            )
        return AuthorityResolution(
            "UNRESOLVED", None, (),
            "Visible authority exists, but none has the requested explicit scope; refusing a semantic guess.",
        )

    scoped_ids = {d.id for d in eligible_scoped}
    excluded = _implementation_lineage_ids(decisions, scoped_ids)
    authority_records = [d for d in eligible_scoped if d.id not in excluded]
    if not authority_records:
        return AuthorityResolution(
            "UNRESOLVED", None, (),
            "Only implementation lineage records matched the scope; no policy authority was selected.",
        )

    graph = DecisionGraph(authority_records)
    active_ids: set[str] = set()
    ambiguous = []
    for decision in authority_records:
        resolution = resolve_active(graph, decision.id)
        if resolution.ambiguous:
            ambiguous.append(resolution.explanation)
        elif resolution.active_id:
            active_ids.add(resolution.active_id)
    if ambiguous or len(active_ids) != 1:
        detail = "; ".join(ambiguous) if ambiguous else f"eligible active IDs: {sorted(active_ids)}"
        return AuthorityResolution(
            "UNRESOLVED", None, (),
            "Authority cannot be reduced to one governing decision: " + detail,
        )
    governing = next(iter(active_ids))
    return AuthorityResolution(
        "GOVERNING", governing, (governing,),
        f"{governing} is the sole eligible active decision in scope {authority_scope!r}.",
    )
