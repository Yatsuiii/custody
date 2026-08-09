"""The external action, and the only question asked before it leaves.

G3 names `export.send` as the guarded action because data egress is irreversible
in the way that matters: a ticket gets closed, exported records do not come back.

The gateway asks one thing. An external action must cite the remembered content
that authorized it, and every citation must be instruction-eligible. An action
citing nothing is refused too, because an unmotivated egress is exactly what a
laundered instruction produces once the memory behind it has been forgotten.

This is second-line defence and is meant to be redundant. If the split in
`service.py` is doing its job, no untrusted memory ever existed to be cited.
Belt and braces are appropriate here: the cost of the first line failing is
measured in data that has already left.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from custody.origin import CustodyRecord


class Denial(str, Enum):
    UNCITED = "uncited"
    UNTRUSTED_CITATION = "untrusted_citation"


@dataclass(frozen=True)
class Export:
    """A request to send content outside the trust boundary."""

    destination: str
    content: str
    #: The remembered items the agent is acting on. Empty is a refusal, not a
    #: default: something must have told the agent to do this.
    cited: tuple[CustodyRecord, ...] = ()


@dataclass(frozen=True)
class Decision:
    export: Export
    allowed: bool
    denial: Denial | None = None
    #: The citations that failed, so a refusal names what it objected to rather
    #: than only that it objected.
    offending: tuple[CustodyRecord, ...] = ()

    def reason(self) -> str:
        if self.allowed:
            return "every citation is instruction-eligible"
        if self.denial is Denial.UNCITED:
            return "no remembered content authorizes this export"
        tools = sorted({c.source_tool or "unknown" for c in self.offending})
        return f"cited content came from untrusted source(s): {', '.join(tools)}"


@dataclass
class ExportGateway:
    """Refuses egress that no trusted memory authorizes.

    Every decision is retained, allowed and denied alike. A gateway that records
    only its refusals cannot show that it let the right things through.
    """

    decisions: list[Decision] = field(default_factory=list)
    sent: list[Export] = field(default_factory=list)

    def request(self, export: Export) -> Decision:
        decision = self._judge(export)
        self.decisions.append(decision)
        if decision.allowed:
            self.sent.append(export)
        return decision

    def denials(self) -> tuple[Decision, ...]:
        return tuple(d for d in self.decisions if not d.allowed)

    @staticmethod
    def _judge(export: Export) -> Decision:
        if not export.cited:
            return Decision(export=export, allowed=False, denial=Denial.UNCITED)

        offending = tuple(
            c for c in export.cited if not c.instruction_eligible()
        )
        if offending:
            return Decision(
                export=export,
                allowed=False,
                denial=Denial.UNTRUSTED_CITATION,
                offending=offending,
            )
        return Decision(export=export, allowed=True)
