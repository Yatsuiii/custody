# DecisionTrace Prospective Authority Replication

## Verdict

**BENCHMARK INVALID — FIX BEFORE CONCLUDING.**

Under the frozen answer key, DecisionTrace scored **98/101 (97.0%)** versus **94/101 (93.1%)** for the preregistered strong-RAG comparator: a **+4.0 percentage-point** difference with a paired timeline-bootstrap 90% interval of **+1.0 to +6.9 points**. That raw score already failed the +8-point primary gate.

Post-run bilateral failure inspection then found a material answer-key inconsistency. `python-paramspec-implementation-c2` and `swift-coroutine-accessors-c2` label an open implementation proposal `UNRESOLVED` only because accepted authority exists in a separate policy scope. Equivalent open-only implementation histories are labeled `NO_GOVERNING_DECISION`. This violates the preregistered exact-scope/parallel-independence rule and aligns the two labels with the resolver's fallback. A sensitivity check—not a relabeling or corrected score—shows those two rows create the entire comparative advantage: consistent `NO_GOVERNING_DECISION` semantics yield 96/101 for each arm.

The evidence gate also failed decisively. DecisionTrace evidence correctness was **56/101 (55.4%)** versus **88/101 (87.1%)** for strong RAG. The resolver usually cited only the winning decision record; it did not bind the proposal, newer mention, rollback, or conflicting artifact needed to prove why that record still governed. This is a real evidence-binding limitation, not a generation retry issue.

Therefore:

- strict GO gate under the frozen key: **FAIL**;
- mandatory dataset-quality gate: **FAIL**;
- public authority-superiority claim: **not authorized**;
- product integration plan and judge claim variants: **intentionally omitted**;
- resolver modification after results: **none**.

The frozen answer key and all outputs remain unchanged. No corrected score is claimed and no rerun was performed. `POSTRUN_AUTHORITY_VALIDITY_AUDIT.md` contains the complete defect analysis.

The previous result remains part of the record: the frozen product lost its development benchmark, 47/61 (77.0%) versus RAG at 52/61 (85.2%). The post-hoc 61/61 result motivated this experiment; it was never treated as prospective evidence.

## Experiment identity and frozen inputs

- Research branch: `research/decisiontrace-authority-prospective`
- Exact starting SHA: `8cbf14d7b809722d5c4f0fb89202317fa8681df3`
- Resolver-freeze commit: `91c9a710331b63105e07785b824047746f1bc7f0`
- Dataset-freeze commit: `dc2d4a69eef52145723fbc0882489abc7fb75252`
- Run-protocol commit: `d8fefb85020aff1021268d0d8b78279e1db75536`
- Raw-run commit, before scoring: `46c064b32b598f302a13daf0afd5356318fa7fe9`
- Resolver manifest SHA-256: `f843d943ae2dbc402897ebdb60d4acae0f2a01c24597507533b2df9b1097bf03`
- Core resolver `app/authority.py` SHA-256: `e969de3d8bc07febb2d480ed6465740bd28f928c5acf6caa03df76c5542ade71`
- Generation model in every arm: `gemini-3.7-flash`
- Embedding model: `text-embedding-005`
- Code/current-tree baseline: omitted as preregistered because a current tree cannot establish the same cross-repository organizational authority state.
- LLM judge calls: zero; authority and evidence scoring were mechanical.

The byte guards cover the resolver and its dependencies, dataset/spec/ledger/source cache, and prompts/retrieval/parser/model helper. None changed after its respective freeze.

## Preregistered hypothesis and gate

Hypothesis: on unseen source-grounded histories, explicit scope, lifecycle status, decision role, and typed transition replay will identify current organizational authority more reliably than a capable model reconstructing authority from equivalent raw history.

`STRONG AUTHORITY ADVANTAGE — USE CLAIM` required all of:

1. DecisionTrace accuracy at least 90%;
2. DecisionTrace at least 8 points ahead of the stronger frozen RAG arm;
3. paired timeline-bootstrap 90% interval strictly above zero;
4. DecisionTrace evidence correctness no more than 3 points below RAG;
5. no materially worse false-authority rate; and
6. lower error rate on at least two of five secondary lifecycle categories.

