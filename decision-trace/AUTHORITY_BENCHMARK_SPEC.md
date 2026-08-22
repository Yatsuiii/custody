# DecisionTrace authority-resolution benchmark — preregistration

Written on `research/decisiontrace-authority-benchmark` from
`ca53fce3ef8f6212e417238f976f2623d8a5fb9e`. This specification is frozen
before any authority-benchmark Gemini generation, any grading, and any product
change. Later amendments may clarify a dry-run defect only before the first
generation call; every amendment must disclose the observed dry-run evidence
and may not use model outputs or scores.

Read `AUTHORITY_BENCHMARK_AUDIT.md` first. The frozen product cannot ingest
general acceptance or supersession events. The primary structured condition is
therefore explicitly **resolver-conditioned**: it evaluates the shipped
Decision/graph/retrieval/answer mechanism after lifecycle facts have been
normalized from source-explicit evidence. It is not presented as end-to-end
ingestion accuracy.

## 1. Research question and hypothesis

**Question.** Given the same ordered engineering history, does explicit,
source-grounded lifecycle state let the frozen DecisionTrace mechanism identify
the decision that governs at each checkpoint more reliably than a strong raw-
document embedding-RAG system using the same Gemini model?

**Central hypothesis.** Raw retrieval will usually find relevant artifacts, but
will more often promote a stale, merely proposed, reverted, or parallel decision
because it must reconstruct authority inside the generation call. DecisionTrace
will make fewer such errors when explicit lifecycle events are replayed before
generation.

This benchmark does not test rationale recall. It does not reuse the v0/v2
score or try to change the closed 87% versus 89% result.

## 2. Experimental unit

The independent cluster is a **timeline**. A timeline contains 4–9 ordered
artifacts/events from one real engineering history or one disclosed hybrid
history. At 3–6 preregistered checkpoints, a developer asks a natural question
of the form:

> What decision currently governs `<authority scope>`?

The scored unit is a `(timeline_id, checkpoint_id)` pair. The checkpoint sees
only events at or before its sequence number. No arm sees future artifacts.

Each timeline declares one or more authority scopes. Ground truth is one of:

- `GOVERNING(decision_id)` — explicit evidence establishes one governing
  decision for that scope;
- `UNRESOLVED` — explicit evidence conflicts or the applicable authority rule
  cannot safely select one;
- `NO_GOVERNING_DECISION` — no accepted/authoritative decision yet exists.

The distinction between `UNRESOLVED` and `NO_GOVERNING_DECISION` is scored.

## 3. Dataset size and composition fixed before source selection

Target: **15 timelines and 60–75 checkpoints**. The dataset is invalid and no
generation may run with fewer than **12 timelines or 48 checkpoints**.

Required source composition:

- at least 4 repositories or formal proposal ecosystems;
- at least 80% of source artifacts are verbatim real public engineering
  artifacts (PRs, revert PRs, RFCs/PEPs/KEPs, proposal metadata, issue/meeting
  decisions, or repository documentation at a pinned revision);
- no fully synthetic timeline;
- at least 8 timelines are fully real lifecycle sequences, meaning every
  lifecycle relation and ordering is directly expressed by the real artifacts;
- at most 7 timelines are hybrid, meaning artifacts are real but an event
  envelope or checkpoint sequencing is normalized from explicit source text;
- developer questions and checkpoint timing are synthetic in every timeline
  and are reported separately from artifact composition.

An event envelope may normalize `accepted`, `supersedes`, `reverts`,
`reaffirms`, `withdrawn`, `implemented`, `mention`, or `reconsiders` only when
the cited source excerpt explicitly supports that fact. It may not infer a
lifecycle transition from merge time, document recency, or semantic similarity
alone. This rule is uniform and cannot be relaxed per failure.

Required scenario coverage (a timeline may satisfy multiple rows):

| Scenario | Minimum timelines | Minimum scored checkpoints |
|---|---:|---:|
| simple supersession | 3 | 6 |
| multi-hop supersession | 2 | 4 |
| revert after supersession | 3 | 6 |
| proposal/reconsideration while an older decision governs | 3 | 6 |
| newer mention without supersession | 3 | 6 |
| parallel independent decisions | 2 | 4 per scope |
| conflicting authority evidence | 2 | 4 |
| implementation revert while policy authority may survive | 2 | 4 |

