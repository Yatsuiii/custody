"""Fifteen controlled variants of one program, each with truth by construction.

The base program is the phase 2 fixture. Every variant states three things: how
the graph is mutated, what already happened before the new document arrives, and
which relations that document genuinely licenses. Ground truth is then computed
by running the engine on those declared relations, so no expected answer is ever
typed by hand and no variant can quietly expect something the rules do not say.

The point of the spread is pressure in both directions. Five variants must
produce no change at all, because a system that finds impact everywhere is worse
than useless, and that failure mode is invisible if every case has an answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    title: str
    sentences: tuple[str, ...]

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    def numbered(self) -> str:
        return "\n".join(f"S{i}: {s}" for i, s in enumerate(self.sentences))


@dataclass(frozen=True, slots=True)
class Relation:
    """A relation the document really does license, with the sentence saying so."""

    target: str
    relation: str
    strength: str
    sentence: int
    confidence: float = 0.9


@dataclass(frozen=True, slots=True)
class Variant:
    id: str
    intent: str
    document: Document
    truth: tuple[Relation, ...]
    mutations: tuple[dict, ...] = ()
    prior: tuple[dict, ...] = ()
    confirmed: bool = False
    notes: str = ""
    program: str = "arc_program.json"
    _: dict = field(default_factory=dict, repr=False)


def doc(identifier: str, title: str, *sentences: str) -> Document:
    return Document(identifier, title, tuple(sentences))


# Two versions of the same study on purpose. The short one bears on exactly one
# assumption, so a variant that means to test a single contradiction is not
# quietly testing two; the long one adds the rollout finding and is used only
# where two relations are the point. A document that licenses a relation the
# variant forgot to declare produces ground truth that punishes a system for
# being right, which is worse than no benchmark at all.
POSITION_PAPER_A2 = doc(
    "D-POS", "Absolute position is recoverable from flattened grids",
    "We probe whether transformers encode absolute cell position without "
    "explicit coordinate features.",
    "Linear probes recover absolute row and column indices from mid-stack "
    "residual streams with 94.6% accuracy at sequence lengths up to 2048 tokens.",
    "Ablating rotary encodings drops probe accuracy to 31.2%.",
)

POSITION_PAPER = doc(
    "D-POS-FULL", "Absolute position is recoverable, and rollouts stay coherent",
    "We probe whether transformers encode absolute cell position without "
    "explicit coordinate features.",
    "Linear probes recover absolute row and column indices from mid-stack "
    "residual streams with 94.6% accuracy at sequence lengths up to 2048 tokens.",
    "Ablating rotary encodings drops probe accuracy to 31.2%.",
    "In twenty-step rollouts the models maintain cell identity without "
    "positional drift, with a mean coherence score of 0.91.",
)

SECOND_POSITION_PAPER = doc(
    "D-POS2", "Independent replication of position probing",
    "An independent group repeated the probing protocol on three further "
    "checkpoints.",
    "Absolute row and column indices were recovered at 91.8% accuracy without "
    "any coordinate features present in the input.",
)

TOKENISER_PAPER = doc(
    "D-TOK", "Byte-level tokenisation reduces training cost for code models",
    "We compare byte-level and subword tokenisation for code models at three "
    "scales.",
    "Byte-level training reduced wall-clock cost by 18% at equal downstream "
    "pass@1, and the gap widened with context length.",
    "We observe no change in reasoning benchmarks outside the code domain.",
)

MEMORY_PAPER = doc(
    "D-MEM", "Activation memory dominates at small batch sizes",
    "We profile grid-reasoning training runs across batch sizes from 8 to 256.",
    "Activation memory, not parameter memory, is the binding constraint at "
    "batch 64 on a single 80GB device.",
)

PROXY_PAPER = doc(
    "D-PRX", "One-step accuracy is a poor proxy for task solve rate",
    "We measure per-step and whole-task performance on 240 grid tasks.",
    "One-step transition accuracy and full-task solve rate correlate at only "
    "r=0.21, and the rank order of models differs between the two.",
)

DECISION_PAPER = doc(
    "D-DEC", "Decision-relevant changes are sparser than reported",
    "We re-audit the held-out split used by several grid reasoning papers.",
    "On 38% of held-out tasks no cell change in a given step alters the final "
    "answer.",
)

# Supports A6 and, in the same breath, supports the already-supported A2. A
# document whose second relation moves nothing is a better test than one with a
# single relation: it separates "found the relation" from "propagated it".
COHERENCE_PAPER = doc(
    "D-COH", "Long-horizon coherence without absolute position",
    "We roll out grid models for twenty steps and measure identity drift.",
    "Cell identity is preserved over twenty steps without explicit coordinate "
    "features, at a mean coherence of 0.93.",
    "Probing the same checkpoints recovers absolute row and column indices at "
    "only 31% accuracy, so the models track relative offsets rather than "
    "absolute position.",
)

# A study that only strengthens what is already believed. It has to be its own
# document: the probing paper above reports a finding that cuts the other way in
# the same abstract, and pointing a "support only" variant at it would declare a
# truth the document does not carry.
RELATIVE_OFFSET_PAPER = doc(
    "D-REL", "Grid models track relative offsets, not absolute position",
    "We probe six grid-reasoning checkpoints for absolute and relative "
    "position information.",
    "Absolute row and column indices are recovered at 8.1% accuracy, barely "
    "above the 6.7% chance rate, in every checkpoint without coordinate "
    "features.",
    "Relative offsets between adjacent cells are recovered at 88% accuracy in "
    "the same models.",
)

HISTORY_PAPER = doc(
    "D-HIST", "Longer histories on a neighbouring benchmark",
    "We study history length on a block-stacking benchmark, not grid "
    "reasoning.",
    "Models given five prior states solved six task families that models given "
    "three prior states failed entirely, in a single seed.",
)

CONTRADICTS = "CONTRADICTS"
SUPPORTS = "SUPPORTS"
STRONG = "STRONG"
MODERATE = "MODERATE"
WEAK = "WEAK"


def evidence_step(document: Document, *relations: Relation) -> dict:
    return {
        "op": "evidence",
        "document": document,
        "relations": relations,
    }


VARIANTS: tuple[Variant, ...] = (
    Variant(
        "V01-root-contradiction",
        "a contradiction against an assumption with dependents in every layer",
        POSITION_PAPER_A2,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
    ),
    Variant(
        "V02-leaf-contradiction",
        "a contradiction against an assumption nothing depends on",
        MEMORY_PAPER,
        (Relation("A7", CONTRADICTS, STRONG, 1),),
        mutations=(
            {"op": "add_assumption", "id": "A7",
             "text": "Parameter memory rather than activation memory is the "
                     "binding constraint at batch 64."},
        ),
        notes="A7 is deliberately unwired: nothing may move but A7 itself.",
    ),
    Variant(
        "V03-support-not-contradict",
        "supporting evidence for an already supported assumption",
        RELATIVE_OFFSET_PAPER,
        (Relation("A2", SUPPORTS, STRONG, 1),),
        notes="A2 is already SUPPORTED. More support must move nothing.",
    ),
    Variant(
        "V04-irrelevant-paper",
        "a real paper with nothing to say about this program",
        TOKENISER_PAPER,
        (),
    ),
    Variant(
        "V05-two-assumptions",
        "one document that contradicts one assumption and settles another",
        POSITION_PAPER,
        (Relation("A2", CONTRADICTS, STRONG, 1),
         Relation("A6", SUPPORTS, STRONG, 3)),
    ),
    Variant(
        "V06-shared-assumption",
        "two hypotheses resting on the same contested assumption",
        POSITION_PAPER_A2,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
        mutations=({"op": "add_edge", "relation": "DEPENDS_ON",
                    "source": "H2", "target": "A2"},),
    ),
    Variant(
        "V07-two-premises",
        "an experiment that requires two assumptions, one of them contested",
        POSITION_PAPER_A2,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
        mutations=({"op": "add_edge", "relation": "REQUIRES",
                    "source": "E5", "target": "A2"},),
    ),
    Variant(
        "V08-duplicate-ingestion",
        "the same document, the same judgment, a second time",
        POSITION_PAPER_A2,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
        prior=(evidence_step(POSITION_PAPER_A2,
                             Relation("A2", CONTRADICTS, STRONG, 1)),),
        notes="The impact already happened. A second pass must add nothing.",
    ),
    Variant(
        "V09-human-override",
        "a rejected relation must not immunise the assumption against new work",
        SECOND_POSITION_PAPER,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
        prior=(
            evidence_step(POSITION_PAPER_A2,
                          Relation("A2", CONTRADICTS, STRONG, 1)),
            {"op": "reject", "target": "A2", "relation": CONTRADICTS,
             "reason": "probed at 2048 tokens; our sequences are 512"},
        ),
    ),
    Variant(
        "V10-more-of-the-same",
        "a second contradiction where one is already standing",
        SECOND_POSITION_PAPER,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
        prior=(evidence_step(POSITION_PAPER_A2,
                             Relation("A2", CONTRADICTS, STRONG, 1)),),
        notes="Already contested. More of the same evidence must not churn.",
    ),
    Variant(
        "V11-retired-hypothesis",
        "impact computed against a program a human has already pruned",
        POSITION_PAPER_A2,
        (Relation("A2", CONTRADICTS, STRONG, 1),),
        prior=({"op": "retire", "hypothesis": "H2",
                "rationale": "folded into H1 after the June review"},),
    ),
    Variant(
        "V12-redundancy",
        "evidence that answers the question a planned experiment would ask",
        COHERENCE_PAPER,
        (Relation("A6", SUPPORTS, STRONG, 1),
         Relation("A2", SUPPORTS, MODERATE, 2)),
        notes="The second relation is real and must move nothing: A2 is "
              "already supported.",
    ),
    Variant(
        "V13-weak-evidence",
        "a real but weak signal, below the strength that moves a state",
        HISTORY_PAPER,
        (Relation("A4", CONTRADICTS, WEAK, 1),),
        notes="Recorded, not acted on. Nothing may move.",
    ),
    Variant(
        "V14-confirmed-invalidation",
        "a confirmed contradiction against an assumption with no standing support",
        PROXY_PAPER,
        (Relation("A5", CONTRADICTS, STRONG, 1),),
        confirmed=True,
    ),
    Variant(
        "V15-completed-work-untouched",
        "a contested premise under both finished and planned experiments",
        DECISION_PAPER,
        (Relation("A1", CONTRADICTS, STRONG, 1),
         Relation("A5", CONTRADICTS, MODERATE, 1)),
        notes="One sentence, two targets: steps that do not matter also "
              "weaken the proxy claim. Declared because a careful reader "
              "would record both, not because a model found them.",
    ),
)


def by_id(identifier: str) -> Variant:
    return next(v for v in VARIANTS if v.id == identifier)
