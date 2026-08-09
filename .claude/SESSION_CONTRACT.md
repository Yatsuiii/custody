# Custody, session contract

Working name: Custody. Chain of custody for agent memory. Rename is cheap until
the first public artifact, expensive after the demo video.

Objective: Ship one submittable artifact to the All Things Agentic Hackathon
(Google, Devpost) under **Fortified Enterprise Fleet**. Custody is a provenance
layer over agent long-term memory across a fleet of departmental agents. Every
durable memory records where its content came from and what it was derived from.
Untrusted-origin content never reaches the memory service. And because
derivation is recorded, a tool discovered compromised later can have every memory
descended from it identified and pulled, across every department, agent and
session since.

The product in one sentence, and it must stay one sentence:

> Poisoned content never enters your agents' memory, and if a tool is later
> found compromised, you can pull everything descended from it.

One deployed Cloud Run control plane, a scalable population of governed ADK
agents, one public repo, one four-minute video.

Branch: feat/memory-provenance
Parent: b0c7019 (repository initialized 2026-08-09)

Allowed files: everything under /run/media/Yatsuiii/Windows-SSD/custody.

## The gap, quoted from source

Verified 2026-08-09 in `google/adk-python`, not inferred:

- `memory/memory_entry.py`. A `MemoryEntry` carries `content`, `custom_metadata`,
  `id`, `author`, `timestamp`.
- `events/event.py`. `Event.author` is *"'user' or the name of the agent,
  indicating who appended the event to the session."*
- `memory/vertex_ai_memory_bank_service.py`. Scope is `{'app_name', 'user_id'}`.
  `metadata` is a free-form mapping nothing validates. `search_memory(app_name,
  user_id, query)` takes **no filter parameter**.

So Memory Bank answers **who appended content and for whom**. It does not answer
**where the content came from** or **what it was derived from**. Custody supplies
those two, on top, through the existing port and without modifying anything.

**Framing rule, and it is not cosmetic.** This is an extension of Memory Bank,
never a correction of it. Memory Bank gives scope and identity; Custody adds
origin and derivation. Any wording that reads as "Google forgot something" is
wrong in the README, the video, and the Devpost copy.

Threat standing: OWASP **ASI06** in the 2026 Agentic AI Top 10. Published attack
success rates of 80%, 95%, 99.8%. 91,000 honeypot attack sessions Oct 2025 to
Jan 2026. Supporting the revocation half: **97%** of actively maintained MCP
servers changed their published tool surface between first and latest release,
and one registry audit found **76 confirmed malicious payloads**. Trust is a
point-in-time judgement, so a write-time control without a revocation path is
half a product.

Non-goals:

- **No model decides a fact.** Origin and derivation come from event structure.
  A model may summarise, explain and rank. It may never label, adjudicate, or
  set trust.
- **No agent that is not enforcing a property or changing what a human does.**
  Two were designed and cut under this rule on 2026-08-09: a Trust Steward,
  because a catalog needs a form and a database rather than an agent; and a Red
  Team agent, because it is separable assurance competing for the fourteen days.
  Both are recorded in `DECISIONS.md`. Do not reinstate either without new
  argument.
- **The console must never become required to use the product.** The core is a
  one-line drop-in, `CustodyMemoryBank(downstream=your_service)`, and that is the
  entire go-to-market. The control plane is the upsell and the demo.
- No new memory store. Memory Bank and ADK's services are the substrate.
- No content classification. Custody governs origin and derivation, not intent.
  Screening content is Model Armor's job and is not being rebuilt.
- No auth, billing, or user management.
- No second submission; no Startup Excellence attempt (needs an incorporated
  organization and corporate email, neither exists).
- No commit and no push without explicit authorization in the session.

## Architecture

**1. Origin labelling. Deterministic, no model.** Built and verified.
Every content part is USER, MODEL, TOOL or DERIVED, read off the event graph.
`Event.get_function_responses()` makes tool origin structural. Taint propagates:
a model turn following an untrusted tool response inside the same invocation is
DERIVED and inherits the distrust, because an agent that summarises a hostile
page produces a laundered copy while the raw response is discarded.

