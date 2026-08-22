# E2H-R1E — Durable Authority Integration (transactional recovery-bound correction)

Status: frozen preregistration/design only. No implementation, deployment, or
production change is authorized by this document.

Design verdict: **INFORMATIVE**. A safe real persistence environment was
verified read-only before this plan was written.

## 1. Lineage and question

Experiment ID: `E2H_R1E_DURABLE_AUTHORITY_INTEGRATION`.

Frozen E2G execution: `bd0fcd3af38b105f326dbe0e4f73149b6da67449`.
Parent E2H-R1D preregistration: `3e642a77cfc24d66c471c6fc83abf25349d232e1`.
Preserved R1D invalid execution commit:
`44c391de9730d6647ddcaa356b365233effdb455`.
R1D reached real Firestore state: policy documents, `R_OLD`, `C_CHILD`, and
`R_CLEAN` committed; `C_CRASH` did not commit. W was killed while a real
pessimistic transaction was live. A fresh W then exhausted finite transaction
attempts while the killed transaction's server-side contention had not yet
cleared. R1D therefore has classification `INVALID_RUNNER_EXCEPTION` /
`INTEGRATION-BLOCKED`; no scored Architecture A verdict was produced. The R1D
namespace is preserved and is not reused.

The only R1E change is runner/recovery treatment of this observed transient
contention state. Architecture A, all security fixtures, policy values,
variants A-H, schemas, gateway rules, security metrics, and security gates are
frozen equivalent to R1D. R1E must distinguish security failure from temporary
recovery contention and from recovery-liveness failure; it must never bypass a
transaction, overwrite an envelope, or turn contention into an ALLOW.

E2G preregistration: `3dbeb4faabdd9383c69609847626db4db7499f36`.
E2G canonical result digest:
`05707014de0ed008db4eadd4ab74f7aa21ae530ea4029e2218b448b5fa6e1bac`.

E2G proved G3 in one deterministic logical state machine. E2H tests the
unproven boundary: a real durable database, three independent processes,
process death/restart, concurrent policy change, stale application state, and
the real action decision reconstructed from durable data.

The single changed variable is the execution boundary: logical in-memory
state becomes Firestore-backed state read by fresh OS processes. Authority
semantics, policy literals, dependency algebra, and fail-closed rules remain
the E2G rules. This is not a production Custody port and makes no production
readiness claim.

## 1A. Verified Firestore transaction semantics

Verified on 2026-08-22 against the official Google documentation and the
installed repository virtual environment (`google-cloud-firestore==2.28.1`):

