# One-Page Proposal (draft — RESEARCH-ONLY status, not yet ready to submit)

## Problem

LLM-agent fleets accumulate persistent memory from tools/sources that were
legitimately trusted at write time. When such a source is later discovered
compromised — sometimes only during a bounded sub-interval of its trusted
lifetime — existing systems either cannot revoke propagated influence at
all (most provenance/authority work is write-time prevention only), or can
only revoke at whole-source granularity (current Custody), destroying
benign memory from the same source's uncompromised periods.

## Precise gap

Verified against 9 independently-confirmed papers plus a field survey
(`research/RELATED_WORK_AUDIT.md`): no located system combines (a)
retroactive revocation scoped to a bounded trust interval rather than a
source's whole lifetime, with (b) derivation matching that survives
laundering (paraphrase, trusted-tool echo, cross-agent relay, manufactured
corroboration) well enough for that scoping to be trustworthy. TMA-NM
(arXiv:2606.24322) solves (b) at write time but explicitly does not address
retroactive revocation. Current Custody solves a coarse version of
retroactive revocation but uses exact-content-hash matching, which TMA-NM's
own theorem proves is unsound under laundering, and has two independently
verified correctness bugs (H/R, silently-dropped multi-parent derivation
edges) in the mechanism any interval-scoped revocation would need to sit
on.

## Research question

When a source is legitimately trusted at t0, propagates influence across
agents/sessions at t1, and is discovered compromised only during
`[t_a, t_b]` at t2, can a fleet revoke exactly that interval's influence —
surviving laundering — with materially less collateral damage than
whole-source revocation?

## Hypothesis (summary — full preregistration in `HYPOTHESES.md`)

H1-H2: interval-scoped revocation reduces post-revocation harmful-action
success and improves repair precision vs. current Custody's whole-tool
revocation, without meaningfully sacrificing recall. H3: fixing the
multi-parent derivation bug closes most of the deterministic laundering
gap; a full laundering-resistant mechanism closes more. H4: this holds
even when the compromise window is only approximately known.

## Proposed method

1. Fix the multi-parent `derived_from` bug in `custody/origin.py:240`
   (E0/E1 — cheap, deterministic, gates everything else).
2. Add a minimal trust-epoch data model (bounded validity interval per
   grant, not just binary trusted/untrusted).
3. Extend `CustodyGraph` with interval-scoped traversal
   (`descendants_for_interval`/`revoke_interval`), reusing the existing
   `_walk` BFS rather than replacing it.
4. Evaluate on a new benchmark slice (`BENCHMARK_PLAN.md`) built because no
   existing benchmark covers this axis — confirmed, not assumed.

## Baselines

B0 (none), B1 (content filter), B2 (provenance-only), B3=B7 (current
Custody's existing whole-tool revocation — the primary baseline this must
beat), B5 (TMA-NM's laundering suite, if its released harness proves
reproducible — unverified as of this writing), a newly-built coarse
user/session purge baseline. B4 (MemLineage) documented as
not-reproducible: no public repo located.

## Evaluation

Paired Recovery/Collateral Pareto frontier (`METRICS.md`) against the
baseline ladder, not a single blended score — a single "Post-Compromise
Recovery Rate" number was explicitly rejected because it can hide
collateral damage (a system that deletes a compromised tool's entire
history scores well on recovery alone while destroying far more benign
memory than an interval-scoped system would).

## Expected contribution, if E0-E9 confirm the hypotheses

A benchmarked demonstration that bounded-interval revocation, combined with
laundering-aware derivation tracking, dominates whole-source revocation on
the Recovery/Collateral frontier — occupying the specific, field-recognized
gap between TMA-NM (write-time, no revocation) and current Custody
(retroactive, but interval-blind and laundering-fragile).

## What would falsify it

- E1: if fixing the multi-parent bug does not close most of the
  deterministic multi-source laundering gap (H3's kill threshold), the
  derivation graph is not a sound foundation for interval scoping and the
  project stops here.
- E7: if the interval-scoped system's Pareto point is statistically
  indistinguishable from current Custody's, on the preregistered confidence
  intervals in `HYPOTHESES.md`, this is a null result and must be reported
  as one.
- If a reproducible TMA-NM artifact turns out to already support
  interval-like scoping on closer inspection (unconfirmed either way by
  this audit), the research question shrinks or closes entirely.

## Status

RESEARCH-ONLY. This document is a draft proposal, not a submission. Next
step: run E0/E1 only (`EXPERIMENT_REGISTRY.md`) before any further
commitment.
