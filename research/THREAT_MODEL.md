# Threat Model — Custody 2.0 candidate (pre-literature-review draft)

This draft is written from the red-team findings in
`CURRENT_CUSTODY_REDTEAM.md` alone. It is deliberately provisional: Phase 0
(literature) can still kill or shrink it further. Do not read this as a
commitment to build anything.

## Claim under evaluation

> "Custody provides retroactive containment of persistent agent-memory
> influence after post-hoc source compromise, using origin-bound,
> non-malleable authority and selective downstream repair."

**Verdict on the wording: reject, too broad on two axes.** It does not say
*bounded-interval*, and current Custody already does whole-tool-lifetime
retroactive containment — so as written this sentence describes work already
shipped, not a research contribution. It also says "non-malleable
authority," which the red-team shows is **false today**: F (trusted-tool
echo) and H/R (silently dropped multi-parent edges) are both authority
values that transformations *can* corrupt or lose. Claiming non-malleability
while F and H are open would be an unfalsifiable/false claim.

### Proposed narrower wording

> "Custody investigates whether authority over agent memory can be scoped to
> a bounded trust interval — not just a binary trusted/untrusted tool — so
> that when a source is discovered compromised only during
> `[t_a, t_b]` inside a longer legitimate trust lifetime, the fleet can
> revoke influence from that interval specifically, including influence that
> reached other agents through relay or restatement, while incurring
> materially less collateral damage than whole-tool revocation or coarse
> purge — and states precisely which laundering transformations (exact
> match, paraphrase, multi-source synthesis) this scoping does and does not
> survive."

This is falsifiable: it fails if bounded-interval revocation performs no
better than whole-tool revocation on collateral damage (H1/H2 in
`HYPOTHESES.md`), or if it cannot be made to survive at least one laundering
class better than the current exact-hash mechanism (H3).

## In scope

- A tool/source that is legitimately vouched (`TrustCatalog.request`,
  `catalog.py:126-135`) for a bounded interval, then discovered compromised
  either at a point (t2) or over a known/uncertain sub-interval
  `[t_a, t_b]`.
- Descendants reached via the two derivation mechanisms Custody already has
  (same-invocation taint, exact-content-hash retrieval match) *and* via the
  laundering classes the red-team found unhandled: paraphrase, cross-session
  restatement without exact match, trusted-tool echo of upstream-compromised
  data, multi-source synthesis (H/R).
- Selective repair: minimizing benign memory destroyed while maximizing
  removal of interval-specific influence.
- The revocation-to-repair pipeline (demote → identify → neutralize),
  reusing `CustodyGraph`'s existing traversal primitives where possible
  rather than replacing them.

## Out of scope (explicit, matching what the red-team found is genuinely
absent, not a convenient exclusion)

- Content-based malicious detection for **user-authored** turns (case A) —
  Custody's origin model is about arrival channel, not content safety; this
  stays Model Armor's job, unchanged.
- Authenticating that an ADK `Event`'s `author`/`invocation_id` actually
  came from the claimed principal (case P) — assumed, not verified, by the
  whole ADK integration layer, not just Custody. Any Custody 2.0 experiment
  reusing this integration inherits this assumption and must say so.
- Revoking a compromised **human principal's** own writes (case Q) — no
  existing primitive to build on (`descendants` keys on `source_tool` only),
  and adding one is a different, larger project (principal-level trust,
  not source-level trust). Named as a non-goal, not solved.
- Rolling back **actions already taken** on now-revoked content (case T) —
  this is an audit/incident-response system, not a memory system; explicitly
  a different research project.
- Cryptographic attestation of a tool's *running code* (Binary Authorization
  territory, already named out of scope in the existing README for the same
  reason).

## Assumptions

- The ADK event stream and its `author`/`invocation_id` fields are honest
  (ties to case P above — a documented assumption now, not silently implied).
- The durable store (`custody/store.py`, `custody/firestore_store.py`) is
  written to exclusively through `CustodyMemoryService`/`CustodyGraph.add`;
  no other write path to the store exists in the current deployment.
