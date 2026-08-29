# RSM Crux Series — Consolidated Summary (14 rounds)

## What this series is, and what it is not

Custody's shipped, live-proven mechanism (`custody/graph.py`, E2D
falsifier PASS, 11/11 live judges) does **whole-tool revocation**: cut a
compromised source and everything structurally derived from it loses
authority, deterministically, via graph traversal, with zero LLM in the
loop. `RESEARCH.md` names an open question beyond that shipped mechanism:
can influence be repaired at finer grain than "revoke the whole subtree" —
specifically, once clean and poisoned content have been fused by an LLM
into new text, can the poisoned contribution be identified and stripped
without also destroying the clean contribution?

This series (`RSM_CRUX_ATTRIBUTION` through `RSM_CRUX14_ROUND10_NAIVE_BATCH_REPEAT`)
is fourteen falsification rounds against pieces of that question, prompted by
a ChatGPT brainstorm ("Repairable Semantic Memory" — claim decomposition,
ATMS-style support formulas, counterfactual repair) that was never
designed or built here. **No claim-carrying memory system, support-formula
engine, or repair operator exists.** Every round is a narrow probe against
live `gemini-3.5-flash`, scored against a precommitted synthetic fixture;
round 11 repeats two earlier probes to measure their observed variance,
round 12 repeats a specific Round 10 honest naive condition, round 13
repeats its spoofed naive condition, and round 14 repeats the full Round 10
naive batch.
`custody/*.py` was not touched in any
round (`git diff --stat main -- custody/` confirmed empty after every
commit). Nothing here has been merged into `main`, and this document does
not authorize that — a merge or citation-rewrite decision is separate and
undecided.

## Results table