**2. The derivation graph. The differentiator, and the hardest part.**
A custody record carries `derived_from[]`, turning a per-item label into a graph
that can be traversed. This is what makes retroactive revocation possible, and it
answers a question nothing else on the market can answer.

**3. Enforcement at the write.** Built and verified.
Sessions are split before the write; untrusted content never reaches the memory
service. Retrieval therefore needs no filter, which matters because Memory Bank
does not offer one.

**4. Revocation.** Demote a tool grant, traverse descendants in the graph, remove
them from Memory Bank, append revocation and audit records.

**Consequence flagged in advance rather than discovered later:** revocation
reintroduces a read-side concern that the write-side split had removed, because a
previously admitted memory can become untrusted after the fact. Deletion from
Memory Bank is the preferred resolution and doubles as the right-to-be-forgotten
path an enterprise will ask for. **Whether the Memory Bank API supports deletion
is unverified and is a day-one check.** If it does not, revocation post-filters
retrieval instead, and G3 is proved that way.

**5. The export gateway.** Built. An external action must cite the remembered
content authorizing it, and every citation must be instruction-eligible.

**6. Judgement.** Gemini explains a quarantined memory and drafts a verdict for a
human. Structurally barred from labelling.

### The fleet

The fleet is the **governed population**, not a pipeline of specialists. The
predecessor died of five invented roles in a pipeline; that shape is banned here.

| Agent | Why it is not ceremony |
| --- | --- |
| **N department worker agents** | The governed population is the fleet. Real ADK agents doing departmental work. They are the subject of governance, not scaffolding, and they make "scalable network of institutional agents" literally true. |
| **Provenance Auditor** | Re-examines admitted memories when trust changes and drives revocation across the graph. Genuinely long-running and asynchronous, which is the "weeks of operations" clause made concrete. |
| **Custody Reviewer** | Explains what a quarantined memory attempted and drafts a verdict. Changes what a human reads: a summary rather than raw traces. |

### Data model

Firestore. One storage primitive: a create that fails when the document exists.

```
departments/{dept}                            tenant boundary
departments/{dept}/agents/{agent_id}          registration, allowed tools
departments/{dept}/grants/{tool}              trust, vouched_by, vouched_at, evidence
custody/{record_id}                           origin, trust, author, invocation,
                                              content_sha256, source_tool,
                                              derived_from[]        <- the graph edge
memories/{memory_ref}                         downstream id -> custody record
quarantine/{item_id}                          withheld content, awaiting review
revocations/{revocation_id}                   tool demoted at T, descendants pulled
audit/{record_id}                             append-only, every decision
```

Writes are idempotent on `(session_id, content_sha256)`. Revocation is idempotent
on the revocation id, so a replayed revocation cannot double-delete.

### Google product mapping

The track scores four capability groups. Every row must be demonstrable by a
command or an artifact. **No row moves to BUILT without one**, because a
predecessor shipped a GEAP table describing an integration that did not exist.

| Capability group | Product | Role in Custody | Status |
| --- | --- | --- | --- |
| Discovery and lifecycle | **Agent Registry** | department agents and their tool grants | PLANNED |
| Execution and state | **Memory Bank** | the governed substrate | PLANNED, central |
| Execution and state | **Agent Runtime** | the Auditor's long-running revocation work | PLANNED |
| Security and governance | **Agent Identity** | the principal that vouches for a tool grant | PLANNED |
| Security and governance | **Agent Gateway** | refuses ungoverned memory writes and exports | PLANNED |
| Security and governance | **Model Armor** | screens content; complements origin, does not replace it | PLANNED |
| Telemetry | **Agent Observability** | traces carrying the custody digest, so a quarantine is reproducible | PLANNED |
| mandatory | **Gemini 3.5+ via Vertex** | explains quarantined memories; never labels | PLANNED |
| mandatory | **ADK** | the seam; `BaseMemoryService` is the port | **BUILT** |
| mandatory | **Cloud Run** | control plane and reviewer | PLANNED |
| supporting | **Firestore** | the graph, quarantine, audit | PLANNED |
| supporting | **Cloud Scheduler** | daily auditor run, which makes elapsed time real | PLANNED |
| bonus | **Gemma** | cheap first-pass triage of the quarantine queue | OPTIONAL |

