# E1 — Result

## Fix implemented

`custody/origin.py`: `lineage` changed from a single
`(record_id, source_tool, source_revision)` triple per invocation to a
tuple of triples, accumulated (appended) rather than overwritten, at every
trusted/citation-resolved tool response. A MODEL or DERIVED turn's
`derived_from` is now `tuple(p[0] for p in predecessors)` — every
accumulated predecessor, not just the last one — and the invocation's
lineage state then collapses to that turn's own single id, so a later turn
depends on the synthesis, not redundantly on the synthesis's own
now-transitively-reachable ancestors (preserves the existing chain-not-
shortcut behavior).

Three call sites changed, all inside `_attribute` in `custody/origin.py`:
the TOOL branch (append instead of overwrite), the DERIVED branch (walk
all accumulated predecessors), the MODEL branch (same). No change to
`custody/graph.py`, `custody/catalog.py`, `custody/service.py`,
`custody/action.py`, `custody/revision.py`, or any adapter — matches the
session contract's allowed-file scope exactly.

No trust epochs, authority lattices, signatures, semantic/LLM matching, or
hypergraph were introduced. `CustodyRecord.derived_from` remains a plain
`tuple[str, ...]`; the DAG representation was not changed, only what
populates it (confirmed necessary and sufficient by E0's root-cause
analysis).

## Attack-case results (all 10 required by the user)

| # | Case | Result |
|---|---|---|
| 1 | A + B → AB | **PASS** — `derived_from` lists both roots |
| 2 | A + B + C → ABC | **PASS** — three-way synthesis, `derived_from` lists all three |
| 3 | A→X; B→Y; X+Y→Z | **PASS** — revoking A reaches Z via A→X→Z; revoking B reaches Z via B→Y→Z, independently confirmed both directions |
| 4 | A and B contain overlapping text | **PASS** — matching is structural (event/invocation position), not content-diffing, so textual overlap between parents has no effect on edge construction |
| 5 | One parent contributes only a small substring | **PASS** — same reason as #4; the fix has no notion of contribution *weight*, so a weak contributor still gets a full edge (this is also case S's known limitation, unchanged — see below) |
| 6 | Paraphrase-free synthesis, derived text ≠ either parent | **PASS** — confirmed the synthesis text is not equal to either source text, edge still constructed correctly |
| 7 | Repeated retrieval, A→X→Y→Z | **PASS** — chain stays single-parent per hop, no shortcut introduced (regression-guarded by `test_a_chained_restatement_is_still_two_hops_not_a_shortcut`) |
| 8 | Convergence, A→X and B→X | **PASS** — same mechanism as case 1, confirmed directly |
| 9 | Divergence then reconvergence, A→X→Z and A→Y→Z | **PASS** — X and Y each independently cite A (existing resolver mechanism), a later invocation retrieves both and synthesizes Z; Z's `derived_from` lists both X and Y, and revoking A reaches Z through either path |
| 10 | Unrelated C untouched when A is revoked | **PASS** — confirmed C survives, unchanged from pre-fix behavior |

All 10 verified against real production code (`take_custody` +
`CustodyGraph`, plus `CustodyGraph.resolve` for case 9's cross-invocation
citation), not a parallel toy model.

## Independent check (user's 6-point list)

1. **Full existing suite**: `python -m unittest discover tests` — 381
   tests, 0 failures, 0 errors (377 baseline + 4 new tests added in E0/E1).
   Ran via `.venv/bin/python`, the project's pinned environment.
2. **New falsifier**: `tests/test_origin.py::MultiParentSynthesisE0` — 4
   tests, all pass (multi-parent synthesis, three-way synthesis, symmetric
   revocation, chain-not-shortcut regression guard).
3. **Existing single-parent behavior unregressed**: confirmed by the same
   381-test run, specifically
   `tests/test_graph.py::RetrievalIsAttributedAsACitation` (chained
   restatement semantics) and every other pre-existing `origin.py`/
   `graph.py` test, all still passing unmodified.
4. **Persisted graph inspected directly**: `CustodyRecord.derived_from`
   tuples were read and asserted directly in every case-1/2/3/8/9 check
   above, not inferred from revocation counts alone (E0's own finding was
   that a correct-looking revocation result without inspecting
   `derived_from` directly would be misleading — this was not repeated
   here).
5. **Revocation from every root independently**: case 3 and case 9 both
   revoke from each distinct root separately, on fresh graphs, and confirm
   the shared/converged descendant is reached from either side.
6. **Replay/idempotency**: confirmed on the case-1 scenario — replaying
   `revoke(tool="crm_lookup", revocation_id="rev-1")` returns an equal
   `Revocation`, logs exactly one revocation, and the graph size is stable
   across the replay.

No unrelated failures were encountered or repaired, per the user's
instruction to leave unrelated issues alone.

## Strongest failure still remaining

**Weighted/partial attribution (case S) is unchanged by this fix and
remains open.** Case 5 above confirms directly: a parent contributing only
a small substring gets exactly the same full-strength edge as a parent
contributing most of the content. The fix corrects *whether* an edge
exists, not *how much* a given ancestor actually mattered — that remains
a genuinely different, harder problem (weighted contribution, not just
correct connectivity), and this experiment was explicitly scoped not to
attempt it (no semantic/LLM classification, per the user's constraints).

The fix also does not touch cross-session laundering (paraphrase,
trusted-tool echo defeating exact-hash matching, D/E/F in
`CURRENT_CUSTODY_REDTEAM.md`) — case 9 worked specifically because the two
citations matched their source text *exactly* via `resolve()`; a
paraphrased citation would still fall through to the pre-existing,
unfixed exact-hash limitation. This was explicitly out of scope for E1 and
remains exactly where the literature audit (TMA-NM) already found it.

## Regression risk assessment

Low. The change is additive at three call sites within one function
(`_attribute`), the type change (`tuple[triple]` instead of `triple`) is
internal to `take_custody` and never crosses `_attribute`'s boundary into
`CustodyRecord` itself (which was already multi-parent-capable), and the
full existing suite passes unmodified. `descendants`/`revoke`/`_walk` in
`custody/graph.py` were not touched at all — E0 already established they
did not need to be.