| # | Round | Question | Result |
|---|---|---|---|
| 1 | `RSM_CRUX_ATTRIBUTION` | Does an LLM judge dependence correctly (A/B/joint/redundant/distractor)? | 19/20 (95%). One miss: redundant support read as conjunctive — a genuine natural-language ambiguity, not a reasoning error. |
| 2 | `RSM_CRUX2_SUBCLAIM_ATTRIBUTION` | Sub-claim-level attribution; does explicit "either is sufficient" language fix the round-1 miss? | 16/19 (84%). Two matched pairs disagreed with each other — inconclusive, diagnosed as a confound (sufficiency rule bundled inside the removable source). |
| 3 | `RSM_CRUX3_REDUNDANT_ISOLATED` | Re-run with the confound fixed: sufficiency rule given as separate, non-removable context. | Explicit: 0/8 false positives. Ambiguous: 4/8. Resolves round 2 cleanly — explicit declaration works once actually isolated from the source. |
| 4 | `RSM_CRUX4_FUSED_GENERATION` | First test where the model *generates* the fused text itself (not hand-written) — can repair strip a model's own fusion? | 0/7 leak (1/8 invalid, fixture bug). Caveat found on inspection: all fusions were additive ("X, and Y"), not entangled — the easier shape. |
| 5 | `RSM_CRUX5_ENTANGLED_INFERENCE` | Genuinely entangled inference (a joint conclusion, not a compound sentence with a findable seam) — the hard shape round 4 didn't reach. | 0/6 leak, after fixing an invalid first attempt (hindsight text had leaked into the generation prompt). Sharpest clean result in the series. |
| 6 | `RSM_CRUX6_CASCADING_REPAIR` | Does retraction propagate two hops, using only each hop's immediate parent (matching how Custody's real graph works)? | 0/5 leak at both hops. Unprompted qualitative finding: model separated "this happened" from "this is still valid" — the same distinction `REPAIR_SEMANTICS.md` makes structurally. |
| 7 | `RSM_CRUX7_POOL_IDENTIFICATION` | Search, not judgment: given a 12-item pool with no parent pointers, find every affected memory. | **First real miss.** Recall 0.5 (missed the 2-hop dependent), precision 1.0, 0/3 adversarial false positives avoided correctly. |
| 7b | `RSM_CRUX7B_STRUCTURAL_PROVENANCE` | Does adding a one-line `provenance` field (pointing at direct parent, matching `direct_parent_ids`) fix round 7's miss? | Recall 1.0, precision 1.0. Confirms the bottleneck was missing information, not a reasoning limit — closes the loop on round 7. |
| 8 | `RSM_CRUX8_SPOOFED_PROVENANCE` | Adversarial: what if the provenance field itself lies about independence (the threat model `TRUSTED_COMPUTING_BASE.md` predicts)? | Naive prompt: recall 0.67, missed the spoofed item — confirms the predicted vulnerability. Skeptical prompt: recall 1.0, caught it, still 0 false positives — but explicitly not treated as "solved," since it's still semantic judgment, not the structural TCB-verified provenance the design actually calls for. |
| 9 | `RSM_CRUX9_REDUNDANT_CASCADE` | Does cascading repair correctly distinguish a pure-cascade dependent (should retract) from a sibling with independent support (should survive), in the same pass? | 12/12 (100%), 4/4 domains. Combines round 3's and round 6's findings into one branch point the model had to get both sides of. |
| 10 | `RSM_CRUX10_SPOOFED_INDEPENDENCE` | Adversarial: what if round 9's "independent" support is itself a laundered restatement of the revoked chain? | Naive: 10/12, missed the spoof, plus one unplanned honest-case false positive (sampling variance, not a fixture change). Skeptical: 12/12 — caught the spoof, all three honest domains still correct, no over-correction. |
| 11 | `RSM_CRUX11_VARIANCE_BOUND` | Do repeated calls on clean round-5 and round-9 controls vary under the same fixture, prompt, model, and parser? | Five repeats: round 5 was 30/30 valid and clean (0/30 leak); round 9 was 60/60 correct (20/20 domains). Zero observed variance in both per-repeat binary metrics; this does not bound the distinct round-10 naive condition. |
| 12 | `RSM_CRUX12_ROUND10_NAIVE_REPEAT` | Does Round 10's naive `vendor_onboarding` false positive recur under the exact same prompt/domain condition? | Five repeats: 15/15 correct, M2b false positives 0/5, and zero observed variance. The original Round 10 miss was not replicated in this small isolated sample; it remains real evidence, not disproven. |
| 13 | `RSM_CRUX13_ROUND10_SPOOF_REPEAT` | Does Round 10's naive spoofed `server_access` M2b miss recur under the exact same prompt/domain condition? | Five isolated repeats: 10/15 correct; M1 and M2a were 5/5, but spoofed M2b was SURVIVE instead of RETRACT in 5/5 calls. Per-call accuracy and M2b-false-negative variance were both 0.0. |
| 14 | `RSM_CRUX14_ROUND10_NAIVE_BATCH_REPEAT` | Does the full Round 10 naive four-domain batch reproduce the same errors in the same order? | Five source-ordered batches: 55/60 correct, with 11/12 in every batch. The spoofed `server_access` M2b false negative recurred 5/5; the honest `vendor_onboarding` M2b false positive recurred 0/5. Batch accuracy and both error-indicator variances were 0.0. |

## What is now reasonably well-supported

- Single-hop dependence judgment, including redundant-vs-sole support,
  works once the ambiguity is actually removed from the prose (rounds 1, 3).
- Repair can strip both additive (round 4) and genuinely entangled
  (round 5) model-generated fusions with zero measured leakage.
- Retraction propagates correctly through a 2-hop chain using only local,
  immediate-parent state (round 6), and correctly stops at a branch with
  independent support rather than over-cascading (round 9) — together,
  the two patterns Custody's real graph traversal needs a semantic layer
  to *not* get wrong if it ever handled unstructured content.
- Structural provenance (a recorded parent pointer, not inferred from
  prose) is what actually fixes search/recall, not better prompting of
  the search step itself (rounds 7 → 7b).
- Repeating two clean controls five times found no label variation in this
  sample: 30/30 valid, clean round-5 repairs and 60/60 round-9 judgments
  were correct (round 11). This is a narrow observed result, not a general
  robustness bound.
