"""Where a piece of remembered content came from, decided by structure.

The whole project rests on this being a fact rather than a judgement. An ADK
event exposes its function responses structurally, so "this text arrived from a
tool" is readable off the event graph and never inferred by a model. If that
ever stops being true, the determinism claim goes with it.

The non-obvious rule is taint propagation. A model turn that follows an
untrusted tool response inside the same invocation is *derived* from it: when an
agent summarises a hostile page, the summary carries the hostility and the raw
tool response is often discarded. Labelling only the raw output would let the
laundered version through, which is the attack.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol, Sequence

#: The author string ADK uses for a human turn. Anything else is an agent name.
USER_AUTHOR = "user"


class Origin(str, Enum):
    """Where content entered the system, not who stored it."""

    USER = "user"
    MODEL = "model"
    TOOL = "tool"
    #: Model output produced after untrusted input in the same invocation.
    DERIVED = "derived"


class Trust(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class Refusal(str, Enum):
    """Why content cannot be admitted to memory.

    Refusing is deliberate. Content that cannot be attributed must not be stored
    as trusted, because absence of evidence would become a clean bill of health,
    which is the failure this system exists to prevent.
    """

    NO_INVOCATION = "no_invocation"
    NO_AUTHOR = "no_author"


class FunctionResponse(Protocol):
    name: str | None


class Part(Protocol):
    """Structural view of `google.genai.types.Part`.

    Duck-typed rather than imported so the core needs no SDK, and so a test can
    supply a two-field stand-in.
    """

    text: str | None
    function_response: FunctionResponse | None


class Content(Protocol):
    parts: Sequence[Part] | None


class Event(Protocol):
    """Structural view of `google.adk.events.Event`."""

    author: str
    invocation_id: str
    content: Content | None


@dataclass(frozen=True)
class CustodyRecord:
    """The provenance of one remembered item.

    `author` answers who appended it, which ADK already records. Everything else
    answers where the content came from, which it does not.
    """

    origin: Origin
    trust: Trust
    author: str
    invocation_id: str
    content_sha256: str
    #: The tool whose response introduced this content, or tainted the model
    #: turn that produced it. Absent for user turns and clean model turns.
    source_tool: str | None = None

    def instruction_eligible(self) -> bool:
        """Whether this may enter context the model treats as instructions.

        The only question the retrieval side asks. Kept on the record so the
        rule lives with the data rather than being re-derived by every caller.
        """
        return self.trust is Trust.TRUSTED


@dataclass(frozen=True)
class Admitted:
    text: str
    record: CustodyRecord
    #: Which event in the session carried this. Taint is a session-level
    #: property, so custody is taken over the whole session and callers need
    #: this to map a verdict back to the event it belongs to.
    event_index: int = 0


@dataclass(frozen=True)
class Rejected:
    text: str
    reason: Refusal
    event_index: int = 0


@dataclass(frozen=True)
class Custody:
    """Everything a session yielded, admitted and refused alike."""

    admitted: tuple[Admitted, ...] = ()
    refused: tuple[Rejected, ...] = ()

    def instruction_eligible(self) -> tuple[Admitted, ...]:
        return tuple(a for a in self.admitted if a.record.instruction_eligible())

    def quarantined(self) -> tuple[Admitted, ...]:
        return tuple(a for a in self.admitted if not a.record.instruction_eligible())


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ToolTrust:
    """Which tools are believed. Everything absent is untrusted.

    Default-deny rather than default-allow: a tool nobody has vouched for is
    reached over the network, and its output is attacker-controlled in exactly
    the cases that matter.
    """

    trusted: frozenset[str] = field(default_factory=frozenset)

    def of(self, tool: str | None) -> Trust:
        if tool is not None and tool in self.trusted:
            return Trust.TRUSTED
        return Trust.UNTRUSTED


def take_custody(events: Iterable[Event], tools: ToolTrust | None = None) -> Custody:
    """Attribute every piece of content in a session to where it came from.

    Pure: no clock, no network, no store. The one place the product's claim is
    actually made, and therefore the one place worth testing exhaustively.
    """
    trust = tools or ToolTrust()
    admitted: list[Admitted] = []
    refused: list[Rejected] = []
    #: Invocations in which untrusted content has already appeared. Model turns
    #: later in the same invocation are derived from it.
    tainted: dict[str, str] = {}

    for index, event in enumerate(events):
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue

        author = getattr(event, "author", "") or ""
        invocation = getattr(event, "invocation_id", "") or ""

        for part in parts:
            response = getattr(part, "function_response", None)
            text = (
                _response_text(response)
                if response is not None
                else getattr(part, "text", None)
            )
            if not text:
                continue

            if not invocation:
                refused.append(
                    Rejected(text, Refusal.NO_INVOCATION, event_index=index)
                )
                continue
            if not author:
                refused.append(Rejected(text, Refusal.NO_AUTHOR, event_index=index))
                continue

            admitted.append(
                Admitted(
                    text=text,
                    event_index=index,
                    record=_attribute(
                        text=text,
                        author=author,
                        invocation=invocation,
                        response=response,
                        trust=trust,
                        tainted=tainted,
                    ),
                )
            )

    return Custody(admitted=tuple(admitted), refused=tuple(refused))


def _attribute(
    *,
    text: str,
    author: str,
    invocation: str,
    response: FunctionResponse | None,
    trust: ToolTrust,
    tainted: dict[str, str],
) -> CustodyRecord:
    common = {
        "author": author,
        "invocation_id": invocation,
        "content_sha256": digest(text),
    }

    if response is not None:
        tool = getattr(response, "name", None)
        verdict = trust.of(tool)
        if verdict is Trust.UNTRUSTED:
            # The first untrusted arrival taints what follows in this invocation.
            tainted.setdefault(invocation, tool or "unnamed-tool")
        return CustodyRecord(
            origin=Origin.TOOL, trust=verdict, source_tool=tool, **common
        )

    if author == USER_AUTHOR:
        return CustodyRecord(origin=Origin.USER, trust=Trust.TRUSTED, **common)

    source = tainted.get(invocation)
    if source is not None:
        return CustodyRecord(
            origin=Origin.DERIVED,
            trust=Trust.UNTRUSTED,
            source_tool=source,
            **common,
        )
    return CustodyRecord(origin=Origin.MODEL, trust=Trust.TRUSTED, **common)


def _response_text(response: FunctionResponse) -> str:
    """The payload a tool returned, flattened to the text a model would read."""
    payload = getattr(response, "response", None)
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return " ".join(str(v) for v in payload.values())
    return str(payload)
