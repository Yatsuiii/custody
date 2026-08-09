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

#: ADK's own memory-retrieval tool (`google.adk.tools.load_memory_tool`). A
#: response from it is not new content, it is a citation of something already
#: written, so `take_custody` attributes it by resolving it rather than by
#: asking whether the tool is vouched for.
DEFAULT_RETRIEVAL_TOOLS: frozenset[str] = frozenset({"load_memory"})


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
    #: Identifies this record within a `custody.graph.CustodyGraph`. Empty for
    #: records built outside `take_custody`, e.g. in tests of downstream
    #: consumers that never join the graph.
    id: str = ""
    #: Ids of the records this one was derived from. Populated for a DERIVED
    #: model turn, pointing at the untrusted arrival that tainted it. This is
    #: the graph edge retroactive revocation walks.
    derived_from: tuple[str, ...] = ()

    def instruction_eligible(self) -> bool:
        """Whether this may enter context the model treats as instructions.

        The only question the retrieval side asks. Kept on the record so the
        rule lives with the data rather than being re-derived by every caller.
        """
        return self.trust is Trust.TRUSTED


class RecordResolver(Protocol):
    """Something that can say whether content already has a custody record.

    `custody.graph.CustodyGraph` satisfies this structurally. Named here
    rather than imported from `graph.py` because `graph.py` already depends on
    this module; the resolver is the narrow slice `take_custody` needs, not
    the whole graph.
    """

    def resolve(self, content_sha256: str) -> CustodyRecord | None: ...


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


def take_custody(
    events: Iterable[Event],
    tools: ToolTrust | None = None,
    *,
    resolver: RecordResolver | None = None,
    retrieval_tools: frozenset[str] = DEFAULT_RETRIEVAL_TOOLS,
) -> Custody:
    """Attribute every piece of content in a session to where it came from.

    Pure with `resolver` omitted, and that is still most of what this does:
    the one place the product's claim is actually made, and therefore the one
    place worth testing exhaustively. With a resolver, a response from a
    retrieval tool is checked against it before falling back to `tools`: a
    match means the content is not new, it is a citation of something already
    admitted, possibly in an earlier session or a different department, and it
    inherits that record's trust and lineage rather than starting fresh. This
    has to happen inline rather than as a pass over the result, because the
    verdict feeds taint tracking for every turn later in the same invocation.
    """
    trust = tools or ToolTrust()
    admitted: list[Admitted] = []
    refused: list[Rejected] = []
    #: Invocations in which untrusted content has already appeared, keyed to
    #: (record id, tool name) of the arrival that caused it. Model turns later
    #: in the same invocation are derived from that record.
    tainted: dict[str, tuple[str, str]] = {}
    #: The most recent tool response record id in each invocation, regardless
    #: of trust. A model turn following it is derived from it on the graph even
    #: when the tool is currently trusted: trust is a point-in-time judgement,
    #: and a tool trusted today can be demoted tomorrow, at which point this
    #: edge is what lets revocation find the restatement.
    lineage: dict[str, str] = {}

    for index, event in enumerate(events):
        content = getattr(event, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue

        author = getattr(event, "author", "") or ""
        invocation = getattr(event, "invocation_id", "") or ""

        for part_index, part in enumerate(parts):
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
                        record_id=f"{invocation}:{index}:{part_index}",
                        response=response,
                        trust=trust,
                        tainted=tainted,
                        lineage=lineage,
                        resolver=resolver,
                        retrieval_tools=retrieval_tools,
                    ),
                )
            )

    return Custody(admitted=tuple(admitted), refused=tuple(refused))


def _attribute(
    *,
    text: str,
    author: str,
    invocation: str,
    record_id: str,
    response: FunctionResponse | None,
    trust: ToolTrust,
    tainted: dict[str, tuple[str, str]],
    lineage: dict[str, str],
    resolver: RecordResolver | None,
    retrieval_tools: frozenset[str],
) -> CustodyRecord:
    common = {
        "author": author,
        "invocation_id": invocation,
        "content_sha256": digest(text),
        "id": record_id,
    }

    if response is not None:
        tool = getattr(response, "name", None)
        cited = (
            resolver.resolve(common["content_sha256"])
            if resolver is not None and tool in retrieval_tools
            else None
        )
        if cited is not None:
            verdict = cited.trust
            derived_from: tuple[str, ...] = (cited.id,)
        else:
            verdict = trust.of(tool)
            derived_from = ()

        if verdict is Trust.UNTRUSTED:
            # The first untrusted arrival taints what follows in this invocation.
            tainted.setdefault(invocation, (record_id, tool or "unnamed-tool"))
        lineage[invocation] = record_id
        return CustodyRecord(
            origin=Origin.TOOL,
            trust=verdict,
            source_tool=tool,
            derived_from=derived_from,
            **common,
        )

    if author == USER_AUTHOR:
        return CustodyRecord(origin=Origin.USER, trust=Trust.TRUSTED, **common)

    source = tainted.get(invocation)
    if source is not None:
        source_id, source_tool = source
        # Chained to the most recent link, not always the original tool
        # response, so a restatement of a restatement is two hops on the
        # graph rather than two parallel edges into the same root.
        derived_from = (lineage.get(invocation, source_id),)
        lineage[invocation] = record_id
        return CustodyRecord(
            origin=Origin.DERIVED,
            trust=Trust.UNTRUSTED,
            source_tool=source_tool,
            derived_from=derived_from,
            **common,
        )
    derived_from = (lineage[invocation],) if invocation in lineage else ()
    if derived_from:
        lineage[invocation] = record_id
    return CustodyRecord(
        origin=Origin.MODEL,
        trust=Trust.TRUSTED,
        derived_from=derived_from,
        **common,
    )


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
