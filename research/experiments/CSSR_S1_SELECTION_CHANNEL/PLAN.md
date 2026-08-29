# CSSR-S1 Execution Plan — Selection Channel and Composite View

**Status:** PLAN ONLY — not implemented, not run

**Lane:** causality/debugging systems

**Authorized artifact:** this `PLAN.md` only

**Frozen specification:**
[`CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md`](../../design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md)

**Specification SHA-256:**
`dd18a84f08fb3330824fed01f2d144c849c6e1af24ecba081d77f224128ce007`

**Freeze record:** [`CSSR_S1_FREEZE.md`](../../design/CSSR_S1_FREEZE.md)

**Freeze commit:** `8ee36360dec9c41591bc69b116dadaa4f5506f02`

This plan adds mechanical serialization and execution order only. It does not
authorize `fixture.json`, `run.py`, `result.json`, `RESULT.md`, an experiment
run, or any production change.

## Preflight stop gate

Before any future implementation, run:

```text
sha256sum research/design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md
```

The output must be exactly:

```text
dd18a84f08fb3330824fed01f2d144c849c6e1af24ecba081d77f224128ce007  research/design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md
```

A mismatch stops the work. Do not update this plan or “repair” the fixture to
match changed prose. Re-review the specification; a material change becomes
`CSSR-S2`.

## Baseline

`FUSED_RECORD` is the safe coarse baseline. One `FREEFORM` invocation receives
`[Q-1, S-A, S-P]`, emits `D-FUSED`, and records all three parents. Activating
`W-P` blocks both `S-P` and `D-FUSED`; no clean output shard survives.

RSM is not a comparator. No LLM-judged independence path is implemented or
rerun.

## Hypothesis

With all roots, timestamps, producer responses, revocation windows, fault
points, reads, and oracle ground truth fixed, switching only from
`FUSED_RECORD` to `CSSR_ISOLATED_SHARDS` will preserve the exact eligible clean
population while blocking every record with revoked support, rejecting forged
or corrupted provenance, and rebuilding the composite view under a new id.

## Single changed variable

```text
materialization_mode = FUSED_RECORD | CSSR_ISOLATED_SHARDS
```

The mode switch includes the treatment's precommitted restricted invocations
and deterministic view projection as one frozen architecture treatment. No
other fixture, policy, timing, producer, fault, or oracle input changes between
comparable arms.

## Implementation boundary for a future authorization

The smallest implementation is one offline, deterministic, standard-library
Python harness under this experiment directory. It must not import or modify
`custody/*.py`, call a network service, invoke an LLM, read production memory,
or use embeddings or semantic classifiers.

The harness has three ownership boundaries:

1. **Harness recorder:** owns append-only producer-context exposure events and
   immutable fixture control inputs. Neither mechanism arm can mutate it.
2. **Mechanism port:** accepts a frozen world plus one
   `materialization_mode`; returns records, envelopes, manifests, states, and
   read decisions. It does not return oracle truth.
3. **Oracle:** consumes fixture truth, recorder events, and mechanism output;
   computes sets, closures, digests, metrics, and verdict without content
   interpretation.

The future implementation is invalid if the candidate mechanism and oracle
share a mutable parent set or if the oracle treats candidate-declared lineage
as exposure ground truth.

## Frozen artifact serialization

### Canonical JSON

Every digestible object uses UTF-8 JSON with:

- lexicographically sorted object keys;
- compact separators `,` and `:`;
- arrays in declared order;
- lowercase hexadecimal SHA-256;
- UTC RFC 3339 timestamps exactly as frozen; and
- no process id, wall clock, random nonce, object address, or retry counter.

`schedule_digest` hashes only:

```text
{
  "dynamic_control_input_ids": [...],
  "fixed_resource_budget_bytes": 1024,
  "ordered_producer_context_ids": [...],
  "transform_revision": "CSSR-SHARD-v1"
}
```

It excludes `job_id` and `schedule_digest` itself.

### Stable replay digest

The stable terminal digest includes sorted records, envelopes, direct edges,
record states, view manifests, revocation generations, publication/read
decisions, and per-record repair outcomes. It excludes only retry counters.

An implementation may record retry counters separately but may not omit any
other field to make replay equality pass.

### Result schema

Any later `result.json` must use schema id `cssr-s1-result-v1` and contain:

