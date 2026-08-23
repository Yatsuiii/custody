# B7 Production Integration Plan

Status: `FROZEN-DESIGN-DRAFT — DO NOT IMPLEMENT`

Recommendation after this design is frozen: `AUTHORIZE`, slice by slice.

This plan implements only Architecture A + P2 + generation composition +
selective receipt-root revocation already validated in the research lineage.
It does not authorize B8, a semantic judge, benchmark fields, inferred
provenance, or a production rewrite.

## Module design

The APOSD boundary is one deep core module, `custody/authority.py`, with narrow
ports into existing adapters/stores:

- callers submit source events or explicit transform operations;
- the module verifies and returns an immutable envelope/denial;
- stores own atomic persistence, not authority policy;
- the action gateway asks for one current-state decision; and
- revocation accepts authenticated ReceiptRootKeys only.

Do not scatter cap lattice, receipt canonicalization, root identity,
dependency union, generation checks, or transform rules across `origin.py`,
`service.py`, `graph.py`, adapters, and tests.

## P0 — stable B7 values and ports

Exact files:

- add `custody/authority.py`;
- minimally export public values from `custody/__init__.py` only if the package
  already uses that convention;
- add `tests/test_authority.py`.

Invariant introduced: one canonical representation for PolicyKey, P2 receipt,
ReceiptRootKey, capability, transform class, dependency, and immutable
envelope. No production signer and no scorer-shaped constructor parameter.

Tests:

- strict receipt/envelope parsing and canonical bytes;
- unknown fields/caps/transforms rejected;
- RootKey changes under every identity-field mutation but not payload metadata;
- `AuthorityProducer` is not constructible through the core API;
- forbidden scorer fields rejected from runtime source-event structures.

Rollback boundary: one additive module/test commit; no persisted state or
caller changes.

Acceptance gate: byte-stable canonical fixtures, exact Gate 1B-R3 receipt field
set, exact Gate 1C-R3 RootKey, and unchanged existing suite.

## P1 — source receipt verification

Exact files:

- `custody/authority.py`;
- `custody/revision.py` only for a narrow source-revision-to-PolicyKey input;
- add static signed fixtures under `tests/fixtures/b7/`;
- `tests/test_authority.py` and `tests/test_revision.py`.

Invariant introduced: ACT roots enter only through a verified source-owned
object and exact P2 binding. `SurfaceAttestation` remains a separate dispatch
contract.

Tests:

- valid source receipt accepted;
- missing/forged receipt denied;
- wrong issuer/key/object/commitment/PolicyKey/scope/revision/generation/cap
  denied;
- copied receipt under a different Custody root ID denied;
- missing trust anchor/current policy denied;
- no test helper supplies an authority decision.

Rollback boundary: verifier/fixtures commit; no admission caller uses it yet.

Acceptance gate: all Gate 1B-R3 forgery/replay controls pass through production
verification, with the test scorer unavailable until after outputs are final.

## P2 — admission and derivation propagation

Exact files:

- `custody/authority.py` (`AdmissionGate`);
- `custody/origin.py`;
- `custody/service.py`;
- `custody/graph.py` for immutable envelope registration;
- `custody/adapters/adk.py`;
- `custody/adapters/memory_bank.py`;
- tests: `test_origin.py`, `test_service.py`, `test_graph.py`,
  `test_cross_session.py`, `test_cross_department.py`,
  `test_adk_memory_bank.py`, `test_adk_conformance.py`, and
  `test_agent_engine_memory_bank.py`.

Invariant introduced:

- ROOT only from verified source events;
- IDENTITY forwards exact support;
- REGISTERED unions all required parent dependencies and adds its transform
  dependency;
- FREEFORM retains observed support and never exceeds INFORM;
- exact-content resolution cannot manufacture ACT;
- cross-agent forwarding creates no root receipt.

API shape:

```text
AdmissionGate.admit_source(source_event, output)
AdmissionGate.admit_identity(parent_id, output)
AdmissionGate.admit_registered(transform_ref, parent_ids, output)
AdmissionGate.admit_freeform(parent_ids, output)
```