Every PLANNED row has an in-memory implementation behind the same port, so an
unreachable component degrades rather than blocks.

**Reachability established 2026-08-09, from the shipped SDKs rather than docs.**
There is no separate GEAP product to find, and no GEAP SDK. **GEAP is Vertex AI
renamed**; Google's own product page is titled "Gemini Enterprise Agent Platform
(formerly Vertex AI)", it absorbed Agentspace at Next '26 in April 2026, and
existing projects need no migration because the services underneath are
identical. Anyone hunting for a distinct product will find only documentation,
which is the correct outcome and not a sign of vapourware.

What that means concretely for each row:

- **Memory Bank** ships in `google-cloud-aiplatform[agent-engines]>=1.148.1,<2`,
  which is the Vertex AI SDK. Reported GA. This is the `gcp` extra of ADK.
- **Agent Identity** is a real ADK extra, `agent-identity`, requiring
  `google-cloud-agentidentitycredentials` and `google-cloud-iamconnectorcredentials`,
  with a shipped module at `google/adk/integrations/agent_identity/`. Reachable
  as code today.
- **Agent Observability** is the `otel-gcp` extra: OpenTelemetry instrumentation
  for google-genai, grpc and httpx.
- **Agent Gateway and Model Armor have no ADK module and no client library**,
  because they are platform and networking services rather than SDK surfaces.
  Demonstrating them is configuration and a routed call, not an import. Plan the
  proof accordingly; do not wait for a package that will never exist.
- Also present and unplanned: `a2a` and `antigravity` extras, if either becomes
  useful.

Baseline:

- Built and green on 2026-08-09: 52 tests, lint clean, entirely offline.
  `custody/origin.py`, `custody/service.py`, `custody/action.py`,
  `custody/adapters/adk.py`, `scripts/demo.py`.
- Verified against real **google-adk 2.6.3** in a project venv, not the system
  interpreter. `VertexAiMemoryBankService` is a `BaseMemoryService`, and the port
  has exactly two abstract methods, so governing one governs the other.
- Pinned by test: `InMemoryMemoryService.search_memory` matches on `part.text`
  only, so a raw `function_response` is stored and never retrieved. The laundered
  restatement is the dangerous form because it is the retrievable one.
- **Day-one checks, when the account lands 2026-08-10.** Whether Memory Bank
  supports deletion. Whether Vertex's `agent_engines.memories.retrieve` accepts
  filters ADK does not pass. Whether GEAP components are reachable on a fresh
  account at all. A 200 on any other account is not evidence.

Acceptance gates:

- **G1 deployment and live substrate.** A Cloud Run control plane accepts a
  trigger and returns a run id; the record shows a Gemini 3.5-or-newer model
  served through Vertex AI; at least one ADK agent runs; memory is written
  through live Memory Bank. Proof: `gcloud run services describe`, one run
  document, console on screen.
- **G2 enforcement is structural, and reports its own cost.** A poisoned memory
  is excluded from instruction-eligible context by construction, with the
  negative control showing the same session acting on it when Custody is off.
  **Fails if the defence is a marker the model is asked to respect.** The same
  run reports recall cost: events withheld against events seen, and how many
  withheld were benign. A gate that hides its price is what this project argues
  against.
- **G3 retroactive revocation across the graph.** A tool trusted on day one is
  demoted on day N. Every memory descended from it, including model restatements
  at least two hops downstream and across more than one department, is identified
  and removed. Replaying the revocation removes nothing further and produces no
  duplicate records. Proof: the graph before, the revocation record, the graph
  after, and a replay.
- **G4 cross-department isolation.** Department A cannot raise trust for
  department B's tools, and a memory quarantined in A never surfaces in B's
  retrieval. Proof: two adversarial attempts, both refused and audited.