```text
schema_id
specification {path, sha256, freeze_commit}
fixture {sha256, synthetic_only}
environment {python_version, network_used, llm_used}
materialization_modes
metric_worlds
job_specs
exposure_events
records
admission_envelopes
direct_edges
view_manifests
revocation_windows
read_decisions
fault_probes
case_results
metrics
verdict
limitations
production_tree_before
production_tree_after
```

`production_tree_before` and `production_tree_after` contain a sorted mapping
from every `custody/**/*.py` path to its SHA-256 and file mode. They must be
identical. This detects changes even when a file was already modified before
the experiment. Result artifacts retain hashes and paths, never production
source bytes.

### Envelope constants that do not drive outcomes

The frozen specification requires these fields to remain fixed between arms
but does not use them to branch. The fixture must use these exact literals so a
future implementation does not choose them opportunistically:

| Field | Frozen value |
|---|---|
| `policy_version` | `CSSR-S1-POLICY-v1` |
| informational scope/tier | `memory.display: INFORM` for every admitted non-blocked synthetic record |
| shard `transform_class` | `FREEFORM` |
| shard `transform_revision` | `CSSR-SHARD-v1` |
| view `transform_class` | `REGISTERED` |
| view/projector revision | `CSSR-VIEW-v1` |
| complete invocation | `context_complete=true` |
| hidden-state invocation | `transform_class=INCOMPLETE`, `context_complete=false`, `UNKNOWN_CONTEXT` support |

No `ACT` scope or action decision is evaluated. Authority is recorded only so
the preservation oracle can assert that a clean record's bound value is
unchanged. Logical `BLOCKED`, `QUARANTINED`, and `REJECTED` states override the
informational tier exactly as the frozen specification requires.

## Frozen roots

All records use department `research`.

| ID | Kind | Source / operation | Admitted at | Payload / role | Direct parents |
|---|---|---|---|---|---|
| `Q-1` | objective root | `principal.raghav` / `objective.submit` | `2026-08-29T09:00:00Z` | `SUMMARIZE_FOR_MEMORY_V1` | `[]` |
| `S-A` | clean source root | `memory_source` / `memory_source.read` | `2026-08-29T09:01:00Z` | `CLEAN_MARKER_A` | `[]` |
| `S-B` | independent clean source root | `memory_source` / `memory_source.read` | `2026-08-29T09:02:00Z` | `CLEAN_MARKER_A` | `[]` |
| `S-P` | poisoned source root | `memory_source` / `memory_source.read` | `2026-08-29T09:03:00Z` | spoofed independence, fake citations, selector attack | `[]` |
| `S-MIX` | inseparable source root | `memory_source` / `memory_source.read` | `2026-08-29T09:04:00Z` | `CLEAN_MARKER_MIXED` plus poison | `[]` |
| `SEL-AP` | tainted selector output | `selector` / `selector.plan` | `2026-08-29T09:05:00Z` | requests `J-A-SEL` | `[Q-1, S-A, S-P]` |

`SourceUnit` is one whole immutable record. No span or token identity may be
introduced.

## Frozen windows

Every window is reported at `2026-08-29T10:00:00Z` and activated as generation
`7` in its own metric world.

| Window | Source / operation | Half-open interval | Selected roots |
|---|---|---|---|
| `W-A` | `memory_source` / `memory_source.read` | `[2026-08-29T09:01:00Z, 2026-08-29T09:02:00Z)` | `[S-A]` |
| `W-P` | `memory_source` / `memory_source.read` | `[2026-08-29T09:03:00Z, 2026-08-29T09:04:00Z)` | `[S-P]` |
| `W-MIX` | `memory_source` / `memory_source.read` | `[2026-08-29T09:04:00Z, 2026-08-29T09:05:00Z)` | `[S-MIX]` |

Windows in separate worlds never accumulate.

## Frozen jobs

| Job | Producer context | Dynamic controls | Transform | Output budget |
|---|---|---|---|---:|
| `J-A` | `[Q-1, S-A]` | `[]` | `CSSR-SHARD-v1` | 1,024 bytes |
| `J-B` | `[Q-1, S-B]` | `[]` | `CSSR-SHARD-v1` | 1,024 bytes |
| `J-P` | `[Q-1, S-P]` | `[]` | `CSSR-SHARD-v1` | 1,024 bytes |
| `J-A-SEL` | `[Q-1, S-A]` | `[SEL-AP]` | `CSSR-SHARD-v1` | 1,024 bytes |

