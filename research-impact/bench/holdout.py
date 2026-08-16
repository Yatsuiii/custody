"""Eighteen holdout variants over a second program. Written before the fix.

The order matters and is the point. These variants, their documents, and their
ground truth were authored and hashed before the admission boundary was changed,
and no model output on them was looked at while designing that change. The dev
set diagnosed; this set reports. If that ordering is broken later, the numbers
here stop meaning anything, so `results/holdout-lock.json` records the hash.

The program underneath is a different domain with a different shape, and four
variants exercise rules the dev set never reached: an experiment that becomes
worth doing again, an ESTABLISHES edge that is deliberately not a dependency,
STALE outranking REDUNDANT on the same node, and support arriving for an already
contested assumption.
"""

from __future__ import annotations

from .variants import (
    CONTRADICTS,
    STRONG,
    SUPPORTS,
    WEAK,
    Relation,
    Variant,
    doc,
    evidence_step,
)

PROGRAM = "agent_program.json"

GRADER_PAPER = doc(
    "E-GRD", "Exit-status graders disagree with themselves across runs",
    "We re-ran 1,200 agent trajectories through three widely used "
    "exit-status graders.",
    "The same trajectory received different verdicts on 11% of tasks across "
    "repeats, driven by timing-dependent test setup rather than the agent.",
)

DISTRIBUTION_PAPER = doc(
    "E-DIST", "Benchmark tasks are shorter than production traffic",
    "We compare public agent benchmark tasks against a month of production "
    "traffic from three deployments.",
    "Production tasks touch 4.2 times more files and run 3.8 times longer "
    "than the benchmark's median task.",
)

OVERFLOW_PAPER = doc(
    "E-OVR", "Context overflow is common in long-horizon coding agents",
    "We instrument agent runs on a 600-task suite and record context usage.",
    "Sixty-one percent of runs exceeded the model's context window before the "
    "agent produced a final patch.",
)

SCHEDULER_PAPER = doc(
    "E-SCH", "Speculative decoding schedules for batched agent serving",
    "We study request scheduling for batched agent inference under mixed "
    "arrival rates.",
    "Speculative decoding raised throughput by 2.1 times at unchanged output "
    "quality.",
)

TRUNCATION_PAPER = doc(
    "E-TRC", "What fixed-window truncation actually drops",
    "We label every observation dropped by fixed-window truncation across 400 "
    "trajectories.",
    "Only 3% of dropped observations were later referenced by the agent, and "
    "removing them changed task success by 0.2 points.",
    "Attention probes over the retained window show no degradation up to 96k "
    "tokens.",
)

DEDUPE_PAPER = doc(
    "E-DUP", "Duplicate tool results are rarer than reported",
    "We measure exact-duplicate tool results across four open agent traces.",
    "Exact duplicates accounted for 6% of trajectory tokens, far below "
    "previously reported figures.",
)

RECALL_PAPER = doc(
    "E-RCL", "Exact-recall tasks cannot be labelled reliably",
    "Three annotators independently labelled 300 tasks for whether success "
    "requires verbatim recall of an earlier tool result.",
    "Inter-annotator agreement was 0.31 kappa, and adjudication changed 44% of "
    "initial labels.",
)

LATENCY_PAPER = doc(
    "E-LAT", "Typed summarisation fits inside the agent step budget",
    "We measure wall-clock cost of typed summary generation inside a live "
    "agent loop across four model sizes.",
    "Typed summaries added 180ms per step at the median, inside the 500ms "
    "step budget in every configuration.",
)

ATTENTION_PAPER = doc(
    "E-ATT", "Attention degrades long before the context window ends",
    "We measure retrieval accuracy from long agent transcripts as a function "
    "of position.",
    "Accuracy on facts placed beyond 60k tokens fell to 54% even though the "
    "window extends to 128k.",
)

REPLICATION_PAPER = doc(
    "E-REP", "Independent replication of grader instability",
    "A second group repeated the grader repeat-run protocol on a different "
    "task suite.",
    "Verdicts differed across repeats on 9% of tasks, matching the earlier "
    "report.",
)

