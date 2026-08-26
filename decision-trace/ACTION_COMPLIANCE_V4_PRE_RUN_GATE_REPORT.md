# DecisionTrace V4 pre-run gate report

## Scope

V1, V2, V3, and all Claude pilot material remain excluded. V3 is excluded
after 36 usable outputs because task-06 full-worktree setup hit `disk quota
exceeded` during Go dependency compilation. V4 has no comparative statistical
output.

## Storage result

- execution filesystem: `/run/media/Yatsuiii/Windows-SSD`, 408 GiB total,
  approximately 97 GiB free after testing;
- host root filesystem: 59 GiB total, approximately 11 GiB free after
  testing;
- free inodes: approximately 25.2 million on the execution filesystem and
  2.5 million on host root;
- largest V4 consumers: shared Go module cache 1.86 GiB, shared Cargo home
  97 MiB, pinned source mirrors 127 MiB, V4 storage total approximately
  2.1 GiB;
- disposable V3 cleanup: stale Go cache under `/tmp`, 1.31 GiB;
- V4 lifecycle: two reusable worker slots, complete pinned worktree per run,
  shared dependency caches, slot-local build outputs, crash-safe cleanup;
- exact guard: 20 GiB execution free, 5 GiB host-root free, 100,000 free
  inodes;
- worst measured slot peak: 806,758,583 bytes (task-07); measured two-slot
  build peak: 1,613,517,166 bytes before shared/frozen artifacts;
- 63-cycle storage stress: PASS, 63/63, zero failures, zero model calls,
  zero residual worktrees, residual growth 877 bytes;
- crash/recovery proof: PASS, including crash cleanup, stale marker recovery,
  and preservation of a live marker.

## Model-free scientific gates

- normalized contracts: PASS, 7/7;
- sanity replays: PASS, 14/14, all tests executed, expected authority outcomes
  preserved;
- 63-row orchestration dry run: PASS, 63/63, three 21-row rounds, zero model
  calls;
- raw A/B/C parity: PASS, 7/7;
- authority resolver freeze: PASS, 9/9;
- extractor-v2 freeze: PASS;
- backend component hash verification: PASS;
- production content was not changed by V4 infrastructure work. The existing
  worktree retains unrelated pre-existing `app/ingest.py` content/mode dirt;
  `app/authority.py` also has a pre-existing mode-only difference and was not
  touched.

## Excluded V4 preflight evidence

Two high-reasoning Luna attempts were used on the excluded Kubernetes fixture;
neither is statistical data. Attempt 1 failed before events because the
managed parent mounted the normal Codex home read-only. The generic V4 fix
added a writable slot-local `CODEX_HOME`, copied only startup metadata, and
passed the full 63-cycle stress again. Attempt 2 reached Codex but failed
before model work because the current managed environment could not resolve
`chatgpt.com` for the provider. It produced zero tool calls, zero edits, zero
tokens, and no patch. No MAX attempt was made.

Therefore the storage and model-free gates pass, but the excluded Codex
preflight gate does not. V4 statistical execution is authorized only after a
new execution window can satisfy the already-frozen preflight rule without
changing the backend or consuming a third preflight attempt.

## Decision

`START V4: NO` — stop before Phase 9. Preserve all artifacts and retry only
the excluded preflight under the same Luna/high configuration when provider
network resolution is available. Do not analyze or reuse any prior output.
