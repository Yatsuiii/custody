# RSM Crux2 — Sub-Claim-Level Attribution (Harder Test)

The first crux falsifier (`RSM_CRUX_ATTRIBUTION`) tested whole-claim
binary judgment: does removing B change M at all? That's the *easier*
version of what RSM actually needs. RSM's real value proposition over
what Custody already ships is repairing a *composite* memory where only
*part* of the claim depends on B — the "Level 4" entanglement case from
the original brainstormed proposal. This test targets that directly, and
re-tests the one weak spot the first run found (redundant support) with
a controlled explicit-vs-ambiguous comparison.

Ground truth fixed in `fixture.json` before any model call, same
discipline as the first crux test.

## Two things this test adds that the first one couldn't check

1. **Sub-claim granularity.** Each case's derived memory `M` is composite
   — 1 to 4 named sub-claims. Ground truth is per-sub-claim, not
   per-case: does *this specific sub-claim* survive removing B? A
   mechanism (or judge) that can only say "M changes somehow" isn't
   useful for repair — repair needs to know *which part*.
2. **Matched explicit-vs-ambiguous pairs for redundant support.** Cases
   6/7 and 8/9 are the same scenario twice — once with the source text
   explicitly stating "either alone is sufficient," once without. If the
   model succeeds on the explicit pair but fails on the ambiguous one,
   that confirms the first test's finding precisely: the gap is that the
   information isn't in the prose, not that the judge is unreliable.
   That's a materially different, more actionable finding than "5% error
   rate."

## Method

10 cases, 19 total sub-claim judgments. One Gemini call per case (not per
sub-claim) with all of that case's sub-claims listed and numbered; the
model answers YES/NO per numbered sub-claim in one response. Parsed and
scored per sub-claim against `fixture.json`'s ground truth, unmodified
after the fact.

## Metrics

- **Sub-claim accuracy**: correct judgments / 19, the primary number.
- **Recall on true sub-claim dependencies**: same safety-critical
  direction as the first test.
- **Explicit vs. ambiguous pair comparison**: case 6 vs. 7, case 8 vs. 9,
  reported side by side rather than folded into the aggregate — this
  pairing is the point of the test, not incidental detail.

## Bar, stated before seeing results

If sub-claim accuracy holds above ~85% *and* the explicit/ambiguous pairs
show a real gap (explicit succeeds, ambiguous fails, replicating test
1's finding rather than it having been noise), that's a coherent,
actionable result: LLM judgment is viable for granular repair *given*
explicit support-mode declaration at write time, and unreliable without
it. If the explicit pairs also fail, that would mean the first test's
finding was noise or something else is going on, and this whole
direction needs more basic groundwork before any further testing.