No timeline may exist solely to test a lexical marker. At least half of all
checkpoints must occur before the final event so final-state luck cannot
dominate the score.

## 4. Source selection and ground-truth rules

Sources are selected without looking at system outputs. Preferred substrates,
in order:

1. formal proposal metadata with explicit status/replaces/superseded-by fields;
2. merged PR and explicit revert-PR histories;
3. accepted design/RFC plus a later source that explicitly replaces it;
4. proposal or reconsideration artifacts explicitly still pending;
5. hybrid histories assembled only from the above source-explicit facts.

Ground truth is deterministic and LLM-free. For every checkpoint, the dataset
must record:

- the authority scope;
- expected authority state and public decision ID, if any;
- the exact evidence artifact IDs needed to prove the answer;
- the transition rule applied;
- the scenario/failure-class tags;
- a short human adjudication note quoting or precisely locating the source
  evidence.

The answer key lives in `data/authority/ground_truth.jsonl`, separate from
condition inputs. Public decision IDs may naturally appear in source artifacts;
hidden expected fields and adjudication notes may not enter prompts.

Exclude before generation when:

- a lifecycle fact requires an LLM to interpret ambiguous prose;
- chronology cannot be pinned;
- a source is inaccessible or its excerpt cannot be verified;
- the correct result depends on an unstated organizational convention;
- a code revert is the only evidence for a policy restoration;
- the case cannot distinguish authority from mere relevance.

Ambiguous but source-grounded histories remain eligible only when the correct
answer is explicitly `UNRESOLVED`; ambiguity is never adjudicated after seeing
an arm's response.

## 5. Authority semantics used for ground truth

These rules are fixed for the benchmark and are deliberately stricter than the
frozen resolver where necessary:

1. A proposal or reconsideration does not govern before explicit acceptance.
2. An accepted decision governs its declared scope unless later explicit
   lifecycle evidence changes it.
3. `B supersedes A` makes B govern only when B is itself explicitly accepted or
   authoritative.
4. A newer mention, implementation artifact, or document timestamp does not
   change authority.
5. Independent scopes coexist and are resolved separately.
6. A revert of B does **not** automatically restore A. The result is the
   explicit decision represented by the revert artifact when that artifact
   establishes a governing rollback decision; otherwise it is `UNRESOLVED`
   until explicit restoration/reaffirmation evidence appears.
7. A code implementation revert does not by itself reverse a surviving policy
   decision.
8. Contradictory authoritative artifacts with no source-grounded precedence
   rule yield `UNRESOLVED`.
9. Evidence must establish the authority transition, not merely discuss the
   same topic.

Rule 6 intentionally exposes the frozen product's actual `REVERTS` semantics
rather than redefining ground truth to match them.

## 6. Conditions

### 6.1 DecisionTrace resolver-conditioned baseline (primary structured arm)

Use the unmodified frozen modules from `ca53fce`: `Decision`,
`DecisionStatus`, `RelationshipType`, `DecisionGraph`, `resolve_active`,
`DecisionIndex`, and `collaborate.answer`.

A deterministic benchmark adapter converts only source-explicit event envelopes
into `Decision` records. It may not read `ground_truth.jsonl`, expected IDs, or
failure labels. It may use the public artifact ID as the decision ID because
the same ID appears in the raw RAG corpus. It may create only relationships
whose source artifact explicitly names both the relation and target. The
adapter and its derivation log are benchmark artifacts, not product changes.

At each checkpoint:

1. load only decisions/events available so far into an isolated JSON store;
2. build the shipped card embedding index;
3. call `collaborate.answer(question, index, k=8)`;
4. record the complete prompt inputs, retrieved IDs, resolver output, Gemini
   response, parsed current claim IDs, and API errors.

The primary score measures resolver-conditioned authority accuracy. A separate
**adapter coverage** metric reports the fraction of eligible lifecycle events
the deterministic adapter could represent. This prevents an oracle-normalized
score from being mistaken for deployed ingestion performance.

### 6.2 Strong raw-document RAG + Gemini

At the same checkpoint, index the same raw artifacts available to DecisionTrace,
including natural artifact IDs, timestamps/order metadata, status words,
supersession language, and revert text. Do not strip lifecycle terms.

