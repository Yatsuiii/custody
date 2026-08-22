# Gate 1B — Trusted-Provenance Boundary

Status: design only. This document defines a trust boundary for a future
falsifier; it does not add the boundary to Architecture A.

## Trust decision

The exact trusted producer for the selected candidate is the policy-authorized
source service that owns the authoritative upstream record. A source-side
adapter may host the issuance code only as part of that source service's
trust-computing base; it is not a second independent trust root. The producer
is not the trusted relay, the scorer, the action target, or the memory
collector.

For a deployment, the producer must already be an authority-bearing component:
it knows the structured record/fact it is returning and the policy grant that
permits the requested action. It issues an immutable origin authority receipt
at the source boundary. A relay can transport that receipt but cannot mint,
edit, or broaden it. If the source service cannot make this assertion, the
value has no consequential authority.

This is intentionally a real trust assumption. It is not a claim that the
current Gate 1 fixture has such a producer. Gate 1A established that it does
not.

## Three-layer boundary

### L1 — world and scorer ground truth

The hidden scorer may know attacker control, causal origin, intended harmful
action, expected dependencies, and verdict labels. No producer, relay,
collector, verifier, or gateway receives this object. A test harness may not
populate a receipt by copying a scorer label.

### L2 — canonical observed event

All systems can observe the ordinary event: payload/content, tool identity,
operation/task, source/revision as actually exposed, action request, and
ordinary event metadata. These fields do not prove upstream authority.

### L3 — baseline-native provenance evidence

The selected P2 candidate adds only an issuer-authenticated receipt produced by
the source service's normal authority boundary. The receipt is a security
input because the candidate's declared runtime contract requires it, not
because the scorer calls a value trusted.

## Component responsibilities

| Component | May know | May issue or change authority | Required trust |
|---|---|---|---|
| Source service / source adapter | authoritative structured upstream record, policy key, scope, current granting generation | issues the receipt for that exact object/claim; cannot issue outside its configured policy | source service, key custody, and policy configuration |
| Policy authority | current policy version/generation, scope, revocation state | advances generation or revokes an issuer/record closure | authoritative policy store |
| Relay/tool | returned value, operation result, any receipt it was given | transports an existing receipt only; never mints or relabels one | relay is not an authority root |
| Collector/admission | observed event, parent IDs, receipt bytes | stores immutable envelope/dependencies; no authority expansion | input validation and atomic persistence |
| Verifier/action gateway | durable envelope, receipt, support/dependencies, current policy | computes effective cap and final ALLOW/DENY | verification key roots, policy reads, fail-closed behavior |
| Scorer | hidden labels and expected outcomes | none in treatment runtime | scorer-only |

## Receipt information and provenance

The minimum receipt information is:

| Field | Producer | What it binds | Failure if absent/incorrect |
|---|---|---|---|
| receipt identity/version | source service | canonical receipt format and idempotent identity | reject malformed proof |
| issuer and verification-key identity | source service/key authority | who made the claim | reject unknown/untrusted issuer |
| upstream record identity | source service | immutable object that received authority | reject fabricated/unrelated record |
| structured authority-claim commitment | source service | object/fact binding without requiring literal text equality | reject wrong value/object |
| canonical PolicyKey | source service/policy authority | the policy namespace, not a global generation | reject wrong source/scope |
| granting generation | policy authority observed by source | the policy grant that made the authority valid | stale/ABA deny at action |
| action scope and bound cap | policy authority/source service | exact operation that may be authorized | scope mismatch or cap expansion deny |
| source revision | source service | revision of the authority-bearing operation | wrong revision deny |
| issuer authentication | source service/key authority | integrity and non-malleability of the above fields | reject unverifiable proof |

The proof binds to a canonical authority-bearing object or structured claim.
It is not a semantic classifier and is not required to hash arbitrary
registered text byte-for-byte. A registered transform must retain the root
proof and its dependency; a new structured claim is permitted only when the
existing transform contract defines the mapping.

