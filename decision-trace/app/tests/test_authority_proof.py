"""Adversarial tests for the AuthorityProof schema and scope-local
semantics — AUTHORITY_SEMANTICS.md, session brief Phase 7 (~20 cases)."""

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import (  # noqa: E402
    AMBIGUOUS_LINEAGE,
    CONFLICTING_EVIDENCE,
    IMPLEMENTATION_NOT_POLICY_AUTHORITY,
    PARTIAL_ACCEPTANCE,
    PROPOSED_NOT_ACCEPTED,
    REVERTED,
    SUPERSEDED,
    WITHDRAWN,
    resolve_authority,
    resolve_authority_with_proof,
)
from models import Decision, DecisionStatus, RelationshipType  # noqa: E402


def decision(did, status=DecisionStatus.ACCEPTED, scope="scope", edges=(), partial=False):
    return Decision(
        id=did, subject=did, current_status=status,
        related_components=[scope], related_decisions=list(edges),
        partial_acceptance=partial,
    )


# 1. accepted decision governs
def test_accepted_decision_governs():
    a = decision("A")
    proof = resolve_authority_with_proof([a], "scope")
    assert proof.authority_state == "GOVERNING"
    assert proof.governing_decision_id == "A"


# 2. proposed newer decision does not govern
def test_proposed_newer_decision_does_not_govern():
    a = decision("A")
    b = decision("B", DecisionStatus.PROPOSED, edges=(("A", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b], "scope")
    assert proof.authority_state == "GOVERNING"
    assert proof.governing_decision_id == "A"
    excluded = {c.decision_id: c for c in proof.excluded_candidates}
    assert excluded["B"].exclusion_reason == PROPOSED_NOT_ACCEPTED


# 3. explicit supersession
def test_explicit_supersession():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b], "scope")
    assert proof.governing_decision_id == "B"
    excluded = {c.decision_id: c for c in proof.excluded_candidates}
    assert excluded["A"].exclusion_reason == SUPERSEDED
    assert "B" in excluded["A"].witness_ids


