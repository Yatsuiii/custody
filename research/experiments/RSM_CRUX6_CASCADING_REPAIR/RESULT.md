# RSM Crux6 Result — Cascading Repair Through a Derivation Chain

**0/5 leak rate at both hops.** Live `gemini-3.5-flash`, 5 cases, each
extended one hop beyond crux5. Full detail in `result.json`, including
every generated and repaired sentence at both hops verbatim.

| Metric | Value |
|---|---|
| Valid cases | 5/5 |
| Hop-1 leak rate (M1, same as crux5's mechanism) | 0/5 |
| Hop-2 leak rate (M2, repaired using only M1's corrected text) | 0/5 |
| Cascade failures (hop-1 clean, hop-2 leaked) | 0 |

This is the test the whole crux series was building toward: not "can a
model retract its own inference" (crux5), but "does retraction propagate
through a chain when each hop only has its immediate parent's corrected
state, never the original root cause" — which is how Custody's actual
derivation graph works (`support`/`effective cap` propagate via meet over
*direct* parents, recursively, not by re-checking the original root at
every hop). It held at both hops, on every case.

## A genuinely interesting behavior that emerged unprompted

`vendor_onboarding`'s hop-2 repair didn't say Procurement never sent the
onboarding paperwork — it said sending it *happened*, but its validity is
now uncertain: *"...but this action can no longer be confidently asserted
as valid or ongoing..."* That's a real distinction, and nobody prompted
for it explicitly: the model separated "this action occurred" (a
historical fact, still true) from "this action's justification still
holds" (now revoked). That is the same distinction Custody's own design
already makes structurally — `REPAIR_SEMANTICS.md`: *"Repair changes
whether a record is usable; it does not rewrite what happened."* Worth
noting as a qualitative finding, not folded into the leak-rate metric,
since it wasn't something this test was built to measure.

## What this does and does not establish

**Does establish:** on 5 cases, two-hop cascading repair — the specific
shape Custody's real derivation graph needs — worked with zero leaks at
either hop, using only each hop's immediate parent, never the original
poisoned source. Combined with crux4 (additive fusion) and crux5
(single-hop entangled inference), every fusion/propagation shape tested
across the series has come back clean once its fixture was properly
controlled.

**Does not establish, and this list is now longer than any single round's
caveats:**
- **Depth.** Two hops, not three or more. Custody's own F1 live proof is
  a 3-hop chain (sales → support → finance); this series has never tested
  three.
- **Fan-out.** Every case here is a single chain, one parent, one child.
  A real graph has multiple children reading the same parent, and
  multiple parents feeding one child (crux1/2's "joint"/"redundant"
  categories) — cascading through *that* shape, combined with entangled
  inference, is untested.
- **Scale.** 5 cases, hand-built, single model, single prompt phrasing,
  same as every round before it.
- **Identification.** Still, as every prior RESULT.md has said: this
  hand-picks the relevant memory at each hop and hands it directly to the
  repair step. Finding which memories in a real store need repair, given
  only a revoked root, remains completely untested by this entire series.
- **Adversarial pressure.** Nothing here has been red-teamed. A user or
  attacker who knew this repair mechanism existed and deliberately
  phrased content to resist it has not been tried.

## Where the crux series stands after six rounds

Every fusion and propagation shape tested (ordinary attribution,
redundant support given explicit declaration, additive model-fused text,
entangled single-hop inference, and now two-hop cascading) has come back
clean. Every round that found a real problem (crux2's contradiction,
crux4's fixture marker miss, crux5's first invalid attempt) traced to a
fixture or scoring design flaw once actually investigated, not a limit of
the underlying mechanism. That consistent pattern is itself worth taking
seriously as a signal — but it is a signal from small, hand-built,
single-model fixtures across six rounds by the same author, not
independent replication, not adversarial testing, and not a literature
search. State it as what it is: real, repeated, positive, narrow
evidence, not a solved problem.
