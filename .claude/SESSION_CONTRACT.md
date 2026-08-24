Objective: Build and freeze a fresh P7 harness revision that fixes the
run02 lifecycle defect by arming Case O/P barriers only after fixture setup.
This session builds the harness only; fresh probes must pass before any P7
execution under the new identity.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: p7/b7-live-20260825-run03
Parent: p7/b7-live-20260825-run02 @ 8ee72faeda2f83c4f925f405a8f4394d7c7661da
        (corrected RPC read interception; run02 invalid attempt is preserved
        separately at evidence commit bda1f8cd250feb5b8f2d351eab8c80adbeddd069)

Fresh P7 identity:
- run_id: p7-b7-20260825-run03
- namespace: custody_p7_b7_20260825_run03
- artifacts: P7_RUN03_RAW_TRACE.json, P7_RUN03_RESULT.json,
  P7_RUN03_CLEANUP.json

Allowed files:
- scripts/p7_run.py
- research/production_b7/P7_HARNESS_DESIGN_NOTE.md
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/.
- No edit to tests/test_b7_production_equivalence.py.
- No reuse of run01 or run02 identities.
- No P7 execution in this harness-build session.
- No claim of infrastructure support until fresh O/P probes pass.

Design decision: `_Barrier` starts disarmed and exposes one explicit `arm()`
transition. Case O arms only after root/child fixture construction and its
history read; Case P arms only after the child watcher is ready and immediately
before the killed-writer setup. The RPC-boundary interception from run02 is
unchanged; only lifecycle ownership is corrected so setup reads cannot consume
or block the race barrier.

Acceptance gates:
1. scripts/p7_run.py uses run03 identity and artifacts, and Case O/P call
   `barrier.arm()` only after setup.
2. The harness compiles, Ruff passes, and the local equivalence test passes;
   custody/ and tests/ remain unchanged.
3. The harness revision is committed and pushed; local HEAD equals the remote
   branch SHA before any fresh probe runs.
4. A separate fresh probe pair uses identity
   p7-barrier-contract-20260825-04 and namespace
   custody_p7_barrier_contract_20260825_04; both O and P must pass before any
   run03 P7 execution.
5. If probes pass, actual P7 run03 requires a separate explicit user
   authorization because run02's authorization applied to the spent run02
   identity.

Verification planned:
- `/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python -m py_compile
  scripts/p7_run.py`
- `/home/Yatsuiii/.local/bin/ruff check scripts/p7_run.py`
- `/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python -m unittest
  tests.test_b7_production_equivalence`
- commit/push/local==remote checks before fresh probes.

Status: active
