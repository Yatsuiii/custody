# Extraction v2 development corpus

This list is permanent: every example named here is permanently excluded
from the seven-task action-compliance benchmark and from any future
action-compliance holdout. Ground truth for these tasks was authored by me
(Raghav's assistant) in this session from the same raw source material now
included in each bundle, using ordinary domain knowledge of the linked
PRs/KEPs — not derived from, or checked against, any of the seven frozen
holdout tasks' `TASK.md`, ledger row, grader, or sanity patch.

## Included dev bundles

| Dev ID | Source | Artifacts | My ground-truth call |
|---|---|---|---|
| `dev-01-k8s-postfilter-victims` | `pilot/task-01-k8s-postfilter-victims` (full `TASK.md` + `context_bundle/`, prepared via `scripts/prepare_action_compliance_bundle.py`, unchanged) | 3 (`PR #136254` original, `PR #137662` revert, current-code excerpt) | Governing: `PR #137662` (REVERTED-as-rollback / REVERTS edge over `PR #136254`), scope = the shared out-of-tree `fwk.PostFilterResult` API. This is the harness's own pilot fixture, explicitly excluded from the seven-task statistical inventory already; it is not the same task as any of the seven. |
| `dev-02-gangscheduling-placement-feasible` | `pilot/task-k8s-02-gangscheduling-placementfeasible-activation/context_bundle` (2 files, verbatim); `requested_change.txt` written by me, generically, from the same context — this task has no `TASK.md` in the repo | 2 (KEP-4671 excerpt, PR #141182) | Governing: `PlacementFeasible` extension point SUPERSEDES `Permit`/`permitPodGroup` for pod-group feasibility/quorum decisions, per the KEP's explicit "tried Permit, abandoned it" statement and the in-flight removal PR. |
| `dev-03-k8s-testgrid-junit-stdout` | `data/v2/rag-target-index/kubernetes-kubernetes-revert-129701.json` (raw revert-PR body, single artifact); `requested_change.txt` written by me | 1 | Governing: `PR #129701` REVERTED (single-artifact case — no separate "original" text is available in this corpus, so the correct extraction is one REVERTED record with no resolvable REVERTS target, not a fabricated pair). |
| `dev-04-rust-span-lowering-dedup` | `data/v2/rag-target-index/rust-lang-rust-revert-149060.json` (raw revert-PR body, single artifact); `requested_change.txt` written by me | 1 | Governing: `rust-lang/rust#149060` REVERTED for a stated performance regression; same single-artifact shape as dev-03. |
| `dev-05-elastic-composite-keyword-ordinals` | `data/v2/rag-target-index/elastic-elasticsearch-revert-152050.json` (raw revert-PR body, single artifact); `requested_change.txt` written by me | 1 | Governing: `elastic/elasticsearch#152050` (and `#152433`) REVERTED for a stated regression; same single-artifact shape. |

All five are real source text — no artifact content was fabricated. Only
the `requested_change.txt` prompt text for dev-02/03/04/05 was written by me
(dev-01 reuses its existing pilot `TASK.md` prompt verbatim); dev prompts are
not benchmark ground truth and never enter the holdout.

## Considered and explicitly excluded (topical overlap with the seven
   holdout tasks)

| Candidate | Why excluded |
|---|---|
| `data/authority/cache/{rag,structured}/python-encoding-warning-*.json` | Subject is PEP-597 ("Add optional EncodingWarning") — the exact PEP governing holdout `task-04-cpython-locale-encoding-scope`. |
| `data/authority/cache/{rag,structured}/manylinux-policy-*.json`, `manylinux-unified-*.json` | Subject is PEP-513 ("A Platform Tag for Portable Linux Built Distributions") — the direct predecessor in the same manylinux-alias lineage as PEP-600, which governs holdout `task-05-packaging-manylinux-aliases`. Developing scope/relationship rules against PEP-513 would implicitly tune for the PEP-600 supersession chain. |
| `data/authority/cache/{rag,structured}/single-file-metadata-*.json` | Subject is PEP-722 ("Dependency specification for single-file scripts") — the exact PEP superseded by PEP-723 in holdout `task-03-pip-inline-script-metadata`. |
| `pilot/task-otf-01-provider-meta-warn` | Same repository (`opentofu/opentofu`) as holdout `task-06-opentofu-static-source-scope`. Excluded on repo-adjacency grounds even though the specific decision (provider_meta warning vs. static-source scope) differs, and separately its `context_bundle/` directory is empty in this checkout — there is no raw source material to build a bundle from without fabricating artifact content, which extraction development must not do. |

## Considered and excluded for lack of raw material (not a topic-overlap
   concern)

| Candidate | Why excluded |
|---|---|
| `data/authority/cache/structured/*.json` (all) | These are already-extracted structured decision records (prior LLM output), not raw source text. Using them as extractor *input* would test the extractor against its own kind of output rather than raw organizational evidence, which does not match the product's real input shape. They were read only to confirm subject matter for the exclusion list above, never as extraction input. |
| `data/authority/cache/rag/*.json` for repos/subjects not listed above (e.g. `pypi-mirror-split`, `packaging-governance`, `metadata-1-1/1-2/redesign`, `python-multiphase-init`, `annotation-semantics`, `elastic-multi-value`, `rust-const-checks`, `rust-str-as-str`, `kubernetes-delayed-preemption`) | Not topically excluded, but not used in this session's dev corpus either — the five bundles above already span three ecosystems (Kubernetes scheduler x3, Rust compiler, Elasticsearch) and three extraction shapes (multi-artifact REVERTS with rollback eligibility, multi-artifact SUPERSEDES, single-artifact REVERTED-only). Kept in reserve as an available, pre-vetted expansion pool for a future extraction-development session if the Phase 8 gate needs more statistical power; recording them here so a future session does not have to re-derive which candidates are safe. |

## Corpus size and its consequence for Phase 8

Five dev tasks, seven decision-bearing artifacts total. This is small.
Percentage thresholds framed for the eventual 63-run/7-task holdout scale
(e.g. literal "90% of N" cutoffs) are not meaningful at this size — a single
wrong call moves the rate by 20 percentage points. Phase 8 below defines a
gate scaled to this corpus (small-N pass/fail counts, not percentages) and
states that choice explicitly before any dev run, per the session contract.
