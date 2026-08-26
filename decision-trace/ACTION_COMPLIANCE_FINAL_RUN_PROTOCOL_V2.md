# DecisionTrace Action-Compliance Final Run Protocol V2

## Status

V1 is invalidated and excluded. Its complete evidence is preserved under
`data/action_compliance/invalidated_sparse_checkout_run/` and documented in
`ACTION_COMPLIANCE_SPARSE_CHECKOUT_INVALIDATION.md`.

V2 preserves the frozen scientific package: seven tasks, exact task prompts,
raw bundles, Arm B summaries, Arm C AuthorityProofs, extractor v2, resolver,
graders, sanity patches, GO criteria, three repetitions, blind A/B/C grading,
and the preregistered 63-run design.

The only execution architecture change is complete pinned worktrees replacing
sparse worktrees. V1 run IDs and outputs are never reused.

## Frozen backend

- CLI: `codex-cli 0.146.1`
- Model: `gpt-5.6-luna`
- Reasoning effort: `high`
- Approval: `never`
- Sandbox: `workspace-write`
- Timeout: 600 seconds
- Concurrency: 1
- Plan seed: `2026082302`
- Invocation: `codex -a never -c 'model_reasoning_effort="high"' -m gpt-5.6-luna exec --sandbox workspace-write --ephemeral --json --color never <PROMPT>`
- Network marker inside coding runs: `CODEX_SANDBOX_NETWORK_DISABLED=1`
- Session isolation: one fresh `--ephemeral` invocation per run

The system prompt and materialized contexts are serialized byte-for-byte as the
frozen system prompt, two LF bytes, and the exact context. No model, reasoning,
prompt, context, tool permission, grader, timeout, or statistical change is
permitted after the first usable V2 statistical output.

## V2 worktree and capture contract

Every task uses `scripts/setup_action_compliance_full_worktree.py`. The helper
performs a shallow pinned fetch where supported and checks out the complete
repository tree. It does not invoke sparse checkout and has no task-specific
checkout exception. Before a model call, the runner verifies the exact pinned
SHA and clean `git status --porcelain=v1`.

The runner records status before and after each model call. Capture remains:

```text
git add -A
git diff --cached --binary --no-ext-diff
```

This captures tracked edits, deletions, and newly created files. A capture
failure is an infrastructure failure only when the final full worktree cannot
be represented reliably. Infrastructure failures with no usable output may be
retried; usable coding results may not.

## V2 gate evidence

- Seven full pinned worktrees: PASS; exact SHAs, clean reset, no sparse checkout.
- All 14 sanity patches: PASS; staged binary capture and reset for every patch.
- Sanity graders: all compliant patches completed and were authority-compliant;
  all violating patches completed and were authority-violating; documented
  task-specific ordinary-test behavior is unchanged.
- 63-row no-model dry run: PASS; 21 rows per round, fresh opaque IDs, separate
  condition map, full worktree creation, new-file capture, cleanup, and atomic
  resume state; zero model calls.
- Excluded Kubernetes V2 preflight: PASS; one HIGH Luna call, zero approval
  prompts, autonomous edit, new-file capture, parseable logs, real tests, and
  clean reset.

## V2 execution plan

The statistical dataset is exactly 63 fresh Codex runs:

```text
7 tasks x 3 arms x 3 repetitions = 63
```

Operational rounds are 21 runs each. The condition map remains separate from
blind grader input. Checkpoint state is written after every run. If a new
deterministic infrastructure defect appears after V2 statistical output begins,
stop and invalidate V2; do not repair and resume.

## V2 preflight result

The single excluded Kubernetes preflight is recorded in
`data/action_compliance/codex_preflight_v2/` and is not statistical data.

Recorded preflight values: `gpt-5.6-luna`, `high`, `never`,
`workspace-write`, 600-second timeout, 238.873 seconds wall time, 1,098,152
input tokens, 10,187 output tokens, 4,523 reasoning output tokens, 12,965-byte
staged patch, and `TESTS_EXECUTED=true`, `NO_TESTS_RAN=false`,
`TESTS_PASS=true`. The excluded fixture's authority result is not a V2
statistical gate.

## Freeze identifiers

- V1: invalidated after six usable outputs because sparse checkout made task-04
  patch capture impossible.
- V2 backend hash: recorded in `ACTION_COMPLIANCE_CODEX_BACKEND_V2_SHA256.txt`.
- V2 manifest: `ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V2_SHA256.txt`.

No V1 comparative output may be analyzed or joined into V2.
