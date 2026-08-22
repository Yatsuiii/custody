# DecisionTrace prospective authority benchmark preregistration

Status: **FROZEN BEFORE SOURCE DISCOVERY**  
Research branch: `research/decisiontrace-authority-prospective`  
Starting commit: `8cbf14d7b809722d5c4f0fb89202317fa8681df3`  
Resolver-freeze commit: `91c9a710331b63105e07785b824047746f1bc7f0`  
Resolver manifest: `data/prospective/resolver_freeze_sha256.json`

The prior authority benchmark is a development set. Its frozen-product result
was DecisionTrace 47/61 (77.0%) versus strong RAG 52/61 (85.2%): RAG won. The
post-hoc resolver's 61/61 result on that same set is motivating evidence only,
not prospective evidence and not a public authority-superiority result.

## Hypothesis and changed variable

**Hypothesis.** On completely unseen, source-grounded organizational-decision
histories, explicit scope, lifecycle status, decision role, and typed transition
replay will identify the currently governing decision more reliably than a
capable model reconstructing authority from equally visible raw history.

The fixed comparison is representational and algorithmic:

- DecisionTrace projects source-explicit public artifact fields into its frozen
  typed decision model and applies the byte-frozen deterministic resolver.
- Strong RAG receives the same visible public artifacts and source-derived
  metadata, retrieves source text, and asks the same Gemini model to infer
  current authority.

No source, expected ID, scope exception, status mapping, edge rule, prompt,
retrieval parameter, parser, metric, or threshold may be changed after a system
output exists. The resolver itself was frozen before even source discovery.

## Strict preregistered GO gate

`STRONG AUTHORITY ADVANTAGE — USE CLAIM` requires **all** primary conditions:

1. DecisionTrace governing-decision accuracy is at least 90%.
2. DecisionTrace is at least 8.0 percentage points ahead of the preregistered
   strong-RAG comparator.
3. The paired timeline-bootstrap 90% confidence interval for DecisionTrace
   minus strong RAG is strictly above zero.
4. DecisionTrace evidence correctness is no more than 3.0 percentage points
   below strong RAG.
5. DecisionTrace's false-authority rate is not materially worse: it may not be
   both more than 3.0 points higher and at least two errors higher than RAG.

It must additionally have a strictly lower eligible-checkpoint error rate than
RAG on at least two of: revert misses, supersession misses, proposal promotion,
parallel-decision collapse, and unsupported authority. A category with zero
eligible checkpoints cannot count.

If every primary condition and the secondary requirement pass, the verdict is
`STRONG AUTHORITY ADVANTAGE — USE CLAIM`. Otherwise:

- DT ahead but strict GO fails: `MODEST AUTHORITY ADVANTAGE — KEEP RESEARCHING`.
- Exact governing-accuracy tie: `TIED WITH RAG — PRODUCT VALUE MUST COME FROM WORKFLOW`.
- RAG ahead: `RAG WINS — DO NOT CLAIM AUTHORITY ADVANTAGE`.
- Any mandatory data, independence, leakage, equivalence, or run-once gate
  fails: `BENCHMARK INVALID — FIX BEFORE CONCLUDING`.

Thresholds are immutable after this preregistration.

## Prospective population and dataset gates

The frozen dataset must contain 20–30 new timelines and 80–120 checkpoints,
with zero fully synthetic timelines. No prior authority timeline, decision ID,
artifact URL, or equivalent source history may be reused. It must cover at
least five ecosystems, and no ecosystem should exceed 30% of timelines; if
defensible primary-source cases cannot meet that diversity gate, the benchmark
is invalid rather than padded.

The target is at least 14 fully-real timelines. A timeline is fully real when
its artifact sequence and evaluated transition times correspond to real source
history. A hybrid timeline may use real pinned artifacts and source-grounded
relations with a synthetic developer query/checkpoint time. Only the query time
may be synthetic. Synthetic artifacts, statuses, relations, or decisions are
forbidden.

Scenario labels may overlap. Before inference the dataset must include:

| Scenario family | Minimum timelines |
|---|---:|
| simple supersession | 5 |
| multi-hop supersession | 3 |
| revert after supersession or implementation | 5 |
| proposal while older authority remains | 5 |
| newer mention without transition | 4 |
| parallel decisions in distinct scopes | 4 |
| conflicting/ambiguous authority evidence | 3 |
| withdrawn or rejected candidate | 3 |
| implementation-versus-policy distinction | 3 |
| revert without automatic policy restoration | 2 |
| explicit restoration after revert | 2 |

These are inclusion gates, not quotas to fill with weak examples. An unclear
source is excluded and logged before outputs. Quality failure invalidates the
benchmark.

## Independence protocol

The only allowed order is:

1. source discovery from primary repositories and official proposal systems;
2. source-only ground-truth adjudication and exclusion logging;
3. complete manual audit and a separate second-pass audit of at least five
   supersession, five revert, five proposal-not-authoritative, every parallel,
   and every ambiguous timeline;
