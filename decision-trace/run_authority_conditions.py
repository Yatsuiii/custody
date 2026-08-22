"""Prepare and run the two preregistered authority conditions.

``--prepare`` performs embeddings/retrieval and writes complete prompts without
generation.  ``--run`` consumes those immutable prepared prompts, invokes each
condition once, and never imports the answer key.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

import vertex
from authority_benchmark import (
    AUTHORITY_DIR, CHECKPOINTS_PATH, RUNS_DIR, adapt_decisions, load_public,
    normalized_public_history, prompt_hash, rag_chunks, render_artifact,
    visible_checkpoint,
)

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
import collaborate  # noqa: E402
from graph import ActiveResolution, DecisionGraph, resolve_active  # noqa: E402
from retrieval import DecisionIndex, RetrievalCandidate  # noqa: E402

PREPARED_DIR = AUTHORITY_DIR / "prepared"
TOP_K = 8

RAG_INSTRUCTIONS = """You are resolving organizational engineering authority from raw historical artifacts.
Answer what governs NOW at this checkpoint, not what is merely relevant or newest.
A proposal, open PR, implementation artifact, mention, or recent document is not
authoritative by itself. Respect explicit acceptance, replacement, withdrawal,
revert, and independent authority scopes. A code revert does not automatically
withdraw an accepted policy. If the visible evidence cannot establish one safe
answer, use UNRESOLVED; if it establishes that no decision governs, use
NO_GOVERNING_DECISION.

Return ONLY one JSON object:
{"authority_state":"GOVERNING|UNRESOLVED|NO_GOVERNING_DECISION",
 "governing_decision_id":"public decision ID or null",
 "evidence_ids":["public decision/artifact IDs"],
 "explanation":"brief source-grounded explanation"}
