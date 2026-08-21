# DecisionTrace Hackathon Hardening Audit

Date: 2026-08-21
Branch: `hardening/collaborative-pre-submission`
Lane: evidence-gated agentic developer tooling

## Scope and baseline evidence

This is a read-only phase-1 audit. Existing user changes were preserved; no
product code or benchmark results were changed by this audit.

Commands run:

- `rg --files -uu` plus direct reads of `README.md`, `BUILD_SCOPE.md`,
  `RESULTS.md`, `HANDOFF.md`, `docs/*.md`, `Dockerfile`, `.streamlit/config.toml`,
  `app/*.py`, `app/tests/*.py`, and the falsifier scripts.
- Source corpus count: `data/decisions.jsonl` has 42 source rows: 21
  `revert_pair` and 21 `kep_alternatives`, all with `rationale_card`.
- Domain expansion count: `app.loader.load_decisions()` produces 63 decisions
  (two decisions per revert pair, one per KEP row).
- Persisted benchmark-run count: 37 files in each of
  `data/runs/{code_only,rag,structured}`.
- `pytest --collect-only`: 46 tests collected.
- `pytest -q app/tests/test_graph.py app/tests/test_ui.py`: 14 passed.
- `pytest -q app/tests/test_store.py::test_all_benchmark_records_load_without_error app/tests/test_store.py::test_store_round_trip_persists_and_reloads`:
  1 passed, 1 failed. The failure is `63 == 55` in
  `app/tests/test_store.py::test_all_benchmark_records_load_without_error`.
- `git diff --check` and `python3 -m compileall -q app *.py`: passed.

The networked Gemini, GitHub, and Firestore tests were not treated as a
passing baseline in this phase. Their outcome remains unknown until the
benchmark/data state is made internally consistent.

## Executive verdict

DecisionTrace has a strong structured-memory core and a real Google Cloud
integration, but it currently presents a single Gemini answer stage surrounded
by deterministic infrastructure rather than a visibly collaborating set of
specialized workers. The core is worth preserving. The weakest submission
point is Collaborative-track legitimacy; the second is that current truth is
more deterministic than the evidence explaining that truth.

The branch is **needs hardening**, not submit-ready, because the current
working tree cannot pass its own store test and its checked-in corpus, cached
runs, documentation, and tests describe different dataset sizes.

## A. Collaborative legitimacy

### What exists today

The product has useful separable responsibilities, but they are modules and
stages, not agent workers with exchanged observations:

| Current component | Actual contribution | Evidence |
|---|---|---|
| `ingest.ingest_repo()` | Discovers merged revert PRs and KEP-style alternatives; asks Gemini for structured extraction and verifies returned quotes | `app/ingest.py:101-126`, `app/ingest.py:276-284` |
| `retrieval.DecisionIndex` | Embeds decision cards and returns evidence-bearing candidates | `app/retrieval.py:77-133` |
| `graph.resolve_active()` | Resolves lifecycle state from typed edges without an LLM | `app/graph.py:70-98` |
| `collaborate.answer()` | Sends retrieved records and resolver output to one Gemini call and parses four claim categories | `app/collaborate.py:56-160` |
| `memory.propose_reconsideration()` | Persists a developer-originated `PROPOSED` record and `RECONSIDERS` edge | `app/memory.py:35-63` |

### Track-fit assessment

- Distinct expertise is present conceptually: discovery/extraction,
  retrieval, lifecycle resolution, provenance-bearing synthesis, and memory
  evolution.
- There is no worker/agent message contract, observation record, challenge
  pass, disagreement object, or reconciliation result. The one Gemini call is
  the only model-level reasoning participant in the answer path.
- `resolve_active()` supplies a deterministic fact to Gemini, but it does not
  exchange an intermediate result with another agent or visibly challenge a
  candidate. The UI renders a chat, card, and timeline; it does not render
  agent contributions.
- A judge could reasonably describe the current system as
  `embedding retrieval -> deterministic helper -> one LLM answer`, with
  “collaboration” implied by module names. That is the weakest point.

