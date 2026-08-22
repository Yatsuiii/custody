# E2B — Adapter Specification

## Location

`research/experiments/E2B_TMANM_SUMMARIZE/attack.py`. Outside
`custody/*.py` entirely. Imports `custody.origin`, `custody.graph`,
`custody.action` read-only, same discipline as E2A. Does not import
TMA-NM's own code — values are transcribed by hand from `code/
laundering.py`, per `PLAN.md`'s quoted source.

## Translation

Two sessions, each a distinct `invocation_id`, both passed through
`take_custody` calls that share one `CustodyGraph` instance across the
boundary (mirroring how a real deployment's graph persists across
sessions):

**Session 1 (write)** — a tool-response event, same shape as E2A:
```python
FakeEvent(
    author="assistant",
    invocation_id="inv-e2b-<case>-s1",
    content=FakeContent([FakePart(
        function_response=FakeResponse(name=<tool>, response=<text>),
    )]),
)
```
Processed via `take_custody([event], trust)`. Per `PLAN.md`'s realism
correction, only the resulting record is added to the shared
`CustodyGraph` **if its trust is TRUSTED** — reproducing
`custody/service.py:250`'s exact policy (`graph.extend(a.record for a in
split.trusted)`) rather than inventing a different one.

**Session 2 (retrieval)** — a `load_memory`-tagged tool-response event
carrying the *transformed* text, in a fresh `invocation_id`:
```python
FakeEvent(
    author="assistant",
    invocation_id="inv-e2b-<case>-s2",
    content=FakeContent([FakePart(
        function_response=FakeResponse(name="load_memory", response=<transformed_text>),
    )]),
)
```
Processed via `take_custody([event], trust, resolver=graph)` — the same
`graph` Session 1 (conditionally) populated. This is the exact structural
path `CustodyGraph.resolve` (`graph.py:187-197`) is wired to: `_attribute`
(`origin.py:312-318`) calls `resolver.resolve(content_sha256)` whenever
the responding tool's `runtime_name` is in `retrieval_tools`
(default `{"load_memory"}`), which is the only case this experiment
constructs.

`"load_memory"` is deliberately **not** added to any `ToolTrust.trusted`
set in this experiment, matching Custody's own documented default-deny
convention (departments vouch for domain tools, never for the retrieval
mechanism itself; nothing in `custody/*.py` grants `load_memory` implicit
trust anywhere). This is stated explicitly because it is the single most
consequential configuration choice in this adapter — it determines what
`verdict = trust.of(runtime_name)` falls back to whenever `resolve()`
misses.

## Consequential action modeled

Identical to E2A: `custody.action.Export`/`ExportGateway`, citing the
Session-2 record and carrying the transformed proposition's actionable
value as content.

## Diagnostics captured per state (not collapsed to one boolean, per the brief)

- `session1_trust`, `session1_added_to_graph` (whether the service-policy
  rule actually added it)
- `session2_resolve_hit` — `graph.resolve(digest(session2_text))` checked
  **directly**, independent of the full `take_custody` call, so a match or
  miss is confirmed rather than inferred from the final verdict alone
- `session2_origin`, `session2_trust`, `session2_derived_from`
- `session2_instruction_eligible`
- `action_allowed`, `action_denial`
- `digest(session1_text) != digest(session2_text)` — verified
  programmatically for every cross-invocation case, so "the text is
  genuinely different" is confirmed, not assumed

## What is deliberately not built

No LLM call of any kind (the transformation is a frozen, hand-constructed
string, per `PLAN.md`). No reimplementation of TMA-NM's `authorized()`
comparator functions. No new Custody mechanism, however small — this
adapter only arranges existing, unmodified Custody calls in a specific
order and inspects their real return values.
