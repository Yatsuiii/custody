# Research Verdict

## VERDICT: RESEARCH-ONLY

Not BUILD. Not KILL. Not a clean PIVOT either — the thesis survives Phases
0-6 in narrowed form, but nothing here should be implemented as "Custody
2.0" yet, and calling this fellowship/paper-grade today would overclaim.

## Reasoning, tied directly to Phases 0-6

**Phase 0 (literature)** found the exact gap the thesis targets —
bounded-interval revocation after legitimate-then-compromised trust, across
laundering transformations — is real and is independently named as
unexplored by a field survey (arXiv:2604.16548), not just asserted by this
project. That is a genuine novelty signal. But it also found the single
strongest adjacent system, TMA-NM (arXiv:2606.24322), formally proves that
Custody's own derivation-matching approach (exact content-hash) is unsound
under laundering, and ships a working, benchmarked alternative. Custody is
not ahead of the field on the mechanism it would need to build interval
scoping on top of — it is behind the strongest comparable system on
exactly that axis.

**Phase 1 (red-team)** found the gap is not hypothetical: case K
(partial-compromise-interval) is a clean, code-verified FAIL with no
mitigating factor, and cases H/R (silently-dropped multi-parent derivation
edges) are **existing correctness bugs**, not scope limitations — the
current system can already under-count blast radius today, on ordinary
multi-source synthesis, independent of any interval question. This is the
strongest reason RESEARCH-ONLY beats BUILD: the foundation the proposed
work would sit on has a known, fixable, but currently unfixed defect.

**Phases 2-6** produced a threat model, hypotheses, baselines, benchmark
plan, and metrics that are all falsifiable and none of which required
inventing a flattering framing — several (H3's kill condition, the PCRR
rejection in `METRICS.md`, the B3=B7 correction in `BASELINES.md`) actively
made the thesis harder to pass, which is the point of this exercise.

## Why not BUILD

Fellowship/paper-grade work needs a working baseline sweep before an
architecture proposal is credible. None of E0-E9 in
`EXPERIMENT_REGISTRY.md` have run. The one experiment cheap enough to run
immediately (E0/E1, fixing the multi-parent bug and checking it against
H3's deterministic sub-case) has not been done, and it is the
cross-cutting gate every other hypothesis depends on. Building "Custody
2.0" architecture now, before that gate is even attempted, would repeat
exactly the failure mode this whole review was commissioned to prevent:
committing to a system around a research contribution that has not been
tested at its cheapest, most falsifiable point.

## Why not KILL

Two independent, verifiable sources (TMA-NM's own scope statement and the
field survey) confirm the specific intersection this thesis targets —
interval-scoped, laundering-resistant retroactive revocation — is not
solved by anything found. That is a real, narrow, citable gap, not a
restated solved problem. Killing the research question outright would be
as unjustified as flattering it; the correct move is to test the cheapest
falsifiable piece before spending more effort.

## Why not a clean PIVOT

A pivot implies memory poisoning is the wrong problem or another gap is
more defensible. Nothing in this audit found a *better* adjacent gap — the
adjacent gaps found (write-time laundering resistance alone, certified
statistical robustness, GDPR-style unlearning) are all already occupied by
real prior art. The problem is not the wrong one; the project is simply not
yet at the stage where committing to build it is justified.

## Fellowship/paper-standard gap analysis

- **Research engineering portfolio project**: closest to achievable now —
  E0/E1 (the bug fix) alone, done rigorously with a regression test and an
  honest writeup of what it fixes and why, is a legitimate, scoped, evidence-
  gated artifact today, independent of whether the larger thesis proceeds.
- **Fellowship research proposal**: `ONE_PAGE_PROPOSAL.md` is a credible
  draft of this, but a reviewer would immediately ask "have you reproduced
  TMA-NM's laundering suite yet?" (E2/E9) — that has not happened, and the
  answer today is "documented as unattempted," not "attempted and
  infeasible." That gap must close before submission.
- **arXiv/preprint-quality empirical paper**: still largely missing —
  E0/E1 have now run (see addendum below) and closed one specific
  correctness question, but E2-E9 (baseline reproduction, benchmark
  harness, the interval-scoped mechanism itself, and the Pareto-frontier
  evaluation) remain NOT STARTED. This is still weeks of work at the pace
  implied by the benchmark plan, not something to claim proximity to yet.
- **Conference submission**: further still — would additionally need the
  Pareto-frontier result (E7) to actually show separation from B7 with the
  preregistered confidence intervals, which cannot be known in advance.

## Addendum, 2026-08-22: E0/E1 falsification experiment result

The next highest-leverage action named below was run, on its own branch
(`research/e0-e1-multiparent-lineage`), scoped explicitly as a
falsification test, not authorization to build further. Full detail in
`research/experiments/E0_CURRENT_LINEAGE_REPRO/` and
`E1_MULTIPARENT_LINEAGE/`.

**Result: FOUNDATION-SURVIVES.** E0 reproduced the H/R multi-parent bug
against real production code (confirmed: revoking one of two trusted
sources feeding a synthesis missed it entirely; revoking the other caught
it — an asymmetric, silent failure). E0 also established the bug was
confined to `take_custody`'s `lineage` bookkeeping in `custody/origin.py`,
not to `custody/graph.py`'s traversal, which was already shown correct by
an existing test. E1 applied the minimal fix the diagnosis implied — no
trust epochs, no hypergraph, no semantic matching — and it closed the
deterministic multi-source case completely: 10/10 attack-case variants
pass, including three-way synthesis, symmetric revocation from either
root, chain-not-shortcut regression protection, and divergence/
reconvergence. The full existing suite (381 tests, up from 377) passes
with zero regressions.

This changes the verdict's reasoning in one specific way, without changing
the verdict itself: **the "known, fixable, but currently unfixed defect"**
cited above as the primary reason to stay RESEARCH-ONLY rather than BUILD
**is now fixed.** The derivation graph current Custody would need to build
bounded-interval revocation on top of is now a sound foundation for the
multi-source-synthesis case specifically — it was not fundamentally
inadequate (case B in the original framing), it was a small, now-corrected
implementation gap (case A). This is a genuine, positive update: the
research thesis's foundation is measurably stronger today than when
`RESEARCH_VERDICT.md` was first written.

**It is not, on its own, grounds to move the verdict to BUILD.** Per this
addendum's own session contract, E0/E1 were scoped as a falsification
check only. The reasons BUILD was rejected above beyond the multi-parent
bug — no baseline sweep has run (E2-E5), no benchmark harness exists yet
(E4), TMA-NM's reproducibility is still unverified (E2), and the interval-
scoping mechanism itself (E6) has not been designed, let alone evaluated —
are all still true and untouched by this experiment. The verdict stays
**RESEARCH-ONLY**. What changes is the next highest-leverage action.

## Next highest-leverage action (superseded — see below for current)

The paragraph below described the action taken in this addendum, kept for
the historical record of what was decided before E0/E1 ran.

Run E0 and E1 only. Fix the `lineage` single-slot bug in
`custody/origin.py:240` on its own branch, write the regression test that
reproduces case H/R, and check the result against H3's cross-cutting kill
condition. This is cheap (hours, not weeks), it is valuable regardless of
whether the larger thesis proceeds (it is a real bug in a system currently
claiming live-proven fleet-wide revocation correctness), and it is the one
result that gates every other hypothesis in this registry. Do not start
E6-E9 (the actual "Custody 2.0" architecture) until E1's result is in hand.

## Current next highest-leverage action (superseded — see E2 addendum below)

E1's result is now in hand and the gate is cleared. The next highest-
leverage action is **E2**: verify whether TMA-NM's (arXiv:2606.24322)
released benchmark/harness repository actually exists and runs. This
gates B5 in `BASELINES.md` and E9 in `EXPERIMENT_REGISTRY.md`, and it is
the cheapest remaining way to further de-risk the thesis before committing
to E4 (building a new benchmark harness) or E6 (designing the interval-
scoped mechanism) — both of which are substantially more expensive than a
single reproducibility check. Do not start E6 (the trust-epoch data model)
or any other architecture work until E2's result is in hand, per this same
addendum's own scope discipline.

## Addendum, 2026-08-22 (same day, continued): E2 result

Full detail in `research/experiments/E2_TMANM_REPRO/`. **Verdict:
EXTERNAL-HARNESS-PARTIAL.** TMA-NM's released code is real (independently
confirmed via ground-truth GitHub API, not an AI-summarized guess), and
its offline, no-cost, formal-correctness reproduction (`test_monitor.py`,
`check_invariant.py`) passed cleanly with zero fixes needed — a genuinely
strong piece of prior art, confirmed again rather than merely cited.

