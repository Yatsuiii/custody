"""Run a sequence of documents through each system, and record every step.

Three systems, one loop. The only differences are what carries forward between
documents and who computes the consequences:

    A0  node states carry forward, nothing else. Recomputes from the current
        description each time.
    A1  a canonical structured state carries forward: every relation it has
        recorded, and every human correction, handed back to it every step.
    B   relations carry forward as an event log, and the engine computes state.

The human correction is applied to all three at the same point and in the way
each can accept it, so no system is penalised for lacking a place to put it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from keel import ledger
from keel.propagate import evaluate

from .harness import AT, admit, base_program
from .sequence import CORRECTION, PROGRAM, Step, steps, true_relations
from .systems import (
    JUDGE_PROMPT,
    JUDGE_PROMPT_V2,
    JUDGE_SCHEMA,
    JUDGE_SCHEMA_V2,
    RULES,
    STRENGTH_RUBRIC,
    relation_for,
)
from .variants import Relation


@dataclass(frozen=True, slots=True)
class Snapshot:
    step: int
    document: str
    states: dict[str, str]
    because: dict[str, list[str]] = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    # Whether this system's own record still holds the relation the human
    # rejected. None when a system keeps no record that could hold one.
    corrected_present: bool | None = None


def genesis() -> tuple:
    return (ledger.event(ledger.PROGRAM_DECLARED, base_program(PROGRAM), AT),)


def _states(program) -> dict[str, str]:
    state = evaluate(program)
    return {node: entry.state for node, entry in state.nodes.items()}


def truth_trajectory(order: str) -> list[Snapshot]:
    """Apply only adjudicated RELATION pairs. AMBIGUOUS moves nothing."""
    log = genesis()
    trail = []
    for step in steps(order):
        relations = [
            Relation(target, relation, strength, sentence, 0.9)
            for target, relation, strength, sentence
            in true_relations(step.document.id)
        ]
        log, _ = admit(log, step.document, relations, "ground-truth")
        program = ledger.replay(log)
        state = evaluate(program)
        trail.append(Snapshot(
            step.index, step.document.id,
            {node: entry.state for node, entry in state.nodes.items()},
            {node: list(entry.because) for node, entry in state.nodes.items()},
        ))
    return trail


def run_b(order: str, model, boundary: str = "v1") -> list[Snapshot]:
    log = genesis()
    trail = []
    for step in steps(order):
        program = ledger.replay(log)
        assumptions = sorted(program.assumptions)
        calls, raw, relations = [], [], []
        for target in assumptions:
            answer, call = _judge(model, target,
                                  program.assumptions[target].text,
                                  step.document, boundary)
            calls.append(call)
            raw.append({"target": target, "answer": answer})
            found = relation_for(target, answer, boundary)
            if found is not None:
                relations.append(found)
        log, _ = admit(log, step.document, relations, "model:judge")
        if step.correction is not None:
            log = _reject_correction(log, step)
        replayed = ledger.replay(log)
        state = evaluate(replayed)
        trail.append(Snapshot(
            step.index, step.document.id,
            {node: entry.state for node, entry in state.nodes.items()},
            {node: list(entry.because) for node, entry in state.nodes.items()},
            calls, {"judgments": raw}, _holds_corrected(replayed),
        ))
    return trail


def _holds_corrected(program) -> bool:
    """Is the rejected relation live in this system's record right now?"""
    for edge in program.edges.values():
        claim = program.claims.get(edge.source)
        if (claim is not None and claim.source == CORRECTION["document"]
                and edge.target == CORRECTION["target"]
                and str(edge.status) != "REJECTED"):
            return True
    return False


def _reject_correction(log: tuple, step: Step) -> tuple:
    """Reject the specific relation the human reviewed, if it was proposed."""
    program = ledger.replay(log)
    target, source = step.correction["target"], step.document.id
    for edge in sorted(program.edges.values(), key=lambda e: e.id):
        claim = program.claims.get(edge.source)
        if (edge.target == target and claim is not None
                and claim.source == source
                and edge.created_by.startswith("model:")):
            return ledger.append(
                log, ledger.reject(edge, "human:program-owner",
                                   step.correction["note"], AT)
            )
    return log


def _judge(model, target: str, text: str, document, boundary: str):
    template = JUDGE_PROMPT if boundary == "v1" else JUDGE_PROMPT_V2
    schema = JUDGE_SCHEMA if boundary == "v1" else JUDGE_SCHEMA_V2
    call = model.ask(
        template.format(assumption_id=target, assumption_text=text,
                        title=document.title, sentences=document.numbered(),
                        rubric=STRENGTH_RUBRIC),
        schema,
    )
    try:
        answer = json.loads(call.text)
    except (json.JSONDecodeError, TypeError):
        answer = {"relation": "UNRELATED", "sentence": 0, "strength": "NONE",
                  "confidence": 0.0}
    return answer, {"kind": "judge", "target": target, **call.as_dict()}


STATE_SCHEMA = {
    "type": "object",
    "properties": {
        "changed": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "to": {"type": "string"},
                    "because": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["node", "to", "because"],
            },
        },
    },
    "required": ["changed"],
}

PERSISTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "relation": {"type": "string",
                                 "enum": ["SUPPORTS", "CONTRADICTS"]},
                    "strength": {"type": "string",
                                 "enum": ["STRONG", "MODERATE", "WEAK"]},
                    "sentence": {"type": "integer"},
                },
                "required": ["target", "relation", "strength", "sentence"],
            },
        },
        "changed": STATE_SCHEMA["properties"]["changed"],
    },
    "required": ["relations", "changed"],
}

STATELESS_PROMPT = """You maintain a research program's state as documents arrive.

This is the program right now, with each node's current state and every
structural relation between them:

{program}

A new document has arrived:

DOCUMENT {doc_id}: {title}
{sentences}

These are the rules that define every state:

{rules}

{rubric}

The confidence floor is 0.6.

List every node whose state changes because of this document, with the state it
now has and why, citing "{doc_id}:S<n>" for any sentence you relied on and the
id of any structural relation that carried the change. List only nodes that
actually change. If nothing changes, return an empty list.
"""

PERSISTENT_PROMPT = """You maintain a research program's state as documents arrive.

You keep a canonical record between documents. Here it is, including every
relation you have recorded so far and every correction the researcher has made:

{state}

A new document has arrived:

DOCUMENT {doc_id}: {title}
{sentences}

These are the rules that define every state:

{rules}

{rubric}

The confidence floor is 0.6. A correction the researcher has made is final for
the relation it names: do not re-add a relation that was rejected, though a
genuinely different document may support a new one.

Return two things. First, every evidence relation this document licenses, as a
target assumption, a polarity, a strength, and the sentence index. Second, every
node whose state changes, with the state it now has and why, citing
"{doc_id}:S<n>" for sentences and relation ids for structure. Return empty lists
if nothing applies.
"""


def _program_view(program, states: dict[str, str]) -> dict:
    return {
        "assumptions": [{"id": n, "text": program.assumptions[n].text,
                         "state": states[n]}
                        for n in sorted(program.assumptions)],
        "hypotheses": [{"id": n, "text": program.hypotheses[n].text,
                        "state": states[n]}
                       for n in sorted(program.hypotheses)],
        "experiments": [{"id": n, "text": program.experiments[n].text,
                         "state": states[n]}
                        for n in sorted(program.experiments)],
        "structure": [{"id": e.id, "relation": str(e.relation), "from": e.source,
                       "to": e.target}
                      for e in sorted(program.edges.values(), key=lambda e: e.id)
                      if str(e.relation) in ("DEPENDS_ON", "REQUIRES",
                                             "TESTS", "ESTABLISHES")],
    }


def run_a(order: str, model, persistent: bool,
          truth: list[Snapshot] | None = None) -> list[Snapshot]:
    """A0 when persistent is false, A1 when it is true."""
    program = ledger.replay(genesis())
    states = _states(program)
    recorded: list[dict] = []
    corrections: list[dict] = []
    trail = []
    for step in steps(order):
        view = _program_view(program, states)
        if persistent:
            payload = dict(view, recorded_relations=recorded,
                           corrections=corrections)
            prompt = PERSISTENT_PROMPT.format(
                state=json.dumps(payload, indent=1), doc_id=step.document.id,
                title=step.document.title, sentences=step.document.numbered(),
                rules=RULES, rubric=STRENGTH_RUBRIC,
            )
            schema = PERSISTENT_SCHEMA
        else:
            prompt = STATELESS_PROMPT.format(
                program=json.dumps(view, indent=1), doc_id=step.document.id,
                title=step.document.title, sentences=step.document.numbered(),
                rules=RULES, rubric=STRENGTH_RUBRIC,
            )
            schema = STATE_SCHEMA
        call = model.ask(prompt, schema)
        answer = _parse(call)
        because = {}
        for item in answer.get("changed", []):
            node = str(item.get("node", ""))
            states[node] = str(item.get("to", ""))
            because[node] = [str(r) for r in item.get("because", [])]
        for item in answer.get("relations", []):
            recorded.append(dict(item, document=step.document.id))
        if step.correction is not None:
            states, recorded, corrections = _correct(
                states, recorded, corrections, step, truth, persistent
            )
        held = None if not persistent else any(
            r.get("target") == CORRECTION["target"]
            and r.get("document") == CORRECTION["document"]
            for r in recorded
        )
        trail.append(Snapshot(
            step.index, step.document.id, dict(states), because,
            [{"kind": "state_update", **call.as_dict()}], answer, held,
        ))
    return trail


def _parse(call) -> dict:
    try:
        parsed = json.loads(call.text)
    except (json.JSONDecodeError, TypeError):
        return {"changed": [], "relations": []}
    return parsed if isinstance(parsed, dict) else {"changed": [],
                                                    "relations": []}


def _correct(states: dict, recorded: list, corrections: list, step: Step,
             truth: list[Snapshot] | None, persistent: bool):
    """The same correction every system gets, in the form each can accept."""
    target = step.correction["target"]
    if truth is not None:
        states[target] = truth[step.index].states[target]
    recorded = [r for r in recorded
                if not (r.get("target") == target
                        and r.get("document") == step.correction["document"])]
    if persistent:
        corrections = [*corrections, dict(CORRECTION)]
    return states, recorded, corrections