- A "compromise interval" `[t_a, t_b]` becomes known to security at t2,
  either exactly or as an uncertain window; Custody 2.0 is not responsible
  for *detecting* compromise, only for acting once notified (matching how
  `/demote` already works: a human or external signal triggers it).

## Trusted computing base

- The ADK `Event` object's field integrity (inherited assumption, see above).
- The durable store's write-path exclusivity (Firestore/SQLite IAM, not a
  Custody-internal control).
- The digest/hash functions used for `content_sha256` and tool-definition
  `revision` (SHA-256, standard cryptographic assumption).
- Whatever mechanism eventually timestamps/authenticates a compromise
  interval's boundaries `t_a`, `t_b` — **this does not exist yet and is
  itself a research question**, not a solved input. Phase 7 must not assume
  a clean, trusted `[t_a, t_b]` is handed down from an oracle; at minimum,
  the benchmark plan must include an *uncertain-window* variant.

## Attacker capabilities

- Can control the content returned by an untrusted (never-vouched) tool at
  any time — already handled today (default-deny).
- Can control the content returned by a **currently-vouched** tool during a
  sub-interval of its trust lifetime, without changing its declared schema
  or serving image (the K/L gap) — this is the primary capability the
  candidate thesis is about.
- Can cause a trusted agent to relay, paraphrase, or synthesize
  attacker-influenced content across sessions/departments (D/E/F/G/H/R gaps).
- Cannot forge ADK event authorship or write directly to the durable store
  (excluded by the trusted-computing-base assumption above — if this
  assumption is wrong, P and Q become in-scope attacks and the whole model
  needs revisiting; flagged, not solved).

## Security invariants (candidate, to be stress-tested against H1-H4)

1. A record's `derived_from` set is a *superset* of every distinct upstream
   source that structurally contributed to it (fixes the H/R single-slot
   bug as a precondition — without this, bounded-interval revocation
   inherits the same silent-miss failure mode as today's whole-tool
   revocation, just narrower).
2. Revoking a bounded interval `[t_a, t_b]` for a source removes every
   record whose derivation chain includes a write from that source that
   occurred inside `[t_a, t_b]`, and preserves every record whose
   derivation chain only includes writes from that source outside the
   interval.
3. No revocation, bounded or otherwise, ever *increases* a record's trust
   or *widens* what it cites beyond what it held at admission time
   (derivation must not manufacture authority — this one already holds in
   current Custody and should not regress).

## What happens under the hard cases the user named

- **Origin labelling itself is wrong** (P): invariant 1 and 2 are only as
  good as the labels feeding them; wrong labels propagate wrong revocation
  scope silently. No mitigation proposed here beyond naming it as inherited
  risk from the TCB assumption.
- **A trusted principal's credentials are stolen**: out of scope (Q), stated
  above — flag, do not pretend to solve.
- **The model invents information with no poisoned ancestor** (hallucination,
  not poisoning): correctly outside this system's claim; Custody only ever
  reasons about content that arrived via a structural, attributable event.
  A hallucinated claim with no tool/user origin at all should be `MODEL`
  origin, `TRUSTED` (current code: `origin.py:371-378` — a model turn with no
  taint and no predecessor gets `Origin.MODEL`, `Trust.TRUSTED`
  unconditionally). Worth flagging as its own boundary case, not folded into
  the poisoning claim.
- **Provenance metadata is lost**: falls back to `Refusal.NO_INVOCATION`/
  `NO_AUTHOR` today (PASS, O) — any bounded-interval extension must preserve
  this fail-closed default rather than treating missing metadata as
  "outside the interval, therefore safe."
- **Two independent sources corroborate the same claim**: this is exactly
  H — currently silently mishandled (one edge dropped). Any Custody 2.0
  design must fix this before bounded-interval revocation is worth building
  on top of it, or the new mechanism inherits the old blind spot.
- **A compromised source contributes to a mostly benign derived memory**:
  this is S — currently all-or-nothing. A bounded-interval design needs an
  explicit answer here (delete the mostly-benign memory too, downgrade it to
  quarantine-for-review, or accept the collateral damage) — this is exactly
  what the PCRR/collateral-damage metric in `METRICS.md` must be able to
  score, not something the architecture can silently duck.
