"""The trust catalog: which department vouches for which tool, and by whom.

`ToolTrust` alone cannot answer G4's question, whether department A can raise
trust for department B's tools, because it has no notion of department at
all: one instance, one flat set, shared by whoever holds it. The catalog is
departmental grants, keyed by (department, tool), and every vouch names the
department making it. A vouch naming a different department than the one
requesting it is not a bug to fix quietly, it is the attack G4 exists to
refuse: an actor in one department writing trust into another's boundary.

Offline stand-in for `departments/{dept}/grants/{tool}` in the contract's
Firestore layout. Wiring this to the real Agent Registry is future work; the
refusal rule and the audit trail are the part worth getting right first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from custody.origin import ToolTrust


@dataclass(frozen=True)
class Grant:
    """One department's vouch for one tool."""

    department: str
    tool: str
    vouched_by: str
    #: Caller-supplied, not `datetime.now()`: this module is pure, like the
    #: rest of the core, so it stays testable without a clock.
    vouched_at: str
    evidence: str = ""


@dataclass(frozen=True)
class Vouch:
    """A request to record a grant, made on behalf of `actor_department`.

    The grant's own `department` is what the actor is asking to change. They
    only ever match when an actor vouches for its own boundary; anything else
    is one department trying to write into another's.
    """

    actor_department: str
    grant: Grant


class Denial(str, Enum):
    WRONG_DEPARTMENT = "wrong_department"


@dataclass(frozen=True)
class VouchDecision:
    vouch: Vouch
    allowed: bool
    denial: Denial | None = None

    def reason(self) -> str:
        if self.allowed:
            return (
                f"{self.vouch.actor_department} vouched for "
                f"{self.vouch.grant.tool}"
            )
        return (
            f"{self.vouch.actor_department} cannot vouch for "
            f"{self.vouch.grant.department}'s tools"
        )


@dataclass
class TrustCatalog:
    """Departmental tool grants. Every decision is retained, allowed and
    denied alike, for the same reason `ExportGateway` keeps both: a catalog
    that records only its refusals cannot show what it let through.
    """

    _grants: dict[tuple[str, str], Grant] = field(default_factory=dict)
    decisions: list[VouchDecision] = field(default_factory=list)

    def request(self, vouch: Vouch) -> VouchDecision:
        if vouch.actor_department != vouch.grant.department:
            decision = VouchDecision(
                vouch=vouch, allowed=False, denial=Denial.WRONG_DEPARTMENT
            )
        else:
            self._grants[(vouch.grant.department, vouch.grant.tool)] = vouch.grant
            decision = VouchDecision(vouch=vouch, allowed=True)
        self.decisions.append(decision)
        return decision

    def denials(self) -> tuple[VouchDecision, ...]:
        return tuple(d for d in self.decisions if not d.allowed)

    def grants(self, department: str) -> tuple[Grant, ...]:
        return tuple(
            g for (dept, _tool), g in self._grants.items() if dept == department
        )

    def trust_for(self, department: str) -> ToolTrust:
        """The `ToolTrust` a department's `CustodyMemoryService` should use:
        exactly what has been vouched for that department, nothing inherited
        from any other. Computed fresh each call, not cached, because a grant
        recorded after construction must take effect and a later revocation
        must too.
        """
        return ToolTrust(trusted=frozenset(g.tool for g in self.grants(department)))
