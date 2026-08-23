# B7 Production Trust Boundary

Status: `FROZEN-DESIGN-DRAFT — DO NOT IMPLEMENT`

## Research-only provenance answer

B7 does **not** intrinsically require an oracle. Its authority input can be
produced from facts available at a real source boundary:

1. an object/record the source service legitimately owns;
2. the source's authenticated identity and key;
3. the source revision;
4. a configured PolicyKey/current generation; and
5. the bounded capability/scope configured for that source operation.

No one in that path needs `true_origin`, an attack label, expected behavior,
scorer truth, or payload classification. If those source facts are unavailable,
B7 returns no ACT authority. That is an unsupported deployment path, not an
invitation to infer provenance from content.

## Actors and ownership

| Actor | May do | Must not do |
|---|---|---|
| Source service / source adapter | read an object it owns; read the current configured PolicyKey generation; emit the source object plus a P2 receipt signed by its issuer key | sign an object outside its owned namespace; accept caller-provided cap/scope/generation without enforcing source policy; consume scorer labels |
| Relay/tool process | forward the source object and unchanged receipt; add transport metadata | hold the issuer private key; mint, broaden, rebind, or replace a receipt merely because it can return content |
| Custody `AdmissionGate` | canonicalize the presented object; verify signature/bindings; construct immutable root/derived envelopes from observed parents and policy | accept self-declared authority, missing parents, receipt-looking payload text, or test/scorer decisions |
| Registered transform executor | execute one configured transform revision over exact observed parent IDs; add its own transform PolicyKey dependency | select REGISTERED from free-form model text; omit required parents; grant a cap above parent/transform meet |
| Model / FREEFORM producer | produce text; retain observed parent lineage for audit/INFORM | mint ACT, choose source identity, assert parent completeness, or issue receipts |
| Durable authority store | atomically create immutable envelopes/dependencies and append policy/revocation state | overwrite an existing envelope or treat a partial record as committed |
| Action gateway | resolve cited record IDs, re-read current authoritative state, evaluate all dependencies, and own the dispatch boundary | trust caller-supplied records, cached absence of revocation, stale generation, or a reusable prior ALLOW |
| Revocation controller | append authenticated receipt-root selectors and compute affected records | select by payload text, rewrite envelopes, or delete a bad parent to elevate survivors |

## Provider-neutral source contract

The production core consumes evidence; it does not provide a generic signer.
Conceptually, the boundary is:

```text
SourceAuthorityEvent
    source_object: canonical object/record owned by the producer
    receipt: AuthorityReceipt

AuthorityVerifier.verify(SourceAuthorityEvent, current_policy, trust_store)
    -> VerifiedSourceRoot | Denial
```

`AuthorityProducer` may exist in a source-service SDK, but not as a Custody API
that accepts arbitrary content and caller-chosen authority fields. Its deployment
contract is:

```text
issue(owned_object_id, operation)
```

The producer itself loads the owned object and configured policy. It does not
accept object bytes, `granted_cap`, `action_scope`, `PolicyKey`, or generation
from the relay request as authoritative input. A stale policy read is safe: the
receipt binds that generation and the action gateway later denies it if the
generation is no longer current.

## Concrete deployment boundaries

### Signed webhook source — strongest external boundary

A Stripe webhook receiver is a realistic deployment-owned producer boundary:

- verify the provider signature against the unmodified raw request body and
  signed timestamp;
- use the authenticated event ID/object ID and API version as source identity,
  object identity, and revision inputs;
- load the deployment's configured PolicyKey/current generation;
- issue P2 only after provider verification succeeds;
- send unverifiable HTTP bodies down the same ingestion path with no receipt.

The adapter does not decide whether an event is benign or malicious. Both cases
are instrumented identically; only possession of valid provider evidence
differs. A provider signature authenticates the event, not its truth or wisdom.

### Deployment-owned MCP source

