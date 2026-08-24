# Installed Firestore SDK contract

Date: 2026-08-24

Environment inspected directly from the installed package:

| component | version |
|---|---|
| Python | 3.12.13 |
| google-cloud-firestore | 2.28.1 |
| google-api-core | 2.34.0 |
| grpcio | 1.83.0 |

Package source was loaded from the active Python environment under
.venv/lib/python3.12/site-packages/google/cloud/firestore_v1/ and inspected
with inspect.signature and inspect.getsource.

## Read/write contracts

| production call | installed behavior | caller expectation | compatible |
|---|---|---|---|
| DocumentReference.get(transaction=transaction) | returns one DocumentSnapshot; missing has exists == False; read-after-write is rejected | one snapshot | YES |
| Transaction.get(document) | returns StreamGenerator[DocumentSnapshot] / Generator[DocumentSnapshot, Any, None], even for one document | one snapshot in Custody port | NO at raw port; normalized |
| Transaction.create | returns None and queues a create for commit | no return used | YES |
| Transaction.set | returns None and queues a set for commit | no return used | YES |
| Transaction.update | returns None and queues an update for commit | not used by B7 adapter | N/A |
| Transaction.delete | returns None and queues a delete for commit | not used by B7 adapter | N/A |
| firestore.transactional | returns _Transactional and retries the callback according to SDK rules | callable runner | YES |
| CollectionReference.stream | returns StreamGenerator[DocumentSnapshot] | iterated as snapshots | YES |
| Query.stream | returns StreamGenerator[DocumentSnapshot] | iterated as snapshots | YES |
| firestore.SERVER_TIMESTAMP | write sentinel reconstructed by Firestore server time | server-assigned timestamps | YES |

## Root cause of codec01

The bounded codec repair changed _FirestoreTransactionPort.get from
document.get(transaction=self._transaction) to self._transaction.get(document).
The latter is the SDK iterator API, so the caller's snapshot.exists access
raised AttributeError: generator has no attribute exists. The repair was
outside the intended codec boundary; the adapter now uses the
transaction-aware DocumentReference.get contract.

## Call-site audit

All custody/firestore_store.py interactions were inspected. Nontransactional
document reads, document creates, document sets, collection streams, query
streams, transaction decoration, server timestamps, and the transaction port
were checked. The only discovered raw contract mismatch was the transaction
read adapter above. Direct transaction.get calls in the store are calls to
Custody's internal transaction port, not raw SDK calls.

## Boundary rule

The fake must model the internal Custody port, while the real adapter must
normalize the installed SDK. A fake must not redefine Transaction.get as a
snapshot-returning API. The repaired fake returns an iterator and the adapter
test proves the port consumes the real shape without changing B7 data.

Real-service contract status at this audit: NOT PROVEN. A hardened
non-security probe is required; no P7 execution is authorized by this file.

