"""Regression checks for the mechanical prospective grader."""

from __future__ import annotations

import json
from pathlib import Path

import grade_authority_prospective as grader


ROOT = Path(__file__).resolve().parent
SCORES = ROOT / "data" / "prospective" / "scores.json"


def test_grader_is_model_free_and_only_grader_names_hidden_key() -> None:
    source = Path(grader.__file__).read_text().casefold()
    assert "import vertex" not in source
    assert "generate(" not in source
    assert "embed(" not in source


def test_every_condition_has_one_mechanically_scored_row_per_checkpoint() -> None:
    scores = json.loads(SCORES.read_text())
    for condition in grader.CONDITIONS:
        rows = scores["all_rows"][condition]
        assert len(rows) == 101
        assert len({row["checkpoint_id"] for row in rows}) == 101
        assert scores["conditions"][condition]["parse_failures"]["numerator"] == 0


def test_primary_comparator_and_gate_follow_preregistered_rule() -> None:
    scores = json.loads(SCORES.read_text())
    assert scores["primary_rag_comparator"] == "rag_embedding"
    gate = scores["strict_gate"]
    assert gate["passed"] is False
    assert gate["conditions"]["dt_lead_at_least_8_points"] is False
    assert gate["conditions"]["dt_evidence_within_3_points"] is False
    assert gate["verdict"] == "MODEST AUTHORITY ADVANTAGE — KEEP RESEARCHING"


def test_bootstrap_is_exactly_the_preregistered_analysis() -> None:
    scores = json.loads(SCORES.read_text())
    bootstrap = scores["paired_timeline_bootstrap"]
    assert bootstrap["samples"] == 100_000
    assert bootstrap["seed"] == 20260822
    assert bootstrap["ci90"][0] > 0


def test_known_authority_misses_are_complete() -> None:
    scores = json.loads(SCORES.read_text())
    dt_misses = {
        row["checkpoint_id"] for row in scores["all_rows"]["decisiontrace"]
        if not row["authority_correct"]
    }
    assert dt_misses == {
        "go-range-functions-c2", "go-range-functions-c3", "go-range-functions-c4"
    }
    for condition in ("rag_embedding", "rag_full_context"):
        assert sum(not row["authority_correct"]
                   for row in scores["all_rows"][condition]) == 7


def test_material_validity_failure_overrides_mechanical_verdict_without_relabeling() -> None:
    audit = json.loads((ROOT / "data" / "prospective" / "validity_audit.json").read_text())
    assert audit["status"] == "invalid"
    assert audit["final_verdict"] == "BENCHMARK INVALID — FIX BEFORE CONCLUDING"
    assert audit["frozen_inputs_modified"] is False
    assert audit["systems_rerun"] is False
    assert set(audit["affected_checkpoints"]) == {
        "python-paramspec-implementation-c2",
        "swift-coroutine-accessors-c2",
    }
    assert audit["sensitivity_not_rescoring"]["decisiontrace"] == "96/101"
    assert audit["sensitivity_not_rescoring"]["primary_rag"] == "96/101"