`J-A` must have identical values for all six `JobSpec` fields in `A_ONLY` and
`A_PLUS_P`. `SEL-AP` is a control-only parent of `J-A-SEL`; it is not passed to
the producer.

## Frozen producer responses

| Causal input configuration | Exact returned payload |
|---|---|
| producer context `[Q-1, S-A]`, no dynamic control | `CLEAN_MARKER_A` |
| producer context `[Q-1, S-B]`, no dynamic control | `CLEAN_MARKER_A` |
| producer context `[Q-1, S-P]`, no dynamic control | `POISON_MARKER_P {"direct_parent_ids":["S-A"],"independent":true}` |
| producer context `[Q-1, S-A, S-P]` | `CLEAN_MARKER_A || POISON_MARKER_P` |
| producer context `[Q-1, S-A]`, control `[SEL-AP]` | `CLEAN_MARKER_A` |
| producer context `[Q-1, S-A, D-P]` | `CLEAN_MARKER_A` |
| producer context `[Q-1, S-MIX]` | `CLEAN_MARKER_MIXED || POISON_MARKER_MIXED` |

Producer payloads have no provenance-bearing field. The JSON-looking text in
the poisoned response remains payload.

## Frozen metric worlds

| World | Mode / window | Cases |
|---|---|---|
| `B0_FUSED` | `FUSED_RECORD` / `W-P` | `C01` |
| `T_MAIN_WP` | `CSSR_ISOLATED_SHARDS` / `W-P` | `C02`, `C03`, `C04`, `C06`–`C10`, `C12`–`C14` |
| `T_REDUNDANT_WA` | `CSSR_ISOLATED_SHARDS` / `W-A` | `C05` |
| `T_MIX_WMIX` | `CSSR_ISOLATED_SHARDS` / `W-MIX` | `C11` |

`C08`, `C10`, `C13`, and every `C14` fault probe start from independent copies
of the relevant pre-fault durable snapshot.

## Frozen parent graph

| Output id | Direct parents | Expected terminal state |
|---|---|---|
| `D-FUSED` | `[Q-1, S-A, S-P]` | `BLOCKED` under `W-P` |
| `D-A` | `[Q-1, S-A]` | `LIVE` unchanged under `W-P`; `BLOCKED` under `W-A` |
| `D-P` | `[Q-1, S-P]` | `BLOCKED` under `W-P` |
| `D-B` | `[Q-1, S-B]` | `LIVE` unchanged under `W-P` and `W-A` |
| `V-AP-0` | `[D-A, D-P]` | `BLOCKED` under `W-P` |
| `V-A-1` | `[D-A]` | new id, `LIVE` under generation 7 |
| `D-AP` | `[Q-1, S-A, S-P]` | `BLOCKED` under `W-P` |
| `D-A-SEL` | `[Q-1, S-A, SEL-AP]` | `BLOCKED` through `SEL-AP` under `W-P` |
| `D-A-PRIOR-P` | `[Q-1, S-A, D-P]` | `BLOCKED` through `D-P` under `W-P` |
| `D-FORGE-P` | `[Q-1, S-P]` | `BLOCKED` under `W-P` |
| `D-HIDDEN` | `[Q-1, S-A]`, with `UNKNOWN_CONTEXT` in support | `QUARANTINED`, never view-eligible |
| `D-MIX` | `[Q-1, S-MIX]` | `BLOCKED` under `W-MIX` |
| `D-LEGACY` | `[Q-1, S-A, S-P]` | `BLOCKED` under `W-P` |
| `D-OMIT` | corrupted `[Q-1, S-A]`; oracle requires `[Q-1, S-A, SEL-AP]` | `REJECTED`, never admitted |
| `V-STALE` | `[D-A, D-P]`, planned at generation 6 | `REJECTED` when generation 7 is current |

Parent order is irrelevant to graph closure. The oracle compares membership as
a set; result serialization sorts parent ids lexicographically solely to make
digests reproducible. Parent-array order is not a verdict gate. Ordered shard
ids in `ViewManifest` remain order-sensitive.

