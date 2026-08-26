"""Fair context assembly for the action-compliance run package.

The assembler has one narrow responsibility: serialize the neutral source
bundle once, then append an arm-specific *derived* section.  The raw prefix is
therefore byte-identical for Arms A, B, and C.  It never accepts task metadata,
ground-truth labels, or a condition-specific source artifact.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bundle_source import LocalBundleSource


Condition = Literal["A", "B", "C"]


@dataclass(frozen=True)
class ContextEnvelope:
    """Serialized coding context and exact byte-level accounting."""

    condition: Condition
    raw_text: str
    context_text: str
    raw_content_sha256: str
    raw_prefix_sha256: str
    context_sha256: str
    raw_bytes: int
    context_bytes: int
    system_bytes: int
    total_bytes: int
    raw_words: int
    context_words: int
    estimated_tokens: int


def raw_content_sha256(source: LocalBundleSource) -> str:
    """Hash the requested prompt and artifact bytes, excluding presentation."""
    digest = hashlib.sha256()
    digest.update(b"requested_change\0")
    digest.update(source.requested_change().encode("utf-8"))
    for artifact in source.list_artifacts():
        digest.update(b"artifact\0")
        digest.update(artifact.source_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(artifact.content.encode("utf-8"))
    return digest.hexdigest()


def render_raw_context(source: LocalBundleSource) -> str:
    """Render the common raw evidence block in deterministic order.

    This serialization intentionally matches the source envelope used by the
    frozen Arm-B summary generator.  Filenames are neutral artifact IDs and
    metadata is derived only from the artifact itself.
    """
    parts = [source.requested_change(), "\n\nRAW SOURCE ARTIFACTS:\n"]
    for artifact in source.list_artifacts():
        parts.append(
            f"\n--- {artifact.source_id} ---\n"
            f"Source URL: {artifact.source_url or '(none)'}\n"
            f"Source title: {artifact.title or '(none)'}\n"
            + artifact.content
        )
    return "".join(parts)


def _word_count(text: str) -> int:
    return len(text.split())


def _estimate_tokens(text: str) -> int:
    # A tokenizer-independent conservative planning estimate.  Exact UTF-8
    # byte counts are stored alongside it; the real backend wrapper enforces
    # the same 8,192-token ceiling before launching an agent.
    return (len(text.encode("utf-8")) + 3) // 4


def assemble_context(
    source: LocalBundleSource,
    condition: Condition,
    system_prompt: str,
    summary: str | None = None,
    authority_proof: str | None = None,
    token_ceiling: int = 8192,
) -> ContextEnvelope:
    """Build one arm context while enforcing shared raw evidence.

    ``summary`` is permitted only for B and ``authority_proof`` only for C.
    The function does not inspect or accept benchmark task metadata.
    """
    if condition == "A" and (summary is not None or authority_proof is not None):
        raise ValueError("Arm A cannot receive a derived section")
    if condition == "B" and (summary is None or authority_proof is not None):
        raise ValueError("Arm B requires only its frozen summary")
    if condition == "C" and (authority_proof is None or summary is not None):
        raise ValueError("Arm C requires only its frozen AuthorityProof")

    raw = render_raw_context(source)
    raw_hash = raw_content_sha256(source)
    raw_prefix = raw
    if condition == "A":
        derived = ""
    elif condition == "B":
        derived = "\n\nDERIVED CONTEXT — ARM B SUMMARY\n" + (summary or "")
    else:
        derived = "\n\nDERIVED CONTEXT — ARM C AUTHORITYPROOF\n" + (authority_proof or "")
    context = raw + derived
    total = system_prompt + "\n\n" + context
    estimated_tokens = _estimate_tokens(total)
    if estimated_tokens > token_ceiling:
        raise ValueError(
            f"context exceeds shared ceiling: {estimated_tokens} > {token_ceiling}"
        )
    return ContextEnvelope(
        condition=condition,
        raw_text=raw,
        context_text=context,
        raw_content_sha256=raw_hash,
        raw_prefix_sha256=hashlib.sha256(raw_prefix.encode("utf-8")).hexdigest(),
        context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
        raw_bytes=len(raw.encode("utf-8")),
        context_bytes=len(context.encode("utf-8")),
        system_bytes=len(system_prompt.encode("utf-8")),
        total_bytes=len(total.encode("utf-8")),
        raw_words=_word_count(raw),
        context_words=_word_count(context),
        estimated_tokens=estimated_tokens,
    )


def proof_text(path: Path) -> str:
    """Read a frozen proof JSON with stable formatting."""
    value = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(value, sort_keys=True, indent=2) + "\n"
