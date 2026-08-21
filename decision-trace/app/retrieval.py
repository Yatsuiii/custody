"""Card-level retrieval — BUILD_SCOPE.md §10.

The falsifier (`decision-trace/RESULTS.md`) showed embedding retrieval
collapsing specifically on long, template-structured raw documents (KEP
files: 62% rationale-match, ~21% on the KEP subset alone) while handing
Gemini the same information as compact structured cards scored 100%. This
module is the direct, low-risk extrapolation the build scope called for:
embed the cards themselves — short, uniform, already stripped of the
boilerplate that broke raw-document retrieval — instead of inlining every
card unconditionally (which doesn't scale) or embedding source documents
(which the falsifier already falsified).

The other non-negotiable: a retrieved Decision is never handed back on its
own. BUILD_SCOPE.md §7 requires that a superseded/reverted decision never
silently reads as current guidance, so every `RetrievalCandidate` carries
its own `ActiveResolution` from Stage 1's deterministic resolver — there is
no code path that returns a Decision without it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import vertex  # noqa: E402

from graph import ActiveResolution, DecisionGraph, resolve_active  # noqa: E402
from models import Decision, DecisionStatus  # noqa: E402
from store import DecisionStore  # noqa: E402


@dataclass
class RetrievalCandidate:
    decision: Decision
    similarity: float
    resolution: ActiveResolution

    @property
    def is_current(self) -> bool:
        # A PROPOSED decision has no lineage edges yet (RECONSIDERS
        # deliberately isn't a lifecycle edge — see graph.py), so it
        # trivially resolves "active" in its own one-node lineage. That's
        # correct for resolve_active's graph semantics but wrong to present
        # as current guidance: a proposal that hasn't been accepted must
        # never read as settled, regardless of what the graph says.
        return (
            self.resolution.active_id == self.decision.id
            and self.decision.current_status != DecisionStatus.PROPOSED
        )


def render_card(d: Decision) -> str:
    """The compact, embeddable representation of a decision — deliberately
    the same shape as the falsifier's "structured" condition cards
    (`run_conditions.structured_cards_for_repo`), since that's the exact
    format proven to work."""
    lines = [f"Decision [{d.id}]", f"Subject: {d.subject}"]
    if d.context:
        lines.append(f"Context: {d.context}")
    if d.chosen_approach:
        lines.append(f"Chosen: {d.chosen_approach}")
    if d.rejected_alternatives:
        lines.append(f"Rejected alternatives: {'; '.join(d.rejected_alternatives)}")
    if d.rationale:
        lines.append(f"Rationale: {d.rationale}")
    if d.constraints:
        lines.append(f"Constraints: {'; '.join(d.constraints)}")
    lines.append(f"Status: {d.current_status.value}")
    return "\n".join(lines)


class DecisionIndex:
    """Embeds every decision in a store once, cached to disk so repeated
    searches and repeated test runs don't re-embed the whole store each time."""

    def __init__(self, store: DecisionStore, cache_path: Path | None = None):
        self.decisions: list[Decision] = store.list_all()
        self.graph = DecisionGraph(self.decisions)
        self.cache_path = cache_path
        self._vecs = self._load_or_build_vectors()

    def _cache_key(self) -> str:
        # Cache is only valid for exactly this set of decision ids+cards —
        # any change invalidates it rather than silently serving stale
        # vectors for a card whose text changed.
        return json.dumps(
            sorted((d.id, render_card(d)) for d in self.decisions)
        )

    def _load_or_build_vectors(self) -> np.ndarray:
        if self.cache_path and self.cache_path.exists():
            cached = json.loads(self.cache_path.read_text())
            if cached.get("key") == self._cache_key():
                return np.array(cached["vecs"])
        cards = [render_card(d) for d in self.decisions]
        vecs = np.array(vertex.embed(cards)) if cards else np.zeros((0, 1))
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps({
                "key": self._cache_key(), "vecs": vecs.tolist(),
            }))
        return vecs

    def reindex(self, store: DecisionStore) -> None:
        """Refreshes the index after the store changed (e.g. Stage 5's
        `memory.propose_reconsideration` added a new candidate). The cache
        key already covers the full decision set, so this naturally
        invalidates and rebuilds rather than serving a stale cache."""
        self.decisions = store.list_all()
        self.graph = DecisionGraph(self.decisions)
        self._vecs = self._load_or_build_vectors()

    def search(self, query: str, k: int = 5) -> list[RetrievalCandidate]:
        if not self.decisions:
            return []
        query_vec = np.array(vertex.embed([query])[0])
        sims = self._vecs @ query_vec / (
            np.linalg.norm(self._vecs, axis=1) * np.linalg.norm(query_vec) + 1e-8
        )
        top_idx = np.argsort(-sims)[:k]
        results = []
        for i in top_idx:
            decision = self.decisions[i]
            resolution = resolve_active(self.graph, decision.id)
            results.append(RetrievalCandidate(
                decision=decision, similarity=float(sims[i]), resolution=resolution,
            ))
        return results


def default_cache_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "card_embeddings.json"