## Harness-owned exposure ground truth

Before invoking either mechanism, the harness constructs an immutable expected
causal-input set for every invocation:

```text
oracle_causal_inputs(invocation) =
    recorder_observed_producer_context_ids(invocation)
    union fixture_dynamic_control_input_ids(invocation)
```

The recording proxy appends one `ExposureEvent` for each record delivered
through the producer-context port. The candidate cannot append, delete, or
rewrite events. Dynamic control ids come from the frozen fixture, not from the
candidate envelope.

`C08` forks after this oracle set is sealed, deletes `SEL-AP` only from the
candidate admission representation, and requires rejection. If the candidate
admits `D-OMIT`, both `parent_set_errors` and `missing_control_edges` increment
and the verdict is KILL.

## World setup admissions and invocation mapping

The frozen per-case table names only the records material to each case. Three
frozen facts therefore belong to no numbered case, and a fixture built from the
case table alone would omit them.

1. `T_MAIN_WP` admits `D-B` from precommitted job `J-B` as world setup. The
   frozen derived graph requires `D-B` live and unchanged under `W-P`, and the
   frozen clean-preservation population counts a main-world `D-B` instance, but
   `C02` runs only `J-A` and `J-P` and `C05` runs in `T_REDUNDANT_WA`.
2. `D-A` exists in both `T_MAIN_WP` and `T_REDUNDANT_WA`, and `D-B` exists in
   both as well. Instances are keyed by `(metric_world, record_id)`, so these
   are four separate observations, not two shared records.
3. Records rejected before admission never join a world population. `D-OMIT`
   and `V-STALE` are excluded by rejection, not by closure. `V-STALE`'s parents
   `[D-A, D-P]` do reach `S-P`, so admitting it would make the treatment
   affected set `14` and break a frozen denominator.

Recomputing root closure over the frozen parent table with exactly these
admissions reproduces every frozen denominator: baseline affected `2`,
treatment affected `13`, aggregate `15`, and eligible clean preservation `3`.
Dropping the main-world `D-B` instead yields `eligible_clean_preservation`
`2/3` and a spurious CAUTION verdict, so this is a required serialization
detail rather than an optional one. Nothing here changes a frozen edge, state,
denominator, or gate; it names the admissions the frozen tables already assume.

Each generated output binds to exactly one of the seven frozen producer-context
configurations. No new configuration is introduced.

| Output | Job or invocation | Producer context | Dynamic controls | Note |
|---|---|---|---|---|
| `D-FUSED` | baseline fused invocation | `[Q-1, S-A, S-P]` | `[]` | `FUSED_RECORD` arm only |
| `D-A` | `J-A` | `[Q-1, S-A]` | `[]` | compared across `A_ONLY` and `A_PLUS_P` |
| `D-B` | `J-B` | `[Q-1, S-B]` | `[]` | world setup in `T_MAIN_WP`; case `C05` in `T_REDUNDANT_WA` |
| `D-P` | `J-P` | `[Q-1, S-P]` | `[]` | |
| `D-A-SEL` | `J-A-SEL` | `[Q-1, S-A]` | `[SEL-AP]` | control-only parent, not producer context |
| `D-AP` | joint invocation | `[Q-1, S-A, S-P]` | `[]` | |
| `D-FORGE-P` | forged-payload invocation | `[Q-1, S-P]` | `[]` | distinct id from `D-P`, same frozen response bytes |
| `D-A-PRIOR-P` | prior-output invocation | `[Q-1, S-A, D-P]` | `[]` | |
| `D-HIDDEN` | incomplete-context invocation | `[Q-1, S-A]` | `[]` | `context_complete=false`; `UNKNOWN_CONTEXT` added by the admission gate, never by the producer |
| `D-MIX` | source-unit-limit invocation | `[Q-1, S-MIX]` | `[]` | |
| `D-LEGACY` | pre-CSSR fused record | `[Q-1, S-A, S-P]` | `[]` | admitted as legacy, not produced by a CSSR job |
| `D-OMIT` | `C08` fork of the `J-A-SEL` invocation | `[Q-1, S-A]` | `[SEL-AP]` sealed, then dropped from the candidate admission | rejected, never admitted |

`V-AP-0`, `V-A-1`, and `V-STALE` have no producer invocation. They are
deterministic projector outputs whose support is the union of their referenced
shards.

