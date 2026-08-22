# Gate 1B — Candidate Provenance Primitives

Status: design comparison only. These are not Architecture A changes and are
not executable specifications.

## Selection criteria

A candidate is useful only if it can distinguish the Gate 1 benign and
tool-echo cases without inspecting text semantics or receiving scorer truth.
It must also preserve the frozen Custody properties:

1. no authority amplification through a relay or transform;
2. legitimate IDENTITY and bounded REGISTERED derivation;
3. FREEFORM cannot manufacture consequential ACT;
4. per-PolicyKey generation freshness, including ABA rejection;
5. source-compromise revocation without rewriting history;
6. all-parent support/dependency preservation; and
7. a plausible trusted producer outside the scorer.

The candidate comparison is against the Gate 1A structural projection, not
against payload classifiers.

## Candidate matrix

| Candidate | Missing bit supplied | Minimum trusted TCB | Gate 1 separation | Main failure/forgery risk | Disposition |
|---|---|---|---|---|---|
| P0 — relay identity only | vendor_lookup is trusted | policy/configuration only | no; both cases still look like a trusted relay | relay can echo any attacker value | negative baseline |
| P1 — authenticated upstream record handle | immutable upstream record reference | issuer/record store and verifier | only if the handle is authenticated and the record is bound to the exact authority claim | fabricated ID, unrelated trusted record, wrong scope/value | insufficient by itself; secured form collapses into P2 |
| P2 — origin authority receipt | issuer-authenticated authority claim bound to an upstream object/claim | source authority or trusted adapter plus verifier | yes; benign has a valid source proof, tool echo does not | receipt confusion, replay, scope/generation mismatch | selected minimum candidate |
| P3 — capability/delegation | unforgeable scoped right to act | capability issuer, key/delegation verifier | only when capability is also bound to the authority-bearing object/claim | unbound token authorizes the wrong value; delegation overreach | known prior family; object-bound form is P2-equivalent |
| P4 — per-hop endorsement | each transform attests received/forwarded authority | every hop plus verifier | yes if a valid root proof remains present | larger TCB, endorsement laundering, parent dropping | not minimum; root P2 still required |
| P5 — semantic/content classifier | inferred “safe” value | classifier/oracle | sometimes, but not authority proof | false positives, adversarial text, disallowed semantic trust | rejected by frozen design |

## Minimum-information result

The smallest trusted invariant is not a single Boolean. It is a verifiable
binding over the minimum tuple:

    issuer I
    immutable authority-bearing upstream object or structured claim O
    policy key K = (department, source, operation, revision, action_scope)
    granting generation g
    action scope s
    bound capability c

The verifier must establish that I authorized O for s at K@g, and that the
presented memory/record is the object or a permitted registered transformation
of that object. A relay identity without this binding proves only who returned
the value, not why the value may authorize an action.

### Proposed P2 shape (design notation only)

The selected candidate is an origin authority receipt, not a proposed
production field name. A future falsifier may represent the proof as:

    AuthorityReceipt(
        receipt_id,
        issuer_id,
        issuer_key_id,
        upstream_record_id,
        authority_claim_commitment,
        policy_key,
        granting_generation,
        action_scope,
        bound_cap,
        source_revision,
        receipt_version,
        issuer_authentication
    )

The receipt is immutable once issued. authority_claim_commitment commits to
the canonical authority-bearing upstream object or structured fact, not
necessarily to the literal text returned by a tool. This is deliberate: an
exact raw-payload hash would recreate the E2C legitimate-transform cliff.
Registered transformations retain the upstream support and may introduce a
new structured commitment only when their already-frozen transform contract
authorizes that mapping. A free-form rewrite receives no new consequential
authority from text similarity.

This notation does not prescribe a cryptographic algorithm, key service,
receipt cache, signature format, or production schema. Those choices are
outside this design phase.

## Candidate behavior under the frozen transforms

| Transform | Receipt/dependency behavior | Consequential result |
|---|---|---|
| IDENTITY | Preserve the immutable receipt and its upstream dependency unchanged. | Eligible only while scope, generation, and revocation checks pass. |
| REGISTERED | Preserve every parent receipt/dependency and add the transform's own operation-policy dependency. A registered structured mapping may create a new claim commitment, but cannot replace the root grant. | Bounded authority is the meet of bound cap, transform cap, all required parent support, receipt scope, and current generation. |
| FREEFORM | Preserve support for audit, but do not mint or upgrade an authority receipt from content similarity. | effective_cap <= INFORM; no consequential ACT. |

