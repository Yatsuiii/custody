"""The append-only log, and the fold that turns it back into a program.

Nothing in this system edits state. Evidence arriving, a human confirming a
relation, a hypothesis being retired: each is an event, appended, and the
current program is what you get by replaying them in order. That is what makes
"why is E4 stale" answerable months later, and what makes a demo reproducible
rather than a recording.

An event's identity is its content, not its arrival time. Ingesting the same
evidence twice therefore appends nothing the second time, so idempotency is a
property of the identifier rather than a check somebody has to remember to
write.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .model import Edge, EdgeStatus, Program, digest
from .program import (
    claim_from_dict,
    decision_from_dict,
    edge_from_dict,
    from_dict,
    source_from_dict,
    validate,
)

PROGRAM_DECLARED = "program_declared"
SOURCE_ADDED = "source_added"
CLAIM_ADDED = "claim_added"
EDGE_PROPOSED = "edge_proposed"
EDGE_CONFIRMED = "edge_confirmed"
EDGE_REJECTED = "edge_rejected"
DECISION_RECORDED = "decision_recorded"

COLLECTIONS = (
    "questions", "hypotheses", "assumptions", "experiments",
    "sources", "claims", "edges", "decisions",
)


@dataclass(frozen=True, slots=True)
class Event:
    id: str
    kind: str
    at: str
    payload: dict

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "at": self.at,
                "payload": self.payload}


def event(kind: str, payload: dict, at: str = "") -> Event:
    return Event("v-" + digest([kind, payload])[:16], kind, at, payload)


def append(log: tuple[Event, ...], new: Event) -> tuple[Event, ...]:
    if any(existing.id == new.id for existing in log):
        return log
    return (*log, new)


def extend(log: tuple[Event, ...], events: list[Event]) -> tuple[Event, ...]:
    for item in events:
        log = append(log, item)
    return log


def replay(log: tuple[Event, ...]) -> Program:
    """Fold the log into a program, and refuse to return a broken one.

    The program under construction is mutated in place here and nowhere else:
    this function owns it until it is returned, after which it is read-only by
    convention throughout the codebase.
    """
    program = Program()
    for item in log:
        _apply(program, item)
    problems = validate(program)
    if problems:
        raise ValueError("replay produced a broken program: " + "; ".join(problems))
    return program


def _apply(program: Program, item: Event) -> None:
    payload = item.payload
    if item.kind == PROGRAM_DECLARED:
        declared = from_dict(payload)
        for name in COLLECTIONS:
            getattr(program, name).update(getattr(declared, name))
    elif item.kind == SOURCE_ADDED:
        source = source_from_dict(payload)
        program.sources[source.id] = source
    elif item.kind == CLAIM_ADDED:
        claim = claim_from_dict(payload)
        program.claims[claim.id] = claim
    elif item.kind == EDGE_PROPOSED:
        edge = edge_from_dict(payload)
        program.edges[edge.id] = edge
    elif item.kind in (EDGE_CONFIRMED, EDGE_REJECTED):
        _restatus(program, payload["edge"], item.kind)
    elif item.kind == DECISION_RECORDED:
        decision = decision_from_dict(payload)
        program.decisions[decision.id] = decision
    else:
        raise ValueError(f"unknown event kind {item.kind}")


def _restatus(program: Program, identifier: str, kind: str) -> None:
    edge = program.edges.get(identifier)
    if edge is None:
        raise ValueError(f"{kind} names an edge that does not exist: {identifier}")
    status = EdgeStatus.CONFIRMED if kind == EDGE_CONFIRMED else EdgeStatus.REJECTED
    program.edges[identifier] = replace(edge, status=status)


def confirm(edge: Edge, actor: str, at: str = "") -> Event:
    return event(EDGE_CONFIRMED, {"edge": edge.id, "actor": actor}, at)


def reject(edge: Edge, actor: str, reason: str, at: str = "") -> Event:
    return event(
        EDGE_REJECTED, {"edge": edge.id, "actor": actor, "reason": reason}, at
    )


def log_as_dicts(log: tuple[Event, ...]) -> list[dict]:
    return [item.as_dict() for item in log]