- **G5 four capability groups, with real elapsed time.** One artifact per group:
  discovery and lifecycle, execution and state, security and governance,
  telemetry. Plus Cloud Scheduler running the Auditor daily from first deploy to
  filming, with one custody record showing genuine timestamps across that span
  including a memory admitted early and revoked later. Nothing fast-forwarded.

Verification:

`make check` runs lint and the offline suite with no network and no cloud; the
core is pure so its whole contract is testable without either. `make demo` runs
the poisoning scenario both ways. `make revoke` demonstrates G3 offline against
the in-memory graph. `make gates` prints PASS/FAIL per gate by reading persisted
custody, quarantine, revocation and audit records rather than asserting in prose.
Manual: watch the four-minute recording and confirm every claim is visible on
screen.

## Stated assumption, not a finding

**Two bets, not one, and they stack.**

First: **long-term memory adoption is early.** Measured 2026-08-09, 2 of 34
official ADK sample agents use a memory service and 1 writes to it. For the
hackathon this is not a problem, because the Fleet track mandates context across
weeks of asynchronous operations, so the judged population must use memory. For
the subscription plan it is a real constraint and should be priced.

What survived testing: the governed path is canonical. ADK's own docstring
recommends `await ctx.add_session_to_memory()` in an after-agent callback, which
writes the whole session including every function response.

Second: **no enterprise incident data exists for memory poisoning.** It has formal
standing as OWASP ASI06 and demonstrated attack success rates in research, which
is more than the predecessor's threat model ever had, but recognised and
demonstrated is not happening to customers. This is a declared bet on a problem
that is arriving. Do not let it drift into the README as evidence of demand.

## Kill conditions

- If the account cannot serve Gemini 3.5+ through Vertex, or an ADK agent cannot
  reach Cloud Run, by **2026-08-20**, stop. Deployment blocked the predecessor
  for its entire life.
- If G2 cannot be made structural, so the only defence is asking the model to
  respect a label, stop and say so. That is the difference between a control and
  a suggestion.
- If Memory Bank already carries enforceable origin metadata, the gap is closed
  and the project is unnecessary. **Checked 2026-08-09 from source: it does
  not.** Re-confirm against the live service.
- If revocation cannot be made correct, ship the write-side control alone and cut
  the revocation claim from every artifact rather than weakening it.

## Staging

Roughly fourteen clear days. Stop wherever the clock stops rather than
half-building everything.

1. Derivation graph and retroactive revocation, offline. The differentiator.
2. Firestore persistence behind the existing ports.
3. **G1 on Cloud Run.** Deliberately third. The predecessor left deployment last
   and stayed blocked for its entire life.
4. Trust catalog on Agent Registry, with cross-department isolation tests.
5. Department worker agents at scale, which is where the credits go.
6. Custody Reviewer on Gemini, plus Observability traces.
7. Console, README, architecture diagram, and the four-minute film.

## Schedule

- Today is 2026-08-09. Submission closes **2026-08-31 17:00 PDT**, which is
  2026-09-01 05:30 IST. The local date is a day later than the posted one.
- XPRIZE was due 2026-08-17 and is mostly finished, so 08-17 to 08-31 is roughly
  fourteen clear days. The old "08-18 onward is double-booked" reasoning was
  based on wrong dates and must not be reused.
- Bonus points are nearly free and most entrants skip them: a public build
  write-up (0.2), a post tagged #AllThingsAgenticHackathon (0.2), additional
  Google models (0.2 each, max 0.6). Claim Gemma honestly for triage. Do not
  invent a Veo use; a forced integration reads worse than an absent one.

## Prior work disclosure

Submission period opened 2026-08-04; this repository was created 2026-08-09, so
it is new work. `../warrant` and `../vigil` are the author's own in-period work
and carry no disclosure burden, but must be listed if any code is lifted.
`google-adk` is consumed unmodified. Do not read from or modify
`~/datahub-causality-agent`, `~/priorto`, Throughline, or Chronicle.

Status: active
