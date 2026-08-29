
# Receipt Collector Paraphrase Falsifier

`research/design/TRUSTED_COMPUTING_BASE.md`'s TCB table names one
component as unproven for the case that actually matters in production:

> Context/receipt collector — Observes every stored record exposed to a
> producer and emits the exact id set. Status: **Unproven across current
> retrieval and server-side Memory Bank transformations.** Failure mode:
> **hidden input can receive an incomplete but trusted-looking output.**

This falsifier tests that claim directly against the real, shipped
mechanism (`custody/origin.py`'s `take_custody`, called with a
`RecordResolver`), not against a synthetic scenario invented for the
test. The exact transformation named as the risk — Memory Bank
server-side paraphrasing — is not hypothetical: it is already visible in
committed live evidence. `proof-out/g1.json`'s `adk_memory_bank` block
carries both `submitted_fact` ("Sales exports require a signed
approval.") and `retrieved_facts` (e.g. "Remember this: Sales exports
require a signed approval. Audit identifier: ..."), which are not
byte-identical. That divergence is Memory Bank's real behavior, captured
on a real Vertex AI project, not an assumption.

## The mechanism under test

`take_custody`'s resolver path (`custody/origin.py`, `_attribute`)
matches a retrieved `load_memory` response against a `RecordResolver` by
exact `content_sha256` digest of the retrieved text. A match inherits the
cited record's trust and lineage (`derived_from = (cited.id,)`); a
non-match falls through to `trust.of(runtime_name)` and
`derived_from = ()`.

## Hypothesis, stated before running

Two candidate outcomes were possible before this falsifier ran, and only
one is consistent with the TCB doc's stated failure mode:

- **H1 (matches the TCB doc's fear):** a paraphrased retrieval's digest
  mismatch still resolves to `Trust.TRUSTED` with a (possibly wrong or
  incomplete) `derived_from` set — an "incomplete but trusted-looking
  output." This would mean content could keep authority without a
  correctly-tracked parent, silently breaking future revocation
  completeness for exactly that content.
- **H2 (the safe direction):** a paraphrased retrieval's digest mismatch
  falls through to `Trust.UNTRUSTED, derived_from=()` — the same
  default-deny path an entirely unrelated, never-before-seen retrieval
  takes. This costs recall (legitimately-trusted content gets
  needlessly re-quarantined on re-admission) but does not cost
  correctness: nothing keeps authority it should not have.

An informal offline check run earlier in the same session (not scored,
not part of this falsifier's committed result) suggested H2, contradicting
the naive reading of the TCB doc's prose. This falsifier reruns that
check formally, against the exact live-evidence-derived string pair, with
a committed, inspectable result.

## Exact repro

1. Build a `CustodyGraph` and admit one record via `graph.add(...)` with
   `content=submitted_fact`, matching `proof-out/g1.json`'s real
   `submitted_fact` string exactly.
2. Call `take_custody` with a `retrieval(...)` event carrying
   `proof-out/g1.json`'s real second `retrieved_facts` entry (the one
   with the "Remember this: ... Audit identifier: ..." prefix Memory
   Bank actually added), and `resolver=graph`.
3. Record the resulting `Trust` value and `derived_from` tuple.
4. Run the same call with the byte-identical `submitted_fact` string as a
   positive control, to confirm the resolver mechanism itself works when
   the digest does match (ruling out an unrelated bug making both cases
   fail the same way).

No content in either fixture string is invented for this test; both come
directly from `proof-out/g1.json`, already committed to this repository.

## Bar, stated before running

If H1: this is a real, live security-relevant finding, and the honest
next step is scoping a fix (the TCB doc's own honest-relay-limitation
section already names the fix direction: only accept parent-ids from an
in-boundary connector or a separately verified identity/integrity
connector, never a raw self-declared match). If H2: this is a recall/
availability finding, already within Custody's own stated tradeoff
(`custody/service.py`'s docstring: "That costs recall, and the cost is
reported rather than hidden"), and the honest next step is naming the
consequence precisely — the cross-session citation/lineage mechanism
tested in `tests/test_graph.py` is real and correct, but likely does not
actually engage against real Memory Bank retrievals in production,
because production retrievals are not byte-identical the way test
fixtures are by construction.
