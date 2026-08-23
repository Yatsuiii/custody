# B7 Production Data Model

Status: `FROZEN-DESIGN-DRAFT — DO NOT IMPLEMENT`

## Ownership and invariants

`custody/authority.py` owns the stable B7 values and algorithms. Durable
backends serialize those values; they do not reimplement verification,
propagation, or current-authority rules.

Invariants:

1. one `record_id` has one immutable envelope;
2. a root is authoritative only with a verified P2 receipt;
3. every derived envelope retains all direct parents and the union of every
   required parent's authority dependencies;
4. no persisted “effective cap” is authoritative—effective authority is
   recomputed against current state;
5. different bytes under an existing ID are a conflict, never an overwrite;
6. only `COMMITTED` envelopes can contribute authority;
7. revocation appends root state and never rewrites an envelope; and
8. missing/malformed parent, dependency, key, policy, generation, receipt, or
   revocation state denies ACT.

## Stable values

### Capability

Closed enum: `NONE < INFORM < ACT`.

- `NONE`: audit/quarantine only; no active informational or consequential use.
- `INFORM`: may be retrieved as information but cannot authorize a
  consequential action.
- `ACT`: may authorize only its exact action scope after every current-state
  check succeeds.

Unknown strings fail closed; they do not default to INFORM or ACT.

### TransformClass

Closed enum: `ROOT`, `IDENTITY`, `REGISTERED`, `FREEFORM`.

- `ROOT` requires a verified source event and P2 receipt.
- `IDENTITY` forwards one exact parent's support and adds no root authority.
- `REGISTERED` requires an exact configured transform PolicyKey/revision and
  preserves every required parent/support dependency.
- `FREEFORM` preserves observed support for audit and is capped at INFORM.

The class is selected by the production entry point, not a caller field in a
generic admission request.

### PolicyKey

Stable ordered fields:

```text
(department, source, operation, revision, action_scope)
```

Canonical representation is a five-element JSON array of non-empty UTF-8
strings. The durable document ID is SHA-256 of the canonical bytes; the full
five fields are persisted and checked on read so the digest is never the only
identity evidence.

### PolicySnapshot

| Field | Meaning | Mutable? | Action-time input? |
|---|---|---:|---:|
| `policy_key` | exact key above | no | yes |
| `version` | operator/audit version string | no within snapshot | trace only |
| `generation` | monotonic integer per PolicyKey | advances by new snapshot | yes |
| `operation_role` | ORIGIN or RELAY | no within snapshot | admission/bound trace |
| `caps` | scope to bounded Capability | no within snapshot | yes |

Semantic equality does not make generations equal. ABA (`g1 -> g2 -> g3` with
g1/g3 values equal) remains stale for a g1 dependency.

## P2 AuthorityReceipt

The production representation preserves the exact Gate 1B-R3 field set. No
benchmark fields are added.

| Field | Purpose | Signed/authenticated? | Persisted? | Canonical form | Backward compatibility | Required at action? |
|---|---|---:|---:|---|---|---:|
| `receipt_version` | schema/canonicalization version | yes | yes | string, initially `1` | absent/unknown version is legacy or DENY; never defaulted | yes |
| `receipt_id` | issuer-assigned immutable receipt identity and selective-root input | yes | yes | non-empty string | absent means no B7 root; no synthesized ID | yes |
| `issuer_id` | authority-producing source identity | yes | yes | non-empty string | old `source_tool` is not promoted to issuer | yes |
| `issuer_key_id` | selects trusted public key | yes | yes | non-empty string | no default/current-key fallback | yes |
| `policy_key` | binds department/source/operation/revision/scope | yes | yes | canonical five-string array | separate old fields are not assembled into authority | yes |
| `granting_generation` | exact policy generation that granted the cap | yes | yes | non-negative JSON integer | absent generation is never treated as current | yes |
| `granted_cap` | maximum source-root capability | yes | yes | `NONE`, `INFORM`, or `ACT` | old trusted bit maps at most to legacy INFORM | yes |
| `action_scope` | prevents cross-scope use | yes | yes | non-empty string; equals PolicyKey scope | no wildcard/default scope for old records | yes |
| `source_revision` | prevents same-source revision substitution | yes | yes | non-empty string; equals PolicyKey/source object revision | old revision remains audit-only without P2 | yes |
| `upstream_record_id` | source-owned object/record identity | yes | yes | non-empty string | content hashes cannot substitute for a missing object ID | yes |
| `upstream_object_commitment` | binds the exact canonical source object | yes | yes | lowercase SHA-256 hex | old payload digest cannot be reinterpreted as this field | yes |
| `issuer_signature` | Ed25519 signature over every field above except itself | evidence | yes | lowercase hex of 64 signature bytes | absent/invalid always denies B7 authority | yes |