SMALL_DEDUPE_PAPER = doc(
    "E-SML", "A single-seed look at duplicate rates in notebook agents",
    "We looked at duplicate tool results in one notebook-editing agent, a "
    "different setting from software repair, with one seed.",
    "Duplicates accounted for 9% of tokens in that single run.",
)

SUPPORT_TRUNCATION_PAPER = doc(
    "E-SUP", "Truncation drops load-bearing observations",
    "We trace which truncated observations the agent later attempts to "
    "reference.",
    "Twenty-nine percent of truncated observations were referenced again "
    "later, and 71% of those references failed.",
)

LOW_OVERFLOW_PAPER = doc(
    "E-LOW", "Context overflow is rarer than this literature assumes",
    "We instrument agent runs on the same 600-task suite with a 128k window.",
    "Only 18% of runs exceeded the context window before a final patch, well "
    "under the 40% figure this line of work assumes.",
)

TWO_PREMISE_PAPER = doc(
    "E-TWO", "Neither overflow nor truncation loss is as large as reported",
    "We re-measure both context overflow and what truncation actually drops, "
    "on the same 600-task suite.",
    "Only 18% of runs exceeded the context window before a final patch.",
    "Only 3% of dropped observations were later referenced by the agent, and "
    "removing them changed task success by 0.2 points.",
)

COMBINED_PAPER = doc(
    "E-CMB", "Summary cost is affordable, and overflow is rarer than assumed",
    "We measure typed summary latency inside a live agent loop and, "
    "separately, context usage across the same suite.",
    "Typed summaries added 150ms per step at the median, inside the 500ms "
    "step budget in every configuration.",
    "Only 18% of runs exceeded the context window before a final patch, well "
    "under the 40% figure this line of work assumes.",
)