4. public/hidden dataset freeze with hashes and a Git commit;
5. leakage, equivalence, unseen-case, and frozen-resolver gates;
6. exactly one generation per condition per checkpoint;
7. mechanical grading and prespecified statistics.

`data/runs_authority_prospective/` must not exist or contain result JSON during
steps 1–4. Discovery notes may record rejected candidates but may never invoke
either model under test. Cases cannot be added, removed, relabeled, or repaired
after the dataset-freeze commit.

## Source and adjudication rules

Every artifact is pinned to a primary-source revision and stores an exact
verbatim excerpt. Every normalized lifecycle status, scope, decision role, and
typed relation must have a source-evidence citation. Recency alone never
establishes ground truth.

Each checkpoint's hidden answer is exactly one of:

- `GOVERNING`: one governing decision ID;
- `MULTIPLE_GOVERNING`: two or more decisions governing explicitly separate
  queried scopes;
- `UNRESOLVED`: visible primary evidence genuinely conflicts or is insufficient
  to establish authority safely; or
- `NO_GOVERNING_DECISION`: sources explicitly establish that no decision in the
  queried scope governs.

Ground truth contains acceptable evidence-artifact sets. An adjudication that
depends on an LLM interpretation of vague prose is marked unresolved or
excluded under a rule recorded before outputs. Queries may name a natural
developer-known subsystem or proposal family, but never an expected decision
ID, expected status, or answer-bearing rationale not naturally part of the
question.

The public artifact envelope may contain only source-derived fields: artifact
and decision identifiers, repository/ecosystem, title, source type, timestamp,
pinned revision and URL, verbatim source text, explicit scope, explicit role,
explicit lifecycle status, and explicit replaces/reverts/implements relations.
All such fields are shown to both conditions. Hidden adjudication and acceptable
evidence sets are available only to the grader.

## Frozen DecisionTrace condition

The prospective runner imports the frozen `adapt_decisions` operation from
`authority_benchmark.py` and `resolve_authority` from `app/authority.py`.
Copying or reimplementing their semantics is forbidden.

For one queried scope, it calls the resolver once. For a developer question
that explicitly names multiple parallel scopes, it calls the same frozen
operation independently once per public `authority_scopes` value and combines
only the returned states and IDs:

- any `UNRESOLVED` result makes the aggregate `UNRESOLVED`;
- otherwise zero unique IDs is `NO_GOVERNING_DECISION`;
- one unique ID is `GOVERNING`;
- more than one unique ID is `MULTIPLE_GOVERNING`.

This generic orchestration is frozen here before cases exist; it introduces no
authority heuristic. Resolver evidence decision IDs are projected to the
latest visible public artifact for the same decision ID. Gemini 3.7 Flash then
receives the state, IDs, resolver explanation, and those source excerpts as
fixed facts and generates one explanation. Governing state/IDs and mechanical
evidence scoring come from deterministic output, not that prose.

DecisionTrace receives no hidden answer IDs, acceptable evidence sets, failure
labels, manually injected target authority, case-specific scope aliases, or
post-hoc hints.

## Strong RAG conditions

Both RAG variants use `gemini-3.7-flash`, the same frozen Vertex helper and
default generation settings as DecisionTrace. They receive titles, natural
timestamps, identifiers, URLs, verbatim excerpts, and all public source-derived
lifecycle/scope/role fields visible to DecisionTrace. Lifecycle words and
rollback artifacts are never removed.

### Embedding RAG

- embedding model: `text-embedding-005`;
- one rendered artifact is chunked at 1,600 characters with 200-character
  overlap, never concatenated across artifact boundaries;
- cosine similarity against the exact developer question;
- top-K: 8 chunks, with stable artifact/chunk order for score ties;
- maximum retrieved text: 12,800 characters plus fixed instructions;
- source identifiers remain attached to every chunk.

### Full-context RAG

All visible artifacts in the timeline are supplied in source order when their
combined rendered text fits 100,000 characters. The dataset gate requires every
checkpoint to fit. This removes retrieval as an excuse and is an intentionally
strong oracle-context baseline.

The **primary strong-RAG comparator** is selected conservatively at aggregate
grading time as whichever frozen RAG variant has higher governing-decision
accuracy; a tie is broken by higher evidence correctness, then in favor of
full-context RAG. The strict gate, paired difference, confidence interval, and
secondary comparisons all use that one selected arm. Both variants are always
reported. This selection rule is frozen before data and is deliberately
favorable to RAG.

Both prompts request only JSON with:

```json
{
  "authority_state": "GOVERNING | MULTIPLE_GOVERNING | UNRESOLVED | NO_GOVERNING_DECISION",
  "governing_decision_ids": ["public decision id"],
  "evidence_artifact_ids": ["public artifact id"],
  "explanation": "brief source-grounded reason"
}
```

