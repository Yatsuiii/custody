"""The two systems under comparison, given identical information.

Baseline A gets everything: the whole graph with current states, every edge id,
the numbered document, and the state rules written out in full. It is asked for
the impact directly. System B is asked one bounded question per assumption and
then runs the deterministic engine on the answers.

The rules text below mirrors `keel/policy.py`. If one changes without the other,
the benchmark is measuring the wrong thing, so they are kept adjacent in review
and the prose is deliberately mechanical rather than readable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from keel import ledger
from keel.model import Strength
from keel.propagate import evaluate

from .harness import Scenario, admit, confirm_new_edges, scenario_context
from .variants import Relation

RULES = """
An assumption's state comes only from evidence relations pointing at it. A
relation counts only if it is not REJECTED, its confidence is at least 0.6, and
its strength is MODERATE or STRONG. Then:
  - if counting contradictions and counting supports both exist: CONTESTED
  - else if only counting contradictions exist: INVALIDATED when at least one is
    STRONG and CONFIRMED by a human, otherwise CONTESTED
  - else if only counting supports exist: SUPPORTED
  - else: UNKNOWN

A hypothesis's state:
  - RETIRED only when a human decision retired it. Nothing else may retire one.
  - else WEAKENED if any assumption it DEPENDS_ON is INVALIDATED, or a counting
    STRONG CONFIRMED contradiction points directly at it
  - else REQUIRES_REVIEW if any assumption it DEPENDS_ON is CONTESTED, or any
    counting contradiction points directly at it
  - else ACTIVE

An experiment's state:
  - a RUNNING or COMPLETED experiment never changes state. Finished work is not
    re-judged.
  - a PLANNED experiment becomes INVALIDATED if any hypothesis it TESTS is
    RETIRED
  - else STALE if any assumption it REQUIRES is CONTESTED or INVALIDATED
  - else REDUNDANT if an assumption it ESTABLISHES has become SUPPORTED or
    INVALIDATED because of evidence that this same experiment did not produce
  - else it stays PLANNED
""".strip()

STRENGTH_RUBRIC = """
STRONG: direct, on-point evidence about the same claim, usually quantitative.
MODERATE: on-point but indirect, partial, or measured in a related setting.
WEAK: suggestive only, small sample, or about a neighbouring question.
""".strip()

# The v2 boundary, designed from the dev set's two diagnosed failures and from
# nothing else. Both were strength errors: a single-seed result on a different
# benchmark called MODERATE where the rubric says WEAK, and a correlation result
# read as evidence about a different property entirely. Neither is a failure of
# knowledge; both are a holistic label doing too much work at once. So v2 stops
# asking for the label. The model answers two narrower factual questions it is
# far better placed to answer, and code computes the strength from a table that
# a reader can check. This moves judgment out of the model without asking the
# model to be more careful, which is the only kind of prompt fix worth making.
STRENGTH_TABLE = {
    ("DIRECT", True): Strength.STRONG,
    ("DIRECT", False): Strength.MODERATE,
    ("ONE_STEP", True): Strength.MODERATE,
    ("ONE_STEP", False): Strength.WEAK,
    ("MULTI_STEP", True): Strength.WEAK,
    ("MULTI_STEP", False): Strength.WEAK,
}


def strength_from(distance: str, same_setting: bool) -> str:
    return str(STRENGTH_TABLE.get((distance, bool(same_setting)),
                                  Strength.WEAK))


JUDGE_SCHEMA_V2 = {
    "type": "object",
    "properties": {
        "relation": {"type": "string",
                     "enum": ["SUPPORTS", "CONTRADICTS", "UNRELATED"]},
        "sentence": {"type": "integer"},
        "inference_distance": {
            "type": "string",
            "enum": ["DIRECT", "ONE_STEP", "MULTI_STEP"],
        },
        "same_setting": {"type": "boolean"},
        "confidence": {"type": "number"},
    },
    "required": ["relation", "sentence", "inference_distance", "same_setting",
                 "confidence"],
}

JUDGE_PROMPT_V2 = """You are judging one relation, and nothing else.

