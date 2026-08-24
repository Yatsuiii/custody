Objective: Build and freeze a real-Firestore P7 harness (scripts/p7_run.py)
that reuses the frozen local B7 case set (tests/test_b7_production_equivalence.py,
cases A1/A2/B-M) unmodified via store injection, and adds real-Firestore /
real-independent-process variants of cases N (restart), O (action/revocation
race), and P (killed writer), per research/production_b7/EQUIVALENCE_TEST_PLAN.md.
This session builds and freezes the harness only; live execution against real
Firestore requires a separate explicit go from the user after the harness is
committed and pushed.

Branch: p7/b7-live-20260824-run01
Parent: origin/stabilization/custody-final-16d3459 @ 16d34593dbc765e4ce3c34f03a0625783127f205
        (independently verified production baseline; see reconciliation audit
        earlier in this session)

Allowed files:
- scripts/p7_run.py
- research/production_b7/P7_RUN01_RAW_TRACE.json
- research/production_b7/P7_RUN01_RESULT.json
- research/production_b7/P7_RUN01_CLEANUP.json
- research/production_b7/P7_HARNESS_DESIGN_NOTE.md
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/ (production B7 implementation frozen at
  16d3459; must remain byte-identical).
- No edit to tests/test_b7_production_equivalence.py; its case construction
  and scorer are reused by import/injection only.
- No modification of the frozen case list, scorer thresholds, resource
  ceilings (reads<=1500, writes<=200, deletes<=200, cost<=$0.01, runtime<=600s),
  or the 90-second recovery bound.
- No live execution against real Firestore until the harness is committed,
  pushed, and remote-verified, and the user gives a separate explicit
  execution go-ahead.
- No commit/push unless explicitly authorized (already granted for this
  build-and-freeze step per user instruction).

Baseline: `.venv/bin/python -m unittest discover tests` = 484/484 on this
worktree at 16d3459 (verified earlier this session). No production code is
touched by this harness, so this baseline must remain unchanged.

Acceptance gates:
1. scripts/p7_run.py imports tests.test_b7_production_equivalence and injects
   a Firestore-backed store via _world() monkeypatch, without duplicating or
   altering any case construction logic (A1/A2/B-M reused verbatim).
2. Cases N/O/P are implemented against real Firestore with real independent
   OS processes (multiprocessing, spawn context), not threads/SQLite.
3. Evidence freeze order is enforced: raw trace written+digested before the
   scorer runs; result written+digested before cleanup; cleanup never
   rewrites raw trace or result files.
4. Resource counters (reads/writes/deletes) are tracked and compared against
   the frozen ceiling; the script refuses to run if expected-output files
   already exist or the namespace is not empty.
5. The script requires an explicit `--i-understand-this-spends-real-firestore-quota`
   flag and is not invoked in this session.

Verification: `python -m py_compile scripts/p7_run.py`; manual read-through
against research/production_b7/EQUIVALENCE_TEST_PLAN.md's frozen case table
and metrics; `git diff --stat custody/ tests/` empty.

Status: active
