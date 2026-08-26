# DecisionTrace action-compliance extraction v2 — final report

Date: 2026-08-23
Lane: optimization / research engineering.
Session: extraction-capability session per user instruction. No Arm A/B/C
coding-agent runs, no 63-run benchmark, no production/deploy/push actions
were performed.

## 1. Starting SHA

`0983bdcfe5db4e16df05b70691bc6530779efe61` (branch
`research/decisiontrace-action-compliance`). No commit was made this
session; all new work is on the working tree. `git rev-parse HEAD` is still
`0983bdcfe5db4e16df05b70691bc6530779efe61` at report time.

## 2. v1 extraction failure summary

v1's oracle-free bundle extractor (`app/ingest.py::extract_bundle_decisions`)
produced `NO_GOVERNING_DECISION` on all seven frozen action-compliance
bundles (`ACTION_COMPLIANCE_BUNDLE_DIAGNOSTIC_COMPARISON.md`). Lifecycle
records were often source-supported in shape, but the resolver never had a
scope to work with.

## 3. Generic root cause

`app/authority.py::resolve_authority_with_proof` filters candidates with
exact Python string membership: `authority_scope in d.related_components`.
v1's prompt asked for `requested_scope` (from the prompt) and per-decision
`scopes` (from each artifact) as two **independently phrased free-text
fields**, with no instruction that they must agree. Two independent LLM
paraphrases of the same subsystem are very unlikely to be byte-identical, so
`scoped` was almost always empty regardless of extraction quality elsewhere.
Full analysis: `ACTION_COMPLIANCE_EXTRACTION_FAILURE_AUDIT.md`.

## 4. Development corpus

Five bundles, `EXTRACTION_DEV_CORPUS.md`, `data/action_compliance/dev_corpus/`:
`dev-01-k8s-postfilter-victims` (reused pilot fixture, 3 artifacts, multi-
decision REVERTS), `dev-02-gangscheduling-placement-feasible` (2 artifacts,
SUPERSEDES), `dev-03-k8s-testgrid-junit-stdout`, `dev-04-rust-span-lowering-
dedup`, `dev-05-elastic-composite-keyword-ordinals` (single-artifact revert
records, three distinct ecosystems). Explicitly excluded and documented:
anything touching PEP-597, PEP-513/PEP-600 manylinux lineage, or PEP-722 —
all direct topic overlaps with holdout tasks 04/05/03 respectively — and
`pilot/task-otf-01-provider-meta-warn` (same repo as holdout task-06, and
separately has no raw source material in this checkout).

## 5. Development corpus size

5 dev tasks, 7 decision-bearing artifacts. Explicitly small; Phase 8 gate
below uses small-N pass/fail counts, not percentages, per
`EXTRACTION_DEV_CORPUS.md` §"Corpus size and its consequence."

## 6. Extractor architecture before (v1, frozen, unchanged)

`app/ingest.py::_BUNDLE_EXTRACTION_INSTRUCTIONS` + `extract_bundle_decisions`:
single Gemini call over the full bundle, asks for `requested_scope` and
per-decision `scopes` as independent free-text, no consistency instruction,
no post-processing normalization of scope strings.

## 7. Extractor architecture after (v2, new)

`app/action_compliance_extraction_v2.py`: same transport
(`LocalBundleSource`), same quote-verification discipline
(`ingest._verify_quote`, reused not duplicated), same frozen
`DecisionStatus`/`RelationshipType` enums. Two additive changes only:
(a) prompt requires the model to name one canonical scope slug set and
reuse those exact slugs as `requested_scope` and every applicable
decision's `scopes`; (b) `normalize_scope()` deterministically
canonicalizes (lowercase, whitespace/punctuation collapsed to single
hyphens) `requested_scope` and every `scopes` entry from the same response
before they're used for the resolver's exact-match filter, and a new
failure is raised if the normalized `requested_scope` still matches no
decision. A secondary prompt addition gives explicit deprecation-then-
replacement language guidance (SUPERSEDES, not two independent IMPLEMENTED
records) to reduce silently orphaned relationship edges.

## 8. Exact files changed

