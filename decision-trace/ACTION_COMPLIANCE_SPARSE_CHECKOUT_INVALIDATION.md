# V1 Phase 9 invalidation

**HARNESS EXECUTION FROM INVALIDATED FREEZE — EXCLUDED**

V1 Phase 9 is invalidated. No V1 comparative output, patch, grader result, or
failure row may enter the final statistical dataset, grading table, bootstrap
input, cost comparison, or primary analysis.

## Preserved evidence

The complete V1 material is archived at:

`data/action_compliance/invalidated_sparse_checkout_run/`

This includes the six usable patches, logs, invocation records, row-level
failures, resume state, old condition map, 63-row plan, V1 protocol, V1
manifest checksum file, V1 backend configuration, and V1 backend hash.

V1 backend hash:

`8f8f4cf2492825266eb5f3d553e22b7c9c28a6c016f0e4692eb9a515b9943eaa`

V1 manifest checksum-file hash:

`e6af9073595be4c61b67ab454a20a0cc130b9cb939d8d4192ab731244fd1ec42`

V1 contained 6 usable Codex outputs and 15 row-level infrastructure failures.
Two additional task-04 attempts reached Codex but failed deterministically at
patch capture; their evidence is preserved in the archived run directory.

## Root cause

The task-04 setup used sparse checkout with a definition that omitted:

`Lib/test/test__pyio_locale.py`

The frozen capture command was:

```text
git add -A
git diff --cached --binary --no-ext-diff
```

Git rejected the legitimate new test path as outside the sparse-checkout
definition. Repairing the sparse definition or changing capture semantics after
comparative output existed would have changed the frozen infrastructure.

V2 therefore uses complete pinned worktrees for every statistical task. There
is no task-specific checkout exception. V1 run IDs are never resumed or reused.
