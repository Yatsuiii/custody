"""Deterministic authority-benchmark equivalence and leakage gates."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import authority_benchmark as bench
from build_authority_cases import build, protected_manifest, validate


@pytest.fixture(scope="module")
def corpus():
    timelines, checkpoints, truth = build()
    return timelines, checkpoints, {g["checkpoint_id"]:g for g in truth}


def test_dataset_preregistered_size_and_scenarios(corpus):
    timelines, checkpoints, truth = corpus
    stats=validate(timelines,checkpoints,list(truth.values()))
    assert stats["total_timelines"] == 15
    assert stats["total_checkpoints"] == 61
    assert stats["adapter_coverage"] == 1.0


def test_builder_is_byte_reproducible(corpus):
    timelines, checkpoints, truth = corpus
    assert json.loads(bench.PUBLIC_PATH.read_text()) == timelines
    assert bench.read_jsonl(bench.CHECKPOINTS_PATH) == checkpoints
    assert bench.read_jsonl(bench.GROUND_TRUTH_PATH) == list(truth.values())


def test_adapter_module_cannot_name_or_open_answer_key():
    source=Path(bench.__file__).read_text()
    adapter=source[source.index("def adapt_decisions"):source.index("def rag_chunks")]
    assert "ground_truth" not in adapter.lower()
    assert "GROUND_TRUTH_PATH" not in adapter


def test_intervention_resolver_cannot_read_answer_key():
    source=(Path(__file__).parent/"app"/"authority.py").read_text().lower()
    assert "ground_truth" not in source
    assert "scenario_types" not in source
    assert "applicable_failures" not in source


def test_questions_do_not_disclose_hidden_status_or_answer(corpus):
    timelines, checkpoints, truth=corpus
    by_t={t["timeline_id"]:t for t in timelines}
    forbidden=("expected_state","scenario_types","applicable_failures",
               "STALE_DECISION","PROPOSAL_PROMOTED","REVERT_MISSED")
    for checkpoint in checkpoints:
        question=checkpoint["question"]
        assert not any(token in question for token in forbidden)
        visible=bench.visible_checkpoint(by_t[checkpoint["timeline_id"]],checkpoint)
        public="\n".join(bench.render_artifact(a) for a in visible.artifacts)
        expected=truth[checkpoint["checkpoint_id"]]["expected_decision_id"]
        if expected and expected in question:
            assert expected in public


def test_prepared_prompts_have_equivalent_visible_histories(corpus):
    timelines, checkpoints, truth=corpus
    if not bench.AUTHORITY_DIR.joinpath("prepared").exists():
        pytest.skip("run prepare mode first")
    by_t={t["timeline_id"]:t for t in timelines}
    for checkpoint in checkpoints:
        prepared=json.loads((bench.AUTHORITY_DIR/"prepared"/f"{checkpoint['checkpoint_id']}.json").read_text())
        visible=bench.visible_checkpoint(by_t[checkpoint["timeline_id"]],checkpoint)
        expected_history=bench.normalized_public_history(visible)
        assert prepared["visible_history"] == expected_history
        public="\n".join(prepared["visible_artifact_text"])
        for arm in ("structured","rag"):
            prompt=prepared[arm]["prompt"]
            hidden=truth[checkpoint["checkpoint_id"]]
            assert "expected_state" not in prompt and "scenario_types" not in prompt
            expected=hidden["expected_decision_id"]
            if expected and expected in prompt:
                assert expected in public
        assert [h["artifact_id"] for h in expected_history] == [h["artifact_id"] for h in prepared["visible_history"]]


def test_evidence_quotes_are_public_substrings(corpus):
    timelines, checkpoints, _=corpus
    by_t={t["timeline_id"]:t for t in timelines}
    for checkpoint in checkpoints:
        visible=bench.visible_checkpoint(by_t[checkpoint["timeline_id"]],checkpoint)
        decisions,_=bench.adapt_decisions(visible)
        public="\n".join(a["source_text"] for a in visible.artifacts)
        assert all(e.quote in public for d in decisions for e in d.evidence)


def test_no_future_artifacts(corpus):
    timelines, checkpoints, _=corpus
    by_t={t["timeline_id"]:t for t in timelines}
    for checkpoint in checkpoints:
        visible=bench.visible_checkpoint(by_t[checkpoint["timeline_id"]],checkpoint)
        assert all(a["sequence"] <= checkpoint["visible_through"] for a in visible.artifacts)


def test_v0_v2_protected_files_match_ca53fce():
    expected=json.loads((bench.AUTHORITY_DIR/"protected_sha256.json").read_text())
    assert expected == protected_manifest()
    for path,digest in expected.items():
        actual=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert actual == digest, path
