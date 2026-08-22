# Preregistered Hypotheses

All thresholds below are fixed now, before any experiment runs, per the
session contract's acceptance gate 4. If a later phase wants to change a
threshold after seeing results, that is a violation of this document, not a
justified update — the fix is to add a new, separately-numbered hypothesis.

Every hypothesis assumes the benchmark slice in `BENCHMARK_PLAN.md`'s
canonical post-hoc-trust-revocation scenario, run against the baseline
ladder in `BASELINES.md`.

## H1 — Bounded-interval revocation reduces harmful-action success under delayed, partial-interval compromise

- **Independent variable**: revocation granularity — whole-tool (B7,
  current Custody) vs. bounded-interval (B8, proposed).
- **Dependent metric**: harmful-action success rate (fraction of scripted
  consequential actions, e.g. `export.send`, that succeed while citing
  interval-poisoned content), measured *after* revocation is applied.
- **Baseline(s)**: B0 (no defense), B2 (provenance-only), B7 (current
  Custody, whole-tool revocation).
- **Benchmark/task set**: `BENCHMARK_PLAN.md` canonical scenario, "exact
  known compromise start" and "uncertain compromise window" variants.
- **Minimum effect required**: B8's post-revocation harmful-action success
  rate must be ≤ 50% of B7's on the same seeded scenario set (i.e. at least
  a 2x reduction), with B7 itself already required to be ≤ B2 and ≤ B0
  (sanity check that whole-tool revocation is not somehow worse than doing
  nothing — if it is, something upstream of H1 is broken and H1 cannot be
  evaluated honestly).
- **Statistical plan**: paired scenarios (same seed, same synthetic
  compromise injection, only revocation strategy varies), minimum N=100
  scenario instances, two-proportion z-test, alpha=0.05, report exact
  counts not just the rate.
- **PASS**: ≥2x reduction, p<0.05.
- **CAUTION**: 1.3x-2x reduction, or p in [0.05, 0.1).
- **KILL**: <1.3x reduction, or B8 does not beat B2 (provenance metadata
  alone), which would mean bounded-interval scoping added nothing over
  simply knowing origin at all.

## H2 — Bounded-interval revocation has higher selective-repair precision than coarse purge

- **Independent variable**: repair strategy — coarse user/session/app purge
  (B3-adjacent), whole-tool revocation (B7), bounded-interval (B8).
- **Dependent metrics**: repair precision = (interval-poisoned records
  correctly removed) / (total records removed); repair recall =
  (interval-poisoned records correctly removed) / (total interval-poisoned
  records that exist); benign records incorrectly removed (raw count and
  rate).
