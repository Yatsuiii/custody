# Mechanism Candidates — Comparative Evaluation

The candidates differ in where provenance comes from and which component must
be trusted. Outcomes below are design predictions, not implementation results.

## A — Central structural admission envelopes

An in-TCB admission gate atomically binds each output to direct stored-record
parents, an operation-level `ORIGIN`/`RELAY` role, a transformation class, and
the action-scoped authority algebra in `AUTHORITY_MODEL.md`. Compromise windows
select authoritative admission-time roots; an immutable overlay blocks their
descendant closure. Free-form output keeps support but is capped at `INFORM`.

## B — Persistent ambient IFC state

Extend today's `tainted`/`lineage` dictionaries into a durable, cross-session
state machine. Keep exact-hash retrieval as the only way to reconnect a later
invocation, do not require explicit input receipts, and retain tool-name trust.
This is the smallest code-shaped extension of current Custody.

## C — Distributed signed capability receipts

Every tool, retrieval service, and transform signs a capability-carrying
receipt over its output, parent receipts, action scopes, and timestamp. The
store verifies signatures and builds the graph from those decentralized
statements. This does not use a central context observer, but makes every
signing producer and its key custody part of the trusted computing base.

## Evaluation matrix

| Case/property | A — structural envelope | B — ambient IFC | C — signed capabilities |
|---|---|---|---|
| Trusted-tool echo (E2A) | Handles structurally when the operation is `RELAY`: observed upstream authority is met; unknown upstream is capped at `INFORM` | Fails for the measured reason: tool-name trust still replaces payload provenance | Handles only if the relay signs truthful upstream dependencies; a valid signature over a lie does not help |
| Exact retrieval | `IDENTITY` receipt may preserve parent caps and support | Preserves today's exact-hash positive control | Preserves via cited signed parent |
| Benign paraphrase (E2B/E2C control) | Keeps ancestry and informational utility; free-form output is deliberately not `ACT` | Loses ancestry at the same hash cliff and blocks it as unknown | Keeps signed ancestry, but a signature alone does not prove semantic fidelity; still capped at `INFORM` unless a registered transform applies |
| Malicious paraphrase | A `NONE` parent remains `NONE`; hidden/incomplete context is at most `INFORM`; later revocation still reaches the output | Safe only accidentally when the original poison was never stored; no traceable edge survives | Same algebra as A if all parents are honestly signed; compromised signers can lie |
| Same-invocation summarization | Receipt names every exposed input; free-form cap applies | Current boolean taint handles untrusted input, but trusted free-form content remains globally trusted | Signed parent chain can represent it; semantic cap still required |
| Cross-agent relay | Parent record ids are independent of department/invocation; department policy still bounds action scopes | Works only for byte-identical content, as current Custody already shows | Works across signers if key/domain policy is shared and verified |
| Multi-parent synthesis (E0/E1) | Direct-parent set plus support union preserves every parent | E1's current in-invocation fix works, but there is no action-scoped computation over the parents | Parent receipt set can represent it, at greater key/distribution cost |
| Manufactured corroboration | No elevation operator exists; safe but conservative | No elevation operator; safe but conservative | Signatures prove identities, not independence; still needs a separate domain-aware elevation design |
| Hallucinated or undeclared content | Provenance is not treated as entailment; free-form/incomplete output is at most `INFORM` | A clean model turn remains globally trusted today | A signed model statement remains a model statement; without the same cap, signatures would overstate it |
| Post-hoc whole-source compromise | Overlay can express whole-source as an unbounded window | Existing demote/revoke handles this | Requires revocation of signer capabilities plus descendant processing |
| Bounded compromise interval (case K) | Selects source roots by authoritative `admitted_at`, then walks descendants | No interval selector or authoritative time rule | Can encode signed time, but clock/key trust and interval revocation still need a controller |
| Uncertain or widened interval | Canonical widening is a new monotonic window version; blocked sets only grow | Not representable | Representable, with the same controller complexity as A plus distributed clocks |
| Selective repair | Old records stay blocked; only a replayed transform creates a clean replacement | Whole-descendant deletion only | Can issue replacement receipts, but signatures do not remove the need for replay |
| Unaffected sibling outside interval | Preserved if its support does not intersect selected roots | Whole-tool revocation deletes it | Preserved if the interval and signed times are correct |
| Weakly contributing parent | Conservatively full support; measurable collateral remains | E1 conservatively keeps the edge; same collateral | Same unless a verifiable field-level transform is introduced |
| Missing provenance | Explicit `UNKNOWN_CONTEXT`; at most `INFORM`, never silently fresh | Exact-hash miss falls back to tool identity, which E2A falsified | Rejects missing/invalid signature, but availability depends on every producer participating |
| Direct store/receipt tampering (case P) | Not addressed beyond exclusive write/IAM assumption | Not addressed | Detects alteration covered by signatures, but not a compromised authorized signer |
| Schema evolution | Versioned envelope; legacy records become `LEGACY_UNKNOWN` and cannot claim interval precision | Lowest migration cost because it changes little | Highest: key rotation, algorithm versioning, and old-signer compatibility are required |
| Write atomicity/replay | One idempotent envelope write, then outbox publication; revocation intent precedes asynchronous repair | Inherits today's graph/downstream split and its crash windows unless separately redesigned | Signed write is replayable, but distributed partial failure is harder |
| Storage/runtime cost | Direct parent ids plus policy metadata; support is derived, not duplicated | Lowest | Highest: signatures, key ids, verification results, and parent receipts |
| Trusted computing base | Context/receipt collector, policy catalog, authoritative store clock, revocation overlay, action gateway | Today's ADK/store boundary; insufficient information remains the core problem | Every signer and key service, verifier, clocks, revocation distribution, action gateway |

## Decision from the matrix

Candidate B is cheap because it declines to add the information E2A and E2C
show is missing. It cannot distinguish a relay from an origin and cannot create
an edge after any byte change. It is therefore not a viable mechanism for the
stated invariants.

Candidate C addresses a different adversary: alteration of provenance after a
producer emits it. No experiment in this branch grants an attacker store-write
or signer-forgery capability. It also does not solve semantic fidelity: a
signature proves who asserted a paraphrase, not whether the paraphrase is true.
Its key and clock surface is unjustified in the current threat model.

Candidate A is the minimum candidate that carries the missing structural facts
without semantic inference or unmeasured cryptography. It is selected for the
preregistered falsifier, with one decisive caveat: the current ADK/Memory Bank
path has not yet proved it can expose a complete set of record ids for every
piece of model context. That unresolved trusted-boundary obligation is why the
final decision is cautious rather than production-authorizing.
