"""Unit tests for the deterministic active-decision resolver (Stage 1)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graph import DecisionGraph, resolve_active  # noqa: E402
from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def make(id_, status=DecisionStatus.ACCEPTED, edges=None):
    return Decision(
        id=id_, subject=id_, current_status=status,
        related_decisions=edges or [],
    )


def test_single_decision_no_edges_is_active():
    a = make("A")
    graph = DecisionGraph([a])
    result = resolve_active(graph, "A")
    assert result.active_id == "A"
    assert result.history == ["A"]
    assert not result.ambiguous


def test_supersede_then_revert_chain():
    """A accepted -> B supersedes A -> C reverts B. C must be active;
    A and B must not be presented as current."""
    a = make("A")
    b = make("B", edges=[("A", RelationshipType.SUPERSEDES)])
    c = make("C", edges=[("B", RelationshipType.REVERTS)])
    graph = DecisionGraph([a, b, c])

    for start in ("A", "B", "C"):
        result = resolve_active(graph, start)
        assert result.active_id == "C", f"resolving from {start} should still find C active"
        assert result.history == ["A", "B", "C"]
        assert not result.ambiguous


def test_reaffirm_reactivates_original_decision():
    """A accepted -> B supersedes A -> C reaffirms A. A must become active
    again; B must not be presented as current."""
    a = make("A")
    b = make("B", edges=[("A", RelationshipType.SUPERSEDES)])
    c = make("C", edges=[("A", RelationshipType.REAFFIRMS)])
    graph = DecisionGraph([a, b, c])

    result = resolve_active(graph, "A")
    assert result.active_id == "A"
    assert not result.ambiguous


def test_two_decisions_superseding_the_same_predecessor_is_ambiguous():
    """A accepted; B supersedes A; C ALSO supersedes A (a fork — two
    decisions competing to be A's successor). The resolver must flag this
    rather than silently picking whichever was processed first."""
    a = make("A")
    b = make("B", edges=[("A", RelationshipType.SUPERSEDES)])
    c = make("C", edges=[("A", RelationshipType.SUPERSEDES)])
    graph = DecisionGraph([a, b, c])

    result = resolve_active(graph, "A")
    assert result.ambiguous
    assert result.active_id is None


def test_unrelated_decision_is_unaffected_by_another_chain():
    a = make("A")
    b = make("B", edges=[("A", RelationshipType.SUPERSEDES)])
    isolated = make("ISOLATED")
    graph = DecisionGraph([a, b, isolated])

    result = resolve_active(graph, "ISOLATED")
    assert result.active_id == "ISOLATED"
    assert result.history == ["ISOLATED"]
    assert not result.ambiguous

    # And resolving the real chain still works, unaffected by ISOLATED.
    chain_result = resolve_active(graph, "A")
    assert chain_result.active_id == "B"


def test_real_falsifier_case_k8s_delayed_preemption_revert():
    """Reconstructs kubernetes-kubernetes-revert-136254 from the falsifier
    dataset: original PR #136254 was reverted by PR #137662, with no
    replacement decision. The original must resolve inactive; the revert
    record itself is the currently active state (there is no successor
    design, so "reverted" is what's operative now)."""
    decisions = [json.loads(line) for line in (DATA_DIR / "decisions.jsonl").open()]
    record = next(
        d for d in decisions if d["decision_id"] == "kubernetes-kubernetes-revert-136254"
    )
    original_id = f"pr-{record['citation']['original_pr']['number']}"
    revert_id = f"pr-{record['citation']['revert_pr']['number']}"

    original = Decision(
        id=original_id,
        subject=record["chosen"],
        current_status=DecisionStatus.IMPLEMENTED,
        rationale=None,
        evidence=[Evidence(
            type="pr", url=record["citation"]["original_pr"]["url"],
            quote=record["chosen"],
        )],
    )
    revert = Decision(
        id=revert_id,
        subject=record["rejected"],
        current_status=DecisionStatus.REVERTED,
        rationale=record["rationale_quote"],
        evidence=[Evidence(
            type="revert_pr", url=record["citation"]["revert_pr"]["url"],
            quote=record["rationale_quote"],
        )],
        related_decisions=[(original_id, RelationshipType.REVERTS)],
    )
    graph = DecisionGraph([original, revert])

    result = resolve_active(graph, original_id)
    assert result.active_id == revert_id
    assert result.active_id != original_id
    assert not result.ambiguous
