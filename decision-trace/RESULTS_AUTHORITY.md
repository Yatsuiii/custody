# DecisionTrace Authority-Resolution Benchmark Results

## Verdict

**RAG WINS — DO NOT CLAIM AUTHORITY ADVANTAGE.**

The untouched DecisionTrace baseline scored **77.0% (47/61)** governing-
decision accuracy; strong raw-history RAG scored **85.2% (52/61)**. The
DecisionTrace-minus-RAG difference was **-8.2 percentage points**, with a
paired timeline-clustered 90% bootstrap interval of **-25.0 to +8.5 points**.
The preregistered authority-advantage criterion was not met.

One preregistered post-baseline intervention moved authority selection into a
scope/status/role-aware deterministic resolver. It scored **100% (61/61)** on
the same benchmark, versus the frozen RAG responses at 85.2%; paired difference
**+14.8 points**, 90% interval **+6.5 to +24.1**. This is a post-hoc result on
the benchmark used for failure forensics. It is promising engineering evidence,
not a valid replacement for the negative untouched baseline and not sufficient
for a public superiority claim without prospective external replication.

## Experiment identity

- Research branch: `research/decisiontrace-authority-benchmark`
- Exact start: `ca53fce3ef8f6212e417238f976f2623d8a5fb9e`
- Frozen pre-result spec commit: `959cd236a0c06207e7c37d300f4ce05331dd1a7d`
- Frozen dataset/prompt commit: `861fe29`
- Frozen untouched baseline/intervention-plan commit: `0db0305`
- Frozen intervention implementation commit: `dc86cbd`
- Generation model in both baseline arms: `gemini-3.7-flash`
- Embedder: `text-embedding-005`
- Code-only baseline: omitted before source selection because the proposal/PR
  ecosystems have no equivalent pinned current-code snapshot that can answer
  the same organizational-authority question.

## Hypothesis and success criterion

Hypothesis: explicit lifecycle state will resolve the currently governing
engineering decision more reliably than a capable model reconstructing
authority from retrieved raw history.

The baseline could support an authority-advantage claim only if all held:

1. DecisionTrace exceeded RAG by at least 10 percentage points;
2. the paired timeline-bootstrap 90% lower bound exceeded zero;
3. DecisionTrace made at least 25% fewer combined stale/false-authority
   errors, with at least four absolute rescues;
4. DecisionTrace evidence correctness was no more than five points below RAG;
5. every dataset, source, equivalence, leakage, and protected-file gate passed.

The baseline failed criteria 1–3. No threshold changed after outputs.

## Dataset

- Timelines: **15**
- Checkpoints: **61** (29 intermediate, 32 final)
- Source artifacts: **39 pinned real artifacts**
- Composition: **7 fully-real timelines / 28 checkpoints**; **8 hybrid
  timelines / 33 checkpoints**
- Fully synthetic timelines: **0**
- Synthetic elements in every timeline: developer question and checkpoint
  timing
- Source substrates: `python/peps`, `python/cpython`, `rust-lang/rust`,
  `kubernetes/kubernetes`, `elastic/elasticsearch`
- Adapter coverage: **100% (21/21)** eligible explicit lifecycle events
- Exclusions after source audit: PEPs 354, 431, and 433; pinned headers showed
  Rejected, Withdrawn, and Draft, so they could not be formerly governing.

### Scenario distribution

Counts overlap because one checkpoint may exercise more than one scenario.

| Scenario | Timelines | Checkpoints |
|---|---:|---:|
| Simple supersession | 6 | 11 |
| Multi-hop supersession | 2 | 5 |
| Revert after supersession/change | 4 | 15 |
| Proposal after a current decision | 4 | 9 |
| Mention without supersession | 3 | 5 |
| Parallel decisions | 3 | 12 |
| Conflicting/insufficient authority evidence | 3 | 5 |
| Implementation revert with surviving policy | 2 | 8 |

Lifecycle artifacts included 18 explicit replacement edges, 6 revert edges,
2 implementation edges, and 6 proposal artifacts.

## Headline metrics

