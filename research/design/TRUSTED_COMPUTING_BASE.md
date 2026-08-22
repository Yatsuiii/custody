# Trusted Computing Base

Architecture A is only as strong as the components that assert structural
facts. This document names those components and the exact property each must
provide. A component is not made trustworthy by being listed here; unverified
entries remain blockers.

## In-boundary components

| Component | Trusted property | Current evidence | Failure consequence |
|---|---|---|---|
| ADK event boundary | `author`, `invocation_id`, function-response structure, and event order are authentic | Inherited project assumption; not authenticated by Custody | Forged principal/origin or impossible causal edges |
| Context/receipt collector | Observes every stored record exposed to a producer and emits the exact id set | **Unproven across current retrieval and server-side Memory Bank transformations** | Hidden input can receive an incomplete but trusted-looking output |
| Admission gate | Validates one envelope and computes role, transform cap, support, and scoped authority; callers cannot submit authority | Design only | Authority amplification or missing parents |
| Policy catalog | Owns operation roles and per-action caps by department and version | Current departmental isolation exists; operation roles/scopes do not | Relay misclassified as origin or cross-department authority leak |
| Durable admission store | Atomic record+envelope write, immutable ids/parents, authoritative admission time, idempotent replay | Firestore has create-time/idempotent create; the combined envelope is not implemented; SQLite/in-memory time is insufficient | Interval misclassification, orphan record, or conflicting replay |
| Revocation controller | Appends windows before repair, advances generation, computes closure, and resumes idempotently | Current graph has idempotent whole-tool traversal; window/overlay protocol is not implemented | Unsafe race, missed descendant, or false completion |
| Action gateway | Requires current-generation `ACT` for the exact action scope and refuses stale/unavailable policy | Current gateway checks a binary record flag; scoped freshness is not implemented | Blocked/informational content authorizes an external action |
| Downstream publisher/deleter | Maps each active memory to a record id and applies idempotent block/delete | Per-record `RecordWriter` path exists; raw session ingestion and opaque server-side derivation do not provide this mapping | Memory remains usable after logical repair or has no receipt |
| Compromise reporter/adjudicator | Supplies a defensible window or conservative uncertainty bound | Explicit external input; detection is out of scope | Too-narrow window misses poison; too-wide window raises collateral |

The model and arbitrary tools are not in the boundary. They may be malicious,
hallucinate, omit context, or return provenance-looking strings.

## Honest relay limitation

Custody cannot force an arbitrary relay tool to reveal truthful upstream
provenance. Only two inputs are accepted as structural facts:

1. record ids observed by Custody's own context/connector adapter; or
2. provenance verified by a separately configured external identity/integrity
   connector.

If neither exists, the receipt includes `UNKNOWN_CONTEXT` and the output is at
most `INFORM`. Treating a tool's self-declared parent list as trustworthy would
silently move E2A's vulnerability from `runtime_name` to `parent_ids`.

## Paths inside and outside the claim

### Eligible path

An in-TCB adapter loads record ids, builds producer context, captures the output,
atomically stores the admission envelope, and publishes one record-addressable
memory. Every consequential action then passes the current-generation scoped
gateway.

### Ineligible path

Raw events are submitted to an opaque service that retrieves, summarizes, or
merges memory without returning source record ids. The result may be retained
as informational output, but it cannot be represented as a complete receipt or
used to claim action-authorizing laundering resistance.

The current system contains both shapes. A mechanism proof must exercise only
the eligible path and must not generalize its result to the opaque path.

## Why signatures are not adopted

The current threat model excludes direct durable-store writes and assumes
exclusive service access. No E0-E2C experiment attacked receipt bytes after
admission. Adding signatures now would introduce signing keys, rotation,
verification freshness, and compromise recovery without stopping an exercised
adversary.

If future scope includes a writer that can alter records outside the admission
gate, the named adversary is **post-admission provenance forgery**. Candidate C
then becomes relevant. Signatures would still not prove that a free-form
transformation is semantically faithful or that an authorized signer is honest.

## Boundary minimization

APOSD ownership is concentrated in two deep modules for any later experiment:

- **AdmissionGate:** one interface accepts producer output plus collector state
  and returns an immutable admission envelope or a fail-closed refusal.
- **RevocationController:** one interface activates a compromise window and
  exposes effective state plus a resumable repair plan.

Callers do not implement role lookups, lattice meets, timestamp fallbacks,
support pruning, generation caching, or retry policy themselves. The action
gateway consumes only `effective_tier(record_id, action_scope, generation)`.

## Privacy and observability

- Receipts store record ids and policy metadata, not duplicate content.
- Logs omit payload text and secrets; explanations refer to ids, scopes,
  policy versions, and window matches.
- Deletion removes payload from downstream and active storage. Minimal
  tombstones follow `REPAIR_SEMANTICS.md` and retention policy.
- Metrics include missing/incomplete receipts, `UNKNOWN_CONTEXT` admissions,
  stale-generation denials, repair retries, legacy timestamp fallbacks, and
  per-window collateral.
- A wrong record must be explainable from its admission envelope through direct
  parents to roots and the exact active window that changed effective state.

## Unresolved production blockers

1. Demonstrate complete record-id capture for model context and retrieval;
   current exact-text `load_memory` and opaque Memory Bank transformations do
   not provide that evidence.
2. Define a production store transaction/outbox for atomic envelope admission
   and record-addressable publication.
3. Migrate or conservatively quarantine records without authoritative
   `admitted_at`; current SQLite/in-memory paths cannot claim interval precision.
4. Implement current-generation scoped checks at every consequential action
   gateway, including stale-cache failure behavior.
5. Prove crash/retry recovery for activation, plan persistence, downstream
   deletion, and concurrent writes.

Until these gates pass, the architecture is suitable for an isolated falsifier,
not a production claim.
