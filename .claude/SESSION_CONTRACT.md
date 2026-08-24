Objective: Build and freeze a corrected real-Firestore P7 harness revision whose
Case O barrier intercepts the installed SDK's production-normalized read path.
This session fixes the harness only. It does not execute P7 or the fresh probe
pair; the probe pair is a separate artifact and must be frozen before execution.

Lane: optimization/research engineering — evidence-gated Firestore harness
infrastructure.

Branch: p7/b7-live-20260825-run02
Parent: p7/b7-live-20260824-run01 @ 085c4d5a9a89d0ae932f5a4814af5620f0223306
        (frozen harness; MUST NOT be modified)

New P7 identity reserved for a later, separately authorized run:
- run_id: p7-b7-20260825-run02
- namespace: custody_p7_b7_20260825_run02

Allowed files:
- scripts/p7_run.py
- research/production_b7/P7_HARNESS_DESIGN_NOTE.md
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/.
- No edit to tests/test_b7_production_equivalence.py.
- No edit to scripts/p7_run.py on p7/b7-live-20260824-run01.
- No execution of scripts/p7_run.py and no P7 quota spend.
- No reuse of P7 run01 or probe identities -01/-02.
- No claim that the barrier is supported until fresh O and P probes both pass.

Design decision: the harness owns the SDK-version-specific interception at one
deep boundary, _P7FirestoreApi.batch_get_documents. The installed SDK source
shows that DocumentReference.get(transaction=...) and Client.get_all(...,
transaction=...) call client._firestore_api.batch_get_documents directly;
Transaction.get() delegates to Client.get_all and is not the production read
boundary. The wrapper counts request documents, pauses only transaction reads,
and delegates every other API method. Transaction.create/set/delete hooks remain
for write counting and Case P's killed-writer barrier.

Baseline: frozen harness parent 085c4d5; production code and equivalence tests
must remain unchanged. The shared worktree's existing 100644->100755 mode-only
changes are unrelated and are not normalized by this work.

Acceptance gates:
1. Installed SDK source is read directly and the wrapper targets the exact
   batch_get_documents call used by DocumentReference.get(transaction=...).
2. scripts/p7_run.py compiles; the new API wrapper has no production/test
   imports beyond the existing harness imports; custody/ and tests/ have no
   content changes.
3. The new harness revision is committed and pushed, and local HEAD equals the
   remote branch SHA before any fresh probe executes.
4. A separate fresh probe branch uses the new harness SHA and identity
   p7-barrier-contract-20260825-03 / custody_p7_barrier_contract_20260825_03;
   it runs O and P only after its own code is committed and remote-verified.
5. Only if both fresh probes record PASS may the result be
   P7-BARRIER-INFRASTRUCTURE-SUPPORTED and may a user separately authorize the
   actual P7 run under p7-b7-20260825-run02.

Verification planned:
- direct read-through of installed google-cloud-firestore document.py and
  transaction.py;
- /run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python -m py_compile
  scripts/p7_run.py;
- source/diff inspection and no-drift checks for custody/ and tests/;
- commit/push/local==remote checks before probe execution.

Status: active
