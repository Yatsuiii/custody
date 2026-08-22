# DecisionTrace authority benchmark audit

Written on `research/decisiontrace-authority-benchmark` from
`ca53fce3ef8f6212e417238f976f2623d8a5fb9e`, before creating or running an
authority benchmark. This audits the frozen product mechanism as implemented,
not the stronger behavior described in the README.

## Scope and evidence read

The audit covers `README.md`, `BUILD_SCOPE.md`, `RESULTS.md`, `RESULTS_V2.md`,
`BENCHMARK_FAILURE_AUDIT.md`, `BENCHMARK_V2_SPEC.md`, `docs/DEMO_SCRIPT.md`,
the complete `.claude/SESSION_CONTRACT.md`, every module under `app/`, every
test under `app/tests/`, and the full DecisionTrace Git history from
`a62f20a` through `ca53fce`. The lifecycle resolver was introduced in
`a62f20a`; `1010d41` replaced store-order replay with deterministic
topological replay and added explicit cycle/fork ambiguity. No later commit
changed the authority semantics.

The closed rationale-recall result governs this session: the fair v2.2
comparison was structured ingestion 87% (72/83) versus labelled RAG 89%
(74/83), with code-only 10% (8/83). It does not establish an authority
advantage and will not be tuned or reused as one.

## Implemented model

`Decision` stores one status enum, optional timestamps and evidence, and a list
of outgoing typed relationships. A lifecycle relationship is encoded on the
later decision and points to the earlier decision it changes. The JSON store
rewrites the whole local file on every save. Firestore stores one document per
decision; relationships are embedded in that document rather than persisted as
independently evidenced transition records.

Only three edge types enter the lifecycle connected component:
`SUPERSEDES`, `REVERTS`, and `REAFFIRMS`. `IMPLEMENTS`, `RECONSIDERS`,
`DEPENDS_ON`, and `RELATED_TO` have no authority effect. The resolver
topologically orders each lifecycle component, using `introduced_at` and then
stable ID only to order independent ready nodes. It then replays lifecycle
edges:

- `SUPERSEDES` or `REVERTS` makes the edge source active when its target is the
  current active node.
- `REAFFIRMS` makes the edge target active.
- A second deactivation of a node that is no longer active returns ambiguous.
- A lifecycle cycle returns ambiguous.
- An isolated node becomes active regardless of its stored status.

`RetrievalCandidate.is_current` adds one rule outside the resolver: an active
ID is not presented as current when that record's status is `PROPOSED`.
`collaborate.answer()` additionally requires the candidate to carry at least
one evidence object and prevents Gemini from emitting a
`current_active_decision` claim for a non-current or ambiguous candidate.

## Answers to the authority questions

### 1. What exact rule currently determines “currently governing”?

Within the queried decision's connected component of `SUPERSEDES`, `REVERTS`,
and `REAFFIRMS` edges, `resolve_active()` replays the topologically ordered
edges. A valid `SUPERSEDES`/`REVERTS` edge promotes its source; a `REAFFIRMS`
edge promotes its target. The result is an active ID or an ambiguity. At the
retrieval/UI boundary, a record whose status is `PROPOSED` is vetoed from being
called current even if the graph selected it.

There is no repository-wide or subject-wide “one governing decision” query.
Resolution always starts from a specific retrieved decision and stays within
that decision's explicitly connected lifecycle component.

### 2. Which lifecycle states exist?

The enum contains `PROPOSED`, `ACCEPTED`, `IMPLEMENTED`, `REVERTED`,
`SUPERSEDED`, and `REAFFIRMED`.

These are labels, not a transition state machine. No code validates allowed
status transitions, reconciles status with edges, or updates a predecessor's
status when an edge is added. `superseded_at` is persisted but never read by
the resolver. `ACCEPTED`, `IMPLEMENTED`, `REVERTED`, `SUPERSEDED`, and
`REAFFIRMED` have identical resolver behavior for an isolated node.

### 3. What relationships are deterministic?

Deterministic authority relationships are `SUPERSEDES`, `REVERTS`, and
`REAFFIRMS`. They define both lineage membership and resolver events.

`RECONSIDERS` is deterministic only in the negative sense that it cannot
change authority. `IMPLEMENTS`, `DEPENDS_ON`, and `RELATED_TO` likewise do not
affect authority. The edge source/target direction is deterministic: the later
record owns an outgoing edge to the earlier record.

### 4. Where can Gemini influence interpretation?

Gemini can influence:

1. ingestion fields (`subject`, `context`, `chosen_approach`, alternatives,
   rationale, constraints), although accepted rationale quotes are checked as
   source substrings;
2. retrieval-time explanation and claim wording in `collaborate.answer()`;
3. which retrieved evidence it describes as relevant within the fixed top-k.

Gemini does not choose the graph's active ID. However, the existing ingestion
prompt does not extract acceptance, supersession, reaffirmation, withdrawal,
scope, or general lifecycle edges. Only revert references are deterministically
recognized by a regex and converted into `REVERTS` edges. KEP-like artifacts
are unconditionally labelled `ACCEPTED`, regardless of their real lifecycle
metadata. Therefore Gemini is not merely separated from authority
interpretation; most authority events are not ingested at all.

### 5. Can a `PROPOSED` decision become current accidentally?

Inside `resolve_active()`, yes. An isolated `PROPOSED` node resolves to itself,
and a `PROPOSED` node carrying a `SUPERSEDES` edge can displace an accepted
predecessor. Direct execution against the frozen code confirmed both status
independence and edge promotion.