The separate entry points own transform classification. There is no generic
`admit(..., transform_class="REGISTERED")` caller-controlled shortcut.

Rollback boundary: eligible B7 path remains opt-in and produces no ACT until P3;
legacy path remains fail-closed/INFORM.

Acceptance gate: legitimate IDENTITY/REGISTERED and cross-agent cases preserve
bounded authority; malicious/missing-parent/mixed-invalid/FREEFORM cases cannot
ACT; every per-record Memory Bank retrieval returns the exact record ID metadata.
Failure to recover that metadata is a hard stop.

## P3 — current-state action gateway

Exact files:

- `custody/action.py`;
- `custody/authority.py` current-state evaluator and state-reader protocol;
- `custody/service.py` integration surface;
- callers `scripts/demo.py` and `scripts/gates.py` first, followed by every
  direct `ExportGateway` caller;
- tests: `test_action.py`, `test_adk_conformance.py`, and new B7 gateway cases.

Invariant introduced: a consequential action is executed only from durable
record IDs whose exact scope has current ACT after all parent, receipt,
generation, key, and revocation checks. Caller-created `CustodyRecord` objects
cannot authorize an action.

Required changes:

- `Export` cites immutable record IDs, not trusted dataclass instances;
- gateway owns/receives an authoritative state reader;
- final decision directly re-reads every required current generation and root
  revocation marker;
- no cached absence/freshness can ALLOW;
- gateway owns dispatch; ALLOW is not a reusable token returned to an arbitrary
  caller;
- decision trace contains IDs, scopes, bound/current generations, root keys,
  and reasons, never payload text or secrets.

Rollback boundary: preserve a separately named legacy demonstration gateway if
needed for historical proofs, but it is not wired to production ACT. No shim may
translate `Trust.TRUSTED` to B7 ACT.

Acceptance gate: A–L in `EQUIVALENCE_TEST_PLAN.md`, plus stale/missing store and
concurrent generation-change denials.

## P4 — selective receipt-root revocation

Exact files:

- `custody/authority.py` (`RevocationController` and effective-state check);
- `custody/graph.py`;
- `custody/control_plane.py`;
- `custody/adapters/memory_bank.py`;
- callers `scripts/revoke.py`, `scripts/incident.py`,
  `scripts/live_memory_deletion.py`, and `scripts/live_fleet.py` where relevant;
- tests: `test_graph.py`, `test_control_plane.py`, `test_cross_session.py`,
  `test_durable_graph.py`, `test_memory_deletion_gates.py`, and B7 revocation
  cases.

Invariant introduced: an append-only authenticated RootKey selector blocks all
supporting descendants immediately while pre-compromise, post-remediation, and
unrelated roots remain usable. Historical envelopes are unchanged.

Required behavior:

- selector never contains payload text;
- exact replay is idempotent; conflicting reuse of an event ID is rejected;
- action path reads root markers directly;
- reverse closure is a dependency query, not semantic traversal;
- deletion/quarantine is cleanup after logical block;
- cache invalidation cannot delay safety;
- coarse tool/revision revocation remains visibly separate.

Rollback boundary: root markers remain active even if cleanup code is rolled
back. A rollback that ignores them is prohibited.

Acceptance gate: all Gate 1C-R3 outcomes reproduce through production graph and
gateway APIs with zero historical rewrites and exact unaffected utility.

## P5 — durable Firestore/SQLite implementation

Exact files:

- `custody/firestore_store.py`;
- `custody/store.py`;
- `custody/control_plane.py` Firestore wiring;
- tests: `test_firestore_store.py`, `test_durable_graph.py`,
  `test_durable_integration.py`, and new independent-process B7 integration
  tests.

Invariant introduced: envelope plus dependencies are atomic and immutable;
policy/revocation/action decisions have explicit linearization; fresh processes
reconstruct identical authority; partial/missing state denies.

Required corrections to current code:

