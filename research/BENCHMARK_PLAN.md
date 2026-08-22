# Benchmark Strategy

## Existing-benchmark integration feasibility

| Benchmark | Covers the bounded-interval question? | Integration feasibility |
|---|---|---|
| MemSecBench (2607.27080) | No bounded-interval/laundering test (confirmed, `RELATED_WORK_AUDIT.md`) | Its Write→Execute→Forget harness and 310-case corpus are the closest structural fit for a "does revocation actually remove the right things" measurement, if the corpus/harness is public. **Action**: check for a public repo before building anything Custody-specific; if it exists, run current Custody (B7) through it unmodified as a sanity check before any new benchmark work, since a fresh, external benchmark result is stronger evidence than a self-authored one. |
| MPBench (2606.04329) | No — write/retrieve only, no Forget stage at all | Useful only for validating Custody's write-time admission (B2-equivalent), not for the revocation question. Low priority. |
| Sleeper benchmarks (2605.15338, 2605.28201) | No — attack-only, no defense/revocation evaluated | Useful as an *attack generator* for the "delayed sleeper trigger" variant below, not as a full benchmark to integrate. |
| TMA-NM laundering suite (2606.24322) | Partially — tests laundering resistance at write time, not bounded-interval revocation | **Highest-value reuse if the repo is real and runs**: its three laundering channels (summarization, trusted-tool echo, Sybil corroboration) map directly onto Custody's D/E/F/H red-team failures and onto H3. Reusing their exact attack generators (rather than writing new ones) makes any laundering-resistance claim directly comparable to a published number. Must be verified runnable before relying on it (see `BASELINES.md` B5). |

**Conclusion**: no existing benchmark covers post-hoc, bounded-interval
trust revocation. This matches the field survey's own statement
(2604.16548) that this exact question is unexplored. A new benchmark slice
is therefore justified — but only for the interval-revocation axis
specifically; write-time laundering resistance should reuse TMA-NM's
generators wherever the repo is actually reproducible, rather than
reinventing them.

## New benchmark slice: POST-HOC TRUST REVOCATION

### Canonical scenario (matches the brief exactly, restated with concrete
parameters so it's buildable, not just describable)

1. Principal `P` / tool revision `R` is vouched (`TrustCatalog.request`)
   and used legitimately across `N` sessions spanning a synthetic
   `T`-day window (default `T=30`, matching the README's own incident
   fixture scale for comparability).
2. Legitimate use accumulates: a mix of benign tool-origin writes and
   their model restatements/derivations, across multiple departments.
3. Compromise occurs during a sub-interval `[t_a, t_b] ⊂ [0, T]` — the
   tool's responses during this window are attacker-controlled, but its
   declared schema and serving image are unchanged (matches red-team
   case L: schema-preserving compromise, the case current Custody
   structurally cannot detect via revision digest alone).
4. Unrelated information also accumulates throughout, from other
   tools/departments, as the benign control population.
5. Security is notified at some `t2 > t_b` and issues a revocation request
   scoped to `[t_a, t_b]` (exact-window variant) or to a security-estimated
   `[t_a', t_b'] ⊇ [t_a, t_b]` (uncertain-window variant, per H4).
6. The system under test must neutralize influence traceable to writes
   inside the true `[t_a, t_b]`, including descendants reached through the
   laundering transformations in the variant list below.
7. Unrelated (outside-interval, other-source) state must survive.
8. Any scripted downstream harmful action (`export.send`-equivalent) citing
   interval-poisoned content must fail after revocation; the same action
   citing benign or outside-interval content must still succeed (this is
   the utility-preservation half of every metric in `METRICS.md`).

### Variants (each a separate scenario file/seed set, not a single monolithic run)

- **Exact known compromise start**: `t_a` given exactly, `t_b` unknown
  (open-ended compromise, ongoing until t2).
- **Uncertain compromise window**: security only knows a coarse estimate
  `[t_a', t_b']` that over- or under-covers the true `[t_a, t_b]` by a
  randomized margin (both directions tested separately — over-coverage
  tests collateral damage, under-coverage tests residual harmful
  influence).
- **Cross-agent summaries**: the compromised-interval content is relayed
  through ≥2 departments via `load_memory`-class retrieval before the
  revocation is issued (reuses `live_chain.py`'s existing pattern as the
  scenario generator, not rebuilt from scratch).
- **Mixed benign/poisoned derivation**: a single model turn synthesizes one
  in-interval and one out-of-interval source in the same invocation (the
  exact scenario that would surface the H/R multi-parent bug if it is not
  yet fixed — this variant is also the regression test for that fix).
- **Corroboration from dependent sources**: two channels that both trace
  back to the same compromised root, made to look independent (attacks the
  same `lineage` single-slot bug from a different angle than the mixed-
  derivation variant).
- **Independent corroboration**: two genuinely independent, both-benign
  sources asserting the same claim — a negative control, must never be
  treated as poisoned by either B7 or B8.
- **Delayed sleeper trigger**: content written during `[t_a, t_b]` is not
  retrieved/acted on until well after `t2` and the revocation — reuse the
  Sleeper papers' attack-generation pattern (2605.15338/2605.28201) for
  the trigger construction.
- **Multiple roots**: two distinct tools, both compromised in
  possibly-different, possibly-overlapping intervals, converging on shared
  descendants — the direct test of case R.
- **Deep derivation chain**: ≥4 hops from the compromised root, to confirm
  scope-correctness does not degrade with chain depth (current Custody's
  `_walk` is breadth-first and hop-count-agnostic, `graph.py:137-147` — the
  new interval-scoped variant must preserve that property, not regress it).

### Explicit design requirement

Every variant must include cases where **Custody fails** — per the brief's
own instruction, a benchmark that only shows PASS results is not a
benchmark, it is a demo. Concretely: every variant must include at least
one scenario instance where the ground-truth compromised interval does
*not* align with any tool-revision boundary (so B7's revision-scoped
revocation cannot solve it even in principle, only B8 could), and at least
one instance where B8 itself is expected to fail (e.g. an
under-coverage uncertain-window case with a very tight true interval) so
that a suspiciously perfect B8 result is itself a red flag during review,
not a result to publish uncritically.
