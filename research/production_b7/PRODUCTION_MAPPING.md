# B7 Production Mapping

Status: `FROZEN-DESIGN-DRAFT — DO NOT IMPLEMENT`

Verdict: `YES-WITH-LIMITATIONS`

## Decision boundary

B7 can be represented as a bounded extension of current Custody. It does not
require `true_origin`, attack labels, scorer truth, semantic classification, or
a B8 mechanism. It does require replacing the production action decision's
binary trust input with an authoritative B7 envelope/state read.

The implementation is limited to an **eligible B7 path** where Custody observes
record IDs and verifies an object-bound source receipt. Current raw ADK session
ingestion and opaque Memory Bank transformations do not expose complete record
identity; those paths may remain useful as legacy/INFORM inputs but must never
produce B7 ACT authority.

Evidence basis:

- Architecture A: `research/design/` and E2D at `d5b671b`;
- generation/action freshness: E2F/E2G at `07eb279` / `bd0fcd3`;
- durable process safety: E2H-R1E at `56c4198`;
- source-issued P2 and transform composition: Gate 1B-R3 at `f3eb51c`;
- selective receipt-root revocation: Gate 1C-R3 at `437fc2a`.

E2H-R1E is `PARTIALLY-SUPPORTED`, not blocked: every preregistered safety
metric passed across real Firestore and independent W/P/G processes. The
specific failure was `recovery_completed_within_bound = 0/1` under 90 seconds.

## Concept-to-code map