| Metric | DecisionTrace baseline | Strong RAG | Post-intervention |
|---|---:|---:|---:|
| Governing accuracy | **47/61 (77.0%)** | **52/61 (85.2%)** | **61/61 (100%)** |
| Wilson 95% CI | 65.1–85.8% | 74.3–92.0% | 94.1–100% |
| Evidence correctness | 53/61 (86.9%) | 54/61 (88.5%) | 61/61 (100%) |
| Evidence Wilson 95% CI | 76.2–93.2% | 78.2–94.3% | 94.1–100% |
| Authority + evidence | 46/61 (75.4%) | 48/61 (78.7%) | 61/61 (100%) |
| Stale-decision incidence | 0/61 (0%) | 0/61 (0%) | 0/61 (0%) |
| False-authority incidence | 3/61 (4.9%) | 0/61 (0%) | 0/61 (0%) |
| Proposal promoted | 0/5 applicable (0%) | 0/5 (0%) | 0/5 (0%) |
| Revert miss | 2/14 applicable (14.3%) | 6/14 (42.9%) | 0/14 (0%) |
| Supersession miss | 4/13 applicable (30.8%) | 0/13 (0%) | 0/13 (0%) |
| Repeated-history consistency | 10/10 (100%) | 7/10 (70%) | 10/10 (100%) |
| API/parse failures | 0/61 | 0/61 | 0/61 |

For zero-incidence 61-row rates, the Wilson 95% interval is 0–5.9%.
Proposal promotion's 0/5 interval is 0–43.4%. Revert-miss intervals are
DecisionTrace 4.0–39.9% and RAG 21.4–67.4%; supersession-miss intervals are
DecisionTrace 12.7–57.6% and RAG 0–22.8%.

The paired cluster bootstrap resampled 15 timelines 10,000 times with seed
`20260822`. Baseline accuracy difference was -8.1 points, 90% CI -25.0 to
+8.5. Post-intervention difference was +14.8 points, 90% CI +6.5 to +24.1.

## Per-scenario governing accuracy

| Scenario | DecisionTrace | RAG |
|---|---:|---:|
| conflicting evidence | 3/5 (60.0%) | 2/5 (40.0%) |
| implementation revert / policy survives | 3/8 (37.5%) | 8/8 (100%) |
| mention without supersession | 1/5 (20.0%) | 5/5 (100%) |
| multi-hop supersession | 3/5 (60.0%) | 5/5 (100%) |
| parallel decisions | 10/12 (83.3%) | 9/12 (75.0%) |
| proposal after current | 8/9 (88.9%) | 9/9 (100%) |
| revert after supersession/change | 15/15 (100%) | 9/15 (60.0%) |
| simple supersession | 8/11 (72.7%) | 11/11 (100%) |

DecisionTrace's baseline advantage was narrow: explicit revert lineages. RAG's
advantage was broader: proposals, accepted supersessions, multi-hop histories,
new mentions, and especially distinguishing accepted policy from its reverted
implementation.

## Per-source governing accuracy

| Source substrate | DecisionTrace | RAG |
|---|---:|---:|
| `elastic/elasticsearch` | 4/4 (100%) | 2/4 (50%) |
| `kubernetes/kubernetes` | 4/4 (100%) | 2/4 (50%) |
| `python/peps` | 28/37 (75.7%) | 34/37 (91.9%) |
| `python/peps` + `python/cpython` | 3/8 (37.5%) | 8/8 (100%) |
| `rust-lang/rust` | 8/8 (100%) | 6/8 (75%) |

Composition split: DecisionTrace 23/28 (82.1%) fully real and 24/33 (72.7%)
hybrid; RAG 22/28 (78.6%) fully real and 30/33 (90.9%) hybrid.

## Complete baseline failures

### DecisionTrace

| Checkpoint | Expected | Predicted | Primary failure | Mechanism |
|---|---|---|---|---|
| `metadata-redesign-c3` | GOVERNING `PEP-345` | GOVERNING `PEP-426` | UNSUPPORTED_AUTHORITY | generation |
| `metadata-redesign-c4` | GOVERNING `PEP-566` | UNRESOLVED | MISSING_CORRECT_DECISION | generation |
| `metadata-redesign-c5` | GOVERNING `PEP-566` | UNRESOLVED | MISSING_CORRECT_DECISION | generation |
| `manylinux-policy-c4` | GOVERNING `PEP-600` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | deterministic resolver |
| `manylinux-policy-c5` | GOVERNING `PEP-600` | UNRESOLVED | MISSING_CORRECT_DECISION | deterministic resolver |
| `metadata-1-1-c1` | GOVERNING `PEP-241` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION | generation |
| `single-file-metadata-c3` | NO_GOVERNING_DECISION | GOVERNING `PEP-722` | UNSUPPORTED_AUTHORITY | generation |
| `annotation-semantics-c5` | UNRESOLVED | UNRESOLVED | EVIDENCE_ERROR | lifecycle representation |
| `pypi-mirror-split-c1` | NO_GOVERNING_DECISION | GOVERNING `PEP-381` | UNSUPPORTED_AUTHORITY | generation |
| `pypi-mirror-split-c3` | GOVERNING `PEP-464` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | deterministic resolver |
| `python-encoding-warning-c2` | GOVERNING `PEP-597` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | generation |
| `python-encoding-warning-c3` | GOVERNING `PEP-597` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | generation |
| `python-encoding-warning-c4` | GOVERNING `PEP-597` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | generation |
| `python-multiphase-init-c3` | GOVERNING `PEP-489` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | generation |
| `python-multiphase-init-c4` | GOVERNING `PEP-489` | UNRESOLVED | PARALLEL_DECISION_COLLAPSE | generation |

