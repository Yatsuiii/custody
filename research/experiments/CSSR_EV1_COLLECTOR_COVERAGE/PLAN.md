# CSSR-EV1 — Production collector coverage

**Status:** RUN. See [`RESULT.md`](RESULT.md) and [`result.json`](result.json).

**Lane:** causality/debugging systems

**Subject:** the shipped collector, `custody/origin.py::take_custody`, reached
through its real enforcement point `custody/service.py::CustodyMemoryService`.

**Not a preregistration.** This packet is honest about its own order of events.
The channel enumeration and the first counterexample were found by reading and
probing the shipped code, before this file existed. Preregistration protects a
metric from being chosen after seeing results; it is not what makes a
counterexample credible. A counterexample is credible because anyone can run
`run.py` and watch the leak happen. Nothing here reports a rate, a threshold,
or a score, so there is no denominator to move. Where this packet does make a
general claim, it is labelled and bounded.

## Why this and not CSSR-S1's fixture

`CSSR_S1_SELECTION_CHANNEL_FALSIFIER.md` names its own dominant unresolved
risk: whether a production collector can completely observe the data and
control influence reaching a transform. Its own freeze record says "A
deterministic harness PASS cannot establish that external-validity premise."

The gap is sharper than that wording suggests. CSSR-S1 freezes `J-A`'s six
`JobSpec` fields as identical in the `A_ONLY` and `A_PLUS_P` worlds, then
measures `independent_job_drift` across those worlds. Drift can only be nonzero
if the harness contradicts its own fixture. The gate that looks like it tests
content-oblivious scheduling cannot fail for the reason the assumption would
fail in production. The same holds for most of the fourteen cases: given the
frozen parent table, the expected blocked set follows from graph closure alone.

So the higher-information action is to measure the shipped collector, where the
answer is not supplied by a fixture.

## Question

For each channel by which content or control can influence a model turn, does
that influence become a `derived_from` edge on the resulting record?

## Method

`run.py` builds sessions from the repository's own ADK event stand-ins,
imported from `tests/test_origin.py` rather than redefined here, so this audit
inherits whatever fidelity `tests/test_adk_conformance.py` establishes against
genuine `google.adk.events.Event` objects. It is offline and deterministic: no
network, no LLM, no dependency outside the standard library and this
repository.

Each channel gets one verdict:

| Verdict | Meaning |
|---|---|
| `CAPTURED` | the influence became a `derived_from` edge |
| `FAIL_CLOSED` | no edge, but the content was withheld from memory, so the cost is recall rather than safety |
| `NOT_CAPTURED` | no edge and no withholding |
| `ABSENT` | the record type has nowhere to record this kind of influence at all |

A `NOT_CAPTURED` verdict is only reported when the leak survives the real write
gate. Checking the pure function alone would prove nothing about the product,
because `split_session` withholds untrusted content before it reaches memory.

## Reachability premise

A missing edge is only a coverage failure if the input really did influence the
output. For the cross-invocation channel that reduces to one question about
ADK: does the model's context in a later invocation contain events from an
earlier invocation of the same session?

Verified against ADK's published source rather than assumed.
`src/google/adk/flows/llm_flows/contents.py` builds request contents from
`invocation_context.session.events` when `agent.include_contents == 'default'`,
and filters through `_should_include_event_in_context`, whose conditions are
isolation scope, branch membership, empty content, framework events, auth
events, and rewind state. `invocation_id` is not among them.

Limitation, recorded rather than hidden: `google-adk` is not installed in this
environment, so `tests/test_adk_conformance.py` could not be run here and the
reading is of `main`, not of the exact pinned version
(`requirements.txt` pins `google-adk>=2.6.3,<3`). Installing it was outside
this work's authorization. The claim is therefore PARTIALLY VERIFIED on
version, VERIFIED on mechanism.

## Acceptance gates

1. Every channel carries a verdict with a `file:line` citation or a probe.
2. Every `NOT_CAPTURED` verdict is demonstrated end to end through
   `CustodyMemoryService.add_session_to_memory`.
3. The reachability premise is checked against ADK source, with the filter
   conditions quoted.
4. `run.py` exits nonzero if observed behavior stops matching the recorded
   table, so this artifact is a regression detector and not a snapshot.
5. No `custody/*.py` file changes. Measurement only.

## Kill condition for the finding, not for the system

If the cross-invocation restatement turns out to be unreachable, because ADK
filters by invocation, because production takes custody per invocation, or
because some other control catches it, the headline finding is withdrawn and
`DECISIONS.md` #4 stands unchallenged. The audit then reports only the
lower-severity channels.

## What a fix is not authorized to do here

This packet measures. It does not repair. Widening taint to session scope is
the obvious move and is exactly what `DECISIONS.md` #4 rejected on availability
grounds, so it is a design decision with a real cost, not a bug fix to be
slipped in under a measurement authorization.
