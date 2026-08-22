"""Runs the three conditions over the v2 benchmark cases.

Same three conditions, same model, same embedder, same TOP_K as v0. What
changes is the unit: a v2 KEP case is one *named alternative*, asked about
by name, rather than one KEP asked about as a set. See BENCHMARK_V2_SPEC.md.

The structured condition stores one first-class object per alternative
instead of a free-form multi-point card. That is the abstraction the
failure audit says v0 was missing: a card capped at six points cannot hold
a nine-alternative section, and a top-5 budget over one decision's points
silently drops whichever alternative the question was about.

The rendered card never contains `evidence_quote`. Rendering it would
reintroduce the original confound, where the string handed to the model was
the same string the judge graded against.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import rag_index
import vertex
from build_v2_cases import shares_6gram
from run_conditions import (
    TOP_K,
    build_query as v0_build_query,
    cite_str,
    get_repo_decoy_index,
)

DATA_DIR = Path(__file__).parent / "data"
V2_DIR = DATA_DIR / "v2"
RUNS_DIR = DATA_DIR / "runs_v2"
CARDS_PATH = V2_DIR / "cards.jsonl"
CARDS_INDEX = V2_DIR / "cards-index.json"
TARGET_INDEX_DIR = V2_DIR / "rag-target-index"

CARD_PROMPT_V2 = """A DecisionTrace record stores each engineering \
alternative as its own entry: what the option was, and why the project did \
not take it.

Decision: "{chosen}" is the approach that was ultimately used.
Alternative that was considered instead: "{name}"

Below is what the project's own design document says about that \
alternative. Write ONE sentence, at most 200 characters, in your own words, \
stating why this alternative was not adopted. If the document defers or \
postpones it rather than rejecting it, say that instead of inventing a \
rejection. Paraphrase: do not copy any contiguous phrase of more than a few \
words from the source. Output only the sentence, no preamble.