| Gate | Result | Pass? |
|---|---:|:---:|
| DecisionTrace accuracy ≥90% | 97.0% | yes |
| Lead ≥8 points | +4.0 points | **no** |
| Paired 90% CI lower bound >0 | +1.0 to +6.9 | yes |
| Evidence within 3 points of RAG | -31.7 points | **no** |
| False authority not materially worse | 3/101 vs 5/101 | yes |
| At least two secondary wins | 2 categories | yes |
| Ground-truth quality | material NO-vs-UNRESOLVED inconsistency | **no** |

The first six rows are the raw frozen-key gate. It failed effect size and evidence before the later validity override. The two secondary wins were supersession misses and unsupported authority; proposal promotion, revert, and parallel-collapse rates tied at zero. Thresholds and comparator selection did not change after collection or output.

## Dataset

- Timelines: **23**
- Authority checkpoints: **101**
- Public artifact snapshots: **86**, representing **52** decision IDs and **61** distinct source URLs
- Composition: **19 fully real timelines / 85 checkpoints**, **4 hybrid timelines / 16 checkpoints**, **0 fully synthetic**
- Synthetic content: developer query wording/checkpoint timing only
- Pinned source cache: 35 repository files, 31 PR records, 3 issue records, and 3 proposal-review comments
- Pre-output exclusions: 5
- Development-set overlap: zero timeline IDs, decision IDs, or source URLs

### Ecosystem distribution

| Ecosystem | Timelines | Checkpoints |
|---|---:|---:|
| Envoy | 1 | 4 |
| Go | 3 | 12 |
| Kubernetes | 2 | 10 |
| LLVM | 1 | 6 |
| OpenTofu | 1 | 4 |
| Python | 5 | 22 |
| Rust | 6 | 24 |
| Swift | 3 | 15 |
| Terraform | 1 | 4 |

### Scenario distribution

Counts overlap because a timeline/checkpoint may test more than one lifecycle property.

| Scenario | Timelines | Checkpoints |
|---|---:|---:|
| Simple supersession | 8 | 29 |
| Multi-hop supersession | 3 | 10 |
| Revert after implementation | 7 | 18 |
| Proposal while current / before acceptance | 16 | 25 |
| Newer mention without transition | 5 | 9 |
| Parallel scopes | 4 | 6 |
| Conflicting or ambiguous | 3 | 5 |
| Withdrawn decision | 3 | 3 |
| Implementation versus policy | 3 | 13 |
| Revert without automatic restoration | 5 | 3 tagged checkpoints |
| Revert without policy restoration | 3 | 3 |
| Explicit restoration | 4 | 5 |
| Partial supersession | 3 | 4 |
| Proposal accepted | 3 | 5 |

The complete source proof and checkpoint adjudication are in `AUTHORITY_PROSPECTIVE_LEDGER.md`; pre-output exclusions remain in `data/prospective/discovery/exclusions.json`.

## Frozen-key headline metrics (diagnostic, not a valid comparative conclusion)

Embedding RAG and full-context RAG tied on governing accuracy at 94/101. Embedding RAG had higher evidence correctness, 88/101 versus 78/101, so it became the primary comparator under the preregistered conservative rule.

| Metric | DecisionTrace | Embedding RAG (primary) | Full-context RAG |
|---|---:|---:|---:|
| Governing accuracy | **98/101 (97.0%)** | **94/101 (93.1%)** | 94/101 (93.1%) |
| Accuracy Wilson 95% CI | 91.6–99.0% | 86.4–96.6% | 86.4–96.6% |
| Evidence correctness | 56/101 (55.4%) | **88/101 (87.1%)** | 78/101 (77.2%) |
| Evidence Wilson 95% CI | 45.7–64.8% | 79.2–92.3% | 68.1–84.3% |
| Authority + evidence | 53/101 (52.5%) | 83/101 (82.2%) | 73/101 (72.3%) |
| False-authority incidence | 3/101 (3.0%) | 5/101 (5.0%) | 5/101 (5.0%) |
| Stale-decision incidence | 0/101 (0%) | 0/101 (0%) | 0/101 (0%) |
| Parse/API failures | 0/101 | 0/101 | 0/101 |
| Repeated-state consistency | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) |

