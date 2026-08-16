# Mining Gemini 3.7 failures on AutomationBench, 2026-08-16

Method change that produced this: stop inventing a thesis about what the model
cannot do, run it on a benchmark whose final state is checked programmatically,
and read the failures. Three earlier candidate products died because each
assumed a weakness that turned out not to exist.

## Getting it to run at all

Every off-the-shelf transport was closed, and this is worth recording because
anyone repeating this will hit the same wall:

- **Vertex OpenAI-compat**: Gemini 3.x requires a `thought_signature` on
  function-call parts across turns; the shim drops it, so every rollout 400s on
  turn two. Thinking cannot be disabled either (`THINKING_LEVEL_MINIMAL`
  unsupported).
- **AutomationBench's own Gemini client**: sends the Interactions API's
  `turn_list` shape; the Developer API now requires `step_list`. Their newest
  release (1.0.6, 2026-07-31) predates the change.
- **Developer API free tier**: `limit: 20` for `gemini-3.7-flash`, still
  exhausted after four idle minutes, so effectively per day, against a benchmark
  needing hundreds of calls.

So `adapter/vertex_client.py` implements the benchmark's own `Client` interface
on google-genai over Vertex. It touches the transport and nothing else: tasks,
tools, graders and runner are unmodified. The one change inside the benchmark is
a branch in `scripts/eval.py` that selects it (`--api vertex_native`).

**Validation, set before writing it:** the `simple` domain, where a correct
transport should score high. It scored **8/8, zero aborts**, after three real
bugs: a missing required `Usage.reasoning_tokens`, one function-response part per
turn where Gemini demands parity with the model's parallel calls, and the
dropped thought signature that broke everything else.

## The run

30 Operations tasks, `gemini-3.7-flash`, reasoning effort high, 0 aborts.

- **Pass rate 50%**, partial credit 80%.
- Zapier's published figure for Gemini 3.6 Flash across all six domains is
  45.00%, so this is directionally plausible rather than a broken harness.

## The cluster: writes to records it never located

Six of the fifteen failures never addressed the identifier the graders check.
**Zero of the fifteen passes did.** The mechanism does not appear in a single
task that passed.

What it looks like, from `pipefy_gmail_vendor_approval`. The agent must act on
vendor cards named in an email. It searched the Pipefy table for "Summit", did
not recover the id, and then issued writes against five invented identifiers in
sequence:

```
POST /cards/Summit/move          POST /cards/summit/fields:update
POST /cards/card_summit/fields:update
POST /cards/NorthWind%20LLC/move POST /cards/NorthWind/move
```

The graders expect `card_903`. It then emailed procurement:

> *"Confirmed. Summit review complete. Decision: Approved. The card in tbl_ops
> has been moved to phase_approved with status Approved."*

So the failure is not "it did not finish". It is: **an unresolved reference
became a guessed identifier, the write went nowhere, and a human was told the
work was done.** The same shape appears in `pipefy_slack_purchase_request`
(`card_711`), `pipefy_vendor_onboarding` (`card_56`),
`sheets_monday_maintenance_queue` (`itm_700`, and 91 tool calls spent),
`drive_notion_lease_archive` (`pg_legal`) and `trello_basecamp_compliance`.

## It is not fixed by one sentence

The filter's second criterion, tested rather than assumed. One sentence was
appended to the Operations system prompt and the same 30 tasks re-run:

> *"Before writing to any record, confirm you have its real identifier from a
> lookup response; never construct, guess, or infer an identifier from a name."*

| | baseline | with the sentence |
| --- | --- | --- |
| pass rate | 50% | 47% |
| partial credit | 80% | 75% |
| id-resolution failures fixed | | **1 of 6** |

The five that stayed broken are missing the *same* identifiers as before. The
instruction names the failure mode exactly and the behaviour barely moves; the
overall score moves slightly the wrong way, within run-to-run variance. The
benchmark's task file was restored from git afterwards and verified clean.

## Two clusters not yet analysed

- **The notification omits the datum that made it actionable** (5 failures): the
  action completes, but the Slack or Gmail message lacks the required value —
  `Due: 2026-02-18`, `275`, `02:00`, `['after','hours','drill']`.
- **The artifact in the second system is never created** (5 failures): Confluence
  pages, Notion pages, a Calendly booking.

## Where this stands against the filter

