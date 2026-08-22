"""Shared, answer-key-blind machinery for the authority benchmark.

The public history and the hidden adjudication are deliberately separate files.
Runners import this module, which never opens ``ground_truth.jsonl``.  The
deterministic grader is the only component allowed to join the two.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUTHORITY_DIR = ROOT / "data" / "authority"
RUNS_DIR = ROOT / "data" / "runs_authority"
PUBLIC_PATH = AUTHORITY_DIR / "timelines.json"
CHECKPOINTS_PATH = AUTHORITY_DIR / "checkpoints.jsonl"
GROUND_TRUTH_PATH = AUTHORITY_DIR / "ground_truth.jsonl"

sys.path.insert(0, str(ROOT / "app"))
from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402


@dataclass(frozen=True)
class VisibleCheckpoint:
    timeline: dict
    checkpoint: dict
    artifacts: tuple[dict, ...]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_public() -> tuple[list[dict], list[dict]]:
    return json.loads(PUBLIC_PATH.read_text()), read_jsonl(CHECKPOINTS_PATH)


def visible_checkpoint(timeline: dict, checkpoint: dict) -> VisibleCheckpoint:
    artifacts = tuple(
        artifact
        for artifact in timeline["artifacts"]
        if artifact["sequence"] <= checkpoint["visible_through"]
    )
    return VisibleCheckpoint(timeline, checkpoint, artifacts)


def render_artifact(artifact: dict) -> str:
    """Render exactly the public envelope supplied to both conditions."""
    fields = [
        f"Artifact ID: {artifact['artifact_id']}",
        f"Decision ID: {artifact['decision_id']}",
        f"Repository: {artifact['repository']}",
        f"Timestamp: {artifact['timestamp']}",
        f"Source URL: {artifact['source_url']}",
        f"Pinned revision: {artifact['pinned_revision']}",
        f"Lifecycle status: {artifact['status']}",
        f"Authority scope: {', '.join(artifact['scopes'])}",
    ]
    if artifact.get("replaces"):
        fields.append(f"Explicitly replaces: {', '.join(artifact['replaces'])}")
    if artifact.get("reverts"):
        fields.append(f"Explicitly reverts: {', '.join(artifact['reverts'])}")
    if artifact.get("implements"):
        fields.append(f"Explicitly implements: {', '.join(artifact['implements'])}")
    fields.extend(("Source text (verbatim excerpt):", artifact["source_text"]))
    return "\n".join(fields)


_STATUS_MAP = {
    "DRAFT": DecisionStatus.PROPOSED,
    "OPEN": DecisionStatus.PROPOSED,
    "FINAL": DecisionStatus.ACCEPTED,
    "ACCEPTED": DecisionStatus.ACCEPTED,
    "ACTIVE": DecisionStatus.ACCEPTED,
    "MERGED": DecisionStatus.IMPLEMENTED,
    "REVERT_MERGED": DecisionStatus.REVERTED,
    "WITHDRAWN": DecisionStatus.REVERTED,
    "REJECTED": DecisionStatus.REVERTED,
    "NOTE": DecisionStatus.PROPOSED,
}


def adapt_decisions(visible: VisibleCheckpoint) -> tuple[list[Decision], list[dict]]:
    """Convert source-explicit envelopes without consulting adjudication.

    Later snapshots replace earlier snapshots of the same logical decision.
    A proposal's ``Replaces`` header remains visible evidence but is not turned
    into a governing edge until its status is authoritative.  NOTE artifacts
    are evidence-only and do not become Decision records.
    """
    by_id: dict[str, Decision] = {}
    derivations: list[dict] = []
    authoritative = {"FINAL", "ACCEPTED", "ACTIVE", "MERGED", "REVERT_MERGED"}
    for artifact in visible.artifacts:
        status = artifact["status"]
        if status == "NOTE":
            derivations.append({
                "artifact_id": artifact["artifact_id"],
                "decision_id": None,
                "action": "evidence_only",
                "reason": "NOTE has no authority transition",
            })
            continue
        edges: list[tuple[str, RelationshipType]] = []
        if status in authoritative:
            edges.extend((target, RelationshipType.SUPERSEDES)
                         for target in artifact.get("replaces", []))
            edges.extend((target, RelationshipType.REVERTS)
                         for target in artifact.get("reverts", []))
        edges.extend((target, RelationshipType.IMPLEMENTS)
                     for target in artifact.get("implements", []))
        decision = Decision(
            id=artifact["decision_id"],
            subject=artifact["subject"],
            current_status=_STATUS_MAP[status],
            context=(f"Authority scopes: {', '.join(artifact['scopes'])}. "
                     f"{artifact['source_text']}"),
            chosen_approach=artifact["title"],
            rationale=artifact["source_text"],
            introduced_at=artifact["timestamp"],
            evidence=[Evidence(
                type=artifact["source_type"],
                url=artifact["source_url"],
                quote=artifact["source_text"],
            )],
            related_components=list(artifact["scopes"]),
            related_decisions=edges,
        )
        by_id[decision.id] = decision
        derivations.append({
            "artifact_id": artifact["artifact_id"],
            "decision_id": decision.id,
            "status": decision.current_status.value,
            "edges": [[target, rel.value] for target, rel in edges],
        })
    return list(by_id.values()), derivations


def rag_chunks(text: str, size: int = 1600, overlap: int = 200) -> list[str]:
    if len(text) <= size:
        return [text]
    step = size - overlap
    return [text[start:start + size] for start in range(0, len(text), step)]


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()


def normalized_public_history(visible: VisibleCheckpoint) -> list[dict]:
    """Canonical history used by equivalence tests and run manifests."""
    return [{
        "artifact_id": a["artifact_id"],
        "decision_id": a["decision_id"],
        "sequence": a["sequence"],
        "rendered_sha256": prompt_hash(render_artifact(a)),
    } for a in visible.artifacts]
