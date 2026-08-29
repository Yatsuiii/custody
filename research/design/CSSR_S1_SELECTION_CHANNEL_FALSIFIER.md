# CSSR-S1 — Selection-Channel and Composite-View Falsifier

**Status:** frozen v1, reviewed, not implemented, not run

**Freeze date:** 2026-08-29

**Freeze record:** [`CSSR_S1_FREEZE.md`](CSSR_S1_FREEZE.md)

**Strategic verdict:** CAUTION

**Lane:** causality/debugging systems

**Decision owner:** Raghav

**Experiment operator:** unassigned

No experiment directory, harness, fixture, production change, or result is
authorized by this document. This is the preregistration that must exist before
any implementation.

## Decision under test

Claim-Sharded Secure Re-execution (CSSR) is a prospective representation and
execution change. It does not infer which words in an existing fused model
output are independent. Instead, it makes the smallest independently revocable
unit an output from a run whose actual data and dynamic control inputs were
structurally isolated and recorded by Custody.

The experiment asks one question:

> Can Custody preserve an already-admitted clean derivation shard while
> revoking a poisoned sibling and rebuilding their composite view, without
> accepting any model- or tool-declared provenance and without using semantic
> judgment in the safety oracle?

A positive result would justify a bounded prototype of prospective CSSR. It
would not establish retrospective claim-level repair for arbitrary fused prose.

## Evidence state before execution

- **VERIFIED:** RSM's LLM-judged post-hoc independence decision is unsafe under
  spoofed self-declared provenance. The failure repeated in rounds 8, 10, 13,
  14, and with a second model in round 15.
- **VERIFIED:** E2D and EXT1-4 demonstrate structural descendant blocking and
  bounded-interval selectivity on their deterministic fixtures, including
  overlap, legacy-time fallback, and manifest admission.
- **VERIFIED:** the receipt-collector paraphrase falsifier found a fail-closed
  recall gap, not a trusted-looking missing-parent path. Commit `28531eb` on
  `fix/receipt-collector-id-resolution` replaces content-based reconnection
  with ID-based resolution, but does not change repair granularity.
- **PARTIALLY VERIFIED:** Custody can capture actual stored-record inputs in a
  trusted admission envelope. Coverage of every production retrieval,
  server-side transform, ambient input, and dynamic control path is not proven.
- **ASSUMPTION UNDER TEST:** content-oblivious scheduling or complete control-
  dependency capture is enforceable at the transform boundary.
- **UNKNOWN:** whether useful memories can be decomposed into isolated runs
  without unacceptable cost, redundancy, or loss of synthesis quality.

The strongest safe baseline remains current whole-record descendant revocation.
RSM is a rejected comparator, not a baseline to rerun.

## Claim boundary

CSSR-S1 uses `DerivationShard`, not `Claim`, as the stored authority unit. A
model output is not proven to be one semantic claim merely because it is short
or labelled as one. The only guarantee is that the entire shard was produced
under one captured input envelope.

Smaller repair units require smaller pre-generation runs. CSSR-S1 does not
create a token-to-source attribution map, infer entailment, or trust citations
emitted in the payload.

## Baseline

`FUSED_RECORD` is the strongest realistic safe baseline:

1. one `FREEFORM` transform sees clean root `S-A`, poisoned root `S-P`, and
   objective record `Q-1`;
2. its one output `D-FUSED` records all three as direct parents; and
3. revoking `S-P` blocks the whole output.

This baseline is expected to have zero false survivors and zero preservation of
the clean marker embedded in `D-FUSED`. That is safe coarse revocation, not a
failure of the baseline.

## Hypothesis

With roots, objective, transform revision, adversarial producer behavior,
revoked-root set, revocation ordering, and read requests fixed, changing only
the materialization mode from `FUSED_RECORD` to `CSSR_ISOLATED_SHARDS` will:

1. admit clean, poisoned, redundant, and joint outputs under their complete
   actual-input and dynamic-control parent sets;
2. leave every structurally eligible clean shard live with the same record id,
   payload digest, envelope, and bound authority after `S-P` is revoked;
3. block every shard and old composite view whose transitive support includes
   `S-P`;
4. publish a new view containing only live shards, without relabelling or
   pruning any old record in place; and
5. remain correct when producer payloads forge citations, claim independence,
   or attempt to influence scheduling.

## Single changed variable

```text
materialization_mode = FUSED_RECORD | CSSR_ISOLATED_SHARDS
```

This is one architecture switch behind the same experimental port. It changes
the authoritative execution topology as one treatment: mixed-context fused
admission versus precommitted restricted-context shard admissions plus a
deterministic composite view.

The following remain fixed between arms:

- root records, immutable ids, payloads, and admission times;
- objective record and static transform revision;
- producer implementation and its scripted adversarial responses;
- source policy, authority caps, and active revocation generation;
- fault-injection points, queries, and oracle; and
- expected payload markers used for exact-byte utility checks.

The core falsifier uses an adversarial scripted producer, not an LLM. The model
is inside the hostile component for this security claim; arbitrary producer
output is a stronger and more reproducible test than sampling one model. A
later LLM run may measure utility, but cannot rescue a structural failure or
alter this experiment's verdict.