The paired cluster bootstrap used 100,000 resamples of 23 timelines, seed `20260822`, and checkpoint-weighted accuracy within each resample. Under the defective frozen key, observed DecisionTrace minus primary RAG was +3.96 points; 90% CI +1.04 to +6.86. This interval is preserved for audit but cannot support inference after the material validity failure.

### Lifecycle error rates

| Error | DecisionTrace | Primary RAG |
|---|---:|---:|
| Proposal promoted | 0/27 (0%) | 0/27 (0%) |
| Revert miss | 0/10 (0%) | 0/10 (0%) |
| Supersession miss | **0/24 (0%)** | 2/24 (8.3%) |
| Parallel collapse | 0/9 (0%) | 0/9 (0%) |
| Unsupported authority, eligible | **3/18 (16.7%)** | 5/18 (27.8%) |
| Unsupported authority, all rows | 3/101 (3.0%) | 5/101 (5.0%) |

Wilson 95% intervals are retained with every numerator/denominator in `data/prospective/scores.json`. Notable intervals: proposal promotion was 0–12.5% for both arms; supersession miss was DT 0–13.8% and RAG 2.3–25.8%; false authority was DT 1.0–8.4% and RAG 2.1–11.1%.

### Unresolved calibration

| Metric | DecisionTrace | Primary RAG |
|---|---:|---:|
| Exact unresolved accuracy / abstention recall | **4/7 (57.1%)** | 0/7 (0%) |
| Wilson 95% CI | 25.0–84.2% | 0–35.4% |
| Abstention precision | 4/4 (100%) | N/A: never predicted unresolved |

DecisionTrace's only three frozen-key authority misses and RAG's largest common failure were the same partial-acceptance Go history. The two RAG `NO_GOVERNING_DECISION` answers shown as misses here are the invalidated rows: the source histories do not make them genuinely unresolved merely because policy authority exists in another scope.

### Material validity sensitivity

This is not an alternate score and did not modify the answer key.

| Treatment of the two disputed open-implementation rows | DecisionTrace | Primary RAG | Difference |
|---|---:|---:|---:|
| Frozen key: UNRESOLVED | 98/101 | 94/101 | +4 |
| Internally consistent sensitivity: NO_GOVERNING_DECISION | 96/101 | 96/101 | 0 |

Because the sensitivity erases the full apparent advantage, the benchmark is invalid rather than a modest win.

## Per-scenario governing accuracy

| Scenario | DecisionTrace | Primary RAG | Full-context RAG |
|---|---:|---:|---:|
| Conflicting/ambiguous | **2/5 (40%)** | 0/5 (0%) | 0/5 (0%) |
| Explicit restoration | 5/5 | 5/5 | 5/5 |
| Implementation versus policy | **13/13** | 11/13 | 11/13 |
| Mention without transition | 9/9 | 9/9 | 9/9 |
| Multi-hop supersession | 10/10 | 10/10 | 10/10 |
| Parallel scopes | 6/6 | 6/6 | 6/6 |
| Partial supersession | **4/4** | 2/4 | 2/4 |
| Proposal accepted | 5/5 | 5/5 | 5/5 |
| Proposal while current | **25/25** | 23/25 | 23/25 |
| Revert after implementation | 18/18 | 18/18 | 18/18 |
| Revert without automatic restoration | 3/3 | 3/3 | 3/3 |
| Revert without policy restoration | 3/3 | 3/3 | 3/3 |
| Simple supersession | 29/29 | 29/29 | 29/29 |
| Withdrawn decision | 3/3 | 3/3 | 3/3 |

The advantage did not come from revert handling: both systems were perfect on the evaluated revert checkpoints. It came from two unresolved partial-supersession checkpoints and two unresolved implementation-proposal checkpoints. Conversely, all three DecisionTrace authority misses came from one Go partial-acceptance family. This concentration is a reason not to extrapolate the +4-point aggregate difference into a broad superiority claim.

