# Authority-Proof Port Plan

Written before any product file is edited, per session contract Phase 2.

## Diff scope confirmed

`git diff 1c33d3d 96cc921` (frozen product vs. the live-integration-
verified research checkpoint) touches **1199 files** in total, almost
entirely `decision-trace/data/**`, prospective/authority-benchmark
scripts, and research handoff docs — none of that is ported.

Restricted to `decision-trace/app/`, the diff is exactly 11 files, 1263
insertions / 32 deletions:

```
app/authority.py                              370  (new file)
app/collaborate.py                             83  (+explain_authority)
app/graph.py                                   95  (+structured lifecycle_events, complexity refactor)
app/models.py                                   9  (+partial_acceptance field)
app/store.py                                    1  (round-trip fix)
app/tests/test_authority.py                    58  (1 test corrected, defect fix)
app/tests/test_authority_explanation.py        96  (new)
app/tests/test_authority_proof.py             296  (new)
app/tests/test_authority_regression_prospective.py 110 (new)
app/tests/test_evidence_completeness.py       109  (new)
app/tests/test_store.py                        68  (Firestore serialization + round-trip tests)
```

`README.md`/`docs/**` are byte-identical between the two commits — the
76%-vs-57% claim was never touched by the research branch and still
needs cleanup here (Phase 11, separate from the port itself).

## What gets ported, verbatim

The 11 files above, applied as `git diff 1c33d3d 96cc921 -- decision-
trace/app/` against this branch. This is a clean, mechanical port: the
research branch's `app/` tree diverged from the frozen product at
exactly this diff and nowhere else, so there is no merge conflict risk
and no reconciliation needed — the frozen product's `app/ui.py`,
`app/ingest.py`, `app/retrieval.py`, `app/memory.py`, `app/loader.py`
are untouched by the research branch and stay exactly as they are on
`explore/decision-trace-v0`.

## What is deliberately NOT ported

- `decision-trace/data/authority/**`, `decision-trace/data/prospective/**`,
  `decision-trace/data/runs_authority*/**` — benchmark/prospective run
  artifacts.
- `decision-trace/data/v2/**`, `decision-trace/data/runs_v2/**` — plateau
  research artifacts.
- `AUTHORITY_BENCHMARK_*.md`, `RESULTS_AUTHORITY*.md`,
  `AUTHORITY_PROSPECTIVE_*.md`, `AUTHORITY_OUTCOME_LEDGER.md`,
  `POSTRUN_AUTHORITY_VALIDITY_AUDIT.md`, `PROSPECTIVE_RESOLVER_FREEZE.md`,
  `BENCHMARK_*.md`, `RESULTS.md`, `RESULTS_V2.md` — research score/audit
  docs. These stay on the research branch only; the product doesn't need
  them and porting them would put unvalidated research claims in a
  product-facing location.
- `build_authority*.py`, `run_authority*.py`, `grade_authority*.py`,
  `audit_authority*.py`, `prepare_authority_prospective.py`,
  `collect_prospective_sources.py`, `write_authority_prospective_ledger.py`,
  `write_prospective_changed_files.py`, `process_boundary_authority.py`,
  `mine_decisions.py` changes tied to research, `backfill_rationale_cards.py`,
  `expand_falsifier_sample.py`, `reextract_kep_quotes.py` — all
  research-only scripts, never imported by `app/`.
- `test_authority_process_boundary.py`, `test_no_leakage_authority*.py`,
  `test_prospective_*_freeze.py` — benchmark-protocol guard tests, not
  product tests (they assert properties of research artifacts that don't
  exist in the product).
- `AUTHORITY_PROOF_AUDIT.md`, `AUTHORITY_SEMANTICS.md`,
  `AUTHORITY_PROOF_ARCHITECTURE_REVIEW.md`, `AUTHORITY_UI_CONCEPT.md`,
  `INTEGRATION_ENVIRONMENT_REPORT.md` — research-session process docs.
  These stay on the research branch as the historical record; this
  integration session writes its own docs (`PORT_PLAN.md`, this file,
  plus an end-of-session decision doc) rather than dragging research
  docs into the product tree.

## New product-side work beyond the mechanical port

The mechanical port alone gives the product a working `authority.py`
and an `explain_authority` function, but does not yet:

1. Wire `resolve_authority_with_proof` into the actual worker pipeline
   `collaborate.answer()` uses — `explain_authority` exists as a
   standalone function today, callable but not called from anywhere in
   the product's question-answering flow. This needs a scope-aware entry
   point (Phase 5).
2. Surface `AuthorityProof` in `app/ui.py` — no UI change was made on
   the research branch at all (`AUTHORITY_UI_CONCEPT.md` was concept-
   only). This needs the minimal "CURRENTLY GOVERNING / WHY THIS
   GOVERNS" addition (Phase 6).
3. Remove the 76%-vs-57% claim from `README.md` and
   `docs/DEMO_SCRIPT.md` (Phase 11) — confirmed present at
   `README.md:55-58` and `docs/DEMO_SCRIPT.md:39-40`.

## Requested-scope question for the UI wiring

The product's existing `collaborate.answer()` is a free-text Q&A flow
(no explicit "authority scope" parameter — it does semantic retrieval
over all decisions and per-lineage `ActiveResolution`, not scope-based
resolution). `resolve_authority_with_proof(decisions, authority_scope)`
needs a scope string. The smallest bridge: derive the scope from the
decision(s) already surfaced by retrieval — when the user's question
resolves to a specific decision (the existing `RetrievalCandidate`/
`is_current` path), use that decision's own `related_components[0]` (or
all of them) as the queried scope(s) and additionally run the authority
resolver, attaching its `AuthorityProof` to the `Answer`. This does not
change what retrieval returns; it adds a second, deterministic
computation alongside it. See Phase 5 implementation for the exact
function.

## Sequencing

1. Apply the mechanical port (`authority.py`, `graph.py`, `models.py`,
   `store.py`, `collaborate.py`'s `explain_authority`, ported tests).
2. Add the new wiring function connecting retrieval's resolved decision
   to `resolve_authority_with_proof` and attach the proof to `Answer`.
3. Add the UI's proof rendering.
4. Remove the stale benchmark claim.
5. Test (offline, then real integrations).
6. Local demo replay.
7. Preview deploy.