- **Baseline(s)**: B3 (provenance + naive full-descendant deletion, i.e.
  today's whole-tool `CustodyGraph.revoke`), plus a coarse
  session/user-purge baseline built fresh since Custody has no such mode
  today.
- **Benchmark/task set**: same as H1, restricted to the "cross-agent
  summaries" and "mixed benign/poisoned derivation" variants, since those
  are where precision separates the strategies.
- **Minimum effect required**: B8 precision ≥ B7 precision + 0.15 absolute,
  with B8 recall not dropping more than 0.05 absolute below B7's recall
  (a precision gain bought by silently giving up recall does not count).
- **Statistical plan**: same paired-scenario design as H1, N≥100,
  bootstrap 95% CI on the precision/recall difference (2000 resamples).
- **PASS**: precision gain ≥0.15 absolute with CI excluding 0, recall drop
  ≤0.05.
- **CAUTION**: precision gain in [0.05, 0.15), or recall drop in
  (0.05, 0.10].
- **KILL**: precision gain <0.05, or recall drop >0.10 — i.e. the interval
  scoping is not meaningfully more surgical than what already exists, or
  it buys precision by silently missing real descendants.

## H3 — Multi-parent/laundering-aware derivation catches what exact-hash matching misses

- **Independent variable**: derivation-tracking mechanism — exact-content-
  hash only (current Custody, `CustodyGraph.resolve`), vs. a
  laundering-aware mechanism (proposed) that also links paraphrase,
  trusted-tool echo, and multi-source synthesis (fixing the H/R single-slot
  `lineage` bug directly).
- **Dependent metric**: laundering-defeat rate = fraction of scripted
  laundering attempts (paraphrase, tool-echo, multi-source synthesis) whose
  resulting descendant is *still* found and revoked when its true
  compromised ancestor is revoked.
- **Baseline(s)**: B3 (current exact-match lineage), B4/B5/B6 if any
  reproducible external laundering-aware lineage baseline exists (pending
  Phase 0 literature outcome — if none reproduces, state that explicitly
  rather than skip the comparison silently).
- **Benchmark/task set**: `BENCHMARK_PLAN.md`'s laundering variant set
  specifically (paraphrase, trusted-tool echo, multi-source/H-R
  reproduction).
- **Minimum effect required**: laundering-defeat rate improves by ≥0.30
  absolute over current Custody's exact-match baseline on the multi-source
  synthesis variant alone (this is the one case the red-team already proved
  is a silent, deterministic miss today — `derived_from` structurally
  cannot represent two parents — so *any* real fix should show a large,
  not marginal, effect here; a marginal result here is itself informative
  that the fix did not actually address the root cause).
- **Statistical plan**: deterministic scenarios (the H/R bug is not
  probabilistic — it either finds the edge or it doesn't), so report exact
  counts, no significance test needed for the multi-source sub-case; use
  the same paired z-test as H1 for the paraphrase sub-case, which is
  stochastic depending on paraphrase severity.
- **PASS**: ≥0.30 absolute improvement on multi-source synthesis, and any
  measurable (>0) improvement on paraphrase without a corresponding rise in
  false-trust (a paraphrase that gets *wrongly* trusted is worse than one
  that stays safely over-quarantined).
- **CAUTION**: multi-source improvement in [0.10, 0.30).
- **KILL**: <0.10 absolute improvement on multi-source synthesis — this
  would mean the proposed fix does not actually close the deterministic bug
  the red-team found, which should be nearly free to fix and easy to verify,
  so failing here is a strong negative signal about the whole research
  direction's execution quality, not just this hypothesis.

## H4 — Dynamic trust epochs recover correctly when a previously-trusted revision is retrospectively marked compromised

- **Independent variable**: presence/absence of a trust-epoch data model
  (B8 vs. B7).
- **Dependent metric**: post-compromise recovery rate (PCRR, defined in
  `METRICS.md`) under three compromise-window certainty conditions: exact
  known window, uncertain window (security only knows "sometime in days
  10-20"), and retroactively-widened window (initial estimate later
  corrected to be larger).
- **Baseline(s)**: B7 (whole-tool revocation — the only "recovery" B7 can
  perform is the same regardless of window certainty, since it has no
  window concept at all).
- **Benchmark/task set**: `BENCHMARK_PLAN.md`'s three compromise-window
  variants.
- **Minimum effect required**: PCRR under the *uncertain-window* condition
  must not collapse to the *exact-window* condition's performance minus
  more than 0.20 absolute — i.e. epoch-based revocation must degrade
  gracefully under realistic uncertainty, not only work in the unrealistic
  case where security knows the exact compromise boundary.
- **Statistical plan**: paired across window-certainty conditions, N≥100
  per condition, report the full distribution not just the mean (window
  uncertainty is exactly where a system might look good on average and bad
  on tail cases).
- **PASS**: uncertain-window PCRR within 0.20 absolute of exact-window PCRR.
- **CAUTION**: within 0.20-0.35.
- **KILL**: gap >0.35 — the epoch model only works in a lab condition
  (exact known window) that security teams do not actually get in practice
  (the user's own Phase 2 framing explicitly calls this out), so it would
  not be a defensible practical contribution even if H1-H3 pass.

## Cross-cutting kill condition

If H3's multi-source sub-case (the deterministic H/R bug fix) does not pass,
**stop and fix that bug in current Custody directly, on its own branch,
before evaluating H1/H2/H4 at all.** Building bounded-interval revocation on
top of a derivation graph that already silently drops real edges means every
other hypothesis is measuring a system with an unknown, uncontrolled error
floor.

## H5 — Structural envelopes make transformation lineage and interval repair deterministic

- **Independent variable:** attribution/authority mechanism — current Custody
  at commit `040c28c` versus Architecture A's structural admission envelope.
  Event corpus, topology, roles, caps, transformation classes, timestamps,
  compromise window, action requests, and injected crash points remain fixed.
- **Dependent metrics:** direct-parent recall, affected-record recall, false
  `ACT` permits, same-record authority increases, benign informational
  retention, outside-window sibling preservation, replay digest stability, and
  unsafe fault windows, all defined exactly in
  `design/DESIGN_FALSIFIER.md`.
- **Baseline:** the measured E1/E2A/E2B/E2C behavior of current Custody. No
  external system is substituted for the local baseline.
- **Benchmark/task set:** the one deterministic six-element graph frozen in
  `design/DESIGN_FALSIFIER.md`: tool echo, benign paraphrase, malicious
  paraphrase, multi-parent synthesis, later compromise, and unaffected sibling.
- **Minimum effect required:** Architecture A must achieve 1.0 direct-parent
  recall, 1.0 affected recall, zero false `ACT` permits, zero same-record
  increases, zero unsafe fault windows, stable replay, retained benign
  informational access, and a live outside-window sibling.
- **Statistical plan:** none. These are deterministic structural properties;
  report exact numerators, denominators, booleans, and per-record evidence.
- **PASS:** every threshold above passes and the existing suite remains 381/381
  with no production-file diff.
- **CAUTION:** all security properties remain fail-closed, but benign
  informational access, sibling selectivity, or terminal replay fails.
- **KILL:** any false action permit, missed affected descendant, silently
  missing declared parent, in-place authority increase, unsafe crash window, or
  dependence on semantic inference/tool self-report.

H5 is preregistered design only. It has not run, and adding it does not
authorize the E2D experimental implementation.
