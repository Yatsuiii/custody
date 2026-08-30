"""Draft a human-readable vouch request. Never grants trust.

The department and tool in a ``VouchDraft`` come from the requester's own
declared request. ``draft_vouch`` asks an injected ``Explain`` callable to
write the evidence a human can review, but it never calls ``/vouch`` and
never writes a catalog or graph fact. The existing deterministic endpoint
remains the only path that can record a grant.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


_EXPLICIT_TOOL = re.compile(
    r"\btool\s*[:=]\s*(?P<tool>[A-Za-z0-9][A-Za-z0-9_.-]*)",
    re.IGNORECASE,
)
_PLAIN_TOOL = re.compile(
    r"\b(?:need|request|onboard|approve|access to)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    r"(?P<tool>[A-Za-z0-9][A-Za-z0-9_.-]*(?:\s+[A-Za-z0-9][A-Za-z0-9_.-]*)*?)"
    r"\s+tool\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VouchDraft:
    """A proposed grant-shaped request, awaiting human submission."""

    department: str
    tool: str
    evidence: str
    drafted_at: str


def _requested_tool(request_text: str) -> str:
    """Read the tool identifier the requester named, without inventing one."""
    for pattern in (_EXPLICIT_TOOL, _PLAIN_TOOL):
        match = pattern.search(request_text)
        if match is not None:
            return match.group("tool").strip()
    raise ValueError(
        "request_text must name a tool, for example 'we need the crm tool'"
    )


def draft_vouch(
    request_text: str,
    *,
    department: str,
    explain: Callable[[str], str],
    drafted_at: str,
) -> VouchDraft:
    """Turn one department request into a reviewable, non-authoritative draft."""
    tool = _requested_tool(request_text)
    evidence = explain(request_text)
    return VouchDraft(
        department=department,
        tool=tool,
        evidence=evidence,
        drafted_at=drafted_at,
    )
