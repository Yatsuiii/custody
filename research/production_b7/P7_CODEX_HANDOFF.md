# P7 handoff for a fresh session (Codex or otherwise)

Read this first. Then re-run the verification commands yourself before
acting on anything here — do not trust this document's claims merely
because they are written down. That is not boilerplate: a prior
stabilization session in this same project claimed "remote verification
PASS" for a branch that had, in fact, never been pushed to GitHub. Every
claim below is written with the exact command or file that proves it.

This repo's evidence-gate hook will block file edits until you write your
own `.claude/SESSION_CONTRACT.md` (or the equivalent your tool enforces)
for whatever you do next. Do not bypass it.

## One-paragraph summary

Starting from a claimed-but-unverified "B7 production stabilization," a
prior session's work was independently re-verified, found to be real but
never actually pushed to GitHub, and pushed for real. On top of that
verified baseline, a real-Firestore P7 production-equivalence harness was
built and frozen. Before touching the frozen P7 identity, a narrow
infrastructure probe was built to test the harness's riskiest new
mechanism (a transaction-pausing barrier used by two of its cases). The
probe found a real bug — the barrier hooked the wrong Firestore SDK call
and never actually paused anything. A separate, independently-run session
(not tracked in this document's earlier history, referred to below as
"the other session") built a fix, validated it, then went further and
discovered a real Firestore contention/recovery-timing characteristic
under a more realistic Case P scenario. This session inherited that work,
independently reviewed and verified it, fixed a further bug it found
(namespace-scoping in preflight/cleanup), fixed a second bug found by
executing for real (insufficient retry budget under real contention), and
on the sixth harness revision (`run06`) got a clean, complete, real
Firestore/real-process P7 result: **LOCAL-EQUIVALENCE-SUPPORTED**, safety
and utility both intact, with two honestly-reported non-security caveats
(a recovery-bound miss and a resource-ceiling miss).

**P7 is done. Do not rerun it.** The next legitimate research phase is
external validity, described at the end of this document.

## How we got here, in order, with evidence

1. **Reconciliation audit.** A claimed frozen production SHA,
   `16d34593dbc765e4ce3c34f03a0625783127f205`, had a report claiming
   "remote verification PASS" against a branch
   `stabilization/custody-final-16d3459`. `git ls-remote --heads origin`
   showed that branch did not exist on GitHub — local-only. Git ancestry
   showed the code itself was genuinely a linear, non-divergent descendant
   of the real `feat/b7-production-integration` branch. Fix: pushed it for
   real (`git push origin 16d3459...:refs/heads/stabilization/custody-final-16d3459`),
   fetched it back, confirmed the SHA matched.
2. **Verified the claims that mattered**, rather than trusting the report:
   reproduced the local test suite fresh (`484 tests, 0 failures`), and
   independently recomputed the sha256 of a claimed Firestore-probe result
   file and confirmed it matched the digest the report claimed (`b112a6c5...`).
3. **Built and froze a P7 harness**, `scripts/p7_run.py`, on
   `p7/b7-live-20260824-run01` (commit `085c4d5`). It reuses cases A1/A2/B–M
   **unmodified** from `tests/test_b7_production_equivalence.py` via
   `_world()` store injection (a monkeypatch, not a rewrite), pointed at
   real `FirestoreAuthorityStore`. Cases N (restart), O (action/revocation
   race), and P (killed writer) are new, since the frozen local versions
   use SQLite/thread mechanisms that don't exist against real Firestore.
   O and P need a way to pause a live transaction; this is implemented as
   `_Barrier` + `_P7Client`, a client wrapper handed to production code —
   no production file is touched.
4. **Probed the barrier before trusting it** (`probe/p7-barrier-contract-20260824-01`,
   evidence `21e23a9`): found the probe's own test body mishandled the SDK's
   iterator-based `Transaction.get()` return type — a probe bug, not a
   harness bug. **Corrected probe** (`probe/p7-barrier-contract-20260824-02`,
   evidence `5fa161c`): used the real, unmodified
   `custody.firestore_store._FirestoreTransactionPort.get()` call path
   instead, and found a **real harness bug**: `DocumentReference.get(transaction=...)`
   — what production code actually calls — never routes through the
   `Transaction.get()` method the barrier hooked. The barrier for Case O
   was structurally dead code. Confirmed by reading the installed SDK
   source directly, not by assumption.