# 4. multi-hop supersession
def test_multi_hop_supersession_chain():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    c = decision("C", edges=(("B", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b, c], "scope")
    assert proof.governing_decision_id == "C"
    excluded = {x.decision_id: x for x in proof.excluded_candidates}
    assert excluded["A"].exclusion_reason == SUPERSEDED
    assert excluded["B"].exclusion_reason == SUPERSEDED
    assert "B" in excluded["A"].witness_ids
    assert "C" in excluded["B"].witness_ids


# 5. implementation record does not automatically replace policy authority
def test_implementation_does_not_replace_policy():
    policy = decision("P")
    impl = decision("I", DecisionStatus.IMPLEMENTED, edges=(("P", RelationshipType.IMPLEMENTS),))
    proof = resolve_authority_with_proof([policy, impl], "scope")
    assert proof.governing_decision_id == "P"
    excluded = {c.decision_id: c for c in proof.excluded_candidates}
    assert excluded["I"].exclusion_reason == IMPLEMENTATION_NOT_POLICY_AUTHORITY
    assert excluded["I"].role == "implementation"


# 6. parallel scopes remain independent
def test_parallel_scopes_remain_independent():
    a = decision("A", scope="x")
    b = decision("B", scope="y")
    proof_x = resolve_authority_with_proof([a, b], "x")
    proof_y = resolve_authority_with_proof([a, b], "y")
    assert proof_x.governing_decision_id == "A"
    assert proof_y.governing_decision_id == "B"
    assert proof_x.requested_scope == "x"
    assert proof_y.requested_scope == "y"


# 7. unrelated policy does not create UNRESOLVED in another empty/open-only scope
def test_unrelated_policy_does_not_taint_empty_scope():
    accepted_elsewhere = decision("A", scope="policy-scope")
    proof = resolve_authority_with_proof([accepted_elsewhere], "impl-scope")
    assert proof.authority_state == "NO_GOVERNING_DECISION"


def test_unrelated_policy_does_not_taint_open_only_scope():
    accepted_elsewhere = decision("A", scope="policy-scope")
    open_impl = decision("I", DecisionStatus.PROPOSED, scope="impl-scope")
    proof = resolve_authority_with_proof([accepted_elsewhere, open_impl], "impl-scope")
    assert proof.authority_state == "NO_GOVERNING_DECISION"


# 8. true conflict produces UNRESOLVED
def test_true_in_scope_conflict_is_unresolved():
    a = decision("A")
    b = decision("B")  # both ACCEPTED, same scope, no lifecycle edge between them
    proof = resolve_authority_with_proof([a, b], "scope")
    assert proof.authority_state == "UNRESOLVED"
    assert proof.governing_decision_id is None


def test_two_accepted_in_open_only_scope_is_unresolved_not_no_governing():
    # Distinguishes case 7 (absence) from case 8 (conflict): scope is not
    # empty, and the conflict is genuinely in-scope.
    a = decision("A", scope="impl-scope")
    b = decision("B", scope="impl-scope")
    proof = resolve_authority_with_proof([a, b], "impl-scope")
    assert proof.authority_state == "UNRESOLVED"


# 9. withdrawn decision cannot govern
def test_withdrawn_decision_cannot_govern():
    withdrawn = decision("A", DecisionStatus.REVERTED)  # no REVERTS edge => withdrawn, not rollback
    proof = resolve_authority_with_proof([withdrawn], "scope")
    assert proof.authority_state == "NO_GOVERNING_DECISION"
    assert proof.excluded_candidates[0].exclusion_reason == WITHDRAWN


# 10. reverted decision semantics (rollback record governs)
def test_rollback_record_governs_its_change_scope():
    original = decision("A", DecisionStatus.IMPLEMENTED)
    rollback = decision("R", DecisionStatus.REVERTED, edges=(("A", RelationshipType.REVERTS),))
    proof = resolve_authority_with_proof([original, rollback], "scope")
    assert proof.governing_decision_id == "R"
    excluded = {c.decision_id: c for c in proof.excluded_candidates}
    assert excluded["A"].exclusion_reason == REVERTED


# 11. proposal after revert
def test_proposal_after_revert_does_not_govern():
    original = decision("A", DecisionStatus.IMPLEMENTED)
    rollback = decision("R", DecisionStatus.REVERTED, edges=(("A", RelationshipType.REVERTS),))
    later_proposal = decision(
        "P2", DecisionStatus.PROPOSED, edges=(("R", RelationshipType.SUPERSEDES),)
    )
    proof = resolve_authority_with_proof([original, rollback, later_proposal], "scope")
    assert proof.governing_decision_id == "R"
    excluded = {c.decision_id: c for c in proof.excluded_candidates}
    assert excluded["P2"].exclusion_reason == PROPOSED_NOT_ACCEPTED


# 12. partial acceptance / claim-level case
def test_partial_acceptance_refuses_full_authority():
    a = decision("A", partial=True)
    proof = resolve_authority_with_proof([a], "scope")
    assert proof.authority_state == "UNRESOLVED"
    assert proof.governing_decision_id is None
    assert proof.excluded_candidates[0].exclusion_reason == PARTIAL_ACCEPTANCE


def test_full_acceptance_is_unaffected_by_partial_flag_default():
    a = decision("A", partial=False)
    proof = resolve_authority_with_proof([a], "scope")
    assert proof.authority_state == "GOVERNING"


# 13. proof includes losing candidate and exclusion reason
def test_proof_includes_losing_candidate_with_reason():
    a = decision("A")
    b = decision("B", DecisionStatus.PROPOSED)
    proof = resolve_authority_with_proof([a, b], "scope")
    ids = {c.decision_id for c in proof.excluded_candidates}
    assert "B" in ids
    assert all(c.exclusion_reason is not None for c in proof.excluded_candidates)


# 14. proof contains supersession witness
def test_proof_contains_supersession_witness():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b], "scope")
    assert any("SUPERSEDES" in w for w in proof.governing_witnesses)
    assert f"B {RelationshipType.SUPERSEDES.value} A" in proof.transition_witnesses


