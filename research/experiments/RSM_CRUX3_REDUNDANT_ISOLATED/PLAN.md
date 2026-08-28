# RSM Crux3 — Redundant Support, Isolated and Properly Controlled

Crux2's explicit-vs-ambiguous comparison (n=2 matched pairs) gave
contradictory results, and the diagnostic follow-up found a real
confound in one pair: the sufficiency rule ("either alone is sufficient")
was written as part of source B's own removable sentence, so removing B
also removed the rule that justified keeping the claim. But the same
confound existed in the pair that succeeded, so it didn't fully explain
the inconsistency — leaving genuine uncertainty rather than a clean
answer.

This test does two things crux2 didn't:

1. **Fixes the confound properly, for every case.** The sufficiency rule
   is always given as separate `policy_context` — background policy that
   is not part of either revocable source, matching how crux2's `C1`-`C5`
   correctly modeled non-revocable policy. Source B never carries its own
   justification for why it's dispensable.
2. **Increases sample size on exactly the comparison that matters**, from
   2 matched pairs to 8, across 8 different real-world domains, so a
   single case's outcome doesn't dominate the read.

Every case in this fixture is genuinely redundant support by
construction — ground truth `depends_on_b = false` in all 16 (8 domains
x explicit/ambiguous). This is a deliberately narrow, single-question
fixture: what is the actual false-positive rate on redundant support,
with the confound controlled, at a sample size that means something?

## Fixture: 8 domains, each in two variants

Domains: vendor certification, expense approval, incident-witness
confirmation, QA test verification, identity verification (KYC-style),
software license compliance audit, background-check tier requirement,
insurance claim documentation. Each domain has source A and source B
independently supporting the same claim.

- **`*_explicit`**: `policy_context` states "either alone is sufficient"
  as separate background, never inside A or B's own text.
- **`*_ambiguous`**: no `policy_context` at all; A and B are stated as
  two independent facts with no explicit sufficiency rule anywhere.

## Method

Same as crux2: one Gemini call per case, single sub-claim ("the derived
claim holds"), YES/NO plus one-sentence reasoning (reasoning captured
this time, unlike crux2's bare-answer format, specifically so a
discrepancy doesn't require an unplanned follow-up call to diagnose).

## Metrics

- **False-positive rate on `*_explicit` cases** (n=8): should be low if
  explicit declaration reliably fixes the problem once the confound is
  controlled.
- **False-positive rate on `*_ambiguous` cases** (n=8): expected to be
  higher, replicating crux1/crux2's finding, now at a sample size that
  can actually distinguish "unreliable" from "one unlucky case."
- **Per-domain pairing**, reported side by side, not just aggregated —
  if explicit still doesn't uniformly help even with the confound fixed,
  that's the real, load-bearing finding this test exists to get a clean
  read on.

## Bar, stated before seeing results

If explicit cases score materially better than ambiguous (e.g. 0-1
false positives vs. 3+), that's a real, actionable result: explicit
support-mode declaration works, crux2's contradiction was the confound
plus noise. If explicit cases still show a comparable false-positive
rate to ambiguous ones even with the confound controlled and n=8 per
arm, that confirms crux2's more concerning reading: the judge's
unreliability on redundant support is not fixed by clearer language, and
this whole approach needs a non-semantic-inference verification layer
to be viable at all -- which was already the standing recommendation, now
with real evidence behind it either way.
