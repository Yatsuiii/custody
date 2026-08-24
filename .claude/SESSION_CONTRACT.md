Objective: Run a CORRECTED O-BARRIER CONTRACT PROBE (probe 02). Not P7, not a
security experiment, not a B7 efficacy test. The prior probe
(probe/p7-barrier-contract-20260824-01, evidence 21e23a9) found its own
txn_body called `transaction.get(doc_ref).to_dict()` and crashed, because
installed google-cloud-firestore 2.28.1 returns iterator semantics from
`Transaction.get`. This probe corrects ONLY that read call by using the real,
unmodified `custody.firestore_store._FirestoreTransactionPort` (imported, not
reimplemented) so the read exercises the same production-normalized path as
frozen P7 Case O. No other change: _Barrier, _P7Client, the transaction
interception strategy, the pause point, and release semantics are reused
byte-identical from the frozen harness.

Branch: probe/p7-barrier-contract-20260824-02
Parent: p7/b7-live-20260824-run01 @ 085c4d5a9a89d0ae932f5a4814af5620f0223306
        (frozen P7 harness; MUST NOT be modified or moved by this work)

Allowed files:
- scripts/p7_barrier_contract_probe_o2.py
- research/production_b7/P7_BARRIER_CONTRACT_PROBE_O2_RESULT.json
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to scripts/p7_run.py, custody/*, or tests/test_b7_production_equivalence.py.
- No edit to _Barrier, _P7Client, _Counters, the transaction interception
  strategy, the pause point, or release semantics -- imported unmodified from
  scripts.p7_run; digests verified to match the frozen harness before running.
- No use of run_id p7-b7-20260824-run01 or namespace custody_p7_b7_20260824_run01.
- No reuse of probe 01's identity/namespace (p7-barrier-contract-20260824-01 /
  custody_p7_barrier_contract_20260824_01); this probe uses -02 throughout.
- No amendment of probe 01's frozen FAIL evidence (21e23a9); it stands as-is.
- No import of the P7 scorer or any frozen attack case.
- Execution against real Firestore under the new scratch identity
  (p7-barrier-contract-20260824-02 / custody_p7_barrier_contract_20260824_02)
  is authorized for this probe only, per explicit user instruction. P7 itself
  remains not authorized.
- P case is not rerun/redesigned in this session; probe 01's P PASS stands as
  the control.

Baseline: N/A -- this probe does not touch custody/ or tests/; `git diff
--stat custody/ tests/ scripts/p7_run.py` empty is the only relevant
no-drift check.

Acceptance gates:
1. Before execution: sha256 of _Barrier and _P7Client source, computed from
   the imported `scripts.p7_run` module, matches the digests recorded in
   probe 01's frozen evidence (_Barrier=868ef667a59967747b7313d86cfaea211
   bfdc03472711cdc4afc16455b36ca93, _P7Client=0b1a3ecbf06a7af4d4597749ba44
   a55781c022c3a626414696b3e144c9917191). If either differs: STOP, report
   BARRIER-CODE-DRIFT, do not proceed to execution.
2. The O txn_body reads via `custody.firestore_store._FirestoreTransactionPort
   .get(doc_ref)` (imported unmodified), not a raw `transaction.get()` call,
   so it faithfully exercises the same call path FirestoreAuthorityStore uses.
3. Records T1-T8 (transaction start, barrier reached, parent observes,
   independent commit while paused, release, resume via production-normalized
   read, resulting behavior, fresh-client final reread) with monotonic
   timestamps, plus callback invocation count and explicit retry-observed
   YES/NO.
4. Exactly one terminal artifact with one of PASS/FAIL/BLOCKED; the script's
   exit code must not be 0 unless the artifact records O-BARRIER PASS.
5. Fresh scratch namespace confirmed empty pre- and post-run; cleanup result
   recorded in the same artifact.

Verification: `python -m py_compile scripts/p7_barrier_contract_probe_o2.py`;
run it against real Firestore; inspect the single result artifact for
attributable T1-T8 evidence; `git diff --stat custody/ tests/
scripts/p7_run.py` empty.

Status: active
