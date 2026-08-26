"""Stage 3: card-level retrieval, using real benchmark decisions.

These tests make real Vertex embedding calls (same credentials/transport
already validated throughout the falsifier work) — not mocked, since the
whole point of this stage is proving retrieval behavior against real data,
the same discipline the falsifier itself used.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loader import load_decisions  # noqa: E402
from retrieval import DecisionIndex  # noqa: E402
from store import JSONFileDecisionStore  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]
FALSIFIER_DATA = APP_DIR.parent / "data" / "decisions.jsonl"


def _build_index(tmp_path) -> DecisionIndex:
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    store.save_many(load_decisions(FALSIFIER_DATA))
    # No cache_path: force a fresh embed for test isolation/correctness,
    # not speed — a real deployment would pass default_cache_path().
    return DecisionIndex(store)


@pytest.mark.live
def test_search_returns_evidence_bearing_candidates(tmp_path):
    index = _build_index(tmp_path)
    results = index.search("why do we use synchronous processing here", k=5)
    assert len(results) == 5
    for r in results:
        assert r.decision.evidence, f"{r.decision.id} returned with no evidence"
        assert r.decision.evidence[0].url.startswith("http")


@pytest.mark.live
def test_delayed_preemption_query_retrieves_the_real_k8s_pair(tmp_path):
    index = _build_index(tmp_path)
    results = index.search(
        "why don't we restore delayed preemption / extending PostFilterResult "
        "with a list of victim pods",
        k=5,
    )
    ids = {r.decision.id for r in results}
    assert "kubernetes/kubernetes-pr-136254" in ids
    assert "kubernetes/kubernetes-pr-137662" in ids


@pytest.mark.live
def test_reverted_decision_never_surfaces_as_current_without_its_resolution(tmp_path):
    """The retrieved original (reverted) decision must carry a resolution
    that says it's inactive, and must name the decision that IS active —
    this is the structural guarantee against silently presenting stale
    guidance, checked directly rather than trusted."""
    index = _build_index(tmp_path)
    results = index.search(
        "why don't we restore delayed preemption / extending PostFilterResult "
        "with a list of victim pods",
        k=5,
    )
    original = next(r for r in results if r.decision.id == "kubernetes/kubernetes-pr-136254")

    assert not original.is_current
    assert original.resolution.active_id == "kubernetes/kubernetes-pr-137662"
    assert original.resolution.active_id != original.decision.id

    # And the revert record itself must report as current.
    revert = next(r for r in results if r.decision.id == "kubernetes/kubernetes-pr-137662")
    assert revert.is_current


def test_empty_store_search_returns_no_candidates(tmp_path):
    store = JSONFileDecisionStore(tmp_path / "empty_store.jsonl")
    index = DecisionIndex(store)
    assert index.search("anything", k=5) == []