The prompt explicitly defines authority as accepted/current organizational
state rather than relevance or recency, warns that proposals, mentions,
implementations, and reverts do not imply policy authority without explicit
evidence, permits uncertainty, and asks for the current answer at the stated
checkpoint. It does not contain hidden adjudication. The exact rendered prompt
template and its hash are frozen in the committed runner before inference.

## Run-once and parsing protocol

Each DecisionTrace explanation, embedding-RAG answer, and full-context-RAG
answer is generated exactly once. Existing output in a condition directory
causes the runner to abort. There are no retries for semantic or formatting
errors; only the already-frozen Vertex transport retry policy applies to 429s
and timeouts. A response parser extracts one JSON object. Missing/malformed
state or IDs is mechanically incorrect and `UNSUPPORTED_AUTHORITY` where
applicable; it is never repaired by another model call.

Run manifests record model names, prompt hashes, public-history hashes,
generation and embedding call counts, errors, start/end times, condition, and
Git SHA. Governing accuracy is graded without an LLM. Explanations are retained
for inspection but do not override structured predictions.

## Prespecified metrics

All proportions report numerator/denominator. Checkpoint accuracy requires an
exact match of authority state and the unordered governing-ID set.

- **Evidence correctness:** the predicted artifact-ID set contains one hidden
  acceptable sufficient evidence set, contains no non-visible ID, and supports
  every asserted governing ID. For unresolved cases it must cite a registered
  conflicting/insufficient-evidence set. Empty evidence is incorrect unless an
  explicitly registered acceptable set is empty.
- **False authority:** a nonempty governing assertion at an unresolved/no-
  governing checkpoint, or any asserted governing ID outside the expected set.
- **Stale decision:** an asserted ID explicitly superseded before checkpoint.
- **Proposal promoted:** an asserted proposed/reconsidered ID before acceptance.
- **Revert miss:** on a revert-eligible checkpoint, failure to return the exact
  post-revert authority state/IDs.
- **Supersession miss:** on a supersession-eligible checkpoint, failure to
  return the exact post-supersession authority state/IDs.
- **Parallel collapse:** on a parallel-eligible checkpoint, suppressing,
  borrowing, or conflating authority across explicit scopes.
- **Unsupported authority:** any positive authority assertion lacking a hidden
  acceptable evidence set, including malformed/unknown citations.
- **Unresolved calibration:** exact accuracy on unresolved checkpoints plus
  abstention precision and recall, where an abstention is `UNRESOLVED`.
- **Consistency:** identical public authority state at repeated unchanged-state
  checkpoints must yield identical structured authority predictions; changes
  in prose do not count.

Failure classes may overlap when one answer commits multiple observable errors.
Rates for named lifecycle misses use their prespecified eligible checkpoint
sets; overall rates use all checkpoints.

Raw binomial rates receive two-sided 95% Wilson score intervals. The paired
DecisionTrace-minus-RAG difference uses a timeline-cluster bootstrap with
100,000 resamples, NumPy generator seed `20260822`, equal-probability sampling
of timelines with replacement, checkpoint-weighted accuracy inside each
resample, and the linear 5th/95th percentiles as the 90% interval. A lower bound
equal to zero fails the strict gate.

## Required breakdowns and forensics

Results are broken down by fully-real/hybrid, ecosystem, every scenario label,
simple/multi-hop, revert, supersession, proposal, parallel scope, and ambiguous
ground truth. Every miss from both systems is classified after scoring with the
taxonomies in the session contract. No corrective intervention follows this
prospective run.

## Leakage, fairness, and validity gates

Before inference automated tests must prove:

1. every protected resolver byte matches the pre-data SHA-256 manifest;
2. public loaders/runners never open or import hidden adjudication;
3. expected IDs/statuses are absent from questions and prompts except when the
   same string occurs naturally in a visible source artifact;
4. RAG receives every visible artifact and public field available to DT;
5. DT receives no hidden adjudication, manual target ID, or unproved relation;
6. every normalized status, scope, role, and relation has visible source proof;
7. prospective decision IDs, source URLs, and histories do not overlap the old
   authority set;
8. result directories were absent at dataset freeze and remain absent until all
   pre-run gates pass;
9. every checkpoint fits the full-context limit; and
10. all existing v0, v2, authority, product, and prospective leakage tests pass.

Failure of a mandatory gate makes the benchmark invalid. It cannot be repaired
after outputs by deleting or replacing cases.

## Kill/continue decision

There is no resolver intervention after this run. The public superiority claim
is killed unless the strict GO gate passes exactly as written. A passing result
permits only a product-integration plan; it does not authorize modifying,
merging, pushing, deploying, or porting code into the frozen product branch.

The benchmark tests organizational authority over explicit decision lifecycle
state. It does not trace downstream derived state or recovery consequences.
