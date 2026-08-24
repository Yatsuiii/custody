"""Draft a human-readable verdict on one quarantined item. Never decides a fact.

Origin and trust are structural, decided in `custody/origin.py` off the event
graph, before anything here runs. This module only explains what an already
quarantined item attempted, for a human to read before they choose to demote
or revoke through the existing endpoints. `Verdict` therefore carries no
trust or origin field, and `draft_verdict` never imports `custody.catalog` or
`custody.graph` — there is no path from a Gemini response to a stored fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from custody.service import Quarantined

#: Injected by the caller: takes the quarantined text, returns a drafted
#: explanation. A live caller wires this to a Gemini call; tests wire it to
#: a fake. Kept as a plain callable, same seam `custody/service.py` already
#: uses for its own downstream ports, so this module stays pure and testable
#: without a network.
Explain = Callable[[str], str]


@dataclass(frozen=True)
class Verdict:
    """What a quarantined item attempted, drafted for a human. Not a fact."""

    department: str
    source_tool: str | None
    summary: str
    drafted_at: str


def draft_verdict(item: Quarantined, *, explain: Explain, drafted_at: str) -> Verdict:
    """Ask `explain` what the quarantined item's text attempted.

    `item.text` is exactly what `take_custody` withheld, so the verdict is
    grounded in the same content a human would see if they inspected the
    quarantine themselves — nothing here summarises a paraphrase of a
    paraphrase.
    """
    summary = explain(item.text)
    return Verdict(
        department=item.user_id,
        source_tool=item.record.source_tool,
        summary=summary,
        drafted_at=drafted_at,
    )