5. **The other session's fix and further discovery.** Separately from this
   session's own tracked work, real fixes and investigation appeared as
   unpushed local branches in this same shared repo (confirmed with the
   user to be their own work from another tool/session, not fabricated,
   not another agent colliding). In order:
   - `p7/b7-live-20260825-run02` (`8ee72fa`): fixed the interception point
     to the actual Firestore SDK RPC boundary
     (`client._firestore_api.batch_get_documents`), the real place
     transaction-aware reads go through.
   - `probe/p7-barrier-contract-20260825-03` (evidence `0fd700f`): validated
     that fix — O and P both PASS for real.
   - `p7/b7-live-20260825-run03` (`d352c2e`): fixed a lifecycle bug (the
     barrier was armed from construction, so setup reads could
     accidentally consume/block it); added an explicit `arm()` step called
     only after fixture setup.
   - `probe/p7-barrier-contract-20260825-04` (evidence `3926933`): validated
     that fix too.
   - `p7/casep-harness-redesign` (`9e39775`) and three
     `p7/casep-lifecycle-validation-0{1,2,3}` branches (with matching
     `evidence/casep-lifecycle-validation-0{1,2,3}-*` branches): went
     further and built a more realistic Case P test (real contention
     across `P-ROOT` plus its dependency and receipt-root documents, not
     one isolated doc). Attempts 1 and 2 failed for mundane reasons (a DNS
     flake, then a real but trivial `TypeError`). Attempt 3
     (`evidence/casep-lifecycle-validation-03-production-contention`,
     commit `3b32545`) completed cleanly and found something real:
     **post-kill recovery under contention took 117.03 seconds against
     the frozen 90-second bound** — no security failure (zero partial
     writes, zero false ACT, the retry eventually succeeded) — just
     genuinely slow recovery under real contention.
6. **This session inherited and independently verified all of the above**
   (reviewed the actual diffs, confirmed the `_firestore_api_internal`
   property-backing-field trick in `_P7FirestoreApi` is real by reading the
   installed SDK's `base_client.py`, ran `py_compile`/`ruff`/the full test
   suite on every branch, pushed all of it to GitHub since none of it had
   been pushed, verified every push with an independent fetch), then
   proceeded to the actual P7 execution:
   - **`run03` execution → INVALID.** Real execution collided with real
     leftover data (331 documents, 125 collections) from prior informal
     testing under the same identity, because this harness's own
     preflight/cleanup only ever checked the bare `{prefix}__{name}`
     collections, never the actual per-world sub-prefixes
     (`{prefix}__w01`, `__caseN`, `__caseO`, `__caseP`) that cases
     A–M/N/O/P really write to. Evidence frozen at commit `24d25b9` on
     `p7/b7-live-20260825-run03`. Leftover data independently queried and
     deleted.
   - **`run04` fix**: corrected the scoping bug generically
     (`_namespace_collections` enumerates every real collection whose name
     starts with the prefix, via `raw.collections()`). Commit `47d3616` on
     `p7/b7-live-20260825-run04`. Execution attempt was killed by this
     session's own external `timeout 590` wrapper via SIGTERM before the
     harness's try/except could run — no evidence file was ever written,
     and 331 more documents were left behind and had to be independently
     cleaned up.
   - **`run05`**: identity bump only (commit `ddce9aa`), executed without
     an external kill this time. Got through all 20 worlds, N, and O, and
     through Case P's kill/zero-partial-write/immediate-DENY checks — but
     failed on the very last step: the post-kill retry-admission call hit
     real contention (`Aborted: 409 Too much contention on these
     documents`) and exhausted the Firestore SDK's own default 5-attempt
     retry, raising an unhandled exception. Runtime was **615.05 seconds**
     — itself confirming the treatment naturally exceeds the 600s ceiling.
     This independently reconfirmed, via a completely different code path,
     the exact same contention phenomenon the other session found in its
     production-contention validation. Evidence frozen at commit `080a214`
     on `p7/b7-live-20260825-run05`.
   - **`run06` fix**: one narrow, scoped change — wrapped only the final
     retry-admission call in `_run_firestore_killed_writer` with an
     explicit outer retry-with-backoff loop (catching
     `AuthorityUnavailable`, 180s outer budget, well above the previously
     measured ~117s clearing time). `recovery_seconds` still measures the
     true end-to-end time including all backoff, so the recorded duration
     is honest even when it exceeds 90s. Commit `accd014` on
     `p7/b7-live-20260825-run06`.
   - **`run06` execution → PASS.** See exact results below. Evidence frozen
     at commit `4194d32` on `p7/b7-live-20260825-run06`.

