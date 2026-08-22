# Requirements From Failures

This document separates evidence-forced primitives from attractive extras.
"Forced" means that removing the primitive recreates a measured or
code-demonstrated failure. It does not mean the proposed mechanism has passed
an implementation test; that remains the job of `DESIGN_FALSIFIER.md`.

## Security invariants

- **I1 — no amplification:** for every action scope, a derived record cannot
  receive more authority than its least-authorized declared input or its
  transformation policy permits.
- **I2 — transformation-stable provenance:** a declared transformation keeps
  structural ancestry across byte changes. This guarantees traceability, not
  semantic fidelity.
- **I3 — complete multi-parent support:** every structurally exposed input is
  represented; no parent is silently overwritten.
- **I4 — authority is not content:** wording, hashes, embeddings, and model
  judgments do not mint authority.
- **I5 — relay non-elevation:** a relay's identity cannot vouch for payloads it
  did not originate.
- **I6 — interval completeness:** every admitted source root inside a declared
  compromise window, and every descendant of those roots, becomes ineffective.
- **I7 — interval non-interference:** records supported only by roots outside
  the window remain effective.
- **I8 — monotonic repair:** revocation never raises an unchanged record's
  authority; useful content is restored only as a newly derived replacement.
- **I9 — action scoping:** authority for one consequential action does not imply
  authority for another; an unspecified scope defaults to no authority.

I1-I8 are tied below to E0/E1/E2A/E2B/E2C or the code-grounded interval
failure K. I9 is a user-required hostile case, not an experimentally isolated
result: E2A exercised only `export.send`. The design includes I9 at the algebra
boundary, but does not claim evidence for a multi-action effect that has not
been measured.

## Candidate 1 — Authority separate from content

- **Evidence:** E2A gave an attacker payload full authority solely because a
  trusted runtime name relayed it. E2C showed a one-character change, a
  paraphrase, and unrelated text all become identical after the exact-hash
  miss. Content bytes therefore cannot carry the missing authority fact.
- **Invariants:** I1, I4, I5.
- **Simpler mechanism check:** tool identity alone is the measured E2A failure;
  content similarity would infer rather than prove authority and is outside the
  deterministic claim. The minimum remaining representation is explicit
  authority metadata bound independently of text.
- **Boundary introduced:** the component that binds authority is in the trusted
  computing base and must be auditable.
- **Disposition:** required.

## Candidate 2 — Structural derivation receipts

- **Evidence:** E2C located the cross-invocation cliff at
  `CustodyGraph.resolve` (`custody/graph.py:187`): exact bytes produce an edge;
  any changed bytes produce none. E1 separately showed that the existing graph
  works once all real parents are supplied.
- **Invariants:** I2, I3, I4.
- **Simpler mechanism check:** persisting today's invocation-local `lineage`
  state still provides no cross-invocation signal. A receipt containing the
  record ids actually exposed by the in-TCB orchestration layer is the minimum
  non-semantic signal. If that layer cannot observe an input id, the design
  marks context incomplete and fails closed; it does not invent an edge.
- **Boundary introduced:** the receipt collector, not the model or arbitrary
  tool, must attest which stored records entered context.
- **Disposition:** required.

## Candidate 3 — Pointwise meet over action scopes, union over support

- **Evidence:** E0 reproduced a real two-parent synthesis whose missing edge
  caused asymmetric revocation; E1 proved a multi-parent DAG is sufficient.
  E2A proved that a single global trusted bit is too coarse at the action gate.
- **Invariants:** I1, I3, I4, I9.
- **Simpler mechanism check:** a scalar loses both the contributing roots needed
  for interval repair and the distinction between action types. The minimum
  deterministic algebra is a finite map `ActionScope -> Tier`, combined
  pointwise with `meet`, while logical root support combines with set union.
  Missing scopes default to `NONE`, so adding action scopes is fail-closed.
- **Boundary introduced:** none beyond Candidates 1 and 2; this is a pure
  computation over policy and declared parents.
- **Disposition:** required. I9's schema shape is specified now; its utility is
  not claimed until a multi-action falsifier exists.

## Candidate 4 — Operation-level ORIGIN versus RELAY policy