HOLDOUT: tuple[Variant, ...] = (
    Variant(
        "H01-root-and-reactivation",
        "a contradiction that shakes three layers and makes finished-with work "
        "worth doing again",
        GRADER_PAPER,
        (Relation("B5", CONTRADICTS, STRONG, 1),),
        program=PROGRAM,
        notes="F7 was redundant because a note already settled B5. Contesting "
              "B5 must return F7 to PLANNED.",
    ),
    Variant(
        "H02-leaf-contradiction",
        "a contradiction against the one assumption nothing depends on",
        DISTRIBUTION_PAPER,
        (Relation("B8", CONTRADICTS, STRONG, 1),),
        program=PROGRAM,
    ),
    Variant(
        "H03-support-for-supported",
        "more support for an assumption already supported",
        OVERFLOW_PAPER,
        (Relation("B1", SUPPORTS, STRONG, 1),),
        program=PROGRAM,
    ),
    Variant(
        "H04-irrelevant-paper",
        "a real systems paper with nothing to say about this program",
        SCHEDULER_PAPER,
        (),
        program=PROGRAM,
    ),
    Variant(
        "H05-two-assumptions",
        "one document that contradicts one assumption and settles another",
        TRUNCATION_PAPER,
        (Relation("B2", CONTRADICTS, STRONG, 1),
         Relation("B7", SUPPORTS, STRONG, 2)),
        program=PROGRAM,
    ),
    Variant(
        "H06-shared-assumption",
        "two hypotheses resting on the same contested assumption",
        DEDUPE_PAPER,
        (Relation("B3", CONTRADICTS, STRONG, 1),),
        mutations=({"op": "add_edge", "relation": "DEPENDS_ON",
                    "source": "H5", "target": "B3"},),
        program=PROGRAM,
    ),
    Variant(
        "H07-two-premises-broken",
        "one document that breaks two of the same experiment's three premises",
        TWO_PREMISE_PAPER,
        (Relation("B1", CONTRADICTS, STRONG, 1),
         Relation("B2", CONTRADICTS, STRONG, 2)),
        program=PROGRAM,
        notes="F4 requires B1, B2 and B5. Two of the three go at once, so its "
              "justification must carry both.",
    ),
    Variant(
        "H08-duplicate-ingestion",
        "the same document and the same judgment, a second time",
        GRADER_PAPER,
        (Relation("B5", CONTRADICTS, STRONG, 1),),
        prior=(evidence_step(GRADER_PAPER,
                             Relation("B5", CONTRADICTS, STRONG, 1)),),
        program=PROGRAM,
    ),
    Variant(
        "H09-human-override",
        "a rejected relation must not immunise the assumption",
        REPLICATION_PAPER,
        (Relation("B5", CONTRADICTS, STRONG, 1),),
        prior=(
            evidence_step(GRADER_PAPER,
                          Relation("B5", CONTRADICTS, STRONG, 1)),
            {"op": "reject", "target": "B5", "relation": CONTRADICTS,
             "reason": "their graders are not ours; ours has no timing setup"},
        ),
        program=PROGRAM,
    ),
    Variant(
        "H10-more-of-the-same",
        "a second contradiction where one already stands",
        REPLICATION_PAPER,
        (Relation("B5", CONTRADICTS, STRONG, 1),),
        prior=(evidence_step(GRADER_PAPER,
                             Relation("B5", CONTRADICTS, STRONG, 1)),),
        program=PROGRAM,
    ),
    Variant(
        "H11-retired-hypothesis",
        "impact against a program a human has already pruned",
        GRADER_PAPER,
        (Relation("B5", CONTRADICTS, STRONG, 1),),
        prior=({"op": "retire", "hypothesis": "H5",
                "rationale": "exact-recall framing folded into H3"},),
        program=PROGRAM,
    ),
    Variant(
        "H12-redundancy",
        "evidence that answers what a planned experiment would have measured",
        LATENCY_PAPER,
        (Relation("B6", SUPPORTS, STRONG, 1),),
        program=PROGRAM,
    ),
    Variant(
        "H13-weak-evidence",
        "a different setting and a single seed, below the strength that moves",
        SMALL_DEDUPE_PAPER,
        (Relation("B3", CONTRADICTS, WEAK, 1),),
        program=PROGRAM,
    ),
    Variant(
        "H14-confirmed-invalidation",
        "a confirmed contradiction against an assumption with no support",
        RECALL_PAPER,
        (Relation("B4", CONTRADICTS, STRONG, 1),),
        confirmed=True,
        program=PROGRAM,
    ),
    Variant(
        "H15-completed-work-untouched",
        "a contested premise under both a finished and a planned experiment",
        LOW_OVERFLOW_PAPER,
        (Relation("B1", CONTRADICTS, STRONG, 1),),
        program=PROGRAM,
        notes="F3 is COMPLETED and requires B1. It must not move.",
    ),
    Variant(
        "H16-support-for-contested",
        "support arriving for an assumption that is already contested",
        SUPPORT_TRUNCATION_PAPER,
        (Relation("B2", SUPPORTS, STRONG, 1),),
        prior=(evidence_step(TRUNCATION_PAPER,
                             Relation("B2", CONTRADICTS, STRONG, 1)),),
        program=PROGRAM,
        notes="Conflicting evidence keeps an assumption CONTESTED. Nothing new "
              "may move, and nothing may be un-contested.",
    ),
    Variant(
        "H17-establishes-is-not-a-dependency",
        "contesting an assumption that only an ESTABLISHES edge touches",
        ATTENTION_PAPER,
        (Relation("B7", CONTRADICTS, STRONG, 1),),
        program=PROGRAM,
        notes="F9 would establish B7. Wanting to settle a question is not "
              "depending on its answer, so F9 must stay PLANNED.",
    ),
    Variant(
        "H18-stale-outranks-redundant",
        "one experiment that is simultaneously premise-broken and answered",
        COMBINED_PAPER,
        (Relation("B6", SUPPORTS, STRONG, 1),
         Relation("B1", CONTRADICTS, STRONG, 2)),
        mutations=({"op": "add_edge", "relation": "REQUIRES",
                    "source": "F8", "target": "B1"},),
        program=PROGRAM,
        notes="F8 establishes B6, now settled, and requires B1, now contested. "
              "STALE must win: an experiment that cannot run answers nothing.",
    ),
)
