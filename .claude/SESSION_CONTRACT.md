Objective: Run and freeze a fresh O/P transaction-barrier probe against the
run03 harness, whose barriers are explicitly armed after fixture setup. This
is infrastructure evidence only, not P7 or B7 efficacy evidence.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: probe/p7-barrier-contract-20260825-04
Parent: p7/b7-live-20260825-run03 @ d352c2edf0c0b08d6d3e9def6aaea106d6d0791e
        (fresh lifecycle-corrected harness; MUST NOT be modified)

Fresh probe identity:
- probe_id: p7-barrier-contract-20260825-04
- namespace: custody_p7_barrier_contract_20260825_04
- result: research/production_b7/P7_BARRIER_CONTRACT_PROBE_04_RESULT.json

Allowed files:
- scripts/p7_barrier_contract_probe_04.py
- research/production_b7/P7_BARRIER_CONTRACT_PROBE_04_RESULT.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to scripts/p7_run.py, custody/, or tests/.
- No reuse of probe identities -01/-02/-03.
- No use of P7 run03 identity or P7 output artifacts.
- No execution until this probe code is committed, pushed, and local HEAD
  equals the remote branch SHA.

Acceptance gates:
1. The probe imports _Barrier, _Counters, _P7FirestoreApi, and _P7Client
   from the run03 harness SHA d352c2edf0c0b08d6d3e9def6aaea106d6d0791e;
   it does not copy their source.
2. O creates its document before `barrier.arm()`, then proves the armed
   production-normalized `_FirestoreTransactionPort.get` reaches the RPC
   barrier, observes an independent commit while paused, and resumes without
   deadlock.
3. P arms only after child setup, reaches Transaction.create, is SIGKILLed
   before commit, and a fresh read finds no partial state.
4. Exactly one result artifact records preflight, timestamped events, source
   digests, both terminal verdicts, and cleanup; exit code is 0 only on dual
   PASS.
5. The result is committed and pushed separately, with local==remote SHA
   verification. Only dual PASS permits requesting separate authorization for
   actual P7 run03.

Verification before execution:
- `/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python -m py_compile
  scripts/p7_barrier_contract_probe_04.py`
- `/home/Yatsuiii/.local/bin/ruff check scripts/p7_barrier_contract_probe_04.py`
- `git diff --stat -- scripts/p7_run.py custody tests` is empty;
- commit/push/local==remote checks for this probe branch.

Status: active
