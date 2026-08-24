# B7 data-model and serialization audit

The domain model remains in custody/authority.py; Firestore encodings are
isolated in custody/firestore_store.py.

| domain value | Firestore representation | identity check |
|---|---|---|
| AuthorityReceipt | embedded in canonical AdmissionEnvelope; source claims use versioned canonical JSON | receipt canonical bytes and binding digest are domain-derived and not rewritten |
| PolicyKey / PolicySnapshot | snapshot map keyed by PolicyKey.digest | loaded key must equal requested key; generation is preserved |
| AuthorityDependency | one dependency map per indexed document plus the B7 record dependency list | dependency digest and record ID are checked on read |
| ReceiptRootKey | named map with firestore_encoding=b7/firestore-root-key-v1 | decoded key reconstructs the same digest |
| RootRevocation | named map with root-key maps, not an array of arrays | selector_bytes is reconstructed from domain keys |
| AuthorityDecision | named record_reasons maps with firestore_encoding=b7/firestore-decision-v1 | decoded decision is the same domain decision |
| AdmissionEnvelope | versioned envelope map; source claims are canonical JSON strings | envelope canonical identity remains domain-owned |
| action decision | request IDs/digests plus encoded decision and server timestamp | request identity and decision fields are checked |

The codec rejects malformed encodings, unexpected field sets, unsupported
encoding versions, invalid SHA-256 strings, invalid source-claim canonical JSON,
and direct array-of-array values before a Firestore RPC. The previously observed
nested-array bug occurred in RootRevocation; the latent AuthorityDecision
record_reasons shape was audited and encoded as maps in the same repair cluster.

No successfully committed affected revocation document exists from the invalid
P7 attempt: the write failed before authoritative commit. Existing B7 records
written by the codec repair retain readable versioned encodings; no migration
of the failed revocation shape is required. Legacy records without B7 metadata
remain non-authoritative under existing fail-closed readers.

Required verification remains: codec round trips, exact identity comparisons,
malformed-input tests, and a real Firestore read/write probe. None permits
benchmark labels or scorer truth into the model.