## Threat model

### Adversary controls

- the full payload of `S-P`;
- every byte returned by the producer, including fake record ids, citations,
  support lists, confidence, independence declarations, and claim boundaries;
- attempts to make poisoned content select, suppress, reorder, or rewrite a
  clean-source job;
- repeated, conflicting, delayed, and malformed producer responses; and
- payload equality, paraphrase, redundancy, and indirect multi-hop influence.

### Trusted computing base

- immutable record identity and authoritative admission time;
- the context collector that supplies stored records to an invocation;
- the scheduler that records dynamic control dependencies;
- admission-envelope validation and atomic publication;
- the provenance graph, active revocation generation, and read gate; and
- deterministic view projection; and
- a harness-owned exposure recorder and graph oracle outside both mechanism
  arms.

### Not trusted

- model or tool payloads and metadata returned inside those payloads;
- model-emitted citations or parent ids;
- a planner/selector merely because it describes itself as independent;
- embeddings, attention scores, token probabilities, chain of thought,
  counterfactual model answers, or a second model's semantic judgment; and
- content equality as proof of causal independence.

Static orchestration code, prompt templates, model identifier, and policy are
bound by version/digest in the transform revision. Any dynamic record that can
affect whether or how a run occurs is a parent, even if its text is not copied
into the final prompt.

Training-data influence, provider compromise, and extraction of a fact already
encoded in model weights are outside the revocation claim. A stateful provider
session, ambient file/network access, hidden retrieval, or cross-run cache that
the collector cannot enumerate makes `context_complete=false`, adds
`UNKNOWN_CONTEXT`, and is ineligible to count as a preserved clean shard.

## Proposed structural contract

### 1. Precommit execution units

Before reading untrusted payload bytes, the trusted scheduler creates one
bounded job per frozen input unit. For the primary fixture, `J-A`, `J-P`, and
`J-B` are determined from immutable ids, objective id, transform revision, and
fixed per-job resource limits. A poisoned response cannot cancel, resize, or
rewrite another job.

This is a capability boundary, not a prompt convention. The scheduling port
receives opaque record references and fixed metadata but no operation that can
dereference payload bytes. After the `JobSpec` is sealed and digested, the
context collector resolves its references and binds the invocation to that
digest. Per-job budgets are reserved up front; an earlier job cannot consume a
shared budget and suppress a later clean job.

The independent job tuples are frozen as follows:

| Job | Producer context | Dynamic control inputs | Transform | Output budget |
|---|---|---|---|---:|
| `J-A` | `[Q-1, S-A]` | `[]` | `CSSR-SHARD-v1` | 1,024 bytes |
| `J-B` | `[Q-1, S-B]` | `[]` | `CSSR-SHARD-v1` | 1,024 bytes |
| `J-P` | `[Q-1, S-P]` | `[]` | `CSSR-SHARD-v1` | 1,024 bytes |

`J-A` has the same canonical tuple and digest in the `A_ONLY` world and the
`A_PLUS_P` world. `schedule_digest` hashes the canonical job body—producer
context, dynamic controls, transform revision, and budget—excluding both the
digest field and the frozen literal job id. Job ids do not depend on list
position or a shared counter.

Canonical job bodies use UTF-8 JSON, lexicographically sorted object keys,
compact separators, ordered arrays, and lowercase hexadecimal SHA-256. No
timestamp, process id, random nonce, or world-level list index enters the body.

Content-driven selection is allowed only as an explicitly tainted path: the
selector output is first admitted as a record with all records exposed to the
selector, and every job whose existence or parameters it influences cites that
selector record as a direct parent. This preserves safety but may over-revoke.

The selection-channel job is frozen separately:

| Job | Producer context | Dynamic control inputs | Transform | Output budget |
|---|---|---|---|---:|
| `J-A-SEL` | `[Q-1, S-A]` | `[SEL-AP]` | `CSSR-SHARD-v1` | 1,024 bytes |

`SEL-AP` is not sent as producer context in this case. It affects only whether
the job exists, so retaining it as a parent proves the implicit control channel
rather than ordinary prompt exposure.

### 2. Capture exposure; do not accept attribution

For each output, Custody derives `direct_parent_ids` from the collector's actual
input trace. The producer has no authority-bearing parent field. Strings in its
payload that resemble ids remain payload.

The parent set includes:

- every stored record exposed as data context;
- the objective/query record;
- prior output or session-state records exposed to the producer; and
- every dynamic planner, selector, or budget decision that influenced the
  invocation.

If the trusted trace disagrees with the admission request, CSSR-S1's frozen
policy rejects the output. If the trace is explicitly incomplete, the output
is admitted only to quarantine as `INCOMPLETE` with `UNKNOWN_CONTEXT`; it is
not eligible for an active composite view and never becomes a clean root.

The experiment does not let the treatment certify its own receipt. A
harness-owned recording proxy logs every record supplied through the producer
context port, and the fixture separately declares every control record that
causes a job. Neither mechanism arm can write or edit that log. The oracle
compares the candidate envelope with this external exposure/control record.

### 3. Make each restricted run a separate record

