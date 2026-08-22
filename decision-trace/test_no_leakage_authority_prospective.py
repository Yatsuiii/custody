"""Offline independence, provenance, equivalence, and freeze gates.

These tests are deliberately runnable before either model condition exists.
They inspect only the source cache, public dataset, hidden answer key, and
frozen resolver manifest.  Conditional run checks activate after inference.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from build_authority_prospective_cases import build, validate


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "prospective"
RUNS = ROOT / "data" / "runs_authority_prospective"
PUBLIC_PATH = DATA / "timelines.json"
CHECKPOINTS_PATH = DATA / "checkpoints.jsonl"
TRUTH_PATH = DATA / "ground_truth.jsonl"
CACHE_PATH = DATA / "discovery" / "source_cache.json"
OLD_PUBLIC_PATH = ROOT / "data" / "authority" / "timelines.json"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


@pytest.fixture(scope="module")
def corpus():
    timelines, checkpoints, truth, exclusions = build()
    return timelines, checkpoints, truth, exclusions


def _proof_record(cache: dict, proof: dict) -> dict:
    kind = proof["kind"]
    if kind == "file":
        return cache["files"][proof["key"]]
    if kind == "pull_request":
        return cache["pull_requests"][proof["key"]]
    if kind == "issue":
        return cache["go_issues"][proof["key"]]
    if kind == "comment":
        return cache["go_acceptance_comments"][proof["key"]]
    raise AssertionError(f"unknown proof kind: {kind}")


def _record_text(record: dict) -> str:
    parts = []
    for field in ("content", "title", "body"):
        value = record.get(field)
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def test_preregistered_dataset_quality_gates(corpus):
    timelines, checkpoints, truth, _ = corpus
    stats = validate(timelines, checkpoints, truth)
    assert stats["timelines"] == 23
    assert stats["checkpoints"] == 101
    assert stats["fully_real"] == 19
    assert stats["hybrid"] == 4
    assert stats["fully_synthetic"] == 0
    assert len(stats["ecosystems"]) == 9


def test_builder_is_byte_reproducible(corpus):
    timelines, checkpoints, truth, exclusions = corpus
    assert json.loads(PUBLIC_PATH.read_text()) == timelines
    assert jsonl(CHECKPOINTS_PATH) == checkpoints
    assert jsonl(TRUTH_PATH) == truth
    assert json.loads((DATA / "discovery" / "exclusions.json").read_text()) == exclusions


def test_manifest_hashes_cover_all_dataset_inputs():
    manifest = json.loads((DATA / "dataset_manifest.json").read_text())
    paths = {
        "source_cache_sha256": CACHE_PATH,
        "timelines_sha256": PUBLIC_PATH,
        "checkpoints_sha256": CHECKPOINTS_PATH,
        "ground_truth_sha256": TRUTH_PATH,
    }
    for key, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[key]


def test_every_claimed_proof_resolves_to_pinned_primary_source(corpus):
    timelines, _, _, _ = corpus
    cache = json.loads(CACHE_PATH.read_text())
    assert cache["collection_completed_at"] <= "2026-08-23"
    for timeline in timelines:
        for artifact in timeline["artifacts"]:
            assert artifact["proofs"], artifact["artifact_id"]
            source_records = []
            for proof in artifact["proofs"]:
                record = _proof_record(cache, proof)
                source_records.append(record)
                if "field" in proof:
                    assert record[proof["field"]] == proof["value"], proof
                if "quote" in proof:
                    assert proof["quote"] in _record_text(record), proof
            source_universe = "\n".join(_record_text(record) for record in source_records)
            for quote in artifact["source_quotes"]:
                assert quote in source_universe, (artifact["artifact_id"], quote)


def test_pinned_file_hashes_and_repository_revisions():
    cache = json.loads(CACHE_PATH.read_text())
    for record in cache["files"].values():
        assert hashlib.sha256(record["content"].encode()).hexdigest() == record["sha256"]
        assert record["revision"] == cache["repositories"][record["repository"]]["revision"]
        assert record["revision"] in record["url"]
    for record in cache["pull_requests"].values():
        assert record["url"].startswith("https://github.com/")
        assert record["createdAt"]


def test_hidden_answer_key_never_appears_in_public_records(corpus):
    timelines, checkpoints, truth, _ = corpus
    public_text = json.dumps(timelines) + json.dumps(checkpoints)
    for forbidden in ("expected_state", "expected_decision_ids",
                      "acceptable_evidence_sets", "applicable_failures",
                      "adjudication"):
        assert forbidden not in public_text
    by_truth = {row["checkpoint_id"]: row for row in truth}
    by_timeline = {row["timeline_id"]: row for row in timelines}
    for cp in checkpoints:
        row = by_truth[cp["checkpoint_id"]]
        visible = [a for a in by_timeline[cp["timeline_id"]]["artifacts"]
                   if a["sequence"] <= cp["visible_through"]]
        visible_text = json.dumps(visible).casefold()
        for expected_id in row["expected_decision_ids"]:
            if expected_id.casefold() in cp["question"].casefold():
                assert expected_id.casefold() in visible_text


def test_all_expected_and_evidence_ids_are_visible(corpus):
    timelines, checkpoints, truth, _ = corpus
    by_timeline = {row["timeline_id"]: row for row in timelines}
    by_truth = {row["checkpoint_id"]: row for row in truth}
    for cp in checkpoints:
        visible = [a for a in by_timeline[cp["timeline_id"]]["artifacts"]
                   if a["sequence"] <= cp["visible_through"]]
        decision_ids = {a["decision_id"] for a in visible}
        artifact_ids = {a["artifact_id"] for a in visible}
        hidden = by_truth[cp["checkpoint_id"]]
        assert set(hidden["expected_decision_ids"]) <= decision_ids
        assert all(set(evidence_set) <= artifact_ids
                   for evidence_set in hidden["acceptable_evidence_sets"])


def test_no_future_artifact_is_visible(corpus):
    timelines, checkpoints, _, _ = corpus
    by_timeline = {row["timeline_id"]: row for row in timelines}
    for cp in checkpoints:
        visible = [a for a in by_timeline[cp["timeline_id"]]["artifacts"]
                   if a["sequence"] <= cp["visible_through"]]
        assert visible
        assert max(a["sequence"] for a in visible) == cp["visible_through"]
        assert all(a["sequence"] <= cp["visible_through"] for a in visible)


def test_no_development_benchmark_case_or_source_is_reused(corpus):
    timelines, _, _, _ = corpus
    old = json.loads(OLD_PUBLIC_PATH.read_text())
    assert {t["timeline_id"] for t in timelines}.isdisjoint(
        {t["timeline_id"] for t in old}
    )
    new_urls = {a["source_url"] for t in timelines for a in t["artifacts"]}
    old_urls = {a["source_url"] for t in old for a in t["artifacts"]}
    assert new_urls.isdisjoint(old_urls)
    new_decisions = {a["decision_id"] for t in timelines for a in t["artifacts"]}
    old_decisions = {a["decision_id"] for t in old for a in t["artifacts"]}
    assert new_decisions.isdisjoint(old_decisions)


def test_source_only_builder_does_not_import_or_invoke_systems():
    source = (ROOT / "build_authority_prospective_cases.py").read_text().casefold()
    forbidden = ("import vertex", "from vertex", "resolve_authority(",
                 "adapt_decisions(", "generate_content(", "embed(")
    assert not any(token in source for token in forbidden)


def test_no_system_output_existed_during_selection():
    marker = DATA / "discovery" / "selection_completed_without_outputs.txt"
    assert marker.exists()
    assert marker.read_text().strip() == "No DecisionTrace or RAG output existed during case selection."


def test_frozen_resolver_guard_passes():
    # Importing this test module executes the same byte checks as the dedicated
    # freeze test without duplicating the protected file list.
    import test_prospective_resolver_freeze as freeze

    freeze.test_manifest_is_the_preregistered_freeze()
    freeze.test_frozen_authority_system_is_byte_identical()


def test_conditions_use_equivalent_histories_after_preparation(corpus):
    prepared = DATA / "prepared"
    if not prepared.exists():
        pytest.skip("prompt preparation has not run")
    _, checkpoints, truth, _ = corpus
    hidden_by_id = {row["checkpoint_id"]: row for row in truth}
    for cp in checkpoints:
        row = json.loads((prepared / f"{cp['checkpoint_id']}.json").read_text())
        histories = row["condition_source_artifact_ids"]
        assert histories["decisiontrace"] == histories["rag_embedding"]
        assert histories["decisiontrace"] == histories["rag_full_context"]
        prompt_text = "\n".join(row["prompts"].values())
        hidden = hidden_by_id[cp["checkpoint_id"]]
        for field in ("expected_state", "acceptable_evidence_sets", "applicable_failures"):
            assert field not in prompt_text
        assert row["expected_answer_fields_present"] is False


def test_run_rows_match_frozen_prepared_prompt_hashes(corpus):
    if not RUNS.exists():
        pytest.skip("prospective inference has not run")
    _, checkpoints, _, _ = corpus
    for condition in ("decisiontrace", "rag_embedding", "rag_full_context"):
        condition_dir = RUNS / condition
        if not condition_dir.exists():
            pytest.skip(f"{condition} has not run")
        for cp in checkpoints:
            prepared = json.loads(
                (DATA / "prepared" / f"{cp['checkpoint_id']}.json").read_text()
            )
            run = json.loads((condition_dir / f"{cp['checkpoint_id']}.json").read_text())
            assert run["prompt_sha256"] == prepared["prompt_sha256"][condition]
            assert run["source_artifact_ids"] == prepared["condition_source_artifact_ids"][condition]