- chunk size: 1,600 characters;
- overlap: 200 characters;
- embedder: frozen `text-embedding-005` via `vertex.py`;
- retrieval budget: top 8 chunks, or all chunks when fewer than 8 exist;
- generation model: frozen `gemini-3.7-flash` via `vertex.py`;
- prompt: explicitly asks for the current governing decision, requires
  `GOVERNING`, `UNRESOLVED`, or `NO_GOVERNING_DECISION`, requires public
  decision/artifact IDs and supporting evidence IDs, tells the model that
  relevance/recency/proposal/implementation do not alone establish authority,
  and permits abstention;
- context includes source identifiers on every chunk;
- no target document is anonymized and no artifact is removed.

The RAG response schema is strict JSON. Parse failure is an incorrect answer,
not retried.

### 6.3 Code/current-repository-only baseline

Omitted. The selected proposal and PR ecosystems do not have a uniform pinned
current-code snapshot that can answer the same authority question. A no-history
prompt would mostly measure Gemini prior knowledge and cannot be made
equivalent across timelines without inventing inputs. This omission is fixed
before source selection and is reported in results.

## 7. Equivalence and no-secret-information rules

- Both arms receive events only through the same checkpoint.
- Both arms use the same public artifact IDs, timestamps, source URLs, and raw
  lifecycle words.
- DecisionTrace gets no expected ID, expected state, scenario label, failure
  label, or adjudication note.
- RAG gets no hidden lifecycle label. A normalized event envelope is included
  in RAG only when it is also the public input from which the structured adapter
  parses the event.
- DecisionTrace evidence quotes must be verbatim substrings of the raw artifact
  RAG receives.
- No arm gets future artifacts.
- Model/version and retry policy are identical. Responses are generated once;
  parse failures, refusals, and API failures are recorded.
- There is no selective regeneration. If an API call fails, the row remains an
  API failure and is not silently scored correct.

## 8. Output contract and deterministic grader

The grader is programmatic; no LLM judge is used for the headline metrics.
This avoids judge retry/variance as a confound.

Normalize each arm to:

```json
{
  "authority_state": "GOVERNING | UNRESOLVED | NO_GOVERNING_DECISION",
  "governing_decision_id": "public id or null",
  "evidence_ids": ["public artifact id", "..."],
  "raw_response": "..."
}
```

For DecisionTrace, a valid `current_active_decision` claim supplies the
governing ID. No valid current claim plus an explicit missing/uncertain claim
normalizes to `UNRESOLVED`, except a claim explicitly saying no accepted
decision exists normalizes to `NO_GOVERNING_DECISION`. Multiple different
current IDs normalize to `UNRESOLVED` and count as inconsistent authority.

**Governing-decision accuracy** is exact authority-state match plus exact public
decision-ID match when the state is `GOVERNING`. Case and punctuation are
normalized; aliases are preregistered in the dataset before generation.

**Evidence correctness** requires at least one expected authority-establishing
artifact ID and forbids citing a conflicting artifact as the authority proof.
Extra relevant evidence is allowed. Correct authority with wrong/no evidence
fails evidence correctness but remains authority-correct.

## 9. Failure classes

Every incorrect row receives all applicable deterministic tags; one primary
tag is selected by the fixed priority order below for mutually exclusive totals.

1. `STALE_DECISION` — predicted ID governed earlier but was superseded.
2. `PROPOSAL_PROMOTED` — predicted ID is only proposed/reconsidered.
3. `REVERT_MISSED` — predicted ID was explicitly displaced by a relevant
   revert decision or the answer ignored an unresolved post-revert state.
4. `SUPERSESSION_MISSED` — predicted predecessor remained after an accepted
   explicit successor.
5. `RECENCY_CONFUSION` — predicted newest mention/document without authority
   evidence.
6. `PARALLEL_DECISION_COLLAPSE` — predicted a decision from a different
   independent scope or suppressed a coexisting scope.
7. `UNSUPPORTED_AUTHORITY` — returned `GOVERNING` when evidence supports
   `UNRESOLVED`/`NO_GOVERNING_DECISION`, or cited no authority-establishing
   evidence.
8. `MISSING_CORRECT_DECISION` — abstained, returned none, or returned an ID not
   covered above when one correct governing decision exists.