**Finding A-1 — P0:** the product’s visible collaborative story is not yet
credible for the Collaborative track. The safest remedy is to expose the
existing deep responsibilities as a small worker topology and add a real
challenge/reconciliation boundary, without removing the deterministic graph
or replacing the answer path.

## B. Decision lifecycle

### Current representation

| Lifecycle stage | Explicit today | Inferred today | Deterministic today | Model-dependent today |
|---|---|---|---|---|
| Proposal | `DecisionStatus.PROPOSED`; conversation candidates | Gemini extraction describes a source as a decision | Status is stored as an enum | `ingest.extract_decision_fields()` fills subject/context/chosen fields |
| Alternatives | KEP source text and `rationale_quote`; `rejected_alternatives` is empty in the frozen loader | The quote is treated as rationale for an alternative | No per-alternative identity or edge | Gemini extraction may emit alternatives for live ingest |
| Acceptance | KEP rows load as `ACCEPTED` | Source type is used as a proxy for accepted design | Stored status only | Extractor can describe chosen approach |
| Implementation | Revert pair’s original PR loads as `IMPLEMENTED` | Merged PR is treated as implementation evidence | Stored status only | No implementation-agent check |
| Supersession | Typed `SUPERSEDES` exists in the enum | Live extraction does not create supersession edges | Resolver can replay a typed edge | No model output is reconciled into a canonical edge |
| Revert | Revert pair creates a second `REVERTS` node and edge, with status `REVERTED` | A revert node is treated as the current operative state until a later explicit event | Resolver advances to the revert node | Source discovery and Gemini extraction identify the pair |
| Current active decision | `ActiveResolution(active_id, history, ambiguous)` | `RetrievalCandidate.is_current` excludes `PROPOSED` | `resolve_active()` traverses lifecycle edges | Gemini must report, not decide, status |

### Important current semantics

- A direct `A -> B` `SUPERSEDES` chain resolves to `B`.
- A multi-hop `A -> B -> C` chain resolves to `C` only when decisions are
  passed in chronological order.
- A `B REVERTS A` event makes the revert record `B` the active operative
  state. The original `A` is not automatically restored. Existing tests and
  the demo depend on this rule.
- A later `REAFFIRMS A` can reactivate `A`.
- A mention without a typed lifecycle edge does not enter the resolver’s
  lineage, so it does not automatically supersede anything.
- Parallel decisions are isolated when no lifecycle edge connects them.
- A fork where two nodes supersede the same active predecessor is surfaced as
  ambiguous.

### Lifecycle gaps

- `DecisionGraph` explicitly assumes callers provide roughly chronological
  input order (`app/graph.py:20-21`), but Firestore stream order is not a
  domain chronology and `introduced_at` is not used to sort. Equal or missing
  timestamps have no stated tie policy.
- Cycles are not fully fail-closed. For example, `A SUPERSEDES B` plus
  `B SUPERSEDES A` can be replayed as a last-writer result rather than an
  ambiguous cycle; the current test suite covers a fork but not a cycle.
- `superseded_at` is never populated by the loader or live ingestion, and
  statuses are not materialized from accepted lifecycle events. Historical
  records remain visible, but the canonical state is carried mostly by edge
  traversal rather than an auditable event record.
- Live ingestion creates only the two validated source shapes. It does not
  yet identify documentation supersession, code implementation evidence, or
  reverts beyond the discovered PR pair.
- Lifecycle edges have no first-class evidence. The edge says that one record
  supersedes/reverts another, but not which source artifact established that
  relationship or why.

**Finding B-1 — P1:** lifecycle resolution is a valuable deterministic moat,
but ordering, cycle handling, and edge provenance need explicit contracts
before the system can claim “current truth” under adversarial evidence.

## C. Provenance

### What survives ingestion

- Frozen records retain source URLs and verbatim `rationale_quote` values.
- `loader.py` transfers those values into `Evidence.quote`; JSON and Firestore
  round trips preserve evidence fields, covered by `app/tests/test_store.py`.
- Live extraction verifies that `rationale_quote` is a whitespace-normalized
  substring of fetched source text before creating evidence
  (`app/ingest.py:72-75`, `app/ingest.py:109-125`).
