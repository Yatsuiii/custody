# B7 Migration and Legacy-Memory Plan

Status: `FROZEN-DESIGN-DRAFT — DO NOT IMPLEMENT`

## Migration rule

Absence of B7 evidence never means trusted. Existing `Trust.TRUSTED`, tool
vouches, revision pins, exact content matches, server timestamps, and current
Memory Bank presence are insufficient to manufacture P2 authority.

Migration is additive and lazy. Existing records remain immutable and receive a
runtime legacy classification; no receipt/support metadata is backfilled from
payload, labels, expected behavior, or historical trust bits.

## Legacy states

| Existing record | B7 migration state | Retrieval behavior | ACT behavior | Upgrade path |
|---|---|---|---|---|
| `Trust.TRUSTED`, no B7 envelope | `LEGACY_PROVENANCE_UNKNOWN` | INFORM-compatible if existing product policy permits retrieval | DENY | source re-reads the current owned object and creates a new B7 root record |
| `Trust.UNTRUSTED` or quarantined | `LEGACY_AUDIT_ONLY` | quarantine/audit only | DENY | only a new verified source event can create a separate B7 record |
| old revision-pinned tool record | `LEGACY_PROVENANCE_UNKNOWN` | INFORM-compatible | DENY; a tool revision authenticates a tool surface, not the returned object | new source-object receipt under current PolicyKey/generation |
| exact-hash-retrieved descendant | `LEGACY_PROVENANCE_UNKNOWN` | existing informational retrieval may continue | DENY | new IDENTITY/REGISTERED operation using explicit record IDs and a B7 parent |
| record removed by coarse tool/revision revocation | historical legacy tombstone | not active | DENY | never restored in place; a new source event creates a new record |
| partially written/malformed B7-shaped record | `INCOMPLETE` | audit/quarantine only | DENY | transaction repair may complete only if exact immutable bytes are recoverable; otherwise leave denied |
| valid `b7/p2-v1` envelope | normal B7 state | according to NONE/INFORM/ACT and record state | current-state evaluation | no migration |

Legacy trusted memory maps to INFORM rather than NONE to preserve bounded benign
retrieval utility without granting consequence. This is a deliberate separation
from the current `instruction_eligible()` method, whose binary trusted value
currently conflates retrieval and action authority.

## Re-attestation

Re-attestation is not a backfill operation. It requires the source boundary to:

1. read the current source-owned object;
2. emit a new runtime `SourceAuthorityEvent` under the current source revision,
   PolicyKey, and generation;
3. pass production P2 verification; and
4. admit a **new Custody record ID** that may reference the legacy record only
   as audit/supersession metadata, not as authority.

The old record remains `LEGACY_PROVENANCE_UNKNOWN` or becomes `SUPERSEDED`; its
bytes, parents, trust bit, and admission history are never rewritten to look
like B7 evidence.

Batch re-attestation is permitted only when the authoritative source itself
enumerates and signs each current object. A migration script may orchestrate
calls but may not synthesize receipts from the old Custody database.

## Raw/opaque Memory Bank path

Current `VertexAiMemoryBankService` session ingestion may summarize, merge, or
return memories without preserving Custody record metadata. During migration:

- it remains available only as a legacy/INFORM path;
- any retrieved item lacking an exact `custody_record_id` and resolvable B7
  envelope cannot cite ACT;
- current exact-content `resolve()` may support audit association but cannot
  upgrade authority; and
- the eligible B7 path uses per-record writes and metadata-preserving retrieval.

If the deployed Memory Bank API does not return custom metadata on the selected
per-record retrieval path, B7 production integration stops at P2 rather than
adding semantic matching or hidden side channels.

## Coarse revocation coexistence

Existing `revoke(tool)` and `revoke_revision(tool, revision)` remain valid
legacy containment tools. They are not converted into selective receipt-root
events because historical records lack authenticated RootKeys.

Rules:

- a legacy coarse revocation may continue to remove/block legacy records;
- B7 root revocation uses only authenticated ReceiptRootKeys;
- an operator may conservatively deny an issuer/tool through policy generation
  change, but must not report it as Gate 1C-R3 selectivity; and
- no migration job infers compromised root IDs from payload text, timestamps,
  incident labels, or scorer results.

## Deployment sequence

1. **Read compatibility:** deploy readers that understand B7 and classify every
   old document as legacy without changing it.
2. **Fail-closed gateway:** deploy current-state gateway behavior so legacy
   citations cannot ACT before any B7 writer is enabled.
3. **Additive state:** create policy/key/dependency/revocation collections and
   indexes; verify permissions and empty/new namespace expectations.
4. **B7 source writes:** enable one source producer and one eligible per-record
   Memory Bank path.
5. **Selective revocation:** enable receipt-root operations only after root and
   dependency reconstruction tests pass across restart.
6. **Retire unsafe compatibility:** remove any production caller that still
   passes caller-constructed records directly to `ExportGateway`.

Step 2 intentionally precedes B7 rollout: a mixed deployment must fail closed,
not continue granting ACT from old binary trust while waiting for receipts.

## Rollback

- Schema additions are append-only; rollback code may ignore new collections
  but must not resume legacy ACT authority.
- If B7 writers are disabled, new B7 records remain readable/auditable and
  action-denied unless the rolled-back gateway still understands their current
  state. Therefore a gateway rollback past B7 awareness is prohibited after B7
  ACT traffic starts.
- Source producer rollback stops issuing new receipts; it does not delete keys
  or envelopes.
- Selective revocation rollback leaves root markers active; ignoring them would
  be an unsafe rollback.

The practical rollback boundary is per implementation slice before production
ACT enablement. After enablement, only forward repair or a global fail-closed
mode is safe.

## Migration acceptance gates

1. Every pre-B7 fixture loads as legacy and produces zero ACT allows.
2. Existing trusted legacy memory remains retrievable as INFORM where expected.
3. Untrusted/quarantined legacy memory remains inactive.
4. Re-attestation creates a new record and never mutates the old document.
5. No tool/revision grant is converted into a P2 receipt.
6. Mixed-version processes share one authoritative classification and fail
   closed on unknown schema.
7. Firestore reload reproduces legacy/B7 state byte-for-byte except documented
   server timestamps.
8. Rollback testing never re-enables legacy ACT or ignores an existing receipt-
   root revocation.

Failure of gates 1, 4, 5, or 8 is a hard stop.