Mechanistic totals for authority misses: generation/presentation 11,
deterministic resolver 3. The evidence-only miss is lifecycle
representation/evidence binding 1. No miss was assigned to ingestion,
retrieval, ambiguous ground truth, or other.

### Strong RAG

| Checkpoint | Expected | Predicted | Primary failure |
|---|---|---|---|
| `single-file-metadata-c1` | NO_GOVERNING_DECISION | NO_GOVERNING_DECISION | EVIDENCE_ERROR |
| `single-file-metadata-c2` | NO_GOVERNING_DECISION | NO_GOVERNING_DECISION | EVIDENCE_ERROR |
| `single-file-metadata-c3` | NO_GOVERNING_DECISION | NO_GOVERNING_DECISION | EVIDENCE_ERROR |
| `annotation-semantics-c5` | UNRESOLVED | NO_GOVERNING_DECISION | PARALLEL_DECISION_COLLAPSE |
| `pypi-mirror-split-c1` | NO_GOVERNING_DECISION | NO_GOVERNING_DECISION | EVIDENCE_ERROR |
| `pypi-mirror-split-c4` | UNRESOLVED | NO_GOVERNING_DECISION | PARALLEL_DECISION_COLLAPSE |
| `pypi-mirror-split-c5` | UNRESOLVED | NO_GOVERNING_DECISION | PARALLEL_DECISION_COLLAPSE |
| `rust-const-checks-c2` | GOVERNING `rust-lang/rust#154930` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION |
| `rust-const-checks-c3` | GOVERNING `rust-lang/rust#154930` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION |
| `kubernetes-delayed-preemption-c2` | GOVERNING `kubernetes/kubernetes#137662` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION |
| `kubernetes-delayed-preemption-c3` | GOVERNING `kubernetes/kubernetes#137662` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION |
| `elastic-multi-value-c2` | GOVERNING `elastic/elasticsearch#147360` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION |
| `elastic-multi-value-c3` | GOVERNING `elastic/elasticsearch#147360` | NO_GOVERNING_DECISION | MISSING_CORRECT_DECISION |

Primary failure-class counts not shown above are zero: STALE_DECISION,
PROPOSAL_PROMOTED, REVERT_MISSED, SUPERSESSION_MISSED, and RECENCY_CONFUSION.
The separately reported revert/supersession miss rates count every incorrect
applicable checkpoint, as preregistered, even when the primary failure is an
abstention. `GRADER_CORRECTION.md` records this reporting correction.

## Single intervention

The frozen hypothesis, expected rescues, and kill rule are in
`AUTHORITY_INTERVENTION.md`. One deep module added
`resolve_authority(decisions, authority_scope)` with four internal semantics:

- gate proposals and terminal non-authoritative records;
- resolve only an explicit authority scope and abstain on unsafe broad scope;
- treat an implementation/revert lineage as evidence rather than policy
  authority when it explicitly implements an accepted policy;
- make the governing state/ID deterministic output that generation cannot
  choose or omit.

It rescued all 14 preregistered authority misses and the one evidence miss,
introduced zero regressions, improved accuracy by 23.0 points, and passed the
leakage/protected/process tests. It therefore survived its engineering kill
criterion. Because the same benchmark informed the intervention, its 61/61
score needs a new prospectively frozen external dataset before supporting a
claim.

## Leakage, reproducibility, and cost

- Authority leakage/equivalence/protected checks: **11/11 passed**.
- New resolver and process-boundary checks: **7/7 passed**.
- Combined focused verification: **18/18 passed**.
- Preserved v2 leakage/regression suite: **341/341 passed**.
- Local product graph/store/UI/quote checks: **24/24 passed**. Networked live
  ingestion, real-Gemini collaboration/retrieval, and Firestore integration
  tests are excluded from this local count and remain part of the shipping gap.
- Secondary fresh-process continuation: 2/2 timelines matched uninterrupted
  resolution (`packaging-governance`, `rust-str-as-str`).
