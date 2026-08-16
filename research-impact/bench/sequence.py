"""Ten interacting documents over one program, with a human correction inside.

Every measurement before this one was single-document, which is the setting that
most flatters a model recomputing from scratch: there is no accumulated state to
get wrong. Here later documents bear on assumptions earlier ones moved, one
document must not propagate, one must not churn, one reactivates work that had
become redundant, and the last is adjacent to a relation a human already
rejected and must not reopen it.

Adjudication is exhaustive and has three labels. The holdout showed that a
"false positive" is sometimes a defensible reading the benchmark author did not
declare, so every document is judged against every assumption, and genuinely
debatable pairs are marked AMBIGUOUS and kept out of the headline rather than
forced into a binary that would punish an exhaustive system for being reasonable.
"""

from __future__ import annotations

from dataclasses import dataclass

from .variants import CONTRADICTS, MODERATE, STRONG, SUPPORTS, WEAK, Document, doc

PROGRAM = "agent_program.json"

RELATION = "RELATION"
NO_RELATION = "NO_RELATION"
AMBIGUOUS = "AMBIGUOUS"

D1 = doc(
    "D1", "Exact-recall tasks can be labelled reliably",
    "Two annotators labelled 300 agent tasks for whether success requires "
    "verbatim recall of an earlier tool result, using a written protocol.",
    "Inter-annotator agreement was 0.81 kappa, and adjudication changed 4% of "
    "initial labels.",
)

D2 = doc(
    "D2", "Duplicate rates in a notebook-editing agent",
    "We looked at one notebook-editing agent, a different setting from software "
    "repair, with a single seed.",
    "Duplicate tool results accounted for 9% of tokens in that run.",
)

D3 = doc(
    "D3", "Independent replication of the recall-labelling protocol",
    "A second group applied the same labelling protocol to a disjoint set of "
    "260 tasks.",
    "They report 0.78 kappa between annotators, consistent with the original "
    "study.",
)

D4 = doc(
    "D4", "Stricter re-annotation collapses the recall subset",
    "We re-annotated the same 300 tasks under a stricter definition of verbatim "
    "recall, requiring the exact string to appear in the final patch.",
    "Agreement fell to 0.28 kappa and the subset shrank by two thirds, so the "
    "labels do not identify a stable population.",
    "Annotation was performed on transcripts of up to 120k tokens.",
)

D5 = doc(
    "D5", "Retrieval from long agent transcripts",
    "We measure retrieval latency and accuracy from agent transcripts as a "
    "function of transcript length.",
    "Models attending over 80k-token transcripts answered more slowly but "
    "without measurable accuracy loss on our task set.",
)

D6 = doc(
    "D6", "Exit-status graders disagree with themselves",
    "We re-ran 1,200 agent trajectories through the same exit-status grader on "
    "identical inputs.",
    "The same trajectory received different verdicts on 11% of tasks across "
    "repeats, driven by timing-dependent test setup.",
)

D7 = doc(
    "D7", "A larger grader-stability study finds determinism",
    "We repeated the grader-stability protocol across 6,000 trajectories and "
    "three independent harness installations.",
    "Verdicts were identical across all repeats once test setup was pinned to "
    "a fixed clock, with no disagreement observed.",
)

D8 = doc(
    "D8", "Context overflow is rarer than this literature assumes",
    "We instrument agent runs on the same 600-task suite with a 128k window.",
    "Only 18% of runs exceeded the context window before a final patch, well "
    "under the 40% figure this line of work assumes.",
)

D9 = doc(
    "D9", "Typed summarisation fits the agent step budget",
    "We measure wall-clock cost of typed summary generation inside a live agent "
    "loop across four model sizes.",
    "Typed summaries added 150ms per step at the median, inside the 500ms step "
    "budget in every configuration.",
)

D10 = doc(
    "D10", "Prompt formatting conventions for tool results",
    "We compare three formatting conventions for rendering tool results into "
    "the agent's prompt: XML tags, markdown fences, and bare text.",
    "Formatting choice changed downstream task success by less than half a "
    "point in every configuration.",
)

DOCUMENTS = {d.id: d for d in (D1, D2, D3, D4, D5, D6, D7, D8, D9, D10)}

# Every document against every assumption. Pairs absent from this table are
# NO_RELATION, which is the overwhelming majority and is asserted, not assumed:
# `lock_sequence.py` refuses to lock unless all 80 pairs resolve.
ADJUDICATION: dict[tuple[str, str], tuple] = {
    ("D1", "B4"): (RELATION, SUPPORTS, STRONG, 1),
    ("D2", "B3"): (RELATION, CONTRADICTS, WEAK, 1),
    ("D3", "B4"): (RELATION, SUPPORTS, MODERATE, 1),
    ("D4", "B4"): (RELATION, CONTRADICTS, STRONG, 1),
    # The trap. Sentence 2 mentions long transcripts and nothing else; it says
    # nothing about which constraint binds, so a relation to B7 is wrong here.
    ("D4", "B7"): (NO_RELATION,),
    # Genuinely debatable: no accuracy loss at 80k could be read as supporting
    # B7, or as too narrow to bear on it. Out of the headline, reported apart.
    ("D5", "B7"): (AMBIGUOUS,),
    ("D6", "B5"): (RELATION, CONTRADICTS, STRONG, 1),
    ("D7", "B5"): (RELATION, SUPPORTS, STRONG, 1),
    ("D8", "B1"): (RELATION, CONTRADICTS, STRONG, 1),
    # The reading the holdout's model made and the holdout's truth did not
    # declare. It is defensible, so this time it is marked rather than scored.
    ("D8", "B7"): (AMBIGUOUS,),
    ("D9", "B6"): (RELATION, SUPPORTS, STRONG, 1),
}

CORRECTION = {
    "after": "D4",
    "document": "D4",
    "target": "B7",
    "verdict": "rejected",
    "note": "D4 does not bear on B7. It reports the transcript length that "
            "annotation ran on, not evidence about which constraint binds. "
            "Human reviewed and rejected this relation.",
}


@dataclass(frozen=True, slots=True)
class Step:
    index: int
    document: Document
    correction: dict | None = None


CANONICAL = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10")
# Two permutations whose semantics permit the same end state: D2 and D3 both
# precede the correction and neither depends on the other, and D8 and D9 touch
# disjoint assumptions. The correction stays pinned to D4 in every order.
SWAP_EARLY = ("D1", "D3", "D2", "D4", "D5", "D6", "D7", "D8", "D9", "D10")
SWAP_LATE = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D9", "D8", "D10")
ORDERS = {"canonical": CANONICAL, "swap-early": SWAP_EARLY,
          "swap-late": SWAP_LATE}


def steps(order: str) -> tuple[Step, ...]:
    built = []
    for index, name in enumerate(ORDERS[order]):
        correction = CORRECTION if name == CORRECTION["after"] else None
        built.append(Step(index, DOCUMENTS[name], correction))
    return tuple(built)


def true_relations(document_id: str) -> tuple[tuple[str, str, str, int], ...]:
    """Only RELATION pairs move state. AMBIGUOUS deliberately does not."""
    return tuple(
        (assumption, *rest)
        for (doc_id, assumption), (label, *rest) in sorted(ADJUDICATION.items())
        if doc_id == document_id and label == RELATION
    )


def label_for(document_id: str, assumption: str) -> str:
    entry = ADJUDICATION.get((document_id, assumption))
    return NO_RELATION if entry is None else entry[0]


def ambiguous_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(
        pair for pair, entry in sorted(ADJUDICATION.items())
        if entry[0] == AMBIGUOUS
    )