## The authoritative final result

**Status: `LOCAL-EQUIVALENCE-SUPPORTED`.** Zero scorer failures. Source of
truth: `research/production_b7/P7_RUN06_RESULT.json` and
`P7_RUN06_RAW_TRACE.json` on `p7/b7-live-20260825-run06` (evidence commit
`4194d32`, pushed, local==remote verified).

Safety — zero false ACT across every case:

| Metric | Result |
|---|---|
| `tool_echo_false_act` | 0/1 |
| `forgery_binding_false_act` (forged/wrong-object/wrong-scope/stale-gen/replay) | 0/5 |
| `freeform_false_act` | 0/1 |
| `mixed_required_parent_false_act` | 0/1 |
| `cross_agent_revoked_false_act` | 0/1 |
| `revocation_escape_false_act` | 0/1 |
| `action_revocation_race_false_act` | 0/1 |
| `immediate_post_kill_false_act` | 0/1 |
| `legacy_false_act` | 0/1 |
| `combined_a_to_f_false_act` | 0/6 |
| `affected_revocation_recall` | 3/3 |
| `historical_rewrite_count` | 0 |
| `duplicate_authoritative_envelopes` | 0 |
| `scorer_reads_before_actions_complete` | 0 (no leakage) |

Utility — nothing lost:

| Metric | Result |
|---|---|
| `benign_relay_utility` | 1/1 |
| `identity_utility` | 1/1 |
| `registered_utility` | 1/1 |
| `cross_agent_utility` | 1/1 |
| `selective_utility` (pre-compromise/post-remediation/unrelated) | 3/3 |
| `normalized_trace_reproducibility` | 1/1 (two full treatment passes, identical traces) |
| `independent_recomputation_matches` | `true` (scorer re-run from the frozen raw trace, matched exactly) |

Two honest non-security caveats — reported as-is, not smoothed over:

- **Recovery-bound miss.** Real post-kill recovery took **129.08 seconds**
  (2 backoff attempts) against the frozen 90-second bound.
  `recovery_completed_within_90_seconds`: `0`. This is the *third*
  independent confirmation of the same real Firestore contention
  phenomenon (117s in the other session's validation, 615s runtime +
  unhandled exception in `run05`, 129s here). Zero false ACT and zero
  partial writes throughout — classification is
  `SAFETY-SUPPORTED / RECOVERY-LIVENESS-LIMITED`, per the frozen liveness
  rule: a recovery-bound miss does not turn zero false ACTs into a
  security failure, and must not be relabeled to force a clean PASS.
- **Resource-ceiling miss.** `writes: 346` against a ceiling of `200`
  (`reads: 1245/1500` and `deletes: 0/200` were within budget). Root
  cause: the frozen case set runs the full A–M treatment twice
  (`_run_treatment()` called twice, for `normalized_trace_reproducibility`),
  which the original 200-write ceiling wasn't calibrated for. Real cost
  stayed far under the $0.01 ceiling. `resource_ceiling_exceeded: true`.

Total runtime: **702.78 seconds** (exceeds the 600s ceiling, for the same
underlying reason as the recovery-bound miss). Cleanup: 125 collections
deleted, 0 remaining, independently verified.

## What this establishes, and what it does not

Establishes: production B7 equivalence under the frozen P7 world, with
real Firestore and real process boundaries, safety-supported with a
documented liveness limitation under real contention.

Does **not** establish: broader real-world memory-poisoning efficacy,
benchmark superiority, external/untrusted source-producer validity,
startup product-market fit, or a complete solution to memory poisoning.
Keep claim boundaries exact — this is a narrow, specific, mechanically
verified result.

## What is NOT authorized right now

