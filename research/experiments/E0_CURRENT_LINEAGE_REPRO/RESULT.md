# E0 — Result

## Reproduction

`tests/test_origin.py::MultiParentSynthesisE0::test_a_synthesis_of_two_trusted_sources_keeps_only_the_last_parent`
(committed on this branch before any fix). Real production code path:
`custody.origin.take_custody` with `FakeEvent`/`FakePart`/`FakeResponse`
stand-ins already used throughout `tests/test_origin.py`, feeding a real
`custody.graph.CustodyGraph`.

Scenario: one invocation, `crm_lookup` (vouched) returns text A,
`payroll_lookup` (vouched) returns text B, a model turn produces a genuine
synthesis of both, none of the three events untrusted.

## Observed behavior (confirmed, both structurally and functionally)

```
root_a id: inv-1:0:0   source_tool: crm_lookup
root_b id: inv-1:1:0   source_tool: payroll_lookup
synthesis derived_from: ('inv-1:1:0',)                 <- only root_b

revoke(tool="crm_lookup")     removed: ('inv-1:0:0',)            synthesis reached? False
revoke(tool="payroll_lookup") removed: ('inv-1:1:0', 'inv-1:2:0') synthesis reached? True
```

- `synthesis.record.derived_from == (root_b.record.id,)`. `root_a`'s id is
  silently absent, even though the synthesized text genuinely depends on
  both A and B, and both were structurally visible tool-response events in
  the same invocation `take_custody` already processes.
- Revoking `crm_lookup` (root_a's source) does **not** reach `synthesis` —
  0 descendants beyond the direct root. This is the harmful case: a
  compromised source's influence survives a real, executed revocation
  undetected.
- Revoking `payroll_lookup` (root_b's source) does reach `synthesis`,
  because it happens to be the parent that survived. This asymmetry — one
  revocation direction works, the other silently fails — was requested
  explicitly by the user's symmetric test design and is exactly what was
  found.

## Root cause, located precisely

`custody/origin.py:240`, the `lineage` dict:

```python
lineage: dict[str, tuple[str, str | None, str | None]] = {}
```

One `(record_id, source_tool, source_revision)` triple per **invocation**,
overwritten on every subsequent tool-response or model-turn event
(`origin.py:335`, `:358`, `:370`). By the time the synthesis model turn is
processed, `lineage.get(invocation)` returns only root_b's triple — root_a's
was already overwritten when root_b's tool response was processed. The
model-turn branch (`origin.py:367-370`) then builds
`derived_from = (predecessor[0],)`, a single-element tuple by construction,
regardless of how many distinct trusted sources actually appeared earlier
in the same invocation.

## Is the graph traversal itself also broken?

No. `tests/test_graph.py::test_a_record_with_two_parents_survives_unless_both_are_pulled`
already proves `CustodyGraph._walk`/`revoke` correctly walk a `derived_from`
tuple with two ids when one is supplied directly (bypassing
`take_custody`). This was re-confirmed here: `CustodyRecord.derived_from`
is already typed `tuple[str, ...]`, and `_walk`'s frontier expansion
(`graph.py:141-144`, `set(r.derived_from) & frontier`) has no
single-parent assumption anywhere in it.

**The bug is confined entirely to `take_custody`'s `lineage` bookkeeping in
`custody/origin.py`, not to `custody/graph.py`.**

## Classification

**(A) — a small, precisely located implementation bug in an otherwise
adequate representation.** `CustodyRecord.derived_from`'s type and
`CustodyGraph`'s traversal already support multi-parent lineage; nothing
that produces a `derived_from` tuple from real events ever populates more
than one element. This is not evidence the DAG representation is
fundamentally inadequate (case B in the user's framing) — a hypergraph or
other structural rewrite is not indicated by this result.

## Verdict on E0

**Reproduced, confirmed, code-located, asymmetric exactly as predicted.**
Proceed to E1.