"""


class MemoryStore:
    def __init__(self, decisions): self._decisions = decisions
    def list_all(self): return list(self._decisions)


class PreparedIndex:
    def __init__(self, candidates): self._candidates = candidates
    def search(self, _question, k=5): return self._candidates[:k]


def _structured_prompt(candidates, question):
    trusted, _ = collaborate._challenge_candidates(candidates)
    context = "\n\n".join(collaborate._render_candidate(c) for c in trusted)
    if not trusted:
        return ""
    return (f"{collaborate._SYSTEM_INSTRUCTIONS}\n\nRetrieved decisions:\n\n"
            f"{context}\n\nQuestion: {question}")


def _candidate_payload(c):
    return {
        "decision_id": c.decision.id, "similarity": c.similarity,
        "resolution": asdict(c.resolution), "is_current": c.is_current,
    }


def _rag_retrieval(visible, question, cache_path):
    texts, ids = [], []
    for artifact in visible.artifacts:
        rendered = render_artifact(artifact)
        for chunk in rag_chunks(rendered):
            texts.append(chunk); ids.append(artifact["artifact_id"])
    key = prompt_hash(json.dumps(list(zip(ids, texts)), sort_keys=True))
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
    else:
        cached = {}
    embed_calls = 0
    if cached.get("key") == key:
        vecs = np.array(cached["vecs"])
    else:
        vecs = np.array(vertex.embed(texts)); embed_calls += 1
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"key": key, "vecs": vecs.tolist()}))
    qvec = np.array(vertex.embed([question])[0]); embed_calls += 1
    sims = vecs @ qvec / (np.linalg.norm(vecs, axis=1)*np.linalg.norm(qvec)+1e-8)
    indices = np.argsort(-sims)[:min(TOP_K, len(texts))]
    retrieved = [{"artifact_id": ids[i], "text": texts[i],
                  "similarity": float(sims[i])} for i in indices]
    context = "\n\n---\n\n".join(
        f"[{r['artifact_id']}]\n{r['text']}" for r in retrieved
    )
    prompt = (f"{RAG_INSTRUCTIONS}\n\nVISIBLE RAW HISTORY\n{context}\n\n"
              f"DEVELOPER QUESTION\n{question}")
    return retrieved, prompt, embed_calls


def prepare_one(timeline, checkpoint):
    visible = visible_checkpoint(timeline, checkpoint)
    decisions, derivations = adapt_decisions(visible)
    cache = AUTHORITY_DIR/"cache"/"structured"/f"{checkpoint['checkpoint_id']}.json"
    existed = cache.exists()
    index = DecisionIndex(MemoryStore(decisions), cache_path=cache)
    candidates = index.search(checkpoint["question"], k=TOP_K)
    structured_prompt = _structured_prompt(candidates, checkpoint["question"])
    rag_retrieved, rag_prompt, rag_embed_calls = _rag_retrieval(
        visible, checkpoint["question"],
        AUTHORITY_DIR/"cache"/"rag"/f"{checkpoint['checkpoint_id']}.json",
    )
    graph = DecisionGraph(decisions)
    resolver = {d.id: asdict(resolve_active(graph, d.id)) for d in decisions}
    payload = {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "timeline_id": checkpoint["timeline_id"],
        "question": checkpoint["question"],
        "authority_scope": checkpoint["authority_scope"],
        "visible_history": normalized_public_history(visible),
        "visible_artifact_text": [render_artifact(a) for a in visible.artifacts],
        "derivations": derivations, "resolver": resolver,
        "structured": {
            "retrieved": [_candidate_payload(c) for c in candidates],
            "prompt": structured_prompt, "prompt_sha256": prompt_hash(structured_prompt),
        },
        "rag": {
            "retrieved": rag_retrieved, "prompt": rag_prompt,
            "prompt_sha256": prompt_hash(rag_prompt),
        },
        "embedding_call_units": (0 if existed else 1) + 1 + rag_embed_calls,
    }
    out = PREPARED_DIR/f"{checkpoint['checkpoint_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2)+"\n")
    return payload


def parse_rag(raw):
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"authority_state":"PARSE_ERROR","governing_decision_id":None,
                "evidence_ids":[],"parse_error":"no JSON object"}
    try: item = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return {"authority_state":"PARSE_ERROR","governing_decision_id":None,
                "evidence_ids":[],"parse_error":str(exc)}
    state = item.get("authority_state")
    if state not in {"GOVERNING","UNRESOLVED","NO_GOVERNING_DECISION"}:
        state = "PARSE_ERROR"
    did = item.get("governing_decision_id")
    evidence = item.get("evidence_ids", [])
    return {"authority_state":state,
            "governing_decision_id":did if isinstance(did,str) else None,
            "evidence_ids":[x for x in evidence if isinstance(x,str)]
                            if isinstance(evidence,list) else [],
            "explanation":item.get("explanation", "")}


def parse_structured(answer, prepared):
    current = sorted({claim.decision_id for claim in answer.claims
                      if claim.category == collaborate.ClaimCategory.CURRENT_ACTIVE_DECISION
                      and claim.decision_id})
    if len(current) == 1:
        state, did = "GOVERNING", current[0]
    elif len(current) > 1:
        state, did = "UNRESOLVED", None
    elif any(v["ambiguous"] for v in prepared["resolver"].values()):
        state, did = "UNRESOLVED", None
    else:
        state, did = "NO_GOVERNING_DECISION", None
    return {
        "authority_state": state, "governing_decision_id": did,
        "evidence_ids": current,
        "claims": [{"text":c.text,"category":c.category.value,
                    "decision_id":c.decision_id} for c in answer.claims],
        "candidates_considered": answer.candidates_considered,
    }


def run_one(timeline, checkpoint):
    prepared = json.loads((PREPARED_DIR/f"{checkpoint['checkpoint_id']}.json").read_text())
    visible = visible_checkpoint(timeline, checkpoint)
    decisions, _ = adapt_decisions(visible)
    by_id = {d.id:d for d in decisions}
    candidates = []
    for row in prepared["structured"]["retrieved"]:
        candidates.append(RetrievalCandidate(
            decision=by_id[row["decision_id"]], similarity=row["similarity"],
            resolution=ActiveResolution(**row["resolution"]),
        ))
    api_errors = []
    try:
        structured_answer = collaborate.answer(
            checkpoint["question"], PreparedIndex(candidates), k=TOP_K
        )
        structured = parse_structured(structured_answer, prepared)
    except Exception as exc:
        api_errors.append({"condition":"decisiontrace","error":f"{type(exc).__name__}: {exc}"})
        structured = {"authority_state":"API_ERROR","governing_decision_id":None,
                      "evidence_ids":[]}
    try:
        rag_raw = vertex.generate(prepared["rag"]["prompt"])
        rag = parse_rag(rag_raw); rag["raw_response"] = rag_raw
    except Exception as exc:
        api_errors.append({"condition":"rag","error":f"{type(exc).__name__}: {exc}"})
        rag = {"authority_state":"API_ERROR","governing_decision_id":None,
               "evidence_ids":[]}
    for condition, result in (("decisiontrace",structured),("rag",rag)):
        out = RUNS_DIR/condition/f"{checkpoint['checkpoint_id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "checkpoint_id":checkpoint["checkpoint_id"],
            "timeline_id":checkpoint["timeline_id"],
            "question":checkpoint["question"],
            "prompt_sha256":prepared[condition if condition == "rag" else "structured"]["prompt_sha256"],
            "visible_history":prepared["visible_history"],
            "prediction":result,
        },indent=2)+"\n")
    return api_errors


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("mode",choices=("prepare","run"))
    args=parser.parse_args()
    timelines, checkpoints=load_public(); by_t={t["timeline_id"]:t for t in timelines}
    manifest={"mode":args.mode,"model":vertex.GEN_MODEL,"embedder":vertex.EMBED_MODEL,
              "checkpoints":len(checkpoints),"generation_calls":0,"embedding_call_units":0,
              "errors":[]}
    for i, checkpoint in enumerate(checkpoints,1):
        print(f"[{i}/{len(checkpoints)}] {checkpoint['checkpoint_id']}", flush=True)
        if args.mode == "prepare":
            payload=prepare_one(by_t[checkpoint["timeline_id"]],checkpoint)
            manifest["embedding_call_units"] += payload["embedding_call_units"]
        else:
            errors=run_one(by_t[checkpoint["timeline_id"]],checkpoint)
            manifest["generation_calls"] += 2
            manifest["errors"].extend(errors)
    (AUTHORITY_DIR/f"{args.mode}_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__": main()