| B7 concept | Current production type/function/module | Current behavior | Required bounded change | API/schema/persistence impact | Primary callers/tests affected |
|---|---|---|---|---|---|
| `AuthorityReceipt` | none; `custody.revision.SurfaceAttestation` is dispatch-surface evidence only | HMAC token binds a `tools/call` to `tools/list`; it does not bind a returned object or memory authority | add the frozen P2 value and canonical verifier in new `custody/authority.py`; do not reuse `SurfaceAttestation` as if it were P2 | new public type; additive nested receipt schema; persisted for source roots | new `tests/test_authority.py`; `tests/test_revision.py` remains a separate contract |
| authority producer | `custody.revision.AttestationAuthority`; `live/registry_attack/server/server.py` owns a server-side key | current signer mints tool-surface tokens; relay/server results carry no object-bound B7 receipt | define an external `SourceAuthorityEvent` contract; production core exposes verification, never a generic minting service. A source-owned adapter may sign only its owned object namespace | new provider-neutral event interface; producer deployment/config outside core verifier | live source adapter in P7; static external fixture in P6 |
| receipt verification | `AttestationAuthority.verify` | verifies HMAC, expiry, nonce, and tool revision | add Ed25519 P2 verification for issuer/key, object commitment, PolicyKey, revision, scope, generation, cap, root identity, and active selective revocation | new `AuthorityTrustStore` read port; missing/malformed key or state denies | `custody/authority.py`, `tests/test_authority.py`, production-equivalence suite |
| `PolicyKey` | department in `CustodyMemoryService`; tool/source revision in `ToolTrust`/`RevisionCatalog`; action scope only in `Export` behavior | fields exist separately; no canonical key or per-key generation | one frozen key `(department, source, operation, revision, action_scope)` owned by `custody/authority.py` | new stable serialized value and Firestore policy documents | `custody/service.py`, `custody/revision.py` as source-revision input, policy tests |
| generation state | none in shipping core; only research runners | current `TrustCatalog` and `RevisionCatalog` have no monotonic authority generation | add current `PolicySnapshot(version, generation, role, caps)` read/write port; exact generation, never semantic equality, controls freshness | new Firestore/SQLite policy representation; action-time authoritative read | `custody/firestore_store.py`, `custody/store.py`, gateway and durable tests |
| source revision | `CustodyRecord.source_revision`; `ToolTrust.revisions`; `RevisionCatalog` / `FirestoreRevisionCatalog` | revision follows admitted tool output and supports revision-wide revocation | retain as one PolicyKey/receipt field; verifier requires equality among receipt, source object, envelope, and PolicyKey | compatible field, stricter admission validation | `custody/origin.py`, `custody/revision.py`, revision tests |
| direct parents | `CustodyRecord.derived_from`; `take_custody`; `CustodyGraph` | current invocation collects parents; later retrieval recovers by exact content hash | retain `derived_from` as immutable direct IDs; B7 ACT path accepts only collector-observed IDs, not content-derived or caller-declared authority | existing field retained; admission API changes to distinguish observed context | origin/graph/service/ADK and cross-session tests |
| support roots | absent | graph computes descendants from direct edges; no materialized all-parent authority support | AdmissionGate unions every required parent's support; source root starts with its authenticated RootKey; no pruning | additive envelope and dependency rows, atomically persisted | authority, graph, durable and equivalence tests |
| transform class | `Origin` distinguishes TOOL/MODEL/DERIVED but not IDENTITY/REGISTERED/FREEFORM | trusted model restatement can inherit binary trust; exact-hash retrieval is the cross-session anchor | explicit frozen classes: ROOT, IDENTITY, REGISTERED, FREEFORM. Class is selected by a trusted entry point, never arbitrary payload/caller metadata | additive enum; new admission methods; no benchmark fields | `origin.py`, `service.py`, adapters and transformation tests |
| effective cap | `Trust` and `CustodyRecord.instruction_eligible()` | binary trusted/untrusted; trusted means action-eligible | persist immutable bound/transform caps and dependencies; compute current cap as all-required-parent meet under `NONE < INFORM < ACT` | API change: retrieval eligibility and ACT authority become separate concepts | `origin.py`, `service.py`, `action.py`; action/service tests |
| action gateway | `custody.action.ExportGateway.request(Export)` | trusts caller-supplied `CustodyRecord` objects and checks only `instruction_eligible()` | gateway accepts record IDs, resolves durable envelopes, verifies all required receipt/policy/revocation state with authoritative reads, and owns dispatch so ALLOW cannot be reused later | breaking security API; decision trace gains scope, roots, bound/current generations, reasons | `action.py`; `scripts/demo.py`, `scripts/gates.py`; action/ADK conformance tests |
| selective revocation | `CustodyGraph.revoke(tool)` and `revoke_revision(tool, revision)`; control-plane `/revoke` | deletes live graph records by issuer/tool or revision; Firestore retains historical source rows | add receipt-root selector using the exact Gate 1C-R3 RootKey; append revocation, block every supporting record logically, never rewrite history | additive API and collection; current coarse endpoints remain legacy-only | `graph.py`, `control_plane.py`, memory-bank revoker, graph/control-plane tests |
| cross-agent propagation | content-hash `resolve()` plus shared graph | exact bytes can recover a parent; transformed bytes lose it | preserve record ID and B7 envelope reference in Memory Bank metadata and agent messages; forwarding adds a dependency but never a root receipt | adapter/API metadata change; no new receipt | ADK/Memory Bank adapters; cross-session/department/live-chain tests |
| durable persistence | `FirestoreCustodyGraph`, `SqliteCustodyGraph` | append/replay exists, but `add` is not a B7 parent/policy transaction; SQLite replaces duplicate IDs and Firestore swallows `AlreadyExists` without immutable-byte conflict validation | transactional `admit` writes one immutable envelope plus all dependency rows after reading parents/current policy; duplicate identical bytes are idempotent, different bytes conflict | additive fields/collections and stricter write contract | `firestore_store.py`, `store.py`, durable/Firestore tests |

## Required production module changes

### New deep module

- `custody/authority.py`: owns `Capability`, `TransformClass`, `PolicyKey`,
  `PolicySnapshot`, `AuthorityReceipt`, `ReceiptRootKey`,
  `AuthorityDependency`, `AdmissionEnvelope`, `SourceAuthorityEvent`, receipt
  canonicalization/verification, `AdmissionGate`, and current-state authority
  evaluation. It must contain no signer that arbitrary Custody callers can use.

### Existing core modules

- `custody/origin.py`: retain content provenance, attach/reference a B7
  envelope, stop treating exact-hash retrieval or binary tool trust as ACT.
- `custody/service.py`: route eligible source/transform writes through
  `AdmissionGate`; commit authority before publication; keep opaque/legacy
  paths fail-closed.
- `custody/graph.py`: retain immutable history, expose root-key support and
  selective revocation without deleting historical evidence.