ASSUMPTION UNDER TEST: {assumption_id}
"{assumption_text}"

DOCUMENT: {title}
{sentences}

Does any single sentence of this document support or contradict that
assumption? Answer with the one sentence that does it best, then answer two
factual questions about it. You are not asked how strong the evidence is:
that is computed from your two answers, not chosen by you.

inference_distance:
  DIRECT     the sentence reports a measurement of the same property the
             assumption is about.
  ONE_STEP   the sentence is about a different property, and one clear
             inference connects it to the assumption.
  MULTI_STEP connecting the sentence to the assumption needs a chain of
             further assumptions, any of which could fail.

same_setting: true if the measurement comes from the same benchmark, domain
and model family the assumption is about; false if it is transferred from a
different setting, a different task suite, or a single anecdotal run.

If no sentence bears on the assumption, answer relation UNRELATED, sentence 0,
inference_distance MULTI_STEP, same_setting false, confidence 0. Do not reason
about experiments or hypotheses: you have not been shown them.
"""

STRENGTH_TABLE_PROSE = """
Strength is computed, not chosen, from two properties of the evidence:
  DIRECT measurement of the same property, same setting        -> STRONG
  DIRECT measurement of the same property, transferred setting -> MODERATE
  one clear inference away, same setting                       -> MODERATE
  one clear inference away, transferred setting                -> WEAK
  a chain of further assumptions away                          -> WEAK
""".strip()

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "relation": {"type": "string",
                     "enum": ["SUPPORTS", "CONTRADICTS", "UNRELATED"]},
        "sentence": {"type": "integer"},
        "strength": {"type": "string",
                     "enum": ["STRONG", "MODERATE", "WEAK", "NONE"]},
        "confidence": {"type": "number"},
    },
    "required": ["relation", "sentence", "strength", "confidence"],
}

BASELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "changed": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node": {"type": "string"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "because": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["node", "from", "to", "because"],
            },
        },
    },
    "required": ["changed"],
}

JUDGE_PROMPT = """You are judging one relation, and nothing else.

ASSUMPTION UNDER TEST: {assumption_id}
"{assumption_text}"

DOCUMENT: {title}
{sentences}

Does any single sentence of this document directly support or directly
contradict that assumption? Answer with the one sentence that does it best.

Strength rubric:
{rubric}

If no sentence bears on the assumption, answer relation UNRELATED, sentence 0,
strength NONE, confidence 0. Do not reason about experiments, hypotheses, or
what should happen next: that is not your job and you have not been shown it.
"""

BASELINE_PROMPT = """You maintain a research program's state as new evidence arrives.

Here is the entire program, with each node's current state, and every relation
between them:

{context}

Here is a new document:

DOCUMENT: {title}
{sentences}

These are the rules that define every state:

{rules}

{rubric}

The confidence floor is 0.6. {confirmation}