- The UI displays evidence URLs, quotes, statuses, and the resolver timeline.

### What does not survive or is not enforced

- A decision does not retain an immutable source snapshot, source artifact ID
  as a typed field, source hash, author, or extraction timestamp. The URL may
  point to mutable `master` content.
- KEP alternatives are not represented as named structured alternatives in the
  frozen loader; `rejected_alternatives` is deliberately empty and the quote
  may be only one sentence from a multi-alternative section.
- Resolver output contains `history` and an active ID, but no deterministic
  explanation such as “C is active because C REVERTS B, which SUPERSEDES A,”
  and no evidence attached to each edge.
- `_parse_claims()` accepts any model-supplied `decision_id`; it does not
  require the ID to be a retrieved candidate, a known store record, or the
  source of a claim’s evidence. A model can therefore emit a confident claim
  with a fabricated or mismatched ID, even though the UI usually renders the
  retrieved card separately.
- `collaborate._render_candidate()` supplies evidence URLs but not a structured
  per-claim evidence key. The final answer’s provenance is inferred from the
  model’s ID tag rather than checked against a canonical claim/evidence map.

**Finding C-1 — P1:** source quotes are retained better than in generic RAG,
but “why is this currently active?” is not yet a fully auditable answer. The
system needs a small provenance/claim validation boundary that can reject
unlinked claims and expose the resolver’s edge-based reason.

## D. Hackathon demonstration

### Strengths preserved

- The delayed-preemption revert is a concrete before/after case that ordinary
  retrieval must reconcile: original PR, revert PR, current operative state,
  evidence quote, and timeline.
- The card, status badge, timeline, and reconsideration write make historical
  truth versus proposed future change visible.
- Firestore persistence and Cloud Run are substantive, not logo padding:
  `FirestoreDecisionStore` owns durable decisions and candidates, and Vertex
  AI through `google-genai` owns embedding and generation calls.
- The benchmark’s structured-vs-RAG result remains useful evidence, but the
  checked-in result is specifically `n=37`, RAG 57%, structured 76%, CAUTION.

### Demo weaknesses

- A judge cannot currently watch “discover -> disagree/challenge -> reconcile
  -> resolve -> update organizational truth.” The script shows answer,
  timeline, and persistence, but not multiple workers exchanging evidence.
- The problem is clearly harder than plain RAG only after the resolver/timeline
  is explained; the current screen does not visually prove a challenge or
  disagreement.
- The “before/after” is mostly a `PROPOSED` reconsideration. It intentionally
  does not change active truth, which is correct, but the demo needs to make
  that distinction explicit: memory updates while governing truth remains
  unchanged until an explicit lifecycle event.
- Demo and README language still contains old 55-decision references even
  though the live working corpus is mid-expansion. This weakens judge trust.
- Google/Gemini/Cloud integration is substantive in code, but the visible
  collaborative contribution of Gemini is currently just one final answer
  call rather than a role in a multi-worker reconciliation.

**Finding D-1 — P0:** the demo cannot yet prove the requested collaborative
spectacle, even though it can prove structured active-truth resolution and
persistence.

## E. Reliability

### P0/P1 risks

- **P0 — inconsistent submission state.** The user-owned expansion has 42
  source rows and 63 loaded decisions, while persisted run artifacts remain
  at 37, `RESULTS.md` remains n=37, README describes 55 loaded decisions,
  and at least one store test asserts 55. The full suite is therefore known
  to fail before networked tests run. The expansion notes explicitly say its
  run/grade/update gates are unfinished.
- **P1 — order-dependent truth.** `DecisionGraph` depends on input order, while
  JSON and Firestore can expose different ordering. This can make equal data
  resolve differently across local and Cloud Run sessions.
- **P1 — cycle and conflict behavior.** Forks are tested as ambiguous, but
  cycles, conflicting agent observations, and conflicting source evidence are
  not represented as a durable uncertainty state. A single Gemini response
  can still select among retrieved candidates without an explicit challenge.
