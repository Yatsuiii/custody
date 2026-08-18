"""Asserts the falsifier's grading key never appears unconditionally in a
condition's prompt. See docs/FALSIFIER_CONFOUND_HANDOFF.md section 4.3 —
this is the invariant whose absence produced the confounded 100/100/100
structured result: the same string (`rationale_quote`) was both handed to
the model and used by the judge to grade it, with no retrieval barrier.

Runs fully offline: reads the frozen decisions file and the already-cached
decoy corpus indices in data/corpus/, no network calls.

- code_only and the query: never carry any decision-specific ground truth,
  so `rationale_quote` can never appear regardless of retrieval.
- structured: after the fix, only ever renders `rationale_card` (the
  distilled paraphrase), never `rationale_quote` — checked unconditionally
  since the card is deterministic, not retrieval-dependent content.
- rag: `rationale_quote` legitimately CAN end up in the realized prompt
  when retrieval correctly finds the target document — that is the
  condition's whole test, not a leak. What must never happen is the
  *decoy* pool (the part every query sees regardless of what it's about)
  carrying another decision's rationale_quote as guaranteed content; that
  pool is checked here since it's cached and query-independent.
"""

from __future__ import annotations

import json

import pytest

from run_conditions import (
    DATA_DIR,
    build_query,
    build_structured_prompt,
    card_text,
    repo_index_cache_file,
)

DECISIONS = [json.loads(line) for line in (DATA_DIR / "decisions.jsonl").open()]


def _run_code_only_prompt(d: dict, query: str) -> str:
    """Mirrors run_code_only's prompt construction without calling Vertex."""
    return (
        f"You are a coding assistant working in {d['repo']}. You have no "
        f"access to this project's issue tracker, PR history, or design "
        f"discussions — only the current state of the code.\n\n"
        f"Developer question: {query}\n\nAnswer as best you can."
    )


@pytest.mark.parametrize("d", DECISIONS, ids=[d["decision_id"] for d in DECISIONS])
def test_query_never_contains_rationale_quote(d):
    query = build_query(d)
    assert d["rationale_quote"] not in query


@pytest.mark.parametrize("d", DECISIONS, ids=[d["decision_id"] for d in DECISIONS])
def test_code_only_prompt_never_contains_rationale_quote(d):
    query = build_query(d)
    prompt = _run_code_only_prompt(d, query)
    assert d["rationale_quote"] not in prompt


@pytest.mark.parametrize("d", DECISIONS, ids=[d["decision_id"] for d in DECISIONS])
def test_structured_card_never_contains_rationale_quote(d):
    assert "rationale_card" in d, (
        f"{d['decision_id']} has no rationale_card — run "
        f"backfill_rationale_cards.py first"
    )
    query = build_query(d)
    card = card_text(d)
    assert d["rationale_quote"] not in card
    prompt = build_structured_prompt(query, [card])
    assert d["rationale_quote"] not in prompt


@pytest.mark.parametrize(
    "repo",
    sorted({d["repo"] for d in DECISIONS}),
)
def test_rag_decoy_pool_never_carries_a_foreign_rationale_quote(repo):
    cache_path = repo_index_cache_file(repo)
    if not cache_path.exists():
        pytest.skip(f"no cached decoy index for {repo}")
    cached = json.loads(cache_path.read_text())
    decoy_texts = cached["texts"]
    repo_quotes = [d["rationale_quote"] for d in DECISIONS if d["repo"] == repo]
    for text in decoy_texts:
        for quote in repo_quotes:
            assert quote not in text, (
                f"decoy pool for {repo} carries a rationale_quote "
                f"unconditionally (query-independent leak)"
            )
