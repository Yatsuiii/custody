# DecisionTrace Action-Compliance Final Run Protocol V6

## Freeze lineage and scope

V1 was invalidated by sparse-checkout patch capture. V2 was invalidated by the
test-interpreter defect. V3 was invalidated by disk-quota infrastructure
failure after 36 usable outputs. V4 was invalidated by deterministic
test-contract/grader interpretation defects after 63 captured outputs. All
Claude, V1, V2, V3, and V4 outputs are excluded permanently.

V5 was model-free only and is superseded by this freeze. V6 uses fresh opaque
run IDs. It preserves the seven task definitions and
prompts, pinned repository SHAs, raw A/B/C contexts, Arm B summaries, Arm C
AuthorityProofs, extractor-v2, authority resolver, semantic graders, sanity
patches, three repetitions, randomized 63-row design, blind grading, paired
task-level bootstrap, and the preregistered GO gate.

The only substantive changes are generic execution infrastructure:

- complete non-sparse pinned worktrees;
- bounded shared-cache/disposable-slot storage; and
- the versioned test/interpreter/grader contract in
  `ACTION_COMPLIANCE_TEST_INTERPRETER_CONTRACT_V6.md`.

`ACTION_COMPLIANCE_V5_FREEZE_SUPERSESSION.md` records the exclusion of all V5
artifacts from the V6 statistical dataset.

## Backend freeze

- Codex CLI: `codex-cli 0.149.0`, rechecked by the host shell immediately
  before preflight;
- model: `gpt-5.6-luna`;
- reasoning effort: `high`;
- approval policy: `never`, explicitly passed as `-a never` to every child;
- sandbox: `workspace-write`;
- timeout: 600 seconds per coding invocation;
- concurrency: two workers, never above three;
- session isolation: fresh `--ephemeral` invocation and fresh full pinned
  worktree per run;
- host runner: `scripts/run_action_compliance_codex_v6.py`, executed from a
  normal host shell and never nested inside another Codex process.

Every child command is assembled as:

```text
codex -a never -c 'model_reasoning_effort="high"' -m gpt-5.6-luna exec --sandbox workspace-write --ephemeral --json --color never <PROMPT>
```

`CODEX_HOME` is inherited from the host by default. The runner performs a DNS
and TCP provider check before preflight and before every statistical batch.
Task dependency commands use the frozen offline caches; all arms share the
same cache policy.

## Worktree, contract, and capture

`scripts/setup_action_compliance_full_worktree.py` checks out each exact pinned
SHA into a complete tree, rejects sparse checkout, prepares dependencies, and
writes `.decisiontrace_setup_metadata.json`. The metadata's interpreter,
argv-list test command, cwd, environment, and observation mode are consumed
verbatim by both independent verification and the blind grader.

The normalized statuses are `executed_with_tests`, `executed_zero_tests`,
`test_build_failed`, `test_collection_failed`, `test_command_error`,
`test_timeout`, and `unknown`. `NO_TESTS_RAN` is separate from `TESTS_PASS`.
Unknown test evidence or an unparseable grader result marks the row `INVALID`
and stops V6; no repair-and-resume is allowed after a usable output.

Before and after every model call the runner records:

```text
git status --porcelain=v1
```

Patch capture is exactly:

```text
git add -A
git diff --cached --binary --no-ext-diff
```

This captures modifications, deletions, and new files. Cleanup/reset executes
in `finally` for normal completion, test failure, grader failure, process
crash, quota pause, and setup failure.

## Schedule and checkpointing

V6 is exactly 7 tasks × 3 arms × 3 repetitions = 63 fresh Codex executions,
randomized with seed `2026082602`. The three 21-row rounds are operational
checkpoints only. The private condition map remains separate from blind rows.

After every attempt the runner atomically records run ID, status, task, patch
checksum, exit status, usable-output flag, usage, wall time, tool count, test
evidence, and grading status. It never regenerates a usable result. Only
objective infrastructure failure without usable model output may be retried.
Quota pauses preserve pending V6 IDs and configuration; model switching,
repetition reduction, and arm selection are prohibited.

## Analysis and GO gate

Grade patches blind and freeze/hash grading outputs before joining the private
condition map. Report run-level values and task-level means over three
repetitions. Bootstrap across seven task clusters, not 63 independent rows.

Choose Arm A or B as the strongest control by compliant-success rate, breaking
ties by lower authority-violation rate. Arm C must satisfy every existing GO
criterion: at least a 10-point compliant-success advantage, at least 50%
relative violation reduction, positive paired task bootstrap 90% CI, no more
than five-point losses in ordinary completion or tests, no material
refusal/no-op increase, and advantage across at least three authority-error
categories. No futility rule is added.

## Required pre-run gates and artifacts

Before the first V6 model call, all of the following must pass:

- 7/7 V6 contracts;
- 14/14 sanity replays with expected authority outcomes and real tests;
- fresh 63-row model-free orchestration with zero model calls;
- bounded storage/recovery and runtime disk guards;
- backend, extractor, authority, raw-context parity, and grader freezes;
- production diff empty; and
- verified `ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V6_SHA256.txt`.

`ACTION_COMPLIANCE_V6_GATE_REPORT.md` records the model-free gate evidence and
the managed-session provider boundary. The excluded Codex preflight and the
statistical launch are host-shell operations; the host runner must pass its
provider precheck before launching any child.

The V6 statistical dataset is `data/action_compliance/codex_runs_v6_host/`.
No prior output directory, including model-free V5 artifacts, is an input.
The final contract-strengthened dry-run artifact is
`data/action_compliance/v6_dry_run_host_contract_v2/`; the earlier V6
model-free dry-run remains audit history and is not an execution input.