## Per-ecosystem and composition results

| Ecosystem | DecisionTrace | Primary RAG |
|---|---:|---:|
| Envoy | 4/4 | 4/4 |
| Go | 9/12 (75.0%) | 9/12 (75.0%) |
| Kubernetes | 10/10 | 10/10 |
| LLVM | 6/6 | 6/6 |
| OpenTofu | 4/4 | 4/4 |
| Python | **22/22** | 21/22 (95.5%) |
| Rust | **24/24** | 22/24 (91.7%) |
| Swift | **15/15** | 14/15 (93.3%) |
| Terraform | 4/4 | 4/4 |

Composition split: DecisionTrace was 82/85 (96.5%) on fully-real checkpoints and 16/16 on hybrid checkpoints; primary RAG was 78/85 (91.8%) fully real and 16/16 hybrid. The four-point aggregate win came entirely from fully-real histories.

## Complete authority misses

### DecisionTrace — 3

| Checkpoint | Ground truth | Prediction | Forensic category |
|---|---|---|---|
| `go-range-functions-c2` | UNRESOLVED | GOVERNING `golang/go#61405` | lifecycle representation |
| `go-range-functions-c3` | UNRESOLVED | GOVERNING `golang/go#61405` | lifecycle representation |
| `go-range-functions-c4` | UNRESOLVED | GOVERNING `golang/go#61405` | lifecycle representation |

The proposal-review comment accepted range-over-int, left range-over-func details for follow-up proposals, and kept implementation experimental. The artifact-level `ACCEPTED` status could not represent partial acceptance within the normalized broad scope, so the frozen resolver promoted the whole record. This is not a regex or priority-rule miss; it is a granularity limit in lifecycle representation.

### Primary RAG — 7 under the frozen key

| Checkpoint | Ground truth | Prediction | Forensic category |
|---|---|---|---|
| `rust-inline-const-c4` | UNRESOLVED | GOVERNING `RFC-2920` | supersession missed |
| `rust-drop-check-c4` | UNRESOLVED | GOVERNING `RFC-1238` | supersession missed |
| `go-range-functions-c2` | UNRESOLVED | GOVERNING `golang/go#61405` | recency/acceptance confusion |
| `go-range-functions-c3` | UNRESOLVED | GOVERNING `golang/go#61405` | recency/acceptance confusion |
| `go-range-functions-c4` | UNRESOLVED | GOVERNING `golang/go#61405` | recency/acceptance confusion |
| `python-paramspec-implementation-c2` | UNRESOLVED | NO_GOVERNING_DECISION | generation reasoning |
| `swift-coroutine-accessors-c2` | UNRESOLVED | NO_GOVERNING_DECISION | generation reasoning |

Embedding and full-context RAG made the same seven frozen-key authority mistakes, so none is attributable to retrieval. The embedding arm had zero forensic retrieval misses. Two rows are now identified as ground-truth defects rather than valid RAG errors; the raw failure file remains unchanged for lineage.

## Complete bilateral failure taxonomy

“Miss” here means authority or evidence, so a correct authority answer with insufficient citations remains a miss under the preregistered combined rubric. Every row is preserved in `data/prospective/failures.jsonl`.

| Condition | Forensic class | Rows |
|---|---|---:|
| DecisionTrace | lifecycle representation | 3 |
| DecisionTrace | evidence binding | 45 |
| Embedding RAG | supersession missed | 2 |
| Embedding RAG | recency confusion | 3 |
| Embedding RAG | generation reasoning failure | 2 |
| Embedding RAG | evidence mistake, authority otherwise correct | 11 |
| Full-context RAG | supersession missed | 2 |
| Full-context RAG | recency confusion | 3 |
| Full-context RAG | generation reasoning failure | 2 |
| Full-context RAG | evidence mistake, authority otherwise correct | 21 |

