# Prospective authority-resolver freeze

This freeze was created before discovering or searching for any prospective
benchmark source. The experiment starts from
`8cbf14d7b809722d5c4f0fb89202317fa8681df3` on
`research/decisiontrace-authority-prospective`. The protected-byte manifest is
`data/prospective/resolver_freeze_sha256.json`.

## Frozen system boundary

The manifest covers the deterministic authority module, lifecycle graph and
domain types, the answer-key-blind public-artifact adapter, reconsideration and
ingestion semantics, evidence and persistence types, retrieval and explanation
boundaries, Vertex model configuration, the intervention runner, its unit
tests, and the preregistered intervention rationale. These files collectively
determine authority eligibility, lifecycle replay, exact-scope matching,
policy-versus-implementation role handling, evidence binding, and the rule that
generation may explain but may not select authority.

Prospective-only dataset, validation, run, grading, and reporting modules may
be added. They must call the frozen `adapt_decisions` and `resolve_authority`
operations and may not copy, shadow, monkeypatch, or reimplement their rules.

## Exact resolver algorithm

For a checkpoint's public history, `adapt_decisions` performs an answer-key-
blind deterministic projection:

1. Only artifacts visible at the checkpoint are considered. Later snapshots
   replace earlier snapshots with the same decision ID.
2. `DRAFT` and `OPEN` map to `PROPOSED`; `FINAL`, `ACCEPTED`, and `ACTIVE` map
   to `ACCEPTED`; `MERGED` maps to `IMPLEMENTED`; `REVERT_MERGED`, `WITHDRAWN`,
   and `REJECTED` map to the legacy `REVERTED` status. `NOTE` is evidence-only.
3. `SUPERSEDES` and `REVERTS` edges are admitted only from an authoritative
   public artifact status. `IMPLEMENTS` edges remain explicit role evidence.
4. Source excerpts become evidence verbatim; the adapter never reads hidden
   adjudication.

`resolve_authority` then applies exactly these rules:

1. Select records with an exact match between the requested authority scope
   and `Decision.related_components`; do not use semantic similarity or
   recency to infer scope.
2. Exclude `PROPOSED` and `SUPERSEDED`. A legacy-`REVERTED` record is eligible
   only when it has an outgoing `REVERTS` edge, distinguishing a rollback event
   from a withdrawn or rejected decision.
3. If no eligible scoped record exists, return `NO_GOVERNING_DECISION` only
   when no eligible authority is visible anywhere; otherwise return
   `UNRESOLVED` rather than borrowing a decision from another scope.
4. When a record explicitly `IMPLEMENTS` an eligible policy, exclude that
   implementation record and its lifecycle lineage from the policy election.
   An implementation revert therefore does not automatically replace policy
   authority.
5. Replay `SUPERSEDES`, `REVERTS`, and `REAFFIRMS` edges within each remaining
   lifecycle component in dependency order. Timestamps and stable IDs only
   order independent events; explicit lifecycle dependencies dominate them.
6. A deactivating edge moves activity from its target to its source. A
   `REAFFIRMS` edge reactivates its target. Cycles and competing transitions
   against a non-active predecessor are ambiguous.
7. Return `GOVERNING` only if all eligible scoped records reduce to exactly one
   unambiguous active ID. Otherwise return `UNRESOLVED`.

## Ambiguity, fallback, and generation

Ambiguous lifecycle components, multiple active IDs in one scope, missing
exact scope with authority elsewhere, and implementation-only matches all
produce `UNRESOLVED`. No recency, semantic-nearest, cross-scope, or model-based
fallback exists. If nothing eligible exists, the result is
`NO_GOVERNING_DECISION`.

Gemini receives the deterministic state and ID as fixed facts. It can produce
one evidence-grounded explanatory sentence, but it cannot change the state or
governing ID. Model failure can affect explanation/evidence presentation, not
mechanically scored authority selection.

## Immutability rule

After this document, manifest, and guard exist, no protected byte, lifecycle
heuristic, priority, regex, adapter rule, or explanation instruction may
change in response to prospective sources or outputs. `pytest -q
test_prospective_resolver_freeze.py` is the local guard. Git history remains
the independent audit trail for the guard and manifest themselves.
