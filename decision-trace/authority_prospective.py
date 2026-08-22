"""Answer-key-blind machinery for the prospective authority run.

The module deliberately has no path or loader for adjudication.  It imports the
already-frozen adapter and resolver, adds only the preregistered multi-scope
orchestration, and builds equivalent public histories for all conditions.
"""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from authority_benchmark import (
    VisibleCheckpoint,
    adapt_decisions,
    prompt_hash,
    rag_chunks,
    render_artifact as frozen_render_artifact,
    visible_checkpoint,
)


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "prospective"
RUNS = ROOT / "data" / "runs_authority_prospective"
PUBLIC_PATH = DATA / "timelines.json"
CHECKPOINTS_PATH = DATA / "checkpoints.jsonl"
PREPARED = DATA / "prepared"
TOP_K = 8
MAX_RETRIEVED_CHARS = 12_800
MAX_FULL_CONTEXT_CHARS = 100_000

sys.path.insert(0, str(ROOT / "app"))
from authority import resolve_authority  # noqa: E402


@dataclass(frozen=True)
class AggregateResolution:
    state: str
    governing_decision_ids: tuple[str, ...]
    evidence_decision_ids: tuple[str, ...]
    explanation: str


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def load_public() -> tuple[list[dict], list[dict]]:
    return json.loads(PUBLIC_PATH.read_text()), read_jsonl(CHECKPOINTS_PATH)


def render_artifact(artifact: dict) -> str:
    """Expose role in addition to every field exposed by the frozen renderer."""
    return frozen_render_artifact(artifact) + f"\nDecision role: {artifact['role']}"


def normalized_history(visible: VisibleCheckpoint) -> list[dict]:
    return [{
        "artifact_id": artifact["artifact_id"],
        "decision_id": artifact["decision_id"],
        "sequence": artifact["sequence"],
        "rendered_sha256": prompt_hash(render_artifact(artifact)),
    } for artifact in visible.artifacts]


def aggregate_authority(visible: VisibleCheckpoint) -> tuple[AggregateResolution, list[dict]]:
    decisions, derivations = adapt_decisions(visible)
    resolutions = [
        resolve_authority(decisions, scope)
        for scope in visible.checkpoint["authority_scopes"]
    ]
    ids = tuple(sorted({
        result.governing_decision_id for result in resolutions
        if result.governing_decision_id is not None
    }))
    evidence = tuple(sorted({item for result in resolutions for item in result.evidence_ids}))
    explanation = " | ".join(
        f"{scope}: {result.explanation}"
        for scope, result in zip(visible.checkpoint["authority_scopes"], resolutions)
    )
    if any(result.state == "UNRESOLVED" for result in resolutions):
        state, ids = "UNRESOLVED", ()
    elif not ids:
        state = "NO_GOVERNING_DECISION"
    elif len(ids) == 1:
        state = "GOVERNING"
    else:
        state = "MULTIPLE_GOVERNING"
    return AggregateResolution(state, ids, evidence, explanation), derivations


def evidence_artifacts(visible: VisibleCheckpoint,
                       decision_ids: tuple[str, ...]) -> list[dict]:
    latest = {}
    for artifact in visible.artifacts:
        if artifact["decision_id"] in decision_ids:
            latest[artifact["decision_id"]] = artifact
    return [latest[item] for item in decision_ids if item in latest]


RAG_INSTRUCTION = """You resolve CURRENT organizational decision authority from a visible engineering history.
Authority is not relevance or recency. A newer item may be only proposed, a mention may carry no transition, an implementation may not govern policy, and a rollback may govern code without restoring an older policy. Respect explicit scope, lifecycle status, decision role, and replaces/reverts/implements evidence. Multiple explicitly queried scopes may have parallel governing decisions. If visible evidence genuinely conflicts or is insufficient, answer UNRESOLVED; if no accepted or implemented decision governs, answer NO_GOVERNING_DECISION. Use only public decision and artifact IDs exactly as shown.

Return exactly one JSON object with these keys:
{"authority_state":"GOVERNING | MULTIPLE_GOVERNING | UNRESOLVED | NO_GOVERNING_DECISION","governing_decision_ids":["public decision id"],"evidence_artifact_ids":["public artifact id"],"explanation":"brief source-grounded reason"}
"""


