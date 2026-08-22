import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority
from models import Decision, DecisionStatus, RelationshipType


def decision(did, status=DecisionStatus.ACCEPTED, scope="scope", edges=()):
    return Decision(id=did,subject=did,current_status=status,
                    related_components=[scope],related_decisions=list(edges))


def test_proposal_cannot_supersede_accepted_decision():
    old=decision("A")
    proposal=decision("B",DecisionStatus.PROPOSED,edges=(("A",RelationshipType.SUPERSEDES),))
    got=resolve_authority([old,proposal],"scope")
    assert (got.state,got.governing_decision_id)==("GOVERNING","A")


def test_accepted_successor_governs():
    old=decision("A")
    successor=decision("B",edges=(("A",RelationshipType.SUPERSEDES),))
    assert resolve_authority([old,successor],"scope").governing_decision_id=="B"


def test_merged_rollback_record_governs_its_change_scope():
    original=decision("A",DecisionStatus.IMPLEMENTED)
    rollback=decision("R",DecisionStatus.REVERTED,edges=(("A",RelationshipType.REVERTS),))
    assert resolve_authority([original,rollback],"scope").governing_decision_id=="R"


def test_withdrawn_record_does_not_govern():
    withdrawn=decision("A",DecisionStatus.REVERTED)
    got=resolve_authority([withdrawn],"scope")
    assert got.state=="NO_GOVERNING_DECISION"


def test_implementation_revert_does_not_replace_policy():
    policy=decision("P")
    implementation=decision("I",DecisionStatus.IMPLEMENTED,
                            edges=(("P",RelationshipType.IMPLEMENTS),))
    rollback=decision("R",DecisionStatus.REVERTED,
                     edges=(("I",RelationshipType.REVERTS),))
    got=resolve_authority([policy,implementation,rollback],"scope")
    assert (got.state,got.governing_decision_id)==("GOVERNING","P")


def test_unrelated_scope_authority_does_not_leak_into_empty_scope():
    # Parallel-scope independence (AUTHORITY_SEMANTICS.md): an accepted
    # decision in scope "y" must not change the answer for scope "broad",
    # which has no records at all. This was the scope-leakage defect the
    # prospective authority run exposed (POSTRUN_AUTHORITY_VALIDITY_AUDIT.md)
    # — the old resolver returned UNRESOLVED here by checking authority
    # anywhere in the input instead of stopping at the requested scope.
    got=resolve_authority([decision("A",scope="x"),decision("B",scope="y")],"broad")
    assert got.state=="NO_GOVERNING_DECISION"
