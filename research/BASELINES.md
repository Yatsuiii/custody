# Baseline Ladder

Strong enough to embarrass Custody, per the brief. Ordered weakest to
strongest. Reproduction status is stated for each — a strawman is only used
where reproduction is documented as infeasible, never by default.

| ID | Baseline | Reproducible? | Notes |
|---|---|---|---|
| B0 | No defense | Trivial, build directly | Raw ADK session -> memory, no gate. |
| B1 | Content/prompt filter only | Reproducible | Route writes through a jailbreak/injection classifier (e.g. reuse Custody's existing Model Armor integration, `live_model_armor.py`, as the filter — it already exists in-repo and is content-only by design). |
| B2 | Provenance metadata only | Reproducible | Tag origin (USER/MODEL/TOOL) at write, never used for revocation or gating beyond that tag — i.e. Custody's `origin.py` labelling with `service.py`'s enforcement gate disabled, records kept but never revocable. |
| B3 | Provenance + naive full-descendant deletion | **Reproducible — this is current Custody**, unmodified: `CustodyGraph.revoke`/`revoke_revision` (`graph.py:149-183`). |
| B4 | MemLineage (weighted derivation DAG, signed provenance) | **Not reproducible in the time available.** No public code repository was located during the literature audit (only the arXiv paper, 2605.14421); the paper's own admission that hosted-model results rely on "auditable logs rather than byte-pinned artifacts" suggests even the authors' own reproduction is partial. Document as infeasible rather than building a strawman. If revisited, contact authors for the harness before assuming it is unreproducible. |
| B5 | TMA-NM (non-malleable, origin-bound authority) | **Best-effort partial reproduction plausible.** The paper claims a released benchmark + harness + TLA+ specs (2606.24322); if the repository is real and accessible, its **laundering test suite specifically** (the 3 channels: summarization, trusted-tool echo, Sybil corroboration) is the single highest-value piece to reproduce, since it is the paper's core claim and the one most directly comparable to Custody's own laundering gaps (D/E/F/H in `CURRENT_CUSTODY_REDTEAM.md`). Full TLA+ proof reproduction is out of scope for an empirical comparison; the benchmark harness is not. **Action item before any experiment**: verify the repo exists and actually runs before committing to this baseline in `EXPERIMENT_REGISTRY.md`. |
| B6 | SMSR (certified statistical robustness) | Possibly reproducible (own 3,150-trial benchmark cited) but **different problem class** — SMSR defends against poisoned writes via majority-voting certificates, not provenance/revocation. Include only as a sanity check that Custody is being compared against the *right* category of defense, not as a same-axis peer. |
| B7 | Current Custody (whole-tool/whole-revision revocation) | Reproducible — the actual system, unmodified, run in its live-proven configuration. **Same object as B3** by construction (naive full-descendant deletion is exactly what `CustodyGraph.revoke` already does) — B3 and B7 are one baseline, not two, and should be reported as such rather than double-counted as independent points. |
| B8 | Proposed dynamic-authority Custody | Not yet built. Depends on H3's kill condition passing first (fix the multi-parent `lineage` bug) before this baseline can be evaluated honestly — see `HYPOTHESES.md` cross-cutting kill condition. |

## Honest correction to the brief's assumed ladder

The brief assumes B3 and B7 are distinct rungs. They are not: B3 ("naive
descendant deletion") *is* what B7 ("current Custody") already does — there
is no separate naive-deletion system to build, `CustodyGraph.revoke` is
that mechanism. Reporting them as two points on the ladder would silently
inflate how many independent baselines Custody is being compared against.
The corrected ladder has **seven** distinct rungs (B0, B1, B2, B3=B7, B4,
B5, B6, B8), and B4 is currently blocked on reproducibility.

## What "embarrass Custody" requires that isn't here yet

A coarse **user/session/app purge** baseline (mentioned in H2 in
`HYPOTHESES.md`) does not exist in Custody today and is not any of B0-B8
above — it must be built fresh (it is a few lines: delete every record for
a given `app_name`/`user_id` regardless of tool) specifically so H2 has a
genuinely coarse comparator, not just "current Custody vs. proposed
Custody." Track this as an explicit build item in
`EXPERIMENT_REGISTRY.md`, not an assumed baseline.