* [Data contention in transactions](https://docs.cloud.google.com/firestore/native/docs/transaction-data-contention)
  states that PESSIMISTIC server transactions lock documents they read,
  competing operations may be delayed or failed, and finite contention retries
  return `ABORTED: Too much contention on these documents`.
* [Transactions and batched writes](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions?hl=en)
  states that the lock deadline is 20 seconds, failed transactions release
  locks, and transactions fail after the lock deadline, 60-second idle
  expiration, or 270-second total transaction limit.
* [Firestore quotas and limits](https://docs.cloud.google.com/firestore/quotas?hl=en)
  independently specifies the 270-second transaction limit and 60-second idle
  expiration.
* [Python `Transaction`](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.transaction.Transaction)
  documents `max_attempts`; the installed client reports default
  `Transaction.max_attempts = 5`.
* [Python `transactional`](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.transaction)
  documents the decorator used to begin, retry, and commit the callback.

The installed client exposes contention as `google.api_core.exceptions.Aborted`
and wraps exhausted decorated attempts as `ValueError: Failed to commit
transaction in N attempts`, with the contention exception as its cause. A
non-contention authentication, malformed-request, or unrelated transport
exception remains an invalid integration execution; R1E does not relabel it as
security-safe contention.

The relevant bound for a killed, idle transaction is the documented 60-second
idle expiration, not the 270-second maximum for an active transaction. The
fixed recovery deadline is therefore:

    max(20 seconds lock deadline, 60 seconds idle expiration)
    + 30 seconds explicit scheduling/network margin
    = 90 seconds.

The 30-second margin is fixed before execution to cover four bounded fresh
process/barrier round trips; it is not selected from a successful outcome.
The 270-second overall limit is recorded for completeness but is not used to
extend an idle orphan-lock bound.

## 2. Environment audit and selection

The repository audit found an existing Firestore seam in
`custody/firestore_store.py`; its production collections are `custody`,
`revocations`, `revision_pins`, `auditor`, and `demotions`. The durable tests
use fakes and do not exercise a real process boundary. Existing Cloud Run and
Gateway/IAP resources are documented in `HANDOFF.md` but are shipping/demo
resources and are not touched by E2H.

Read-only environment checks confirmed:

* project `project-988bc9fe-092c-4b32-90c` is ACTIVE;
* Firestore database `(default)` is Firestore Native, `us-central1`, with
  `PESSIMISTIC` concurrency;
* the repository's ignored `.gcloud/application_default_credentials.json`
  exists; credential contents are never read into artifacts;
* `google-cloud-firestore` is already an installed repository dependency;
* no new Cloud Run service or GCP resource is required for this slice.

Environment A is selected: the existing owned Firestore database with a new
isolated collection prefix, accessed by local OS subprocesses. Environment B
is unnecessary. Environment C (Firestore emulator) is weaker and is not a
scored fallback. Environment D (SQLite/local persistence) is rejected because
E2D/E2G already covered that logical boundary. If the project, database,
credentials, or namespace cannot be verified at execution time, verdict is
`INTEGRATION-BLOCKED`; do not fake real persistence.

## 3. Exact namespace and cleanup

The exact environment is project `project-988bc9fe-092c-4b32-90c`, database
`(default)`, region `us-central1`, namespace prefix
`custody_research_e2h_r1e_20260822`.

Only these collections may be touched: `custody_research_e2h_r1e_20260822_policies`,
`custody_research_e2h_r1e_20260822_envelopes`,
`custody_research_e2h_r1e_20260822_dependencies`, and
`custody_research_e2h_r1e_20260822_controls`.

The preregistration-time read-only verification for this fresh namespace
returned zero documents in all four collections on 2026-08-22. This is
evidence of natural emptiness, not a guarantee; execution must re-check
the same four names immediately before its first write. A nonzero result
blocks the run without deletion or namespace substitution.

The recorded pre-registration limit-one counts are:

    policies = 0
    envelopes = 0
    dependencies = 0
    controls = 0

Before execution, read-only counts of these exact collections must be zero. If
any is non-empty, abort as `INTEGRATION-BLOCKED` rather than deleting unknown
data. Cleanup deletes only documents under these four prefixes and verifies
all four are empty. No production collection, live Memory Bank scope, Cloud
Run service, Gateway policy, or shipping branch is referenced.

Canonical artifacts record logical events and generations, never credentials,
PIDs, hostnames, or server timestamps.

## 4. Process topology

The runner starts three independent executable OS processes. Each creates its
own Firestore client and receives serialized runtime input only.

* **W — writer/admission:** reads policy/parents, writes immutable envelopes
  and dependencies, and never authorizes a consequential action.
* **P — policy control:** owns current policy documents and advances versions/
  generations transactionally; it never edits historical envelopes.
* **G — action gateway:** starts with zero memory after each restart, reads
  durable records and current policies, computes G3, and returns ALLOW/DENY.

G must not receive W's in-memory objects. PIDs and invocation identities are
diagnostic only; canonical traces use logical event sequence numbers.

## 5. Minimum durable schema

`PolicyRecord` documents live in `..._policies`, one current document per
canonical PolicyKey `(department, source, operation, revision, action_scope)`.
Fields are `policy_key`, `version`, `generation`, `role`, `caps`, and
server-provided `updated_at` (audit only). Generations are monotonic per key.

`AdmissionEnvelope` documents live in `..._envelopes`, keyed by `record_id`.
Immutable fields are `record_id`, `payload_digest`, `transform_class`,
`bound_caps`, `direct_parent_ids`, `support_root_ids`, `own_policy_key`,
`own_policy_version`, `own_granting_generation`, `admission_state`, and
server `admitted_at` (audit only). Only `COMMITTED` state can authorize;
`INCOMPLETE` is fail-closed state required for the partial-admission probe.

`AuthorityDependency` documents live in `..._dependencies`, keyed by
`(record_id, policy_key, root_record_id, action_scope)`. Fields are
`record_id`, `policy_key`, `granting_generation`, `root_record_id`, and
`action_scope`. The set is exactly the G3 parent-union plus the child's own
transform dependency. No weights, semantic labels, or parent pruning exist.

`..._controls` contains only barrier acknowledgements and test fault markers;
control documents are never authority inputs.

## 6. Datastore atomicity and authoritative reads

W uses the Firestore Python client's pessimistic transaction. It reads parent
envelopes/dependencies and the captured policy, then creates the envelope and
all dependency rows in one commit. The transaction either commits the
complete `COMMITTED` admission or leaves no authoritative admission. A
duplicate output ID is never overwritten: identical immutable bytes are an
idempotent replay; different policy-bound bytes return
`RETRY_POLICY_CONFLICT`.

P reads the current policy document in a transaction, checks the expected
generation, and writes exactly one next version/generation. An unexpected
generation is a conflict, never an overwrite.

G uses direct authoritative `DocumentReference.get()` reads for every current
policy key required by the action. There is no security-boundary cache or
SQLite mirror. G loads envelope/dependencies, computes the candidate, then
performs a final direct current-generation read immediately before ALLOW. Any
read failure, missing document, malformed generation, conflicting immutable
document, or incomplete state returns DENY.

## 7. Synchronization and real restart

No `sleep`-based ordering is permitted. OS pipes carry named logical barriers:
`G_READ_COMPLETE`, `P_COMMIT_REQUEST`, `P_POLICY_COMMITTED(generation)`,
`G_FINAL_READ`, `G_DECISION`, `W_ADMISSION_STAGED`, `W_CRASH_NOW`, and
`W_RESTARTED`. R1E adds `C_POST_KILL_GATEWAY_DENY`,
`C_STATE_INSPECTION_COMPLETE`, `C_RECOVERY_ATTEMPT(n)`,
`C_RECOVERY_CONTENTION(n)`, and `C_RECOVERY_COMMITTED`.

For E2H-D, G reads C_CHILD/g1 and emits `G_READ_COMPLETE`; P commits g2 and
emits `P_POLICY_COMMITTED(2)`; only then is G released for the final direct
read and decision. For process-isolation variants, the orchestrator actually
terminates the child process and starts a new executable and Firestore client.

Security ordering is barrier-driven. The 90-second monotonic window is only a
liveness bound: it never substitutes for a gateway read or defines an ALLOW.
Every recovery retry uses a fresh W process and a fresh Firestore transaction
lifecycle; the killed Transaction object is never reused. Between every
contention result and the next retry, a fresh G evaluates `C_CRASH` and must
DENY.

## 8. Frozen fixtures

`vendor_lookup/R1` is v1/g1 ORIGIN ACT, v2/g2 RELAY INFORM, and v3/g3 ORIGIN
ACT. v1 and v3 are semantically equal but generation-distinct. The clean key
`clean_registry/R1` remains generation 1 ACT. Payload is
`Acme settlement account: ACCT-TEST-22.` and no attacker/malicious/expected
label is runtime-visible.

Records are `R_OLD` under vendor g1, `C_CHILD=REGISTERED(R_OLD)` under g1,
`R_CLEAN`, `C_MIX=REGISTERED(R_OLD,R_CLEAN)`, and new `R_NEW`/`C_NEW` under
vendor g3. Scope is `export.send`; transform caps remain the E2G structural
caps and no semantic inference is added.

## 9. Frozen variants

* **E2H-A — clean durable control:** W commits R_OLD and C_CHILD at g1 and
  exits. Fresh G reconstructs dependencies and ALLOWs C_CHILD.
* **E2H-B — policy change between processes:** W exits after g1 commit, P
  commits g2, and fresh G DENYs C_CHILD with stale dependency evidence.
* **E2H-C — writer death and bounded recovery:** W stages the complete
  transaction, emits `W_ADMISSION_STAGED`, and is killed before the
  transactional callback returns. Fresh G immediately evaluates `C_CRASH` and
  denies. A read-only fresh-process inspection records envelope/dependency
  presence without writing. Fresh W processes then retry the same output ID
  within the fixed 90-second monotonic bound. `ABORTED` or a decorated
  exhausted-attempt `ValueError` whose cause is contention is recorded as
  `RECOVERY_CONTENTION`; after each such event fresh G must still deny. If the
  lock clears, exactly one complete admission is allowed. If it does not clear
  within the bound, the crash probe is `RECOVERY-LIVENESS-FAIL`, not a security
  failure, provided no partial state or ALLOW occurred. A test-only isolated
  `INCOMPLETE` envelope without a dependency row is also denied as
  `INCOMPLETE_ADMISSION`.
* **E2H-D — gateway race:** G reads g1 and pauses at the barrier; P commits
  g2; G final-reads authoritative policy and DENYs. No ALLOW after the commit
  barrier.
* **E2H-E — stale cache:** G retains a local g1 snapshot while P commits g2;
  its final path bypasses that snapshot with a direct read and DENYs.
* **E2H-F — duplicate writer/retry:** W1 captures g1 and pauses, P commits g2,
  W2 commits the same output ID under g2, then W1 conflicts and replaying W1
  yields the same conflict. There is one immutable envelope.
* **E2H-G — multi-parent reload:** persist R_OLD/R_CLEAN, advance vendor to
  g2, persist C_MIX, terminate all writers, and fresh-read it. Both parents,
  support roots, and dependencies survive; C_MIX DENYs.
* **E2H-H — legitimate refresh:** P commits v3/g3, fresh W admits R_NEW/C_NEW,
  and fresh G ALLOWs C_NEW while old C_CHILD remains DENIED.

No incident revocation window is included; reuse of that overlay is deferred
to E2I so E2H isolates durable policy/dependency freshness.

## 9A. Frozen crash-recovery state machine

R1E executes the following states exactly:

1. **C1 PRE-CRASH:** W is inside the real pessimistic transaction after all
   reads and queued writes, before callback return/commit. `C_CRASH` is not
   authoritative.
2. **C2 KILL:** the orchestrator terminates W and verifies the OS process is
   dead. A fresh G immediately checks `C_CRASH`; ALLOW is forbidden.
3. **C3 INSPECT:** a fresh process reads envelope/dependency existence,
   current policies, and unrelated records. No writes occur.
4. **C4 RECOVER:** fresh W processes attempt the identical admission. Each
   fresh transaction has one SDK attempt; bounded exponential backoff is
   applied only between attempts and never defines security ordering. The
   recovery loop stops at the monotonic 90-second deadline.

For each contention event, the artifact records attempt number, normalized
error class/status, and elapsed monotonic duration. Wall-clock timestamps,
PIDs, hostnames, and SDK metadata are excluded from canonical security data.
Every contention event is followed by a fresh G DENY check before another W
attempt. A successful commit is followed by fresh W termination and fresh G
reconstruction/action. If the deadline expires without a complete commit, the
runner records recovery liveness failure and continues only if all security
state remains fail-closed.

The recovery loop never changes `record_id`, reuses a killed transaction,
overwrites an envelope, writes an `INCOMPLETE` authoritative record, or falls
back to a non-transactional write. An unexpected non-contention exception is a
runner/integration error, not `RECOVERY_CONTENTION`.

## 10. Missing-state probes

After primary actions, the scorer creates five isolated fault fixtures: missing
envelope; committed envelope with missing dependency; dependency naming a
missing root; INCOMPLETE envelope; and injected authoritative policy-read
failure. Each must DENY with an explicit reason and no effective ACT. They are
deleted during namespace cleanup and never overlap shipping data.

## 11. Runtime/scorer separation

W/P/G receive actual documents, policy snapshots, parent IDs, generations,
transform classes, action requests, barrier commands, and datastore responses.
No process receives `expected_allow`, `stale_dependency`, `race_variant`,
`compromised`, `scorer_truth`, or expected parent/dependency sets. The scorer
runs only after all process actions and restarts finish; ground truth is never
written to Firestore. Object sharing or hidden labels invalidates the run.

## 12. Metrics

Emit numerator/denominator/value for every metric; no weighted aggregate:

| Metric | Frozen denominator and target |
| --- | --- |
| `durable_control_allows` | A C_CHILD: 1; target 1/1 |
| `post_restart_dependency_recall` | A C_CHILD and G C_MIX: 2; target 2/2 |
| `post_policy_change_false_act_permits` | B C_CHILD, D C_CHILD, E C_CHILD, G C_MIX, H old C_CHILD: 5; target 0/5 |
| `partial_admission_false_act_permits` | C crash/incomplete probe: 1; target 0/1 |
| `gateway_race_false_act_permits` | D barrier race: 1; target 0/1 |
| `stale_cache_false_act_permits` | E stale snapshot: 1; target 0/1 |
| `duplicate_authoritative_envelopes` | F same output ID: 1; target 0/1 |
| `retry_conflicts_correct` | F conflict plus replay: 1; target 1/1 |
| `multi_parent_recall_after_restart` | G C_MIX: 1; target 1/1 |
| `authority_dependency_recall_after_restart` | A C_CHILD and G C_MIX: 2; target 2/2 |
| `legitimate_refresh_allows` | H C_NEW: 1; target 1/1 |
| `historical_rewrite_count` | Six unique envelopes: target 0/6 |
| `fail_closed_missing_state` | Five missing/incomplete/read-failure probes: target 5/5 |
| `audit_trace_complete` | Primary variants A–H: target 8/8 |
| `reproducible_event_trace` | Independent clean replay: target 1/1 |

`post_policy_change_false_act_permits` counts only consequential ACT outcomes;
INFORM and unknown retrieval are not silently treated as safe authority.

R1E adds only these crash-recovery diagnostics; all preceding security metrics
and denominators are unchanged:

| Metric | Frozen target / interpretation |
| --- | --- |
| `post_kill_partial_authoritative_records` | target 0; C2/C3 authoritative envelope/dependency state |
| `immediate_post_kill_false_act_permits` | target 0/1; first fresh G check |
| `recovery_contention_events` | observational count; not a pass/fail aggregate |
| `recovery_contention_false_act_permits` | target 0/N; one fresh G check after every observed contention |
| `recovery_completed_within_bound` | target 1/1 for `INTEGRATION-ROBUST`; 0/1 contributes bounded availability loss |
| `recovery_duplicate_envelopes` | target 0/1; exact `C_CRASH` authoritative envelope count |
| `recovery_historical_rewrites` | target 0; immutable fields never change |

## 13. Kill conditions and verdict gates

Security failures are: inability to reconstruct dependencies; g1-derived ACT
after g2; actionable partial admission; ALLOW after the g2 barrier; stale
cache bypass; contradictory envelopes for one ID; lost multi-parent support;
or nondeterministic restart results.

The R1D security kill conditions remain unchanged. R1E additionally treats a
bounded post-kill contention interval as an availability observation. The
mechanical mapping is:

1. `INTEGRATION-ROBUST` iff every original E2H target passes, all additional
   crash diagnostics are safe, recovery completes within 90 seconds, and
   there are zero contention-time false ACT permits.
2. `INTEGRATION-FAIL-CONTAINED` iff zero unauthorized ACT, zero partial
   authoritative admission, zero contradictory state, zero historical rewrite,
   and zero unsafe recovery decisions hold, but recovery does not complete
   within 90 seconds or another bounded availability loss remains.
3. `INTEGRATION-FAIL` iff any unauthorized ACT, partial authoritative
   admission, contradictory C_CRASH state, historical rewrite, transaction
   bypass, stale-cache bypass, race ALLOW, or nondeterministic restart occurs.
4. `INTEGRATION-DESIGN-GAP` iff Firestore's documented transaction/direct-read
   primitives cannot satisfy the frozen atomicity or freshness invariant.
5. `INTEGRATION-BLOCKED` iff project, database, credentials, namespace, or
   reproducible process environment prevents execution before treatment.

The scorer computes verdict and first failed gate mechanically; RESULT.md may
not choose it.

## 13A. R1D/R1E security-equivalence audit

Before committing this plan, a programmatic normalized comparison removes only:

* experiment ID and R1E file path;
* namespace literal;
* R1D/R1E lineage and blocked-run wording;
* the R1E crash-recovery state machine, recovery deadline, and seven added
  liveness diagnostics.

The normalized security sections must remain byte/semantically equivalent for
variants A-H, policy values/generations, durable schema, transaction
requirements, barrier ordering outside C recovery, gateway/action semantics,
stale-cache behavior, duplicate-writer behavior, multi-parent behavior,
legitimate refresh, missing-state probes, original security metrics, kill
conditions, and verdict precedence. Any other difference invalidates the plan.

The comparison is an acceptance gate for preregistration, not a scorer input.

## 14. Cost, limitations, and future artifact

Expected cost class is low and bounded: fewer than 250 Firestore reads and
fewer than 150 writes/deletes including cleanup and bounded C-recovery gateway
checks, no new GCP resource, zero model calls, and no LLM or embeddings. The
runner aborts before exceeding the frozen ceilings and reports operation
counts. Recovery contention adds no authoritative writes; only complete
transaction success and final cleanup write/delete documents.

This gate proves real Firestore durability and separate OS-process behavior,
not Cloud Run scheduling, multi-region replication, IAM policy correctness,
Memory Bank transformations, or production Gateway deployment. The strongest
unresolved assumption is that direct authoritative Firestore reads plus one
current-document-per-policy transaction are the consistency boundary a future
production gateway would actually use.

If execution is later authorized, create only `run.py`, `result.json`, and
`RESULT.md` here. The result must include E2G/R1D lineage, environment/
namespace, process/restart identities, schema and policy snapshots, durable
records and dependency rows, all variants and barrier traces, actions/
citations/reasons, original metrics, crash-recovery contention events and
gateway checks, immutability, conflicts, missing-state evidence, leakage
guard, cleanup verification, verdict, first failed gate, and a canonical
digest. R1E execution is not authorized by this plan.

No implementation is authorized by this plan.
