# E2 — Custody Adapter Feasibility Map

For each TMA-NM attack classified IMPLEMENTED in `ATTACK_MATRIX.md`. No
adapter code is written here — feasibility assessment only, per the
session's scope.

## General structural mismatch, stated once

TMA-NM's harness represents a scenario as a flat list of dict items
(`{content, true_origin, looks_benign, edge_untrusted, indep_trusted,
asserts_value}` in `laundering.py`, or `MemoryItem` objects with
`origin`/`act_class`/`corroborations` in `agent_bench.py`/`monitor.py`).
Custody's `take_custody` (`custody/origin.py`) instead consumes a
*sequence of ADK-shaped events* grouped by `invocation_id`, and derives
origin/trust/`derived_from` structurally from that event sequence, not
from a pre-labelled item list. **Any adapter must translate TMA-NM's flat
scenario items into a synthetic event sequence** (using the same
`FakeEvent`/`FakePart`/`FakeResponse` stand-ins Custody's own test suite
already uses) before Custody's real code can evaluate anything. This
translation is mechanical (a scenario's `tool_echo` item becomes a
`FakePart(function_response=FakeResponse(name=<tool>, response=<content>))`
event; a `summarize` item becomes a plain-text model-turn event following
a tool-response event in the same invocation) and is the same category of
work for every attack below, so it is stated once here rather than
repeated eight times.

## A/B — Summarization/paraphrase laundering