DecisionTrace's evidence-binding failures cluster around proposal-not-authoritative checkpoints (25), newer mentions (9), and revert/implementation context. The deterministic resolver emits the winning decision ID as evidence, but often omits the negative or transition artifact required by the frozen sufficient-evidence set. This is why high authority accuracy did not translate into an auditable answer advantage.

No miss was classified as DecisionTrace extraction, scope resolution, role resolution, generation/explanation, or genuinely ambiguous adjudication. No RAG miss was classified as retrieval failure, stale-artifact preference, revert failure, or parallel collapse.

## Leakage, fairness, and run integrity

- Complete pre-inference suite: **545 passed, 2 conditional skips**.
- Product suite: **59/59 passed**, including real Vertex collaboration/ingestion/retrieval and real Firestore persistence.
- All v0/v2/authority/prospective leakage tests passed.
- Post-run prompt/history/hash checks: **21/21 passed**.
- Frozen resolver, dataset, and run-protocol guards passed before and after inference.
- All 303 result rows match the committed prompt hash and public source-universe IDs.
- Both RAG arms saw the same public artifact universe and fields as DecisionTrace; full-context RAG saw every visible artifact in order.
- Expected answers, sufficient-evidence sets, and failure labels were absent from model prompts.
- Prospective run output did not exist during discovery or adjudication.
- No old authority timeline, decision ID, or artifact URL was reused.
- Generation errors: 0/303; parse errors: 0/202 RAG answers.
- Selective retries, semantic regeneration, judge retries, post-output case changes, and resolver edits: zero.

The two conditional skips occurred only before prepared/run directories existed; after outputs existed, the complete prospective integrity suite passed without skips.

## API and cost-relevant work

- Prospective Gemini generations: **303** (101 DecisionTrace explanations, 101 embedding-RAG answers, 101 full-context-RAG answers).
- Prospective embedding endpoint requests: **56**, containing **227 text items**.
- LLM judge calls: **0**.
- Primary-source metadata acquisition: **37 GitHub CLI/API record requests** plus 5 shallow primary-repository clone operations.
- Dataset source cache: 35 files, 31 PRs, 3 issues, 3 comments.
- The mandatory product preflight suite also exercised real Vertex and Firestore paths. Its legacy helpers do not expose a request counter, so those integration requests are disclosed but not silently folded into the exact prospective benchmark tally.

## Exact changed files

The exact branch-relative inventory contains **443 paths** in `CHANGED_FILES_AUTHORITY_PROSPECTIVE.txt`. It lists every hand-authored research file, frozen input, prepared prompt, raw response, score row, and manifest; broad untracked user files outside this experiment are excluded. The principal hand-authored additions are:

- `PROSPECTIVE_RESOLVER_FREEZE.md`
- `AUTHORITY_PROSPECTIVE_SPEC.md`
- `AUTHORITY_PROSPECTIVE_LEDGER.md`
- `RESULTS_AUTHORITY_PROSPECTIVE.md`
- `AUTHORITY_PROSPECTIVE_OUTCOME_LEDGER.md`
- `POSTRUN_AUTHORITY_VALIDITY_AUDIT.md`
- `collect_prospective_sources.py`
- `build_authority_prospective_cases.py`
- `authority_prospective.py`
- `prepare_authority_prospective.py`
- `run_authority_prospective.py`
- `grade_authority_prospective.py`
- the five prospective freeze/leakage/grader test modules
- `data/prospective/` and `data/runs_authority_prospective/`

No existing v0/v2/authority benchmark file, frozen product file, deployment file, or live data was modified.

## APOSD review

The research harness keeps three deep boundaries: `authority_prospective.py` owns public rendering, frozen resolution orchestration, retrieval, and parsing; thin prepare/run scripts own one-shot persistence; the grader alone owns the hidden-key join. Answer-key knowledge does not leak upward into runners. The raw-run commit passed the repository APOSD hook. Earlier research commits reported that the external hook reviewer errored and the hook failed open; because GO failed, no external product-integration APOSD review was commissioned or claimed.

The largest design red flag is not code shape but domain granularity: artifact-level status cannot express that an accepted review comment authorizes one subclaim while deferring another. That limitation is explicitly recorded rather than patched after the run.