- `custody/action.py`: replace caller-supplied-record trust checks with durable
  ID resolution and current-state B7 evaluation.
- `custody/firestore_store.py`: add policy, envelope dependency, issuer-key,
  and receipt-root revocation persistence plus transactional admission.
- `custody/store.py`: mirror the same ports for deterministic local tests;
  replace unsafe `INSERT OR REPLACE` for B7 envelopes with immutable conflict
  behavior.
- `custody/control_plane.py`: add root-revocation and policy-generation
  operations; legacy `/revoke` remains explicitly coarse.
- `custody/adapters/adk.py`: carry B7 record IDs/metadata and invoke the core
  admission path; it must not infer receipts from tool identity.
- `custody/adapters/memory_bank.py`: preserve `custody_record_id` and envelope
  version on retrieval, not only on write; deletion remains an asynchronous
  cleanup after logical block.
- `custody/revision.py`: remains owner of source/tool revision identity. Only a
  narrow conversion into `PolicyKey` is added; its `SurfaceAttestation` is not
  promoted into object authority.

### Live proof modules, only in P7

- `live/registry_attack/server/server.py`: as a deployment-owned **ORIGIN**
  example, emit a B7 receipt over `_customer_record`; keep the existing
  dispatch-surface attestation separate.
- `live/gateway_probe/agent.py`: round-trip the B7 source event and cite durable
  record IDs at the action endpoint.
- a bounded `scripts/live_b7.py` proof driver and deterministic judge; no model
  or benchmark adapter.

### Existing callers requiring compatibility updates

`scripts/demo.py`, `scripts/gates.py`, `scripts/revoke.py`,
`scripts/incident.py`, `scripts/isolate.py`, `scripts/live_chain.py`,
`scripts/live_memory_bank.py`, `scripts/live_memory_deletion.py`,
`scripts/live_fleet.py`, `scripts/live_registry_attack.py`, and
`scripts/live_revision_binding.py` call one or more changed service, graph,
gateway, or receipt-adjacent interfaces. They must either use B7 public APIs or
be explicitly labelled legacy evidence; no silent compatibility shim may grant
ACT.

Primary existing tests affected are `test_origin.py`, `test_graph.py`,
`test_action.py`, `test_service.py`, `test_cross_session.py`,
`test_cross_department.py`, `test_durable_graph.py`,
`test_durable_integration.py`, `test_firestore_store.py`, `test_revision.py`,
`test_adk_memory_bank.py`, `test_adk_conformance.py`,
`test_agent_engine_memory_bank.py`, and `test_control_plane.py`.

## What stays unchanged

- `custody.revision.SurfaceAttestation` and `custody.nonce_ledger` continue to
  protect dispatch-surface freshness; they are not P2 receipts.
- `custody.memory_bank.memory_id_for` remains the record-to-memory ID mapping.
- reviewer/model outputs remain structurally unable to grant authority.
- Gate 1, Gate 2, frozen research runners, and benchmark adapters are not
  production dependencies.

## DDIA review

Verdict: `RISKY`, but representable as a bounded extension.

Chosen design: one immutable B7 envelope per custody record, materialized
all-required dependencies, authoritative per-PolicyKey generations, append-only
receipt-root revocations, and a gateway that directly reads current state.

Key invariants: one ID/one immutable envelope; no caller-selected authority;
all parents/support retained; stale/missing/revoked state denies; revocation
never rewrites history; cache absence never authorizes.

Rejected alternatives: reusing binary `ToolTrust`; converting
`SurfaceAttestation` into object authority; exact-content identity; issuer-wide
revocation; in-place support pruning; a parallel research mechanism in tests.

Unresolved risks: complete B7 record-ID capture through the chosen Memory Bank
path, source key ownership/rotation, Firestore transaction contention and the
known >90-second recovery case, and operational latency of authoritative action
reads.

## Hard-stop result

None of the six hard-stop conditions is established by the current repository:
B7 is representable, needs no scorer/oracle data, retains the frozen security
model, has a demonstrated durable state shape, maps legacy data fail-closed, and
does not require a rewrite. Implementation must stop if the per-record Memory
Bank metadata cannot be recovered at retrieval or if a real producer cannot be
isolated from the relay signing boundary.