SOURCE
{body}"""


def load_cases() -> list[dict]:
    return [json.loads(line) for line in (V2_DIR / "cases.jsonl").open()]


def build_query(c: dict) -> str:
    """The developer question. Identical for all three conditions.

    Built only from repo, context/chosen and the alternative's name, never
    from the evidence span, so no condition can read its own grading key
    out of the question. Revert cases reuse v0's query verbatim, so that
    arm is unchanged between benchmarks."""
    if c["source"] == "revert_pair":
        return v0_build_query(c)
    return (
        f"I'm designing \"{c['context']}\" in {c['repo']} and I'm "
        f"considering using \"{c['alternative_name']}\". Was that approach "
        f"already considered on this project, and if so, why wasn't it "
        f"adopted?"
    )


def distill_reason(c: dict) -> str:
    prompt = CARD_PROMPT_V2.format(
        chosen=c["chosen"], name=c["alternative_name"],
        body=c["evidence_quote"],
    )
    return vertex.generate(prompt).strip().strip('"')


def build_cards(cases: list[dict], attempts: int = 3) -> list[dict]:
    """One card per case, cached. A card whose reason overlaps the graded
    span is regenerated, since that is a leak rather than a bad score."""
    done = {}
    if CARDS_PATH.exists():
        done = {json.loads(line)["case_id"]: json.loads(line)
                for line in CARDS_PATH.open()}
    cards, leaked = [], []
    for i, c in enumerate(cases):
        if c["case_id"] in done:
            cards.append(done[c["case_id"]])
            continue
        if c["source"] == "revert_pair":
            reason = c["reason"]
        else:
            print(f"[card {i + 1}/{len(cases)}] {c['case_id'][:70]}")
            for _ in range(attempts):
                reason = distill_reason(c)
                if not shares_6gram(reason, c["evidence_quote"]):
                    break
            else:
                leaked.append(c["case_id"])
        cards.append({"case_id": c["case_id"], "decision_id": c["decision_id"],
                      "reason": reason})
        with CARDS_PATH.open("a") as f:
            f.write(json.dumps(cards[-1]) + "\n")
    if leaked:
        raise SystemExit(f"cards still overlap their graded span: {leaked}")
    return cards


def card_text(c: dict, reason: str) -> str:
    """A first-class alternative record. Renders the abstractive reason,
    never the verbatim evidence span the judge grades against."""
    label = ("Rejected/Reverted" if c["source"] == "revert_pair"
             else "Alternative considered")
    return (
        f"Decision [{c['decision_id']}]\n"
        f"Context: {c['context']}\n"
        f"Chosen: {c['chosen']}\n"
        f"{label}: {c['alternative_name']}\n"
        f"Why it was not used: {reason}\n"
        f"Evidence: {cite_str(c)}"
    )


def get_card_index(cases: list[dict], cards: list[dict]):
    by_case = {k["case_id"]: k["reason"] for k in cards}
    docs = [{"id": c["case_id"], "text": card_text(c, by_case[c["case_id"]])}
            for c in cases]
    return rag_index.load_or_build_index(CARDS_INDEX, docs)


def run_structured(index, query: str) -> tuple[str, list[str]]:
    chunk_texts, chunk_ids, chunk_vecs = index
    retrieved = rag_index.top_k_chunks(query, chunk_texts, chunk_ids,
                                       chunk_vecs, k=TOP_K)
    prompt = (
        f"You have retrieved the following {len(retrieved)} decision cards "
        f"from this project's structured engineering-decision memory via "
        f"semantic search:\n\n"
        + "\n\n".join(t for _, t in retrieved)
        + f"\n\n---\n\nDeveloper question: {query}\n\nAnswer using only the "
        f"decision cards above. If a decision is relevant, cite its evidence "
        f"(PR/issue number or file path) and explain the reasoning. If "
        f"nothing above is relevant, say so."
    )
    return vertex.generate(prompt), [i for i, _ in retrieved]


def target_index(c: dict):
    """Per-decision index of the case's own source document, cached so the
    cases sharing a KEP embed it once instead of once each."""
    TARGET_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    doc = (V2_DIR / "sources" / f"{c['decision_id']}.txt").read_text()
    return rag_index.load_or_build_index(
        TARGET_INDEX_DIR / f"{c['decision_id']}.json",
        [{"id": "TARGET", "text": doc}],
    )


def run_rag(c: dict, query: str) -> tuple[str, list[str]]:
    d_texts, d_ids, d_vecs = get_repo_decoy_index(c["repo"])
    t_texts, t_ids, t_vecs = target_index(c)
    retrieved = rag_index.top_k_chunks(
        query, t_texts + d_texts, t_ids + d_ids,
        np.vstack([t_vecs, d_vecs]), k=TOP_K,
    )
    context = "\n\n---\n\n".join(f"[{i}]\n{t}" for i, t in retrieved)
    prompt = (
        f"You have retrieved the following {TOP_K} document chunks from this "
        f"repository's issue/PR/design-proposal history via semantic "
        f"search:\n\n{context}\n\n---\n\nDeveloper question: {query}\n\n"
        f"Answer using only the retrieved chunks above. If a retrieved chunk "
        f"cites a specific PR/issue number or file and explains a prior "
        f"decision relevant to the question, name it and explain the "
        f"reasoning. If nothing retrieved is relevant, say so."
    )
    return vertex.generate(prompt), [i for i, _ in retrieved]


def run_code_only(c: dict, query: str) -> str:
    prompt = (
        f"You are a coding assistant working in {c['repo']}. You have no "
        f"access to this project's issue tracker, PR history, or design "
        f"discussions — only the current state of the code.\n\n"
        f"Developer question: {query}\n\nAnswer as best you can."
    )
    return vertex.generate(prompt)


def _write(cond: str, case_id: str, payload: dict) -> None:
    out = RUNS_DIR / cond / f"{case_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))


def main() -> None:
    cases = load_cases()
    cards = build_cards(cases)
    index = get_card_index(cases, cards)
    errors = []
    for i, c in enumerate(cases):
        cid = c["case_id"]
        query = build_query(c)
        print(f"[{i + 1}/{len(cases)}] {cid[:78]}")
        for cond in ("code_only", "structured", "rag"):
            if (RUNS_DIR / cond / f"{cid}.json").exists():
                continue
            try:
                if cond == "code_only":
                    payload = {"query": query, "response": run_code_only(c, query)}
                elif cond == "structured":
                    resp, got = run_structured(index, query)
                    payload = {"query": query, "response": resp, "retrieved": got}
                else:
                    resp, got = run_rag(c, query)
                    payload = {"query": query, "response": resp, "retrieved": got}
            except Exception as e:  # recorded, never scored as correct
                errors.append({"case_id": cid, "condition": cond,
                               "error": f"{type(e).__name__}: {e}"})
                print(f"    API FAILURE {cond}: {type(e).__name__}")
                continue
            _write(cond, cid, payload)
    (V2_DIR / "api_errors.json").write_text(json.dumps(errors, indent=1))
    print(f"done; {len(errors)} API failures recorded")




# --- v2.1: unsupervised ingestion (BENCHMARK_V2_SPEC.md Amendment 2) ---
#
# v2 built one card per test case from that case's own graded span, which
# made retrieval an exact-key lookup against a store shaped like the answer
# sheet. Here the ingester reads a whole Alternatives section and decides
# for itself how many alternatives there are and what to call them. It
# never sees the case list or any per-case evidence span, so the store can
# be incomplete, can name things differently, and can get reasons wrong —
# which is what a real ingestion pipeline risks and what v2 never tested.

INGESTED_CARDS = V2_DIR / "cards_ingested.jsonl"
INGESTED_INDEX = V2_DIR / "cards-ingested-index.json"
RUNS_INGESTED = RUNS_DIR / "structured_ingested"

INGEST_PROMPT = """You are the ingestion step of an engineering \
decision-memory system. Read the "Alternatives" section of a real design \
document below and extract every distinct alternative approach it discusses.