The product compensates later: `RetrievalCandidate.is_current` and the UI veto
`PROPOSED`, and `collaborate.answer()` excludes it from authoritative claim
IDs. This prevents the common presentation bug but does not repair the graph
result. A caller using `resolve_active()` directly can still receive a proposal
as the active ID, and an older candidate's explanation can name that proposal
as the lineage's active decision.

### 6. How are superseded decisions treated?

A decision targeted by a valid later `SUPERSEDES` edge becomes inactive and
the edge source becomes active. A decision merely labelled `SUPERSEDED`, with
no edge, remains active in an isolated lineage. Conversely, a source can
supersede another decision regardless of whether its own status is accepted.

Two successors both superseding the same predecessor cause ambiguity when the
second edge is replayed. A missing edge target is silently ignored.

### 7. How are reverts treated?

`REVERTS` has exactly the same resolver operation as `SUPERSEDES`: its source
becomes active and its target becomes inactive. The product models the revert
record itself as the governing state. It does not automatically restore the
predecessor, distinguish code rollback from policy authority, or return
unresolved pending an explicit restoration.

This is intentional in the existing tests: `A accepted -> B supersedes A -> C
reverts B` resolves to `C`, and a real revert PR is asserted to be the active
record. Whether `C` expresses a durable governing decision is not checked.

### 8. What happens after `A -> B -> C` supersession chains?

With `B SUPERSEDES A` and `C SUPERSEDES B`, every starting node in the
component resolves to `C`. Topological dependencies dominate timestamps and
store iteration order. A cycle returns `active_id=None, ambiguous=True`.

Status is not consulted: the same result occurs if `B` is `PROPOSED` or `C` is
labelled `REVERTED`.

### 9. What happens when `B` supersedes `A` and `B` is later reverted?

If `C REVERTS B`, the current resolver returns `C`. `A` does not resume. The
result is not unresolved. Restoring `A` requires a separate later record with a
`REAFFIRMS A` edge, whose source is treated as an event but whose target `A`
becomes active.

### 10. How are unrelated or parallel decisions prevented from suppressing each other?

Only explicit lifecycle edges join components. Unconnected decisions resolve
independently, so a decision in subsystem X cannot suppress an unconnected
decision in subsystem Y.

The model has no first-class authority scope or decision key, however.
`related_components` is stored but never used by the graph or retrieval
resolver. Two conflicting decisions about the same subsystem with no edge are
both independently current; two truly parallel decisions joined by a mistaken
lifecycle edge suppress one another. Retrieval can return multiple independently
current candidates and leaves their semantic reconciliation to Gemini.

### 11. Does a newer document automatically outrank an older authoritative one?

No. Timestamps only break deterministic ordering among ready nodes inside an
already connected lifecycle graph. A newer mention, implementation artifact,
proposal, or unrelated decision does not outrank an older decision without a
recognized lifecycle edge.

The practical caveat is retrieval: a newer or more semantically similar card
may be retrieved while the governing card falls outside top-k. The resolver
cannot resolve a lineage that was never represented or retrieved correctly.

### 12. What evidence is required before changing authority?

At graph level, none. A typed edge between known IDs is sufficient; edges do
not carry citations, issuer identity, acceptance evidence, or confidence, and
the resolver does not require the edge source itself to have evidence.

At answer level, the candidate decision must have at least one `Evidence`
object to reach Gemini, but the evidence need not prove the lifecycle edge or
the authority transition. A title quote on an original PR is enough to satisfy
the candidate evidence check. The system validates evidence presence, not that
the cited artifact establishes acceptance, supersession, revert semantics, or
scope.

## Implemented authority invariant

> Within one explicitly edge-connected lifecycle component, authority is the ID selected by topologically replaying `SUPERSEDES`/`REVERTS` sources and `REAFFIRMS` targets, subject to ambiguity on cycles/forks and a later presentation-only veto for `PROPOSED`; stored status, recency, scope, and lifecycle evidence do not otherwise establish authority.

This is the implementation's invariant. It is weaker than the product thesis
that a decision becomes governing only through explicit lifecycle evidence.

## DDIA review

**Verdict: architecturally unshippable for an end-to-end authority claim; usable
as a resolver-conditioned research baseline.**

- **Chosen design:** one decision document owns status, evidence, and embedded
  outgoing edges; reads rebuild an in-memory graph and replay a component.
- **Key invariants actually enforced:** known lifecycle edges have a stable
  direction; replay order is store-independent; cycles and simple forks fail
  closed; proposals are blocked from authoritative answer claims.
- **Rejected interpretation:** status values are not an event log or validated
  state machine, so they cannot be treated as proof of lifecycle transitions.
- **Failure modes:** missing targets are ignored; edge and decision writes are
  not an atomic transition; Firestore upserts can overwrite history; no
  concurrency/conflict strategy exists; a retry is idempotent only when it
  repeats the same full decision payload; no audit trail explains who changed
  an edge; graph correctness does not survive incorrect extraction.
- **Smallest proof artifact:** checkpoint timelines that expose the same raw
  evidence to both arms, use only source-explicit lifecycle facts, report a
  resolver-conditioned DecisionTrace score separately from any end-to-end
  ingestion score, and include process-restart replay as a secondary test.
- **Unresolved risk:** because the frozen product cannot ingest general
  acceptance or supersession events, a benchmark that silently hands it gold
  lifecycle edges would measure an oracle-normalized resolver, not the deployed
  system. The preregistration must name that boundary and must not label the
  result end-to-end authority accuracy.

## Differentiation check

This audit concerns organizational authority: which explicit proposal,
acceptance, replacement, reconsideration, or rollback record governs at a
checkpoint. It does not trace downstream derivations or perform source-based
removal. The benchmark remains valid only while its state graph is a decision
lifecycle, not a source-to-derived-state lineage.