1. **Attack input**: a real LLM-generated paraphrase of a poisoned tool
   response, presented as the agent's own note (`true_origin =
   agent_from_untrusted`).
2. **Memory operation**: one write, treated by naive defenses as agent-
   authored (benign-looking, no live untrusted edge).
3. **Provenance/authority metadata TMA-NM tracks**: `origin` (fixed at
   write, non-malleable by construction — TMA-NM's `Origin.AGENT` is
   itself downstream of an `UNTRUSTED_EXTERNAL` write only if the harness
   *labels* it that way; TMA-NM's own defense reads ground-truth origin,
   which this scenario's `true_origin` field encodes for the paper's
   comparator baselines, not for `tma_nm` itself, which uses its own
   internal origin tracking).
4. **Action-success criterion**: the agent's proposed action targets the
   attacker's `value` and the defense under test authorizes it.
5. **TMA-NM's assumption**: origin is bound at write time and cannot be
   changed by a later transformation — the paraphrase changes *content*,
   never the bound authority.
6. **Equivalent Custody component**: exactly the same claim Custody's
   `DERIVED` taint mechanism makes for same-invocation summarization
   (`origin.py:8-12`, `:330-334`) — this is Custody's best-covered case
   (red-team verdict PASS for same-invocation laundering). Where TMA-NM's
   scenario differs is that its `summarize` channel is realistically
   cross-session (the poison was written earlier, in a different session,
   matching Custody's D/E red-team gap — cross-invocation paraphrase,
   which Custody's exact-content-hash `resolve()` does *not* survive).
7. **Can current Custody represent the scenario?** Yes, structurally — a
   two-event sequence (tool response, then a differently-worded model
   turn in a *separate* invocation) is exactly representable as
   `FakeEvent`s. What Custody would very likely get *wrong* is exactly
   what the red-team already predicted: since the paraphrase changes the
   text, `CustodyGraph.resolve`'s exact-hash match would fail, so the
   restatement would not inherit `derived_from` at all and would fall
   back to `trust.of("load_memory")` or similar — almost certainly
   UNTRUSTED by default (fail-closed, matching TMA-NM's `tma_nm` outcome
   by accident of conservative defaults, not by a real laundering-aware
   mechanism). This is worth stating precisely: Custody might *score*
   well on this specific adapted scenario without actually possessing
   TMA-NM's mechanism, because Custody's default-deny posture and TMA-NM's
   non-malleable-origin posture can produce the same output (block) via
   different reasoning. A single pass/fail number would not distinguish
   them — the adapter would need to check *why* Custody blocked it, not
   just whether it did.
8. **Adaptation requires**: only test-harness plumbing (event translation)
   plus a small script to call `take_custody`/`ExportGateway` in place of
   `authorized()`. No semantic change to Custody needed to *run* this
   scenario. A semantic change (laundering-aware matching) would only be
   needed if the goal is to make Custody pass *for the right reason*
   rather than by accident of its existing conservative default.

## C — Trusted-tool echo

1. **Input**: a trusted-tool-shaped response carrying the attacker's value.
2. **Operation**: one tool-response write, labelled by the harness as
   coming from a nominally trusted source.
3. **TMA-NM metadata**: `true_origin = tool_echo_untrusted` — the harness's
   own ground truth, deliberately different from what a naive defense
   would observe (`looks_benign=True`).
4. **Success criterion**: same as A/B.
5. **TMA-NM's assumption**: a defense reading only the tool's *identity*
   as trusted will authorize this; TMA-NM instead requires
   Sybil-resistant corroboration before elevating an item whose true
   origin traces to compromise, regardless of which tool relayed it.
6. **Equivalent Custody component**: this is **exactly** red-team case F
   (`CURRENT_CUSTODY_REDTEAM.md`), Custody's cleanest confirmed FAIL.
   `ToolTrust.of()`/`trust.of(runtime_name)` (`origin.py:194-197`, `:325`)
   is a pure tool-*identity* lookup with no notion of the payload's own
   upstream provenance.
7. **Can current Custody represent the scenario?** Yes, trivially — a
   single `FakeEvent` with a `function_response` from a tool present in
   the department's `ToolTrust.trusted` set. Custody would almost
   certainly get this **wrong**, matching the red-team's prediction: the
   response is stamped `Origin.TOOL`, `Trust.TRUSTED` purely because the
   tool name is vouched, with no mechanism to question the payload. This
   is the single highest-value scenario to adapt first: it is the one
   case where this experiment's own code reading gives high confidence
   Custody will concretely fail an adapted version of TMA-NM's own test,
   not just fail the red-team's synthetic reasoning about it.
8. **Adaptation requires**: only test-harness plumbing — no semantic
   change needed to *observe* the failure. Fixing it (making Custody
   resistant to this) would require a semantic change roughly analogous
   to TMA-NM's own Sybil-resistant elevation gate — out of scope for this
   experiment, a candidate for a later E6-class design task if the thesis
   proceeds.

## E — Manufactured corroboration (including the correlated-domain variant)

1. **Input**: two items, either both untrusted-duplicate assertions
   (`corroborate` channel) or two nominally-trusted-but-domain-correlated
   assertions (`stress_independence.py` S3).
2. **Operation**: two writes, both asserting the same value.
3. **TMA-NM metadata**: `indep_trusted` flag per item (base channel), or
   `domain` tag per item (independence-stress variant).
4. **Success criterion**: same as above.
5. **TMA-NM's assumption**: independence requires distinct administrative
   domains, not just distinct item ids — the harder S3 variant is
   specifically designed to defeat a naive "count >= 2" check.
6. **Equivalent Custody component**: Custody has **no corroboration
   concept of any kind** — `TrustCatalog`/`ToolTrust` never counts or
   correlates multiple sources supporting one claim; trust is decided
   per-write, per-tool, independent of whether other sources agree. Case H
   in the red-team (fake independent corroboration) is the closest match,
   but for a different reason than TMA-NM tests: Custody's H gap is about
   a *derivation-graph* edge silently dropping (now fixed by E1), not
   about a corroboration-*counting* mechanism, because Custody never had
   one to defeat in the first place.
7. **Can current Custody represent the scenario?** Partially. The base
   `corroborate` channel (two duplicate untrusted items) is representable
   and Custody would correctly refuse both (default-deny, no elevation
   mechanism exists to raise them). The harder S3 domain-correlated
   variant is **not meaningfully representable as a distinguishing test**
   for Custody, because Custody has nothing that could pass or fail on
   domain-correlation in the first place — it either trusts a tool or it
   doesn't, with no notion of "two trusted tools sharing an upstream
   domain." Adapting S3 against Custody would not test anything Custody
   claims to do; it would be testing for the *absence* of a mechanism
   Custody never built, which is already known from the literature audit
   (Custody has no corroboration concept at all) and would not be a fair
   or informative comparison.
8. **Adaptation requires**: the base `corroborate` channel — only test-
   harness plumbing. The S3 domain-correlated variant — **impossible/unfair
   translation**, per the user's explicit instruction not to force-fit an
   attack that tests a materially different threat model; Custody simply
   has no corroboration-independence claim to falsify here.

## H — Indirect/direct memory poisoning

Already Custody's best-covered, most-proven case (red-team verdict PASS,
live-demonstrated by `make demo`). Feasibility: trivial to adapt (only
harness plumbing), but low marginal value — this is not where Custody's
weakness lies, and TMA-NM's own results show every compared defense class
(except `capability_ifc`) already handles this case, so an adapted run
would likely just confirm what is already known on both sides.

## I — Delayed/sleeper activation

1. **Input**: an item written in session N, referenced in session N+2 or
   later.
2. **Operation**: write, then a later, temporally-separated act attempt.
3. **TMA-NM metadata**: `t_write` session index; the monitor enforces the
   invariant regardless of elapsed session count.
4. **Success criterion**: same pattern as above, evaluated after the delay.
5. **TMA-NM's assumption**: write-time binding makes elapsed time
   irrelevant to the authority decision — "dormancy and trigger-disguise
   irrelevant" (README, `memory.py` docstring).
6. **Equivalent Custody component**: `instruction_eligible()`
   (`origin.py:122-128`) is likewise a permanent, write-time-decided flag
   with no time-based re-evaluation — Custody's red-team case C reached
   the same PARTIAL verdict for the same structural reason (a written-
   untrusted item stays untrusted forever, correctly, absent a manual
   `demote`/`revoke`).
7. **Can current Custody represent the scenario?** Yes, directly — a
   multi-invocation sequence with a large `invocation_id`/session gap
   between the poisoned write and the later action attempt. Custody would
   very likely pass this cleanly, for the same structural reason TMA-NM
   does: both bind authority at write time and never let elapsed time
   alone change it.
8. **Adaptation requires**: only test-harness plumbing. Low marginal
   value for the same reason as H — this is not where either system's
   interesting disagreement lies.

## Cases explicitly NOT force-fit (per the user's instruction)

D (cross-agent relay) and J (mixed-source derived memory) are not mapped
above because TMA-NM's harness does not implement them at all
(`ATTACK_MATRIX.md`) — there is nothing to adapt *from*. Building a D or J
scenario would mean writing a wholly new scenario in TMA-NM's own harness
style, which is design work indistinguishable from E4 (a new benchmark
slice), not reuse of an existing one, and is explicitly out of this
experiment's scope.

## Net feasibility read

The **cheapest, highest-value single adapted experiment**, if this
proceeds past E2, is case C (trusted-tool echo): it is trivial to
translate, and this experiment's own code-level analysis gives high
confidence it would produce a genuine, freshly-adapted-from-published-work
FAIL against current Custody — stronger evidence than the red-team's
synthetic reasoning about the same case, because it would be measured
against an attack construction someone else designed and already validated
against eight real models, not one this project invented to make itself
look bad or good.
