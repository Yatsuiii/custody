# Action-Compliance V6 Storage Contract

V1 was invalidated by sparse-checkout capture. V2 was invalidated by the
interpreter contract. V3 was invalidated by disk quota during Go setup. V4
was invalidated by deterministic test-contract/grader interpretation defects.
All prior comparative outputs remain excluded.

## Bounded lifecycle

V6 uses two worker slots and one disposable full worktree per slot. A slot is
created only inside `V4StoragePolicy.lifecycle()` and is removed in `finally`
after setup, model execution, patch capture, grading, and test verification.
No 63-worktree persistent clone is permitted.

Shared source mirrors and dependency caches are immutable with respect to
benchmark outputs and source modifications. Per-slot Go build caches and Cargo
targets are disposable. Python task environments are recreated in the
worktree; no condition-specific cache is used.

V6 storage root:

`data/action_compliance/v6_execution_storage/`

The existing local V4 source/dependency caches may be referenced as immutable
cache inputs; V4 patches, logs, row files, condition maps, and grading data are
never read as V6 statistical input.

## Paths and policy

- source mirrors: `<V6_ROOT>/sources/`;
- shared Go module cache: `<V6_ROOT>/shared/go-modcache/`;
- shared Cargo registry: `<V6_ROOT>/shared/cargo-home/`;
- shared Python wheel/cache paths: `<V6_ROOT>/shared/python-wheelhouse/` and
  `<V6_ROOT>/shared/pip-cache/`;
- per-slot temporary path: `<V6_ROOT>/tmp/slot-NN/`;
- per-slot Go build cache: `<V6_ROOT>/slots/slot-NN/.../go-cache/build/`;
- per-slot Cargo target: `<V6_ROOT>/slots/slot-NN/cargo-target/`.

Every child receives the same offline dependency policy. The Codex provider
inherits the normal host network environment and is checked for reachability
before launch; tasks themselves use their frozen cached dependency commands.

## Guards and recovery

Before each new run, V6 requires at least 20 GiB free on the execution
filesystem, 5 GiB free on the host root filesystem, and 100,000 free inodes.
If a guard fails, no model process starts. Abandoned marked or unmarked V6
slots are recoverable only when their marker proves they are not owned by a
live matching process.

The model-free stress and crash-recovery gates must pass before statistical
execution. A guard pause is resumable; a deterministic contract, worktree, or
grader defect after the first usable V6 output invalidates V6 and cannot be
repaired in place.