`live/registry_attack/server/server.py` is already an independently deployed
process with a server-only key and an owned `_customer_record` function. It is a
valid P7 **ORIGIN** producer candidate if it signs the returned customer object
at runtime. Its current `SurfaceAttestation` is insufficient: that token binds
`tools/call` to a `tools/list` digest, not the returned record. The two token
types and keys remain separate.

An MCP server acting as a relay over a hidden web page or upstream API may not
sign that page as its own authoritative object. It can forward upstream B7
evidence if present; otherwise its result is at most INFORM.

### Signed content source

A C2PA manifest can establish signer identity and object/content binding for an
asset. A provider-specific adapter may map a validated asset into a B7 source
event, but C2PA alone does not grant an action capability or assert factual
truth. PolicyKey/cap assignment remains deployment policy, not content-derived.

## Issuer/key boundary

- Gate 1B-R3's P2 primitive remains Ed25519.
- The private key exists only in the source service/source adapter.
- Custody stores or resolves only public trust anchors keyed by
  `(issuer_id, issuer_key_id)`.
- Relay, model, memory service, action caller, scorer, and test runner never
  receive the private key.
- Missing key, unknown issuer, malformed key, signature failure, or key access
  failure returns DENY.
- Rotation adds a new key ID. Existing receipts remain verifiable only while
  their trust anchor is retained; deleting a key must not silently look like a
  selective receipt-root revocation.

Key compromise response beyond disabling a trust anchor is operational policy.
B7's validated selectivity is receipt-root revocation, not an invented
key-compromise recovery protocol.

## Benign/malicious instrumentation symmetry

The same source adapter, verifier, admission API, store, transform APIs, and
gateway are used for every case:

| Runtime input | Receipt result | B7 outcome |
|---|---|---|
| source-owned object returned through a relay | source-issued, object-bound receipt verifies | bounded root authority may propagate |
| attacker/free-form payload returned by that relay | no source receipt | no ACT |
| forged or modified receipt | signature/binding verification fails | no ACT |
| valid receipt replayed for another object/record/scope/revision | binding mismatch | no ACT |
| source receipt from an old generation | generation mismatch at action | no ACT |

There is no branch named benign, malicious, attack class, expected action, or
scorer result.

## Transform and relay boundary

- ROOT: admitted only from a verified `SourceAuthorityEvent`.
- IDENTITY: created only by a structural copy/forward operation over one exact
  existing record ID; it forwards support and adds no root authority.
- REGISTERED: created only through a configured transform revision and exact
  observed parent IDs; it unions all support and adds its transform dependency.
- FREEFORM: automatically assigned to model/free-form output; it retains
  observed support for audit but is capped at INFORM.
- Cross-agent forwarding is IDENTITY or REGISTERED depending on the configured
  operation. The receiving agent cannot turn a receipt copy into a new root.

## Leakage exclusions

Production APIs, event schemas, logs, tests, and live fixtures must reject or
scan for fields equivalent to:

`true_origin`, `attacker_controlled`, `malicious`, `benign`, `attack_type`,
`adversarial_goal`, `expected_memory`, `expected_allow`, `expected_action`,
`ground_truth`, `scorer`, and `unauthorized_action`.

The scorer is enabled only after all production action traces are final. Tests
may hold expected outcomes in a separate assertion table; that table is never
passed to source production, admission, storage, transformation, revocation, or
gateway constructors.

## Trust-boundary acceptance gates

1. The source producer loads its own object; a relay cannot submit arbitrary
   object bytes to be signed.
2. The relay process has no issuer private key.
3. A legitimate and attacker event traverse the same adapter and production
   APIs.
4. P2 verification uses no content classifier or scorer field.
5. Sources lacking authenticated object evidence are retained only under the
   fail-closed legacy/FREEFORM policy.
6. The P7 source event is emitted at runtime by the deployed source component,
   not minted by the production-equivalence runner.

Failure of gates 1, 2, 3, or 6 is a hard stop for implementation authorization
of the corresponding source adapter.