## Case execution order and expected outcomes

The numeric order is reporting order. Cases that share `T_MAIN_WP` may reuse an
immutable pre-window snapshot; fault cases always fork it.

| Case | Operation | Exact expected outcome |
|---|---|---|
| `C01_BASELINE_FUSED` | materialize `[Q-1, S-A, S-P]` in `FUSED_RECORD`, then activate `W-P` | live generated `{}`; blocked `{S-P, D-FUSED}` |
| `C02_ISOLATED_CLEAN_POISON` | compare `J-A` in `A_ONLY`/`A_PLUS_P`; run `J-A` and `J-P`; activate `W-P` | six-field job drift `0`; live `{D-A}`; blocked `{S-P, D-P}` |
| `C03_COMPOSITE_REBUILD` | publish `V-AP-0`; activate `W-P`; publish generation-7 `V-A-1` | live `{D-A, V-A-1}`; blocked `{S-P, D-P, V-AP-0}`; `D-A` identity/digests unchanged |
| `C04_SPOOFED_PROVENANCE` | admit poisoned response as `D-FORGE-P`; activate `W-P` | live `{}`; blocked `{S-P, D-FORGE-P}`; forged payload ids ignored |
| `C05_REDUNDANT_CLEAN_ROOTS` | admit `D-A` and byte-identical `D-B`; activate `W-A` | live `{D-B}` unchanged; blocked `{S-A, D-A}`; no identity merge |
| `C06_JOINT_INFERENCE` | admit `D-AP`; activate `W-P` | live `{}`; blocked `{S-P, D-AP}`; no surviving subspan |
| `C07_TAINTED_SELECTOR` | admit `SEL-AP`; execute control-only `J-A-SEL`; activate `W-P` | live `{}`; blocked `{S-P, SEL-AP, D-A-SEL}` |
| `C08_CONTROL_EDGE_CORRUPTION` | drop `SEL-AP` from candidate admission after sealing oracle inputs | rejected `{D-OMIT}`; no record or active publication |
| `C09_INDIRECT_PRIOR_OUTPUT` | expose `D-P` as prior state while producing `D-A-PRIOR-P`; activate `W-P` | live `{}`; blocked `{S-P, D-P, D-A-PRIOR-P}` |
| `C10_HIDDEN_PROVIDER_STATE` | mark context enumeration incomplete | quarantined `{D-HIDDEN}` with `UNKNOWN_CONTEXT`; never view-eligible |
| `C11_SINGLE_SOURCE_UNIT_LIMIT` | admit `D-MIX`; activate `W-MIX` | live generated `{}`; blocked `{S-MIX, D-MIX}`; clean-looking subspan not retained |
| `C12_LEGACY_FUSED_LIMIT` | admit legacy `D-LEGACY`; activate `W-P` | live generated `{}`; blocked `{S-P, D-LEGACY}`; no post-hoc split |
| `C13_STALE_VIEW_RACE` | plan `V-STALE` at generation 6; activate `W-P`; attempt publish; rebuild | `V-STALE` rejected; live `{D-A, V-A-1}`; blocked `{S-P, D-P}` |
| `C14_CRASH_AND_RETRY` | stop/replay at every frozen boundary during the `C03` sequence | terminal live `{D-A, V-A-1}`; blocked `{S-P, D-P, V-AP-0}`; stable digest equals no-fault run |

Unlisted unaffected roots remain live. They do not enter generated-memory
marker metrics.

## Crash, retry, and freshness probes

For `C14`, fork the same pre-fault snapshot and stop at each boundary:

1. after `JobSpec` creation, before producer invocation;
2. after producer bytes return, before envelope validation;
3. after envelope durability, before active publication;
4. after shard admission, before view-manifest publication;
5. after generation-7 revocation intent, before descendant cleanup;
6. after `V-STALE` planning at generation 6, after generation 7 activates,
   before publish; and
7. after `V-AP-0` blocks, before `V-A-1` publishes.

For every fork:

- replay the same request twice;
- identical id/fields are a no-op;
- identical id with changed fields is a conflict;
- a record without its envelope is never active;
- affected records are ineffective once generation 7 is active;
- stale manifests are never returned live; and
- the stable terminal digest equals the no-fault digest.

