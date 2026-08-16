"""Gemini collaboration layer — BUILD_SCOPE.md §12, §16.

Scoped to exactly five question classes: why is this designed this way,
was X tried before, what constraints apply, is this decision still
current, what changed. Not a general chat-with-your-repo interface.

The one rule this module exists to enforce: Gemini receives the resolved
decision + evidence from Stage 3 (`RetrievalCandidate`, already carrying
`ActiveResolution`) and reports it — it never decides lifecycle status
itself. The prompt states each candidate's resolved status as given fact,
and every claim in the answer must be tagged with why it should be
trusted: a verbatim historical record, the resolver's current-truth
verdict, the model's own inference, or an admission that the data doesn't
say. That last category exists specifically so "I don't know" is a valid,
expected answer rather than something the model has to be tricked into
via hedging language.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vertex  # noqa: E402

from retrieval import DecisionIndex, RetrievalCandidate  # noqa: E402


class ClaimCategory(Enum):
    VERIFIED_HISTORICAL_FACT = "verified_historical_fact"
    CURRENT_ACTIVE_DECISION = "current_active_decision"
    INFERRED_ADVICE = "inferred_advice"
    MISSING_OR_UNCERTAIN = "missing_or_uncertain"


@dataclass
class Claim:
    text: str
    category: ClaimCategory
    decision_id: str | None  # citation, when the claim traces to a specific decision


@dataclass
class Answer:
    question: str
    claims: list[Claim]
    candidates_considered: list[str]  # decision ids retrieved for grounding


_SYSTEM_INSTRUCTIONS = """You are DecisionTrace, an engineering-decision memory assistant.
You answer exactly these question types: why a subsystem is designed a
certain way, whether an approach was tried before, what constraints apply
to a subsystem, whether a decision is still current, and what changed
about a prior decision.

You are given a set of retrieved decisions below. For EACH ONE, the
"Resolved status" line is ALREADY DETERMINED by a separate deterministic
system — you must never contradict it, guess a different current/inactive
status, or imply a reverted/superseded decision might still be active.
Report it as given fact.

Respond with ONLY a JSON array, no other text. Each element:
{
  "text": "one claim, in your own words",
  "category": one of "verified_historical_fact" | "current_active_decision" | "inferred_advice" | "missing_or_uncertain",
  "decision_id": "the decision id this claim cites, or null if it cites none"
}

Category meanings:
- verified_historical_fact: a fact directly stated in a decision's
  evidence/rationale below (e.g. what was originally chosen, why it was
  rejected/reverted historically).
- current_active_decision: what IS currently active, per the "Resolved
  status" lines given to you — never your own guess.
- inferred_advice: your own reasoning/suggestion that goes beyond what's
  directly stated (e.g. "you may want to check X").
- missing_or_uncertain: use this explicitly when the retrieved decisions
  don't actually answer the question, rather than inventing an answer.

If nothing retrieved is relevant to the question, return a single
missing_or_uncertain claim saying so — do not fabricate a decision."""


def _render_candidate(c: RetrievalCandidate) -> str:
    d = c.decision
    lines = [f"--- Decision [{d.id}] (similarity {c.similarity:.2f}) ---"]
    lines.append(f"Subject: {d.subject}")
    if d.chosen_approach:
        lines.append(f"Chosen approach: {d.chosen_approach}")
    if d.rejected_alternatives:
        lines.append(f"Rejected alternatives: {'; '.join(d.rejected_alternatives)}")
    if d.rationale:
        lines.append(f"Rationale (verbatim source excerpt): {d.rationale}")
    if d.evidence:
        lines.append("Evidence: " + "; ".join(f"{e.url}" for e in d.evidence))
    if c.is_current:
        lines.append(f"Resolved status: CURRENTLY ACTIVE (id={d.id})")
    else:
        lines.append(
            f"Resolved status: NOT active/superseded/reverted. "
            f"The currently active decision in this lineage is "
            f"id={c.resolution.active_id!r}."
        )
    return "\n".join(lines)


def _parse_claims(raw: str) -> list[Claim]:
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return [Claim(
            text="Model did not return a parseable answer.",
            category=ClaimCategory.MISSING_OR_UNCERTAIN, decision_id=None,
        )]
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return [Claim(
            text="Model returned malformed JSON.",
            category=ClaimCategory.MISSING_OR_UNCERTAIN, decision_id=None,
        )]

    claims = []
    for item in items:
        try:
            category = ClaimCategory(item["category"])
        except (KeyError, ValueError):
            category = ClaimCategory.MISSING_OR_UNCERTAIN
        claims.append(Claim(
            text=item.get("text", ""), category=category,
            decision_id=item.get("decision_id"),
        ))
    return claims


def answer(question: str, index: DecisionIndex, k: int = 5) -> Answer:
    candidates = index.search(question, k=k)
    if not candidates:
        return Answer(
            question=question,
            claims=[Claim(
                text="No decisions in memory are relevant to this question.",
                category=ClaimCategory.MISSING_OR_UNCERTAIN, decision_id=None,
            )],
            candidates_considered=[],
        )

    context = "\n\n".join(_render_candidate(c) for c in candidates)
    prompt = f"{_SYSTEM_INSTRUCTIONS}\n\nRetrieved decisions:\n\n{context}\n\nQuestion: {question}"
    raw = vertex.generate(prompt)
    claims = _parse_claims(raw)
    return Answer(
        question=question, claims=claims,
        candidates_considered=[c.decision.id for c in candidates],
    )