- Old v0/v2 protected paths: byte-identical to `ca53fce` by SHA-256 manifest.
- Baseline generation: **122 Gemini calls**.
- Intervention generation: **61 Gemini calls**.
- Total benchmark generation: **183 Gemini calls**.
- Retrieval preparation: **244 embedding API call units**.
- LLM judge calls: **0**; grading was deterministic.
- Source acquisition calls are read-only GitHub/PEP metadata requests and are
  not model-cost calls.
- No selectively regenerated answer, judge retry, deployment, push, or merge.

The existing product integration suite includes real Vertex and Firestore
calls. It was not rerun to completion as part of this result; focused local
product/resolver tests and the benchmark's actual Vertex paths were exercised.
The global APOSD hook also could not run its external reviewer because the
review service reported a session limit. The hook failed open as configured.
Accordingly, the research artifact is complete, but the intervention is
**not shippable product code** until that review gate and the full integration
suite run successfully.

## Threats to validity

1. Only 15 timelines are independent; 61 checkpoints are repeated measures.
   The paired timeline bootstrap is more informative than treating 61 rows as
   independent.
2. Eight timelines are hybrid. Their source artifacts and lifecycle text are
   real, but checkpoint sequencing/questions are normalized for evaluation.
3. The structured arm is resolver-conditioned, not an end-to-end deployed
   ingestion score. The frozen product does not extract general acceptance or
   supersession events from arbitrary prose.
4. Explicit normalized authority scopes are derivable public inputs supplied
   equally to RAG and DecisionTrace, but robust scope extraction remains an
   unmeasured product problem.
5. PEP cases dominate the dataset. PR reverts are fewer and make RAG look
   weaker; Python policy/implementation cases make DecisionTrace look weaker.
6. Evidence grading for non-governing answers is strict because the frozen
   answer key contains no expected evidence IDs for those rows. RAG sometimes
   cited relevant evidence while correctly abstaining and was counted evidence-
   incorrect. Governing accuracy is unaffected.
7. The post-intervention 100% result is explicitly post-hoc and likely reflects
   close alignment between the new deterministic invariant and this benchmark's
   adjudication. External prospective replication is mandatory.

## Exact changed-file set

Hand-authored research/code files:

- `AUTHORITY_BENCHMARK_AUDIT.md`
- `AUTHORITY_BENCHMARK_SPEC.md`
- `AUTHORITY_INTERVENTION.md`
- `GRADER_CORRECTION.md`
- `RESULTS_AUTHORITY.md`
- `AUTHORITY_OUTCOME_LEDGER.md`
- `authority_benchmark.py`
- `build_authority_cases.py`
- `run_authority_conditions.py`
- `run_authority_intervention.py`
- `grade_authority.py`
- `process_boundary_authority.py`
- `test_no_leakage_authority.py`
- `test_authority_process_boundary.py`
- `app/authority.py`
- `app/tests/test_authority.py`

Generated research artifacts:

- `data/authority/.gitignore`, `SPOT_CHECKS.md`, `timelines.json`,
  `checkpoints.jsonl`, `ground_truth.jsonl`, `dataset_stats.json`,
  `protected_sha256.json`, `prepare_manifest.json`, `run_manifest.json`,
  `intervention_run_manifest.json`, and `baseline_scores.json`;
- exactly one `data/authority/prepared/<checkpoint_id>.json` for each of the
  61 IDs in `checkpoints.jsonl`;
- exactly one `data/runs_authority/{decisiontrace,rag,decisiontrace_intervention}/<checkpoint_id>.json`
  per checkpoint (183 run rows total).

No pre-existing v0/v2 file changed. `expand_falsifier_sample.py` and the
parent-worktree untracked paths shown by `git status` predated this session and
were not staged or modified.

## Differentiation check

This benchmark tests organizational authority: accepted decisions, proposals,
supersessions, explicit rollbacks, policy/implementation separation, parallel
scopes, and safe uncertainty. It does not perform source-to-derived-state
lineage traversal or downstream state invalidation.

## Recommendation and next action

**RAG WINS — DO NOT CLAIM AUTHORITY ADVANTAGE.**

The highest-leverage next action is a prospectively preregistered external
replication containing unseen repositories and independently adjudicated scope
labels. Freeze it before running the new resolver. Do not tune this 61-row
benchmark again.

Judge-safe sentence:

> On 61 temporal authority checkpoints, the frozen DecisionTrace baseline scored 77% versus strong RAG at 85%; one post-hoc deterministic authority resolver reached 100%, so the original system showed no authority advantage and the redesign requires prospective replication.