The approach that was ultimately used is: "{chosen}"

For each alternative the section names, output one JSON object with:
  "name":   what the option is, as short as you can make it
  "reason": one sentence, at most 200 characters, in your own words, for \
why it was not adopted — or that it was deferred, if the document defers \
rather than rejects it

Rules:
- Extract every distinct alternative the section discusses. Do not stop \
early and do not merge distinct options into one.
- Do not invent alternatives that are not in the text. If the section \
gives no reason for one, set "reason" to "no reason stated in the source".
- Paraphrase. Do not copy contiguous phrases of more than a few words.

Output ONLY a JSON array, no other text.

ALTERNATIVES SECTION
{section}"""


def _parse_ingested(raw: str) -> list[dict]:
    import re
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [it for it in items
            if isinstance(it, dict) and it.get("name") and it.get("reason")]


def ingest_decision(d: dict, section: str) -> list[dict]:
    prompt = INGEST_PROMPT.format(chosen=d["chosen"], section=section[:12000])
    return _parse_ingested(vertex.generate(prompt))


def build_ingested_cards() -> list[dict]:
    """One ingestion call per KEP, plus the unchanged revert cards."""
    from build_v2_cases import canonical_alternatives
    from run_conditions import load_decisions

    if INGESTED_CARDS.exists():
        return [json.loads(line) for line in INGESTED_CARDS.open()]

    cases = load_cases()
    quotes = {}
    for c in cases:
        quotes.setdefault(c["decision_id"], []).append(c["evidence_quote"])
    by_case = {json.loads(line)["case_id"]: json.loads(line)
               for line in CARDS_PATH.open()}

    out, leaked = [], []
    for d in load_decisions():
        did = d["decision_id"]
        if d["source"] == "revert_pair":
            out.append({"card_id": did, "decision_id": did,
                        "alternative_name": d["rejected"],
                        "reason": by_case[did]["reason"], "source": "revert_pair"})
            continue
        source = (V2_DIR / "sources" / f"{did}.txt").read_text()
        can = canonical_alternatives(source)
        if not can:
            continue
        _, _, start, end = can
        print(f"[ingest] {did}")
        for i, item in enumerate(ingest_decision(d, source[start:end])):
            if any(shares_6gram(item["reason"], q) for q in quotes.get(did, [])):
                leaked.append(f"{did}#{i}")
            out.append({"card_id": f"{did}::ing::{i}", "decision_id": did,
                        "alternative_name": str(item["name"])[:200],
                        "reason": str(item["reason"])[:400],
                        "source": "kep_alternative"})
    with INGESTED_CARDS.open("w") as f:
        for c in out:
            f.write(json.dumps(c) + "\n")
    # Recorded rather than fatal. An ingested reason is paraphrased from a
    # section that contains every graded span for its decision, so a shared
    # six-word run is usually an unavoidable technical phrase rather than a
    # copied rationale. The count is published so a reader can judge; the
    # overlapping cards are listed so they can be read.
    (V2_DIR / "ingest_overlaps.json").write_text(json.dumps(leaked, indent=1))
    if leaked:
        print(f"WARNING: {len(leaked)} ingested cards share a 6-gram with a "
              f"graded span; see data/v2/ingest_overlaps.json")
    return out


def ingested_card_text(card: dict, d: dict) -> str:
    label = ("Rejected/Reverted" if card["source"] == "revert_pair"
             else "Alternative considered")
    return (
        f"Decision [{card['decision_id']}]\n"
        f"Context: {d['context']}\n"
        f"Chosen: {d['chosen']}\n"
        f"{label}: {card['alternative_name']}\n"
        f"Why it was not used: {card['reason']}\n"
        f"Evidence: {cite_str(d)}"
    )


def get_ingested_index(cards: list[dict]):
    from run_conditions import load_decisions
    byid = {d["decision_id"]: d for d in load_decisions()}
    docs = [{"id": c["card_id"], "text": ingested_card_text(c, byid[c["decision_id"]])}
            for c in cards]
    return rag_index.load_or_build_index(INGESTED_INDEX, docs)


def main_ingested() -> None:
    cases = load_cases()
    cards = build_ingested_cards()
    print(f"ingested store: {len(cards)} cards for {len(cases)} cases "
          f"({len(cards) / len(cases):.2f} per case)")
    index = get_ingested_index(cards)
    RUNS_INGESTED.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cases):
        out = RUNS_INGESTED / f"{c['case_id']}.json"
        if out.exists():
            continue
        print(f"[{i + 1}/{len(cases)}] {c['case_id'][:70]}")
        query = build_query(c)
        resp, got = run_structured(index, query)
        out.write_text(json.dumps(
            {"query": query, "response": resp, "retrieved": got}, indent=2))
    print("done")


if __name__ == "__main__":
    import sys



# --- v2.2: label the RAG target with its real identity (Amendment 3) ---
#
# v0 indexed the answer-bearing document as {"id": "TARGET"} while every
# decoy kept its real path or PR number, so the one document RAG had to
# cite was the one document whose identity was hidden. Measured: RAG
# retrieved the target in 65/65 KEP cases and stated a correct reason in
# 88% of them, but cited correctly in 49%. That gap was a label, not a
# capability. Only the identifier changes here; the cached vectors are
# reused, so this costs no re-embedding.

RUNS_RAG_LABELLED = RUNS_DIR / "rag_labelled"


def target_label(c: dict) -> str:
    cit = c["citation"]
    return (f"{c['repo']}#{cit['revert_pr']['number']}"
            if "original_pr" in cit else cit["file"]["path"])


def run_rag_labelled(c: dict, query: str) -> tuple[str, list[str]]:
    d_texts, d_ids, d_vecs = get_repo_decoy_index(c["repo"])
    t_texts, _, t_vecs = target_index(c)
    label = target_label(c)
    retrieved = rag_index.top_k_chunks(
        query, t_texts + d_texts, [label] * len(t_texts) + d_ids,
        np.vstack([t_vecs, d_vecs]), k=TOP_K,
    )
    context = "\n\n---\n\n".join(f"[{i}]\n{t}" for i, t in retrieved)
    prompt = (
        f"You have retrieved the following {TOP_K} document chunks from this "
        f"repository's issue/PR/design-proposal history via semantic "
        f"search:\n\n{context}\n\n---\n\nDeveloper question: {query}\n\n"
        f"Answer using only the retrieved chunks above. If a retrieved chunk "
        f"cites a specific PR/issue number or file and explains a prior "
        f"decision relevant to the question, name it and explain the "
        f"reasoning. If nothing retrieved is relevant, say so."
    )
    return vertex.generate(prompt), [i for i, _ in retrieved]


def main_rag_labelled() -> None:
    RUNS_RAG_LABELLED.mkdir(parents=True, exist_ok=True)
    cases = load_cases()
    for i, c in enumerate(cases):
        out = RUNS_RAG_LABELLED / f"{c['case_id']}.json"
        if out.exists():
            continue
        print(f"[{i + 1}/{len(cases)}] {c['case_id'][:70]}")
        query = build_query(c)
        resp, got = run_rag_labelled(c, query)
        out.write_text(json.dumps(
            {"query": query, "response": resp, "retrieved": got}, indent=2))
    print("done")


if __name__ == "__main__":
    import sys

    modes = {"ingested": main_ingested, "rag_labelled": main_rag_labelled}
    next((f for k, f in modes.items() if k in sys.argv), main)()