9. `EVIDENCE_ERROR` — authority answer correct but expected authority evidence
   absent or wrong.

Primary priority is the numbered order except that `EVIDENCE_ERROR` is primary
only when authority is correct. Retrieval misses and parse/API failures are
recorded separately as mechanisms, not silently mapped to lifecycle semantics.

## 10. Metrics

Report numerator/denominator for:

- governing-decision accuracy;
- evidence correctness;
- authority-plus-evidence combined accuracy;
- stale-answer rate (`STALE_DECISION` among all checkpoints);
- false-authority rate (`GOVERNING` predicted when expected state is not
  `GOVERNING`, plus proposal promotion and unsupported authority);
- proposal-promoted rate;
- revert-miss rate on revert-applicable checkpoints;
- supersession-miss rate on supersession-applicable checkpoints;
- consistency across repeated checkpoints: identical visible history and scope
  must normalize to the same answer;
- adapter coverage;
- retrieval coverage of expected evidence for RAG and expected cards for
  DecisionTrace;
- API/parse failure rate.

Break down by scenario type, repository/ecosystem, real versus hybrid timeline,
and checkpoint position (intermediate versus final).

Use Wilson 95% intervals for marginal proportions. Because checkpoints within a
timeline are dependent, use a paired cluster bootstrap over timelines (10,000
resamples, fixed seed `20260822`) for the DecisionTrace-minus-RAG accuracy
difference and stale/false-authority differences. Report both; do not treat the
per-checkpoint Wilson interval as independent evidence.

## 11. Preregistered success criterion

Declare an authority advantage only if **all** hold on the untouched baseline:

1. DecisionTrace governing-decision accuracy exceeds RAG by at least **10
   percentage points**;
2. the lower bound of the paired timeline-clustered **90%** bootstrap interval
   for that accuracy difference is greater than 0;
3. DecisionTrace makes at least **25% fewer** combined stale and false-authority
   errors than RAG, with at least 4 absolute errors rescued;
4. DecisionTrace evidence correctness is no more than 5 percentage points below
   RAG;
5. every dataset, equivalence, leakage, and source-verification gate passes.

Why 10 points: at the minimum 48 checkpoints it requires roughly five net
rescues, large enough to matter against the operational complexity of lifecycle
state. The paired interval prevents one repeated long timeline from manufacturing
that margin. The error-reduction condition requires the gain to come from the
claimed authority mechanism rather than unrelated response formatting.

Result labels are frozen:

- `STRONG AUTHORITY ADVANTAGE — USE CLAIM`: all success criteria and at least a
  15-point accuracy advantage.
- `MODEST AUTHORITY ADVANTAGE — KEEP RESEARCHING`: all success criteria with a
  10–<15-point advantage, or a positive 3–<10-point advantage that fails only
  the magnitude/interval criterion.
- `TIED WITH RAG — PRODUCT VALUE MUST COME FROM WORKFLOW`: absolute accuracy
  difference at most 3 points, with no material stale/false-authority advantage.
- `RAG WINS — DO NOT CLAIM AUTHORITY ADVANTAGE`: RAG leads by more than 3 points,
  or DecisionTrace has materially more stale/false-authority errors.
- `BENCHMARK INVALID — FIX BEFORE CONCLUDING`: any mandatory data, equivalence,
  leakage, ground-truth, protected-file, or minimum-size gate fails.

No threshold changes after generation.

## 12. Dry-run dataset gates before Gemini

The build command must print and persist:

- total timelines and checkpoints;
- repositories/ecosystems;
- lifecycle event counts;
- every scenario count in §3;
- supersession, revert, proposal-only, parallel, and conflict counts;
- real artifact, fully-real timeline, hybrid timeline, and synthetic query
  counts;
- intermediate versus final checkpoint counts;
- exclusions by rule;
- adapter coverage and any unrepresentable event types.

Before generation, manually source-check and record in
`data/authority/SPOT_CHECKS.md` at least:

- 3 supersession timelines;
- 3 revert timelines;
- 3 proposal-not-authoritative timelines;
- 2 parallel timelines.

Every checked ground truth must cite an artifact URL, pinned identifier/revision,
and exact supporting excerpt. If any ground truth needs model interpretation,
exclude it or mark the checkpoint `UNRESOLVED` under the predeclared rules.

