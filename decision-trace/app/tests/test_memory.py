"""Stage 5: persistent memory. The mandatory property is the cross-session
proof — a genuinely fresh store/index instance, reading only the persisted
file, must recall a candidate decision created in an earlier "session"."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collaborate import answer  # noqa: E402
from loader import load_decisions  # noqa: E402
from memory import propose_reconsideration  # noqa: E402
from models import DecisionStatus, RelationshipType  # noqa: E402
from retrieval import DecisionIndex  # noqa: E402
from store import JSONFileDecisionStore  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]
FALSIFIER_DATA = APP_DIR.parent / "data" / "decisions.jsonl"

RECONSIDER_TARGET = "kubernetes/kubernetes-pr-137662"  # the active revert decision
CHANGED_ASSUMPTION = (
    "The 1.36 minor release constraint that motivated dropping delayed "
    "preemption no longer applies — we're now targeting a later release "
    "with room for the rework."
)


def test_candidate_persists_links_correctly_and_does_not_alter_resolution(tmp_path):
    store_path = tmp_path / "store.jsonl"
    store = JSONFileDecisionStore(store_path)
    store.save_many(load_decisions(FALSIFIER_DATA))

    candidate = propose_reconsideration(store, RECONSIDER_TARGET, CHANGED_ASSUMPTION)

    assert candidate.current_status == DecisionStatus.PROPOSED
    assert candidate.related_decisions == [(RECONSIDER_TARGET, RelationshipType.RECONSIDERS)]
    assert candidate.rationale == CHANGED_ASSUMPTION  # stored verbatim, not summarized

    # Same-session read-back.
    assert store.get(candidate.id) is not None

    # Recording a proposal must not silently change what's active — only a
    # later, separate acceptance step would (out of MVP scope).
    from graph import DecisionGraph, resolve_active
    graph = DecisionGraph(store.list_all())
    result = resolve_active(graph, "kubernetes/kubernetes-pr-136254")
    assert result.active_id == RECONSIDER_TARGET


def test_fresh_session_retrieval_recalls_the_candidate_decision(tmp_path):
    """The mandatory cross-session proof: a genuinely new store/index
    built from the same file, not the same in-process objects."""
    store_path = tmp_path / "store.jsonl"

    # "Session 1": create and record the candidate, then let it fall out
    # of scope entirely.
    def session_one():
        s = JSONFileDecisionStore(store_path)
        s.save_many(load_decisions(FALSIFIER_DATA))
        return propose_reconsideration(s, RECONSIDER_TARGET, CHANGED_ASSUMPTION).id

    candidate_id = session_one()

    # "Session 2": brand new objects, same file.
    fresh_store = JSONFileDecisionStore(store_path)
    fresh_index = DecisionIndex(fresh_store)  # no cache — force a real fresh embed

    results = fresh_index.search(
        "Should we reconsider delayed preemption now that the release "
        "constraint has changed?",
        k=5,
    )
    result_ids = {r.decision.id for r in results}
    assert candidate_id in result_ids


def test_proposed_candidate_never_reads_as_currently_active(tmp_path):
    """Regression test for a real bug caught during Stage 6's manual UI
    walkthrough: a freshly created PROPOSED candidate has no lineage edges
    (RECONSIDERS isn't a lifecycle edge), so it trivially resolved "active"
    in its own one-node lineage and the UI/Gemini both presented an
    unaccepted proposal as settled current guidance. A proposal must never
    read as current, regardless of what the graph alone says."""
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    store.save_many(load_decisions(FALSIFIER_DATA))
    candidate = propose_reconsideration(store, RECONSIDER_TARGET, CHANGED_ASSUMPTION)

    index = DecisionIndex(store)
    results = index.search(CHANGED_ASSUMPTION, k=5)
    candidate_result = next(r for r in results if r.decision.id == candidate.id)

    assert not candidate_result.is_current
    # And the real active decision for that subsystem is unaffected.
    real_active_result = next(
        r for r in index.search("delayed preemption", k=10)
        if r.decision.id == RECONSIDER_TARGET
    )
    assert real_active_result.is_current


def test_fresh_session_answer_considers_the_candidate_decision(tmp_path):
    store_path = tmp_path / "store.jsonl"

    def session_one():
        s = JSONFileDecisionStore(store_path)
        s.save_many(load_decisions(FALSIFIER_DATA))
        return propose_reconsideration(s, RECONSIDER_TARGET, CHANGED_ASSUMPTION).id

    candidate_id = session_one()

    fresh_store = JSONFileDecisionStore(store_path)
    fresh_index = DecisionIndex(fresh_store)

    result = answer(
        "Should we reconsider delayed preemption now that the release "
        "constraint has changed?",
        fresh_index,
    )
    assert candidate_id in result.candidates_considered