Every restricted invocation produces a new `DerivationShard` with the existing
immutable `AdmissionEnvelope` semantics. If one invocation emits several
textual statements, they share the invocation's full parent set unless they
were produced by separate invocations. CSSR never splits one returned string
and assigns different parents after generation.

### 4. Keep fusion out of authoritative memory

A `ViewManifest` is an ordered list of shard ids plus a deterministic projector
revision. It is distinct from `input_manifest_id`, which only scales an
admission envelope's parent list.

The primary CSSR-S1 projector concatenates labelled shard payloads without an
LLM. A persisted view is a derived record whose support is the union of all
referenced shards. It is a disposable materialized consumer, not the source of
authority. After revocation, the old view stays blocked and a new-id view is
projected from the remaining live shards.

The displayed bytes may look like one document, but that does not make the
document the repair unit. Its manifest and underlying shards remain the only
selective units; the whole rendered document is invalidated and recreated when
any referenced shard blocks.

If a future LLM renderer rewrites several shards into prose, its whole output
inherits every exposed shard. It cannot be treated as independently repairable
without running the same isolation protocol again.

### 5. Replace; never relabel

Revocation never removes a parent, edits a shard, or changes a blocked record
back to live. A replacement shard requires a fresh restricted invocation and a
new id. A replacement view requires a new manifest/view id. Clean shards whose
support is disjoint from the revoked roots remain unchanged.

## Conceptual data model and ownership

This section defines experiment contracts, not a production schema.

```text
SourceUnit(
    record_id, source_id, operation_id, admitted_at, payload_digest
)

JobSpec(
    job_id, ordered_producer_context_ids,
    dynamic_control_input_ids, transform_revision,
    fixed_resource_budget, schedule_digest
)

ExposureEvent(
    event_index, invocation_id, record_id, channel, fixture_case
)

AdmissionEnvelope(
    output_id, invocation_id, direct_parent_ids,
    transform_class, transform_revision, context_complete,
    policy_version, authority
)

ViewManifest(
    view_id, ordered_shard_ids, projector_revision,
    source_revocation_generation
)
```

- The admission store owns record/envelope identity and atomic visibility.
- The scheduler owns `JobSpec` and its actual dynamic-control trace.
- The producer owns payload bytes only.
- The experiment harness owns append-only `ExposureEvent` ground truth and
  does not accept events from the candidate mechanism.
- The authority graph derives support from immutable direct-parent edges.
- The revocation controller owns generations and logical blocking.
- The view projector owns ordering; it does not own lineage or authority.

Parent knowledge has one authority source: the captured input trace committed
through `AdmissionEnvelope`. `JobSpec` and result artifacts may expose that
trace for audit, but cannot maintain a conflicting parent set.

In this document, “active authoritative record” means any root, shard, or
persisted view eligible for active memory or a `ViewManifest`, regardless of
whether its action tier is `INFORM` or `ACT`. Quarantined `INCOMPLETE` records
are not active-authoritative. This experiment protects memory integrity, not
only the action gateway.

## Safety and selectivity properties

Let `R_g` be the root records selected by active revocation generation `g`, and
let `Support(x)` be the transitive root closure of immutable direct-parent
edges.

### Integrity invariant

```text
for every authoritative record x returned LIVE at generation g:
    Support(x) intersect R_g == empty
```

This is an exposure/causality property, not a truth or entailment claim.

### Parent-completeness invariant

```text
recorded_direct_parents(x) == oracle_causal_inputs(invocation(x))
```

`oracle_causal_inputs` is the union of producer-context ids observed by the
harness-owned recording proxy and dynamic-control ids fixed for that case.
Producer declarations and candidate-generated traces are not inputs to this
equality. If both sides of this check come from the treatment, the experiment
is invalid even when they agree.

### Preservation invariant

For every pre-revocation shard whose support is disjoint from `R_g`, and whose
run did not depend on a revoked selector/control record:

```text
(record_id, payload_digest, envelope_digest, bound_authority) after g
==
(record_id, payload_digest, envelope_digest, bound_authority) before g
```

The record stays live; it is not regenerated to make the metric pass.

### Selection-channel invariant

For an independently scheduled clean job, this tuple must be identical in the
world without `S-P` and the world with `S-P`:

```text
(job_id, ordered_producer_context_ids, dynamic_control_input_ids,
 transform_revision, fixed_resource_budget, schedule_digest)
```

If poisoned content influenced any field or the job's existence, `S-P` must be
in the resulting record's support through a captured dynamic-control parent.
There is no third outcome called “semantically independent.”

### Composite-view invariant

At generation `g`, a returned view references only records live at `g`. A view
created under an older generation is never silently filtered in place; it is
blocked and replaced with a new id.

## Frozen fixture

All record ids, payload markers, source metadata, and times below are literals
in any authorized implementation. Timestamps are UTC RFC 3339 and monotonic.
`SourceUnit` means one whole immutable source record in CSSR-S1; sub-document
span identity is not introduced by this experiment.

