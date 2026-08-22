# E1 — Minimal multi-parent lineage fix

## Scope discipline

Only the change needed for one derived record to retain multiple upstream
parents. Explicitly not doing: trust epochs, authority lattices,
signatures, semantic similarity, LLM classification, TMA-NM-style
authority separation, new infrastructure, new Cloud services. Confined to
`custody/origin.py`'s `_attribute`/`take_custody` internals — no change to
`custody/graph.py`, which E0 already showed handles multi-parent
`derived_from` tuples correctly once they exist.

## Is a DAG still the right structure, or is a hypergraph required?

**A DAG remains correct. No hypergraph is introduced.** `CustodyRecord.
derived_from` is already `tuple[str, ...]` — an ordinary DAG node already
supports an arbitrary number of parent edges; nothing about "one node, many
parents" requires hyperedges (a hyperedge would be needed only if a single
*edge* needed to connect more than two nodes atomically, e.g. to represent
"this specific edge is jointly authored by A and B as one indivisible
unit" — that is not the semantics here; A's contribution and B's
contribution are two ordinary, independent edges into the same child).
E0 already found `CustodyGraph._walk` has no single-parent assumption. The
only defect is that `take_custody` never *constructs* more than one edge.

## The fix

`custody/origin.py`'s `lineage` dict changes from holding one
`(record_id, source_tool, source_revision)` triple per invocation to
holding a **tuple of triples** — every distinct trusted upstream arrival
seen so far in the invocation, not just the most recent:

```python
lineage: dict[str, tuple[tuple[str, str | None, str | None], ...]] = {}
```

- A trusted (or citation-resolved) tool response **appends** its own
  triple to the invocation's tuple, instead of overwriting it.
- A MODEL or DERIVED turn's `derived_from` becomes the tuple of **every**
  predecessor id currently accumulated for the invocation, not just the
  last one.
- After a MODEL/DERIVED turn consumes the accumulated predecessors, the
  invocation's lineage state **collapses to that turn's own single id**
  going forward — a later turn depends on the synthesis, not redundantly
  on the synthesis's own now-transitively-reachable ancestors. This
  preserves the existing "restatement of a restatement is two hops, not a
  shortcut" behavior (`test_a_restatement_of_the_retrieval_chains_to_it_
  not_the_original` in `tests/test_graph.py`) exactly as before — that
  test is unchanged by this fix and must still pass.
- `source_tool`/`source_revision` on the resulting `CustodyRecord` (fields
  that are inherently singular, unlike `derived_from`) keep taking the
  most-recently-seen predecessor's values, same as before — this is
  informational metadata only; correctness of revocation reachability
  depends on `derived_from`, which now lists every parent, not on these
  singular fields.

## Conservative direction chosen deliberately

Accumulating *every* trusted source seen so far in the invocation (rather
than attempting to infer which specific sources a given model turn
"actually" used) is an over-approximation, and over-approximation is the
safe direction here: it can at worst attribute an edge to a source that
did not truly influence a given synthesis (a false-positive edge, costing
a small amount of extra collateral damage on a future revocation), but it
cannot silently drop a true dependency (a false-negative edge, which is
the security-critical failure E0 reproduced). This matches the same
conservative philosophy the existing taint mechanism already uses for
untrusted content (`origin.py:330-334`, any untrusted arrival taints
everything after it in the invocation, whether or not a given later turn
actually read it).

## What this does not fix

- Cross-invocation/cross-session multi-parent synthesis (still relies on
  exact-content-hash `resolve()`, out of scope for E1 per the user's
  explicit framing: "we are NOT yet solving semantic provenance
  inference").
- Paraphrase/laundering resistance (a later, separate experiment).
- Weighted/partial attribution (case S in `CURRENT_CUSTODY_REDTEAM.md`) —
  still all-or-nothing per parent, just now correctly listing all parents.
