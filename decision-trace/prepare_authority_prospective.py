"""Freeze public prompts and retrieval exactly once before generation."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone

import vertex
from authority_prospective import (
    DATA,
    PREPARED,
    aggregate_authority,
    chunk_public_history,
    decisiontrace_prompt,
    evidence_artifacts,
    full_context,
    load_public,
    normalized_history,
    prompt_hash,
    rag_prompt,
    render_retrieved,
    select_chunks,
    visible_checkpoint,
)


def git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def main() -> None:
    if PREPARED.exists():
        raise SystemExit("preparation has already started; retrieval rerun forbidden")
    PREPARED.mkdir(parents=True, exist_ok=False)
    timelines, checkpoints = load_public()
    by_timeline = {item["timeline_id"]: item for item in timelines}
    prepared_rows = []
    embedding_items = 0
    embedding_requests = 0
    started = datetime.now(timezone.utc).isoformat()
    (PREPARED / "_PREPARATION_STARTED.json").write_text(json.dumps({
        "started_at": started,
        "git_sha": git_sha(),
        "run_once_guard": "Directory creation precedes the first embedding call.",
    }, indent=2) + "\n")
    for timeline in timelines:
        timeline_checkpoints = [cp for cp in checkpoints if cp["timeline_id"] == timeline["timeline_id"]]
        final_visible = visible_checkpoint(timeline, timeline_checkpoints[-1])
        all_chunks = chunk_public_history(final_visible)
        queries = [cp["question"] for cp in timeline_checkpoints]
        inputs = [item["text"] for item in all_chunks] + queries
        vectors = vertex.embed(inputs)
        embedding_items += len(inputs)
        embedding_requests += math.ceil(len(inputs) / 5)
        chunk_vectors = vectors[:len(all_chunks)]
        query_vectors = vectors[len(all_chunks):]
        for cp, query_vector in zip(timeline_checkpoints, query_vectors):
            visible = visible_checkpoint(timeline, cp)
            visible_chunk_count = sum(
                1 for chunk in all_chunks
                if any(a["artifact_id"] == chunk["artifact_id"] for a in visible.artifacts)
            )
            chunks = all_chunks[:visible_chunk_count]
            selected = select_chunks(chunks, chunk_vectors[:visible_chunk_count], query_vector)
            resolution, derivations = aggregate_authority(visible)
            dt_evidence = evidence_artifacts(visible, resolution.evidence_decision_ids)
            prompts = {
                "decisiontrace": decisiontrace_prompt(cp["question"], resolution, dt_evidence),
                "rag_embedding": rag_prompt(cp["question"], render_retrieved(selected), mode="embedding top-8"),
                "rag_full_context": rag_prompt(cp["question"], full_context(visible), mode="full visible context"),
            }
            universe = [item["artifact_id"] for item in visible.artifacts]
            prepared_rows.append({
                "checkpoint_id": cp["checkpoint_id"],
                "timeline_id": cp["timeline_id"],
                "question": cp["question"],
                "visible_history": normalized_history(visible),
                "condition_source_artifact_ids": {
                    "decisiontrace": universe,
                    "rag_embedding": universe,
                    "rag_full_context": universe,
                },
                "retrieved": [{key: value for key, value in item.items() if key != "text"}
                              for item in selected],
                "retrieved_artifact_ids": [item["artifact_id"] for item in selected],
                "deterministic_prediction": {
                    "authority_state": resolution.state,
                    "governing_decision_ids": list(resolution.governing_decision_ids),
                    "evidence_artifact_ids": [item["artifact_id"] for item in dt_evidence],
                    "resolver_explanation": resolution.explanation,
                    "derivations": derivations,
                },
                "prompts": prompts,
                "prompt_sha256": {condition: prompt_hash(prompt)
                                  for condition, prompt in prompts.items()},
                "expected_answer_fields_present": False,
            })
    for row in prepared_rows:
        (PREPARED / f"{row['checkpoint_id']}.json").write_text(json.dumps(row, indent=2) + "\n")
    manifest = {
        "git_sha": git_sha(),
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": vertex.EMBED_MODEL,
        "embedding_content_items": embedding_items,
        "embedding_endpoint_requests": embedding_requests,
        "checkpoints": len(prepared_rows),
        "prompt_template_sha256": hashlib.sha256(
            (DATA.parent.parent / "authority_prospective.py").read_bytes()
        ).hexdigest(),
    }
    (DATA / "prepare_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