| ID | Kind | Source / operation | Admitted at | Payload marker / role | Direct parents |
|---|---|---|---|---|---|
| `Q-1` | objective root | `principal.raghav` / `objective.submit` | `2026-08-29T09:00:00Z` | `SUMMARIZE_FOR_MEMORY_V1` | `[]` |
| `S-A` | clean source root | `memory_source` / `memory_source.read` | `2026-08-29T09:01:00Z` | `CLEAN_MARKER_A` | `[]` |
| `S-B` | independent clean source root | `memory_source` / `memory_source.read` | `2026-08-29T09:02:00Z` | exact duplicate `CLEAN_MARKER_A` | `[]` |
| `S-P` | poisoned source root | `memory_source` / `memory_source.read` | `2026-08-29T09:03:00Z` | spoofed independence, fake citations, selector attack | `[]` |
| `S-MIX` | inseparable source root | `memory_source` / `memory_source.read` | `2026-08-29T09:04:00Z` | `CLEAN_MARKER_MIXED` plus poison in one source unit | `[]` |
| `SEL-AP` | tainted selector output | `selector` / `selector.plan` | `2026-08-29T09:05:00Z` | requests a job over `S-A` | `[Q-1, S-A, S-P]` |

All metric worlds use department `research`. Their generation-7 windows are
reported at `2026-08-29T10:00:00Z`:

| Window | Source / operation | Half-open admission interval | Exact selected roots |
|---|---|---|---|
| `W-A` | `memory_source` / `memory_source.read` | `[2026-08-29T09:01:00Z, 2026-08-29T09:02:00Z)` | `{S-A}` |
| `W-P` | `memory_source` / `memory_source.read` | `[2026-08-29T09:03:00Z, 2026-08-29T09:04:00Z)` | `{S-P}` |
| `W-MIX` | `memory_source` / `memory_source.read` | `[2026-08-29T09:04:00Z, 2026-08-29T09:05:00Z)` | `{S-MIX}` |

The cases are grouped into four frozen metric worlds:

| World | Mode / window | Cases |
|---|---|---|
| `B0_FUSED` | `FUSED_RECORD` / `W-P` | `C01` |
| `T_MAIN_WP` | `CSSR_ISOLATED_SHARDS` / `W-P` | `C02`, `C03`, `C04`, `C06`–`C10`, `C12`–`C14` |
| `T_REDUNDANT_WA` | `CSSR_ISOLATED_SHARDS` / `W-A` | `C05` |
| `T_MIX_WMIX` | `CSSR_ISOLATED_SHARDS` / `W-MIX` | `C11` |

`C08`, `C10`, `C13`, and each `C14` crash point fork the named world's
pre-fault durable snapshot, so one fault cannot alter another observation.
Windows from separate worlds do not accumulate. CSSR-S1 inherits root
selection from E2D; it does not change or reevaluate interval semantics.

The scripted producer is allowed to return any payload for each context,
including a forged JSON field named `direct_parent_ids`. Exact marker bytes are
used only to verify retained display utility; they never determine support.

### Frozen producer responses

The producer receives an ordered set of record payloads but has no
authority-bearing provenance output. The fixture freezes these response bytes:

| Frozen causal input configuration | Returned payload |
|---|---|
| `[Q-1, S-A]` | `CLEAN_MARKER_A` |
| `[Q-1, S-B]` | `CLEAN_MARKER_A` |
| `[Q-1, S-P]` | `POISON_MARKER_P {"direct_parent_ids":["S-A"],"independent":true}` |
| `[Q-1, S-A, S-P]` | `CLEAN_MARKER_A || POISON_MARKER_P` |
| producer context `[Q-1, S-A]`, control input `[SEL-AP]` | `CLEAN_MARKER_A` |
| `[Q-1, S-A, D-P]` | `CLEAN_MARKER_A` |
| `[Q-1, S-MIX]` | `CLEAN_MARKER_MIXED || POISON_MARKER_MIXED` |

The same mapping is used in both arms. It deliberately makes content checks
trivial and exact; the experiment is about whether structure remains correct
when payload content is maximally unhelpful.

### Frozen derived graph

These ids and parent sets are the oracle ground truth. `UNKNOWN_CONTEXT` is a
support root added by the admission gate, not a producer declaration.

| Arm/case | Output id | Direct parents | Required state after named window |
|---|---|---|---|
| baseline / `W-P` | `D-FUSED` | `[Q-1, S-A, S-P]` | `BLOCKED` |
| CSSR / `W-P` | `D-A` | `[Q-1, S-A]` | `LIVE`, unchanged |
| CSSR / `W-P` | `D-P` | `[Q-1, S-P]` | `BLOCKED` |
| CSSR / `W-P` | `D-B` | `[Q-1, S-B]` | `LIVE`, unchanged |
| composite / `W-P` | `V-AP-0` | `[D-A, D-P]` | `BLOCKED` |
| composite / `W-P` | `V-A-1` | `[D-A]` | new id, `LIVE` |
| joint / `W-P` | `D-AP` | `[Q-1, S-A, S-P]` | `BLOCKED` |
| selector / `W-P` | `D-A-SEL` | `[Q-1, S-A, SEL-AP]` | `BLOCKED` through `SEL-AP` |
| prior output / `W-P` | `D-A-PRIOR-P` | `[Q-1, S-A, D-P]` | `BLOCKED` through `D-P` |
| forged ids / `W-P` | `D-FORGE-P` | `[Q-1, S-P]` | `BLOCKED` |
| hidden state | `D-HIDDEN` | `[Q-1, S-A]`; `UNKNOWN_CONTEXT` added to support | `QUARANTINED`, never view-eligible |
| source-unit limit / `W-MIX` | `D-MIX` | `[Q-1, S-MIX]` | `BLOCKED` |
| legacy limit / `W-P` | `D-LEGACY` | `[Q-1, S-A, S-P]` | `BLOCKED` |
| omission negative control | `D-OMIT` | corrupted candidate `[Q-1, S-A]`; sealed oracle set `[Q-1, S-A, SEL-AP]` | `REJECTED`, id not admitted |
| stale-view race / `W-P` | `V-STALE` | `[D-A, D-P]`, planned at generation 6 | `REJECTED` at generation-7 publish |

