# RSM Crux Series — Consolidated Summary (10 rounds)

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

This series (`RSM_CRUX_ATTRIBUTION` through `RSM_CRUX10_SPOOFED_INDEPENDENCE`)
is ten falsification rounds against pieces of that question, prompted by
a ChatGPT brainstorm ("Repairable Semantic Memory" — claim decomposition,
ATMS-style support formulas, counterfactual repair) that was never
designed or built here. **No claim-carrying memory system, support-formula
engine, or repair operator exists.** Every round is a narrow, single-call
or few-call probe against live `gemini-3.5-flash`, scored against a
precommitted synthetic fixture. `custody/*.py` was not touched in any
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

## What remains open, unresolved, or actively concerning

- **Provenance and independence claims are only as trustworthy as their
  source.** Rounds 8 and 10 confirmed, live, the exact vulnerability
  `TRUSTED_COMPUTING_BASE.md` predicted, in two different contexts
  (a provenance pool, and redundant-support repair): self-declared
  independence can lie, a naive judge misses it, and a "be skeptical"
  prompt is a real, twice-replicated mitigation that still isn't the
  structural fix — provenance only from Custody's own in-boundary
  receipt collector, never self-declared, remains unbuilt.
- **Round 10's naive run also surfaced an unplanned finding: single-call
  results carry real sampling variance.** The same domain and prompt
  that scored correctly in round 9 produced a false positive in round
  10's naive condition on a rerun. No round in this series has been
  repeated enough times to separate a genuine mechanism limit from
  one unlucky sample — this is a real, now-demonstrated gap, not a
  hypothetical one.
- **n is small everywhere.** Largest round is 20 cases (round 1); most
  are 4-16. No round uses more than one model. Harder or more numerous
  spoofs, and combining the skeptical mitigation with multi-hop cascades
  in the same test, remain untested past round 10's single spoof shape.
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

Ten rounds, each precommitted before running, most with an honestly
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
(a mitigation, twice-replicated, not a structural fix), and round 10's
own naive rerun is a live reminder that single-call results carry
variance this series has not yet bounded. That is the honest state of
the open question as of this series, not a claim that repairable
semantic memory has been built, validated at scale, or is ready for any
production decision.
