"""Reading a program from a document, and refusing to read a broken one.

Validation here is not defensive coding. A dependency edge pointing at the wrong
kind of node, or an excerpt that does not occur in the document it claims to
quote, would still evaluate to some state, and that state would be confidently
wrong. Both are refused at the door instead.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from .model import (
    EVIDENCE_RELATIONS,
    STRUCTURAL_RELATIONS,
    Assumption,
    Claim,
    Decision,
    Edge,
    EdgeStatus,
    Experiment,
    ExperimentState,
    Hypothesis,
    Program,
    Question,
    Relation,
    Source,
    Strength,
    claim_id,
    digest,
    edge_id,
    normalize,
)

# Which node kind each end of a structural edge must name.
STRUCTURAL_SHAPE = {
    Relation.DEPENDS_ON: ("hypotheses", "assumptions"),
    Relation.REQUIRES: ("experiments", "assumptions"),
    Relation.TESTS: ("experiments", "hypotheses"),
    Relation.ESTABLISHES: ("experiments", "assumptions"),
}


def load(path: str | Path) -> Program:
    return from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def from_dict(payload: dict) -> Program:
    program = Program(
        questions={q["id"]: Question(q["id"], q["text"])
                   for q in payload.get("questions", [])},
        hypotheses={h["id"]: Hypothesis(h["id"], h["text"], h["question"])
                    for h in payload.get("hypotheses", [])},
        assumptions={a["id"]: Assumption(a["id"], a["text"])
                     for a in payload.get("assumptions", [])},
        experiments={e["id"]: _experiment(e) for e in payload.get("experiments", [])},
        sources={s["id"]: source_from_dict(s) for s in payload.get("sources", [])},
        decisions={d["id"]: decision_from_dict(d)
                   for d in payload.get("decisions", [])},
    )
    refs: dict[str, str] = {}
    for raw in payload.get("claims", []):
        claim = claim_from_dict(raw)
        program.claims[claim.id] = claim
        refs[raw.get("ref", claim.id)] = claim.id
    for raw in payload.get("edges", []):
        edge = edge_from_dict(raw, refs)
        program.edges[edge.id] = edge
    problems = validate(program)
    if problems:
        raise ValueError("program is not well formed: " + "; ".join(problems))
    return program


def _experiment(raw: dict) -> Experiment:
    return Experiment(
        raw["id"], raw["text"], ExperimentState(raw["lifecycle"]),
        int(raw.get("cost_days", 0)),
    )


def source_from_dict(raw: dict) -> Source:
    return Source(
        raw["id"], raw["title"], raw["text"], raw.get("kind", "paper"),
        raw.get("produced_by"),
    )


def claim_from_dict(raw: dict) -> Claim:
    identifier = claim_id(raw["source"], raw["excerpt"])
    return Claim(identifier, raw["source"], raw["text"], raw["excerpt"])


def decision_from_dict(raw: dict) -> Decision:
    return Decision(
        raw["id"], raw["actor"], raw["kind"], raw["target"],
        raw.get("rationale", ""), raw.get("at", ""),
    )


def edge_from_dict(raw: dict, refs: dict[str, str] | None = None) -> Edge:
    relation = Relation(raw["relation"])
    source = (refs or {}).get(raw["source"], raw["source"])
    strength = Strength(raw["strength"]) if raw.get("strength") else None
    identifier = raw.get("id") or edge_id(relation, source, raw["target"])
    return Edge(
        identifier, relation, source, raw["target"],
        EdgeStatus(raw.get("status", "CONFIRMED")), strength,
        float(raw.get("confidence", 1.0)), raw.get("created_by", "human"),
        raw.get("created_at", ""),
    )


def validate(program: Program) -> list[str]:
    problems: list[str] = []
    for claim in program.claims.values():
        source = program.sources.get(claim.source)
        if source is None:
            problems.append(f"claim {claim.id} quotes unknown source {claim.source}")
        elif normalize(claim.excerpt) not in normalize(source.text):
            problems.append(f"claim {claim.id} excerpt is not in {claim.source}")
    for edge in program.edges.values():
        problems.extend(_edge_problems(program, edge))
    return problems


def _edge_problems(program: Program, edge: Edge) -> list[str]:
    if edge.source == edge.target:
        return [f"edge {edge.id} points at itself"]
    if edge.relation in STRUCTURAL_SHAPE:
        return _structural_problems(program, edge)
    if edge.relation in EVIDENCE_RELATIONS:
        return _evidence_problems(program, edge)
    return [f"edge {edge.id} has relation {edge.relation}, which cannot be stored"]


def _structural_problems(program: Program, edge: Edge) -> list[str]:
    source_kind, target_kind = STRUCTURAL_SHAPE[edge.relation]
    problems = []
    if edge.source not in getattr(program, source_kind):
        problems.append(f"edge {edge.id} source {edge.source} is not a {source_kind}")
    if edge.target not in getattr(program, target_kind):
        problems.append(f"edge {edge.id} target {edge.target} is not a {target_kind}")
    return problems


def _evidence_problems(program: Program, edge: Edge) -> list[str]:
    problems = []
    if edge.source not in program.claims:
        problems.append(f"edge {edge.id} is evidence but {edge.source} is not a claim")
    if edge.target not in program.assumptions and edge.target not in program.hypotheses:
        problems.append(f"edge {edge.id} target {edge.target} cannot hold evidence")
    if edge.strength is None:
        problems.append(f"edge {edge.id} is evidence with no strength")
    return problems


def to_dict(program: Program) -> dict:
    """The document form, for artifacts and for replay comparison."""
    return {
        "questions": [vars_of(q) for q in _sorted(program.questions)],
        "hypotheses": [vars_of(h) for h in _sorted(program.hypotheses)],
        "assumptions": [vars_of(a) for a in _sorted(program.assumptions)],
        "experiments": [vars_of(e) for e in _sorted(program.experiments)],
        "sources": [vars_of(s) for s in _sorted(program.sources)],
        "claims": [vars_of(c) for c in _sorted(program.claims)],
        "edges": [vars_of(e) for e in _sorted(program.edges)],
        "decisions": [vars_of(d) for d in _sorted(program.decisions)],
    }


def digest_of(program: Program) -> str:
    """One number for a whole program, so two folds can be compared exactly."""
    return digest(to_dict(program))


def _sorted(items: dict) -> list:
    return [items[key] for key in sorted(items)]


def vars_of(item: object) -> dict:
    fields = getattr(type(item), "__slots__", ())
    return {name: _plain(getattr(item, name)) for name in fields}


def _plain(value: object) -> object:
    return str(value) if isinstance(value, StrEnum) else value


def is_structural(relation: Relation) -> bool:
    return relation in STRUCTURAL_RELATIONS
