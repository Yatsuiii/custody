Objective: run04 got a real Firestore treatment mostly through (125
collections of real data written, through w20 + caseN/O/P) but was killed
by my OWN external `timeout 590` wrapper sending SIGTERM before the
harness's own try/except could run, so no evidence file was ever written
(not classified INVALID -- simply never got to record anything) and the
leftover real data (confirmed by query, then deleted) was never cleaned by
the harness itself. This session bumps to a fresh run05 identity with NO
external hard-kill wrapper, so the harness's own code runs to completion
(however long that legitimately takes) and writes its own evidence/cleanup
regardless of runtime; if total runtime exceeds the frozen 600s ceiling,
that is reported honestly as a ceiling miss, not hidden by an external kill.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: p7/b7-live-20260825-run05
Parent: p7/b7-live-20260825-run04 @ 47d361606775a3bb5bd69466aa3d7c168b662b6b
        (namespace-scoping fix; run04's incomplete/uncleaned attempt is not
        evidence of anything -- no result was ever recorded for it, and its
        leftover real data was independently queried and deleted before
        this branch was created)

Fresh P7 identity:
- run_id: p7-b7-20260825-run05
- namespace: custody_p7_b7_20260825_run05
- artifacts: P7_RUN05_RAW_TRACE.json, P7_RUN05_RESULT.json,
  P7_RUN05_CLEANUP.json

Allowed files:
- scripts/p7_run.py
- research/production_b7/P7_RUN05_RAW_TRACE.json
- research/production_b7/P7_RUN05_RESULT.json
- research/production_b7/P7_RUN05_CLEANUP.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/.
- No edit to tests/test_b7_production_equivalence.py.
- No reuse of run01/run02/run03/run04 identities or namespaces.
- No change to the O/P barrier mechanism or the namespace-scoping fix from
  run04 -- this branch changes only the identity constants.
- No external process-level timeout/kill wrapper around the real execution;
  let the harness's own internal waits (barrier timeouts, subprocess joins)
  govern completion so it can always reach its own try/except and write its
  evidence files, however long that takes.
- Execution against real Firestore under run_id p7-b7-20260825-run05 is
  authorized by the user's explicit "fix this & run properly" instruction
  earlier in this session.

Baseline: `.venv/bin/python -m unittest discover tests` = 484/484 on this
worktree (verified earlier this session); custody/ and
tests/test_b7_production_equivalence.py must remain byte-identical to
16d3459, since this change touches only scripts/p7_run.py's identity
constants.

Acceptance gates:
1. scripts/p7_run.py uses run05 identity and artifacts; RUN_ID/NAMESPACE_PREFIX
   and the three output paths are updated together; no other logic changes.
2. The harness compiles, Ruff passes, and the local equivalence test
   (tests.test_b7_production_equivalence) still passes; `git diff --stat
   custody/ tests/` empty.
3. Namespace custody_p7_b7_20260825_run05 independently confirmed empty
   (direct query, not just trusting the harness's own preflight) before
   execution.
4. Committed and pushed before execution; local HEAD equals remote branch
   SHA, verified by independent fetch, before running against real
   Firestore.
5. Execution runs via run_in_background with no external timeout kill;
   whatever P7_RUN05_RESULT.json records (TREATMENT-COMPLETED or
   P7-INVALID-RUNNER-ATTEMPT) is reported honestly, including runtime vs.
   the 600s ceiling and any recovery-bound miss.

Verification: `.venv/bin/python -m py_compile scripts/p7_run.py`;
`~/.local/bin/ruff check scripts/p7_run.py`; `.venv/bin/python -m unittest
discover tests` (484/484); commit/push/local==remote check; then execute
`scripts/p7_run.py --i-understand-this-spends-real-firestore-quota` for
real, in background, without a hard kill, and report the result honestly.

Status: active
