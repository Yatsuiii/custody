# RSM Crux5 Result — Entangled Inference

**0/6 leak rate on the properly-controlled run.** Live `gemini-3.5-flash`,
generate → classify → repair → classify per case, 6 cases. Full detail
in `result.json`. This is the sharpest test in the whole crux series —
genuinely entangled fusion (a stated conclusion, not a compound sentence
with a findable seam) — and it comes out clean.

## The first attempt was invalid, and that's worth reporting precisely

The first run of this experiment used a fixture where the disputed
value's text already said "later found unreliable" *at generation time*.
Result: 4 of 6 generations either refused to assert the conclusion or
asserted its negation outright (e.g. *"Sarah Chen is not authorized...
because her clearance is based on a compromised record"*) — the model
was reasoning correctly, but the test was broken: it leaked the future
revocation into the present-tense generation step, so there was no
confident conclusion for repair to ever retract. This is the same shape
of mistake crux2's `C6` made (disambiguating information placed where it
shouldn't be), caught the same way — by looking at the actual generated
text before trusting the aggregate number, not after.

Fixed by splitting the fixture into `value_at_write_time` (given only at
generation, no hindsight) and a separate `revocation_notice` (given only
at repair time) — mirroring the real scenario the whole research
programme is about: a source legitimately trusted when a memory was
written, discovered bad only later. Rerun on the corrected fixture: 6/6
valid generations, all confidently asserting the expected conclusion.

## The repair result, and why it's the strongest signal in the series

All 6 repairs correctly and explicitly retract the conclusion rather than
repeating it — every repaired text states, in its own words, that the
conclusion "can no longer be confidently asserted" and names the specific
revoked information as the reason. This is the harder fusion shape
(`f2(A,B)`, a joint inference, not `f1(A,B)`, an additive compound) that
crux4 didn't test, and it's the shape the original brainstormed proposal
specifically flagged as the actually-hard, likely-impossible case. It did
not fail here.

## The real methodological limitation, and how it was checked

Scoring required a third, independent classifier call (confident-assertion
vs. hedged/withdrawn), which is itself a semantic judgment — a real
circularity risk `PLAN.md` named before running. Spot-checked 3 of 6
cases by hand against the classifier's stated reasoning (`cfo_approval`,
`server_access`, `vendor_onboarding`): in all 3, the classifier's
reasoning matches a direct manual reading of the repaired text — it
correctly identifies confident assertion in the pre-repair text and
correctly identifies explicit hedging in the post-repair text, citing the
specific hedge language each time rather than a generic verdict. No
disagreement found, but 3 of 6 is not exhaustive verification.

## What this does and does not establish

**Does establish:** on 6 cases, across 6 different domains, a model that
generated a confident inference from a rule and a value can — when told
that value is now revoked — correctly retract the inference rather than
either repeating it verbatim or leaving it unstated-but-implied. This is
real, positive evidence on the specific fusion shape the original
"impossibility boundary" argument named as the hard case, not the easier
one crux4 tested.

**Does not establish:**
- Scale. 6 cases is small even by this series' standards. A false clean
  result from favorable case selection can't be ruled out.
- Robustness to adversarial phrasing. Every rule/value pair here is a
  clean, single-threshold comparison. Real memories entangle more than
  one rule, or state conclusions across several inferential steps — untested.
- That the *identification* step (recognizing, in a large corpus of real
  memories, which specific stored conclusions depended on a given
  revoked source) is solvable — this test hand-picked the one relevant
  memory per case and told the model exactly which source was revoked.
  Finding that memory in the first place, among thousands, is a separate,
  unaddressed problem.
- Anything about whether this generalizes outside a single Gemini model
  or this specific prompt phrasing.

## Where this leaves the whole crux series

Five rounds in: reliable ordinary attribution (crux1, ~95-100%), reliable
redundant-support judgment given explicit declaration (crux3, 0/8),
reliable repair of additive model-fused text (crux4, 0/7), and now
reliable retraction of an entangled inference (crux5, 0/6). Every round
that found a real gap (crux2's contradiction) traced to a fixture design
flaw once investigated, not to a fundamental limit of the mechanism —
though that pattern itself should be read cautiously: it may mean the
approach is genuinely more robust than the original brainstormed
pessimism suggested, or it may mean the fixtures across all five rounds
share a blind spot none of them have found yet. Both readings are
consistent with the evidence so far. Still not a claim of novelty (no
literature search has been run), still not scaled beyond hand-built
synthetic fixtures, and still not a change to what ships in the
hackathon submission.
