Objective: run05 executed for real (615.05s runtime -- already confirming
the treatment naturally exceeds the 600s ceiling) and got all the way
through 20 worlds, N, and O, and through Case P's kill/zero-partial-write/
immediate-DENY checks, but failed on the FINAL step: the post-kill retry
admission hit real Firestore contention (`Aborted: 409 Too much contention
on these documents`) and exhausted the SDK's default 5-attempt retry,
raising an unhandled AuthorityUnavailable. This independently confirms,
via a different code path, the same real contention phenomenon the other
session measured directly in its "production contention" validation (117s
to clear). This session adds one narrow, scoped fix: wrap only the final
retry-admission call in `_run_firestore_killed_writer` with an explicit
outer retry-with-backoff loop (catching AuthorityUnavailable, budget
generous enough to exceed the previously measured ~117s clearing time),
so the harness observes and records the real recovery duration instead of
crashing. No other logic changes. Fresh run06 identity.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: p7/b7-live-20260825-run06
Parent: p7/b7-live-20260825-run05 @ ddce9aab3b3773af65d7449dd11dc100bb936893
        (run05 INVALID attempt preserved as-is at its own P7_RUN05_*.json
        evidence; not modified by this branch)

Fresh P7 identity:
- run_id: p7-b7-20260825-run06
- namespace: custody_p7_b7_20260825_run06
- artifacts: P7_RUN06_RAW_TRACE.json, P7_RUN06_RESULT.json,
  P7_RUN06_CLEANUP.json

Allowed files:
- scripts/p7_run.py
- research/production_b7/P7_RUN05_RAW_TRACE.json
- research/production_b7/P7_RUN05_RESULT.json
- research/production_b7/P7_RUN05_CLEANUP.json
- research/production_b7/P7_RUN06_RAW_TRACE.json
- research/production_b7/P7_RUN06_RESULT.json
- research/production_b7/P7_RUN06_CLEANUP.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/.
- No edit to tests/test_b7_production_equivalence.py.
- No reuse of run01-run05 identities or namespaces.
- No change to the O/P barrier mechanism, the namespace-scoping fix, or any
  case construction/scorer semantics -- this branch only wraps one call
  site's transient-failure handling.
- No enlargement of the 90-second recovery bound or the frozen resource
  ceiling; a miss is still reported honestly, not hidden by the retry loop.
  The retry loop's own outer budget is a harness-robustness allowance, not
  a redefinition of what counts as "recovered in time."
- No external process-level timeout/kill wrapper around the real execution.
- Execution against real Firestore under run_id p7-b7-20260825-run06 is
  authorized by the user's explicit follow-up approval of this specific
  backoff fix.

Baseline: `.venv/bin/python -m unittest discover tests` = 484/484 on this
worktree (verified earlier this session); custody/ and
tests/test_b7_production_equivalence.py must remain byte-identical to
16d3459, since this change touches only scripts/p7_run.py.

Acceptance gates:
1. Only `_run_firestore_killed_writer`'s final retry-admission call gains a
   retry-with-backoff wrapper catching `custody.authority.AuthorityUnavailable`;
   no other function changes.
2. `recovery_seconds` still measures from the kill to the eventual
   successful retry (including all backoff time), so an honest recovery
   duration is recorded even if it exceeds 90s.
3. scripts/p7_run.py uses run06 identity and artifacts; RUN_ID/NAMESPACE_PREFIX
   and the three output paths are updated together.
4. The harness compiles, Ruff passes, and the local equivalence test still
   passes; `git diff --stat custody/ tests/` empty.
5. Namespace custody_p7_b7_20260825_run06 independently confirmed empty
   before execution; committed and pushed before execution; local HEAD
   equals remote branch SHA, verified by independent fetch.

Verification: `.venv/bin/python -m py_compile scripts/p7_run.py`;
`~/.local/bin/ruff check scripts/p7_run.py`; `.venv/bin/python -m unittest
discover tests` (484/484); commit/push/local==remote check; then execute
`scripts/p7_run.py --i-understand-this-spends-real-firestore-quota` for
real, in background, without a hard kill, and report the result honestly,
including runtime vs. the 600s ceiling and any recovery-bound miss.

Status: active