- **Evidence:** E2A's `tool_echo` attack is exactly the case a tool-name trust
  lookup cannot distinguish: the same runtime returns genuine data and relayed
  attacker data with identical standing.
- **Invariants:** I5, and therefore I1.
- **Simpler mechanism check:** inspecting arbitrary tool code or trusting a
  tool-supplied `upstream_id` would move the same unverified claim to a new
  field. Each tool operation is configured as `ORIGIN` or `RELAY`; ambiguous
  and mixed operations default to `RELAY`.
- **Boundary introduced:** role policy and any connector that vouches for
  external upstream provenance enter the trusted computing base.
- **Disposition:** required.

## Candidate 5 — Interval selection over authoritative admission time

- **Evidence:** red-team case K is a code-demonstrated failure: tool and
  revision revocation cannot distinguish records admitted during days 12-18
  from records admitted outside that window. E2A's measured revision-aware
  control additionally showed that even a pre-issued revocation for the exact
  revision does not affect a later matching write. Current Firestore records
  already carry a server-assigned `admitted_at`; the graph does not query it.
- **Invariants:** I6, I7.
- **Simpler mechanism check:** a new trust-epoch field on every record is not
  required for the first falsifier. The minimum is an append-only compromise
  window plus root selection by `(source, optional revision, admitted_at)` and
  the existing descendant closure. The window is explicitly in admission-time
  coordinates; uncertain source-time windows must be widened before use.
- **Boundary introduced:** only stores that can provide authoritative admission
  time qualify. `None`, caller-supplied, SQLite legacy, and in-memory times are
  unclassifiable and fall back to conservative whole-source handling.
- **Disposition:** required.

## Candidate 6 — Revocation overlay plus replacement-only repair

- **Evidence:** E2B measured benign collateral from fail-closed transformation
  loss; E1 showed a mixed descendant can have several parents; case K requires
  preserving outside-window siblings. These together require a result more
  precise than deleting a tool's entire history.
- **Invariants:** I6, I7, I8.
- **Simpler mechanism check:** immediately deleting every affected descendant
  is safe but cannot support review, retry, or selective restoration. Merely
  removing a bad support entry and re-running `meet` on the unchanged text is
  unsafe: `meet(NONE, ACT)=NONE`, then deleting the `NONE` parent would raise
  the same text to `ACT`. The minimum safe rule is an immutable revocation
  overlay; restoration requires a newly executed transform and a new record.
- **Boundary introduced:** the action gateway must consult the current overlay,
  and the repair worker must be idempotent and crash-resumable.
- **Disposition:** required.

## Candidate 7 — Corroboration-based elevation

- **Evidence:** no E0-E2C experiment forces elevation. TMA-NM's independence
  stress test shows that naive corroborator counting is vulnerable to shared-
  domain compromise.
- **Simpler mechanism check:** default-deny without elevation already satisfies
  I1, though with lower utility.
- **Disposition:** deferred. Ordinary derivation never calls an elevation
  operator. Independent and correlated corroborators are therefore treated the
  same in the core design: they cannot raise a low-tier claim.

## Candidate 8 — Signed provenance receipts

- **Evidence:** no experiment modeled direct store-write or receipt forgery;
  case P records it as an inherited trusted-boundary assumption.
- **Simpler mechanism check:** store IAM, exclusive writes, and append-only
  auditing are the current named controls. Signatures add key custody without
  addressing any attacker exercised here.
- **Disposition:** rejected for this phase. Reconsider only if the threat model
  adds a concrete adversary able to modify receipt or record storage.

## Candidate 9 — Weighted semantic attribution

- **Evidence:** E1 case 5 confirms a weak contributor receives the same edge as
  a dominant contributor. No experiment provides reliable ground-truth weights.
- **Simpler mechanism check:** treating every declared input as contributing is
  conservative and deterministic; weighting would require a semantic judge or
  an instrumented transform that emits verifiable field-level provenance.
- **Disposition:** out of scope. Mixed affected content is quarantined whole;
  this expected collateral is measured rather than hidden.

## Minimum evidence-forced slice

Candidates 1-6 form the smallest coherent slice. Candidates 7-9 are not
smuggled into it. The slice can be falsified without production changes by the
scenario and gates in `DESIGN_FALSIFIER.md`.
