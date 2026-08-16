"""Runs the three-condition falsifier for each mined decision.

Conditions:
  1. code-only   — Gemini gets a one-line subsystem description, no history.
  2. rag         — Gemini gets the top-5 embedding-retrieved chunks from a
                    per-repo corpus. That corpus is the repo's decoy pool
                    PLUS the decision's own source document (the revert PR
                    body / KEP file) — RAG must find the needle among real
                    distractors, it isn't handed the answer for free, but it
                    also isn't excluded from ever finding it (that would rig
                    the falsifier the other way).
  3. structured  — Gemini gets every pre-extracted DecisionTrace card for
                    that repo, inlined directly, no retrieval step.

Each decision gets one synthetic query, built only from its `chosen`/
`context` fields (never `rationale_quote`), proposing to redo the reverted
change or revisit the rejected KEP alternative — so the query can't leak the
ground-truth rationale it's meant to test recall of.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np

import rag_index
import vertex
from gh_util import gh_json

DATA_DIR = Path(__file__).parent / "data"
RUNS_DIR = DATA_DIR / "runs"
TOP_K = 5

_repo_index_cache: dict[str, tuple] = {}


def load_decisions() -> list[dict]:
    return [json.loads(line) for line in (DATA_DIR / "decisions.jsonl").open()]


def build_query(d: dict) -> str:
    if d["source"] == "revert_pair":
        return (
            f"I'm working in {d['repo']} and I'm planning to reintroduce a "
            f"change along these lines: \"{d['chosen']}\". Before I do, is "
            f"there anything in this project's history I should know about "
            f"— has something like this been tried and undone before, and "
            f"if so why?"
        )
    return (
        f"I'm designing \"{d['context']}\" in {d['repo']} and I'm considering "
        f"an alternative approach instead of whatever was ultimately chosen. "
        f"What does this project's history say about alternatives that were "
        f"already considered here, and why weren't they used?"
    )


def fetch_target_document(d: dict) -> str:
    c = d["citation"]
    if "original_pr" in c:
        num = c["revert_pr"]["number"]
        pr = gh_json(
            "pr", "view", str(num), "--repo", d["repo"],
            "--json", "number,title,body",
        )
        return f"PR #{num}: {pr['title']}\n\n{pr.get('body') or ''}"
    path = c["file"]["path"]
    content = gh_json("api", f"repos/{d['repo']}/contents/{path}")
    text = base64.b64decode(content["content"]).decode("utf-8", errors="ignore")
    return f"{path}\n\n{text}"


def repo_corpus_file(repo: str) -> Path:
    return DATA_DIR / "corpus" / f"{repo.replace('/', '-')}.jsonl"


def repo_index_cache_file(repo: str) -> Path:
    return DATA_DIR / "corpus" / f"{repo.replace('/', '-')}-index.json"


def get_repo_decoy_index(repo: str):
    """Decoy chunk index, shared and cached across all decisions in a repo
    (decoys never include any decision's own citation doc, so this is safe
    to reuse — only the per-decision target doc is added at query time)."""
    if repo not in _repo_index_cache:
        decoys = [json.loads(line) for line in repo_corpus_file(repo).open()]
        _repo_index_cache[repo] = rag_index.load_or_build_index(
            repo_index_cache_file(repo), decoys
        )
    return _repo_index_cache[repo]


def run_rag(d: dict, query: str, target_doc: str) -> tuple[str, list[str]]:
    decoy_texts, decoy_doc_ids, decoy_vecs = get_repo_decoy_index(d["repo"])
    target_texts, target_doc_ids, target_vecs = rag_index.build_index(
        [{"id": "TARGET", "text": target_doc}]
    )
    chunk_texts = target_texts + decoy_texts
    chunk_doc_ids = target_doc_ids + decoy_doc_ids
    chunk_vecs = np.vstack([target_vecs, decoy_vecs])

    retrieved = rag_index.top_k_chunks(
        query, chunk_texts, chunk_doc_ids, chunk_vecs, k=TOP_K
    )
    context = "\n\n---\n\n".join(f"[{doc_id}]\n{text}" for doc_id, text in retrieved)
    prompt = (
        f"You have retrieved the following {TOP_K} document chunks from this "
        f"repository's issue/PR/design-proposal history via semantic "
        f"search:\n\n{context}\n\n---\n\nDeveloper question: {query}\n\n"
        f"Answer using only the retrieved chunks above. If a retrieved "
        f"chunk cites a specific PR/issue number or file and explains a "
        f"prior decision relevant to the question, name it and explain "
        f"the reasoning. If nothing retrieved is relevant, say so."
    )
    retrieved_ids = [doc_id for doc_id, _ in retrieved]
    return vertex.generate(prompt), retrieved_ids


def structured_cards_for_repo(all_decisions: list[dict], repo: str) -> str:
    cards = []
    for d in all_decisions:
        if d["repo"] != repo:
            continue
        c = d["citation"]
        cite = (
            f"PR #{c['original_pr']['number']} / revert PR #{c['revert_pr']['number']}"
            if "original_pr" in c else c["file"]["path"]
        )
        cards.append(
            f"Decision [{d['decision_id']}]\n"
            f"Context: {d['context']}\n"
            f"Chosen: {d['chosen']}\n"
            f"Rejected/Reverted: {d['rejected']}\n"
            f"Rationale: {d['rationale_quote']}\n"
            f"Evidence: {cite}"
        )
    return "\n\n".join(cards)


def run_structured(all_decisions: list[dict], d: dict, query: str) -> str:
    cards = structured_cards_for_repo(all_decisions, d["repo"])
    prompt = (
        f"You have access to this repository's structured engineering-decision "
        f"memory:\n\n{cards}\n\n---\n\nDeveloper question: {query}\n\n"
        f"Answer using only the decision memory above. If a decision is "
        f"relevant, cite its evidence (PR/issue number or file path) and "
        f"explain the reasoning. If nothing above is relevant, say so."
    )
    return vertex.generate(prompt)


def run_code_only(d: dict, query: str) -> str:
    prompt = (
        f"You are a coding assistant working in {d['repo']}. You have no "
        f"access to this project's issue tracker, PR history, or design "
        f"discussions — only the current state of the code.\n\n"
        f"Developer question: {query}\n\n"
        f"Answer as best you can."
    )
    return vertex.generate(prompt)


def main() -> None:
    decisions = load_decisions()
    for cond in ("code_only", "rag", "structured"):
        (RUNS_DIR / cond).mkdir(parents=True, exist_ok=True)

    for i, d in enumerate(decisions):
        did = d["decision_id"]
        query = build_query(d)
        print(f"[{i + 1}/{len(decisions)}] {did}")

        out = RUNS_DIR / "code_only" / f"{did}.json"
        if not out.exists():
            resp = run_code_only(d, query)
            out.write_text(json.dumps({"query": query, "response": resp}, indent=2))

        out = RUNS_DIR / "structured" / f"{did}.json"
        if not out.exists():
            resp = run_structured(decisions, d, query)
            out.write_text(json.dumps({"query": query, "response": resp}, indent=2))

        out = RUNS_DIR / "rag" / f"{did}.json"
        if not out.exists():
            target_doc = fetch_target_document(d)
            resp, retrieved_ids = run_rag(d, query, target_doc)
            out.write_text(json.dumps(
                {"query": query, "response": resp, "retrieved": retrieved_ids},
                indent=2,
            ))

    print("done")


if __name__ == "__main__":
    main()