Two findings sharpen, rather than overturn, the standing RESEARCH-ONLY
verdict:

1. **TMA-NM's headline 0%-vs-68% laundering numbers compare against the
   paper author's own hand-built generic `lineage`-class stand-in, not
   against Custody's or MemLineage's actual code.** No direct TMA-NM-vs-
   Custody number exists anywhere. This slightly *weakens* how directly
   TMA-NM's results indict Custody specifically — the earlier reading
   ("Custody is currently the weaker system on this axis") is directionally
   still correct on structural grounds (Custody's own exact-hash mechanism
   is a real instance of the malleable category TMA-NM's theorem covers)
   but was not, and still is not, an empirically measured head-to-head.
2. **TMA-NM's data model has no derivation/lineage field at all** — it
   cannot represent a multi-parent synthesized memory (Custody's own
   E0/E1 case) in principle, not just in practice. This *strengthens*
   Custody's relative position on graph expressiveness specifically: post-
   E1, Custody is ahead of TMA-NM on "can this system represent a
   derivation graph," while TMA-NM remains ahead on "is the authority
   signal itself laundering-resistant." These are different, only
   partially overlapping capabilities — see `NOVELTY_MATRIX.md`'s
   addendum.

Of TMA-NM's 10 requested attack classes, 6 are real, adaptable to Custody
as pure test-harness plumbing (A/B summarization-paraphrase, C
trusted-tool echo, E manufactured corroboration in its base form, H direct
poisoning, I delayed activation); 2 (D cross-agent relay, J mixed-source
derived memory) do not exist in TMA-NM's harness at all, and J is not
representable in TMA-NM's data model even in principle. Case C (trusted-
tool echo) is flagged as the single highest-value next adaptation: this
experiment's own code reading gives high confidence it would reproduce
Custody's red-team case F as a genuine, externally-sourced FAIL, and —
unlike reproducing TMA-NM's own comparative numbers — evaluating Custody's
side of that scenario needs no LLM calls at all, since Custody's decision
is deterministic.

**Verdict stays RESEARCH-ONLY.** This was evidence collection only, not
authorization to build the case-C adapter, and E4/E6 remain unstarted.

## Current next highest-leverage action (post-E2)

Not yet decided in this session — E2 was scoped as evidence collection
only, per its own contract. The registry (`EXPERIMENT_REGISTRY.md`) now
names the case-C adapter as the best-supported next concrete step if and
when a further step is explicitly authorized.
