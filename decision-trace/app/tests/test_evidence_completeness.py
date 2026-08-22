"""Mechanical (non-LLM) evidence-completeness check — session brief Phase 9.

The prospective run measured DecisionTrace evidence correctness at
56/101 (55.4%) against RAG's 88/101 (87.1%) even though DecisionTrace's
governing-decision accuracy was 98/101. This module defines, without any
LLM judge, what "complete" means for each authority-result shape and
checks the AuthorityProof structurally against it. This is a coverage
check on the new proof object's own worked examples (the brief's Phase 3
examples plus the disputed prospective structures), not a rescoring of
the frozen 101-row benchmark.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority_with_proof  # noqa: E402
from models import Decision, DecisionStatus, RelationshipType  # noqa: E402


def decision(did, status=DecisionStatus.ACCEPTED, scope="scope", edges=(), partial=False):
    return Decision(
        id=did, subject=did, current_status=status,
        related_components=[scope], related_decisions=list(edges),
        partial_acceptance=partial,
    )


def missing_witnesses(proof, required_decision_ids: set[str]) -> set[str]:
    """The fixture-encoded requirement: every decision id named in
    `required_decision_ids` must appear somewhere in the proof — as the
    governing id, a considered/excluded candidate, or a witness_id/edge
    string — so a reader can find it without re-running the resolver."""
    seen = set()
    if proof.governing_decision_id:
        seen.add(proof.governing_decision_id)
    for c in proof.considered_candidates:
        seen.add(c.decision_id)
        seen.update(c.witness_ids)
    for edge in proof.transition_witnesses + proof.governing_witnesses:
        seen.update(edge.split(" ", 2)[::2])  # source and target tokens
    return required_decision_ids - seen


# Brief Phase 3, example 1: A accepted, B proposed later.
# Required witnesses: A accepted, B exists, B proposed, exclusion reason.
def test_evidence_complete_accepted_vs_later_proposal():
    a = decision("A")
    b = decision("B", DecisionStatus.PROPOSED)
    proof = resolve_authority_with_proof([a, b], "scope")
    assert not missing_witnesses(proof, {"A", "B"})
    excluded = {c.decision_id: c for c in proof.excluded_candidates}
    assert excluded["B"].exclusion_reason is not None


# Brief Phase 3, example 2: A accepted, B accepted and supersedes A.
# Required: B accepted (governing), B supersedes A (transition witness).
def test_evidence_complete_supersession():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b], "scope")
    assert not missing_witnesses(proof, {"A", "B"})
    assert f"B {RelationshipType.SUPERSEDES.value} A" in proof.transition_witnesses


# Brief Phase 3, example 3: A accepted, B supersedes A, B reverted, C
# proposed afterward. Required: every relevant transition (A->B, revert of
# B) plus C's non-authoritative status.
def test_evidence_complete_multi_hop_with_revert_and_later_proposal():
    a = decision("A")
    b = decision("B", edges=(("A", RelationshipType.SUPERSEDES),))
    revert_b = decision("R", DecisionStatus.REVERTED, edges=(("B", RelationshipType.REVERTS),))
    c = decision("C", DecisionStatus.PROPOSED, edges=(("R", RelationshipType.SUPERSEDES),))
    proof = resolve_authority_with_proof([a, b, revert_b, c], "scope")
    assert proof.governing_decision_id == "R"
    assert not missing_witnesses(proof, {"A", "B", "R", "C"})
    assert f"B {RelationshipType.SUPERSEDES.value} A" in proof.transition_witnesses
    assert f"R {RelationshipType.REVERTS.value} B" in proof.transition_witnesses
    excluded = {c_.decision_id: c_ for c_ in proof.excluded_candidates}
    assert excluded["C"].exclusion_reason is not None


# Conflict case: both conflicting candidates/evidence required.
def test_evidence_complete_conflict():
    a = decision("A")
    b = decision("B")
    proof = resolve_authority_with_proof([a, b], "scope")
    assert proof.authority_state == "UNRESOLVED"
    assert not missing_witnesses(proof, {"A", "B"})
    assert proof.ambiguity_witnesses


# Implementation-vs-policy case: policy winner plus the demoted
# implementation record must both be named.
def test_evidence_complete_implementation_vs_policy():
    policy = decision("P")
    impl = decision("I", DecisionStatus.IMPLEMENTED, edges=(("P", RelationshipType.IMPLEMENTS),))
    proof = resolve_authority_with_proof([policy, impl], "scope")
    assert not missing_witnesses(proof, {"P", "I"})


# Partial-acceptance case: the winner must still be named even though it
# does not end up governing, with a reason a reader can check.
def test_evidence_complete_partial_acceptance():
    a = decision("A", partial=True)
    proof = resolve_authority_with_proof([a], "scope")
    assert not missing_witnesses(proof, {"A"})
    assert proof.excluded_candidates[0].exclusion_reason == "PARTIAL_ACCEPTANCE"
