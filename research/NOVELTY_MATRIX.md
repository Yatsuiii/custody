# Novelty Matrix

Rows are the properties that matter for the candidate thesis. Columns are
current Custody and the closest real prior art (see `RELATED_WORK_AUDIT.md`
for full citations). `?` = not directly evaluated in that paper's own
reported results, inferred from stated scope.

| Property | Current Custody | TMA-NM (2606.24322) | MemLineage (2605.14421) | MemSecBench (2607.27080) | Survey (2604.16548) | Proposed Custody 2.0 |
|---|---|---|---|---|---|---|
| Structural origin labelling at write | Yes (`origin.py`) | Yes | Yes (signed) | N/A (benchmark) | Framework only | Yes (reuse) |
| Authority tracked separately from content | No — trust is `Trust.TRUSTED/UNTRUSTED` baked into the record at write, not a separable field | **Yes, formally, central contribution** | Partial (lineage-derived score) | N/A | Named as a governance objective | Must adopt TMA-NM's separation or explain why not |
| Derivation/lineage graph | Yes, but single-parent-per-invocation (`lineage` dict bug, `origin.py:240`) | Yes | Yes, weighted DAG | No graph, prompt-based repair | Named, not solved by any cited system | Must fix multi-parent bug first (H3 kill condition) |
| Laundering-resistant matching | **No — exact content-hash only** (`graph.py:187-197`) | **Yes, 0% laundering ASR, proven (T1)** | Not tested | Not tested | Named as open field-wide | Open question — no existing reusable mechanism found |
| Binary trust vs. trust epoch/interval | **Binary only, no epoch anywhere in code** | Binary (write-time bound, non-malleable) | Weighted threshold, still static per snapshot | Behavioral, no epoch model | **Named explicitly as unexplored** ("does not deeply explore bounded-interval revocation") | Core proposed contribution |
| Source legitimately trusted, later found compromised (t0→t2 model) | Supported operationally (`/demote`) but revocation is whole-tool-lifetime, not interval-scoped | **Not the threat model — write-time laundering prevention only** | Not modeled | Implicit only | Named, not solved | Core proposed contribution |
| Retroactive revocation after descendants exist | **Yes — already shipped**, whole-tool/whole-revision granularity (`graph.py:149-183`) | **Confirmed absent** | **Confirmed absent** | Yes, but 30-pt precision/preservation gap | Named as underexplored at bounded-interval granularity | Must beat current Custody's own baseline (H1/H2) |
| Selective (vs. coarse) repair | Yes at tool/revision granularity, not sub-interval | No repair mechanism at all (prevention-only design) | No repair mechanism at all | Attempted, weak (56.1% repair, 30pt collateral gap) | Named as limited field-wide | Must show ≥0.15 precision gain over current Custody (H2) |
| Cross-agent/fleet propagation modeled | Yes, live-proven (`live_chain.py`, `live_fleet.py`) | Not the focus | Not evaluated at fleet scale | Not evaluated at fleet scale | Named as its own lifecycle phase | Reuse Custody's existing fleet mechanism |
| Machine-checked / formally proven guarantees | No | **Yes, TLA+** | No | No | N/A | Not attempted — explicitly named as a Phase 7 non-goal unless a specific adversary requires it |
| Reproducible benchmark released | No dedicated poisoning/revocation benchmark, only demo fixtures | Yes | Yes | Yes | N/A (survey) | Required if this proceeds — see `BENCHMARK_PLAN.md` |

## Reading this matrix honestly

Two rows should worry the project more than any absence of prior art does:

1. **"Authority tracked separately from content"** — Custody is a **No**
   here, and TMA-NM is a proven **Yes** with a formal separation theorem
   that specifically indicts content/lineage-only defenses under
   laundering. Custody's structural origin labelling is real and
   well-engineered, but it is not the same claim as TMA-NM's, and where
   they overlap (laundering resistance), Custody is currently the weaker
   system, not a peer.
2. **"Laundering-resistant matching"** — Custody's own background note in
   this review already conceded this before the literature audit ran; the
   audit confirms it is not merely a Custody-specific gap but a proven
   theoretical limit of the *mechanism class* (content-hash/lineage-only)
   Custody uses.

## Addendum, E2 (2026-08-22): verified against TMA-NM's actual code, not just its abstract

`research/experiments/E2_TMANM_REPRO/` independently cloned and partially
reproduced TMA-NM's released harness. Two corrections to the table above,
both strengthening rather than weakening the novelty case:

- The **"Laundering-resistant matching"** row's TMA-NM cell should read
  more precisely as "Yes, against the author's own hand-built generic
  `lineage`-class stand-in" — not against Custody's or MemLineage's actual
  code. No head-to-head number between TMA-NM and Custody specifically
  exists; the only real head-to-head test would require adapting TMA-NM's
  harness to call Custody directly (assessed feasible for 6 of 10 attack
  classes in `research/experiments/E2_TMANM_REPRO/CUSTODY_ADAPTER_MAP.md`,
  not yet built).
- A new fact belongs in the **"Derivation/lineage graph"** row: TMA-NM's
  `MemoryItem` has no `derived_from`/lineage field at all — it is
  architecturally incapable of representing a multi-parent synthesized
  memory (Custody's own E0/E1 case), regardless of whether it is tested.
  This is a genuine structural difference, not just an untested gap: on
  the "can this system represent a derivation graph" axis, Custody (post-
  E1 fix) is now ahead of TMA-NM, not behind it — the earlier reading that
  Custody was simply "the weaker system" on this row overstated the case.
  TMA-NM remains ahead specifically on *laundering resistance of the
  authority signal itself*; Custody is ahead on *derivation-graph
  expressiveness*. These are genuinely different, only partially
  overlapping capabilities, not one system strictly dominating the other.

The one row where Custody is unambiguously ahead of every paper found is
**"Retroactive revocation after descendants exist"** — Custody already
ships this, live-proven at fleet scale, and no other reviewed system does
at all (two of them confirm its absence in their own text). This is real
and should not be discounted. But it is coarse (whole-tool/whole-revision),
and the row the field survey explicitly names as unexplored —
bounded-interval revocation — is exactly the next increment from where
Custody already stands, not a from-scratch problem.

**Net reading**: the thesis's proposed contribution is not "provenance for
agent memory" (solved, multiple ways, better than Custody in the
laundering dimension by TMA-NM) and not "retroactive revocation exists"
(Custody already has it). It is the **intersection** of trust-epoch/interval
scoping (novel per the survey's own admission) applied to a derivation
mechanism that must first be made at least as laundering-resistant as
today's exact-hash approach, or the interval-scoped repair will just be a
more precise version of a mechanism that still misses laundered
descendants. That intersection is not occupied by anything found in this
audit.