- Repeating Round 10's exact naive `vendor_onboarding` prompt/domain five
  times produced 15/15 correct judgments and no M2b false positives (round
  12). This strengthens the sample-variance interpretation of that honest
  miss, without establishing a general error rate.
- Repeating Round 10's complete naive four-domain sequence five times
  reproduced the same 11/12 batch result each time: the spoofed
  `server_access` M2b miss persisted, while the honest `vendor_onboarding`
  M2b stayed correct (round 14). This is sequence-specific evidence, not a
  general robustness bound.

## What remains open, unresolved, or actively concerning

- **Provenance and independence claims are only as trustworthy as their
  source.** Rounds 8 and 10 confirmed, live, the exact vulnerability
  `TRUSTED_COMPUTING_BASE.md` predicted, in two different contexts
  (a provenance pool, and redundant-support repair): self-declared
  independence can lie, a naive judge misses it, and a "be skeptical"
  prompt is a real, twice-replicated mitigation that still isn't the
  structural fix — provenance only from Custody's own in-boundary
  receipt collector, never self-declared, remains unbuilt.
- **Sampling variance is only partly bounded.** Round 10's naive run
  surfaced an honest-case false positive even though round 9's clean
  condition got the same domain/prompt right. Round 11 found zero label
  variation across five repeats of rounds 5 and 9, and round 12 found no
  recurrence across five repeats of Round 10's exact naive
  `vendor_onboarding` condition. Round 13 found the opposite pattern on
  the exact spoofed `server_access` condition: the M2b false negative
  recurred 5/5 with zero observed within-condition variance. The original
  honest-case flip remains real evidence; round 14's full source-ordered
  batch also did not reproduce it. Broader naive behavior is still
  unmeasured.
- **n is still small and model coverage is one.** Rounds 12 and 13 add only
  five isolated calls each, and round 14 adds five fixed-order batches, for
  three hand-built checks. Other spoof shapes, randomized ordering, a
  second model, and combining the skeptical mitigation with multi-hop
  cascades in the same test remain untested.
- **Circularity risk in the classifier-scored rounds (5-9):** a second
  Gemini call judges "confident assertion vs. hedged/retracted." This was
  mitigated by manual spot-checks of stated reasoning each round, not
  eliminated.
- **No literature search has been run** on prior claim-decomposition or
  ATMS-style repair work. No novelty claim is made or should be inferred
  from any result in this series.
- **The production mechanism does not need any of this.** Whole-tool
  revocation is already deterministic and LLM-free. Everything in this
  series is evidence about a harder, unbuilt, unshipped extension — not
  evidence the shipped mechanism has a gap.

## Bottom line

Fourteen rounds, each precommitted before running, most with an honestly
reported miss, confound, or caveat rather than a clean pass — the series
did not manufacture a smooth success story. The central hypothesis this
whole line of testing was checking — that fused content is not
recoverably separable after the fact — did not hold up as an
*impossibility*: every specific mechanism probed (attribution, entangled
inference, cascading repair, redundant-support discrimination, pool
search given structural provenance, adversarial independence-spoofing)
came back with a positive, reproducible result under its own tested
conditions, once given either explicit structure (provenance fields) or
an explicit skepticism instruction. What holds it back from being
"solved" is narrower and sharper than the original framing: independence
and provenance claims have to be trustworthy at the source, nothing
tested here addresses that except by asking an LLM to be suspicious
(a mitigation, twice-replicated, not a structural fix). Rounds 11 and 12
found zero label variance in five repeats of two clean controls and in
five repeats of the exact Round 10 naive `vendor_onboarding` condition;
round 13 found a zero-variance repeated miss on the exact spoofed
`server_access` condition; and round 14 reproduced that miss in the full
source-ordered naive batch while again finding no vendor false positive.
That narrows the interpretation of the original honest-case flip toward
sample-specific variance in that control while confirming a repeatable
naive failure on this spoof shape, but the series still has not estimated
general error rates, randomized order effects, or model coverage. That is
the honest state of the open question as of this series, not a claim that
repairable semantic memory has been built, validated at scale, or is ready
for any production decision.