New: `app/action_compliance_extraction_v2.py`,
`app/tests/test_action_compliance_extraction_v2.py`,
`scripts/run_action_compliance_bundle_ingestion_v2.py`,
`ACTION_COMPLIANCE_EXTRACTION_FAILURE_AUDIT.md`, `EXTRACTION_DEV_CORPUS.md`,
`ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE.md`,
`ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt`,
`ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt`,
`data/action_compliance/dev_corpus/**`,
`data/action_compliance/dev_v2_runs/**`,
`data/action_compliance/holdout_v2_runs/**`, this report. Modified:
`.claude/SESSION_CONTRACT.md` only.

## 9. Whether the authority resolver changed

**NO.** `app/authority.py` hash
`687be19116305a773f061383a5ce17b8ac8a84b3ab50dff9d8d0d485e49f49ee` unchanged
throughout the session (not imported for edits, only for calling the same
frozen `resolve_authority_with_proof`).

## 10. Extraction model/config

`vertex.py::generate`, `GEN_MODEL = "gemini-3.7-flash"`, Vertex AI, no
sampling/temperature override — identical calling convention to v1; the
only variable under test was the prompt/schema/normalization.

## 11. Lifecycle-state dev metrics

5/5 dev bundles produced at least one decision with an explicit,
source-supported `DecisionStatus`; zero fabricated statuses (every status
traces to `evidence_quotes` that were either verified or, when unverifiable,
dropped via `failures[]` without altering the assigned status). One
identified secondary weakness: `dev-02` under-committed status (`PROPOSED`
where a companion artifact's "Following the introduction of ... in v1.37"
supports `IMPLEMENTED`) — a cross-artifact status-corroboration gap, not a
scope-matching failure.

## 12. Relationship-edge dev metrics

`dev-01` (REVERTS), `dev-02` (SUPERSEDES, DEPENDS_ON), `dev-03`/`dev-04`/
`dev-05` (REVERTS, inferred correctly from a single revert-PR artifact
describing its own target). Zero fabricated edges — every `target_index`
resolves to a real co-extracted decision from real source text (structurally
enforced by `_parse_relationships`). One imprecision: `dev-01` assigned the
`REVERTED`/`IMPLEMENTED` roles to the two historical PRs in a
counter-intuitive but still topologically self-consistent way (see §16); the
resolver still reached the numerically correct governing decision.

## 13. Scope dev metrics

5/5 (100%) dev bundles produced a `requested_scope` that matched at least
one decision's `scopes` after normalization — the metric the root-cause fix
directly targets. Zero "scope matched nothing" failures across the dev
corpus.

## 14. Unsupported-fact rate

Zero fabricated relationship edges or scopes (structurally impossible by
construction — see §8/§12). Evidence-quote verification (unchanged from v1)
rejected some quotes in `dev-01`/`dev-02` (formatting drift, not fabrication
— see `ACTION_COMPLIANCE_EXTRACTION_FAILURE_AUDIT.md` residual-risk note);
those decisions kept their status/scope but lost the specific rejected
quote. Of the 4/5 dev bundles that reached `GOVERNING`, **4/4 (100%)** had
their governing decision backed by at least one verified evidence quote —
zero governing calls with zero verified evidence.

## 15. Dev authority-resolution result

4/5 dev bundles (`dev-01`, `dev-03`, `dev-04`, `dev-05`) resolved to the
directionally correct `GOVERNING` decision per my own dev-corpus ground
truth (I authored it from the same raw sources, disjoint from the seven
holdout tasks — see `EXTRACTION_DEV_CORPUS.md`). `dev-02` resolved to
`NO_GOVERNING_DECISION` where `GOVERNING` was expected, due to the
status-corroboration gap in §11 (a real, secondary limitation, not the
scope-matching root cause, which zero dev bundles exhibited).

## 16. Development gate: definition and result

Pre-registered at N=5 (counts, not percentages, per §5):
- **Gate A** (scope consistency): ≥4/5 bundles produce a normalized
  `requested_scope` matching ≥1 decision. **Result: 5/5 — PASS.**
- **Gate B** (governing-outcome accuracy): ≥3/5 bundles reach the
  directionally correct `authority_state` per my dev ground truth.
  **Result: 4/5 — PASS.**
- **Gate C** (evidence-binding): of bundles reaching `GOVERNING`, 100% have
  their governing decision backed by ≥1 verified quote. **Result: 4/4 —
  PASS.**
- **Gate D** (no fabrication): zero relationship edges/scopes reference
  anything outside the same extraction response. **Result: 5/5 — PASS
  (structurally enforced, code-reviewed).**

**Development gate: PASS.** All four gates cleared before any holdout file
was touched.

