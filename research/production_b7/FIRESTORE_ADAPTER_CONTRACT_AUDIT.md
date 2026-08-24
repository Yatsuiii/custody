# Firestore Adapter Contract Audit

Status: **adapter repair pending real-service contract probe**

This audit is not a P7 execution and contains no attack cases, scorer fields,
or B7 efficacy result.

## Installed environment

| Component | Version |
|---|---|
| Python | 3.12.13 |
| google-cloud-firestore | 2.28.1 |
| google-api-core | 2.34.0 |
| grpcio | 1.83.0 |

The inspected source files are the installed modules under
`.venv/lib/python3.12/site-packages/google/cloud/firestore_v1/`.

## Exact SDK contracts

`DocumentReference.get(..., transaction=transaction)` has the installed
signature return annotation `DocumentSnapshot`. Its source constructs and
returns one snapshot, including an explicit `exists=False` snapshot for a
missing document.

`Transaction.get(ref_or_query)` has the installed signature return annotation
`StreamGenerator[DocumentSnapshot] | Generator[DocumentSnapshot, Any, None]`.
For a `DocumentReference`, its implementation calls `client.get_all([ref],
transaction=self, ...)` and returns that iterator. It does not return a
snapshot and therefore has no `.exists` attribute.

The failed codec01 run called the second API through the transaction adapter,
then a caller evaluated `snapshot.exists`. That produced the preserved
`AttributeError: 'generator' object has no attribute 'exists'` in the POLICY
role. The Firestore codec was not the cause of that failure; the adapter had
changed its SDK call shape.

The installed write contracts are:

| SDK method | Installed return / behavior |
|---|---|
| `DocumentReference.create` | `WriteResult`; create-only, conflict if present |
| `DocumentReference.set` | `WriteResult`; replace or merge |
| `DocumentReference.update` | `WriteResult`; update existing document |
| `DocumentReference.delete` | protobuf `Timestamp`; delete succeeds even if absent |
| `Transaction.create` | `None`; queues a create until transaction commit |
| `Transaction.set` | `None`; queues replace/merge until commit |
| `Transaction.update` | `None`; queues an update until commit |
| `Transaction.delete` | `None`; queues a delete until commit |
| `firestore.transactional` | `_Transactional` callable that runs/retries a transaction callback |
| `CollectionReference.stream` | `StreamGenerator[DocumentSnapshot]` |
| `Query.stream` | `StreamGenerator[DocumentSnapshot]` |

Custody ignores direct write return values, which is compatible. It iterates
all stream results, which is compatible. It uses `.exists`, `.to_dict()`, and
`.create_time` only on document reads that return snapshots.

## Production call-site audit

| Production method / path | SDK call | Expected/actual installed type | Caller expectation | Compatible? |
|---|---|---|---|---|
| `FirestoreCustodyGraph._reload` | collection `.stream()` | generator of snapshots | iterate and sort snapshots | YES |
| `FirestoreCustodyGraph.add/revoke/record` | document `.create()` | `WriteResult` | ignore result; reread document | YES |
| `FirestoreCustodyGraph.add/revoke/record` | document `.get()` | `DocumentSnapshot` | `.exists`, `.to_dict`, `.create_time` | YES |
| `_FirestoreTransactionPort.get` before repair | `transaction.get(document)` | generator | one snapshot with `.exists` | **NO** |
| `_FirestoreTransactionPort.get` after repair | `document.get(transaction=transaction)` | `DocumentSnapshot` | one snapshot with `.exists` | YES |
| `_FirestoreTransactionPort.create` | `transaction.create` | `None` | queue write; ignore result | YES |
| `_FirestoreTransactionPort.set` | `transaction.set` | `None` | queue write; ignore result | YES |
| `FirestoreAuthorityStore._get` outside transaction | `document.get()` | `DocumentSnapshot` | authoritative snapshot | YES |
| `FirestoreAuthorityStore._run_transaction` | `client.transaction()` + `firestore.transactional` | `Transaction` + transactional callable | execute callback with retries | YES |
| B7 admission/policy/revocation/action transaction reads | port `.get` | snapshot after repaired mapping | `.exists`, `.to_dict` | YES after repair |
| `FirestoreAuthorityStore.records` | collection `.stream()` | generator of snapshots | iterate records | YES |
| `action_decisions`, `root_revocations`, `affected_record_ids` | collection `.stream()` | generator of snapshots | iterate/query in Python | YES |
| `FirestoreRevisionCatalog.approve` | document `.set(..., merge=True)` | `WriteResult` | ignore result | YES |
| `FirestoreRevisionCatalog.admit` | document `.get()` | `DocumentSnapshot` | `.exists`, `.to_dict` | YES |
| `FirestoreAuditorLog.heartbeat` | query `.stream()` + document `.create()` | generator + `WriteResult` | `next`; ignore write result | YES |
| `FirestoreDemotionLog.record/all` | document `.create()` + collection `.stream()` | `WriteResult` + generator | ignore/iterate | YES |
| `FirestoreNonceLedger.seen/mark` | document `.get()` + `.create()` | snapshot + `WriteResult` | `.exists`; ignore write result | YES |
| B7 writes with `firestore.SERVER_TIMESTAMP` | sentinel in create payload | SDK transform sentinel | server assigns write time | YES |

No production call site uses `Transaction.update` or `Transaction.delete`.
No other SDK-contract mismatch was found in the audited production surface.

## Fake/test-double gap

The prior `_FakeTransaction.get` directly called `_FakeDocument.get()` and
returned a `_FakeSnapshot`. That modeled the internal Custody port rather than
the installed SDK. It made the incorrect `transaction.get(document)` adapter
line appear valid, so 476 project tests and the 11 Firestore codec tests could
pass while the real POLICY process received a generator.

The safer boundary is to keep the internal port explicit: its `get` method
returns one snapshot because that is what Custody callers need. The real
adapter translates the SDK's iterator-returning `Transaction.get` family into
that port by calling the document's transaction-aware read. The fake now
returns an iterator from `Transaction.get` and accepts the transaction keyword
on `DocumentReference.get`, matching the installed shape. A contract test
fails against the old adapter and passes only when the translation is correct.

## Repair boundary

Authorized change: the Firestore transaction read adapter and its SDK-shape
tests/fake. No authority, receipt, root selector, generation, capability,
transform, action, or persistence identity changes are included.

The non-security real-service probe is a separate artifact. It must verify
storage mechanics only and must stop on the first SDK-contract exception.
