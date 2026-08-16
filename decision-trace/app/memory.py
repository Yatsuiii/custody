"""Persistent memory writes — BUILD_SCOPE.md §3 steps 5-6, §11.

This is the one capability that separates DecisionTrace from a retrieval
demo: a developer can tell the system an old assumption changed, ask it to
record that, and have the record survive into a genuinely new session. A
candidate created here gets `PROPOSED` status and a `RECONSIDERS` edge to
whatever it's reconsidering — it deliberately does NOT change what
`resolve_active` reports as currently active. `RECONSIDERS` isn't in
`graph.DEACTIVATING_RELATIONSHIPS`/`REACTIVATING_RELATIONSHIPS`, so a
proposal can be recorded and recalled without silently overriding settled
history; only a later, separate acceptance step (out of MVP scope) would
do that.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Decision, DecisionStatus, Evidence, RelationshipType  # noqa: E402
from store import DecisionStore  # noqa: E402


def _candidate_id(target_id: str, changed_assumption: str) -> str:
    # Deterministic: the same reconsideration text against the same target
    # always yields the same id, so recording it twice updates rather than
    # duplicates.
    digest = hashlib.sha1(changed_assumption.encode()).hexdigest()[:8]
    return f"candidate-{target_id.replace('/', '-')}-{digest}"


def propose_reconsideration(
    store: DecisionStore,
    target_decision_id: str,
    changed_assumption: str,
    subject: str | None = None,
) -> Decision:
    """Records that a developer wants to reconsider `target_decision_id`
    because `changed_assumption` is no longer true. `changed_assumption`
    is stored verbatim as the candidate's rationale and evidence quote —
    it's a direct quote of what the developer said, not a summary, keeping
    the same no-fabrication discipline the rest of the product uses for
    mined evidence."""
    target = store.get(target_decision_id)
    if target is None:
        raise KeyError(f"unknown decision id: {target_decision_id}")

    candidate = Decision(
        id=_candidate_id(target_decision_id, changed_assumption),
        subject=subject or f"Reconsider: {target.subject}",
        current_status=DecisionStatus.PROPOSED,
        context=f"Reconsideration of {target_decision_id}",
        rationale=changed_assumption,
        evidence=[Evidence(
            type="conversation", url="", quote=changed_assumption,
        )],
        related_decisions=[(target_decision_id, RelationshipType.RECONSIDERS)],
    )
    store.save(candidate)
    return candidate
