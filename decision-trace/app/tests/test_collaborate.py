"""Stage 4: Gemini collaboration layer, using real benchmark decisions and
real Gemini calls (same discipline as Stage 3 — not mocked)."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collaborate import (  # noqa: E402
    ClaimCategory,
    _challenge_candidates,
    _parse_claims,
    answer,
)
import vertex  # noqa: E402
from graph import ActiveResolution  # noqa: E402
from loader import load_decisions  # noqa: E402
from models import Decision, DecisionStatus, Evidence  # noqa: E402
from retrieval import DecisionIndex, RetrievalCandidate  # noqa: E402
from store import JSONFileDecisionStore  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]
FALSIFIER_DATA = APP_DIR.parent / "data" / "decisions.jsonl"


def _build_index(tmp_path) -> DecisionIndex:
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    store.save_many(load_decisions(FALSIFIER_DATA))
    return DecisionIndex(store)


def test_answer_never_claims_the_reverted_original_is_current(tmp_path):
    """The single non-negotiable safety property: Gemini must not
    contradict resolve_active's ground truth by tagging the reverted
    original as currently active."""
    index = _build_index(tmp_path)
    result = answer(
        "Why don't we restore delayed preemption / extending "
        "PostFilterResult with a list of victim pods?",
        index,
    )
    for claim in result.claims:
        if claim.category == ClaimCategory.CURRENT_ACTIVE_DECISION:
            assert claim.decision_id != "kubernetes/kubernetes-pr-136254", (
                f"claimed the reverted original is current: {claim.text!r}"
            )


def test_answer_correctly_identifies_the_revert_as_current(tmp_path):
    index = _build_index(tmp_path)
    result = answer(
        "Why don't we restore delayed preemption / extending "
        "PostFilterResult with a list of victim pods?",
        index,
    )
    current_claims = [c for c in result.claims if c.category == ClaimCategory.CURRENT_ACTIVE_DECISION]
    assert current_claims, "expected at least one current_active_decision claim"
    assert any(c.decision_id == "kubernetes/kubernetes-pr-137662" for c in current_claims)


def test_answer_cites_historical_fact_with_a_real_decision_id(tmp_path):
    index = _build_index(tmp_path)
    result = answer(
        "Was extending PostFilterResult with victim pods tried before?",
        index,
    )
    known_ids = {"kubernetes/kubernetes-pr-136254", "kubernetes/kubernetes-pr-137662"}
    historical = [c for c in result.claims if c.category == ClaimCategory.VERIFIED_HISTORICAL_FACT]
    assert historical, "expected at least one verified_historical_fact claim"
    assert any(c.decision_id in known_ids for c in historical)


def test_unrelated_question_yields_missing_or_uncertain_not_fabrication(tmp_path):
    """A question with nothing relevant in the decision store must not
    produce a confident, fabricated answer."""
    index = _build_index(tmp_path)
    result = answer(
        "What is the price of milk in our office cafeteria?",
        index,
    )
    assert any(c.category == ClaimCategory.MISSING_OR_UNCERTAIN for c in result.claims)
    confident_categories = {ClaimCategory.VERIFIED_HISTORICAL_FACT, ClaimCategory.CURRENT_ACTIVE_DECISION}
    assert not any(c.category in confident_categories for c in result.claims)


def test_all_claims_have_a_valid_category():
    from collaborate import _parse_claims
    claims = _parse_claims(
        '[{"text": "x", "category": "verified_historical_fact", "decision_id": "a"}, '
        '{"text": "y", "category": "not_a_real_category", "decision_id": null}]'
    )
    assert claims[0].category == ClaimCategory.VERIFIED_HISTORICAL_FACT
    # An invalid category from the model degrades to missing_or_uncertain
    # rather than crashing or silently accepting an unrecognized tag.
    assert claims[1].category == ClaimCategory.MISSING_OR_UNCERTAIN


def test_claim_gate_rejects_unknown_authoritative_decision_id():
    claims = _parse_claims(
        '[{"text": "invented current truth", "category": '
        '"current_active_decision", "decision_id": "not-retrieved"}]',
        allowed_ids={"known"},
        authoritative_ids={"known"},
    )

    assert claims[0].category == ClaimCategory.MISSING_OR_UNCERTAIN
    assert claims[0].decision_id is None


def test_provenance_challenger_rejects_evidence_less_candidates():
    candidate = RetrievalCandidate(
        decision=Decision(
            id="unproven",
            subject="Unproven decision",
            current_status=DecisionStatus.ACCEPTED,
        ),
        similarity=0.99,
        resolution=ActiveResolution(
            active_id="unproven", history=["unproven"],
        ),
    )

    trusted, challenges = _challenge_candidates([candidate])

    assert trusted == []
    assert "no source evidence" in challenges[0]


def test_provenance_challenger_retains_evidence_and_reports_ambiguity():
    candidate = RetrievalCandidate(
        decision=Decision(
            id="ambiguous",
            subject="Ambiguous decision",
            current_status=DecisionStatus.ACCEPTED,
            evidence=[Evidence(type="pr", url="https://example.test/1", quote="fact")],
        ),
        similarity=0.99,
        resolution=ActiveResolution(
            active_id=None,
            history=["A", "B"],
            ambiguous=True,
            explanation="Lifecycle is ambiguous because the lineage contains a cycle",
        ),
    )

    trusted, challenges = _challenge_candidates([candidate])

    assert trusted == [candidate]
    assert "lifecycle is ambiguous" in challenges[0]


def test_answer_emits_discover_resolve_challenge_reconcile_handoffs(monkeypatch):
    candidate = RetrievalCandidate(
        decision=Decision(
            id="active",
            subject="Use the selected approach",
            current_status=DecisionStatus.ACCEPTED,
            evidence=[Evidence(
                type="proposal",
                url="https://example.test/decision",
                quote="The selected approach is supported by the evidence.",
            )],
        ),
        similarity=0.99,
        resolution=ActiveResolution(
            active_id="active", history=["active"],
            explanation="active is the only governing decision in this lineage",
        ),
    )

    class StubIndex:
        def search(self, question, k=5):
            return [candidate]

    monkeypatch.setattr(
        vertex,
        "generate",
        lambda prompt: json.dumps([{
            "text": "The selected approach is active.",
            "category": "current_active_decision",
            "decision_id": "active",
        }]),
    )

    result = answer("What is active?", StubIndex())

    assert [report.worker for report in result.worker_reports] == [
        "Evidence Scout",
        "Lifecycle Resolver",
        "Provenance Challenger",
        "Gemini Reconciler",
    ]
    assert result.claims[0].category == ClaimCategory.CURRENT_ACTIVE_DECISION
    assert result.claims[0].decision_id == "active"
