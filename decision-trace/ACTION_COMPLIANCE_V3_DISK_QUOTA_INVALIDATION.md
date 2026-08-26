# Action-Compliance V3 Invalidation — Deterministic Task-06 Setup Failure

Date: 2026-08-24

V3 is invalidated and must not be analyzed.

The V3 statistical runner was stopped after 36 fresh Codex outputs had been
produced. Those outputs, and every failed attempt from the same execution, are
excluded from the final dataset. No V1, V2, Claude, or partial V3 output may be
joined, graded as final data, bootstrapped, or used for the primary analysis.

## Evidence preserved

The complete partial execution remains under:

`data/action_compliance/codex_runs_v3/`

The V3 protocol and manifest remain unchanged. The run state, opaque IDs,
condition map, prompts, worktree logs, Codex logs, patches, and failure rows
are preserved in place.

At invalidation:

- usable V3 outputs: 36
- final infrastructure-failure rows: 2
- failed task-06 setup attempts: 6 total (3 attempts for each affected row)
- rows with model output: none for the failed task-06 rows
- pending rows: 25
- interrupted active rows: the two task-06 rows above
- statistical outputs retained for analysis: 0

Affected opaque run IDs:

- `93bd91b605c643b05f0e9c6ac433ed47`
- `fd9ff064bad02192d5aa14e272e265c0`

Affected task:

- `task-06-opentofu-static-source-scope`

## Exact defect

The generic full-worktree setup helper ran the already-frozen task-06
dependency preflight (`go mod download`, followed by a compile-only Go test).
Both concurrent task-06 rows repeatedly failed while Go was writing build or
vet artifacts:

`disk quota exceeded`

The error occurred before any Codex invocation and before any model output.
It reproduced across both opaque rows and all three setup attempts per row.
The host filesystem still reported free space; the failure was the effective
quota imposed on the setup/build environment, not a benchmark-task result.

## Why execution cannot continue

V3 already has usable comparative outputs. Repairing this condition would
require changing the frozen execution infrastructure, such as concurrency,
Go cache placement, dependency-preflight behavior, or worktree setup rules.
That would violate the post-first-output freeze. Continuing with other rows
would also leave the planned 63-row experiment incomplete while silently
conditioning execution on task-specific infrastructure availability.

Therefore this is a deterministic infrastructure invalidation, not a model
outcome and not a quota-resumable V3 checkpoint.

## Required disposition

- Mark all V3 material as `HARNESS EXECUTION FROM INVALIDATED FREEZE — EXCLUDED`.
- Do not grade or analyze the 36 usable outputs.
- Do not reuse any V3 run IDs or condition map for a replacement experiment.
- Preserve this record and create a new versioned freeze before any restart.
