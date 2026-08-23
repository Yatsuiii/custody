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

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, Sequence

from custody.authority import (
    AuthorityConflict,
    AuthorityDataError,
    AuthorityDecision,
    AuthorityEvaluator,
    AuthorityStore,
    AuthorityUnavailable,
    Capability,
    canonical_json_bytes,
    runtime_json_object,
)
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


@dataclass(frozen=True)
class AuthorityAction:
    """One consequential request; citations are supplied separately."""

    request_id: str
    action_scope: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id:
            raise AuthorityDataError("action.request_id must be a non-empty string")
        if not isinstance(self.action_scope, str) or not self.action_scope:
            raise AuthorityDataError("action.action_scope must be a non-empty string")
        object.__setattr__(
            self,
            "payload",
            runtime_json_object(self.payload, field="action.payload"),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "action_scope": self.action_scope,
            "payload": self.payload,
        }


class AuthorityDispatcher(Protocol):
    """The effectful endpoint kept behind the B7 current-state decision."""

    def dispatch(self, action: AuthorityAction) -> object: ...


@dataclass(frozen=True)
class AuthorityExecution:
    decision: AuthorityDecision
    dispatched: bool
    result: object | None = None


@dataclass(frozen=True)
class AuthorityGateway:
    """Linearize current B7 authority and own consequential dispatch."""

    store: AuthorityStore

    def execute(
        self,
        action_request: AuthorityAction,
        cited_record_ids: Sequence[str],
        dispatcher: AuthorityDispatcher,
    ) -> AuthorityExecution:
        if not isinstance(action_request, AuthorityAction):
            raise AuthorityDataError("gateway requires an AuthorityAction")
        if isinstance(cited_record_ids, (str, bytes)):
            raise AuthorityDataError("cited_record_ids must be a sequence")
        citations = tuple(cited_record_ids)
        if any(not isinstance(item, str) or not item for item in citations):
            raise AuthorityDataError("citations must be non-empty record IDs")
        if len(citations) != len(set(citations)):
            raise AuthorityDataError("citations must not contain duplicates")
        if not hasattr(dispatcher, "dispatch"):
            raise AuthorityDataError("gateway requires an action dispatcher")
        request_digest = hashlib.sha256(
            canonical_json_bytes(
                {
                    "action": action_request.as_dict(),
                    "cited_record_ids": list(citations),
                }
            )
        ).hexdigest()

        try:
            linearized = self.store.linearize_action(
                request_id=action_request.request_id,
                request_digest=request_digest,
                decide=lambda state: AuthorityEvaluator(
                    state=state, trust_store=self.store
                ).evaluate_action(
                    request_id=action_request.request_id,
                    request_digest=request_digest,
                    action_scope=action_request.action_scope,
                    cited_record_ids=citations,
                ),
            )
        except (AuthorityConflict, AuthorityUnavailable) as error:
            return AuthorityExecution(
                decision=AuthorityDecision(
                    request_id=action_request.request_id,
                    request_digest=request_digest,
                    action_scope=action_request.action_scope,
                    cited_record_ids=citations,
                    allowed=False,
                    effective_cap=Capability.NONE,
                    reason=(
                        "ACTION_REQUEST_ID_CONFLICT"
                        if isinstance(error, AuthorityConflict)
                        else "AUTHORITY_STATE_UNAVAILABLE"
                    ),
                    evaluated_record_ids=(),
                    support_root_key_digests=(),
                    record_reasons=(),
                ),
                dispatched=False,
            )

        if not linearized.decision.allowed or not linearized.created:
            return AuthorityExecution(linearized.decision, False)
        result = dispatcher.dispatch(action_request)
        return AuthorityExecution(linearized.decision, True, result)
