# DecisionTrace Action-Compliance Final Run Protocol V3

## Status and lineage

V1 was invalidated by sparse-checkout patch capture after six usable outputs.
V2 was invalidated after one usable output because independent test discovery
used the host Python instead of task-02's worktree virtualenv. Both attempts,
including all usable and failed material, are preserved and excluded.

V3 is a new freeze with fresh opaque run IDs and a complete pinned worktree for
every run. No V1, V2, Claude pilot, or preflight output is statistical data.

## Scientific package

V3 preserves byte-identically the seven task definitions, requested-change
prompts, raw source bundles, Arm B summaries, Arm C AuthorityProofs,
extractor-v2 outputs, authority resolver, coding system prompt, graders,
sanity patches, GO criteria, bootstrap method, three repetitions, and blind
A/B/C design. The only execution-layer changes are the full-worktree model and
the normalized interpreter/test-command contract.

Arms remain A: complete raw context; B: complete raw context plus the frozen
strong-LLM summary; C: complete raw context plus the frozen AuthorityProof.
Raw A/B/C prefixes remain equal for all seven tasks. The condition map is
private and separate from blind grading input.

## Frozen backend

- CLI: `codex-cli 0.146.1`
- model: `gpt-5.6-luna`
- reasoning effort: `high`
- approval: `never`, explicitly passed as `-a never` to every child
- sandbox: `workspace-write`
- timeout: 600 seconds per coding invocation
- concurrency: 2 initially, never above 3
- plan seed: `2026082401`
- session isolation: fresh `--ephemeral` invocation and fresh worktree per run
- invocation: `codex -a never -c 'model_reasoning_effort="high"' -m gpt-5.6-luna exec --sandbox workspace-write --ephemeral --json --color never <PROMPT>`
- network marker: `CODEX_SANDBOX_NETWORK_DISABLED=1`, identical across arms

No Claude-specific flags, YOLO mode, danger-full-access, MAX reasoning, model
switching, or inherited approval policy is permitted.

## Worktree, test, and capture contract

`scripts/setup_action_compliance_full_worktree.py` creates a fresh shallow
checkout of the exact pinned SHA with the complete repository tree. Sparse
checkout is disabled and no task-specific checkout exception exists. The
runner verifies the SHA and clean `git status --porcelain=v1` before every
model call, and records status before and after the call.

The setup-owned `.decisiontrace_setup_metadata.json` records the normalized
`interpreter`, complete `test_command`, `test_cwd`, and `test_env`. The runner
consumes that command verbatim; it does not substitute pytest, Go, Cargo, or an
ambient Python command heuristically. `TESTS_EXECUTED`, `NO_TESTS_RAN`, and
`TEST_EXECUTION_STATUS` are distinct fields.

Patch capture is exactly:

    git add -A
    git diff --cached --binary --no-ext-diff

This captures tracked edits, deletions, and new files. A capture failure is an
infrastructure failure only when the final full worktree cannot be represented
reliably.

## Schedule, state, and retries

The schedule is exactly `7 tasks x 3 arms x 3 repetitions = 63 runs`.
Randomized order and the separate condition map are frozen before execution.
Each run has an opaque 128-bit ID. Atomic state is checkpointed after every
attempt with `PENDING`, `RUNNING`, `USABLE_COMPLETE`, `INFRA_FAILURE`, or
`INVALID`, plus patch checksum, exit status, usage, wall time, test evidence,
and grading status.

Only objective infrastructure failures with no usable model output may be
retried. Wrong implementations, failing tests, authority violations,
refusals, incomplete patches, no-ops, and bad architectures are outcomes and
are never retried. A deterministic harness defect after the first usable V3
output invalidates V3; it is not repaired and resumed.

## Blind grading and analysis

The grader receives only the opaque run ID, task, pinned worktree, and patch.
It does not receive A/B/C condition, summary, proof label, or expected result.
All usable patches are graded before condition-map unblinding. Outputs and
grading tables are frozen and hashed before analysis.

The primary statistic is the task-level mean across three repetitions, with
paired bootstrap across the seven task clusters. Run-level and task-level
results are both reported. Arm C is compared with the stronger of A and B by
compliant-success rate, tied by lower authority-violation rate.

The existing GO gate is unchanged: at least 10 percentage points compliant-
success advantage; at least 50% relative authority-violation reduction; paired
task-level bootstrap 90% CI strictly above zero; ordinary completion no more
than 5 points worse; test-pass rate no more than 5 points worse; no material
refusal/no-op increase; and advantage across at least 3 authority categories.
No early stopping or futility rule is added.

## Freeze artifacts

- backend: `ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V3.json`
- backend hash: `ACTION_COMPLIANCE_CODEX_BACKEND_V3_SHA256.txt`
- normalized contract: `ACTION_COMPLIANCE_TEST_INTERPRETER_CONTRACT_V3.md`
- manifest: `ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V3_SHA256.txt`
- zero-model dry run: `data/action_compliance/v3_dry_run/`

The V3 manifest is generated after the zero-model dry run and verified with
`sha256sum -c`. No statistical model call is allowed before those gates pass.