List every node whose state changes because of this document, with the state it
had, the state it now has, and the justification for each: the ids of the
existing relations that carry the change, and "S<n>" for any sentence of the new
document you relied on. List only nodes that actually change. If nothing
changes, return an empty list.
"""

CONFIRMED_NOTE = (
    "The researcher has already confirmed the relations this document licenses, "
    "so treat them as CONFIRMED by a human."
)
UNCONFIRMED_NOTE = (
    "The relations this document licenses are machine-proposed and not yet "
    "confirmed by a human."
)


@dataclass(frozen=True, slots=True)
class Outcome:
    system: str
    changed: dict[str, str]
    because: dict[str, list[str]]
    calls: list[dict] = field(default_factory=list)
    raw: list[dict] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    boundary: str = "v1"

    def as_dict(self) -> dict:
        return {
            "system": self.system,
            "boundary": self.boundary,
            "changed": self.changed,
            "because": self.because,
            "calls": self.calls,
            "raw": self.raw,
            "failures": self.failures,
        }


def _parse(call, failures: list[str], label: str) -> dict | None:
    if call.error:
        failures.append(f"{label}:{call.error}")
        return None
    try:
        return json.loads(call.text)
    except (json.JSONDecodeError, TypeError):
        failures.append(f"{label}:unparseable")
        return None


def relation_for(target: str, answer: dict, boundary: str) -> Relation | None:
    """Turn one judgment into a relation, computing strength when v2 is on.

    Shared with the judge on purpose: it re-derives strength from the model's
    own two answers rather than trusting the strength the producer recorded.
    """
    if answer.get("relation") not in ("SUPPORTS", "CONTRADICTS"):
        return None
    strength = (answer.get("strength") if boundary == "v1"
                else strength_from(answer.get("inference_distance", ""),
                                   bool(answer.get("same_setting", False))))
    return Relation(
        target, str(answer["relation"]), str(strength),
        int(answer.get("sentence", 0)), float(answer.get("confidence", 0.0)),
    )


def run_system_b(scenario: Scenario, model, boundary: str = "v1") -> Outcome:
    """One bounded question per assumption, then the engine does the rest."""
    context = scenario_context(scenario)
    document = scenario.variant.document
    template = JUDGE_PROMPT if boundary == "v1" else JUDGE_PROMPT_V2
    schema = JUDGE_SCHEMA if boundary == "v1" else JUDGE_SCHEMA_V2
    calls, raw, failures, relations = [], [], [], []
    for assumption in context["assumptions"]:
        prompt = template.format(
            assumption_id=assumption["id"], assumption_text=assumption["text"],
            title=document.title, sentences=document.numbered(),
            rubric=STRENGTH_RUBRIC,
        )
        call = model.ask(prompt, schema)
        calls.append({"kind": "judge", "target": assumption["id"],
                      **call.as_dict()})
        answer = _parse(call, failures, f"judge:{assumption['id']}")
        if answer is None:
            continue
        raw.append({"target": assumption["id"], "answer": answer})
        relation = relation_for(assumption["id"], answer, boundary)
        if relation is not None:
            relations.append(relation)
    log, admission = admit(scenario.log, document, relations, "model:judge")
    if scenario.variant.confirmed:
        log = confirm_new_edges(log, admission)
    after = evaluate(ledger.replay(log))
    changed = {
        node: after.state_of(node) for node in after.nodes
        if scenario.before.state_of(node) != after.state_of(node)
    }
    return Outcome(
        "B", changed,
        {node: list(after.nodes[node].because) for node in changed},
        calls, raw, failures, boundary,
    )


def run_baseline_a(scenario: Scenario, model, boundary: str = "v1") -> Outcome:
    """Everything at once: the graph, the rules, the document, one answer."""
    context = scenario_context(scenario)
    document = scenario.variant.document
    rubric = (STRENGTH_RUBRIC if boundary == "v1"
              else STRENGTH_RUBRIC + "\n\n" + STRENGTH_TABLE_PROSE)
    prompt = BASELINE_PROMPT.format(
        context=json.dumps({k: v for k, v in context.items()
                            if k != "document"}, indent=1),
        title=document.title, sentences=document.numbered(), rules=RULES,
        rubric=rubric,
        confirmation=CONFIRMED_NOTE if scenario.variant.confirmed
        else UNCONFIRMED_NOTE,
    )
    failures: list[str] = []
    call = model.ask(prompt, BASELINE_SCHEMA)
    answer = _parse(call, failures, "baseline")
    changed, because = {}, {}
    for item in (answer or {}).get("changed", []):
        node = str(item.get("node", ""))
        changed[node] = str(item.get("to", ""))
        because[node] = [str(ref) for ref in item.get("because", [])]
    return Outcome(
        "A", changed, because,
        [{"kind": "baseline", **call.as_dict()}],
        [answer or {}], failures, boundary,
    )
