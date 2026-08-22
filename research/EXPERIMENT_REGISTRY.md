# Experiment Registry

Template populated with the concrete first experiments this thesis needs,
in dependency order. Nothing below has been run. Status is tracked
honestly; do not mark PASS/FAIL until the experiment actually executes.

| # | Experiment | Depends on | Hypothesis | Status | Artifact path (when run) |
|---|---|---|---|---|---|
| E0 | Reproduce the `lineage` single-slot bug (`origin.py:240`, pre-fix) using real `take_custody`+`CustodyGraph` production code: two trusted tool calls in one invocation, one model-turn synthesis of both, revoke each source independently. | None | Cross-cutting kill condition, `HYPOTHESES.md` | **DONE — bug confirmed and code-located.** Asymmetric failure reproduced exactly as predicted: `derived_from` retained only the most-recently-seen parent; revoking the *other* parent's tool missed the synthesis entirely. Root cause isolated to `custody/origin.py`'s `lineage` dict; `custody/graph.py` traversal already correct. | `research/experiments/E0_CURRENT_LINEAGE_REPRO/{PLAN,RESULT}.md`, `tests/test_origin.py::MultiParentSynthesisE0` (committed pre-fix, then updated to fixed-behavior assertions per E1) |
| E1 | Minimal fix: `lineage` accumulates every distinct trusted arrival per invocation instead of overwriting; `derived_from` becomes the full accumulated set on a synthesizing turn. No trust epochs, no semantic matching, no hypergraph. | E0 | H3 (multi-source synthesis sub-case only — the deterministic part) | **DONE — PASS.** All 10 user-specified attack cases (A+B→AB through unrelated-C-survives) pass against real production code. Full existing suite (381 tests, was 377) passes with 0 regressions. Idempotent replay confirmed. Cross-cutting kill condition (`HYPOTHESES.md`) **cleared**: the deterministic multi-source miss is fully closed, not just partially improved — stronger than the ≥0.30-absolute-improvement PASS threshold, which assumed a probabilistic result; this one is 100% (10/10) on the deterministic sub-case actually tested. | `research/experiments/E1_MULTIPARENT_LINEAGE/{PLAN,RESULT}.md`, `custody/origin.py` (3 call sites in `_attribute`), `tests/test_origin.py` (4 new tests) |
| E2 | Verify TMA-NM's benchmark/harness repository actually exists and runs (per `BASELINES.md` B5 action item) before relying on it anywhere else in this registry. | None | Gates B5 in `BASELINES.md` | **DONE — EXTERNAL-HARNESS-PARTIAL.** Repo verified real via ground-truth `gh api` (not AI-summarized guess), pinned at `63f1359d677efbe1a65b982b2a54cabfec97f1e1`. Offline/no-cost formal reproduction (`test_monitor.py`, `check_invariant.py`) PASSED cleanly, no fix needed. LLM-backed empirical runs BLOCKED (no OpenRouter key obtained, no spend authorized) — read as source code instead; author's own logged `results/*.json` used as secondary, self-reported evidence only. 6/10 attack classes (A,B,C,E,H,I) found IMPLEMENTED and adaptable to Custody as pure harness plumbing; D (cross-agent relay) and J (mixed-source derived memory) NOT PRESENT in TMA-NM at all — J is architecturally unrepresentable in TMA-NM's data model (no lineage field). | `research/experiments/E2_TMANM_REPRO/{PLAN,SOURCE_AUDIT,REPRODUCTION,ATTACK_MATRIX,CUSTODY_ADAPTER_MAP,RESULT}.md` |
| E3 | Build the coarse user/session/app purge baseline (does not exist in Custody today, per `BASELINES.md`). | None | H2 | NOT STARTED | — |
| E4 | Build the benchmark harness for the canonical post-hoc-revocation scenario and its 9 variants (`BENCHMARK_PLAN.md`), generating ground-truth ancestor sets so "graph descendants correctly identified" (`METRICS.md`) can be scored automatically. | None (can run in parallel with E0-E3) | Enables H1/H2/H4 | NOT STARTED | — |
| E5 | Run B0/B1/B2/B7 (=B3) through E4's harness as the baseline sweep, before any new mechanism is built. This is the number that must show B7 already beating B0/B2 (H1's sanity check) — if it doesn't, stop and investigate the harness, not the thesis. | E4 | H1 sanity check | NOT STARTED | — |
| E6 | Design and implement the minimal trust-epoch data model (extends `Grant`/`ToolTrust` with a validity interval) and interval-scoped `descendants_for_interval`/`revoke_interval`, reusing `_walk`'s existing traversal. | E0, E1 pass | H1, H2, H4 | NOT STARTED | — |
| E7 | Run B8 (E6's system) through E4's harness, plot the Recovery/Collateral Pareto frontier against B7 per `METRICS.md`'s adopted primary metric. | E5, E6 | H1, H2 | NOT STARTED | — |
| E8 | Run the uncertain-window and retroactively-widened-window variants specifically for H4. | E7 | H4 | NOT STARTED | — |
| E9 | E2 confirmed TMA-NM's harness is real and its offline formal claims reproduce, but its actual laundering-*generator* scenarios (the ones that would produce a comparable ASR number) are cost/API-key-gated and were not run. Adapt case C (trusted-tool echo, the highest-confidence-of-failure case per `CUSTODY_ADAPTER_MAP.md`) as harness plumbing against B7/B8 — this specific adaptation needs no LLM calls on Custody's side, since Custody's own decision is deterministic. If this is not pursued, report H3's laundering sub-case using this project's own generators only, flagged as not independently cross-validated. | E2 (done), E6 | H3 | NOT STARTED | — |

## Kill/pivot checkpoints tied to this registry

- After E1: if H3's cross-cutting kill condition fails, stop. Ship E0/E1 as
  a standalone bug-fix contribution to current Custody (real, small,
  legitimate), and do not proceed to E6-E9 under this thesis.
  **Checkpoint reached and cleared (see `research/experiments/
  E1_MULTIPARENT_LINEAGE/RESULT.md`).** This is a gate-clearing result, not
  a green light for E6-E9: per this session's own scope ("NOT permission
  to begin Custody 2.0"), E2-E9 remain NOT STARTED and un-authorized until
  a separate, explicit decision to proceed is made. E0/E1 stand on their
  own as a legitimate, shippable fix to current Custody regardless of what
  happens to the larger thesis.
- After E2: **checkpoint reached (EXTERNAL-HARNESS-PARTIAL).** Per this
  session's scope, this is evidence collection only, not authorization to
  build the case-C adapter or proceed to E4/E6. The next explicitly
  authorized step, if any, is a separate decision.
- After E5: if B7 does not clear its own sanity-check bar, the benchmark
  harness (not Custody) is suspect — fix E4 before trusting any later
  result.
- After E7: this is the actual go/no-go point for the whole thesis. If
  B8's Pareto point is not distinguishable from B7's, report a null result
  per `METRICS.md`'s kill condition rather than reframing the metric.
