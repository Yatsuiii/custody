"""Shared chunking + retrieval index for the embedding-RAG condition.

Replaces two earlier approaches that both undercounted long documents:
  - truncating every doc to its first 2000 chars (missed sections that
    start deep in a file, e.g. a KEP's Alternatives section at char 78888
    of a 106602-char file)
  - fixed-size 1800-char windows capped at 12 chunks/doc (still only
    covered the first ~19K chars of that same file)

Chunks by markdown section (## / ### headings) instead: a document's
"## Alternatives Considered" section becomes its own chunk regardless of
how far into the file it starts, which is both how real RAG pipelines
commonly chunk structured docs and a natural fix for the coverage problem.
Oversized sections are still sub-split with overlap so no single chunk is
unbounded. Short, header-less bodies (e.g. a revert PR description) yield
one chunk, unchanged from before.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

import vertex

MAX_SUBCHUNK = 2500
SUBCHUNK_OVERLAP = 250
HEADING = re.compile(r"^#{2,3}\s+.+$", re.MULTILINE)


def chunk_by_section(text: str) -> list[str]:
    bounds = [m.start() for m in HEADING.finditer(text)]
    if not bounds:
        sections = [text]
    else:
        bounds = [0] + bounds + [len(text)]
        sections = []
        # Preamble before the first heading, then one chunk per heading.
        if bounds[1] > 0:
            sections.append(text[0:bounds[1]])
        for i in range(1, len(bounds) - 1):
            sections.append(text[bounds[i]:bounds[i + 1]])

    chunks = []
    for s in sections:
        s = s.strip()
        if not s:
            continue
        if len(s) <= MAX_SUBCHUNK:
            chunks.append(s)
            continue
        step = MAX_SUBCHUNK - SUBCHUNK_OVERLAP
        for start in range(0, len(s), step):
            c = s[start:start + MAX_SUBCHUNK].strip()
            if c:
                chunks.append(c)
    return chunks or [text[:MAX_SUBCHUNK]]


def build_index(docs: list[dict]) -> tuple[list[str], list[str], np.ndarray]:
    """docs: [{"id": ..., "text": ...}, ...].
    Returns (chunk_texts, chunk_doc_ids, vecs)."""
    chunk_texts, chunk_doc_ids = [], []
    for doc in docs:
        for c in chunk_by_section(doc["text"]):
            chunk_texts.append(c)
            chunk_doc_ids.append(doc["id"])
    vecs = np.array(vertex.embed(chunk_texts))
    return chunk_texts, chunk_doc_ids, vecs


def load_or_build_index(
    cache_path: Path, docs: list[dict]
) -> tuple[list[str], list[str], np.ndarray]:
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        return cached["texts"], cached["doc_ids"], np.array(cached["vecs"])
    chunk_texts, chunk_doc_ids, vecs = build_index(docs)
    cache_path.write_text(json.dumps({
        "texts": chunk_texts, "doc_ids": chunk_doc_ids, "vecs": vecs.tolist(),
    }))
    return chunk_texts, chunk_doc_ids, vecs


def top_k_chunks(
    query: str, chunk_texts: list[str], chunk_doc_ids: list[str],
    chunk_vecs: np.ndarray, k: int = 5,
) -> list[tuple[str, str]]:
    query_vec = np.array(vertex.embed([query])[0])
    sims = chunk_vecs @ query_vec / (
        np.linalg.norm(chunk_vecs, axis=1) * np.linalg.norm(query_vec) + 1e-8
    )
    idx = np.argsort(-sims)[:k]
    return [(chunk_doc_ids[i], chunk_texts[i]) for i in idx]