- **P1 — no semantic retrieval floor.** `DecisionIndex.search()` returns the
  top-k vectors for every query, including decoys. `answer()` calls Gemini for
  any non-empty result; there is no calibrated similarity threshold, source
  identity filter, or explicit “retrieval found no credible evidence” gate.
- **P1 — retry budget can exceed the request budget.** `vertex._with_backoff()`
  retries all exceptions up to six attempts with 60-second HTTP timeouts and
  exponential sleeps. A persistent failure can outlive the Cloud Run timeout,
  especially during cold-start embedding or live ingest.
- **P1 — missing evidence can be stored.** Live extraction creates accepted
  decisions with empty evidence when quote verification fails. That is safer
  than fabricating a quote, but those records must remain non-authoritative and
  should not be eligible to ground a current-truth answer.
- **P1 — persistent demo state leaks.** Firestore is shared and candidates from
  prior smoke tests remain visible. This is realistic product state but makes
  a submission demo non-reproducible without a reset/fixture boundary.

### P2 risks

- `_parse_claims()` uses greedy regular-expression extraction rather than a
  schema-validated response; malformed output degrades, but valid-looking
  untrusted IDs are not checked.
- `JSONFileDecisionStore._flush()` rewrites the file in place rather than
  atomically replacing it. A process interruption during a write can corrupt
  local state.
- Firestore uses one collection despite `BUILD_SCOPE.md` describing separate
  `decisions`, `edges`, and `conversations` collections. The actual one-
  collection design is simpler and should be documented rather than silently
  treated as the three-collection architecture.
- Benchmark comments/tests/docs contain stale “55”, “18 pairs”, and “19 KEP”
  assumptions alongside the in-progress expansion. This is primarily a
  submission hygiene risk once the corpus decision is made.

## Adversarial case coverage

| Case | Current status | Evidence / gap |
|---|---|---|
| Straight supersession | Partially supported | Resolver handles a typed edge; no focused test in `test_graph.py` for a plain A -> B supersession with evidence. |
| Multi-hop supersession | Supported under input-order assumption | `test_supersede_then_revert_chain` exercises a 3-node chain, but not pure A -> B -> C or reordered input. |
| Revert | Supported with explicit current semantics | Existing test makes the revert node active; no test proves a later explicit replacement or reaffirmation after the revert. |
| Mention without supersession | Safe by omission | Only lifecycle edge types enter the lineage; no direct regression test. |
| Conflicting agents | Missing | No agent observations or reconciliation object exists. |
| Parallel decisions | Supported | Existing isolated-lineage test covers this. |
| Missing provenance | Unsafe for authority | Empty evidence can be stored; model IDs are not validated. |
| Code reality vs documentation | Missing | No implementation/revert evidence reconciliation beyond the paired revert shape. |
| Decoy retrieval | Partially protected | Card IDs and resolver status help after retrieval, but no relevance floor prevents a decoy from reaching Gemini. |

## Audit-ranked change candidates (not selected yet)

These are deliberately narrow candidates for phase 4. Selection must be capped
at three and made only after this audit is reviewed against regression risk.

1. Add a visible, testable worker topology around the existing path:
   evidence scout, lifecycle resolver, provenance challenger, and Gemini
   reconciler. Preserve `DecisionIndex`, `resolve_active`, and the final
   `Answer` API; return a compact collaboration trace for the UI.
2. Add a canonical provenance/claim gate: validate model claim IDs against
   retrieved candidates, require evidence for authoritative categories, and
   attach a deterministic lifecycle explanation to the resolution.
3. Make lifecycle replay deterministic independent of store order and fail
   closed on cycles/conflicts, with adversarial tests for supersession, revert,
   mentions, parallel decisions, missing evidence, and decoys.
4. Close the benchmark state safely: either complete the additive 42-row
   rerun/grade/update gates or restore the pre-expansion corpus as a separate
   deliberate choice. Do not edit numbers without rerunning the evaluation.
5. Add a submission-safe demo reset/fixture boundary and document one-command
   startup/verification, without replacing the Cloud Run/Firestore path.

## Phase-1 conclusion