Every unsigned field is authenticated by the Ed25519 signature. The signature
is evidence rather than a field recursively signed by itself.

### Receipt canonicalization

Version 1 uses the already validated P2 canonical bytes:

```text
json.dumps(unsigned_receipt,
           sort_keys=True,
           separators=(",", ":"),
           ensure_ascii=True)
+ "\n"
```

Rules:

- object keys are exactly the receipt fields above, excluding
  `issuer_signature`;
- `policy_key` is an array, never a tuple/object/string;
- generations are integers, never floats;
- extra or missing keys fail parsing;
- non-finite numbers and duplicate JSON keys are rejected;
- receipt version changes, rather than silent parser drift, are required for a
  future canonicalization change.

The source object commitment is SHA-256 over the same canonical JSON rules
applied to the complete provider-specific source-object claim. Custody receives
that claim in `SourceAuthorityEvent` and recomputes the commitment before
admission. The claim is not inferred from displayed payload text.

## ReceiptRootKey

Gate 1C-R3 identity is preserved exactly:

```text
(
  issuer_id,
  receipt_id,
  upstream_record_id,
  upstream_object_commitment,
  policy_key,
  granting_generation,
  custody_root_record_id,
)
```

The durable selector key is SHA-256 of this canonical array. The full tuple is
stored alongside its digest and reconstructed from the verified receipt/root at
read time. Payload text, attack labels, timestamps, and mutable metadata are not
selector inputs.

This prevents a copied receipt from creating an unrevoked root under another
Custody record ID.

## AdmissionEnvelope

One nested immutable envelope is persisted with each new `custody/{record_id}`
document:

| Field | Source/meaning |
|---|---|
| `schema_version` | `b7/p2-v1` |
| `record_id` | immutable Custody record ID |
| `payload_digest` | existing SHA-256 content digest; payload may be held elsewhere |
| `admission_state` | `COMMITTED`; `INCOMPLETE` and `LEGACY` never authorize |
| `transform_class` | ROOT/IDENTITY/REGISTERED/FREEFORM |
| `direct_parent_ids` | complete observed direct parents |
| `support_root_ids` | union of authenticated support root record IDs |
| `support_root_key_digests` | exact corresponding ReceiptRootKeys |
| `own_policy_key` | source/transform operation PolicyKey |
| `own_policy_version` | immutable bound policy version |
| `own_granting_generation` | immutable bound generation |
| `bound_cap` | cap bound at admission |
| `transform_cap` | transform's maximum cap; FREEFORM <= INFORM |
| `authority_receipt` | required for ROOT, absent for derived records |
| `source_object_claim` | canonical source claim for ROOT or a deletion-safe retained commitment if policy permits payload deletion |
| `admitted_at` | Firestore server create time; audit only, never freshness authority |
| `supersedes_record_id` | optional existing Architecture A replacement reference; never mutates old record |

Current effective capability is not stored in the envelope. It is a function of
this immutable state plus current policy, key, and revocation state.

## AuthorityDependency

Every required authority fact is materialized at admission:

| Field | Meaning |
|---|---|
| `record_id` | dependent envelope |
| `kind` | `SOURCE_AUTHORITY` or `TRANSFORM_POLICY` |
| `policy_key` | exact source/transform key |
| `granting_generation` | immutable generation used by the record |
| `root_record_id` | authenticated source root for source dependencies; the record itself for its transform dependency |
| `root_key_digest` | ReceiptRootKey digest for source dependencies; absent for transform policy |
| `action_scope` | exact scope |
| `receipt_id` | exact root receipt ID for source dependencies; absent for transform policy |

For a derived record:

```text
Dependencies(M) = union(Dependencies(P1), ..., Dependencies(Pn))
                  + M.transform_policy_dependency
Support(M)      = union(Support(P1), ..., Support(Pn))
```

