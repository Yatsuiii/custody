# DecisionTrace Action-Compliance Final Run Protocol V4

## Freeze lineage

V1 was invalidated by sparse-checkout patch capture after six usable outputs.
V2 was invalidated by the test-interpreter contract defect. V3 was invalidated
by a deterministic disk-quota infrastructure failure after 36 usable outputs.
All V1/V2/V3, Claude pilot, and preflight material is excluded. V4 uses a
fresh opaque schedule and contains no reused statistical output.

## Scientific invariants

V4 preserves byte-identically the seven task definitions and prompts, pinned
repository snapshots, raw source bundles, Arm B summaries, Arm C
AuthorityProofs, extractor-v2, authority resolver, coding system prompt,
graders, sanity patches, blind A/B/C construction, three repetitions,
randomized 63-row schedule semantics, bootstrap analysis, and the existing GO
gate. The sole substantive experiment-infrastructure change is the bounded
complete-worktree/storage lifecycle described in
`ACTION_COMPLIANCE_V4_STORAGE_CONTRACT.md`.

## Frozen backend

- CLI: `codex-cli 0.146.1`
- model: `gpt-5.6-luna`
- reasoning effort: `high`
- approval: `never`, explicitly passed as `-a never` to every child
- sandbox: `workspace-write`
- timeout: 600 seconds per coding invocation
- concurrency: 2 workers, never above 3
- plan seed: `2026082402`
- session isolation: fresh `--ephemeral` invocation and fresh full pinned
  worktree per run
- host entry point: `python3 scripts/run_action_compliance_codex_v4.py`, run
  from a normal host shell; it invokes the installed `codex` executable
  directly and never nests a Codex process inside another Codex session
- command: `codex -a never -c 'model_reasoning_effort="high"' -m
  gpt-5.6-luna exec --sandbox workspace-write --ephemeral --json --color
  never <PROMPT>`
- network: the host runner performs DNS/TCP reachability checks to
  `chatgpt.com:443` before the preflight and before every statistical batch;
  coding children inherit the normal host network environment. Dependency
  setup remains identical across arms and uses pinned offline Go/Cargo caches.
- excluded preflight cache: before its single Codex call, the host runner
  prepares the Kubernetes Go module cache with host-enabled `go mod download`,
  then proves the exact frozen test command succeeds with `GOPROXY=off`;
  failure blocks the model call.
- `CODEX_HOME`: inherited from the normal host shell by default. The runner
  does not override it; `--isolate-codex-home` is an explicit opt-in only.

No Claude flags, YOLO/danger-full-access, MAX reasoning, model switching,
condition-specific permissions, or inherited approval policy is permitted.

## Worktree, test, and patch contract

`setup_action_compliance_full_worktree.py` uses a shallow local source cache,
checks out the exact pinned SHA, and exposes the complete repository tree.
Sparse checkout is disabled and there are no task-specific checkout
exceptions. SHA and clean status are verified before each model call.

The setup-owned `.decisiontrace_setup_metadata.json` is the sole source of the
interpreter, complete test command, test cwd, and test environment. The runner
does not infer pytest, Go, Cargo, or host Python commands. `TESTS_EXECUTED`,
`NO_TESTS_RAN`, and `TEST_EXECUTION_STATUS` remain distinct.

Before and after each model run the runner records:

`git status --porcelain=v1`

Patch capture is exactly:

`git add -A`

`git diff --cached --binary --no-ext-diff`

This captures modifications, deletions, and newly created files.

## Schedule, checkpointing, and retry policy

The frozen statistical design is 7 tasks × 3 arms × 3 repetitions = 63 fresh
Codex runs, randomized using seed `2026082402`. The three 21-run rounds are
checkpointing only. The private condition map is separate from blind grading.

After every attempt the runner atomically checkpoints run ID, status, task,
patch checksum, exit status, usable-output flag, usage metadata, wall time,
tool count, test evidence, and grading status. Statuses are `PENDING`,
`RUNNING`, `USABLE_COMPLETE`, `INFRA_FAILURE`, and `INVALID`.

Only objective infrastructure failure with no usable output may be retried.
Wrong code, failing tests, authority violation, refusal, incomplete patch,
no-op, or bad architecture is a statistical result and is never regenerated.

If the disk guard fires, execution pauses before a new model call. If quota
stops the provider, V4 remains valid and resumes only from pending V4 IDs. A
deterministic infrastructure defect requiring a methodological change after
the first usable V4 output invalidates V4; it is not repaired and resumed.

## Blind grading and analysis

The grader receives only opaque run ID, task, pinned worktree, and patch. It
does not receive arm, summary, proof, or expected result. All usable patches
and grading outputs are frozen and hashed before condition-map unblinding.
Run-level and task-level results are reported; the primary statistic is the
task mean over three repetitions with paired bootstrap across seven task
clusters. The existing GO gate is unchanged and no futility rule is added.

## Required artifacts

- backend: `ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V4.json`
- backend hash: `ACTION_COMPLIANCE_CODEX_BACKEND_V4_SHA256.txt`
- host runner: `scripts/run_action_compliance_codex_v4.py`
- storage contract: `ACTION_COMPLIANCE_V4_STORAGE_CONTRACT.md`
- normalized test contract: `ACTION_COMPLIANCE_TEST_INTERPRETER_CONTRACT_V3.md`
- manifest: `ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V4_SHA256.txt`
- model-free storage stress: `data/action_compliance/v4_storage_stress_final9/`
- model-free 63-row orchestration: `data/action_compliance/v4_dry_run_final5/`
- model-free sanity replay: `data/action_compliance/v4_sanity_replay_final/`
- crash/recovery verification: `data/action_compliance/v4_storage_recovery_test.json`
- excluded host preflight: `data/action_compliance/v4_codex_preflight_host_v2/`

The V4 manifest is generated and verified after all zero-model gates. No
statistical model call may precede the final `sha256sum -c` check.
