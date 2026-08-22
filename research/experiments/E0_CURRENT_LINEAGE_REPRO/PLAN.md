# E0 — Reproduce the multi-parent lineage failure

## Question

Does `custody/origin.py`'s `take_custody`, feeding a real
`custody/graph.py::CustodyGraph`, correctly give a synthesized memory
`derived_from` edges to **every** upstream trusted source that genuinely
contributed to it, or does it retain only one?

## Why this must use production code, not a toy model

`tests/test_graph.py::test_a_record_with_two_parents_survives_unless_both_are_pulled`
already proves `CustodyGraph._walk`/`revoke` handle a record whose
`derived_from` tuple has two ids correctly — that record was constructed
directly with `derived_from=("evil", "clean")`, bypassing `take_custody`
entirely. That test does **not** prove `take_custody` itself ever produces
such a tuple from real ADK-shaped events. E0 exists to test exactly that
gap: whether the *graph traversal* is sound (already shown to be, by the
existing test) versus whether the *origin-labelling layer that populates
the graph* is sound (untested until now). Using `take_custody` with the
same `FakeEvent`/`FakePart`/`FakeResponse` stand-ins the existing test
suite already uses (`tests/test_origin.py`) keeps this a real-code test,
not a parallel implementation, per the user's explicit instruction.

## Scenario

One invocation, three tool calls / turns:

1. `crm_lookup` (vouched, trusted) returns text A → admitted as `root_A`,
   `Trust.TRUSTED`, added to the graph.
2. `payroll_lookup` (vouched, trusted) returns text B → admitted as
   `root_B`, `Trust.TRUSTED`, added to the graph.
3. A model turn produces new text that is not equal to A or B (a genuine
   synthesis, e.g. `"Combining both: {A} and {B}."`) → this becomes
   `derived_AB`.

All three happen inside **one invocation**, which is the case
`origin.py`'s `lineage` dict (`origin.py:240`) is scoped to — this is
deliberately the most favorable case for Custody to get right (same
invocation, both parents structurally visible as tool-response events in
the same event stream take_custody already processes), not an
artificially hard cross-session case. If it fails here, it fails
everywhere the cross-session/retrieval-resolver mechanism would also rely
on the same `lineage` state.

## Required observation

- Inspect `derived_AB.record.derived_from` directly. Expected under
  correct behavior: `{root_A.record.id, root_B.record.id}` (as a set,
  order not asserted). Actual behavior to be recorded, not assumed.
- Add `root_A`, `root_B`, `derived_AB` to a real `CustodyGraph`.
- Call `graph.revoke(tool="crm_lookup", revocation_id="rev-A")`. Record
  whether `derived_AB.record.id` is in `revocation.removed`.
- Reset with a fresh graph (same three records). Call
  `graph.revoke(tool="payroll_lookup", revocation_id="rev-B")`. Record
  whether `derived_AB.record.id` is in `revocation.removed` this time.
- This directly answers the user's symmetric-revocation requirement.

## Also record, per the user's inspection checklist

- The actual persisted `derived_from` tuple value, not just whether
  revocation happened to work (a correct revocation result with an
  incomplete `derived_from` would be lucky, not sound, and must not be
  reported as a pass).

## Classification

- If `take_custody` produces `derived_from` with only one parent id even
  though two trusted sources structurally contributed: **A confirmed
  reproduction of an implementation bug** in the origin-labelling layer
  specifically (not the graph traversal layer, which is already shown
  sound by the existing test cited above). This determines the E0/E1
  framing is (A) a small implementation bug in an otherwise adequate
  representation — `CustodyRecord.derived_from` is already a `tuple`, so
  the *representation* is adequate; the *population* of it is not.
