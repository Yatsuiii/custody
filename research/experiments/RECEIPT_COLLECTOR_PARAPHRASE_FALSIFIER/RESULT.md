
# Receipt Collector Paraphrase Falsifier — Result

**H2 confirmed, H1 rejected. The paraphrase-mismatch case fails closed
(`Trust.UNTRUSTED, derived_from=()`), not open.** Offline, no network
call, run against the real, shipped `custody.origin.take_custody`
resolver path, using the real paraphrase divergence Vertex AI Memory
Bank produced against real infrastructure (`fixture.json`, frozen from
`proof-out/g1.json`, proof id `6e5564941ed54c368ec864dc38b196fd`, captured
2026-08-28). Full raw output in `result.json`.

## What was tested, and why the naive reading was wrong

`research/design/TRUSTED_COMPUTING_BASE.md`'s TCB table marks the
context/receipt collector "Unproven across current retrieval and
server-side Memory Bank transformations," with failure mode "hidden
input can receive an incomplete but trusted-looking output." Read on its
own, that sentence sounds like a security hole: content that should be
tracked back to a revocable parent instead ends up looking trustworthy
without one.

That reading does not survive contact with the actual code. `_attribute`
in `custody/origin.py` only ever reaches `Trust.TRUSTED` with a non-empty
`derived_from` through the resolver's exact `content_sha256` match. When
the digest does not match — which is exactly what happens when Memory
Bank paraphrases a retrieved fact, as it demonstrably does in the real
evidence this falsifier is built from — there is no silent middle state.
The code falls all the way through to `trust.of(runtime_name)`, the same
default-deny path a request for content nobody has ever seen takes.
`ToolTrust`'s own default is "everything absent is untrusted." There is
no code path in `_attribute` that produces `TRUSTED` with an *incomplete*
`derived_from`; it is either the resolver's exact match (complete,
correct lineage) or the tool-trust fallback (no lineage at all, and
untrusted by default since `load_memory` itself is not normally in an
operator's `trusted` set).

## Result

| | Trust | derived_from |
|---|---|---|
| Paraphrased retrieval (real Memory Bank output) | `UNTRUSTED` | `[]` |
| Exact-match control (byte-identical text) | `TRUSTED` | `['original-1']` |

The control confirms the resolver mechanism itself is not broken in some
unrelated way that would make both cases fail identically — it works
exactly as `tests/test_graph.py` already demonstrates when given
byte-identical input. The paraphrase case is the only variable changed,
and it alone determines the outcome.

## What this actually establishes

**Not a security hole.** Nothing in this mechanism lets content retain
authority it should not have. The TCB doc's specific fear — a "trusted-
looking" but incomplete output — was not found; the observed behavior is
the conservative one `custody/service.py`'s own docstring already
names as an accepted tradeoff ("That costs recall, and the cost is
reported rather than hidden").

**A real, different, quieter cost.** Because Memory Bank paraphrases
essentially every retrieval in the live evidence gathered so far
(`retrieved_facts` differs from `submitted_fact` in both entries this
project's own G1 gate has captured), the cross-session citation/lineage
mechanism `tests/test_graph.py` proves correct
(`test_a_retrieval_matching_the_graph_inherits_its_lineage`,
`test_a_restatement_of_the_retrieval_chains_to_it_not_the_original`) is
real and tested, but likely does not actually engage against real Memory
Bank retrievals in production. Those tests are true of the code; they are
not demonstrated to be true of what actually happens when a real deployed
agent calls `load_memory` against real, paraphrasing Memory Bank output.
That is a live gap between "correct in the test suite" and "exercised in
production," not a correctness bug.

## What was wrong in this session's first pass at this question

The initial hypothesis, stated before opening this falsifier, leaned on
the TCB doc's prose without first reading the code path it described.
That is exactly the mistake this project's own house discipline exists to
catch — and the correction happened before this result was written up,
not after. Recorded here rather than smoothed over.

## Scope and what remains open

- One production-derived paraphrase pair, one resolver, one fixture. Not
  a systematic survey of how often or how severely Memory Bank
  paraphrases across a larger sample of real retrievals.
- Does not test the `RecordResolver` matching against a *near*-collision
  case (a paraphrase that happens to preserve enough structure that some
  future, more permissive matching heuristic — fuzzy matching, embedding
  similarity — might wrongly treat as a match). This falsifier only tests
  today's exact-digest mechanism, which is what ships.
- Does not quantify the actual recall cost in the live system (how much
  legitimately-trusted content gets needlessly re-quarantined because of
  this). That would need a live measurement, not an offline repro.
- Does not evaluate whether the recall cost is worth paying down with a
  narrower fix (e.g., matching on a normalized/canonicalized text form,
  or Memory Bank's own `metadata.custody_record_id` field already written
  at admission time in `custody/adapters/memory_bank.py`'s
  `AgentEngineMemoryBank.write_record` — which would sidestep the digest-
  match problem entirely if `search_memory`'s retrieval path surfaced it,
  which it currently does not). That is a real design question this
  falsifier surfaces but does not answer.
