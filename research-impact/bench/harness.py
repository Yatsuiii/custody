"""Turn a variant into a scenario: the state before, and the truth after.

Ground truth is the engine applied to the relations the variant declares as
real. That is a bounded circularity and it is stated in the artifact: the
experiment asks whether unconstrained reasoning reproduces a written rule set,
not whether the rule set is the right one. Both systems are judged against the
same construction, from the same starting state, with the same document.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from keel import ingest, ledger
from keel.model import Relation as EdgeRelation
from keel.model import Source
from keel.propagate import GraphState, evaluate

from .variants import Document, Variant

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
AT = "2026-08-15T12:00:00Z"


@dataclass(frozen=True, slots=True)
class Scenario:
    variant: Variant
    program: dict
    log: tuple
    before: GraphState
    truth_state: GraphState
    truth_changed: dict[str, str]
    truth_because: dict[str, tuple[str, ...]]
    sentence_edges: dict[int, str]

    def unchanged_nodes(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.before.nodes) - set(self.truth_changed)))


def base_program(name: str = "arc_program.json") -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def apply_mutations(program: dict, mutations: tuple[dict, ...]) -> dict:
    mutated = json.loads(json.dumps(program))
    for change in mutations:
        if change["op"] == "add_assumption":
            mutated["assumptions"].append(
                {"id": change["id"], "text": change["text"]}
            )
        elif change["op"] == "add_edge":
            mutated["edges"].append(
                {k: v for k, v in change.items() if k != "op"}
            )
        elif change["op"] == "remove_edge":
            mutated["edges"] = [
                e for e in mutated["edges"]
                if not (e["relation"] == change["relation"]
                        and e["source"] == change["source"]
                        and e["target"] == change["target"])
            ]
        else:
            raise ValueError(f"unknown mutation {change['op']}")
    return mutated


def source_of(document: Document) -> Source:
    return Source(document.id, document.title, document.text, "paper", None)


def proposals_for(document: Document, relations, proposed_by: str) -> list:
    """Relations are addressed by sentence index, so an excerpt cannot drift."""
    proposals = []
    for item in relations:
        if not 0 <= item.sentence < len(document.sentences):
            continue
        proposals.append(ingest.proposals_from([{
            "target": item.target,
            "relation": item.relation,
            "strength": item.strength,
            "confidence": item.confidence,
            "excerpt": document.sentences[item.sentence],
            "claim": document.sentences[item.sentence],
        }], proposed_by)[0])
    return proposals


def admit(log: tuple, document: Document, relations, proposed_by: str) -> tuple:
    program = ledger.replay(log)
    admission = ingest.ingest(
        program, source_of(document), proposals_for(document, relations,
                                                    proposed_by), AT,
    )
    return ledger.extend(log, list(admission.events)), admission


def confirm_new_edges(log: tuple, admission) -> tuple:
    program = ledger.replay(log)
    for record in admission.admitted:
        edge = program.edges.get(record["edge"])
        if edge is not None:
            log = ledger.append(log, ledger.confirm(edge, "human:program-owner", AT))
    return log


def _apply_prior(log: tuple, steps: tuple[dict, ...]) -> tuple:
    for step in steps:
        if step["op"] == "evidence":
            log, _ = admit(log, step["document"], step["relations"],
                           "model:prior-judge")
        elif step["op"] == "reject":
            log = _reject(log, step)
        elif step["op"] == "retire":
            log = ledger.append(log, ledger.event(ledger.DECISION_RECORDED, {
                "id": f"d-retire-{step['hypothesis']}",
                "actor": "human:program-owner",
                "kind": "retire_hypothesis",
                "target": step["hypothesis"],
                "rationale": step["rationale"],
            }, AT))
        else:
            raise ValueError(f"unknown prior step {step['op']}")
    return log


def _reject(log: tuple, step: dict) -> tuple:
    program = ledger.replay(log)
    edge = next(
        e for e in sorted(program.edges.values(), key=lambda e: e.id)
        if e.target == step["target"]
        and e.relation is EdgeRelation(step["relation"])
        and e.created_by.startswith("model:")
    )
    return ledger.append(
        log, ledger.reject(edge, "human:program-owner", step["reason"], AT)
    )


def build(variant: Variant) -> Scenario:
    program = apply_mutations(base_program(variant.program), variant.mutations)
    log = _apply_prior(
        (ledger.event(ledger.PROGRAM_DECLARED, program, AT),), variant.prior
    )
    before = evaluate(ledger.replay(log))

    truth_log, admission = admit(log, variant.document, variant.truth,
                                 "ground-truth")
    if variant.confirmed:
        truth_log = confirm_new_edges(truth_log, admission)
    truth_program = ledger.replay(truth_log)
    truth_state = evaluate(truth_program)
    changed = {
        node: truth_state.state_of(node) for node in truth_state.nodes
        if before.state_of(node) != truth_state.state_of(node)
    }
    return Scenario(
        variant, program, log, before, truth_state, changed,
        {node: truth_state.nodes[node].because for node in changed},
        {item.sentence: record["edge"]
         for item, record in zip(variant.truth, admission.admitted, strict=False)},
    )


def scenario_context(scenario: Scenario) -> dict:
    """Everything a system may see. Both systems get exactly this."""
    program = ledger.replay(scenario.log)
    return {
        "assumptions": [
            {"id": node, "text": program.assumptions[node].text,
             "state": scenario.before.state_of(node)}
            for node in sorted(program.assumptions)
        ],
        "hypotheses": [
            {"id": node, "text": program.hypotheses[node].text,
             "state": scenario.before.state_of(node)}
            for node in sorted(program.hypotheses)
        ],
        "experiments": [
            {"id": node, "text": program.experiments[node].text,
             "state": scenario.before.state_of(node)}
            for node in sorted(program.experiments)
        ],
        "edges": [
            {"id": edge.id, "relation": str(edge.relation), "from": edge.source,
             "to": edge.target, "status": str(edge.status),
             "strength": None if edge.strength is None else str(edge.strength),
             "confidence": edge.confidence, "asserted_by": edge.created_by}
            for edge in sorted(program.edges.values(), key=lambda e: e.id)
        ],
        "claims": [
            {"id": claim.id, "source": claim.source, "excerpt": claim.excerpt}
            for claim in sorted(program.claims.values(), key=lambda c: c.id)
        ],
        "document": {
            "id": scenario.variant.document.id,
            "title": scenario.variant.document.title,
            "sentences": list(scenario.variant.document.sentences),
        },
        "researcher_confirms_new_relations": scenario.variant.confirmed,
    }
