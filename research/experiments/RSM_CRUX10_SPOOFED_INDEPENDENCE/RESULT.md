# RSM Crux10 Result — Skeptical Framing Catches the Spoof and Doesn't Break the Honest Cases

**Naive: 10/12 (83%), spoofed item missed, plus one unplanned honest-case
false positive. Skeptical: 12/12 (100%), spoofed item caught, all three
honest domains stay correct.** Live `gemini-3.5-flash`, four domains, two
prompt conditions, one call per domain per condition. Full detail in
`result.json`.

This was the sharpest open gap named in round 9's own `RESULT.md`:
redundant-support judgment under adversarial-independence pressure, not
just honest independence (round 9) or adversarial provenance in a
different context (round 8).

## The naive miss confirms the predicted vulnerability, plus a bonus finding

`server_access`'s `M2b` cited an "independent" re-confirmation that was, in
ground truth, populated from the same compromised HR record — a laundered
restatement, not real independence. The naive prompt (identical to round
9's, which scored 12/12 on all-honest domains) missed it, reasoning that
"independent confirmation from the central badge-provisioning system"
settled the matter. This directly replicates round 8's finding in a new
context: self-declared independence is not evidence of actual
independence, and a judge that doesn't know to doubt it won't.

A second, unplanned miss showed up in the same naive run: `vendor_
onboarding`'s honest `M2b` was wrongly RETRACTed, with the model reasoning
that the memory was "partially derived from Memory 1... meaning its joint
basis is no longer valid" — treating a genuinely redundant two-source
support as if it were conjunctive (both required), the same
misreading round 1's `R2` and round 2's ambiguous cases made. This did not
happen in round 9's run of the identical domain and prompt; it is model
sampling variance on a single call, not a fixture change, and is reported
as exactly that — a reminder that any of these single-call results can
flip on rerun, not just a reason to distrust the pattern found in round 9.

## The skeptical result is the strongest signal so far, on the axis that actually mattered

Round 8 flagged the real risk with a "be skeptical" mitigation: does
priming distrust of independence claims start producing false positives
on cases where the independence is genuine? This round tested that
directly, with three honest domains sitting right next to the spoofed
one in the same run. The skeptical prompt caught the spoof (`server_
access`'s `M2b`, with reasoning explicitly naming that the badge system is
"likely populated from the compromised HR system") and correctly kept all
three honest domains at SURVIVE, with reasoning in each case explicitly
calling the independence "genuine." That is 12/12, not just "the spoof
was caught" — the over-correction failure mode round 8 explicitly left
open did not materialize here.

## What this does and does not establish

This is real, positive evidence that skeptical framing generalizes past
round 8's single provenance-pool context into a structurally different
task (redundant-support repair) without degrading precision on honest
cases — two independent confirmations now, not one. It remains, as round
8 said, not the real fix: this is still an LLM being asked to judge
plausibility, the exact shape of semantic inference
`research/design/DESIGN_FALSIFIER.md` names as a preregistered KILL
condition for the production mechanism. One spoof shape (a claimed
independent system that shares an unstated upstream), one call per
condition, no repeated sampling to separate signal from the variance the
naive run's second miss already demonstrates exists. The structural
answer stays the same as round 8's: never trust self-declared
independence or provenance, verify it from Custody's own TCB-observed
receipts.

## Scope

Four domains, one spoof, two prompt conditions, single-call-per-condition
(no repetition to bound variance — the naive run's own internal
inconsistency with round 9 on an identical domain/prompt is evidence this
matters). Not a red-team suite. Harder or more numerous spoofs, repeated
sampling for variance, and combining this with round 6/9's multi-hop
cascade in the same test all remain untested.