No dependency is dropped because its cap is weak, duplicated semantically, or
inconvenient. Canonical tuple ordering and deduplication are by exact identity.

## Durable collections

Existing collection names remain for existing data. Additive B7 state is:

| Collection | Key | Owner / authoritative use |
|---|---|---|
| `custody` | `record_id` | existing record plus immutable nested B7 envelope; source of record/parent/support history |
| `authority_dependencies` | digest of `(record_id, kind, policy_key, root_record_id, scope)` | canonical dependency rows; reverse lookup by `root_key_digest` |
| `authority_policies` | PolicyKey digest | current per-key snapshot; updated transactionally with expected generation |
| `authority_issuer_keys` | digest of `(issuer_id, key_id)` | public trust anchor and exact identity; private keys never stored here |
| `authority_revocations` | `revocation_id` | append-only event containing exact selected RootKeys and server create time |
| `revoked_receipt_roots` | `root_key_digest` | direct authoritative lookup from root to first revocation event; create-only |
| `authority_action_decisions` | caller-supplied idempotency/request ID | immutable allow/deny trace; not itself authority |

Current coarse `revocations` remains for legacy tool/revision deletion and is
not silently interpreted as Gate 1C-R3 receipt-root state.

SQLite mirrors the same ports/tables for deterministic local tests. SQLite is
not evidence for Firestore process behavior.

## Atomicity and replay

### Admission

A Firestore transaction:

1. reads every direct parent envelope and dependency row;
2. reads the exact current own PolicyKey and, for ROOT, the issuer key;
3. verifies receipt/transform rules and constructs support/dependencies;
4. creates the immutable `custody` envelope and all dependency rows; and
5. commits all or none.

Identical replay returns the stored envelope. Any changed payload digest,
receipt, parent, support, dependency, policy binding, generation, cap, or
transform under the same ID returns `RETRY_POLICY_CONFLICT`. It never replaces
or merges the first envelope.

Downstream Memory Bank publication is non-authoritative. It happens after the
envelope commit and is idempotent by `memory_id_for(record_id)`. A crash may
leave a committed-but-unpublished record (availability failure); it cannot
create an authoritative memory without an envelope. Recovery retries the same
record ID. E2H-R1E's >90-second contention risk remains visible.

### Policy update

The policy controller transaction reads expected generation `g`, creates/writes
exactly `g+1`, and conflicts on any unexpected generation. Historical envelopes
are untouched.

### Revocation

One transaction creates the `authority_revocations/{revocation_id}` event and
every selected `revoked_receipt_roots/{root_key_digest}` marker. Identical
replay is a no-op; a reused ID with different selectors is a conflict.

Logical blocking is immediate from the root markers. Reverse-closure lookup and
Memory Bank deletion may proceed afterward; their delay cannot restore ACT.

### Action

The gateway reads the cited envelopes/dependencies, current policies, issuer
keys, and each exact root marker using authoritative reads. It writes one
immutable decision trace at the compare-and-decide linearization point. A
transaction retry repeats every current-state read. Any read error, transaction
contention exhaustion, missing document, malformed value, or inconsistent
dependency set denies.

Caches may accelerate DENY. A cache hit showing revocation can deny, but cached
absence/freshness can never produce ALLOW.

## Backward compatibility

- A document without `schema_version=b7/p2-v1` loads as `LEGACY`, not as a
  partially populated B7 envelope.
- Existing `source_tool`, `source_revision`, `derived_from`, and
  `content_sha256` remain readable for audit and legacy traversal.
- Existing trusted bits do not synthesize a receipt, generation, root key, or
  ACT cap.
- A B7 parser rejects unknown receipt fields but may ignore explicitly
  namespaced non-authority document metadata outside the receipt/envelope.
- No backfill can turn a legacy record into a B7 record in place.

## Operational limitation retained from E2H-R1E

Security under process death/contention is supported, but bounded recovery is
not: the killed Firestore transaction did not clear within the frozen 90-second
window. Production metrics must separately expose:

- time from contention detection to successful idempotent recovery;
- records committed but not yet published;
- recovery contention count;
- action denials caused by missing/incomplete state; and
- oldest pending recovery age.

No dashboard or retry loop may relabel this liveness failure as a security
failure or hide it inside an aggregate pass rate.