| criterion | status |
| --- | --- |
| Gemini 3.7 fails it repeatedly with reasonable context and tools | **met**, 6 of 15 failures, 0 of 15 passes |
| not fixed by one extra sentence | **met**, 1 of 6, net score unchanged |
| a product-level mechanism would fix it | plausible: read-after-write against the id claimed, and refusing to report success for a write that cannot be confirmed |
| outcome mechanically checkable | **met**, that is what the benchmark already does |
| no incumbent markets that outcome | **FAILED**, see below |
| demo in a real executable environment | **met**, this benchmark is one |
| looks nothing like Custody | **met** |

**The honest risk, flagged before any building.** The fix may belong in the tool
layer rather than in a product: a harness that verifies its own writes is a
library, and "it should be a library" is exactly what killed the Contribution
Gate. The competitor check and that question have to be answered before a line
of product code.

## Gate 5, checked 2026-08-16: the cluster is already named and already fixed

**arXiv 2606.30531, "Entity Binding Failures in Tool-Augmented Agents"** (Suresh
Babu and Indukuri, 29 June 2026) defines this exact failure: agents select the
correct tool but act on the wrong real-world entity. It evaluates the mechanisms
this project would have proposed, by name, including provenance tracking:
entity-resolution preconditions, confidence-gated binding, clarification under
ambiguity, and provenance tracking, over 60 diagnostic tasks, five model
backends and six tool-use methods. Baselines produced wrong-entity actions in
24 to 26 percent of runs; entity-aware methods eliminated them while reducing
task completion by deferring under ambiguity. That trade-off is the interesting
part of the problem and it is already characterised.

The outcome is also occupied commercially: Tilores markets stopping agents from
confusing two customers, Explorium markets entity matching as a pre-write check
for agents, and the execution layers where the gate belongs (Merge, Composio,
Arcade) are funded and shipping. The "it should be a library" risk flagged above
is not hypothetical; it is where the industry has already put it.

**So the cluster dies as a product.** What survives is smaller and real: an
independent reproduction of a seven-week-old finding on a harder benchmark than
the one it was published on, with deterministic graders, on a frontier model,
plus the measurement that a prompt-level instruction naming the failure fixes
1 of 6. Corroborating a recent paper is a contribution. It is not a submission.

## Gate 5 for the other two clusters, checked before analysing them

Both are occupied, and by work published while this project was being argued
about.

**Cluster 2, the report that does not match what was done.** arXiv 2607.25364,
"Explanation-Bound Tool Execution for AI Agents: Server-Verified Action Claims
Without Trusting Model Rationales" (July 2026), is the mechanism exactly:
convert the agent's rationale into typed action claims and check them
server-side against held facts including payload, provenance and freshness,
treating the explanation as an untrusted claim set rather than evidence. It
reports 136 conformance scenarios, 96 designated hard contradictions all
refused, and 232 metamorphic checks. Commercially, Patronus's Percival detects
20+ failure modes across four categories including output generation and
incorrect tool use.

**Cluster 3, the second system's artifact never created.** Durable execution
owns this: Temporal, Inngest, Restate, DBOS, Step Functions, with 2026
procurement language reported as "durable by default or do not ship". The
residual research gap, that durable execution does not gate external effect
settlement on per-resource progress for unmodified tools, is itself already
taken by Atomix (arXiv 2602.14849).

**And the remedy for cluster 1 was published two weeks ago.** arXiv 2608.02645,
"Verified Tool Calls Improve LLM Agent Reliability Under Non-Atomic Failures",
covers read-after-write verification for tool calls and names the exact
complication, that production CRMs do not offer strong read-after-write
guarantees.

So all three clusters found in this run are real, reproducible, and already
claimed. The failure-mining method did its job: it found genuine failures in one
afternoon where three earlier theses had evaporated on contact. It found them in
a field that is publishing faster than a fifteen-day build can move.

## What this run leaves behind

- `adapter/vertex_client.py`: a working AutomationBench transport for Gemini 3.x
  over Vertex, which did not exist before today and which anyone else hitting
  the thought-signature wall will need.
- A reproducible 50% Operations baseline for `gemini-3.7-flash`.
- Two unmined clusters, recorded honestly rather than pursued: the notification
  omitting the datum that made it actionable, and the second system's artifact
  never being created.
