# CSSR-EV1 Result — the shipped collector does not observe every input

**Run:** 2026-08-29, offline, no LLM, no network.

**Command:** `python3 research/experiments/CSSR_EV1_COLLECTOR_COVERAGE/run.py`

**Artifact:** [`result.json`](result.json), schema `cssr-ev1-coverage-v1`.

**Subject:** `custody/origin.py::take_custody`, reached through
`custody/service.py::CustodyMemoryService.add_session_to_memory`. No
`custody/*.py` file was changed.

## Coverage table

| Channel | Question | Verdict |
|---|---|---|
| `C1_same_invocation_data` | tool response and the model turn restating it, one invocation | `CAPTURED` |
| `C2_cross_invocation_data` | the same exchange, split by a user follow-up | **`NOT_CAPTURED`** |
| `C3_retrieval_byte_identical` | retrieval response matching an admitted record byte for byte | `CAPTURED` |
| `C4_retrieval_paraphrased` | retrieval response restating a record in other words | `FAIL_CLOSED` |
| `C5_payload_flattening` | two different tool payloads flattening to one string | `NOT_CAPTURED` |
| `C6_control_influence` | a record that changed whether an invocation happened | `ABSENT` |

## Finding 1, the headline: laundering across one turn boundary

**VERIFIED.** The same four pieces of content, in the same causal order, are
handled two different ways depending only on whether the user's follow-up
opened a new invocation.

Inside one invocation, the collector is correct. The restatement is
`origin=derived`, `trust=untrusted`, `derived_from=('inv-A:1:0',)`, and it is
withheld from memory. Two of three events are quarantined.

Split across two invocations of the same session, the restatement is
`origin=model`, `trust=trusted`, `derived_from=()`. Only one of four events is
withheld. The restatement is written downstream as trusted, and revoking the
tool whose content it carries removes nothing.

The attack is one ordinary conversational beat:

1. the user asks a question; the agent fetches a hostile page;
2. the agent's reply in that same invocation is correctly quarantined;
3. the user says "summarise what you found", which opens invocation B;
4. the agent's summary in invocation B is admitted as trusted with no lineage.

Step 2 does not help. Quarantining the invocation-A turn does not stop the
invocation-B turn, and per `DECISIONS.md` #4 the laundered restatement is the
only retrievable form in the first place, because `search_memory` matches on
`part.text` and never on a raw `function_response`.

**Reachability, PARTIALLY VERIFIED.** A missing edge only matters if the input
really influenced the output. ADK's `contents.py` builds the LLM request from
`invocation_context.session.events` when `agent.include_contents == 'default'`,
and `_should_include_event_in_context` filters on isolation scope, branch,
empty content, framework events, auth events, and rewind state.
`invocation_id` is not a filter. So the invocation-A tool response is in the
invocation-B model context. VERIFIED on mechanism; PARTIALLY VERIFIED on
version, because `google-adk` is not installed here, the reading is of `main`
rather than the pinned `>=2.6.3,<3`, and `tests/test_adk_conformance.py` could
not be run in this environment.

**This contradicts no recorded decision, and that is the problem.**
`DECISIONS.md` #4 chose invocation-scoped taint deliberately: "Without that
scope every session ends untrusted and the system is an outage." That is an
availability argument, and it is a reasonable one. What was never recorded is
the safety price. This experiment prices it: the price is that retroactive
revocation, the property the project exists to provide, does not hold across a
turn boundary. The decision may still be the right tradeoff. It should be made
with the number visible.

## Finding 2: content-addressed resolution collides under payload flattening

**VERIFIED, lower severity.** `_response_text` flattens a dict payload with
`" ".join(str(v) for v in payload.values())`, dropping keys. `{"x": "alpha",
"y": "beta"}` and `{"z": "alpha beta"}` produce the same `content_sha256`.
`CustodyGraph.resolve` is content-addressed, so it cannot distinguish them, and
a retrieval response that collides with an admitted record inherits that
record's trust and lineage.

Bounded honestly: this needs the colliding text to arrive through a retrieval
tool to become a trust decision, and the ID-based resolution on
`fix/receipt-collector-id-resolution` (`28531eb`) may already remove the
content-matching path. That branch was not evaluated here.

## Finding 3: control influence has no representation

**VERIFIED.** `CustodyRecord`'s fields are `origin`, `trust`, `author`,
`invocation_id`, `content_sha256`, `source_tool`, `source_revision`, `id`,
`derived_from`, `admitted_at`. `derived_from` is populated only from data
exposure in `_attribute`. Nothing records that a record caused an invocation to
happen, be scheduled differently, or be given a different budget.

This one matters most for CSSR. The selection channel is CSSR-S1's central new
mechanism: `SEL-AP` is a control-only parent of `J-A-SEL`, never passed as
producer context, and `C07`/`C08` exist to prove that edge is captured and that
dropping it is rejected. Production has no field for that edge. CSSR-S1's
treatment arm assumes a data model the shipped system does not have.

## What this does to CSSR-S1

**The harness result would not transfer.** CSSR-S1's `parent_set_errors` and
`missing_control_edges` are computed against a harness-owned recorder watching
the harness's own producer-context port, which by construction sees every
exposure. The production equivalent of that recorder is `take_custody` reading
ADK events, and it demonstrably does not see a real input. A CSSR-S1 PASS would
say that a mechanism written to a specification matches that specification.

**Two of the fourteen frozen cases have no production substrate.** `C07` and
`C08` both turn on a control edge that `CustodyRecord` cannot express.

**What survives.** Nothing here falsifies CSSR as a design. Prospective
isolation is still the only structural answer on the table, and the RSM series
already established that the retrospective, LLM-judged alternative is unsafe
under spoofed provenance. What this changes is the ordering: the premise CSSR
rests on is now measured, and it is false for at least one channel and absent
for another.

## Recommendation

**CAUTION on CSSR-S1 execution; the collector is the higher-information
target.**

Building `fixture.json` and `run.py` for CSSR-S1 would consume real effort to
produce a result whose value is capped by the two findings above. The same
effort spent on the collector answers a question whose answer is not already
determined by a fixture. Concretely, in descending order of information gained:

1. Decide `DECISIONS.md` #4 with the price visible. Session-scoped taint,
   scoped-and-decayed taint, or an explicit accepted-risk record. This is a
   design decision with a genuine availability cost, not a bug fix, so it needs
   its own authorization and its own falsifier.
2. If a control-edge concept is wanted in production, that is the CSSR-S1
   selection-channel mechanism arriving in the real system, and it can be
   falsified there instead of in a synthetic world.
3. Only then is a CSSR-S1 harness worth its cost, because only then can a PASS
   claim anything about production.

**Kept honest:** this is one counterexample in a small enumeration. Channels
not probed here, including server-side memory injection, provider-side session
state, and tool-internal retrieval, remain UNKNOWN, not safe. `run.py` exits
nonzero if any recorded verdict stops matching, so a later collector change
will fail this artifact rather than quietly age out of date.