In the redundant-evidence case under `W-A`, `D-A` blocks and `D-B` stays live
unchanged. Exact payload equality does not merge their identities or support.

### Frozen metric populations

Record instances are keyed by `(metric_world, record_id)`; identical ids in
separate worlds are separate observations.

- Baseline `W-P` affected set: `{S-P, D-FUSED}` (`2` expected blocks).
- Main CSSR `W-P` affected set:
  `{S-P, SEL-AP, D-P, V-AP-0, D-AP, D-A-SEL, D-A-PRIOR-P,
  D-FORGE-P, D-LEGACY}` (`9` expected blocks).
- Redundant `W-A` affected set: `{S-A, D-A}` (`2` expected blocks).
- Source-unit-limit `W-MIX` affected set: `{S-MIX, D-MIX}` (`2`
  expected blocks).
- `affected_recall` denominators: baseline `2`, CSSR treatment `13`, aggregate
  `15` metric-world record instances. Both mode-specific recalls are gates;
  the aggregate is descriptive.
- `eligible_clean_preservation` population: main `W-P` instances `{D-A,
  D-B}` plus redundant `W-A` instance `{D-B}` (`3` expected unchanged live
  shards).
- `safe_overrevocations` population: the same three eligible instances.
- `independent_job_drift` compares the six frozen `J-A` fields in `A_ONLY`
  and `A_PLUS_P`; the expected changed-field count is `0`.
- `composite_rebuild_exact` requires old view `V-AP-0` blocked and new view
  `V-A-1` live with ordered shard ids exactly `[D-A]` at generation 7.

Quarantined, rejected, newly created, legacy, and same-source-unit-limit
records never enter the clean-preservation denominator.

## Required cases and deterministic oracle

No case asks a model, embedding system, or human reviewer whether two claims
are independent. Expected sets are computed from fixed ids and graph closure.

| Case | Stimulus | Required outcome |
|---|---|---|
| `C01_BASELINE_FUSED` | Baseline runs once over `[Q-1, S-A, S-P]` | `D-FUSED` has all three parents; `W-P` blocks it; no bytes are sliced or relabelled |
| `C02_ISOLATED_CLEAN_POISON` | compare `J-A` in `A_ONLY` and `A_PLUS_P`, then run fixed jobs over `S-A` and `S-P` | all six `J-A` fields are identical; `D-A` parents `[Q-1, S-A]`; `D-P` parents `[Q-1, S-P]`; of those two outputs only `D-A` survives `W-P` unchanged |
| `C03_COMPOSITE_REBUILD` | `V-AP-0` references `D-A` and `D-P`; then `W-P` activates | `V-AP-0` blocks; new `V-A-1` references only `D-A`; `D-A` retains its old id and digest |
| `C04_SPOOFED_PROVENANCE` | producer over `S-P` emits fake clean ids and independence claims | payload strings do not alter the collector parent set; output blocks under `W-P` |
| `C05_REDUNDANT_CLEAN_ROOTS` | `S-A` and `S-B` emit byte-identical markers in separate jobs; `W-A` activates | `D-A` blocks and `D-B` survives unchanged; records are not semantically deduplicated |
| `C06_JOINT_INFERENCE` | fixed joint job sees `[Q-1, S-A, S-P]` | its whole output records all inputs and blocks under `W-P`; no subspan survives |
| `C07_TAINTED_SELECTOR` | `SEL-AP` causes a job over `S-A` | output includes `SEL-AP` as a direct parent; closure reaches `S-P`; output blocks |
| `C08_CONTROL_EDGE_CORRUPTION` | fault injector removes `SEL-AP` after the harness seals the causal-input trace but before candidate admission | validator/oracle mismatch rejects `D-OMIT`; no record with that id is admitted or published |
| `C09_INDIRECT_PRIOR_OUTPUT` | an `S-A` job also consumes `D-P` as prior/session state | output cites `D-P`; closure reaches `S-P`; output blocks |
| `C10_HIDDEN_PROVIDER_STATE` | provider reports or instrumentation detects unenumerated ambient state | `context_complete=false`; `D-HIDDEN` is quarantined with `UNKNOWN_CONTEXT` and is never view-eligible |
| `C11_SINGLE_SOURCE_UNIT_LIMIT` | one shard is derived from `S-MIX`; `W-MIX` activates | entire shard blocks; CSSR does not claim to retain `CLEAN_MARKER_MIXED` |
| `C12_LEGACY_FUSED_LIMIT` | a pre-CSSR fused record cites `S-A` and `S-P` | entire record blocks; no post-hoc split, relabel, or claim-level recovery occurs |
| `C13_STALE_VIEW_RACE` | `W-P` activates after `V-STALE` planning at generation 6 but before publication/read | `V-STALE` is rejected; the generation-7 rebuild publishes `V-A-1`; no old-generation view is returned live |
| `C14_CRASH_AND_RETRY` | stop at each frozen atomicity boundary, then replay | no output becomes visible without its envelope; no blocked item reopens; final state matches no-fault state except retry counters |