## 13. Leakage and protected-artifact gates

`test_no_leakage_authority.py` must prove for every realized prompt:

- hidden expected IDs do not appear unless naturally present in a visible
  source artifact;
- expected state, scenario/failure tags, and adjudication notes never appear;
- no RAG-only hidden lifecycle labels are injected;
- the DecisionTrace adapter never reads the ground-truth path;
- benchmark questions contain no status or rationale answer;
- visible artifact IDs and histories are equivalent at every checkpoint;
- no future event appears;
- evidence quotes are substrings of the equivalent raw artifact;
- v0/v2 protected files match a checksum manifest captured from `ca53fce`.

Protected paths include `RESULTS.md`, `RESULTS_V2.md`,
`BENCHMARK_FAILURE_AUDIT.md`, `BENCHMARK_V2_SPEC.md`, all v0/v2 scripts, and
`data/v2/` plus `data/runs_v2/`. Authority work writes only new authority paths.

No generation command is allowed until all dry-run, spot-check, unit, equivalence,
leakage, and protected-checksum gates pass.

## 14. Baseline run and one-intervention protocol

Generate every eligible checkpoint once for both arms. Do not rerun an incorrect,
malformed, or refused response. Grade once with the deterministic grader.

If DecisionTrace does not satisfy the success criterion:

1. classify every DecisionTrace miss as `ingestion/extraction`, `lifecycle
   representation`, `deterministic resolver`, `retrieval`, `generation`,
   `evidence binding`, `ambiguous ground truth`, or `other`;
2. write `AUTHORITY_INTERVENTION.md` before code, stating one hypothesis, the
   exact single changed variable, expected rescued case IDs, implementation
   owner/module, and kill criterion;
3. choose exactly one highest-leverage system change only if the miss taxonomy
   supports it;
4. freeze the dataset, questions, RAG responses, model settings, grader, and
   thresholds;
5. regenerate the DecisionTrace arm for every checkpoint exactly once. RAG
   responses are reused only because their realized prompts are byte-identical;
6. report baseline and post-intervention separately. Never replace the baseline.

Default intervention kill criterion: kill/revert the change if it rescues fewer
than half the preregistered expected cases, creates more than one new regression,
or fails any leakage/equivalence/protected-file gate. A more specific criterion
must be frozen in `AUTHORITY_INTERVENTION.md` before implementation.

## 15. Process-boundary test

Secondary only. On at least two timelines, persist through a middle checkpoint,
destroy the process/store objects, reopen a fresh process against the same JSON
store, continue the timeline, and verify the authority result and evidence are
identical to uninterrupted replay. This is not included in the headline
accuracy denominator.

## 16. Cost-relevant work

At 60–75 checkpoints, baseline generation budget is 120–150 Gemini calls: one
DecisionTrace answer and one RAG answer per checkpoint. Headline grading uses
zero Gemini calls. Embedding calls are cached by exact visible corpus/checkpoint
content and fully counted in the run manifest. No card distillation calls are
allowed: structured records use only source-verbatim evidence and deterministic
event normalization.

If one intervention is attempted, add one DecisionTrace generation per
checkpoint (60–75 calls); reuse RAG only under byte-identical prompt hashes.
API errors are not retried outside `vertex.py`'s fixed transport retry policy.

## 17. Required artifacts

- `AUTHORITY_BENCHMARK_AUDIT.md`
- `AUTHORITY_BENCHMARK_SPEC.md`
- `AUTHORITY_INTERVENTION.md` only if the protocol triggers it
- `build_authority_cases.py`
- `run_authority_conditions.py`
- `grade_authority.py`
- `test_no_leakage_authority.py`
- `data/authority/` for sources, timelines, ground truth, manifests, exclusions,
  prompt hashes, and spot checks
- `data/runs_authority/` for immutable baseline and optional intervention runs
- `RESULTS_AUTHORITY.md`

## 18. Authority-versus-lineage boundary

The benchmark asks which organizational decision governs after explicit
proposal, acceptance, replacement, reconsideration, and rollback events. It
does not follow source-derived descendants or remove downstream state. If a
timeline's expected output becomes a set of affected derived records rather
than one governing decision/uncertainty per authority scope, the case is
invalid and must be redesigned before generation.
