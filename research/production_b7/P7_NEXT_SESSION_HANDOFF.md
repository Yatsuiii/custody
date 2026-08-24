# P7 handoff — read this first, then verify it yourself

Do not trust this document's claims merely because they are written down.
The prior stabilization session's own "remote verification PASS" claim
turned out to be false (see "How we got here" below) — that failure mode is
exactly why every fact below is written with the branch/SHA/command that
proves it. Re-run the verification commands before acting on anything here.
This repo's evidence-gate hook will block edits until you write your own
`.claude/SESSION_CONTRACT.md` for whatever you do next — that is
intentional, do not bypass it.

## One-paragraph summary

We independently verified a claimed "stabilization" of the B7
production-integration branch, found its final commit was real but never
actually pushed to GitHub (only to local-only branches, despite the
session's own report claiming otherwise), pushed it for real, built and
froze a real-Firestore P7 harness on top of it, and then — before touching
the frozen P7 identity — built a probe to test only the harness's riskiest
new mechanism (a transaction barrier used by two of its cases). The probe
found a real bug: the barrier hooks the wrong Firestore SDK call, so it
never actually pauses the transaction it's supposed to pause for Case O.
P7 has **not** been run. It should not be run until that bug is fixed in a
new harness revision and re-verified.

## How we got here (chronological, with evidence)

1. **Reconciliation audit.** A prior stabilization session claimed a frozen
   production SHA `16d34593dbc765e4ce3c34f03a0625783127f205` with "remote
   verification PASS" against a branch `stabilization/custody-final-16d3459`.
   `git ls-remote --heads origin` showed that branch did not exist on GitHub
   — it was local-only. Git ancestry showed `16d3459` genuinely is a linear
   descendant of the current `feat/b7-production-integration` HEAD (no
   divergence, no missing commits either direction) — the *code* was fine,
   only the *publication claim* was false.
2. **Fix:** pushed `16d3459` for real:
   `git push origin 16d34593dbc765e4ce3c34f03a0625783127f205:refs/heads/stabilization/custody-final-16d3459`,
   then independently fetched it back and confirmed the SHA matched. This is
   now genuinely on GitHub.
3. **Verified, don't trust, the stabilization claims that mattered:**
   - Local test suite: reproduced myself on a fresh worktree at `16d3459`
     — `484 tests, 0 failures, 0 errors, 0 skipped`.
   - Real Firestore contract probe (19/19 ops, non-security, adapter-level):
     independently recomputed the sha256 of
     `research/stabilization/FIRESTORE_CONTRACT_PROBE_RESULT.json` and it
     matched the digest the report claimed (`b112a6c5...`). This one was
     real, unlike the "remote verification" claim.
4. **Built and froze a P7 harness** — `scripts/p7_run.py`, branch
   `p7/b7-live-20260824-run01`, commit
   `085c4d5a9a89d0ae932f5a4814af5620f0223306`, parent `16d3459`. It reuses
   cases A1/A2/B–M **unmodified** from
   `tests/test_b7_production_equivalence.py` via `_world()` store injection
   (monkeypatch, not a rewrite) pointed at real `FirestoreAuthorityStore`.
   Cases N (restart), O (action/revocation race), and P (killed writer) are
   new, real-Firestore, real-independent-process implementations, since the
   frozen local versions depend on SQLite triggers/threads that don't exist
   against Firestore. O and P need a way to pause a transaction mid-flight;
   this harness implements that as `_Barrier` + `_P7Client` — a client
   wrapper that monkeypatches the bound `.get`/`.create` methods on the real
   `firestore.Transaction` object it hands back to
   `custody/firestore_store.py`, entirely in harness code, no production
   change. Committed and pushed **before** any execution; confirmed
   local SHA == `origin/p7/b7-live-20260824-run01`.
5. **Did not run P7.** Instead, built a narrow infrastructure probe to test
   only the barrier mechanism, per explicit instruction, because it's new
   and unproven. Two rounds:
   - **Probe 01** (`probe/p7-barrier-contract-20260824-01`, evidence
     `21e23a9e6d1fd4f775f17ebc18d064c56a229e06`): P-barrier **PASS** (child
     process reached the barrier, parent SIGKILLed it, fresh client
     confirmed zero partial writes). O-barrier: the probe's own naive test
     body called `transaction.get(doc_ref).to_dict()` and crashed with
     `AttributeError: 'generator' object has no attribute 'exists'` —
     because `google-cloud-firestore==2.28.1`'s `Transaction.get()` returns
     iterator semantics, not a single snapshot (this exact fact is already
     documented correctly in
     `research/stabilization/FIRESTORE_SDK_CONTRACT.md`). This was a bug in
     the *probe's* test body, not in the reused `_Barrier`/`_P7Client` code
     — the mechanical barrier properties (interception, pause,
     parent-observes, independent-commit-while-paused, clean release, no
     deadlock) were all independently confirmed true from the event log
     before the crash.
   - **Probe 02** (`probe/p7-barrier-contract-20260824-02`, evidence
     `5fa161c16b9a498cc1635c095a00d2e4f802dfba`): corrected the read to go
     through the real, unmodified
     `custody.firestore_store._FirestoreTransactionPort.get()` — the exact
     call `FirestoreAuthorityStore` actually makes — instead of a raw
     `transaction.get()` call. Verified first (and it matched) that the
     `_Barrier`/`_P7Client` source digests were byte-identical to the frozen
     harness. Result: **the barrier was never reached.** The transaction
     completed in one invocation with zero pause. Root cause, confirmed by
     reading the installed SDK source directly
     (`.venv/lib/python3.14/site-packages/google/cloud/firestore_v1/document.py`,
     `DocumentReference.get`): when called as `document.get(transaction=t)`,
     it does **not** call `t.get(...)` at all — it builds its own request
     via `self._prep_batch_get(...)` and calls
     `self._client._firestore_api.batch_get_documents(...)` directly, using
     `t` only for request metadata. `_P7Client`'s barrier hooks the bound
     `.get` method on the `Transaction` object, so for reads it is
     structurally never invoked by the real production read path. (Case P
     is unaffected: `_FirestoreTransactionPort.create()` *does* call
     `transaction.create(...)` directly, which is why the P-barrier
     correctly intercepted it in probe 01.)

**This is a real, reproducible bug in the frozen P7 harness's Case O
mechanism** (`scripts/p7_run.py`, commit `085c4d5`), not a probe artifact.

## Branch / SHA reference table

| What | Branch | SHA / commit |
|---|---|---|
| Production baseline (frozen, pushed for real) | `stabilization/custody-final-16d3459` | `16d34593dbc765e4ce3c34f03a0625783127f205` |
| Current `feat/b7-production-integration` HEAD | `feat/b7-production-integration` | `cb9761dc63a78e29cd366fca7cbaba5f5399c6da` (ancestor of the row above, not divergent) |
| Frozen P7 harness (built, not yet executed as P7) | `p7/b7-live-20260824-run01` | `085c4d5a9a89d0ae932f5a4814af5620f0223306` |
| Barrier probe 01 (P PASS, O inconclusive/probe-bug) | `probe/p7-barrier-contract-20260824-01` | evidence `21e23a9e6d1fd4f775f17ebc18d064c56a229e06` |
| Barrier probe 02 (O FAIL, real harness bug found) | `probe/p7-barrier-contract-20260824-02` | evidence `5fa161c16b9a498cc1635c095a00d2e4f802dfba` |
| This handoff | `docs/p7-handoff-20260825-01` | (see current HEAD) |

All branches above are pushed to `origin` (`https://github.com/Yatsuiii/custody.git`)
and were independently fetch-verified to match local SHAs at the time each
was written. Re-verify with `git ls-remote --heads origin | grep -E
'stabilization/custody-final-16d3459|p7/b7-live-20260824-run01|probe/p7-barrier-contract'`
before trusting this table — do not assume it's still current.

Identities already spent / excluded — do not reuse, do not reuse suffixes
derived from them: `p7-b7-20260824-ec32e4e31d21`, `p7-b7-20260824-obs01`,
`p7-b7-20260824-codec01`, `p7-barrier-contract-20260824-01`,
`p7-barrier-contract-20260824-02`.

## What is authorized right now

Nothing that spends real Firestore quota. Specifically **not authorized**:

- Running `scripts/p7_run.py` with `--i-understand-this-spends-real-firestore-quota`
  (i.e., an actual P7 run under `run_id p7-b7-20260824-run01`).
- Any further barrier probe under probe identities `-01` or `-02` (spent).

## The exact next task

1. **Fix the Case O read-interception strategy** in a **new** harness
   revision. Do not edit `scripts/p7_run.py` in place on
   `p7/b7-live-20260824-run01` — that branch is frozen evidence for probe 01
   and 02's digest checks; branch from it instead (e.g.
   `p7/b7-live-20260825-run02` or similar, your call, just don't reuse `-01`
   naming). The fix needs `_P7Client`'s barrier to intercept whatever call
   `DocumentReference.get(transaction=...)` actually routes through at the
   RPC layer — e.g. wrapping `self._client._firestore_api.batch_get_documents`,
   or wrapping `DocumentReference.get` itself on the references handed out
   by `_P7Client.collection(...)`, rather than the `Transaction.get` bound
   method. Verify your fix against the *actual* installed SDK source before
   trusting any assumption about it, the way this session did — don't
   assume, read `document.py` and `transaction.py` in
   `google/cloud/firestore_v1/` directly.
