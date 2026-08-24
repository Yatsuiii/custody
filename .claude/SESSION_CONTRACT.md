Objective: Run and freeze a fresh O/P transaction-barrier contract probe
against the corrected P7 harness. This is infrastructure evidence only, not
P7, a security experiment, or a B7 efficacy test.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: probe/p7-barrier-contract-20260825-03
Parent: p7/b7-live-20260825-run02 @ 8ee72faeda2f83c4f925f405a8f4394d7c7661da
        (corrected harness; MUST NOT be modified by this probe)

Fresh probe identity:
- probe_id: p7-barrier-contract-20260825-03
- namespace: custody_p7_barrier_contract_20260825_03
- result: research/production_b7/P7_BARRIER_CONTRACT_PROBE_03_RESULT.json

Allowed files:
- scripts/p7_barrier_contract_probe_03.py
- research/production_b7/P7_BARRIER_CONTRACT_PROBE_03_RESULT.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to scripts/p7_run.py, custody/, or tests/.
- No reuse or amendment of probe identities -01/-02 or their evidence.
- No use of P7 run02 identity or P7 output files.
- No import of the P7 scorer or frozen attack cases.
- No execution until this probe code and contract are committed, pushed, and
  local HEAD equals origin's branch SHA.

Acceptance gates:
1. The probe imports _Barrier, _Counters, _P7FirestoreApi, and _P7Client from
   scripts.p7_run at harness SHA
   8ee72faeda2f83c4f925f405a8f4394d7c7661da; it does not copy their source.
2. O proves a production-normalized `_FirestoreTransactionPort.get` reaches
   the corrected `batch_get_documents` barrier, an independent Firestore
   client commits while paused, release completes without deadlock, and the
   delayed read observes that external commit.
3. P proves the real Transaction.create barrier is reached in an independent
   spawned process, SIGKILL occurs before commit, and a fresh read finds no
   partial probe state.
4. The script writes exactly one terminal result artifact, records timestamped
   event evidence plus source digests, records a fresh preflight and cleanup,
   and exits 0 only when both O and P are PASS.
5. After execution, the result artifact is committed and pushed separately;
   local and remote SHAs are independently matched before reporting the
   outcome. Only a dual PASS permits the label
   P7-BARRIER-INFRASTRUCTURE-SUPPORTED and a request for separate user
   authorization of actual P7.

Verification before execution:
- `/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python -m py_compile
  scripts/p7_barrier_contract_probe_03.py`
- `/home/Yatsuiii/.local/bin/ruff check scripts/p7_barrier_contract_probe_03.py`
- `git diff --stat -- scripts/p7_run.py custody tests` is empty;
- commit/push/local==remote checks for this probe branch.

Status: active