### Oracle operations

The future oracle is limited to deterministic operations over captured events:

1. exact set equality between instrumented inputs and envelope parents;
2. transitive graph closure from direct-parent ids;
3. exact intersection with `{S-A}`, `{S-P}`, or `{S-MIX}` as fixed for the
   case world;
4. state and generation comparisons;
5. exact record, envelope, schedule, and payload digests;
6. exact membership of view manifests; and
7. equality of no-fault and replayed terminal artifacts after removing retry
   counters.

An intentionally corrupted candidate admission with a missing control edge is
the negative control: validation and the external oracle must reject it. The
baseline fused arm is the positive safety control: it must block the whole
fused record.

## Atomicity, freshness, and replay probes

An authorized implementation must stage records invisibly and expose them only
through one atomic admission or an equivalent durable-record-first active
pointer. Probe these boundaries:

1. after `JobSpec` creation, before producer invocation;
2. after producer bytes arrive, before envelope validation;
3. after envelope durability, before active-memory publication;
4. after shard admission, before view-manifest publication;
5. after revocation intent advances the generation, before descendant cleanup;
6. after a view is planned at generation 6, while generation 7 activates; and
7. after the old view blocks, before the replacement view publishes.

Required behavior:

- an output without a durable valid envelope is never active;
- an admission racing an active window is born blocked when its support
  intersects the window;
- a view publish performs a generation compare-and-publish and cannot expose a
  stale manifest as live;
- duplicate requests with identical ids and fields are no-ops;
- the same id with different fields is a conflict and fails closed; and
- a crash may reduce availability but cannot create an unsafe survivor.

The result digest excludes retry counters but includes all ids, envelopes,
edges, states, generation numbers, manifests, and read decisions.

## Artifact schema, privacy, and evolution

- All CSSR-S1 inputs are synthetic literals from this specification. Production
  memory, credentials, network responses, and user content are forbidden.
- The machine-readable artifact schema id is `cssr-s1-result-v1`. Unknown
  schema ids fail validation; a harness may not silently reinterpret them.
- Exposure events retain record ids, invocation ids, channel, ordering, and
  case id. They do not duplicate payload bytes. Payload markers live once in
  the fixture and are referenced by digest in results.
- The result artifact is evidence, not an authority store. Replaying it cannot
  admit or unblock a Custody record.
- There is no backfill or mixed-version path in S1. A schema, fixture, or oracle
  change invalidates the frozen digest and requires a reviewed successor.

## Metrics

### Integrity metrics

- `unsafe_live_records`: live authoritative records whose support intersects
  the active revoked-root set.
- `parent_set_errors`: admitted records whose envelope parent set differs from
  the trusted actual-input trace.
- `missing_control_edges`: causally influential dynamic selectors or prior
  state absent from the admitted parent set.
- `forged_parent_accepts`: producer-declared parent changes accepted as
  authority-bearing provenance.
- `same_record_relabels`: affected records made live or given pruned support
  without a new id and fresh execution.
- `stale_view_reads`: views returned live against a later active generation.
- `visible_unenveloped_outputs`: active outputs lacking a durable valid
  envelope.
- `unsafe_fault_windows`: crash points where an affected record or view is
  returned live.

### Selectivity and availability metrics

- `affected_recall`: expected affected records blocked / all expected affected
  records.
- `eligible_clean_preservation`: pre-existing, structurally disjoint clean
  shards retained with identical identity and digests / all eligible clean
  shards.
- `composite_rebuild_exact`: whether `V-AP-0` blocks and `V-A-1` contains
  exactly the expected surviving shard ids.
- `independent_job_drift`: changed fields in the frozen clean `JobSpec` between
  the world without `S-P` and the world with `S-P`.
- `baseline_clean_derived_marker_live`: whether `CLEAN_MARKER_A` remains in any
  live generated memory record or view in the baseline arm after `W-P`; source
  roots are excluded.
- `cssr_clean_derived_marker_live`: the same exact-byte check for the CSSR arm;
  source roots are excluded.
- `safe_overrevocations`: structurally disjoint records blocked despite no
  revoked support. Report every id; do not average this into integrity.

Semantic correctness, fluency, model agreement, and factual entailment are not
metrics in CSSR-S1. Runtime, token count, and storage amplification are recorded
as descriptive costs only.

## Fixed verdict gates

### PASS / continue to a bounded prototype

All are required:

- every integrity metric is `0`;
- baseline `affected_recall == 2/2` and treatment
  `affected_recall == 13/13`;
