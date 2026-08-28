# RSM Crux7 Result — Pool Identification: the First Real Miss

**Recall: 0.5 (1/2). Precision: 1.0 (0/10 false positives). Adversarial
false-positive rate: 0.0 (0/3).** Live `gemini-3.5-flash`, one call, 12
memories, 2 true positives, 10 negatives (3 deliberately adversarial).
Full detail, including the raw response, in `result.json`.

This is the first genuine miss anywhere in the crux series, precommitted
in `PLAN.md` as the serious-finding direction before running: *"Missing
either true positive... would mean the bottleneck isn't judgment, it's
search."* That's exactly what happened, and it should not be undersold
by the otherwise-clean precision numbers next to it.

## What happened

The model flagged memory #1 (*"Sarah Chen may access the server room
unescorted"* — the direct dependent) but not memory #2 (*"The Security
desk recorded the activation of an unescorted access credential issued to
Sarah Chen for the server room"* — the crux6 downstream memory, genuinely
2-hop dependent on the same revoked record). Its raw response was simply
`"1"` — no reasoning was requested in this round's prompt, a design choice
worth revisiting for any follow-up specifically to see *why* #2 was
skipped, not just that it was.

## The good news sitting right next to the miss

Zero false positives, out of 10 real opportunities to have one — including
all 3 memories hand-written specifically to tempt a name/topic-keyword
match rather than genuine dependence (`#10` same person, different fact;
`#11` same wording pattern, different person; `#12` same topic, no
connection). The model did not pattern-match on surface similarity even
once. That's a real, clean, precisely-targeted positive result on exactly
the failure mode the original brainstormed proposal predicted would be
hardest to avoid.

## Why this matters more than crux4-6's clean numbers

Crux4, 5, and 6 all *told* the model explicitly which parent a memory was
derived from before asking it to repair — crux6's hop-2 repair prompt
says outright "this memory was based on a fact recorded by another
department, which has just been revised." This test never states that
relationship; the model had to recognize, from reading memory #2's text
cold inside a pool of 11 others, that it depended on the same revoked
record as memory #1. It didn't. That's a materially different and harder
capability than anything crux1-6 measured, and it's the one Custody's own
real architecture doesn't actually need solved by an LLM at all — the
structural derivation graph (validated in E2D and its extensions) finds
exactly this kind of multi-hop dependent deterministically, by walking
real `derived_from` edges, not by re-deriving the relationship from text.
This result is better read as *evidence for why that structural approach
exists* than as a gap Custody itself has, but it is a real limit on how
far LLM-judgment-only identification could go without that structural
backbone underneath it.

## Scope

n=1 pool, one revoked source, one miss out of two opportunities — far too
small to state a recall rate with any real confidence beyond "not
reliably 100% here." No repeated pools, no variation in pool size or
distractor density, no test of whether providing reasoning (rather than a
bare number list) would have caught what a chain-of-thought might have
surfaced. A single, real, informative data point, not a rate.

## Where this leaves the series

Six rounds of clean results (crux1, 3, 4, 5, 6) established that judgment
and repair are reliable *given the relevant memory or memories directly*.
This seventh round found the actual bottleneck the whole line of research
was implicitly assuming away: finding those memories in the first place,
without being told which ones matter, is not reliable — at least not for
multi-hop dependents, and not from a single bare-list prompt. That's not
a reason to discard everything before it; it's the reason Custody's real
identification mechanism is a deterministic graph traversal, not an LLM
judgment call, and this result is the closest thing in the whole series
to direct evidence for why that design choice is the right one.
