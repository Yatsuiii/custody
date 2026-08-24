Objective: Run P7_TRANSACTION_BARRIER_CONTRACT_PROBE -- an infrastructure-only
probe (NOT P7, not a security experiment, not a B7 efficacy test) that proves
the transaction-barrier primitive used by frozen P7 cases O and P
(scripts/p7_run.py::_Barrier / _P7Client at commit
085c4d5a9a89d0ae932f5a4814af5620f0223306) behaves as that harness assumes
against the actually installed google-cloud-firestore SDK and real Firestore.
Imports _Barrier/_P7Client/_Counters directly from the frozen scripts/p7_run.py
(unmodified) rather than reimplementing them. Uses a separate scratch
namespace and writes no P7 run_id/result/raw/cleanup artifact.

Branch: probe/p7-barrier-contract-20260824-01
Parent: p7/b7-live-20260824-run01 @ 085c4d5a9a89d0ae932f5a4814af5620f0223306
        (frozen P7 harness; MUST NOT be modified or moved by this work)

Allowed files:
- scripts/p7_barrier_contract_probe.py
- research/production_b7/P7_BARRIER_CONTRACT_PROBE_RESULT.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to scripts/p7_run.py, custody/, or tests/test_b7_production_equivalence.py.
- No use of run_id p7-b7-20260824-run01 or namespace custody_p7_b7_20260824_run01.
- No P7 result/raw/cleanup artifact under any P7-recognized filename.
- No import of the P7 scorer (_PostActionScorer/_load_scoring_table) or any
  frozen attack case; this probe writes only plain scratch documents.
- No change to B7 semantics.
- Execution against real Firestore under the new scratch identity
  (p7-barrier-contract-20260824-01 / custody_p7_barrier_contract_20260824_01)
  is authorized for this probe only, per explicit user instruction; P7 itself
  (run_id p7-b7-20260824-run01) remains not authorized.

Baseline: N/A -- this probe does not touch custody/ or tests/, so the 484/484
local baseline is not re-verified by this contract; `git diff --stat custody/
tests/` empty is the only relevant no-drift check.

Acceptance gates:
1. scripts/p7_barrier_contract_probe.py imports _Barrier, _P7Client, _Counters
   from scripts.p7_run without copying or altering their source, and records
   sha256 digests of that source in its result artifact.
2. O-BARRIER: proves transaction.get() is intercepted at the expected call
   site, the pause is observed by the parent, an independent second Firestore
   client can commit while paused, release resumes the transaction without
   deadlock, and the resumed read observes the externally committed value.
3. P-BARRIER: proves transaction.create() is intercepted before commit, the
   parent observes the pause, SIGKILL terminates the child, and a fresh
   Firestore client finds zero partial/companion documents afterward.
4. Exactly one terminal result artifact
   (research/production_b7/P7_BARRIER_CONTRACT_PROBE_RESULT.json) with one of
   PASS/FAIL/BLOCKED per sub-probe and one overall outcome; the script's own
   exit code must not be 0 unless that artifact was written with outcome
   P7-BARRIER-INFRASTRUCTURE-SUPPORTED.
5. Scratch namespace is confirmed empty pre- and post-run; cleanup result is
   recorded in the same artifact, not a separate silent step.

Verification: `python -m py_compile scripts/p7_barrier_contract_probe.py`;
run it against real Firestore; inspect the single result artifact for
attributable pass/fail evidence (timestamps/event log) rather than inferring
success from absence of error; `git diff --stat custody/ tests/
scripts/p7_run.py` empty.

Status: active