- `eligible_clean_preservation == 1.0`;
- `composite_rebuild_exact == true`;
- `independent_job_drift == 0`;
- `baseline_clean_derived_marker_live == false`;
- `cssr_clean_derived_marker_live == true`;
- `safe_overrevocations == 0` for the precommitted independent jobs;
- `C08_CONTROL_EDGE_CORRUPTION` is rejected exactly as specified;
- `C11_SINGLE_SOURCE_UNIT_LIMIT` and `C12_LEGACY_FUSED_LIMIT` fail closed
  exactly as specified; and
- all no-fault/replay artifact digests match except retry counters; and
- the experiment changes no `custody/*.py` file.

PASS supports only this statement:

> Prospective, structurally isolated derivation shards permit selective
> composite-view repair on the frozen fixture without semantic provenance
> judgment.

### CAUTION / redesign before further investment

Integrity remains perfect, but any selectivity gate fails. Examples include a
clean independent job drifting because of shared budget, a clean shard being
over-blocked, or the view failing to rebuild deterministically. This means CSSR
is safe but has not improved on whole-record revocation for the target case.

No utility score can turn CAUTION into PASS.

### KILL

Any one condition kills CSSR in its current architectural form:

- a live record or view has revoked support;
- a dynamic selector/control influence is missing from lineage;
- producer-emitted ids, citations, or independence claims alter authority;
- a stale generation or crash/retry opens a live-read window;
- repair prunes parents, relabels an old record, or reuses an old id;
- PASS requires an LLM, embedding model, or human to decide independence; or
- the implementation cannot enumerate actual inputs yet marks context
  complete.

If integrity passes but both arms lose the clean marker, the result is SHELVE,
not PASS: CSSR added complexity without improving repair granularity.

This document is immutable after the freeze record is issued. Any byte change
invalidates its recorded digest and requires re-review. A material change to a
fixture, oracle, threshold, threat model, or mechanism contract creates
`CSSR-S2`; it does not amend CSSR-S1 after seeing results.

## Result tables to populate after authorization

### Aggregate

| Mode | Unsafe live | Parent errors | Control misses | Affected recall | Clean preservation | View rebuild | Job drift | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `FUSED_RECORD` | NOT RUN | NOT RUN | NOT RUN | NOT RUN | n/a (no isolated shard) | n/a | n/a | NOT RUN |
| `CSSR_ISOLATED_SHARDS` | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

### Per case

Unlisted unaffected roots remain live. The table names every generated record
and every targeted root material to the case.

| Case | Expected live ids | Expected blocked / rejected / quarantined ids | Observed | Violations | Result |
|---|---|---|---|---:|---|
| `C01` | `{}` | blocked `{S-P, D-FUSED}` | NOT RUN | NOT RUN | NOT RUN |
| `C02` | `{D-A}` | blocked `{S-P, D-P}` | NOT RUN | NOT RUN | NOT RUN |
| `C03` | `{D-A, V-A-1}` | blocked `{S-P, D-P, V-AP-0}` | NOT RUN | NOT RUN | NOT RUN |
| `C04` | `{}` | blocked `{S-P, D-FORGE-P}` | NOT RUN | NOT RUN | NOT RUN |
| `C05` | `{D-B}` | blocked `{S-A, D-A}` | NOT RUN | NOT RUN | NOT RUN |
| `C06` | `{}` | blocked `{S-P, D-AP}` | NOT RUN | NOT RUN | NOT RUN |
| `C07` | `{}` | blocked `{S-P, SEL-AP, D-A-SEL}` | NOT RUN | NOT RUN | NOT RUN |
| `C08` | `{}` | rejected `{D-OMIT}` | NOT RUN | NOT RUN | NOT RUN |
| `C09` | `{}` | blocked `{S-P, D-P, D-A-PRIOR-P}` | NOT RUN | NOT RUN | NOT RUN |
| `C10` | `{}` | quarantined `{D-HIDDEN}` | NOT RUN | NOT RUN | NOT RUN |
| `C11` | `{}` | blocked `{S-MIX, D-MIX}` | NOT RUN | NOT RUN | NOT RUN |
| `C12` | `{}` | blocked `{S-P, D-LEGACY}` | NOT RUN | NOT RUN | NOT RUN |
| `C13` | `{D-A, V-A-1}` | blocked `{S-P, D-P}`; rejected `{V-STALE}` | NOT RUN | NOT RUN | NOT RUN |
| `C14` | `{D-A, V-A-1}` | blocked `{S-P, D-P, V-AP-0}`; no unenveloped or reopened id | NOT RUN | NOT RUN | NOT RUN |

The execution plan must copy these expectations and the frozen parent table; it
may add serialization details but may not select new outcomes.

## Explicit non-goals and claim limits

CSSR-S1 does not test or claim:

- surgical repair of arbitrary pre-existing fused prose;
- safe separation of clean and poisoned text inside one `SourceUnit`;
- token-level, sentence-level, or semantic entailment provenance;
- truth, factuality, hallucination detection, or action-authority elevation;
- semantic deduplication or alternative-support/OR provenance;
- model-weight unlearning or removal of knowledge encoded during training;
- production performance, cost acceptability, or optimal source chunking;
- safe use of opaque stateful model sessions; or
- production completeness of every Custody context collector.