- replace B7 use of SQLite `INSERT OR REPLACE` with create-or-identical;
- replace Firestore's current “swallow `AlreadyExists`, then add caller bytes to
  memory” behavior with stored-byte comparison and conflict;
- perform parent/current-policy reads and envelope/dependency creates in one
  transaction;
- direct-read current policy/root state for ALLOW;
- make duplicate envelopes impossible;
- retain immutable records after logical revocation.

Rollback boundary: additive collections and readers land before B7 writes.
Once B7 ACT is enabled, rollback must preserve B7 reads and revocation markers.

Acceptance gate:

- production APIs reproduce E2H-R1E's safety metrics across independent W/P/G
  processes and real Firestore;
- restart reconstruction, transaction contention, partial admission, gateway
  race, stale cache, duplicate envelope, missing state, and killed writer all
  fail contained;
- the existing 90-second recovery metric is reported unchanged. Missing it is
  a liveness limitation and blocks a recovery-SLA claim, but does not erase a
  passing safety result.

## P6 — production-equivalence suite

Exact files:

- add `tests/test_b7_production_equivalence.py`;
- add immutable external-world fixtures under `tests/fixtures/b7/`;
- update existing tests only where public production APIs legitimately changed;
- no imports from `research/` or frozen runner code.

Invariant introduced: the experimental runner no longer implements B7. Tests
construct source events, call production public interfaces, and inspect durable
outputs/action traces.

Rollback boundary: tests-only commit after P0–P5; failures block P7.

Acceptance gate: every A–P case in `EQUIVALENCE_TEST_PLAN.md` passes twice with
stable normalized traces; forbidden-field/static-mechanism scans pass; full
existing suite passes; no benchmark/model/API call occurs.

## P7 — live source-to-action proof

Exact files:

- `live/registry_attack/server/server.py`;
- `live/gateway_probe/agent.py`;
- add `scripts/live_b7.py` and a deterministic offline judge/test;
- deployment manifests only if required by the existing live server build.

Invariant introduced: a deployment-owned source component emits the P2 event at
runtime over an object it owns; the relay has no issuer key; production Custody
persists/evaluates it; the actual action endpoint observes allow/deny.

Controls:

- legitimate source record through relay: ALLOW;
- attacker tool echo with no source receipt: DENY;
- forged/wrong-object/wrong-scope/stale-generation/replay: DENY;
- selective root revocation: affected DENY, unrelated/current replacement
  ALLOW;
- Firestore restart between admission and action;
- no model or benchmark labels.

Rollback boundary: live proof is isolated from shipping collections and uses a
new bounded namespace/source key. Cleanup never deletes unknown resources.

Acceptance gate: source-authored event/log, Custody envelope/dependencies,
authoritative action trace, and source dispatch evidence correlate by immutable
IDs. A fixture minted by `scripts/live_b7.py` is invalid—the deployed source
must emit it.

## Hard-stop conditions

Stop implementation immediately if any occurs:

1. a B7 requirement cannot be represented without semantic inference or a new
   security primitive;
2. the source producer needs scorer/attack truth;
3. a caller can select ACT/REGISTERED or invoke a generic signer;
4. per-record ID/support metadata cannot survive storage/retrieval/restart;
5. admission cannot atomically persist the envelope/dependency set;
6. action ALLOW requires trusting a stale cache or caller-constructed record;
7. migration would grant legacy records ACT; or
8. the change expands into replacing Custody/ADK/Memory Bank rather than a
   bounded extension.

## Risks and release boundary

Biggest implementation risk: complete identity/support capture through the
real Memory Bank and agent-to-agent retrieval path. Cryptographic receipt
verification is straightforward; silently losing one required parent or record
ID would recreate provenance laundering behind a stronger-looking schema.

Secondary risk: Firestore orphan-lock recovery exceeded 90 seconds in E2H-R1E.
Safety was fail-contained, but operator-facing recovery latency is unresolved.

No new research mechanism is required. Release authorization is distinct from
implementation authorization: production ACT stays disabled until P6 passes;
an end-to-end deployment claim waits for P7 and must preserve the liveness
limitation if still present.
