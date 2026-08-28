# RSM Crux9 Result — Cascading Repair Correctly Stops at Redundant Support

**12/12 (100%) correct, 4/4 domains fully correct.** Live
`gemini-3.5-flash`, four domains, one repair call per domain, three
judgments per call (M1, M2a, M2b). Full detail in `result.json`.

Every domain: M1 (sole support = revoked B) correctly RETRACT. M2a (pure
cascade, sole support = M1) correctly RETRACT. M2b (support = M1 **and**
independent C) correctly SURVIVE, with the model's stated reasoning in
every case correctly naming the independent fact as the reason the
conclusion holds — not just guessing the label.

## Why this is the closing question of the series, not just another round

Crux3 established that a single-hop judgment can tell "sole support" from
"redundant support" apart (0/8 vs 4/8 leak). Crux6 established that
cascading repair can propagate a retraction correctly two hops deep — but
every memory in that chain had exactly one support, so there was no branch
point where "keep cascading" and "stop, this one has independent backing"
could be confused for each other. This round puts both patterns in the
same prompt, same pass: M2a and M2b are structurally identical in shape
(both "depend on M1"), differing only in whether M1 is their *sole*
support or *one of two*. A model that defaults to "anything touching the
revoked chain retracts" — the same over-broad behavior whole-tool
revocation already produces without any LLM — would get M2a right and M2b
wrong. It got both right, in all four domains, with reasoning that
correctly cited the independent fact each time.

## What this does and does not establish

This is real evidence that the distinction crux3 found in isolation
survives being embedded in a cascade context with a plausible-looking
trap next to it. It is not evidence this scales past n=4 domains, past
one branch point per chain, past a single LLM call with no adversarial
pressure on the independent fact itself (crux8 already showed
self-declared independence can be spoofed and fool a naive prompt — this
round's `independent_fact_c` values are all stipulated honest, the same
simplifying assumption crux7b made before crux8 stress-tested it). A
harder version of this test would spoof C's independence the way crux8
spoofed provenance, and check whether the skeptical-prompt mitigation
from crux8 still catches it while correctly leaving M2b's *other*, honest
domains alone. That combination — redundant-support judgment under
adversarial-independence pressure — remains untested.

## Scope

Four domains, one call each, hand-templated (not LLM-fused) memory text,
honest provenance throughout. Consistent with every other round in this
series: a positive result on a controlled probe, not a validated
mechanism. The production answer to "does a cascade stop at redundant
support" is still the same as it has been throughout — Custody's
structural design (`custody/graph.py`'s deterministic closure) doesn't
need this judgment call at all for whole-tool revocation; this round is
evidence about the unbuilt, unshipped, semantic-layer question of
finer-grained repair, not about what's already shipped.