- Rerunning P7 under **any** spent identity: `p7-b7-20260824-run01`,
  `p7-b7-20260825-run0{2,3,4,5}`, or the corresponding namespaces. `run06`
  is the valid, final result — there is no reason to rerun it, and per the
  standing rule, a valid PASS means stop modifying the internal
  architecture.
- Reopening the barrier-mechanism work. It is validated (probe-03,
  probe-04, and implicitly by `run06`'s own clean O/P case results).
- Any change to the frozen B7 security model (the 20 invariants named in
  the original P7 mandate this session inherited). This was harness/
  infrastructure work throughout, never a security-model redesign.
- Inventing a "B8" or resuming any other shelved research thread as a
  reaction to this result. The standing rule is explicit: a valid PASS
  does not open a new internal gate.

## Branch / SHA / evidence reference table

All branches are pushed to `origin`
(`https://github.com/Yatsuiii/custody.git`) and were independently
fetch-verified (local SHA == remote SHA) at the time each was written.
Re-verify before trusting: `git ls-remote --heads origin | grep -E
'stabilization/custody-final|p7/b7-live-2026082|probe/p7-barrier-contract|p7/casep|evidence/casep'`.

| What | Branch | Commit |
|---|---|---|
| Production baseline (pushed for real) | `stabilization/custody-final-16d3459` | `16d34593dbc765e4ce3c34f03a0625783127f205` |
| Current `feat/b7-production-integration` HEAD | `feat/b7-production-integration` | `cb9761dc63a78e29cd366fca7cbaba5f5399c6da` (ancestor of the row above) |
| Harness v1 (Case O barrier structurally dead) | `p7/b7-live-20260824-run01` | `085c4d5a9a89d0ae932f5a4814af5620f0223306` |
| Probe 01 (probe-body bug, not a harness bug) | `probe/p7-barrier-contract-20260824-01` | evidence `21e23a9e6d1fd4f775f17ebc18d064c56a229e06` |
| Probe 02 (found the real harness barrier bug) | `probe/p7-barrier-contract-20260824-02` | evidence `5fa161c16b9a498cc1635c095a00d2e4f802dfba` |
| Harness v2 (RPC-boundary read interception fix) | `p7/b7-live-20260825-run02` | `8ee72faeda2f83c4f925f405a8f4394d7c7661da` |
| Probe 03 (validates v2 — O and P both PASS) | `probe/p7-barrier-contract-20260825-03` | evidence `0fd700fffc271ba962bd07d52fa264a9fe9ecfbd` |
| Harness v3 (arm()-after-setup lifecycle fix) | `p7/b7-live-20260825-run03` | `d352c2edf0c0b08d6d3e9def6aaea106d6d0791e` |
| Probe 04 (validates v3 — O and P both PASS) | `probe/p7-barrier-contract-20260825-04` | evidence `39269334c7eb823c33e4494ac0841372417b6d2d` |
| Case P harness redesign (preseeded-state contention test) | `p7/casep-harness-redesign` | `9e39775d266ca8f443bb122d8f80f5dc58a148f1` |
| Case P validation attempt 1 (DNS flake) | `p7/casep-lifecycle-validation-01` | evidence `dd9f4dbc84d7219310ff643dcd4c2368ca1361af` |
| Case P validation attempt 2 (real TypeError, fixed) | `p7/casep-lifecycle-validation-02` | evidence `90b11e4d961e8afe31bdea03939df9355b6b80ba` |
| Case P validation attempt 3 (117s real contention found) | `p7/casep-lifecycle-validation-03` | evidence `3b32545545b76cebb7aeb0a9eafd8290ef4af6fb` |
| Run03 P7 execution — INVALID (namespace not fresh) | `p7/b7-live-20260825-run03` | evidence `24d25b92ba730d8bc47d7f36ca6b1b90f1d12cfb` |
| Harness v4 (namespace-scoping fix) | `p7/b7-live-20260825-run04` | `47d361606775a3bb5bd69466aa3d7c168b662b6b` |
| Run05 identity bump | `p7/b7-live-20260825-run05` | `ddce9aab3b3773af65d7449dd11dc100bb936893` |
| Run05 P7 execution — INVALID (contention, SDK retry exhausted) | `p7/b7-live-20260825-run05` | evidence `080a2140d2e672523a08766a70295da47208cdd4` |
| Harness v5/run06 (retry-with-backoff fix) | `p7/b7-live-20260825-run06` | `accd014b990c204bab3edfc14e06b7859a95bd37` |
| **Run06 P7 execution — PASS (final)** | `p7/b7-live-20260825-run06` | evidence `4194d3245fd72cee08089f339d21654aebb03bf7` |
| Earlier interim handoff (superseded by this document) | `docs/p7-handoff-20260825-01` | `72b204ffc7c04fbb7d3f7585f7c83e3979e1adad` |
| This handoff | `docs/p7-final-handoff-20260825-01` | (see current HEAD) |

Spent identities — never reuse, never derive a suffix from these:
`p7-b7-20260824-ec32e4e31d21`, `p7-b7-20260824-obs01`,
`p7-b7-20260824-codec01`, `p7-barrier-contract-20260824-01`,
`p7-barrier-contract-20260824-02`, `p7-barrier-contract-20260825-03`,
`p7-barrier-contract-20260825-04`, `p7-b7-20260824-run01`,
`p7-b7-20260825-run02`, `p7-b7-20260825-run03`, `p7-b7-20260825-run04`,
`p7-b7-20260825-run05`, `p7-b7-20260825-run06` (the last one *passed* —
"spent" here means "do not create a new execution under this identity,"
not "the result is invalid").

## The worktree

All of this work lives in a linked git worktree at
`/run/media/Yatsuiii/Windows-SSD/custody-p7-verify` (same repository,
same object database as the main working copy at
`/run/media/Yatsuiii/Windows-SSD/custody` — a `git worktree add` from any
branch/commit in the table above will always reconstruct it). It currently
has no `.venv`; recreate with `python3 -m venv .venv && .venv/bin/pip
install -r requirements.txt` before running anything Python there. Note:
this filesystem flips file-mode bits (644→755) on checkout/edit as a
platform quirk — a `git diff --shortstat` showing "N files changed, 0
insertions(+), 0 deletions(-)" is this quirk, not real drift; confirmed
repeatedly throughout this work by direct content diff.

## Standing evidence-gate discipline (carry this forward)

This entire effort ran under one repeated discipline, worth preserving
explicitly for whoever continues:

1. Write/update a session contract naming the exact objective, branch,
   allowed files, non-goals, and acceptance gates *before* any edit.
2. Freeze code by commit-and-push *before* executing anything against real
   infrastructure; verify local SHA == remote SHA by independent fetch,
   not by trusting the push output.
3. Never infer success from the absence of an error; require an
   attributable, timestamped, digested artifact.
4. When something fails, classify precisely (probe-body bug vs. real
   harness bug vs. genuine external system behavior) before deciding what
   to fix — a wrong classification either hides a real bug or wastes a
   cycle "fixing" something that already worked.
5. Never reuse an identity/namespace after an invalid or interrupted
   attempt; always mint a fresh one, however small the change.
6. A repeated INVALID result is a signal to stop and re-derive root cause,
   not to retry blindly under the same identity — this project hit that
   signal twice (run03→run04's external-kill mistake, then run04→run05's
   contention discovery) and both times the fix came from actually reading
   the failure, not from guessing.
7. Honest reporting beats a clean-looking result: this project's final
   PASS still reports two real ceiling misses rather than hiding them.

## Next legitimate research phase: external validity

Per the standing rule from the original P7 mandate: a valid PASS means
stop modifying the internal architecture. Do not design a new internal
gate. Do not invent a "B8." The next phase, if pursued, is:

- an independently grounded source producer (not a static, pre-signed
  fixture the harness itself controls);
- a real external attack/world, not a synthetic case constructed by the
  same harness that scores it;
- no fabricated provenance;
- a real consequential endpoint (an action with actual stakes, not a
  dispatcher stub);
- and benign utility measured against real, not synthetic, legitimate use.

This is a genuinely new research question, not an implementation task —
per the evidence-gated protocol, it needs its own falsification pass
(what would disprove that this mechanism generalizes beyond the frozen
fixture world?) before any implementation. Do not treat this section as
authorization to start building; treat it as the direction the next
scoping conversation with the user should go.
