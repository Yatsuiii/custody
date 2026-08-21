"""Stage 2: load the falsifier's verified decisions into the storage
abstraction, and prove citations/evidence and lifecycle survive the round
trip."""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import vertex  # noqa: E402
from graph import DecisionGraph, resolve_active  # noqa: E402
from loader import load_decisions  # noqa: E402
from store import FirestoreDecisionStore, JSONFileDecisionStore, _firestore_doc_id  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1]
FALSIFIER_DATA = APP_DIR.parent / "data" / "decisions.jsonl"


def test_all_benchmark_records_load_without_error():
    decisions = load_decisions(FALSIFIER_DATA)
    source_records = [json.loads(line) for line in FALSIFIER_DATA.open()]
    expected = sum(
        2 if record["source"] == "revert_pair" else 1
        for record in source_records
    )
    assert len(decisions) == expected
    assert len({d.id for d in decisions}) == expected  # no id collisions


def test_store_round_trip_persists_and_reloads(tmp_path):
    decisions = load_decisions(FALSIFIER_DATA)
    store_path = tmp_path / "store.jsonl"

    store = JSONFileDecisionStore(store_path)
    store.save_many(decisions)

    # Fresh store instance reading the same file — proves it's the file,
    # not just the in-process index, that persisted the data.
    reloaded_store = JSONFileDecisionStore(store_path)
    assert len(reloaded_store.list_all()) == len(decisions)


def test_k8s_delayed_preemption_pair_loads_and_resolves(tmp_path):
    """Same assertion as Stage 1's hardcoded test, but now driven entirely
    through the loader + store instead of manually constructed Decisions."""
    decisions = load_decisions(FALSIFIER_DATA)
    store = JSONFileDecisionStore(tmp_path / "store.jsonl")
    store.save_many(decisions)

    original_id = "kubernetes/kubernetes-pr-136254"
    revert_id = "kubernetes/kubernetes-pr-137662"

    original = store.get(original_id)
    revert = store.get(revert_id)
    assert original is not None
    assert revert is not None

    graph = DecisionGraph(store.list_all())
    result = resolve_active(graph, original_id)
    assert result.active_id == revert_id
    assert result.active_id != original_id
    assert not result.ambiguous


def test_evidence_round_trips_exactly_against_source_record():
    """The loaded Evidence.quote/url must match the falsifier's own
    verified record byte-for-byte — this is the "preserve citations and
    evidence" requirement, checked directly, not assumed."""
    import json

    records = [json.loads(line) for line in FALSIFIER_DATA.open()]
    record = next(
        r for r in records if r["decision_id"] == "kubernetes-kubernetes-revert-136254"
    )

    decisions = load_decisions(FALSIFIER_DATA)
    revert_id = f"{record['repo']}-pr-{record['citation']['revert_pr']['number']}"
    revert_decision = next(d for d in decisions if d.id == revert_id)

    assert revert_decision.rationale == record["rationale_quote"]
    assert revert_decision.evidence[0].quote == record["rationale_quote"]
    assert revert_decision.evidence[0].url == record["citation"]["revert_pr"]["url"]


def test_kep_decision_loads_with_evidence():
    import json

    records = [json.loads(line) for line in FALSIFIER_DATA.open()]
    record = next(r for r in records if r["source"] == "kep_alternatives")

    decisions = load_decisions(FALSIFIER_DATA)
    decision = next(d for d in decisions if d.id == record["decision_id"])

    assert decision.rationale == record["rationale_quote"]
    assert decision.evidence[0].url == record["citation"]["file"]["url"]
    assert decision.evidence[0].quote == record["rationale_quote"]


def test_firestore_store_round_trip_persists_and_reloads():
    """Real Firestore, no mocks. Writes to a throwaway collection under the
    project vertex.py already talks to, reads back via a fresh client
    instance to prove it's Firestore persisting the data, not an in-process
    cache, then deletes every document it created."""
    decisions = load_decisions(FALSIFIER_DATA)[:3]
    collection = f"decisiontrace-test-{uuid.uuid4().hex[:12]}"

    store = FirestoreDecisionStore(collection, project=vertex.PROJECT)
    store.save_many(decisions)

    try:
        reloaded_store = FirestoreDecisionStore(collection, project=vertex.PROJECT)
        reloaded = {d.id: d for d in reloaded_store.list_all()}
        assert len(reloaded) == len(decisions)

        for original in decisions:
            round_tripped = reloaded[original.id]
            assert round_tripped.subject == original.subject
            assert round_tripped.rationale == original.rationale
            assert round_tripped.current_status == original.current_status
            assert [
                (e.type, e.url, e.quote) for e in round_tripped.evidence
            ] == [(e.type, e.url, e.quote) for e in original.evidence]

        single = reloaded_store.get(decisions[0].id)
        assert single is not None
        assert single.id == decisions[0].id
        assert reloaded_store.get("nonexistent-id") is None
    finally:
        for d in decisions:
            store._collection.document(_firestore_doc_id(d.id)).delete()