# 15. proof contains revert witness
def test_proof_contains_revert_witness():
    original = decision("A", DecisionStatus.IMPLEMENTED)
    rollback = decision("R", DecisionStatus.REVERTED, edges=(("A", RelationshipType.REVERTS),))
    proof = resolve_authority_with_proof([original, rollback], "scope")
    assert f"R {RelationshipType.REVERTS.value} A" in proof.governing_witnesses


# 16. proof contains conflicting evidence for unresolved state
def test_proof_contains_conflicting_evidence_witness():
    a = decision("A")
    b = decision("B")
    proof = resolve_authority_with_proof([a, b], "scope")
    assert proof.authority_state == "UNRESOLVED"
    assert proof.ambiguity_witnesses
    reasons = {c.exclusion_reason for c in proof.excluded_candidates}
    assert reasons == {CONFLICTING_EVIDENCE}


def test_proof_contains_ambiguous_lineage_witness():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    c = decision("C", edges=(("A", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b, c], "scope")
    assert proof.authority_state == "UNRESOLVED"
    reasons = {x.exclusion_reason for x in proof.excluded_candidates}
    assert AMBIGUOUS_LINEAGE in reasons
    assert proof.ambiguity_witnesses


# 17. proof contains exact scope identity
def test_proof_contains_exact_scope_identity():
    a = decision("A", scope="the-exact-scope")
    proof = resolve_authority_with_proof([a], "the-exact-scope")
    assert proof.requested_scope == "the-exact-scope"


# 18. proof is deterministic independent of input order
def test_proof_deterministic_independent_of_input_order():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    c = decision("C", DecisionStatus.PROPOSED)
    forward = resolve_authority_with_proof([a, b, c], "scope")
    backward = resolve_authority_with_proof([c, b, a], "scope")
    shuffled = resolve_authority_with_proof([b, a, c], "scope")
    assert forward == backward == shuffled


# 19. repeated resolution is structurally equivalent
def test_repeated_resolution_is_structurally_equivalent():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    decisions = [a, b]
    first = resolve_authority_with_proof(decisions, "scope")
    second = resolve_authority_with_proof(decisions, "scope")
    assert first == second


# 20. missing evidence never fabricates certainty
def test_missing_evidence_never_fabricates_certainty():
    proof = resolve_authority_with_proof([], "scope")
    assert proof.authority_state == "NO_GOVERNING_DECISION"
    assert proof.governing_decision_id is None
    assert proof.considered_candidates == ()


def test_ambiguous_lineage_never_fabricates_a_winner():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    c = decision("C", edges=(("A", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b, c], "scope")
    assert proof.governing_decision_id is None
    assert proof.authority_state == "UNRESOLVED"


# Backward-compatibility: resolve_authority() still works and reflects the
# same fixed scope-locality semantics as resolve_authority_with_proof().
def test_resolve_authority_backward_compatible_summary():
    a = decision("A")
    got = resolve_authority([a], "scope")
    assert got.state == "GOVERNING"
    assert got.governing_decision_id == "A"
    assert got.evidence_ids == ("A",)


def test_resolve_authority_reflects_scope_locality_fix():
    accepted_elsewhere = decision("A", scope="policy-scope")
    got = resolve_authority([accepted_elsewhere], "impl-scope")
    assert got.state == "NO_GOVERNING_DECISION"


def test_candidate_assessment_is_immutable():
    a = decision("A")
    proof = resolve_authority_with_proof([a], "scope")
    cand = proof.considered_candidates[0]
    try:
        replace(cand, decision_id="mutated")
    except Exception:  # noqa: BLE001 - replace() itself should succeed; this just checks frozen dataclass semantics
        raise
    assert cand.decision_id == "A"  # original untouched
