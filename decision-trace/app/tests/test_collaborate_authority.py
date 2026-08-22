"""Phase 5 (product integration): resolve_authority_with_proof is wired
into collaborate.answer()'s worker pipeline. Mocked (unlike
test_collaborate.py's real-call discipline) because these tests are
about the deterministic wiring and citation-gating logic, not generation
quality — the same reasoning as test_authority_explanation.py."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collaborate import ClaimCategory, answer  # noqa: E402
import vertex  # noqa: E402
from graph import ActiveResolution  # noqa: E402
from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402
from retrieval import RetrievalCandidate  # noqa: E402


def _evidence():
    return [Evidence(type="pr", url="https://example.test/pr", quote="q")]


class StubIndex:
    """`retrieved_ids` order matters: `_resolve_authority_for_candidates`
    scopes against `candidates[0]`, mirroring how real retrieval ranks by
    similarity — the first id here is the top-ranked candidate."""

    def __init__(self, decisions, retrieved_ids):
        self.decisions = decisions
        by_id = {d.id: d for d in decisions}
        self._candidates = [
            RetrievalCandidate(
                decision=by_id[did], similarity=0.9,
                resolution=ActiveResolution(active_id=did, history=[did], explanation="stub"),
            )
            for did in retrieved_ids
        ]

    def search(self, question, k=5):
        return self._candidates


def test_answer_attaches_authority_proof_when_scope_available(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"], evidence=_evidence())
    index = StubIndex([a], ["A"])

    monkeypatch.setattr(vertex, "generate", lambda prompt: json.dumps([{
        "text": "A is active.", "category": "current_active_decision", "decision_id": "A",
    }]))
    result = answer("Is A still current?", index)

    assert result.authority_proof is not None
    assert result.authority_proof.authority_state == "GOVERNING"
    assert result.authority_proof.governing_decision_id == "A"
    assert [r.worker for r in result.worker_reports] == [
        "Evidence Scout", "Lifecycle Resolver", "Provenance Challenger", "Gemini Reconciler",
    ]
    assert "GOVERNING" in result.worker_reports[1].summary


def test_authority_proof_overrides_stale_current_active_claim(monkeypatch):
    """The proof is canonical: even if Gemini's prose claims a decision is
    current, the citation-gating in answer() demotes that claim unless it
    names the proof's own governing_decision_id."""
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"], evidence=_evidence())
    b = Decision(id="B", subject="B", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"], evidence=_evidence(),
                 related_decisions=[("A", RelationshipType.SUPERSEDES)])
    index = StubIndex([a, b], ["B"])

    # B genuinely governs (supersedes A), so this should be accepted.
    monkeypatch.setattr(vertex, "generate", lambda prompt: json.dumps([{
        "text": "B is active.", "category": "current_active_decision", "decision_id": "B",
    }]))
    result = answer("Is B current?", index)
    assert result.authority_proof.governing_decision_id == "B"
    assert result.claims[0].category == ClaimCategory.CURRENT_ACTIVE_DECISION
    assert result.claims[0].decision_id == "B"


def test_authority_proof_rejects_claim_naming_wrong_governing_id(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"], evidence=_evidence())
    b = Decision(id="B", subject="B", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"], evidence=_evidence(),
                 related_decisions=[("A", RelationshipType.SUPERSEDES)])
    index = StubIndex([a, b], ["B", "A"])

    # Gemini (wrongly) claims A is current active, but the proof says B
    # governs — the claim must be demoted, not trusted.
    monkeypatch.setattr(vertex, "generate", lambda prompt: json.dumps([{
        "text": "A is still active.", "category": "current_active_decision", "decision_id": "A",
    }]))
    result = answer("Is A current?", index)
    assert result.authority_proof.governing_decision_id == "B"
    assert result.claims[0].category == ClaimCategory.MISSING_OR_UNCERTAIN
    assert result.claims[0].decision_id is None


def test_answer_has_no_authority_proof_when_top_candidate_unscoped(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 evidence=_evidence())
    index = StubIndex([a], ["A"])

    monkeypatch.setattr(vertex, "generate", lambda prompt: json.dumps([{
        "text": "A is active.", "category": "current_active_decision", "decision_id": "A",
    }]))
    result = answer("Is A current?", index)
    assert result.authority_proof is None
    # Falls back to the pre-existing is_current heuristic when there's no
    # scope to resolve — unchanged behavior for unscoped decisions.
    assert result.claims[0].category == ClaimCategory.CURRENT_ACTIVE_DECISION
