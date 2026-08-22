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
from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402
from store import (  # noqa: E402
    FirestoreDecisionStore,
    JSONFileDecisionStore,
    _decision_to_firestore_dict,
    _dict_to_decision,
    _firestore_dict_to_decision,
    _firestore_doc_id,
)

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


def test_firestore_serialization_preserves_partial_acceptance():
    """Non-network: Decision -> firestore dict -> firestore-shaped dict ->
    Decision must preserve partial_acceptance and every other field, without
    touching a real Firestore project. Proves the serialization path itself
    is correct independent of network/auth/IAM."""
    original = Decision(
        id="A", subject="A", current_status=DecisionStatus.ACCEPTED,
        evidence=[Evidence(type="pr", url="https://example.test/pr", quote="q")],
        related_components=["scope"],
        related_decisions=[("B", RelationshipType.SUPERSEDES)],
        partial_acceptance=True,
    )
    firestore_dict = _decision_to_firestore_dict(original)
    # Firestore rejects nested arrays; related_decisions must already be
    # reshaped into a list of maps before this dict would ever reach a
    # real document.
    assert firestore_dict["related_decisions"] == [{"target_id": "B", "type": "SUPERSEDES"}]
    assert firestore_dict["partial_acceptance"] is True

    round_tripped = _firestore_dict_to_decision(firestore_dict)
    assert round_tripped == original
    assert round_tripped.partial_acceptance is True


def test_firestore_serialization_default_partial_acceptance_is_false():
    original = Decision(id="A", subject="A", current_status=DecisionStatus.ACCEPTED)
    round_tripped = _firestore_dict_to_decision(_decision_to_firestore_dict(original))
    assert round_tripped.partial_acceptance is False


def test_pre_partial_acceptance_firestore_document_deserializes_safely():
    """Simulates a real production Firestore document written before
    `partial_acceptance` existed on the Decision model — no such key in
    the stored document at all, not even a null. Backward compatibility
    requirement (session brief Phase 8): must default safely, not KeyError."""
    old_production_doc = {
        "id": "old-prod-decision", "subject": "Old decision",
        "current_status": "ACCEPTED", "context": None, "chosen_approach": None,
        "rejected_alternatives": [], "rationale": None, "constraints": [],
        "introduced_at": None, "superseded_at": None, "evidence": [],
        "related_components": ["x"], "related_decisions": [],
    }
    decision = _firestore_dict_to_decision(old_production_doc)
    assert decision.partial_acceptance is False
    assert decision.id == "old-prod-decision"


def test_pre_partial_acceptance_json_record_deserializes_safely():
    old_json_record = {
        "id": "old-json-decision", "subject": "Old decision",
        "current_status": "ACCEPTED", "related_decisions": [],
    }
    decision = _dict_to_decision(old_json_record)
    assert decision.partial_acceptance is False


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


def test_firestore_store_round_trip_preserves_partial_acceptance():
    """Real Firestore, disposable collection, cleaned up in `finally` —
    same discipline as the test above. Isolated to one narrow claim:
    partial_acceptance (this session's new field) survives a real
    Decision -> Firestore -> Decision round trip, not just the in-memory
    serialization helpers."""
    decision = Decision(
        id="partial-acceptance-roundtrip-probe",
        subject="Partial acceptance round-trip probe",
        current_status=DecisionStatus.ACCEPTED,
        evidence=[Evidence(type="pr", url="https://example.test/pr", quote="probe quote")],
        related_components=["probe-scope"],
        related_decisions=[("some-other-id", RelationshipType.IMPLEMENTS)],
        partial_acceptance=True,
    )
    collection = f"decisiontrace-test-{uuid.uuid4().hex[:12]}"
    store = FirestoreDecisionStore(collection, project=vertex.PROJECT)
    store.save(decision)

    try:
        reloaded_store = FirestoreDecisionStore(collection, project=vertex.PROJECT)
        round_tripped = reloaded_store.get(decision.id)
        assert round_tripped is not None
        assert round_tripped.partial_acceptance is True
        assert round_tripped == decision
    finally:
        store._collection.document(_firestore_doc_id(decision.id)).delete()
