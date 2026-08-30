"""Draft a human-readable incident notice. Never revokes anything.

The Auditor and graph already made the revocation decision before this module
runs. ``draft_notice`` receives only the public demotion fields it needs,
asks an injected ``Explain`` callable to phrase them for a human, and returns
a notice with no trust or origin field. The structural input protocol keeps
this drafting boundary independent of the catalog and graph modules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class DemotionLike(Protocol):
    """The read-only demotion fields needed to draft an incident notice."""

    department: str
    tool: str
    demoted_by: str
    demoted_at: str


@dataclass(frozen=True)
class Notice:
    """A post-revocation notice drafted for a human operator."""

    department: str
    tool: str
    summary: str
    drafted_at: str


def _demotion_text(demotion: DemotionLike) -> str:
    return (
        "The Auditor completed a revocation after this demotion.\n"
        f"Department: {demotion.department}\n"
        f"Tool: {demotion.tool}\n"
        f"Demotion recorded by: {demotion.demoted_by}\n"
        f"Demotion recorded at: {demotion.demoted_at}"
    )


def draft_notice(
    demotion: DemotionLike,
    *,
    explain: Callable[[str], str],
    drafted_at: str,
) -> Notice:
    """Phrase an already-completed revocation for a human to read or forward."""
    summary = explain(_demotion_text(demotion))
    return Notice(
        department=demotion.department,
        tool=demotion.tool,
        summary=summary,
        drafted_at=drafted_at,
    )