The large collaborative product should remain. The structured decision graph,
evidence quotes, card retrieval, Firestore persistence, live ingestion, and
Gemini/Vertex integration are valuable strengths. The first hardening decision
must repair the submission-state contradiction and make the existing roles
legible as real cooperating workers. Any lifecycle/provenance change must be
small, deterministic, and protected by adversarial tests; a research refactor
or a generic chat/RAG redesign would violate the product thesis.

## Selected changes before implementation

The following three changes are selected using
`collaborative-track value × correctness gain × moat gain ÷ regression risk`:

### 1. Make the checked-in submission state self-consistent

Update the benchmark-count assertions, stale comments, and judge-facing
corpus description to distinguish:

- the frozen, graded falsifier evidence (`RESULTS.md`, n=37, with 37 runs per
  condition), and
- the user-owned in-progress additive source corpus (42 JSONL rows, 63 loaded
  domain decisions, with new runs/grades intentionally not yet claimed).

Add a test-level invariant that derives the expected loaded count from the
source rows instead of hardcoding the old 55. This does not alter metrics,
rerun the benchmark, or rewrite the user’s data expansion. It closes the
known failing store test and prevents another silent count drift.

### 2. Add a real worker boundary and provenance gate to the answer path

Keep the existing modules and Gemini provider, but make their collaboration
explicit and observable:

`EvidenceScout` (card retrieval) -> `LifecycleResolver` (typed deterministic
resolution) -> `ProvenanceChallenger` (evidence/ambiguity/identity checks) ->
`GeminiReconciler` (grounded explanation).

Each worker contributes a small report to the answer trace. The challenger
rejects authoritative claims whose IDs are not retrieved/known or whose
source evidence is missing; it does not invent a replacement answer. The UI
will show this trace in a compact expander so the judge can see discovery,
challenge, reconciliation, and the final resolution. The existing `Answer`
shape remains compatible, with trace data additive.

### 3. Make lifecycle resolution order-independent and fail closed

Retain the current revert semantics: a revert record is the active operative
state until a later explicit lifecycle event says otherwise. Sort lifecycle
replay by `introduced_at` with stable ID fallback, detect cycles, and return an
ambiguous resolution rather than selecting a last-writer result. Add focused
tests for straight supersession, multi-hop supersession, revert semantics,
mention-without-edge, parallel lineages, missing provenance, conflicting
lineages, and decoy candidate protection where the resolver is involved.

This is a deep-module change inside `graph.py`; callers continue to receive
`ActiveResolution`, while uncertainty becomes an explicit result instead of
an accidental choice based on Firestore iteration order.

### DDIA decision record

**Verdict:** risky but shippable after the gates below; no unresolved write,
replay, or storage migration is introduced by the selected changes.

- **Chosen design:** keep `DecisionStore` as the persistence owner; keep
  lifecycle edges embedded in `Decision`; compute worker traces per answer;
  keep resolver output deterministic and read-only.
- **Key invariants:** unique decision IDs; proposals never become current;
  evidence-less records cannot ground authoritative claims; lifecycle cycles
  and forks are ambiguous; chronological ties resolve by stable ID; a revert
  does not silently restore its predecessor.
- **Rejected alternatives:** introducing Pub/Sub/queues, a graph database,
  three new Firestore collections, or Google ADK session state for this
  hardening pass. Each would enlarge operational risk without being needed to
  show multi-worker evidence exchange.
- **Failure mitigation:** missing evidence becomes a challenge/uncertain
  result; ambiguous lifecycle state is surfaced; duplicate writes remain
  idempotent by decision ID; benchmark metrics remain frozen until a complete
  rerun exists.
- **Acceptance gates:** the store suite passes; lifecycle adversarial tests
  pass; model claims cannot ground an unknown or evidence-less decision; the
  UI renders worker stages; the full validation report states exactly which
  benchmark artifacts were and were not rerun.
- **Smallest proof artifact:** one demo query showing
  `discover -> challenge -> reconcile -> resolve`, with a reverted historical
  node, an active operative node, deterministic lifecycle explanation, and
  clickable evidence.