## DDIA review

### System boundary and correctness model

- **Decision:** treat pinned source artifacts as the shared evidence log, public structured envelopes as a deterministic projection, and the resolver as a pure replay/read model.
- **Invariant:** authority may change only through a visible eligible lifecycle transition in exact scope; absence of exact-scope authority produces abstention rather than semantic guessing.
- **Evidence:** resolver/dataset/protocol SHA guards, 101 checkpoint replays, and raw run rows committed before grading.

### Main data risks

| Risk | Failure mode | Observed evidence | Recommendation |
|---|---|---|---|
| Coarse lifecycle record | Partial acceptance promotes a whole artifact | 3 Go false-authority rows | Do not ship a broad claim; future research needs claim-level lifecycle representation, prospectively frozen before another dataset. |
| Evidence/read-model divergence | Resolver state is correct but proof omits transition/distractor context | 45 DT evidence-binding misses | Treat authority and sufficient proof as separate correctness outputs; do not infer proof completeness from a winning ID. |
| Repeated checkpoint dependence | 101 rows overstate 23 independent histories | Paired timeline CI used | Continue reporting clustered inference and timeline counts beside checkpoint counts. |
| End-to-end extraction unmeasured | Public scope/status/role fields are source-grounded but normalized | Manual ledger and proof cache | Any product integration would need a separate extraction benchmark and ambiguity-preserving ingestion contract. |

### Shippability

The research artifact preserves its exact lineage, but its ground truth is not sufficiently consistent for a comparative conclusion. The resolver is **not approved for product integration in this session**. No storage schema, Firestore data, deployed read model, or frozen product code was changed.

## Threats to validity

1. **Fatal:** two `UNRESOLVED` labels depend on accepted authority in a separate scope and align with resolver fallback behavior. Their consistent-label sensitivity erases the comparative advantage.
2. The independent unit count is 23 timelines, not 101 checkpoints; clustering is handled statistically but the population is still modest.
3. One researcher performed both adjudication and the required second source-only pass. Every proof is inspectable, but there was no independent annotator; this likely allowed the fatal inconsistency through.
4. Four PEP timelines are hybrid. Their lifecycle facts are real and pinned; checkpoint wording/timing is normalized.
5. Public status, role, scope, and relation fields are source-grounded and equally visible to all arms, but this evaluates resolution over structured ingestion, not arbitrary end-to-end extraction quality.
6. The evidence rubric intentionally requires enough context to prove why a tempting proposal/mention/revert does not govern. This is stricter than merely citing the winner and materially exposes DecisionTrace's winner-only evidence output.
7. The Go range-function family produced all three DecisionTrace authority misses and three of seven frozen-key RAG misses. Claim-level partial acceptance is a specific unresolved architecture boundary.
8. Recent 2026 PR histories increase temporal realism but may not represent older governance systems.

## Outcome and recommendation

This experiment cannot validly determine whether the resolver generalized or overfit. The frozen-key 97.0% shows it handled many unseen histories, but the two material labels create the entire comparative advantage; the consistent-label sensitivity ties RAG. Evidence binding was also substantially worse. The requested centerpiece claim is not earned.

Recommendation: keep the frozen product and public submission claims unchanged. Do not relabel these rows, optimize this benchmark, reuse its outputs as corrected evidence, or port the resolver into the product. If authority research continues, start a fresh preregistered run with an implementation-independent `NO_GOVERNING_DECISION`/`UNRESOLVED` invariant, independent adjudication, claim-level lifecycle representation, and evidence sufficiency as a first-class output.

## Why this remains a distinct system question

Custody concerns persistent-state safety and selective recovery. DecisionTrace concerns which organizational decision currently governs across proposals, acceptances, replacements, rollbacks, and reconsideration. This benchmark never models downstream derivation traversal or recovery actions; it scores organizational authority and supporting evidence.

## Judge-safe research sentence

The prospective authority run was invalidated by two material ground-truth inconsistencies, so it does not support a comparative product claim.
