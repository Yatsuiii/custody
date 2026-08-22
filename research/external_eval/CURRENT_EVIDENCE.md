# Current Evidence Freeze

Status: evidence consolidation only. No external comparative benchmark run is
authorized by this document. The internal falsification sequence ends at
E2H-R1E; a future run must use an externally authored attack or benchmark.

Date of freeze: 2026-08-22. Repository lineage is preserved through
`research/e2h-r1e-durable-authority-integration` at
`56c41981ef4f8625061aad65e3bf4beaf1bbe1d2`.

## What current Custody claims

The shipped system separates structural origin from remembered content,
admits trusted records through `take_custody`, stores derivation links, and
requires an instruction-eligible citation at the `ExportGateway`. Missing
event attribution is fail-closed. Tool revisions and source identity are
available to the current catalog, and the shipped revocation path walks the
stored graph for a tool/revision. These are implementation/design guarantees,
not a claim that every memory-poisoning threat is solved.

The pre-research system did not have interval-scoped authority, a current
generation action check, or a durable authority-dependency vector. Its trust
boundary also accepts configured tool identity as an authority input. Exact-
content retrieval matching remains a binary boundary: a byte-identical
citation can resolve while a changed or paraphrased citation misses.

## Evidence ledger

| Evidence | Environment and variable | Result | Establishes | Does not establish |
|---|---|---|---|---|
| E0 | Real frozen Custody `take_custody` + `CustodyGraph`; two trusted parents | **FOUNDATION BUG**: one synthesis parent was silently overwritten; revoking the other root missed the synthesis | The original graph population path was unsound for multi-parent input | That the graph representation itself was inadequate, or that all poisoning attacks succeed |
| E1 | Real Custody after the minimal lineage accumulation fix | **FOUNDATION-SURVIVES**: 10/10 prescribed multi-parent cases and 381/381 tests passed | Structural parent accumulation and graph traversal work for the tested cases | Weighted contribution, paraphrase laundering, or interval revocation |
| E2A | Published TMA-NM `tool_echo` construction, translated to unchanged Custody; no model call | **EXTERNAL-FAIL**: trusted-tool echo received trusted standing and an allowed export | An externally authored laundering construction reproduces the trusted-tool identity failure | Comparative performance, Architecture A efficacy, or general memory-poisoning ASR |
| E2B | Published TMA-NM summarize construction, real invocation boundary | **EXTERNAL-PASS-ACCIDENTAL**: attack and benign paraphrase were both denied through different default-deny/hash paths | Current Custody does not provide a useful benign transformed-memory path | A defense against laundering; the attack was not separated from collateral denial |
| E2C | Deterministic exact-vs-transformed retrieval probe | **EXACT-MATCH-DEPENDENCY-CONFIRMED**: only byte-identical retrieval retained ancestry | The current cross-session dependency is exact-hash based | Semantic ancestry, external benchmark efficacy, or post-hoc repair |
| E2D | Logical SQLite harness; real frozen Custody baseline vs Architecture A | **PASS**: Architecture A scored 0/6 false ACT, 4/4 affected recall, 13/13 parent recall; baseline scored 2/6 false ACT and 1/4 affected recall | The proposed envelope/dependency algebra is coherent in a deterministic model | Real persistence, external attacks, production readiness, or truth of content |
| E2E | Logical Architecture A harness; only role RELAY→ORIGIN changed | **POLICY-FAIL-CONTAINED**: direct ACT and 3/3 propagation occurred, but scope/revision containment and 5/5 revocation recall held | Operation role is a bounded trusted-policy assumption with recoverable blast radius | Detection of misconfiguration, policy selection quality, or production integration |
| E2F | Logical SQLite process-free model; S3 action-current semantics | **TOCTOU-ROBUST**: stale ACT permits 0/5, ABA false accepts 0/1, retry conflict 1/1 | Policy generation freshness works for a record directly cited by the gateway | Freshness through a durable external memory stack |
| E2G | Logical G3 support-root freshness model | **GENERATION-COMPOSITION-ROBUST**: stale dependencies remained denied through fresh children, cross-agent depth-3, mixed parents, and ABA; all recall gates passed | Fresh envelopes do not refresh stale authority when dependencies are retained | Firestore/process atomicity, real caches, model behavior, or external benchmark outcomes |
| E2H | First real Firestore preflight | **INTEGRATION-BLOCKED** because the preregistered namespace had one pre-existing policy document; no scored variant ran | The safety gate prevented an unsafe write into a non-empty namespace | Any persistence security result |
| E2H-R1D | Real Firestore and process death; writer killed during a real pessimistic transaction | **INVALID_RUNNER_EXCEPTION / blocked**: state before failure showed no `C_CRASH` commit; recovery handling was incomplete | The runner encountered genuine server-side contention after process death | Firestore transaction failure, partial authoritative admission, or Architecture A failure |
| E2H-R1E | Real Firestore Native, independent W/P/G processes, two clean runs | **INTEGRATION-FAIL-CONTAINED**: all authority-safety gates passed; only 90-second recovery liveness failed (0/1). Three contention events were observed and every gateway check denied | Durable reconstruction, policy races, stale cache, partial-admission fail-closed behavior, duplicate prevention, and clean refresh survived real persistence | A fast crash-recovery SLO, Cloud Run behavior, model-layer security, or production readiness |

