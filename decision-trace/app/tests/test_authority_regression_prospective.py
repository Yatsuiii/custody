"""Regression fixtures replaying the exact real-world facts behind the
three prospective-benchmark defects, hand-built from
AUTHORITY_PROSPECTIVE_LEDGER.md and POSTRUN_AUTHORITY_VALIDITY_AUDIT.md.

This is engineering validation, not a rescored benchmark: no new score is
claimed, no frozen prospective artifact (data/prospective/**,
RESULTS_AUTHORITY_PROSPECTIVE.md, the answer key) is read or mutated.
These three cases are reconstructed from the ledger's own prose because
those two documents already establish, independently of any resolver
run, what the internally-consistent ground truth should have been. The
general scope-locality and partial-acceptance fixes in authority.py are
not conditioned on these specific ids — see test_authority_proof.py for
the general-rule tests these fixtures corroborate.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority_with_proof  # noqa: E402
from models import Decision, DecisionStatus, RelationshipType  # noqa: E402


def test_python_paramspec_implementation_c2_is_no_governing_not_unresolved():
    """AUTHORITY_PROSPECTIVE_LEDGER.md row `python-paramspec-implementation-c2`:
    visible through seq 2 only. PEP-612 (FINAL/POLICY) lives in scope
    `python-paramspec-policy`. cpython#23702 (OPEN/IMPLEMENTATION,
    implements PEP-612) lives in scope `python-paramspec-implementation`
    and is not yet merged. The frozen key answered UNRESOLVED here by
    letting PEP-612's authority in the *policy* scope leak into the
    *implementation* scope query — POSTRUN_AUTHORITY_VALIDITY_AUDIT.md's
    finding. Under scope-local semantics the implementation scope has an
    open-only record and nothing else: absence, not conflict.
    """
    pep_612 = Decision(
        id="PEP-612", subject="PEP-612", current_status=DecisionStatus.ACCEPTED,
        related_components=["python-paramspec-policy"],
    )
    open_pr = Decision(
        id="python/cpython#23702", subject="python/cpython#23702",
        current_status=DecisionStatus.PROPOSED,
        related_components=["python-paramspec-implementation"],
        related_decisions=[("PEP-612", RelationshipType.IMPLEMENTS)],
    )
    proof = resolve_authority_with_proof(
        [pep_612, open_pr], "python-paramspec-implementation"
    )
    assert proof.authority_state == "NO_GOVERNING_DECISION"


def test_swift_coroutine_accessors_c2_is_no_governing_not_unresolved():
    """Same structural defect, `swift-coroutine-accessors-c2`: SE-0474
    (ACCEPTED/POLICY) in scope `swift-yielding-accessor-policy`;
    swift#90516 (OPEN/IMPLEMENTATION, implements SE-0474) in scope
    `swift-coroutine-accessor-implementation`. Queried scope is the
    implementation scope, visible through seq 2 (open PR only)."""
    se_0474 = Decision(
        id="SE-0474", subject="SE-0474", current_status=DecisionStatus.ACCEPTED,
        related_components=["swift-yielding-accessor-policy"],
    )
    open_pr = Decision(
        id="swiftlang/swift#90516", subject="swiftlang/swift#90516",
        current_status=DecisionStatus.PROPOSED,
        related_components=["swift-coroutine-accessor-implementation"],
        related_decisions=[("SE-0474", RelationshipType.IMPLEMENTS)],
    )
    proof = resolve_authority_with_proof(
        [se_0474, open_pr], "swift-coroutine-accessor-implementation"
    )
    assert proof.authority_state == "NO_GOVERNING_DECISION"


def test_go_range_functions_c2_partial_acceptance_is_unresolved():
    """`go-range-functions-c2`: golang/go#61405's acceptance comment
    accepted range-over-int but explicitly deferred range-over-func
    details to a follow-up proposal, under one normalized scope
    `go-range-function-details`. The frozen resolver's artifact-level
    ACCEPTED promoted the whole record to GOVERNING
    (RESULTS_AUTHORITY_PROSPECTIVE.md's `lifecycle representation` miss,
    56/101 evidence rows); ground truth is UNRESOLVED. Marking the
    decision `partial_acceptance=True` (the source evidence for this one
    record explicitly limits what its ACCEPTED status covers) makes the
    resolver match ground truth instead of overclaiming.
    """
    go_61405 = Decision(
        id="golang/go#61405", subject="golang/go#61405",
        current_status=DecisionStatus.ACCEPTED,
        related_components=["go-range-function-details"],
        partial_acceptance=True,
    )
    proof = resolve_authority_with_proof(
        [go_61405], "go-range-function-details"
    )
    assert proof.authority_state == "UNRESOLVED"
    assert proof.governing_decision_id is None


def test_go_range_functions_c1_open_only_is_no_governing():
    """`go-range-functions-c1`: visible through seq 1 only (OPEN proposal,
    no acceptance comment yet). Ground truth NO_GOVERNING_DECISION — this
    one was already correct under the old resolver and must stay correct
    under the new one (no regression on the cases that worked)."""
    open_issue = Decision(
        id="golang/go#61405", subject="golang/go#61405",
        current_status=DecisionStatus.PROPOSED,
        related_components=["go-range-function-details"],
    )
    proof = resolve_authority_with_proof([open_issue], "go-range-function-details")
    assert proof.authority_state == "NO_GOVERNING_DECISION"