2. **Re-run both O and P as a fresh probe pair** under a new probe identity
   (not `-01`/`-02`) against the corrected barrier, following the same
   discipline used this session: freeze the probe code by commit+push
   *before* execution, verify local==remote, run against real Firestore,
   freeze the result as a separate evidence commit, verify local==remote
   again.
3. **Only if both O and P probes PASS** on the corrected harness: report
   `P7-BARRIER-INFRASTRUCTURE-SUPPORTED` and explicitly ask the user to
   authorize an actual P7 run under the new harness's own fresh identity
   (not `p7-b7-20260824-run01`, which is tied to the harness commit that had
   the bug).
4. Do not, at any point in that sequence, modify `custody/*` or
   `tests/test_b7_production_equivalence.py`, and do not execute P7 itself
   without a separate, explicit go-ahead message from the user after step 3.

## Standing rules that still apply (carried over, not re-litigated)

- Frozen B7 security model (20 invariants) is unchanged and out of scope for
  this line of work — this is infrastructure/harness work, not a security
  redesign.
- No claim of "verified" without the command/digest that proves it, in this
  document or in the next session's report.
- A repeated `HARNESS-BARRIER-BUG` after this fix is evidence of deeper
  brittleness in the barrier approach itself, not something to patch around
  indefinitely — if the second fix also fails on real Firestore, that's a
  signal to reconsider the interception *strategy*, not just patch the call
  site again.
