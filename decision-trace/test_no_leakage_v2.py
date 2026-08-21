"""Proves the v2 benchmark never hands a condition its own grading key.

Same invariant as test_no_leakage.py, restated for v2's unit (one named
alternative rather than one decision), plus two v2-specific checks: the
question names the alternative, so it must be shown not to also carry the
alternative's rationale; and the distilled card reason must not be a
copy of the graded span.

The structured check is stronger than v0's. Rather than testing one card,
it asserts that no case's `evidence_quote` appears anywhere in the whole
rendered card corpus, which holds whatever retrieval returns.

Runs fully offline against data/v2/ and the cached decoy indices.
"""

from __future__ import annotations

import json

import pytest

from build_v2_cases import shares_6gram
from run_conditions import repo_index_cache_file
from run_conditions_v2 import (
    CARDS_PATH,
    build_query,
    card_text,
    load_cases,
)

CASES = load_cases()
IDS = [c["case_id"] for c in CASES]
REASONS = (
    {json.loads(line)["case_id"]: json.loads(line)["reason"]
     for line in CARDS_PATH.open()}
    if CARDS_PATH.exists() else {}
)


def _code_only_prompt(c, query):
    """Mirrors run_code_only's prompt construction without calling Vertex."""
    return (
        f"You are a coding assistant working in {c['repo']}. You have no "
        f"access to this project's issue tracker, PR history, or design "
        f"discussions — only the current state of the code.\n\n"
        f"Developer question: {query}\n\nAnswer as best you can."
    )


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_query_never_contains_evidence(c):
    assert c["evidence_quote"] not in build_query(c)


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_query_never_paraphrases_evidence(c):
    """The alternative's name is in the question by design; its rationale
    must not be. A shared six-word span is the tripwire."""
    assert not shares_6gram(build_query(c), c["evidence_quote"])


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_card_reason_is_not_a_copy_of_evidence(c):
    if c["case_id"] not in REASONS:
        pytest.skip("cards not built yet")
    reason = REASONS[c["case_id"]]
    assert c["evidence_quote"] not in reason
    assert reason not in c["evidence_quote"]
    assert not shares_6gram(reason, c["evidence_quote"])


def test_no_card_in_the_corpus_carries_any_case_evidence():
    """Whatever the top-5 returns, the structured prompt is drawn from this
    corpus, so this covers every possible retrieval outcome."""
    if not REASONS:
        pytest.skip("cards not built yet")
    corpus = "\n\n".join(card_text(c, REASONS[c["case_id"]]) for c in CASES)
    for c in CASES:
        assert c["evidence_quote"] not in corpus, (
            f"{c['case_id']} evidence appears in the rendered card corpus"
        )


@pytest.mark.parametrize("c", CASES, ids=IDS)
def test_code_only_prompt_never_contains_evidence(c):
    assert c["evidence_quote"] not in _code_only_prompt(c, build_query(c))


def _cited_doc(c):
    cit = c["citation"]
    return (f"{c['repo']}#{cit['original_pr']['number']}"
            if "original_pr" in cit else cit["file"]["path"])


@pytest.mark.parametrize("repo", sorted({c["repo"] for c in CASES}))
def test_rag_decoy_pool_excludes_every_cited_source_document(repo):
    """The anti-planting invariant. RAG may legitimately retrieve the target
    document — that is its whole test — but the target must arrive through
    the per-case target index, not be sitting in the query-independent decoy
    pool where every question would hit it for free."""
    cache_path = repo_index_cache_file(repo)
    if not cache_path.exists():
        pytest.skip(f"no cached decoy index for {repo}")
    decoy_docs = set(json.loads(cache_path.read_text())["doc_ids"])
    for c in CASES:
        if c["repo"] == repo:
            assert _cited_doc(c) not in decoy_docs


@pytest.mark.parametrize("repo", sorted({c["repo"] for c in CASES}))
def test_decoy_evidence_overlap_only_from_other_documents(repo):
    """Public corpora genuinely repeat themselves: KEP-5593 inherits its
    Alternatives text from its predecessor KEP-4603, which is a legitimate
    decoy. That is a property of the real world, and it can only help the
    RAG arm, never structured or code-only. What it must never be is the
    case's *own* cited document. Overlaps are printed so they are disclosed
    in RESULTS_V2.md rather than buried."""
    cache_path = repo_index_cache_file(repo)
    if not cache_path.exists():
        pytest.skip(f"no cached decoy index for {repo}")
    cached = json.loads(cache_path.read_text())
    texts, doc_ids = cached["texts"], cached["doc_ids"]
    for c in (x for x in CASES if x["repo"] == repo):
        for text, doc_id in zip(texts, doc_ids):
            if c["evidence_quote"] in text:
                assert doc_id != _cited_doc(c)
                print(f"DUPLICATE: {c['case_id']} evidence also in {doc_id}")