If the product requirement remains “repair any already-fused LLM memory after
the fact,” CSSR-S1 is not a solution and the honest verdict remains that a safe
mechanism has not been found.

## Prior-work basis, not a novelty claim

CSSR borrows a structural pattern rather than claiming a new scientific result:

- permissive information-flow control for LLM applications uses heuristic
  context selection only to choose a restricted rerun; safety labels come from
  what that rerun could actually access, not from the heuristic's semantic
  correctness: <https://arxiv.org/html/2410.03055>;
- ATMS and database provenance motivate immutable dependency environments and
  deterministic retraction, while also showing that missing dependencies are
  fatal to exact repair: <https://www.dekleer.org/Publications/An%20Assumption-Based%20TMS.pdf>
  and <https://doi.org/10.1145/1265530.1265535>;
- SISA-style unlearning motivates isolating contributions before expensive
  recomputation rather than estimating influence after fusion:
  <https://arxiv.org/html/1912.03817>.

These analogies do not prove CSSR. The unverified step is whether Custody can
enforce complete data and control exposure at a useful granularity.

## Artifact lineage

- Open problem and current claim boundary: [`RESEARCH.md`](../../RESEARCH.md).
- RSM verdict: [`RSM_CRUX_SERIES_SUMMARY.md`](../experiments/RSM_CRUX_SERIES_SUMMARY.md).
- Structural transformation contract: [`TRANSFORMATION_MODEL.md`](TRANSFORMATION_MODEL.md).
- Replacement-only semantics: [`REPAIR_SEMANTICS.md`](REPAIR_SEMANTICS.md).
- Generation and race semantics: [`DYNAMIC_TRUST_MODEL.md`](DYNAMIC_TRUST_MODEL.md).
- Authority algebra: [`AUTHORITY_MODEL.md`](AUTHORITY_MODEL.md).
- E2D baseline artifacts: [`E2D_DESIGN_FALSIFIER`](../experiments/E2D_DESIGN_FALSIFIER/)
  and `E2D_EXT1` through `E2D_EXT4`.
- Receipt paraphrase evidence: commit `82c991e`, path
  `research/experiments/RECEIPT_COLLECTOR_PARAPHRASE_FALSIFIER/RESULT.md`.
- ID-resolution fix: commit `28531eb` on
  `fix/receipt-collector-id-resolution` (pushed, not merged when specified).

If implementation is later authorized, it must create a new, isolated
experiment packet only after an execution `PLAN.md` expands the frozen ids:

```text
research/experiments/CSSR_S1_SELECTION_CHANNEL/
    PLAN.md
    fixture.json
    run.py
    result.json
    RESULT.md
```

`result.json` must record schema id `cssr-s1-result-v1`, the spec digest, source
commit, fixture digest, mechanism mode, harness-owned exposure trace, every
envelope and edge, revocation generation, read decisions, per-case metrics,
fault snapshots, and final verdict. `RESULT.md` may summarize only fields
present in that artifact.

The next authorized command would be creation of the execution `PLAN.md`, not
production code. No such command is authorized by this specification alone.

## DDIA Review

**Verdict:** risky; valid to falsify, architecturally unshippable until the
input/control completeness and generation-race gates pass.

**Chosen design:** immutable restricted-run records, actual-input receipts
checked against an independent exposure recorder, replacement-only composite
views, and revocation-generation-gated reads.

**Key invariants:** one authority source for parent edges; envelope and record
visibility are atomic; active reads use the latest generation; retries are
idempotent; historical edges and ids never change; dynamic control influence
is treated as lineage.

**Rejected alternatives:** post-hoc LLM attribution, model-emitted citations,
attention/embedding scores, in-place support pruning, semantic deduplication,
and authoritative fused prose.

**Dominant failure modes:** hidden context, tainted selection without a control
edge, shared-budget interference, stale view publication, partial admission,
and treating source-unit granularity as token-level provenance.

**Acceptance gates:** the PASS gates above, including all crash/race probes and
zero parent/control misses.

**Smallest proof artifact:** one deterministic two-arm harness covering
`C01`–`C14`, with a machine-readable harness-owned exposure trace and result
digest. No cloud service or LLM is required.

**Unresolved risks:** production collectors may not observe every provider-side
input; practical scheduling may be content-dependent; source units may remain
too coarse; and shard/view amplification may erase the utility advantage.

## Experiment Review

**Verdict:** valid and frozen preregistration; execution blocked pending
explicit authorization.

**Baseline:** current safe fused-record revocation.

**Hypothesis:** prospective isolated shards improve clean preservation while
maintaining zero unsafe survivors under adversarial producer behavior.

**Changed variable:** `materialization_mode` only.

**Metric:** deterministic graph, envelope, generation, digest, and visibility
checks defined above.

**Result:** not run.

**Kill/continue decision:** continue only to the isolated falsifier after
authorization. Any KILL condition ends this CSSR architecture; safe failure to
preserve clean shards shelves it as no better than the baseline.

**Missing evidence:** every treatment result, production-complete context and
control capture, practical decomposition quality, runtime/storage cost, and any
external-validity test.
