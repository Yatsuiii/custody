# DecisionTrace V4 Storage Contract

## Status and lineage

V1 was invalidated by sparse-checkout patch capture after six usable outputs.
V2 was invalidated by the generic test-interpreter contract defect. V3 was
invalidated after 36 usable outputs when repeated task-06 setup attempts hit
`disk quota exceeded` during Go dependency compilation. Every prior output and
failed attempt remains excluded from V4.

V4 changes execution/storage infrastructure only. Tasks, prompts, raw A/B/C
contexts, summaries, AuthorityProofs, extractor-v2, authority resolver,
graders, backend, repetitions, statistics, and GO criteria are unchanged.

## Diagnosed V3 failure

The audit in `ACTION_COMPLIANCE_V3_DISK_FAILURE_AUDIT.md` records the evidence:

- the repository filesystem had ample capacity but the effective execution
  environment was quota-limited;
- `/tmp` was a separate 7.5 GiB quota-bearing tmpfs;
- the stale Go build cache under `/tmp` alone was 1.31 GiB;
- root Go caches occupied 4.28 GiB (`~/.cache/go-build`) and 1.52 GiB
  (`~/go`);
- inodes were healthy and no persistent V3 worktree leak was found.

The failure is therefore classified as a combination of effective quota,
temporary-filesystem pressure, and unbounded generated Go cache growth, not a
benchmark or task defect.

## Bounded lifecycle

There are exactly two reusable worker slots and no persistent per-run
worktrees. Each run:

1. checks the disk guard and recovers only stale V4-owned slot markers;
2. creates one complete pinned worktree in its assigned slot;
3. uses the shared immutable dependency caches and slot-local build outputs;
4. records status, captures the staged binary patch, grades, and executes the
   frozen test contract;
5. resets the worktree and removes the entire slot and slot temporary tree in
   a `finally` path.

The lifecycle also runs cleanup when setup, Codex, tests, grading, quota, or
the orchestrator raises. Startup recovery removes only slot directories with
an expired V4 ownership marker whose recorded process identity no longer
matches the live process. An unmarked slot root is also removable because
slot creation and marker publication are serialized by a process-wide
lifecycle lock; this closes the crash window between those two operations.
Point-in-time directory-size accounting tolerates a file disappearing between
enumeration and `stat()` while a build or test cleanup is active; filesystem
free-byte and inode measurements remain authoritative for the guard.

## Exact paths and cache policy

The V4 storage root is:

`/run/media/Yatsuiii/Windows-SSD/custody-search-2/decision-trace/data/action_compliance/v4_execution_storage`

The runner explicitly exports:

- `TMPDIR`, `TMP`, `TEMP`: `<root>/tmp/slot-00` or `slot-01`;
- `GOMODCACHE`: `<root>/shared/go-modcache`;
- `GOCACHE`: `<root>/slots/<slot>/<task>/go-cache`;
- `GOPROXY=off`, `GOSUMDB=off`;
- `CARGO_HOME`: `<root>/shared/cargo-home`;
- `CARGO_TARGET_DIR`: `<root>/slots/<slot>/cargo-target`;
- `CARGO_NET_OFFLINE=true`;
- `PIP_CACHE_DIR`: `<root>/shared/pip-cache`;
- `CODEX_SQLITE_HOME`: `<root>/codex-sqlite`;
- `CODEX_HOME`: inherited from the normal host shell and not overridden by the
  official host runner. The optional `--isolate-codex-home` flag creates a
  disposable per-slot home from the existing authentication/configuration/
  model metadata; it is not part of the default execution command;
- `PYTHONDONTWRITEBYTECODE=1`.

The isolated V4 execution environment also supplies Git's `safe.directory=*`
configuration through environment-scoped config variables. This is required
because the mounted execution filesystem presents files as a different owner
inside the sandbox; it applies only to the disposable V4 execution process and
does not modify the user's global Git configuration.

Pinned source mirrors contain only the required pinned commit and are reused
by all arms. Shared caches contain dependencies only; no source modifications,
patches, prompts, grading outputs, or condition-specific artifacts are stored
in them. Slot build caches and Cargo targets are deleted after each run. The
same cache and network policy is applied to A, B, and C.

The excluded Kubernetes preflight is prepared separately before its model
call: the host runner uses host-enabled Go module download only to populate the
shared module cache, then runs the exact frozen Kubernetes test command with
`GOPROXY=off`. A failed offline verification blocks the preflight model call.

## Normalized test contract

The setup metadata is the sole authority. The runner consumes its command,
cwd, and environment verbatim. `<WORKTREE>` and `<V4_STORAGE_ROOT>` below are
path templates; setup materializes the absolute paths for each slot.

| Task | Interpreter | Exact test command | cwd | Important env |
|---|---|---|---|---|
| task-01-k8s-postfilter-victims | `go` | `go test ./pkg/scheduler/framework/preemption/... ./pkg/scheduler/framework/plugins/defaultpreemption/...` | `<WORKTREE>` | `GOWORK=off`, slot `GOCACHE`, shared `GOMODCACHE` |
| task-02-django-index-together-superseded | `<WORKTREE>/.venv/bin/python` | `<WORKTREE>/.venv/bin/python runtests.py model_indexes -v1` | `<WORKTREE>/tests` | none |
| task-go-01-maps-sorted-keys | `go` | `go test -overlay=<WORKTREE>/overlay.json maps` | `<WORKTREE>` | `GOWORK=off`, slot `GOCACHE`, shared `GOMODCACHE` |
| task-03-pip-inline-script-metadata | `/usr/bin/python3.14` | `/usr/bin/python3.14 -m unittest discover -s tests/unit -p test_script_metadata.py` | `<WORKTREE>` | `PYTHONPATH=<WORKTREE>/src` |
| task-04-cpython-locale-encoding-scope | `/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python` | `/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python Lib/test/test__pyio_locale.py` | `<WORKTREE>` | none |
| task-05-packaging-manylinux-aliases | `/usr/bin/python3.14` | `/usr/bin/python3.14 tests/test_manylinux_pep600.py` | `<WORKTREE>` | `PYTHONPATH=<WORKTREE>` |
| task-06-opentofu-static-source-scope | `go` | `go test ./internal/configs -run ^TestDecisionTrace -count=1` | `<WORKTREE>` | slot `GOCACHE/build`, shared `GOMODCACHE` |
| task-07-axum-optional-typed-header | `cargo` | `cargo test --offline -p axum-extra --features typed-header --test decisiontrace_optional_typed_header -- --nocapture` | `<WORKTREE>` | shared `CARGO_HOME`, slot `CARGO_TARGET_DIR` |

## Freeze gates

The final V4 gate requires all seven contracts, all fourteen sanity replays,
real test execution, authority outcomes, new-file patch capture, the complete
63-cycle model-free stress test, bounded residual storage, the crash/recovery
test, backend/extractor/authority/raw-context freeze checks, and no production
code diff. No Codex statistical call is permitted before every gate is
recorded as passing.