Retry counters may differ and are reported outside the stable digest.

## Frozen metric populations

Record instances are keyed by `(metric_world, record_id)`.

| Metric population | Exact members / denominator |
|---|---|
| Baseline affected | `{S-P, D-FUSED}` / `2` |
| Treatment affected | main `{S-P, SEL-AP, D-P, V-AP-0, D-AP, D-A-SEL, D-A-PRIOR-P, D-FORGE-P, D-LEGACY}` plus redundant `{S-A, D-A}` plus mixed `{S-MIX, D-MIX}` / `13` |
| Aggregate affected (descriptive, not a gate) | baseline `2` plus treatment `13` / `15` |
| Eligible clean preservation | main `{D-A, D-B}` plus redundant-world `{D-B}` / `3` |
| Safe overrevocation | same three clean instances / `3` |
| Independent job drift | six `J-A` fields compared across `A_ONLY` and `A_PLUS_P` |
| Composite rebuild | old `V-AP-0`; new ordered manifest `[D-A]` in `V-A-1` |

Quarantined, rejected, newly created, legacy, and same-source-unit-limit records
do not enter clean-preservation recall.

## Metrics

### Integrity

- `unsafe_live_records`
- `parent_set_errors`
- `missing_control_edges`
- `forged_parent_accepts`
- `same_record_relabels`
- `stale_view_reads`
- `visible_unenveloped_outputs`
- `unsafe_fault_windows`

Every integrity metric must be an exact integer count.

### Selectivity and availability

- baseline and treatment `affected_recall`;
- `eligible_clean_preservation`;
- `composite_rebuild_exact`;
- `independent_job_drift`;
- `baseline_clean_derived_marker_live`;
- `cssr_clean_derived_marker_live`; and
- `safe_overrevocations` with every affected id listed.

Runtime, number of invocations, payload bytes, and record/view amplification are
descriptive costs. They cannot compensate for a failed gate.

## Fixed verdict computation

Apply this precedence without averaging:

1. **KILL** if any integrity metric is nonzero, a fault opens an unsafe read,
   an old record is relabelled/pruned/reused, context is marked complete when
   unenumerated, or the mechanism/oracle needs semantic independence judgment.
2. **SHELVE** if integrity is perfect but both modes lose the clean derived
   marker; CSSR then adds no repair granularity over the baseline.
3. **CAUTION** if integrity is perfect but any other selectivity requirement
   fails.
4. **PASS** only when every gate below holds.

### PASS gates

- every integrity metric equals `0`;
- baseline `affected_recall == 2/2`;
- treatment `affected_recall == 13/13`;
- `eligible_clean_preservation == 3/3`;
- `composite_rebuild_exact == true`;
- `independent_job_drift == 0`;
- `baseline_clean_derived_marker_live == false`;
- `cssr_clean_derived_marker_live == true`;
- `safe_overrevocations == 0/3`;
- `D-OMIT` is rejected;
- `D-MIX` and `D-LEGACY` fail closed exactly as frozen;
- every fault-fork stable digest equals the no-fault digest except retry
  counters; and
- `production_tree_before == production_tree_after` for every
  `custody/**/*.py` path, digest, and mode.

PASS permits only this claim:

> Prospective, structurally isolated derivation shards permit selective
> composite-view repair on the frozen synthetic fixture without semantic
> provenance judgment.

## Result tables

### Aggregate

| Mode | Unsafe live | Parent errors | Control misses | Affected recall | Clean preservation | View rebuild | Job drift | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `FUSED_RECORD` | NOT RUN | NOT RUN | NOT RUN | expected `2/2` | n/a | n/a | n/a | NOT RUN |
| `CSSR_ISOLATED_SHARDS` | NOT RUN | NOT RUN | NOT RUN | expected `13/13` | expected `3/3` | NOT RUN | NOT RUN | NOT RUN |

### Per case

| Case | Expected live | Expected blocked / rejected / quarantined | Observed | Violations | Result |
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
| `C14` | `{D-A, V-A-1}` | blocked `{S-P, D-P, V-AP-0}` | NOT RUN | NOT RUN | NOT RUN |

## Conformance audit against the frozen specification

Performed 2026-08-29, after this plan was drafted and before any fixture
exists. The audit asks one question: does this plan copy the frozen values, or
has it quietly chosen an outcome the specification did not fix?

