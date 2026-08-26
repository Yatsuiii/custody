# Action-Compliance V3 Disk Failure Audit

Date: 2026-08-24
Status: completed before cleanup

## Scope and preservation

V3 remains permanently invalidated. Its protocol, manifest, run metadata,
condition map, 36 excluded usable outputs, failed task-06 evidence, and
invalidation records are preserved. No V3 output is eligible for grading,
analysis, or reuse.

## Filesystem measurements

Measured before cleanup:

| Location | Filesystem | Capacity/free | Inodes | Usage |
|---|---|---:|---:|---:|
| `/` | ext4 `/dev/nvme0n1p5` | 59G / 5.8G free | 2,504,075 free | 37% inodes |
| `/tmp` | 7.5G tmpfs | 6.1G free at audit | 1,039,213 free | 1% inodes |
| repository | ntfs3 `/dev/nvme0n1p3` | 408G / 99G free | not reported by NTFS mount | 76% blocks |

The `/tmp` mount is explicitly configured with `usrquota`. `quota`,
`xfs_quota`, and a project-quota query tool were unavailable in the audit
environment, so the numeric per-user hard limit cannot be read directly.

## Largest measured consumers

| Consumer | Size |
|---|---:|
| `/home/Yatsuiii/.cache/go-build` | 4.28G |
| `/home/Yatsuiii/go` | 1.52G |
| `/tmp/codex-k8s-postfilter-gocache` | 1.31G |
| `/home/Yatsuiii/.cache` total | 5.84G |
| `/home/Yatsuiii/.pyenv` | 737M |
| repository `.venv` | 445M |
| `/home/Yatsuiii/.cargo` | 240M |
| `/home/Yatsuiii/.cache/pip` | 227M |
| V3 run artifacts | 8.9M |
| all action-compliance data | 120M |

No abandoned V3 worktrees were present at audit time. V3 run logs and patches
were therefore not the storage driver.

## Failure reconstruction

Both affected V3 task-06 rows failed during the generic full-worktree setup
preflight, before Codex invocation. Each row exhausted three setup attempts;
all six attempts reported `disk quota exceeded` while Go was writing build or
vet artifacts. The failing paths included `/tmp/go-build...` and the
per-run Go cache beneath the temporary action-compliance directory.

The failure is classified as:

- **B — effective user quota:** verified by the exact error and the `/tmp`
  `usrquota` mount option; the numeric limit is unavailable.
- **D — temporary-directory capacity:** verified as the build writes were in
  `/tmp`, a finite 7.5G tmpfs.
- **E — runaway/shared generated cache pressure:** contributing evidence;
  stale Go build/cache material occupied 1.31G in `/tmp`, and the host Go
  caches occupied 5.80G on `/`.

The audit does not support actual inode exhaustion: both `/` and `/tmp` had
substantial free inodes. It does not support leaked V3 worktrees: none were
left. It does not support the benchmark content or grader as the cause.

## Cleanup eligibility

Only generated execution/cache material may be removed. Frozen research
artifacts and all V3 evidence remain protected. The disposable cleanup target
is the stale `/tmp/codex-k8s-postfilter-gocache` directory; its measured size
and before/after usage will be recorded in the V4 storage contract.

## V4 design consequence

V4 must place temporary worktrees, Go build/module caches, Cargo caches and
targets, and Python/pip temporary material under an explicitly provisioned
large repository-side execution-storage root on `/dev/nvme0n1p3`, not under
`/tmp` or the root filesystem. It must use two bounded worker slots, one
disposable worktree per slot, hard post-run cleanup, startup recovery, and
pre-run free-space/inode guards. A 63-cycle model-free stress test must pass
before any V4 model call.
