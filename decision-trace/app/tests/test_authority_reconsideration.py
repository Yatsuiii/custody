"""Phase 7 (product integration): the reconsideration demo moment,
strengthened by AuthorityProof. Offline, no network — pure store +
authority resolver, same discipline as test_authority_proof.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority_with_proof  # noqa: E402
from graph import DecisionGraph, resolve_active  # noqa: E402
from memory import propose_reconsideration  # noqa: E402
from models import Decision, DecisionStatus, RelationshipType  # noqa: E402
from store import JSONFileDecisionStore  # noqa: E402


def test_reconsideration_is_excluded_as_proposed_not_accepted(tmp_path):
    """Session brief Phase 7's exact scenario: a REVERTED decision governs
    a scope. A user submits a reconsideration. The new candidate is
    PROPOSED. The AuthorityProof still names the existing decision as
    governing and explicitly excludes the reconsideration with reason
    PROPOSED_NOT_ACCEPTED — the strongest demo moment, not just an
    absence of change."""
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")

    original = Decision(
        id="original", subject="Use approach A", current_status=DecisionStatus.IMPLEMENTED,
        related_components=["subsystem-x"],
    )
    rollback = Decision(
        id="rollback", subject="Revert approach A", current_status=DecisionStatus.REVERTED,
        related_components=["subsystem-x"],
        related_decisions=[("original", RelationshipType.REVERTS)],
    )
    store.save_many([original, rollback])

    # Governing truth before reconsideration: the rollback record.
    before = resolve_authority_with_proof(store.list_all(), "subsystem-x")
    assert before.authority_state == "GOVERNING"
    assert before.governing_decision_id == "rollback"

    candidate = propose_reconsideration(
        store, "rollback", "The perf regression that caused the revert is now fixed."
    )
    assert candidate.current_status == DecisionStatus.PROPOSED
    assert candidate.related_components == ["subsystem-x"]

    after = resolve_authority_with_proof(store.list_all(), "subsystem-x")

    # Governing truth is unchanged by the reconsideration.
    assert after.authority_state == "GOVERNING"
    assert after.governing_decision_id == "rollback"

    excluded = {c.decision_id: c for c in after.excluded_candidates}
    assert candidate.id in excluded
    assert excluded[candidate.id].exclusion_reason == "PROPOSED_NOT_ACCEPTED"

    # Cross-check against the lower-level lineage resolver too. RECONSIDERS
    # is deliberately not a lifecycle edge (memory.py's own docstring), so
    # resolve_active trivially reports the candidate active in its own
    # one-node lineage — that's expected graph.py behavior, not a bug. The
    # actual current-guidance guard is the PROPOSED status check
    # (retrieval.py's RetrievalCandidate.is_current, mirrored here), which
    # authority.py's own _can_govern already applies for the proof above.
    graph = DecisionGraph(store.list_all())
    resolution = resolve_active(graph, candidate.id)
    assert resolution.active_id == candidate.id  # own one-node lineage, as documented
    assert candidate.current_status == DecisionStatus.PROPOSED  # the guard that matters
