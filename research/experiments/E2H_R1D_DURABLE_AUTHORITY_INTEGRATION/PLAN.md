# E2H-R1D — Durable Authority Integration (transactional wrapper correction)

Status: frozen preregistration/design only. No implementation, deployment, or
production change is authorized by this document.

Design verdict: **INFORMATIVE**. A safe real persistence environment was
verified read-only before this plan was written.

## 1. Lineage and question

Experiment ID: `E2H_R1D_DURABLE_AUTHORITY_INTEGRATION`.

Frozen E2G execution: `bd0fcd3af38b105f326dbe0e4f73149b6da67449`.
Parent E2H-R1C preregistration: `b165ee139429c1b14f87798237137bf43ec8bf5d`.
Invalid E2H-R1C execution commit: `b85e0e9a8e0a11d888cc014713a445c9ef068212`.
Failure classification: `EXECUTION-IMPLEMENTATION-ERROR`. R1C consumed
the Firestore transaction-read generator but used a manually constructed
`Transaction` without starting its transaction lifecycle; the client
returned `ValueError: Transaction not in progress, cannot be used in API
requests` before any policy seed write. No scored security variant ran.
Corrected integration primitive: wrap each atomic admission/policy update
in the installed client's `firestore.transactional` callback so begin,
all reads, writes, retries, and commit use one real pessimistic transaction.
Document-reference reads are consumed inside that callback; dependency
queries remain transaction-bound streams. This is an SDK lifecycle
correction, not a change to Architecture A or any security rule.
The contaminated R1 and R1C namespaces remain untouched.
Single environmental variable: fresh isolated collection namespace.
All security semantics, fixtures, variants, metrics, denominators,
verdict gates, barriers, transaction requirements, and cleanup rules remain
frozen equivalent to the parent R1C plan.

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
`custody_research_e2h_r1d_20260822`.

Only these collections may be touched: `custody_research_e2h_r1d_20260822_policies`,
`custody_research_e2h_r1d_20260822_envelopes`,
`custody_research_e2h_r1d_20260822_dependencies`, and
`custody_research_e2h_r1d_20260822_controls`.

The preregistration-time read-only verification for this fresh namespace
returned zero documents in all four collections on 2026-08-22. This is
evidence of natural emptiness, not a guarantee; execution must re-check
the same four names immediately before its first write. A nonzero result
blocks the run without deletion or namespace substitution.

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
`W_RESTARTED`.

For E2H-D, G reads C_CHILD/g1 and emits `G_READ_COMPLETE`; P commits g2 and
emits `P_POLICY_COMMITTED(2)`; only then is G released for the final direct
read and decision. For process-isolation variants, the orchestrator actually
terminates the child process and starts a new executable and Firestore client.

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
* **E2H-C — writer death:** W stages the complete transaction, emits
  `W_ADMISSION_STAGED`, and is killed before `transaction.commit()`. Fresh W
  retries and fresh G evaluates. Either no admission then one complete commit,
  or one complete commit is valid; an incomplete admission may never ALLOW.
  A test-only isolated INCOMPLETE envelope without a dependency row is also
  denied as `INCOMPLETE_ADMISSION`.
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

## 13. Kill conditions and verdict gates

Security failures are: inability to reconstruct dependencies; g1-derived ACT
after g2; actionable partial admission; ALLOW after the g2 barrier; stale
cache bypass; contradictory envelopes for one ID; lost multi-parent support;
or nondeterministic restart results.

Mechanical precedence is:

1. `INTEGRATION-ROBUST` iff every variant/probe meets target, false ACT is
   zero, recall/conflict/immutability/audit/replay/fail-closed checks pass.
2. `INTEGRATION-FAIL-CONTAINED` iff no unauthorized ACT occurs but measurable
   availability/selectivity loss remains.
3. `INTEGRATION-FAIL` iff any unauthorized ACT, contradictory state, lost
   dependency, stale-cache bypass, race ALLOW, or nondeterministic restart
   occurs.
4. `INTEGRATION-DESIGN-GAP` iff Firestore transaction/direct-read primitives
   cannot satisfy the frozen atomicity or freshness invariant.
5. `INTEGRATION-BLOCKED` iff the project, database, credentials, namespace, or
   reproducible process environment cannot be safely used.

The scorer computes verdict and first failed gate mechanically; RESULT.md may
not choose it.

## 14. Cost, limitations, and future artifact

Expected cost class is low and bounded: fewer than 250 Firestore reads and
fewer than 150 writes/deletes including cleanup, no new GCP resource, zero
model calls, and no LLM or embeddings. The runner aborts if ceilings are
exceeded and reports operation counts.

This gate proves real Firestore durability and separate OS-process behavior,
not Cloud Run scheduling, multi-region replication, IAM policy correctness,
Memory Bank transformations, or production Gateway deployment. The strongest
unresolved assumption is that direct authoritative Firestore reads plus one
current-document-per-policy transaction are the consistency boundary a future
production gateway would actually use.

If execution is later authorized, create only `run.py`, `result.json`, and
`RESULT.md` here. The result must include E2G lineage, environment/namespace,
process/restart identities, schema and policy snapshots, durable records and
dependency rows, all variants and barrier traces, actions/citations/reasons,
metrics, immutability, conflicts, missing-state evidence, leakage guard,
cleanup verification, verdict, first failed gate, and a canonical digest.

No implementation is authorized by this plan.