## Gate 1 benign/attack boundary

The future falsifier must keep the published tool-echo value, relay identity,
and consequential action. The only new treatment-native input is whether the
source boundary actually supplied a valid receipt:

1. **Benign path:** an authoritative source service returns the legitimate
   structured account record and emits a receipt before the relay returns it.
   The relay forwards the receipt.
2. **Tool-echo path:** an attacker-controlled value is returned through the
   trusted relay without an issuer receipt. The relay's identity remains
   trusted for transport but cannot manufacture source authority.

The receipt is not constructed from a scorer field. Its producer is the
source-side authority event. If a benchmark cannot expose that producer
without setting true_origin from hidden labels, the case is
BENCHMARK-INTERFACE-AMBIGUOUS rather than a security pass.

## Verification contract

At admission and again at consequential action, a verifier must establish:

1. receipt authentication and issuer trust;
2. exact upstream record/claim binding;
3. action-scope and cap containment;
4. source/revision and PolicyKey match;
5. granting-generation freshness against the authoritative current policy;
6. receipt support preserved through every parent and transform;
7. revocation status for the issuer/record/generation; and
8. no missing or conflicting required security state.

Unknown, malformed, missing, or conflicting proof is NONE and DENY. The relay
cannot turn an absent proof into INFORM/ACT by asserting that it is trusted.

## Transform and graph boundary

- **IDENTITY:** forwards the receipt and dependency unchanged.
- **REGISTERED:** retains all parent IDs, support roots, receipt dependencies,
  and the registered operation-policy dependency. It may cap or map authority
  but cannot replace the root grant.
- **FREEFORM:** retains support for audit only and is capped at INFORM.
- **Cross-agent:** transports evidence without minting; the final verifier
  checks the original issuer and support closure.
- **Multi-parent:** unions all direct parents and authority dependencies.
  One valid parent cannot wash an absent, stale, forged, or revoked parent.

## Generation and revocation boundary

The source receipt carries the PolicyKey and exact granting generation. A
current child generation is not a substitute for an inherited root generation.
The action gateway performs per-key current-generation checks, so semantic ABA
equivalence does not refresh an old receipt.

When the source is compromised later, the policy/revocation authority advances
the affected generation or selects the affected issuer/record closure. The
gateway denies affected descendants without rewriting receipts, payload
commitments, parent IDs, or admission metadata. Unrelated policy keys and
unaffected roots remain eligible.

## Trust-root failure analysis

The source service is the component that knows whether a value is an
authority-bearing record. If that service is itself compromised, a receipt can
be honestly signed but substantively wrong. No cryptographic receipt can infer
truth without a trusted issuer. The design therefore requires:

- source key custody and issuer configuration to be explicit;
- a policy authority able to revoke or advance the affected generation;
- an action gateway that verifies directly against current policy;
- no global trust token and no fallback to payload semantics.

This residual assumption is the same category as TMA-NM's authenticated
origin-monitor assumption. It is disclosed, not claimed as novelty.

## Data-system review boundary

The smallest future implementation would need an atomic immutable admission
record plus receipt/dependency rows, an authoritative per-key policy read,
idempotent output identity, and a fail-closed action gate. It must preserve
historical proof fields while allowing current effective authority to change.
Any design that requires asynchronous repair before denying an incomplete
record, global generation invalidation, or last-write-wins authority is outside
this plan.

## Acceptance gates for a future falsifier

1. The source-side producer is independently represented and is not a scorer
   projection.
2. The relay cannot mint or broaden the receipt.
3. A valid benign receipt allows the legitimate action.
4. Tool echo without a receipt is denied without payload inspection.
5. Forged, wrong-object, wrong-scope, wrong-generation, and replay controls
   are denied.
6. IDENTITY/REGISTERED/FREEFORM and multi-parent behavior preserve the frozen
   authority rules.
7. The closest prior-art primitive is run or explicitly marked unavailable.

No acceptance gate authorizes implementation in this session.