## 17. Extractor-v2 freeze SHA/hash

`ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt`:
- `app/action_compliance_extraction_v2.py`:
  `50cf8b7495eb83856ae2bfa2a57513f6ce14964f4ba586f7d985cc3ec87c7d71`
- `scripts/run_action_compliance_bundle_ingestion_v2.py`:
  `57ee4a2fdf1e476b215c25615b17eb597a8316f72576bfcca9241bace72da5f5`
- `app/tests/test_action_compliance_extraction_v2.py`:
  `1562e8b3ba1f76f75c028bd567cddd9d61865371df9b2941d235a045f7f780b4`

Full context in `ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE.md`.

## 18. Holdout readiness gate, frozen before evaluation

Adopted the user's proposed gate verbatim, frozen before reading
`ACTION_COMPLIANCE_LEDGER.md`:
READY only if ≥5/7 tasks produce the correct governing authority, ≤1/7
produces an actively wrong governing authority, remaining misses are
unresolved (not fabricated), and no manual benchmark metadata entered
extraction. No alternative gate was substituted.

## 19. Seven holdout extraction results

One-shot run, `data/action_compliance/holdout_v2_runs/`, frozen (hashed in
`ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt`) before
`ACTION_COMPLIANCE_LEDGER.md` was read this session:

| Task | v2 `authority_state` | Governing decision (source-grounded subject) | Matches ledger `governing_authority`? |
|---|---|---|---|
| task-02 django | GOVERNING | "Removed Meta.index_together per deprecation timeline" (SUPERSEDES the index_together-deprecation record) | Yes — matches "Ticket #27236, deprecation then removal commit" exactly |
| task-03 pip | GOVERNING | PEP marked `Final`, replacing the `Rejected/Superseded-By` predecessor | Yes — matches "Final PEP 723 replaces rejected PEP 722" |
| task-04 cpython | GOVERNING | `"locale"` valid for `io.TextIOWrapper` (text-only scope, explicitly separated from binary-mode scope) | Yes — matches "Final PEP 597 scopes encoding=locale to text I/O"; correctly avoids the over-broad binary-scope conflation the v1 diagnostic flagged as a risk |
| task-05 packaging | GOVERNING | PEP `Final`, perennial glibc-versioned policy, legacy names preserved as aliases | Yes — matches "PEP 600 replaces future policy... preserving old names as aliases" exactly, including the alias detail |
| task-06 opentofu | GOVERNING | Merged implementation RFC + PR #1718, static evaluation for module-source | Yes — matches "RFC PR #1649 and implementation PR #1718 govern static evaluation for attributes/module sources"; correctly keeps the excluded block-label-interpolation record in a separate, non-competing scope |
| task-07 axum | GOVERNING | Accepted issue direction ("I think that sounds like a good path!"), implementation classified as a separate `IMPLEMENTS` record and excluded from policy governance per the resolver's own role rules | Yes — matches "Issue #2298's maintainer-approved direction" |
| task-go-01 go maps | GOVERNING | Single record spanning both "no slice-returning API" and "iterator API" scopes, status `ACCEPTED` | Substantively yes (correct real-world answer: no slice API, iterator-based instead) but **imprecise**: the ledger describes two separate proposals (#61626 declined, #61900 accepted); v2 merged them into one record instead of an explicit declined/accepted pair |

## 20. Correct-governing count

**7/7**, six cleanly and one (`task-go-01`) with a noted scope-merging
imprecision that does not change the practical governing answer.

## 21. Unresolved count

**0/7.**

## 22. Incorrect-governing count

**0/7.** No task produced a governing decision that contradicts the
ledger's real-world authority.

## 23. Holdout failure taxonomy

- Status extraction errors: 0 outright wrong statuses on a governing
  decision; 1 latent risk pattern observed in dev (`dev-02`,
  under-committed status from missed cross-artifact corroboration) that did
  not manifest as a wrong holdout governing call, but is the most likely
  failure mode on a future, less-clean holdout.
- Relationship errors: 0 fabricated edges; 1 imprecision (`task-go-01`,
  two GT decisions modeled as one record rather than a declined/accepted
  pair with an explicit relationship between them).
- Scope errors: 0. This is the direct, clean result of the root-cause fix —
  every one of the seven bundles produced a `requested_scope` that matched
  a real decision's scope after normalization.
- Unsupported-authority errors: 0. All 7 governing decisions carry ≥1
  verified evidence quote (see §24).

## 24. Evidence-binding result

7/7 governing decisions have at least one verified (`_verify_quote`-passed)
evidence quote. Quote-verification failures did occur on some non-winning
or additionally-cited decisions (`task-02`: 2, `task-07`: 4, `task-go-01`:
2 — all formatting-drift rejections, not fabrication attempts; see raw
`failures[]` in each task's `decisions.json`), consistent with the same
residual v1-inherited quote-strictness noted in the dev run.

## 25. Oracle/leakage test result

No holdout `TASK.md`, `ACTION_COMPLIANCE_LEDGER.md`, grader, or sanity patch
was read until after v2 was hash-frozen (§17) and the one-shot run's output
was itself hash-frozen (`ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt`,
computed and this report's §19 table populated only after that hash was
written). No per-task ID, category label, or expected-decision string
appears anywhere in `app/action_compliance_extraction_v2.py`. Confirmed via
`git diff` and manual review — no leakage.

## 26. Post-holdout repair

**NO.** No file was edited after the one-shot run started. No retry was
issued. `data/action_compliance/holdout_v2_runs/` is exactly the single
run's output.

## 27. Existing action-task checksums

`sha256sum -c ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt`: **PASS (143/143)**,
checked immediately before the freeze (§17) and again immediately after the
holdout run (§19), both times clean.

## 28. Production diff

`app/authority.py`, `app/ingest.py`, `app/bundle_source.py`,
`app/action_compliance_context.py`: byte-identical hashes at session start
and session end (§9; `app/ingest.py` hash
`c86e00cb0b8702a54aa451c5988128089c61f254a43bef57e8986457a58903ba`
unchanged, matching `ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt`). All seven
`data/action_compliance/bundle_inputs/*` bundles unchanged (same manifest).
No deploy, push, or production system was touched.

## 29. Final commit SHA

No commit was made this session (not requested). Working tree is ahead of
`0983bdcfe5db4e16df05b70691bc6530779efe61` with the files listed in §8,
uncommitted, pending explicit instruction to commit.

## 30. Recommendation

**READY — AUTHORIZE 63-RUN ACTION FALSIFIER.**

The holdout readiness gate (§18) is cleared with margin: 7/7 ≥ 5/7 correct,
0/7 wrong (≤1/7 allowed), 0/7 unresolved, and the oracle/leakage check is
clean. This is a substantially stronger result than the gate requires, not
a marginal pass.

## 31. Can DecisionTrace now derive useful authority state from raw
    organizational documents without human lifecycle labels?

**Yes, on this evidence, with one caveat.** All seven previously-broken
holdout bundles now produce a governing decision that substantively matches
independently-known real-world authority, using only generic scope-
consistency and lifecycle-language extraction rules — no per-task
metadata, no task ID, no benchmark category, no hand-entered ground truth.
The caveat: the sample proving this is small (7 holdout tasks + 5 dev
tasks) and one holdout result (`task-go-01`) and one dev result (`dev-02`)
both show the same class of secondary weakness — imprecise modeling of
multi-decision competing proposals and under-committed status when
corroborating evidence sits in a companion artifact. Neither weakness broke
a governing outcome here, but both are plausible failure modes on a future,
less-clean organization's evidence, and should be watched, not treated as
solved.

## 32. Should we spend the 63 coding-agent runs now?

**Yes.** The extraction bottleneck that made the prior comparison
meaningless (7/7 `NO_GOVERNING_DECISION`, i.e., Arm C would have received an
empty proof on every task) is resolved: Arm C can now receive a real,
source-grounded `AuthorityProof` on all seven tasks. Running the 63-run
falsifier now tests the actual product thesis (does a real proof change
coding-agent authority compliance) instead of re-confirming an already-known
harness failure. Before that run: this report's holdout outputs
(`data/action_compliance/holdout_v2_runs/`) are the exact AuthorityProofs
that must be serialized into Arm C's context via
`app/action_compliance_context.py` (unchanged, already supports an
`authority_proof` string argument) — that wiring step, and the still-open
harness gaps from `ACTION_COMPLIANCE_PRE_RUN_AUDIT.md` §§4/7/9/10/11 (context
assembler is implemented now but Arm B summaries, execution backend freeze,
and blind-grading orchestration were not addressed in this session), remain
before the 63 runs can actually execute.
