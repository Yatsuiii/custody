# P7 real-Firestore harness design note

Status: harness built and frozen; not yet executed against real Firestore.

## What this reuses vs. what is new

- Cases A1, A2, B-M: reused **unmodified** from
  `tests/test_b7_production_equivalence.py` (`_run_treatment`,
  `_load_scoring_table`, `_PostActionScorer`) via monkeypatching
  `tests.test_b7_production_equivalence._world` for the duration of the run,
  so each `_world()` call gets a fresh `FirestoreAuthorityStore` instead of
  `InMemoryAuthorityStore`. No case construction, expected outcome, or metric
  definition is redefined. This is the same `_load_scoring_table()` and
  `_PostActionScorer.score()` used by the frozen local proof.
- Cases N (restart), O (action/revocation race), P (killed writer): the local
  versions use SQLite triggers and Python threads/subprocess against a local
  file, which do not exist against real Firestore. These are reimplemented
  against real Firestore with real independent OS processes
  (`multiprocessing`, spawn context), preserving the same required results
  from `research/production_b7/EQUIVALENCE_TEST_PLAN.md`.

## New mechanism: transaction barrier

Production code (`custody/firestore_store.py`) is not modified. The barrier
needed for cases O and P is implemented entirely in the harness's own
Firestore client wrapper (`_P7Client.transaction()`), which monkeypatches
the bound `.get` / `.create` methods on the real `firestore.Transaction`
object it hands back to `custody/firestore_store.py`'s `_run_transaction`.
This works because `FirestoreAuthorityStore._run_transaction` calls
`self._client.transaction()` -- and the harness controls what `self._client`
is (a namespaced, instrumented client), exactly as the existing, previously
verified `scripts/firestore_contract_probe.py::_NamespacedClient` does for
namespacing alone.

- **Case O** arms a pause on the first `transaction.get()` matching the
  `O-DESC` document during the action's evaluation transaction. The main
  thread waits for that pause, commits a real revocation, then releases the
  paused transaction. This forces the action's authoritative read to observe
  the already-committed revocation, matching the plan's required ordering
  ("gateway reads candidate, revocation commits at the barrier, gateway
  performs final authoritative check").
- **Case P** arms a pause on the first `transaction.create()` in a real
  subprocess's `admit_source` transaction, signals the parent process via a
  `multiprocessing.Event`, and the parent sends `SIGKILL` before ever
  releasing the barrier. Firestore's transaction atomicity means no partial
  write can have reached the server, which is verified by reading the
  namespace from a second, freshly connected client after the kill.

## Known limitation, stated honestly

This barrier is deterministic and repeatable (unlike a pure network-timing
race), but it is a **new mechanism**, not something proven elsewhere in this
repository before this session. It has not yet been exercised against real
Firestore; correctness of the monkeypatch (that `_run_transaction` truly
routes through `self._client.transaction()` for a namespaced, non-fake
client) was verified by reading `custody/firestore_store.py` directly, not
by a dry run, because no offline fake Firestore double with matching
transaction semantics exists in this repository to test against safely.

## Resource policy and identity

- run_id: `p7-b7-20260824-run01`, namespace prefix
  `custody_p7_b7_20260824_run01` -- does not reuse or derive from any prior
  identity found in this repository (`p7-b7-20260824-ec32e4e31d21`, `-obs01`,
  `-codec01`).
- Ceiling: reads<=1500, writes<=200, deletes<=200, cost<=$0.01,
  runtime<=600s, recovery bound 90s (unchanged from the values stated for
  this project).
- The script refuses to run without an explicit
  `--i-understand-this-spends-real-firestore-quota` flag, refuses to run if
  its output files already exist, and refuses to run if the namespace is not
  empty.

## Not yet done

Live execution against real Firestore. That is a separate, explicit step
requiring its own go-ahead, per this session's contract.
