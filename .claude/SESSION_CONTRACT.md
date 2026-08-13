# Custody, session contract

Working name: Custody. Chain of custody for agent memory. Rename is cheap until
the first public artifact, expensive after the demo video.

Objective: Ship one submittable artifact to the All Things Agentic Hackathon
(Google, Devpost) under **Fortified Enterprise Fleet**. Custody is a
revision-aware provenance layer over agent long-term memory across a fleet of
departmental agents. An agent may bind only a tool whose live MCP definition
matches the version its department approved. Every durable memory records where
its content came from, which exact tool version introduced it, and what it was
derived from. Because derivation is recorded, a tool revision discovered
compromised later can have every memory descended from it identified and pulled,
across every department, agent and session since.

The product in one sentence, and it must stay one sentence:

> Custody blocks an observed unapproved tool revision before dispatch, and if
> an approved revision is later compromised, identifies every memory descended
> from it for selective revocation.

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
**where the content came from**, **which tool version introduced it**, or **what
it was derived from**. Custody supplies those facts, on top, through the
existing port and without modifying anything.

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

## Revision pivot, proven live on 2026-08-13

Google Agent Registry does not automatically introspect an MCP server. If a
server changes a tool schema, its owner must manually upload a new definition.
That creates a measurable gap between the catalogued surface and the one an
agent can bind at runtime. The source is [Google's Agent Registry MCP management
documentation](https://docs.cloud.google.com/agent-registry/manage-mcp-tools?hl=en).

`make revision-spike` is the decision artifact. It reads a saved registry
snapshot and a changed later `tools/list` fixture, computes canonical SHA-256
revision digests, and proves all five required gates:

1. stale Registry metadata differs from the changed surface;
2. the baseline binds the stale snapshot;
3. the governed path refuses before tool dispatch;
4. revision-specific revocation removes three cross-department descendant hops
   and preserves a sibling revision plus unrelated memory; and
5. the breach, detection, and containment story has a 150-second demo budget.

The offline proof output is `proof-out/revision-spike.json`. Its live successor,
`make live-registry-attack`, writes `proof-out/live-registry-attack.json` and is
judged independently by `make registry-gates`.

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

**1. Revision admission. Deterministic, no model.** Built and verified live.
`custody/revision.py` canonicalizes a live `tools/list` response, compares every
server-qualified tool digest with the department's approved pin, and refuses a
mismatch before dispatch. Its successful admission yields the trust and exact
revision that the existing origin boundary consumes. The approved snapshot is
read back from a real Agent Registry Service. The application-side catalog is
still in-memory; durable approval storage remains future work.

**2. Origin labelling. Deterministic, no model.** Built and verified.
Every content part is USER, MODEL, TOOL or DERIVED, read off the event graph.
`Event.get_function_responses()` makes tool origin structural. Taint propagates:
a model turn following an untrusted tool response inside the same invocation is
DERIVED and inherits the distrust, because an agent that summarises a hostile
page produces a laundered copy while the raw response is discarded.

**3. The derivation graph. The differentiator, and the hardest part.**
A custody record carries `derived_from[]`, turning a per-item label into a graph
that can be traversed. Tool roots carry a server-qualified tool id plus revision
digest, so revocation can select one definition without deleting a later clean
revision. This is what makes retroactive revocation possible, and it
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
| Discovery and lifecycle | **Agent Registry** | department agents and approved MCP revision pins | **LIVE**, stale v1 snapshot vs live v2 proof |
| Execution and state | **Memory Bank** | the governed substrate | **LIVE**, `make live-g1` |
| Execution and state | **Agent Runtime** | identity-bound deterministic Gateway probe | **LIVE**, `make live-gateway` |
| Security and governance | **Agent Identity** | exact principal authorized for the registered MCP tool | **LIVE**, `make live-gateway` |
| Security and governance | **Agent Gateway** | IAP-enforced allow/deny boundary before owned MCP dispatch | **LIVE**, `make live-gateway` |
| Security and governance | **Model Armor** | screens content; complements origin, does not replace it | **LIVE**, `make live-model-armor` |
| Telemetry | **Agent Observability** | traces carrying the custody digest, so a quarantine is reproducible | **LIVE**, `make live-observability` |
| mandatory | **Gemini 3.5+ via Vertex** | explains quarantined memories; never labels | **LIVE**, Gemini 3.5 Flash |
| mandatory | **ADK** | the seam; `BaseMemoryService` is the port | **LIVE**, real Runner callback in G1 |
| mandatory | **Cloud Run** | control plane and reviewer | **LIVE**, control plane revision `00001-hz6` |
| supporting | **Firestore** | the graph, quarantine, audit | PARTIAL: `custody`/`revocations`/`auditor` collections LIVE behind `FirestoreCustodyGraph`/`FirestoreAuditorLog` (G5); `quarantine`/`departments`/`grants` remain in-memory, PLANNED |
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

- **Memory Bank** ships in `google-cloud-aiplatform[agent-engines]==1.163.0`,
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
- **Two of the three day-one checks settled 2026-08-10 without credentials**,
  by reading `google-cloud-aiplatform` 1.163.0 rather than waiting for an
  account. Both were questions about a client library's surface.

  **Deletion is supported.** `agent_engines.memories.delete(name=...)` exists,
  keyed on the memory's resource name
  (`projects/{p}/locations/{l}/reasoningEngines/{r}/memories/{m}`). So G3's
  preferred revocation path is available and the post-filter fallback is not
  needed. Consequence: a custody record must map to that resource name, which
  is what `memories/{memory_ref}` in the data model is for. **Unresolved:** ADK's
  `add_session_to_memory` returns `None`, so the names of memories it created
  are not handed back. Obtaining the mapping needs either the raw client or a
  list call, and that is a real design decision, not a detail.

  **Scope is an arbitrary, enforced isolation primitive**, and this is the more
  useful finding. `Memory.scope` is `dict[str, str]`, documented as *"Required.
  Immutable. Represents the scope of the Memory. Memories are isolated within
  their scope."* ADK merely happens to pass `{app_name, user_id}`. So
  department, and potentially trust, can be carried in scope and Memory Bank
  enforces the isolation itself rather than Custody enforcing it alone. That
  strengthens G4 and gives back a read-side filter if one is ever needed.
  **Inferred, not yet run:** that arbitrary scope keys are accepted and that
  retrieval matches on them exactly. The docstring says so; the account will
  settle it.

  **Still needs the account:** whether GEAP components are reachable on a fresh
  trial project at all. A 200 on any other account is not evidence.

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

- **R1 revision-aware admission.** A real MCP server's registered tool
  definition is approved, then its live `tools/list` definition changes without
  a Registry update. An ungoverned agent still binds the stale catalogue entry;
  Custody detects the digest mismatch before dispatch. A later revocation removes
  all and only records descended from that revision. Proof: Registry entry, live
  `tools/list` digest, denied application-side admission trace and unchanged
  server dispatch counter, graph before and after.

- **S1 Gateway enforcement.** One identity-enabled Agent Runtime is bound to an
  Agent-to-Anywhere Gateway and one registered owned MCP server. Under an exact
  tool allow-list, one call reaches the same-instance server ledger. After an
  etag-protected transition to an allow-list containing no registered tool, the
  same call returns 403 and every ledger field remains unchanged. Proof: raw
  Gateway, extension, policy, Cloud Run, Registry, Runtime and Agent Identity
  resources; the initial, allow and deny IAM policy snapshots; the
  server-authored Admin Activity etag chain; both ledger transitions; and
  distinct trace-correlated `tools/call` logs independently judged and reread
  from Google Cloud by `make gateway-gates`.

- **M1 Model Armor content screening.** One owned Model Armor Template
  (`custody-approved-tool-ingress`, PI-and-jailbreak filter enabled at
  `MEDIUM_AND_ABOVE`, discovered already provisioned in the project and reused
  rather than recreated) screens a proof-bound jailbreak/PI payload and a
  proof-bound clean payload through live `sanitizeUserPrompt` calls. Model
  Armor has no ADK client library, same as Agent Gateway; the proof is
  configuration plus a routed call, not an import. Proof shape mirrors R1/S1:
  `scripts/live_model_armor.py` writes `proof-out/live-model-armor.json`, and
  `scripts/model_armor_gates.py` independently judges it offline, then
  independently rereads the Template and both Cloud Logging entries (by
  server-issued insert ID) from Google Cloud using code-owned resource
  identifiers. Non-goal: Model Armor does not gate MCP tool admission or IAP;
  it is a separate, additive content check, not folded into
  `DedicatedIapPolicy`.

- **O1 Agent Observability.** Extends the G1 live ADK Runner call
  (`scripts/live_memory_bank.py`, additive only: one new `admitted_digests`
  field, no change to G1's admitted/withheld counts or Memory Bank behavior)
  with an explicit OTel span wrapping the admitted session, carrying the
  exact `content_sha256` digest of one admitted `CustodyRecord` as a
  `custody.digest` span attribute, exported to Cloud Trace via
  `google.adk.telemetry.google_cloud.get_gcp_exporters(enable_cloud_tracing=
  True, ...)`. **A real environment limit reshaped the claim during
  building**: `cloudtrace.googleapis.com/v1` returns "_Trace bucket not
  found in project" for every trace this producer exports, and `v2` has no
  read/list endpoint at all — Cloud Trace's own span storage is not
  independently verifiable in this project via any API found. The
  independently-verified claim instead binds through Cloud Logging: the
  producer also writes one structured log entry (`custody-observability`
  log) carrying the exact trace ID, span ID, and digest, and
  `scripts/observability_gates.py` rereads that entry from Google Cloud by
  its server-issued insert ID, the same mechanism every other live proof
  here already uses. `scripts/live_observability.py` writes
  `proof-out/live-observability.json`.

- **G5 Cloud Scheduler elapsed-time record, clock started 2026-08-13, gate
  itself still open.** Structurally different from every other gate: it
  requires genuine calendar time between first deploy and filming ("nothing
  fast-forwarded"), so it cannot be produced and verified in one session, only
  started. DDIA review chose Firestore (Native mode, us-central1) as an
  append-only log behind the existing `CustodyGraph`/`TrustCatalog` ports,
  mirroring `custody/store.py`'s SQLite pattern; `custody/firestore_store.py`
  implements `FirestoreCustodyGraph` and `FirestoreAuditorLog`.
  `CustodyRecord.admitted_at` and `Revocation.revoked_at` are new optional
  fields (`None` unless a durable store stamps them from its own
  server-assigned write time; the pure core never sets them). The control
  plane gained `POST /auditor` (idempotent daily heartbeat; seeds one fixed
  synthetic record, `g5-elapsed-time-seed`, on the very first invocation
  ever) and `GET /custody/{id}` (durable read-back). Deployed as Cloud Run
  revision `custody-control-plane-00003-hd2` with
  `CUSTODY_FIRESTORE_PROJECT` set and `max-instances=1`. **Durability across a
  real cold start was verified live**: the seed record's `admitted_at`
  (`2026-08-13T11:55:24.745231+00:00`) was byte-identical after forcing a new
  revision, and the heartbeat correctly reported `first_run: false`. Cloud
  Scheduler job `custody-g5-auditor` (`us-central1`, daily at 06:00 UTC,
  `POST /auditor`) is created and `ENABLED`. Non-goal for now: the eventual
  revocation of the seed record (near filming, via the existing `/revoke`
  endpoint) and `scripts/scheduler_gates.py` (offline judge plus live
  attestation, mirroring `model_armor_gates.py`) are deliberately deferred —
  building a judge for a multi-day span before any days have elapsed would
  have nothing real to judge. Known gap: the control plane is fully public
  (`allUsers` invoker, unchanged from its existing G1 posture) rather than
  gated behind OIDC as DDIA recommended; Cloud Run IAM is service-level, not
  per-route, and every other mutating endpoint on this service (`/sessions`,
  `/vouch`, `/revoke`) was already public and unauthenticated before this
  session, so gating only `/auditor` was not possible without either
  splitting it into a second service or authenticating the whole demo
  control plane — judged out of scope for this pass. Document this precisely
  as a synthetic proof service, same posture as the Registry MCP server, not
  as a hardened design.

Verification:

`make check` runs lint and the offline suite with no network and no cloud; the
core is pure so its whole contract is testable without either. `make demo` runs
the poisoning scenario both ways. `make revoke` demonstrates G3 offline against
the in-memory graph. `make gates` prints PASS/FAIL per gate by reading persisted
custody, quarantine, revocation and audit records rather than asserting in prose.
`make revision-spike` produces the separate R1 offline evidence artifact.
`make live-registry-attack` produces R1 live evidence, and
`make registry-gates` independently recomputes and judges it. `make
live-gateway` produces S1 live evidence. `make gateway-gates` first rejects
stale, broadened, inconsistent, fail-open or unbound fields, then independently
rereads the fixed owned Google Cloud resources and exact log insert IDs so a
coherent forged JSON document cannot pass.
Manual: watch the four-minute recording and confirm every claim is visible on
screen.

**G1 passed live on 2026-08-13.** `make live-g1` generated a unique proof scope,
verified Cloud Run revision `custody-control-plane-00001-hz6`, received a
proof-bound response from `gemini-3.5-flash` through Vertex AI, and ran a real
ADK Runner whose one after-agent callback sent two admitted events through
Custody into Agent Engine `6936011268348182528`. Memory Bank returned one memory
from that unique scope. `make gates` independently read `proof-out/g1.json` and
reported G1 PASS. G1 evidence expires after 24 hours and must be regenerated for
filming.

**R1 passed live on 2026-08-13.** `make live-registry-attack` deployed Cloud Run
revisions `custody-export-mcp-00007-ntt` and `00008-fhn` at one URL, registered
the exact v1 `tools/list` snapshot in Agent Registry, and left that Service
unchanged while v2 added `forward_to` and changed its safety annotations. The
negative control dispatched v2 once through the endpoint read back from
Registry, and the returned payload identified the same process as the ledger.
Custody observed revision `a418b10c...` instead of approved
`e5f7639e...`, raised `revision_mismatch`, and the same server instance's
dispatch counter did not move. Graph roots were bound to hashes of the live v1
and v2 call results; revoking v1 removed its three-hop sales/support/finance
lineage while preserving the v2 branch and unrelated record. `make
registry-gates` independently recomputed both revision digests and reported
eight PASS results. This is a live Agent Registry and Cloud Run claim; the
descendant deletion is still CustodyGraph, not live Memory Bank deletion.
It proves fail-closed blocking for an observed declared-surface mismatch. It
does not detect behavior-only changes with an identical `tools/list`, and an
allowed call is not yet cryptographically bound to the preceding surface read.
The live Gateway now enforces Agent Identity and tool-name admission, but its
IAP condition does not attest the revision digest. Until the Gateway or MCP
server binds that digest at dispatch, the broader no-unapproved-revision
contract remains architecturally unshippable.

**S1 passed live again on 2026-08-13 against schema v2, proof
`e2b9f562fa3a48249054b977b5779a21`.** The first schema-v2 attempt
(`8030f2119417461bb9db9c4eb066ef64`) was deliberately rejected: its CEL
expired the empty-name handshake clause together with the `lookup_customer`
lease, so a post-expiry call could fail before `tools/call` and produce no
log. Recovery restored exact safe deny; no cloud mutation was left in flight.
The corrected canonical condition splits the two clauses so handshake/non-tool
traffic stays admitted independent of the tool lease:
`api.getAttribute(...) == '' || (request.time < timestamp(...) &&
api.getAttribute(...) == 'lookup_customer')`. Agent Runtime
`5289382654590844928` retained its Agent Identity and regional Gateway
binding. Under the corrected lease, Cloud Run revision
`custody-export-mcp-00009-wp2` moved from dispatch count 0 to 1 for one
allowed `lookup_customer` call; a `custody_policy_canary` call under the same
live lease was denied before dispatch, proving the admission was narrow
rather than a broad historical allow; a `lookup_customer` call issued after
the server-side `request.time` boundary passed was denied before dispatch;
and a final `lookup_customer` call after the policy was restored to safe deny
was denied before dispatch. The ledger stayed byte-identical at 1 across all
three denied controls. Gateway logs recorded four distinct traces as
`ALLOWED/200` and `DENIED/403`. Admin Activity bound the initial, allow and
deny etags in order. `make gateway-gates` reported twenty PASS results across
the offline judge and the independent live Google Cloud attestation. The
proof is bounded to this owned Runtime, Gateway and MCP path; it does not
establish universal egress coverage, repair stale Registry metadata, remove
the allowed call TOCTOU boundary, or delete live Memory Bank descendants.

**M1 passed live on 2026-08-13, proof `4af5a4b8d3244c3c80054c15b69e58ad`.**
Template `custody-approved-tool-ingress` was found already provisioned in the
project with `logSanitizeOperations` enabled and was reused rather than
recreated. A proof-bound jailbreak/PI prompt was blocked
(`MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK`, "The prompt violated Prompt
Injection and Jailbreak filters."); a proof-bound clean prompt with the same
proof ID was allowed (`MODEL_ARMOR_SANITIZATION_VERDICT_ALLOW`). Both calls
produced one server-authored Cloud Logging entry each, bound to the exact
proof-embedded prompt text. `make model-armor-gates` reported nine PASS
results across the offline judge and the independent live Google Cloud
attestation. The proof is bounded to this one owned Template; it does not
screen traffic Custody has not explicitly routed through it and does not gate
MCP tool admission or IAP.

**O1 passed live on 2026-08-13, proof `753d24b91d2845dbb1dd58eb5bd5429e`.**
The same live ADK admission G1 proves ran inside one OTel span
(`custody.g1.admission`, trace `dc70e417a45d636c86d7fa1d273a7101`, span
`e2de8000416c1e5a`) carrying the exact digest of one admitted `CustodyRecord`
as a `custody.digest` attribute, exported to Cloud Trace. One server-authored
Cloud Logging entry recorded that same trace ID, span ID, and digest
together. `make observability-gates` reported seven PASS results across the
offline judge and the independent live Google Cloud attestation, which
rereads the log entry, not the Cloud Trace span: this project's Cloud Trace
v1 API returns no default trace bucket for any exported trace, and v2 has no
read endpoint, so Cloud Trace's own storage is not independently verifiable
here. The proof shows a trace/digest binding exists for one live admission;
it does not verify Cloud Trace storage, and it does not change G1's
admitted/withheld counts or Memory Bank behavior.

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
4. Revision catalog on Agent Registry and Agent Gateway, with a real changed
   MCP surface and cross-department isolation tests.
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