E2H-R1E operation counts per independent run were 199 reads, 31 writes, and
28 deletes; model calls were zero. Cleanup completed and the two normalized
event traces matched. The failed gate is an availability bound, not an
authority-safety violation.

## Internal result interpretation

The strongest defensible internal statement is:

> Architecture A is a logically coherent, action-scoped, generation-aware
> authority prototype. It survived deterministic falsifiers and a real
> Firestore/process boundary without an observed unauthorized ACT permit, but
> its real crash-recovery path exceeded the preregistered 90-second bound.

This statement is narrower than “Custody solves memory poisoning.” The current
Custody implementation already has an externally sourced trusted-tool-echo
failure, and Architecture A has not yet been measured against a comparative
external benchmark or a model-backed downstream agent.

## Evidence classes and untested claims

- **Logical model:** E2D, E2F, and E2G; these prove deterministic invariants
  of the harnesses only.
- **External attack adaptation:** E2A–E2C; these use a published TMA-NM
  attack construction but only measure the current Custody adapter.
- **Real persistence integration:** E2H-R1E; this is real Firestore and real
  OS-process separation, but not a shipping service or model benchmark.
- **Untested claim:** comparative end-to-end reduction in harmful actions,
  persistence, retrieval, delayed activation, selective repair, and benign
  utility against external benchmark families and reproducible baselines.

The next evidence must therefore start with an external attack/benchmark
artifact, pin its version and license, retain attacks Architecture A may fail,
and compare a baseline ladder before any new mechanism or production work.

## External Gate 1 interface correction

The first Gate 1 draft was deliberately not frozen because it prohibited every
baseline from receiving `true_origin`, while the pinned TMA-NM
`code/laundering.py` `tool_echo` reference constructs that field and its
official `tma_nm` authorization helper reads it. The corrected boundary is
documented in `TMANM_RUNTIME_BOUNDARY.md`.

The external comparison now separates three layers: scorer/world truth,
canonical observed events, and baseline-native security metadata. TMA-NM's
paper legitimately assumes an authenticated origin-labeling monitor, but the
published synthetic `tool_echo` field is also benchmark-materialized ground
truth. It is therefore classified **B3-ORACLE-COUPLED** for this Gate 1
fixture. TMA-NM remains a faithfully executed native benchmark reference; its
origin metadata is not passed to Current Custody or Architecture A, and the
primary table is explicitly a **NATIVE-INTERFACE COMPARATIVE SECURITY
EVALUATION**, not an equal-information comparison.

This correction changes no attack, endpoint, baseline, cost ceiling, benign
control, or Architecture A kill gate. No external Gate 1 result exists yet.

## Explicit stop conditions for the internal sequence

No E2I, E2J, or new bespoke deterministic Architecture A test is planned.
Only a future external evaluation result that exposes a specific new failure
can justify a separately preregistered follow-up.