The relay may forward a receipt. It cannot mint, edit, broaden, or relabel a
receipt. Cross-agent forwarding has the same rule.

## Critical forgery and replay analysis

| Case | Required verifier behavior |
|---|---|
| 1. Malicious relay fabricates upstream_record_id | Reject: no issuer-authenticated receipt or the record/claim commitment does not verify. |
| 2. Relay replays an old valid receipt | Exact replay for the same immutable object is only idempotent forwarding; it grants no new object. A receipt presented for a different object/record fails. A receipt whose policy generation is no longer current is stale and denies. |
| 3. Receipt belongs to a different payload/value | Reject the commitment/object binding. No raw-text similarity fallback. |
| 4. Receipt belongs to a different action scope | Reject the signed scope mismatch; do not meet an unrelated scope into ACT. |
| 5. Receipt belongs to a different source revision | Reject the signed source_revision/policy-key mismatch. |
| 6. Receipt belongs to an old policy generation | E2F action-current check denies; generation g1 never becomes fresh because a relay or child was created at g3. |
| 7. Receipt belongs to an unrelated trusted record | Reject the immutable record/claim binding even if its issuer and cap look trusted. |
| 8. Multi-parent child mixes one valid and one unproven input | Preserve both parents/support roots/dependencies; any required unproven or stale authority makes the consequential action deny. A clean parent cannot wash the other. |
| 9. FREEFORM tries to preserve ACT | Keep support for audit, cap the transform at INFORM, and deny consequential ACT. |
| 10. Cross-agent relay forwards a receipt | Forwarding is allowed only without alteration; the final verifier checks the same issuer, object, scope, generation, and dependency chain. |
| 11. Issuing source is compromised after issuance | Policy/revocation authority advances the affected key/generation or revokes the issuer/record closure. Historical fields remain unchanged; affected descendants deny while unrelated roots remain usable. |

These controls are requirements for a future falsifier, not claims that the
primitive has been implemented.

## Generation, revocation, and support rules

### Generation

The receipt carries the exact PolicyKey and granting generation that issued
the authority. Action checks resolve the current generation for that key. A
semantic match between v1@g1 and v3@g3 does not satisfy freshness. A child
creation generation never substitutes for an inherited granting generation.

### Revocation

The source or policy authority may advance a generation or activate a bounded
revocation selector. The gateway evaluates the receipt and the full support
closure at action time. Revocation changes effective authority, not immutable
receipt fields, parent IDs, payload commitments, or historical admission
metadata. Unrelated policy keys remain unaffected.

### Multi-parent

For C = REGISTERED(A, B), the direct-parent set and the union of all support
roots/receipts are retained. The action gate evaluates every dependency
required for the requested scope. A valid proof on A cannot wash an absent,
forged, stale, or revoked proof on B.

## Why P1, P3, and P4 are not smaller

- P1 is only safe when the record handle is itself authenticated and resolved
  to an immutable authority claim. That authenticated handle is already the
  object-bound part of P2.
- P3 is established delegation technology. A token with only subject/scope
  caveats authorizes a holder, not a particular tool-returned value. Binding
  it to the upstream claim, policy key, and generation turns it into P2.
- P4 adds attestations at every hop but still needs a trusted root proof. It
  increases the TCB and audit surface without supplying a smaller invariant.
- P5 is not provenance. It is a semantic inference mechanism explicitly
  excluded from this line of work.

## Novelty disposition

P2 is the minimum candidate that could make Gate 1 utility possible without
content semantics. It is not a novel primitive: TMA-NM already assumes the
essential authenticated origin distinction, MemLineage supplies signed
provenance plus derivation enforcement, and capability/delegation systems
provide object-bindable authority tokens.

The defensible hypothesis is therefore COMPOSITION-NOVELTY-ONLY: an
authenticated authority proof might be composed with Custody's tested
derivation-stable authority, per-key generation invalidation, retrospective
selective revocation/repair, multi-parent support preservation, and durable
cross-process enforcement. That composition remains untested and is not
implemented here.
