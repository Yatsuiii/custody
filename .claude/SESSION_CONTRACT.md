Objective: Fix a real namespace-scoping bug found by executing run03 for
real: `_collection_counts`/`_cleanup` in scripts/p7_run.py only checked the
bare `{prefix}__{name}` collections, never the actual per-world/per-case
sub-prefixes (`{prefix}__w01`, `__caseN`, `__caseO`, `__caseP`, ...) that
cases A-M/N/O/P actually write to. This let run03 execute against a
namespace that silently already had real leftover data (through w20 plus
caseN/O/P, confirmed by direct query and cleaned up manually before this
session started), causing a real `AuthorityConflict` inside
`custody/firestore_store.py`'s `put_policy` (a genuine collision on
pre-existing conflicting policy data, not a security-relevant B7 result --
classified P7-INVALID-RUNNER-ATTEMPT, evidence frozen at
research/production_b7/P7_RUN03_*.json on p7/b7-live-20260825-run03,
NOT amended by this work). This session fixes the scoping bug only, under a
fresh run04 identity, then executes P7 for real once verified.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: p7/b7-live-20260825-run04
Parent: p7/b7-live-20260825-run03 @ d352c2edf0c0b08d6d3e9def6aaea106d6d0791e
        (run03 INVALID attempt preserved as-is at that commit's own
        P7_RUN03_*.json evidence; not modified by this branch)

Fresh P7 identity:
- run_id: p7-b7-20260825-run04
- namespace: custody_p7_b7_20260825_run04
- artifacts: P7_RUN04_RAW_TRACE.json, P7_RUN04_RESULT.json,
  P7_RUN04_CLEANUP.json

Allowed files:
- scripts/p7_run.py
- research/production_b7/P7_HARNESS_DESIGN_NOTE.md
- research/production_b7/P7_RUN04_RAW_TRACE.json
- research/production_b7/P7_RUN04_RESULT.json
- research/production_b7/P7_RUN04_CLEANUP.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/.
- No edit to tests/test_b7_production_equivalence.py.
- No reuse of run01/run02/run03 identities or namespaces.
- No change to the O/P barrier mechanism (RPC-boundary interception,
  arm()-after-setup lifecycle) validated by probe-03/probe-04 -- this
  session only fixes namespace scoping in preflight/cleanup.
- Execution against real Firestore under run_id p7-b7-20260825-run04 is
  authorized by the user's explicit "fix this & run properly" instruction
  earlier in this session, given as blanket authorization after the O/P
  barrier mechanism was independently validated.

Baseline: `/run/media/Yatsuiii/Windows-SSD/custody-p7-verify/.venv/bin/python
-m unittest discover tests` = 484/484 on this worktree at 16d3459-derived
history (verified earlier this session); custody/ and
tests/test_b7_production_equivalence.py must remain byte-identical to
16d3459, since this fix touches only scripts/p7_run.py.

Acceptance gates:
1. `_namespace_collections`/`_collection_counts`/`_cleanup` in
   scripts/p7_run.py enumerate every real Firestore collection whose name
   starts with the namespace prefix (via `raw.collections()`), not a fixed
   list of bare `{prefix}__{name}` names, so preflight/cleanup actually
   cover every sub-prefix cases A-M/N/O/P write to.
2. scripts/p7_run.py uses run04 identity and artifacts; RUN_ID/NAMESPACE_PREFIX
   and the three output paths are updated together.
3. The harness compiles, Ruff passes, and the local equivalence test
   (tests.test_b7_production_equivalence) still passes; `git diff --stat
   custody/ tests/` empty.
4. Namespace custody_p7_b7_20260825_run04 confirmed empty (via the fixed,
   correctly-scoped preflight) before execution.
5. Committed and pushed before execution; local HEAD equals remote branch
   SHA, verified by independent fetch, before running against real
   Firestore.

Verification: `.venv/bin/python -m py_compile scripts/p7_run.py`;
`~/.local/bin/ruff check scripts/p7_run.py`; `.venv/bin/python -m unittest
discover tests` (484/484); commit/push/local==remote check; then execute
`scripts/p7_run.py --i-understand-this-spends-real-firestore-quota` for
real and record the result honestly, including any recovery-bound miss.

Status: active