def rag_prompt(question: str, history_text: str, *, mode: str) -> str:
    return (
        RAG_INSTRUCTION
        + f"\nContext mode: {mode}. Artifacts are ordered source records visible at this checkpoint.\n\n"
        + history_text
        + f"\n\nDeveloper question: {question}\n"
    )


def decisiontrace_prompt(question: str, resolution: AggregateResolution,
                         artifacts: list[dict]) -> str:
    evidence = "\n\n".join(render_artifact(item) for item in artifacts) or "(none)"
    return (
        "You are DecisionTrace's explanation layer. The byte-frozen deterministic authority resolver "
        "has already determined the structured result below. Do not change, omit, or second-guess its "
        "state or IDs. Explain it briefly from only the supplied evidence. Return only the explanation.\n\n"
        f"Authority state: {resolution.state}\n"
        f"Governing decision IDs: {json.dumps(list(resolution.governing_decision_ids))}\n"
        f"Resolver explanation: {resolution.explanation}\n\nEvidence:\n{evidence}\n\n"
        f"Developer question: {question}\n"
    )


def chunk_public_history(visible: VisibleCheckpoint) -> list[dict]:
    chunks = []
    ordinal = 0
    for artifact in visible.artifacts:
        rendered = render_artifact(artifact)
        for index, text in enumerate(rag_chunks(rendered, size=1600, overlap=200)):
            chunks.append({
                "ordinal": ordinal,
                "artifact_id": artifact["artifact_id"],
                "chunk_index": index,
                "text": text,
            })
            ordinal += 1
    return chunks


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    denom = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / denom if denom else 0.0


def select_chunks(chunks: list[dict], chunk_vectors: list[list[float]],
                  query_vector: list[float]) -> list[dict]:
    scored = [
        item | {"similarity": cosine(vector, query_vector)}
        for item, vector in zip(chunks, chunk_vectors)
    ]
    ranked = sorted(scored, key=lambda item: (-item["similarity"], item["ordinal"]))[:TOP_K]
    selected, used = [], 0
    for item in ranked:
        remaining = MAX_RETRIEVED_CHARS - used
        if remaining <= 0:
            break
        text = item["text"][:remaining]
        selected.append(item | {"text": text})
        used += len(text)
    return selected


def render_retrieved(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[Retrieved artifact {item['artifact_id']} chunk {item['chunk_index']}]\n{item['text']}"
        for item in chunks
    )


def full_context(visible: VisibleCheckpoint) -> str:
    text = "\n\n".join(render_artifact(artifact) for artifact in visible.artifacts)
    if len(text) > MAX_FULL_CONTEXT_CHARS:
        raise ValueError(f"full context is {len(text)} characters")
    return text


def parse_rag_response(raw: str, visible: VisibleCheckpoint) -> dict:
    result = {
        "authority_state": "MALFORMED",
        "governing_decision_ids": [],
        "evidence_artifact_ids": [],
        "explanation": "",
        "parse_error": None,
    }
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("no JSON object")
        parsed = json.loads(match.group(0))
        state = parsed["authority_state"]
        ids = parsed["governing_decision_ids"]
        evidence = parsed["evidence_artifact_ids"]
        if state not in {"GOVERNING", "MULTIPLE_GOVERNING", "UNRESOLVED",
                         "NO_GOVERNING_DECISION"}:
            raise ValueError("invalid authority_state")
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise ValueError("governing_decision_ids is not a string list")
        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
            raise ValueError("evidence_artifact_ids is not a string list")
        visible_decisions = {a["decision_id"] for a in visible.artifacts}
        visible_artifacts = {a["artifact_id"] for a in visible.artifacts}
        if not set(ids) <= visible_decisions:
            raise ValueError("unknown governing decision ID")
        if not set(evidence) <= visible_artifacts:
            raise ValueError("unknown evidence artifact ID")
        result.update({
            "authority_state": state,
            "governing_decision_ids": sorted(set(ids)),
            "evidence_artifact_ids": sorted(set(evidence)),
            "explanation": str(parsed.get("explanation", "")),
        })
    except Exception as exc:
        result["parse_error"] = f"{type(exc).__name__}: {exc}"
    return result
