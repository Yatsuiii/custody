"""Phase 10: Gemini explains an AuthorityProof but never decides it.
Mocked (unlike test_collaborate.py's real-call discipline) because the
point under test is the deterministic-first ordering and prompt
construction, not generation quality."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority_with_proof  # noqa: E402
from collaborate import ClaimCategory, explain_authority  # noqa: E402
import vertex  # noqa: E402
from models import Decision, DecisionStatus, RelationshipType  # noqa: E402


def test_explain_authority_reports_resolver_before_gemini(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"])
    proof = resolve_authority_with_proof([a], "scope")

    captured_prompt = {}

    def fake_generate(prompt):
        captured_prompt["prompt"] = prompt
        return json.dumps([{
            "text": "A currently governs scope.",
            "category": "current_active_decision",
            "decision_id": "A",
        }])

    monkeypatch.setattr(vertex, "generate", fake_generate)
    result = explain_authority(proof)

    assert [r.worker for r in result.worker_reports] == ["Authority Resolver", "Gemini Reconciler"]
    assert result.worker_reports[0].stage == "resolve"
    assert "GOVERNING" in captured_prompt["prompt"]
    assert result.claims[0].category == ClaimCategory.CURRENT_ACTIVE_DECISION
    assert result.claims[0].decision_id == "A"


def test_explain_authority_cannot_cite_an_uncounted_decision(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"])
    proof = resolve_authority_with_proof([a], "scope")

    monkeypatch.setattr(vertex, "generate", lambda prompt: json.dumps([{
        "text": "Fabricated decision governs.",
        "category": "current_active_decision",
        "decision_id": "not-a-real-id",
    }]))
    result = explain_authority(proof)

    # A citation Gemini invents outside the proof's own candidate set is
    # demoted to uncertainty, exactly like collaborate.answer()'s existing
    # allowed_ids gate — Gemini cannot smuggle in authority it wasn't given.
    assert result.claims[0].category == ClaimCategory.MISSING_OR_UNCERTAIN
    assert result.claims[0].decision_id is None


def test_explain_authority_unresolved_state_forbids_governing_claim(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"])
    b = Decision(id="B", subject="B", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"])
    proof = resolve_authority_with_proof([a, b], "scope")
    assert proof.authority_state == "UNRESOLVED"

    monkeypatch.setattr(vertex, "generate", lambda prompt: json.dumps([{
        "text": "A governs after all.",
        "category": "current_active_decision",
        "decision_id": "A",
    }]))
    result = explain_authority(proof)

    # No decision is authoritative when the proof itself is UNRESOLVED —
    # authoritative_ids is empty, so any current_active_decision claim is
    # demoted regardless of which candidate Gemini names.
    assert result.claims[0].category == ClaimCategory.MISSING_OR_UNCERTAIN


def test_explain_authority_edges_use_relationship_values(monkeypatch):
    a = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"])
    b = Decision(id="B", subject="B", current_status=DecisionStatus.ACCEPTED,
                 related_components=["scope"],
                 related_decisions=[("A", RelationshipType.SUPERSEDES)])
    proof = resolve_authority_with_proof([a, b], "scope")

    captured = {}
    monkeypatch.setattr(vertex, "generate", lambda prompt: captured.setdefault("p", prompt) or "[]")
    explain_authority(proof)

    assert "SUPERSEDES" in captured["p"]
    assert "Excluded candidates" in captured["p"]
