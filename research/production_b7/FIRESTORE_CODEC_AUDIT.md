# B7 Firestore Persistence Codec Audit

Classification: `IMPLEMENTATION-CODEC-REPAIR`

The preserved P7 attempts remain invalid. This repair changes only Firestore
storage encoding and does not authorize a live execution.

## Observed defect and bug-class audit

| Persisted value | Old shape | Finding | New storage shape |
| --- | --- | --- | --- |
| `RootRevocation.root_keys` | array of `ReceiptRootKey` arrays | observed P7 rejection | array of versioned root-key maps |
| revoked-root marker `root_key` | root-key array containing a `PolicyKey` array | latent rejection | versioned root-key map |
| `AuthorityDecision.record_reasons` | array of `[record_id, reason]` arrays | latent rejection when non-empty | array of `{record_id, reason}` maps |
| `AdmissionEnvelope.source_object_claim` | arbitrary external JSON stored directly | latent rejection for externally supplied nested arrays | versioned canonical-JSON string wrapper |
| `PolicySnapshot` | map containing scalar arrays and maps | safe | unchanged |
| `AuthorityReceipt` | map containing a scalar `PolicyKey` array | safe | unchanged inside encoded envelope |
| `AuthorityDependency` | map containing a scalar `PolicyKey` array | safe | unchanged |
| support/direct-parent collections | arrays of scalars or arrays of dependency maps | safe | unchanged |
| cross-agent state | same envelope/dependency codecs | no separate shape | same repaired codecs |

Every B7 transaction write now passes one recursive pre-RPC guard that rejects
an array directly containing another array. Arrays of maps and arrays of
scalars remain valid.

## Identity invariants

The domain representations remain unchanged:

- `AuthorityReceipt.canonical_bytes()` and `binding_digest`;
- `ReceiptRootKey.as_list()`, `canonical_bytes()`, and `digest`;
- `RootRevocation.selector_bytes()`;
- `AuthorityDecision` fields and equality;
- `PolicyKey`, generation, scope, capability, support closure, and revocation
  semantics.

Codec tests compare these values before and after Firestore encode/decode.

## Compatibility decision

Read-only aggregate audit of project `project-988bc9fe-092c-4b32-90c`, database
`(default)`, found:

- zero documents in every dedicated unprefixed B7 collection;
- 13 unprefixed `custody` documents, of which zero have `record_kind == "b7"`;
- the preserved P7 cleanup recorded zero committed revocation documents and
  markers.

No persisted production B7 data requires migration.

Legacy reads remain for shapes that could validly have reached Firestore:

- a direct envelope whose source claim contains no nested array;
- a direct action decision with an empty `record_reasons` array.

No legacy revocation decoder is added because every valid domain revocation
has at least one root key, making the old nested-array representation
uncommittable. Revocation and marker creation are transactional, so no old
marker can be committed independently through the production write path.

## Verification boundary

The local test suite exercises all eight B7 document families through
`FirestoreAuthorityStore`, checks the recursive safety invariant, and feeds
each resulting document through the pinned Google Firestore SDK write
serializer. The Firestore emulator component is not installed locally, so no
emulator claim is made. A future live proof requires a fresh identity and is
not executed as part of this repair.