**Digest.** `sha256sum research/design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md`
recomputed as
`dd18a84f08fb3330824fed01f2d144c849c6e1af24ecba081d77f224128ce007`, equal to
the digest in `CSSR_S1_FREEZE.md`. The preflight stop gate passes.

**Tables compared item by item.** Frozen roots and admission times, the three
windows and their half-open intervals and selected roots, the four job tuples,
the seven producer responses, the four metric worlds and their case
assignments, all fifteen derived-graph rows and their parent sets and required
states, the metric populations, the fourteen cases and their expected
live/blocked/rejected/quarantined sets, the seven fault boundaries, the eight
integrity metrics, the seven selectivity metrics, the PASS gates, and the
verdict precedence. No frozen value is altered by this plan.

**Denominators recomputed, not copied.** Root closure was recomputed
independently over the frozen parent table for all four worlds, outside this
repository and without reading the plan's prose totals. The computation
reproduces the frozen affected sets exactly and yields baseline `2`, treatment
`13`, aggregate `15`, and eligible clean preservation `3`. `D-HIDDEN` is
correctly outside the affected set because its support does not reach `S-P`,
and correctly outside clean preservation because it is quarantined.

**Divergences found and their disposition.**

| Finding | Class | Disposition |
|---|---|---|
| The frozen case table never admits `D-B` in `T_MAIN_WP`, yet the frozen derived graph and clean-preservation population both require that instance | serialization gap, would produce `2/3` and a spurious CAUTION | resolved by the world-setup section above; no frozen value changed |
| The specification's descriptive aggregate denominator `15` was absent from the plan | omission of a descriptive figure | added to the metric-population table, marked not a gate |
| The output-to-producer-context binding for `D-FORGE-P`, `D-AP`, `D-A-PRIOR-P`, `D-HIDDEN`, `D-MIX`, `D-LEGACY`, and `D-OMIT` was inferable but never stated | serialization gap | resolved by the invocation mapping table above |
| The specification renders `eligible_clean_preservation == 1.0` and `safe_overrevocations == 0`; the plan renders them `3/3` and `0/3` | equivalent under the frozen population of `3` | no change; the fraction form is retained because it names the denominator |

Nothing found required a change to a frozen edge, state, visibility decision,
denominator, or verdict, so this plan does not stop and `CSSR-S2` is not
triggered.

**Two verdict-relevant traps a future harness must not fall into.** Both were
identified by the closure recomputation, not by reading prose:

1. Admitting `V-STALE` rather than rejecting it adds a fourteenth affected
   record. The correct treatment recall would then read `13/14`, presenting an
   integrity-adjacent bug as a selectivity shortfall.
2. Omitting the main-world `D-B` reads as `eligible_clean_preservation == 2/3`
   and produces CAUTION from a fixture defect rather than from mechanism
   behavior.

**What this audit does not establish.** It checks the preregistration against
itself. It is not evidence that CSSR works, that a harness will pass, or that
production collectors can observe every data and control input. The
specification's own dominant unresolved risk is unchanged, and the strategic
verdict remains CAUTION.

## Planned implementation sequence — not yet authorized

Each stage requires a new explicit authorization. Do not infer authorization
from this plan.

1. **Fixture authorization:** create only `fixture.json`, mechanically copying
   the frozen roots, windows, jobs, responses, worlds, parents, cases, fault
   points, metric populations, and spec digest.
2. **Harness authorization:** create only `run.py`; validate spec and fixture
   digests before constructing either arm.
3. **Execution authorization:** run the offline harness once, writing only
   `result.json`; an incomplete run has status `RUN_INCOMPLETE` and no strategic
   verdict.
4. **Result-review authorization:** inspect the machine-readable artifact and
   create `RESULT.md` whose claims map to exact JSON fields.

No stage authorizes a `custody/*.py` change, production integration, cloud
call, LLM call, commit, push, or claim expansion.

## Verification commands for future stages

These commands are recorded, not run by this plan:

```text
sha256sum research/design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md
python research/experiments/CSSR_S1_SELECTION_CHANNEL/run.py
sha256sum research/experiments/CSSR_S1_SELECTION_CHANNEL/result.json
```

The future harness must exit nonzero before materialization if the spec digest,
fixture digest, schema id, or synthetic-only assertion fails.

## Artifact lineage

- Frozen spec: `research/design/CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md`,
  SHA-256
  `dd18a84f08fb3330824fed01f2d144c849c6e1af24ecba081d77f224128ce007`.
- Freeze record: `research/design/CSSR_S1_FREEZE.md`.
- Persisted freeze commit:
  `8ee36360dec9c41591bc69b116dadaa4f5506f02`.
- This plan is the only artifact authorized after that commit.
- No result exists.

## DDIA Review

**Verdict:** architecturally unshippable; valid to implement only as the frozen
offline falsifier after further authorization.

**Chosen design:** immutable synthetic records, candidate-independent exposure
events, atomic admission/publication, generation-gated views, and deterministic
replay artifacts.

**Key invariants:** one frozen oracle ground truth; no unenveloped visibility;
latest-generation reads; immutable parents and ids; idempotent duplicates;
conflicting replays fail closed; synthetic data only.

**Rejected alternatives:** candidate-owned oracle traces, semantic attribution,
in-place repair, authoritative fused prose, network/LLM dependencies, and
production code changes.

**Failure modes:** missing control edges, incomplete context, partial admission,
stale view publication, duplicate/conflicting replay, spec drift, fixture drift,
and writes outside the experiment packet.

**Acceptance gates:** the fixed PASS/KILL gates above plus matching pre/post
production status and artifact digests.

**Smallest proof artifact:** after separate authorization, `fixture.json`, one
standard-library `run.py`, and one generated `result.json` covering `C01`–`C14`.

**Unresolved risks:** a fixture PASS cannot prove production-complete context
or control capture, useful decomposition, or acceptable amplification cost.

## Experiment Review

**Verdict:** valid frozen execution plan; implementation and result blocked
pending separate authorization.

**Baseline:** `FUSED_RECORD` safe coarse revocation.

**Hypothesis:** `CSSR_ISOLATED_SHARDS` preserves the frozen clean population
without an unsafe survivor.

**Changed variable:** `materialization_mode` only.

**Metric:** exact structural counts, closures, identities, generations, and
digests.

**Result:** not run.

**Kill/continue decision:** KILL on any integrity failure; SHELVE if CSSR safely
adds no clean preservation; continue only on full PASS.

**Missing evidence:** every execution result and all production external
validity.

## Outcome Ledger

### Decision 1

**Decision:** authorize and freeze the execution plan only; retain staged
authorization for every later artifact.

**Lane:** causality/debugging systems.

**Artifact:** this `PLAN.md`.

**Acceptance gate:** the recorded specification digest matches; all four
worlds, fourteen cases, exact populations, and verdict gates are copied without
semantic judgment or a changed outcome.

**Result:** PLAN CREATED / NOT IMPLEMENTED / NOT RUN.

**Next action:** review this plan, then explicitly authorize `fixture.json`
only if it mechanically matches the frozen tables.

**Kill condition:** spec digest mismatch, new experimental variable, changed
denominator/outcome, candidate-owned oracle truth, or semantic independence
judgment.

**Status:** shipped.

### Decision 2

**Decision:** run the plan review gate before authorizing `fixture.json`, and
resolve findings only where a strictly mechanical addition preserves every
frozen value.

**Lane:** causality/debugging systems.

**Artifact:** the conformance audit section above, plus the world-setup and
invocation-mapping additions it required.

**Acceptance gate:** the specification digest matches; all frozen denominators
reproduce from an independent closure recomputation; every divergence is
recorded with its disposition rather than normalized away.

**Result:** PLAN REVIEWED. Digest matched. Baseline `2`, treatment `13`,
aggregate `15`, and clean preservation `3` reproduced exactly. One
verdict-relevant serialization gap found (`D-B` missing from `T_MAIN_WP`) and
closed mechanically. No frozen value changed; `CSSR-S2` not triggered.

**Next action:** obtain explicit authorization for `fixture.json` only, built
by mechanically copying the frozen tables plus the world-setup admissions, with
its own digest recorded before `run.py` is discussed.

**Kill condition:** a later stage needing to change a denominator, an expected
outcome, or a gate; candidate-owned oracle truth; or any semantic independence
judgment entering the mechanism or the oracle.

**Status:** shipped.
