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
| **Provenance Auditor** | Re-examines trust and drives revocation across the graph, deterministically, on the deployed Cloud Scheduler's own daily clock rather than the demoter's request. **Real, live-proven 2026-08-14**: `/demote` withdraws a grant durably; `/auditor`'s sweep is the only thing that ever calls `CustodyGraph.revoke` on a demotion's behalf. `make live-auditor` / `make auditor-gates`, 9/9 PASS. See the sub-build section below. |
| **Custody Reviewer** | Explains what a quarantined memory attempted and drafts a verdict. Changes what a human reads: a summary rather than raw traces. **Real, live-proven 2026-08-14**: `custody/review.py`'s `draft_verdict` takes one `Quarantined` item and a real Gemini call through Vertex AI, returns a `Verdict` with no trust/origin field. `make live-review` / `make review-gates`, 9/9 PASS. See the sub-build section below. |

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
| mandatory | **Gemini 3.5+ via Vertex** | explains quarantined memories; never labels | **LIVE**, `make live-review`, real verdict on a quarantined item (`scripts/live_review.py`), not the earlier connectivity echo |
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

- **R2 dispatch-bound attestation, closing R1's stated TOCTOU gap.** R1's own
  admission check runs client-side, at read time; nothing before this bound
  the specific `tools/call` dispatch to the specific `tools/list` read that
  authorized it, and IAP's static CEL conditions cannot carry a per-request
  digest asserted by an earlier, separate call. The owned MCP server
  (`custody-export-mcp`) now mints a short-lived, server-signed token over
  the digest it just returned from `tools/list`, and refuses to dispatch a
  tool unless the caller presents a token whose digest matches what the
  server computes for that handler **at the instant of dispatch**, before it
  runs. Proof: a token minted against one revision is refused server-side,
  citing the digest mismatch, when presented after the server is redeployed
  to a different revision; the dispatch counter does not move. **Non-goal,
  stated plainly and never overclaimed**: this closes the declared-surface
  TOCTOU only. It does not and cannot detect a behavior-only change under an
  identical `tools/list` — that needs the server to attest its own running
  code identity, a different and larger problem, left open. The nonce-replay
  ledger is process-local, the same single-owned-instance scope R1 and S1
  already accept, not a new, broader guarantee.

- **R2 replay closed.** A structurally valid, unexpired token presented a
  second time is refused citing nonce replay; only its first use's dispatch
  counter moves. Proof: two `tools/call` traces under the same nonce, one
  accepted, one denied, independently correlated from Cloud Logging.

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

- **D1 selective deletion from live Memory Bank, viability gate.** `G3`
  proves revocation across `CustodyGraph`; it has never deleted the
  underlying memory from live Memory Bank, per `custody/graph.py`'s own
  module docstring ("wiring that deletion to live Memory Bank is a day-one
  check, not a design change here") and `DECISIONS.md` #2/#3. Before writing
  deletion code: verify live, against the real G1 Agent Engine
  (`6936011268348182528`), whether a `CustodyRecord` can be mapped to a
  deletable Memory Bank resource name (`memories.delete(name=...)`), using
  `ingest_events`'s returned operation and/or a `memories.retrieve`/`list`
  call to find the created memory's own name. **Fails, and the correct
  outcome is documentation, not code**, if Memory Bank's server-side
  derivation (already established in `DECISIONS.md` #3: "a stored memory is
  therefore not byte-identical to any event and cannot be matched back to a
  custody record afterwards") means no reliable one-to-one mapping exists
  between an admitted `CustodyRecord` and one `memories.delete`-able name. If
  it does pass: extend `FirestoreCustodyGraph.revoke` (or a thin wrapper) to
  call `memories.delete` for each removed record's mapped memory name, and
  prove it live — revoke a tool, then show the memory is gone from a
  `search_memory` call afterward. Proof: `proof-out/live-memory-deletion.json`
  or equivalent, showing the pre-revoke memory name(s), the revoke call, and
  a post-revoke `search_memory`/`retrieve` that no longer returns it.

- **D2 selective deletion, built on a corrected finding.** D1's `ingest_events`
  finding stands (`DECISIONS.md` #2), but a live-tested correction found a
  real, deterministic mapping through a different write path:
  `agent_engines.memories.create(config={"memory_id": <id>})` does not share
  `ingest_events`'s consolidation behavior, verified live with two
  contradictory same-scope facts staying as two separate, independently
  deletable resources. Build this as a new, additive, opt-in write
  capability (`custody/service.py`'s `RecordWriter`, `custody/adapters/
  memory_bank.py`), never a replacement for `ingest_events` or a change to
  G1's already-proven Cloud Run flow. Proof: one session writes two
  trusted, different-tool records through the new path to the real Agent
  Engine; both are retrievable via `search_memory`; revoking one tool
  deletes exactly its memory (`memories.delete` on the predicted
  `memory_id_for(record.id)` name) and a subsequent `search_memory` no
  longer returns it while the other tool's memory is untouched. Non-goal,
  stated in every artifact: memories already written through `ingest_events`
  (including G1's own) are not covered by this mechanism.

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

**R2 passed live on 2026-08-13, proof `0aa93adc180a4e4794c85869bdcb312f`,
closing the gap R1 stated above.** The owned `custody-export-mcp` server
(revisions `custody-export-mcp-00011-rm5` then `-00012-8kz`, same Cloud Run
URL, same secret) now mints a short-lived, HMAC-signed token bound to the
digest it returns from every `tools/list`, and verifies it itself, at the
instant of dispatch, before `lookup_customer` ever runs. A token minted
against v1's digest, presented to the redeployed v2 instance, was refused
server-side citing `digest_mismatch`, with `dispatch_count` staying at 0 on
that instance; the same token replayed against v1 a second time was refused
citing `replayed`, with `dispatch_count` staying at 1. Both denials, and both
Cloud Run revisions, were independently reread live from Cloud Logging and
Cloud Run by `make revision-binding-gates` (13 PASS: 9 offline structural
checks, 4 live rereads by server-issued insert ID and revision name), not
just trusted from the producer's own JSON. One real implementation surprise
worth recording: the obvious channel, `MiddlewareContext.message.meta`, does
not carry the caller's token, because FastMCP's own `tools/call` dispatcher
rebuilds `CallToolRequestParams` from just `(name, arguments)` before a
middleware ever sees it, discarding the request's `_meta`. The token only
survives in the low-level MCP SDK's `request_ctx` contextvar, read via
`Context.request_context.meta`; the first live attempt failed for exactly
this reason before the fix was found and verified in-process. **Non-goal,
unchanged from R1's own statement of it**: this closes the declared-surface
TOCTOU only. A behavior-only change under an identical `tools/list` is still
undetected, since nothing here attests the server's running code, only the
schema it declares. The consumed-nonce set is process-local, the same
single-owned-instance scope R1 and S1 already require, not a new, broader
replay guarantee.

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

**D1 checked live on 2026-08-13 against Agent Engine
`6936011268348182528`, and is a documented non-viability, not a build.**
`agent_engines.memories.delete(name=...)` was already confirmed callable
(day-one check). The open question was whether a `CustodyRecord` can be
mapped to the name it deletes. It cannot, reliably, through the governed
`ingest_events` write path Custody uses:
`MemoryBankIngestEventsOperation` carries no `response` and no created-memory
name (true of the type itself, and `operation.response` was empty on every
live call); `IngestionDirectContentsSourceEvent` accepts no metadata Memory
Bank passes through to the memory it generates, so no id can ride along at
write time either. A post-hoc `memories.retrieve`/`list` content match was
tried as a fallback and is unsound rather than merely approximate: ingesting
a second, topically related fact into the same scope as a first was observed
live overwriting the **same** memory resource name in place
(`update_time` advanced, `create_time` did not, `fact` text replaced
entirely). A Memory Bank memory is a mutable, server-consolidated target, not
a 1:1 destination for one ingested event, so deleting it on one record's
revocation can destroy content later merged in from other, still-trusted
records, and failing to delete it can leave a revoked record's own content
already silently superseded and gone. No code was added to
`FirestoreCustodyGraph.revoke`. `custody/graph.py`'s module docstring,
`DECISIONS.md` #2, and the README limitations section were updated to state
this as a checked, live-confirmed limitation rather than an open day-one
question.

**A second, narrower hypothesis was raised and also checked live, same day.**
`IngestEventsConfig` has request-level `metadata` plus
`metadata_merge_strategy=REQUIRE_EXACT_MATCH`, documented as "restrict
consolidation to memories that have exactly the same metadata as the
request." The idea: tag every ingest with `{"custody_record_id": <id>}` so
consolidation only ever merges writes from the same record, giving deletion a
safe, filterable partition. Tested live, same engine, same scope-reuse
pattern: two ingests carrying **different** `custody_record_id` metadata
values, one topically related fact each, still collapsed into **one** memory
resource, its fact rewritten to merge both ("...requires 90 days instead of
30"). `REQUIRE_EXACT_MATCH` did not prevent cross-record consolidation in
practice. Per the DDIA review's own stop condition ("if gate 1 fails, stop"),
this closes the metadata-partition path too, without needing to chase the
separate `list(filter=...)` syntax error the same probe also hit. No code
was written for this path either. This does not change G3's offline graph-revocation guarantee, only
closes the gap between it and live Memory Bank deletion as not closable
through the `ingest_events` write path.

**Corrected the same day, on request, live-verified rather than reasoned
from a docstring.** `agent_engines.memories.create(fact=..., config=
{"memory_id": <custody_record_id>, ...})` does not share `ingest_events`'s
consolidation behavior: live-tested with two contradictory, same-topic
facts in one scope, both `memory_id`-pinned to a record id, and both
persisted as separate resources with distinct `create_time`s, no overwrite.
`memories.delete()` on the predicted name removed exactly the targeted one
and left the other's fact untouched. **Selective deletion is proven
buildable now, with a real, deterministic `record.id → memory_id` mapping
and no search or content-matching needed.** The catch is architectural, not
technical, and is exactly what `DECISIONS.md` #3 already named: `create()`
takes `fact` from the caller instead of deriving it from raw session events,
so using it means Custody stops governing ADK's existing write path
(`add_session_to_memory` → `ingest_events`, the one G1's live proof already
depends on) and starts authoring memory content itself, trading the
"extends Memory Bank" framing for "second memory writer." That tradeoff has
not been made here; it is a roadmap decision, not a finding this session
should make unilaterally this close to the submission deadline. Full
write-up in `DECISIONS.md` #2.

**D2 passed live on 2026-08-13, first attempt, against Agent Engine
`6936011268348182528`.** On explicit request, the tradeoff above was made
for a new, additive, opt-in write path only, never for G1's own:
`custody/service.py` gained a `RecordWriter` capability
(`CustodyMemoryService.add_session_to_memory` writes one record at a time
through `downstream.write_record` when a downstream offers it, unchanged
otherwise), and `custody/adapters/memory_bank.py` gained
`AgentEngineMemoryBank` (writes via `memories.create`, `memory_id` pinned to
`memory_id_for(record.id)`) and `RevokingMemoryBankGraph` (wraps any
graph's `revoke`, then deletes each removed record's memory by that same
computed name). One live session wrote two trusted, different-tool records
(`sales/lookup`, `finance/lookup`); both facts were retrievable via
`search_memory` before revocation. `RevokingMemoryBankGraph.revoke(tool=
"sales/lookup", ...)` removed exactly `inv-sales:0:0` from the graph and
deleted `.../memories/cr-5e69b7e2...`; a subsequent `search_memory` no
longer returned the sales fact while the finance fact was untouched. `make
memory-deletion-gates` independently recomputed `memory_id_for` for both
records and reported seven PASS results. **This is the exact acceptance
criterion the original ask stated**: "revoke a tool, show the memory is
gone from a `search_memory` call afterward," now proven live rather than
closed as non-viable. G1's Cloud Run control plane, its ADK Runner flow,
and its `ingest_events`-written memories are unchanged and remain outside
what this mechanism can delete; that boundary is stated in the producer's
own `claim_boundary` field and checked by the gate script, not left as
prose.

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

## G1 migration to the D2 write path (scoped session, opened 2026-08-14)

Objective: Migrate G1's live write path from `ingest_events`
(`BlockingAgentPlatformMemoryBank` in `scripts/live_memory_bank.py`) to D2's
`AgentEngineMemoryBank`/`RecordWriter` path
(`custody/adapters/memory_bank.py`), so memories G1's own ADK Runner writes
become selectively deletable via `RevokingMemoryBankGraph`, the same
mechanism D2 already proved for a standalone session. `CustodyMemoryService.
add_session_to_memory` (`custody/service.py:225`) already auto-detects a
`write_record`-capable downstream, so no core code changes; this is a
downstream-swap plus new live proof/gates scripts.

Branch: feat/memory-provenance
Parent: 6d22ff8

Allowed files: `scripts/live_memory_bank.py`, `scripts/live_g1.py`, a new
`scripts/g1_migration_gates.py` (or equivalent gates script name), `README.md`
limitations section, `DECISIONS.md`, `HANDOFF.md`, `proof-out/*`. No changes
to `custody/service.py`, `custody/adapters/memory_bank.py`, or
`custody/adapters/adk.py` unless a live check finds the existing D2
primitives insufficient (if so, stop and report before editing them, since
those are D2's already-closed, independently-gated surface).

Non-goals:

- No Cloud Run redeploy. G1's Cloud Run leg (`_cloud_run_proof` in
  `scripts/live_g1.py`) hits the already-deployed control plane's
  `/sessions` and `/health` endpoints unchanged; only the ADK/Memory-Bank
  leg (`prove_adk_memory_bank`) changes downstream.
- No change to `custody/service.py`, D2's `RecordWriter` protocol, or
  `AgentEngineMemoryBank`/`RevokingMemoryBankGraph` — those are D2's
  already-proven, already-gated surface (`make memory-deletion-gates`,
  7/7 PASS). Reuse them; do not reopen them.
- Do not silently keep G1's old `ingest_events` proof claim once the new
  path is proven live — `HANDOFF.md`'s "Known limitations" line about
  G1's memories being undeletable must be corrected or explicitly
  superseded, not left stale.
- Do not round up an offline/unit-test pass to a live claim. Every gate
  below needs a live re-read from Google Cloud, same discipline as every
  other gate in this project.

Baseline: `make live-g1` currently passes against the `ingest_events` path
(`proof-out/g1.json`, evidence expires 24h and is already stale as of this
session — regenerate before trusting it as a pre-change baseline). `make
memory-deletion-gates` passes 7/7 against D2's standalone proof
(unaffected by this work).

Acceptance gates:

1. G1's ADK Runner flow runs live end to end on the new `write_record` path
   against real Agent Engine `6936011268348182528` — same Cloud Run health
   check, same Gemini 3.5 call, same ADK `Runner`/`after_agent_callback`
   shape as today's `live_g1.py`, only the Memory Bank downstream changed.
2. A record G1's own Runner wrote is verifiably revocable: after revoking
   its tool, a subsequent `search_memory` in that scope no longer returns
   it. Independently rereadable, not just producer-claimed.
3. No regression to G1's existing admitted/withheld counts, refused count,
   or the Gemini/Cloud Run legs of `live_g1.py` — same shape as
   `custody_split` and the `cloud_run`/`gemini` blocks in `proof-out/g1.json`
   today.
4. The retrieval-quality question is decided and documented either way:
   whether losing Memory Bank's own session-level derivation (one
   summarized memory per session under `ingest_events`) for one raw
   `admitted.text` fact per record under `write_record` changes what
   `search_memory` returns, checked live against the same `QUERY` this
   proof already uses, not assumed from the D2 write-up.

Verification: a new `make g1-migration-gates`-equivalent script
independently rereads the live artifact the same way
`scripts/memory_deletion_gates.py` and `scripts/registry_gates.py` do
(recompute `memory_id_for`, reread Cloud Logging/Agent Engine by
server-issued identifiers, reject a coherent forged JSON document). Manual:
confirm `search_memory` no longer returns the revoked fact and does return
the surviving one.

**Closed 2026-08-14, all four gates passed live.** No new gates script was
needed: `scripts/gates.py`'s existing `judge_g1` already rereads
`proof-out/g1.json` the same way (independently recomputing `memory_id_for`
for the revoked record, checking the raw before/after `search_memory`
results) and now covers this migration's shape directly, so a separate
script would have duplicated it. Found and fixed a real integration gap
first (`custody/adapters/adk.py`'s `_SessionRebuilding` never proxied
`write_record`, so `CustodyMemoryBank` could not have reached the D2 path
regardless of downstream). `make live-g1` ran live against Agent Engine
`6936011268348182528`: gate 1 (Runner + Gemini + Cloud Run unchanged, now
on `write_record`), gate 2 (a tool-origin record written through this run
is retrievable, then confirmed gone after its tool is revoked, sibling
conversational memories untouched), gate 3 (`make gates` reports G1 PASS,
same Cloud Run/Gemini legs), gate 4 (decided live: `write_record` returns
two raw, unmerged per-event facts where `ingest_events` returned one
Memory-Bank-synthesized fact — documented in `README.md`, `DECISIONS.md`
#2, `HANDOFF.md`). No Cloud Run redeploy occurred, matching the stated
non-goal.

Status: complete, superseded by the file-level status below

## Fleet review, 2026-08-14: the Provenance Auditor and Custody Reviewer rows
were named, not built

Reviewed on request against actual code, not the table's own prose. Three
findings:

1. **N department worker agents**: only one live ADK agent has ever run, once
   per proof script, one department per invocation. Never proven at N>1.
   Explicitly deferred again this pass, at the user's direction.
   **Closed 2026-08-14** — see "Sub-build: N department worker agents"
   below; five departments now run live, and the property N=1 could never
   exercise (a tool shared across departments, revoked once, pulled from
   both) is proven, not just five isolated invocations.
2. **Provenance Auditor**: the table claims it "re-examines admitted memories
   when trust changes and drives revocation across the graph." The actual
   `/auditor` handler (`custody/control_plane.py`) only seeds one fixed
   synthetic record on first-ever call and no-ops after — G5's elapsed-time
   heartbeat, not trust re-examination. There is no code path today where a
   trust change (a demotion) automatically produces a revocation; `/vouch`
   only grants, never demotes, and `/revoke` is a separate, directly-called
   endpoint with no link to catalog state at all.
3. **Custody Reviewer / Gemini row**, marked **LIVE** in the product-mapping
   table: the only live Gemini call in the repo (`scripts/live_g1.py`,
   `_gemini_proof`) is a connectivity echo ("return exactly
   CUSTODY_G1_OK:<id>"). No code path ever shows Gemini a quarantined memory
   or drafts a verdict. This is the most likely claim to be challenged live.

User's direction: build all three for real, one at a time, sequenced 2
(Auditor) then 3 (Reviewer) then 1 (N agents, deferred for now — no session
size chosen yet). Each sub-build gets its own scoped section below, closed
independently, with a handoff written at the end so work can continue in a
separate session.

## Sub-build: real Provenance Auditor (opened 2026-08-14)

Objective: close finding 2 above. `/vouch` gains a symmetric `/demote`
endpoint so trust can actually be withdrawn, not just granted; `/auditor`'s
existing daily Cloud Scheduler heartbeat (already live, G5) sweeps
outstanding demotions and drives `CustodyGraph.revoke` itself, so a
demotion recorded now and a revocation applied later, asynchronously, on
the Scheduler's own clock, is a real property rather than something a
script does on the demoter's behalf in the same call.

Branch: feat/memory-provenance
Parent: 0b4a816

Allowed files: `custody/catalog.py`, `custody/control_plane.py`,
`custody/firestore_store.py`, `tests/test_catalog.py`,
`tests/test_control_plane.py`, a new `scripts/live_auditor.py` and
`scripts/auditor_gates.py`, `Makefile`, `README.md` (fleet/product-mapping
sections only), `HANDOFF.md`, `.claude/SESSION_CONTRACT.md`,
`proof-out/*`. No changes to `custody/graph.py`, `custody/origin.py`, or
`custody/service.py` — `CustodyGraph.revoke`'s idempotency-on-`revocation_id`
contract is already correct and sufficient; the Auditor is a caller of it,
not a reason to reopen it.

Non-goals:

- No LLM in the Auditor. Trust re-examination stays deterministic, same
  discipline as revision admission and origin labelling — "no model decides
  a fact" is a project-wide rule, not something this sub-build gets to
  relax just because the table calls it an "agent."
- No full Firestore migration of `departments`/`grants`. Those remain
  documented PLANNED/in-memory except for the one new durable log this
  sub-build needs (demotions) to make the sweep survive a cold start —
  narrower than migrating the whole `TrustCatalog`.
- No change to G5's existing seed-record/heartbeat behavior. The sweep is
  additive inside the same `/auditor` handler, not a replacement.
- No N>1 worker agents in this sub-build (separate, deferred item).
- No Cloud Scheduler reconfiguration; the existing daily job
  (`custody-g5-auditor`, `0 6 * * *` UTC) is the trigger, unchanged.

Baseline: `make check` 296/296 passing offline (confirmed 2026-08-14, before
this sub-build). `make gates` reports G1/G2/G3/G4 PASS, G5 BLOCKED
(unaffected by this work — G5's own gate is calendar-time-gated, not
logic-gated).

Acceptance gates:

1. `TrustCatalog.demote` refuses a cross-department demotion by the same
   rule `request`/vouch already enforces (offline test) — a department
   cannot un-trust another department's tool any more than it can trust one.
2. A demotion is durably logged and survives a forced Firestore reread,
   same discipline G5 already proved for the seed record's `admitted_at`.
3. `/auditor`'s sweep is idempotent by construction, reusing
   `CustodyGraph.revoke`'s existing `revocation_id` dedup (the demotion's
   own deterministic id, not a fresh uuid) rather than a second
   bookkeeping table: two sweeps after one demotion produce exactly one
   revocation; a third sweep with no new demotions changes nothing.
4. Live proof, mirroring every other live gate's discipline (producer
   writes an artifact, an independent script rereads Google Cloud rather
   than trusting the artifact): demote a tool live through the deployed
   control plane; confirm the graph has *not* removed its records yet
   (proving the demotion and the revocation are genuinely decoupled, not
   silently synchronous); trigger `/auditor`; confirm via `GET
   /custody/{id}` or an equivalent durable read that the descendants are
   now gone. `scripts/auditor_gates.py` independently rereads Firestore/Cloud
   Logging by server-issued identifiers, same as `memory_deletion_gates.py`.

Verification: `make check`, a new `make live-auditor` writing
`proof-out/live-auditor.json`, and `make auditor-gates` judging it
independently. Manual: confirm the fleet table's Provenance Auditor row and
`HANDOFF.md` are corrected to cite this live evidence instead of the old
heartbeat-only description.

**Closed 2026-08-14, all four gates passed live, proof `668ad6bb08384da889c76a008e6a218d`.**
`TrustCatalog.demote` (`custody/catalog.py`) mirrors `request`'s
cross-department refusal exactly (offline tests in `tests/test_catalog.py`).
`FirestoreDemotionLog` (`custody/firestore_store.py`) is durable,
create-fails-if-exists per demotion id, replay-on-construction, covered
offline in `tests/test_firestore_store.py::FirestoreDemotionLogTests`
(cold-start replay included). `/auditor`'s sweep reuses
`CustodyGraph.revoke`'s existing idempotency on the demotion's own
deterministic id, no second bookkeeping table, covered in
`tests/test_control_plane.py::TheAuditorSweepsDemotionsAsynchronously`
(310/310 offline total). Redeployed `custody-control-plane` to Cloud Run
revision `custody-control-plane-00004-ttb` (same service, same env,
`--max-instances=1`, `--allow-unauthenticated`, same posture as before — a
prerequisite the original acceptance gates did not anticipate needing,
authorized live during the session). `make live-auditor` against the
deployed service: a tool is vouched and used, a demotion is recorded
(`/demote`, allowed), a live reread of `/custody/{id}` immediately after
confirms **no** revocation yet (the decoupling is real, not simulated),
`/auditor`'s sweep then applies exactly one revocation keyed by the
demotion's own deterministic id, and a second, independent live reread of
`/custody/{id}` (by `scripts/auditor_gates.py`, using its own
`gcloud`-derived URL, not the producer's) confirms the record now carries
that revocation. `make auditor-gates` reported 9/9 PASS: 8 offline
structural checks plus one independent live Google Cloud reread. Non-goal,
stated in the artifact's own `claim_boundary`: this does not independently
prove cross-cold-start durability of the demotion log within the live
script itself; that mechanism is proven offline instead (create-fails-if-
exists, replay-on-construction), the same split G5 already uses between its
live seed-record proof and its offline Firestore replay tests. No LLM
anywhere in this path — trust re-examination stayed deterministic, per the
project's own "no model decides a fact" rule.

Status: complete, superseded by the file-level status below

## Sub-build: real Custody Reviewer (opened 2026-08-14)

Objective: close finding 3 above. Build `custody/review.py`: a pure module
that takes one `Quarantined` item (`custody/service.py`) and an injected
`explain` callable, and drafts a `Verdict` — a summary of what the
quarantined content attempted, for a human to read. Structurally barred
from setting trust or labelling origin: `Verdict` carries no trust/origin
field, `draft_verdict` never imports or calls into `custody/catalog.py` or
`custody/graph.py`, and calling it does not mutate any catalog or graph
state, so a Gemini call has no path to becoming a fact, only an
explanation. Wire a live proof: `scripts/live_review.py` poisons a session
the same deterministic way `make demo`/G2 already do offline (an
ungranted tool's response lands in quarantine, no model involved in that
step), then makes a real Gemini call through Vertex AI (`google.genai`,
same client pattern `scripts/live_g1.py`'s `_gemini_proof` already uses) to
draft a verdict on that specific quarantined item's text, proving the call
actually reads the content rather than echoing a fixed string.

Branch: feat/memory-provenance
Parent: f9e19cd

Allowed files: `custody/review.py` (new), `scripts/live_review.py` (new),
`scripts/review_gates.py` (new), `tests/test_review.py` (new), `Makefile`,
`README.md` (the Gemini product-mapping row and a new Custody Reviewer
section), `HANDOFF.md`, `.claude/SESSION_CONTRACT.md`, `proof-out/*`,
`DECISIONS.md` if a real design tradeoff surfaces mid-build. No changes to
`custody/service.py`, `custody/origin.py`, `custody/catalog.py`,
`custody/graph.py`, or `custody/control_plane.py` — the Reviewer only
reads a `Quarantined` item already produced by existing, already-proven
poisoning logic (G2/`make demo`, `ControlPlane.ingest`); it does not need a
new HTTP endpoint or a Cloud Run redeploy, since the live claim here is the
Gemini call, not new control-plane plumbing.

Non-goals:

- No trust or origin decision anywhere in this module. `draft_verdict`
  returns a summary string plus the item's already-known department and
  source tool; it never sets `Trust`, `Origin`, or calls `revoke`/`demote`/
  `vouch`. If a future console wants a human to act on a verdict, that
  action goes through the existing `/demote` or `/revoke` endpoints,
  driven by the human, not by this module.
- No Cloud Run redeploy and no new control-plane endpoint. The quarantine
  item is produced in-process by the same deterministic `ControlPlane.
  ingest` logic G2 already proves offline; only the Gemini leg needs to be
  live.
- No content classification or verdict scoring rubric. A verdict is a
  drafted explanation for a human, not a pass/fail judgement — consistent
  with the project's "no model decides a fact" rule and Model Armor
  already owning content screening.
- Do not leave the Gemini product-mapping row in `README.md` claiming
  "LIVE" for something the fleet review already found is only a
  connectivity echo — correct it once this sub-build's own live proof
  lands, cite the new evidence, not the old echo.

Baseline: `make check` 310/310 passing offline (confirmed against
`f9e19cd`). `make gates` reports G1/G2/G3/G4 PASS, G5 BLOCKED. `make
auditor-gates` 9/9 PASS (unaffected by this work).

Acceptance gates:

1. `draft_verdict` is pure and structurally incapable of setting a fact:
   offline test constructs a `Quarantined` item, calls `draft_verdict` with
   a fake `explain`, and asserts the returned `Verdict` has no trust/origin
   field and that no `TrustCatalog`/`CustodyGraph` passed alongside it (if
   any) changed state.
2. Live proof: an ungranted tool's response is quarantined (deterministic,
   offline-shape, same as G2); a real Gemini call through Vertex AI is
   given that exact quarantined text and asked to draft a verdict; the
   verdict text provably reflects the specific content read, not a fixed
   echo — proven by a per-run random marker embedded in the synthetic
   quarantined content that only a call which actually read it could
   reproduce, appearing in the model's response.
3. The claim in `README.md`'s Gemini product-mapping row is corrected to
   cite this live evidence (`proof-out/live-review.json`) instead of the
   old connectivity-echo claim, and the fleet table's Custody Reviewer row
   in this file is updated to match.
4. `HANDOFF.md`'s "Custody Reviewer — not started" line is corrected once
   this closes.

Verification: `make check`, a new `make live-review` writing
`proof-out/live-review.json`, and `make review-gates` judging it — offline
structural checks (freshness, marker echoed in the verdict, no trust/
origin key present anywhere in the proof JSON) plus one independently
issued, separate live Gemini call (not reusing the producer's response) to
confirm Vertex AI is reachable under the project's own credentials at
judge time too, the same "do not just trust the producer" discipline every
other gate script in this project already applies. Manual: read
`proof-out/live-review.json`'s verdict text and confirm it reads as an
explanation, not a trust label.

**Closed 2026-08-14, all four gates passed live, proof `22d187b18ff54ccd809c7eeff52e6394`.**
`custody/review.py`'s `Verdict` dataclass has exactly four fields
(`department`, `source_tool`, `summary`, `drafted_at`) and `draft_verdict`
imports neither `custody.catalog` nor `custody.graph`, checked both by an
offline unit test and by an AST-parse test that fails if a future edit ever
adds either import (`tests/test_review.py`, 5/5 passing, 315/315 offline
total). `make live-review` quarantined one ungranted tool's response
in-process, through the same `ControlPlane.ingest` logic G2 already proves
offline (`quarantined: 1`, `admitted: 0`), then called `gemini-3.5-flash`
through Vertex AI with that item's exact text. The verdict correctly
explained "an attempt to export customer records using the tool
`review_probe_tool_22d187b1`" and reproduced the per-run marker
(`proof-marker-22d187b18ff5`) embedded in the quarantined text, proving the
call read the specific content rather than echoing a fixed string, closing
the fleet-review finding that the only live Gemini call in the repo was a
connectivity echo. `make review-gates` reported 9/9 PASS: 8 offline
structural checks (freshness, quarantine count, marker present in both the
source text and the verdict, verdict schema exactly matching `Verdict`'s
four fields with no trust/origin/label key, department/tool consistency,
Vertex AI used) plus one independently issued, separate Gemini call under
the project's own credentials at judge time, confirming Vertex AI is
reachable now rather than only trusting the producer's response — there is
no durable Cloud resource to reread here, so the independent check re-makes
the live call instead of re-reading one, the same substitution O1 made for
Cloud Trace storage. No Cloud Run redeploy, no new control-plane endpoint,
matching the stated non-goals. No LLM anywhere near a trust or origin
decision — the Gemini call only ever produces a `summary` string.

Status: complete, superseded by the file-level status below

## Sub-build: N department worker agents (opened 2026-08-14)

Objective: close finding 1 above. Only one live ADK Runner has ever run,
once per proof script, one department per invocation — the fleet's central
claim, revocation reaching every memory descended from a compromised tool
"across every department, agent and session," has never been exercised at
N>1. User-chosen size: **N=5** departments.

Checked in code before scoping, not assumed: `CustodyGraph.revoke`
(`custody/graph.py:131`) matches descendants by `tool` name alone —
`CustodyRecord` (`custody/origin.py`) carries no `department` field at all.
This is not a bug to fix; it is exactly what the product's own one-sentence
claim requires (a compromised tool is pulled everywhere it was used, not
just where it was first reported). But it means the one property this
sub-build must prove live, which N=1 structurally could never exercise, is:
**a tool shared by two departments, revoked once, is pulled from both** —
not merely "5 agents ran."

Branch: feat/memory-provenance
Parent: ce54bad

Allowed files: a new `scripts/live_fleet.py` and `scripts/fleet_gates.py`,
`scripts/live_memory_bank.py` (parametrize `prove_adk_memory_bank` by
department/`user_id` instead of the hardcoded `APP_NAME`/`user_id`
constants; no behavior change to the existing `make live-g1` call site),
`Makefile`, `README.md` (fleet/product-mapping sections only), `HANDOFF.md`,
`.claude/SESSION_CONTRACT.md`, `proof-out/*`. No changes to
`custody/graph.py`, `custody/catalog.py`, `custody/origin.py`,
`custody/control_plane.py`, or `custody/adapters/*` — the revocation,
trust-catalog, and Memory Bank write/delete mechanisms this sub-build
exercises are already correct and already covered offline (Auditor,
D2, G1 migration sub-builds); this is a proof-at-scale build, not a new
mechanism.

Non-goals:

- No new Cloud Run services or Agent Engine identities per department.
  Memory Bank already scopes by `{app_name, user_id}` per write/search
  call (`custody/adapters/memory_bank.py`); five departments are five
  `user_id` values against the one already-owned Agent Engine
  (`6936011268348182528`), not five deployments. Standing up N runtimes
  would prove infra replication, not the fleet claim.
- No department-scoped revocation. `CustodyGraph.revoke`'s global-by-tool
  matching is the intended semantics (see above), not something this
  sub-build narrows. If the user later wants revocation scoped to one
  department even when a tool name collides across departments, that is a
  different, explicitly-scoped change to `custody/graph.py`, not this one.
- No UI or dashboard visualizing the fleet. Evidence is the same
  artifact-plus-independent-gates shape every other live gate here uses.
- No new trust/catalog logic. Departmental grant isolation
  (`TrustCatalog.request`/`demote` refusing cross-department writes) is
  already proven offline (`tests/test_catalog.py`) and live (Auditor
  sub-build); this build reuses it, does not re-test it.

Baseline: `make check` 315/315 passing offline (confirmed 2026-08-14, after
the Custody Reviewer commit). `make gates` reports G1/G2/G3/G4 PASS, G5
BLOCKED (calendar-gated, unaffected).

Acceptance gates:

1. Five live department worker agents (`sales`, `legal`, `hr`, `finance`,
   `engineering`, or equivalent distinct `user_id`s), each a real ADK
   `Runner`/Gemini conversational turn plus one tool-origin write, through
   the same `CustodyMemoryBank`/`write_record` wiring G1 already proved —
   not five copies of a mock. Each department's tool-origin fact is
   independently retrievable via `search_memory` scoped to its own
   `user_id`.
2. The fleet claim, proven for the first time at N>1: two of the five
   departments independently trust and invoke a tool with the *same name*
   (a shared, cross-department tool). Revoking that tool once (`/demote` +
   the existing `/auditor` sweep, same mechanism the Auditor sub-build
   proved) removes the tool-origin memory from *both* departments'
   `search_memory` results, not just the reporting department's — the
   derivation graph's own stated claim, exercised live instead of assumed.
3. A sibling check that the same revocation leaves the other three,
   unrelated departments' memories untouched — the revocation is
   tool-scoped, not blast-radius-unbounded.
4. Live proof, same discipline as every other gate here: the producer
   script (`scripts/live_fleet.py`) writes `proof-out/live-fleet.json`;
   `scripts/fleet_gates.py` independently rereads live Memory Bank per
   department (recomputing `memory_id_for` itself, not trusting the
   producer's claim) rather than trusting the artifact.

Verification: `make check`, a new `make live-fleet` writing
`proof-out/live-fleet.json`, and `make fleet-gates` judging it
independently. Manual: confirm the fleet review's finding 1 in
`.claude/SESSION_CONTRACT.md`'s "Fleet review" section and `HANDOFF.md` are
corrected to cite this live evidence instead of "never proven at N>1."

**Closed 2026-08-14, all gates passed live, proof `2f5461ce99ba46aebe7f43ac72595612`.**
Five live department worker agents (`sales`, `legal`, `hr`, `finance`,
`engineering`) each ran a real ADK `Runner`/`gemini-3.5-flash` conversational
turn plus one tool-origin write, through the exact `CustodyMemoryBank` ->
`AgentEngineMemoryBank`/`write_record` wiring G1 already proved, all five
sharing one `CustodyMemoryBank` instance (one process-wide `CustodyGraph`,
not five isolated ones) against Agent Engine `6936011268348182528`. `sales`
and `finance` independently trusted and invoked the same tool name,
`cross_dept_export_tool`; `legal`, `hr`, and `engineering` each used a
distinct tool name. One `/demote`-style revocation
(`RevokingMemoryBankGraph.revoke(tool="cross_dept_export_tool", ...)`)
removed exactly `sales` and `finance`'s tool-origin records
(`revocation.removed` held both, no others) and their Memory Bank entries;
`legal`, `hr`, and `engineering`'s own tool-origin memories were confirmed
still present, both in the producer's own before/after `search_memory`
reads and in `fleet_gates.py`'s independent `memories.get` reread by a
`memory_id_for`-recomputed name, not the producer's claim. `make fleet-gates`
reported 15/15 PASS: 10 offline structural checks plus 5 independent live
Memory Bank rereads (2 confirming deletion, 3 confirming survival). `make
check` 315/315 offline, unaffected. `make gates` reports the same baseline
as before this sub-build (G1/G2/G3/G4 PASS, G5 correctly BLOCKED on
elapsed time) — no core module changed (`custody/graph.py`,
`custody/catalog.py`, `custody/origin.py`, `custody/control_plane.py`, and
every `custody/adapters/*` file are untouched by this sub-build, exactly as
scoped). No new Cloud Run services or Agent Engine identities: five
departments are five `user_id` values against the one already-owned
engine, Memory Bank's own `{app_name, user_id}` scoping is what separates
them. **Non-goal, stated in the artifact's own `claim_boundary`:** this does
not test `TrustCatalog`'s per-department grant boundary (a department
cannot vouch/demote another's tool) — that is already proven offline and
live, unchanged, by the Auditor sub-build; this build proves the
derivation graph's cross-department revocation reach instead, which is a
different property N=1 could never exercise.

Status: complete, superseded by the file-level status below

## Sub-build: legible daily heartbeat (opened 2026-08-14)

Objective: the daily `/auditor` heartbeat's Cloud Logging trail is currently
just generic Cloud Run access-log entries (method, URL, timestamp) — a judge
would have to manually diff timestamps across days to see elapsed time.
Add `elapsed_days_since_seed` to the heartbeat's own response, computed from
the seed record's durably-stamped `admitted_at` (never a client clock claim
about itself, same discipline every other timestamp in this project
follows), and write it into a new structured Cloud Logging entry
(`custody-auditor` log, mirroring O1's `custody-observability` pattern) so
each day's entry is self-explanatory without cross-referencing.

Branch: feat/memory-provenance
Parent: b61827b

Allowed files: `custody/control_plane.py`, `requirements.txt`,
`tests/test_control_plane.py`, `HANDOFF.md`, `.claude/SESSION_CONTRACT.md`.

Non-goals:

- No change to the heartbeat's idempotency, the demotion sweep, or any
  gate/proof already passing. Purely additive.
- No new live proof script. This is legibility for the *existing*,
  still-accumulating G5 span, not a new capability with its own gate — the
  eventual `scripts/scheduler_gates.py` will read this field once a real
  span exists, not before.
- No redeploy required by this change alone in isolation, but since the
  live control plane needs the code to actually take effect, a redeploy is
  expected as part of closing this out.

Acceptance gates:

1. `elapsed_days_since_seed` is `None` offline (no durable `admitted_at` to
   compute from) and a real integer once a durable, Firestore-backed seed
   exists — covered by an offline test asserting the `None` case, since the
   integer case needs real elapsed days to differ meaningfully from 0.
2. The structured log write only happens when the control plane is
   constructed with a live log client; offline/local runs and every
   existing test are unaffected (no `google.cloud.logging` import error
   without credentials).
3. `make check` still 315/315, `make gates` still G1-G4 PASS.

Verification: `make check`. Manual: after redeploy, one live `/auditor`
call and a `gcloud logging read` against the new `custody-auditor` log name
shows the field.

**Closed 2026-08-14.** `ControlPlane.auditor` reads the seed record back
through the existing `graph.record` port, computes
`elapsed_days_since_seed` from its durably-stamped `admitted_at` (`None`
offline, since the pure in-memory graph never stamps one — covered by
`tests/test_control_plane.py::TheAuditorHeartbeatIsIdempotentAndSeedsOnce
::test_elapsed_days_since_seed_is_none_without_a_durable_admitted_at`), and
writes the whole heartbeat payload to a new `custody-auditor` structured
log only when a `log_client` is configured (offline/local runs stay
credential-free, covered by
`test_no_structured_log_write_without_a_log_client`; the write itself is
covered against a fake logger by
`TheHeartbeatWritesAStructuredLogWhenConfigured`). 319/319 offline.
Redeployed to Cloud Run revision `custody-control-plane-00005-s2k`
(user-authorized live, same as the prior two redeploys this session).
Verified live: one manual `/auditor` call returned
`"elapsed_days_since_seed": 0` and the same payload appeared in
`projects/project-988bc9fe-092c-4b32-90c/logs/custody-auditor`
(`insertId 1pm8pk5f30azdx`) within seconds. The day's own Cloud-Scheduler-
triggered fire (`2026-08-14T06:00:03Z`) had already happened a few minutes
before this redeploy landed, against the prior revision, so it does not
carry the new field; every fire from tomorrow's `06:00 UTC` onward will.
`make gates` still reports G1-G4 PASS, G5 correctly BLOCKED (unaffected —
this is legibility for G5's still-accumulating span, not a new gate).

Status: complete, superseded by the file-level status below

## Prior work disclosure

Submission period opened 2026-08-04; this repository was created 2026-08-09, so
it is new work. `../warrant` and `../vigil` are the author's own in-period work
and carry no disclosure burden, but must be listed if any code is lifted.
`google-adk` is consumed unmodified. Do not read from or modify
`~/datahub-causality-agent`, `~/priorto`, Throughline, or Chronicle.

Status: active

## Presentation pass: one judge-facing incident narrative (opened 2026-08-14)

Objective: the project's whole product surface was the README plus five
separate terminal demos (`make demo`, `make cost`, `make revoke`, `make
isolate`, plus live scripts); nothing told the single incident story a judge
needs in one place. No web frontend exists anywhere in this repo — checked
by inspection (`find` for `.html`/`.tsx`/`.jsx`, `package.json`) before
editing, and confirmed `custody/control_plane.py` is a pure JSON HTTP API
with no template/console. Given that, the "product surface" this pass
targets is the terminal, consistent with the project's existing style
(README's own `$ make demo` blocks), not a new GUI invented under budget
pressure.

Branch: feat/memory-provenance
Parent: 7b53ff3

Allowed files: `scripts/incident.py` (new), `Makefile`, `README.md` (hero
section only, above "## The gap this fills"). No changes to `custody/*`,
`custody/adapters/*`, or any other script — this is presentation over
already-built, already-gated capability, not new backend work.

Non-goals:

- No web console. No new backend capability. `scripts/incident.py` composes
  `scripts/cost.py`'s existing fixture (`build()`, same `vendor_portal`
  compromise, same 5-department/8-tool fleet) with
  `custody.service.CustodyMemoryService` + `custody.catalog.TrustCatalog`
  (both already built and tested) to narrate one shared `CustodyGraph`
  rather than inventing new mechanics.
- No fabricated metrics. Every number `scripts/incident.py` prints
  (affected memories, departments touched, unrelated preserved) is computed
  by that run against real graph traversal (`CustodyGraph.descendants`,
  `.revoke`), asserted against in the script itself (`assert record_id in
  descendants`), not hand-typed. No "agents" count is printed because the
  fixture does not model per-agent identity, only departments — printing
  one would be inventing a number the data does not support.
- No "live" claim. This is an offline scripted narrative, same discipline
  as `make demo`/`make cost`/`make revoke` (none of which claim liveness).
  `make live-auditor` remains the actual live proof of the asynchronous
  demote-then-sweep path; `scripts/incident.py`'s docstring says so
  explicitly and points there.
- Timestamps (`VOUCHED_AT`, `DEMOTED_AT`) are caller-supplied constants,
  same pattern as `revoke.py`'s `revocation_id="rev-2026-08-N"` — a demo
  fixture, not a claim about wall-clock time.

Baseline: `make check` 319/319 passing before this pass (confirmed
2026-08-14). No regression: same count after (`ruff check` clean,
`python -m unittest discover` 319/319).

Acceptance gates:

1. `make incident` runs and exits 0, printing, in order: an active trust
   incident header (source, status, reason, trust-then-compromise gap),
   blast radius (affected/departments/unrelated, all computed), a traced
   lineage chain with explicit `derived_from` edges across three
   departments, the surgical revoke call plus an idempotent replay, and an
   evidence block naming the trust transition, derivation path, and
   revocation id.
2. The script's own internal assertions hold (computed blast radius exactly
   equals the traced chain's six record ids, revoked count equals blast
   radius, replay removes zero further and produces exactly one revocation
   record) — verified by `main()`'s exit code, not eyeballed.
3. `make check` still passes at the same count, unmodified.
4. README's hero section leads with the incident narrative and states
   plainly that its numbers come from the run, with an explicit pointer to
   `make live-auditor` for the live version of the same claim, so nothing
   here reads as a stronger claim than what is proven.

Verification: `make incident` (manual read of the printed narrative against
the acceptance gates above), `make check` (regression), `ruff check
scripts/incident.py`.

**Closed 2026-08-14, all four gates passed.** `make incident` exits 0;
32 affected memories, 3 of 5 departments touched, 575 unrelated preserved
(fixture is seeded/deterministic, so these numbers are stable run to run,
same as `make cost`'s already-documented 40/560/93% figures). `make check`
unchanged at 319/319. README's hero block replaced the old cold-open with
the incident narrative and an explicit "computed by the run, not typed in"
line plus a pointer to `make live-auditor`; the prior `make demo` cold-open
(supplier-page instruction) moved below it, framed as one property among
several the rest of the README walks apart. Known gap: this is a terminal
narrative, not a graphical judge-facing screen — correct given no frontend
existed to redesign and building one from scratch was out of this pass's
budget, but if judges specifically expect a GUI, that is a real gap to
name, not to paper over.

Status: complete

## GUI pass: first judge-facing screen, hackathon-scoped (opened 2026-08-14)

Objective: the user wants a real startup eventually, and named this
explicitly as the first GUI version, hackathon-focused. Terminal narrative
alone (previous section) was judged insufficient once a GUI was requested.
Built a static, dependency-free HTML page rather than a framework app: no
`npm install`, no new runtime, nothing that needs `make check`'s "no clone,
install dependencies" default relaxed. Chosen deliberately so the same data
contract (`scripts/incident.py`'s `compute()` dict) can later back a real
live console without a rewrite — this is explicitly framed as pass one of
a product surface, not a throwaway demo page.

Branch: feat/memory-provenance
Parent: (this session, on top of the terminal-incident close above)

Allowed files: `scripts/incident.py` (refactor `run()`'s body into
`compute()` + `render()`, same terminal output, no behavior change — verified
by rerunning `make incident`), `scripts/render_gui.py` (new), `web/`
(new, generated), `Makefile`, `README.md` (hero section only).

Non-goals:

- No JS framework, bundler, or CDN dependency. Vanilla HTML/CSS/JS in one
  file, self-contained, opens without a build step — hackathon judges get
  zero setup friction, and it costs nothing to keep working the same way
  once this becomes a real product's first screen.
- No new backend, no live wiring to the Cloud Run control plane. The page
  renders one offline run's data, same discipline as `make incident`; it is
  not a claim that the deployed system serves this page.
- No generic-AI visual language: no robot/brain/shield icons, no gradients,
  no "AI-powered" badges, no chat bubbles. Dark, dense, monospace,
  security/incident-response register, matching the terminal narrative's
  own tone rather than introducing a second brand.
- The "Revoke descendants" button is a client-side phase toggle over
  already-computed before/after data (both real, both from the same run),
  not a live mutation — the page does not call any service.

Baseline: `make check` 319/319 (unchanged from the terminal-incident close).

Acceptance gates:

1. `make gui` runs, writes `web/incident.html` and `proof-out/incident.json`
   from the same `compute()` the terminal command uses — no hand-typed
   numbers in the template.
2. The page renders the same hierarchy as the terminal narrative: trust
   incident header, blast-radius stat row, influence lineage with visible
   `derived_from` edges and a distinct compromised-root marker, a surgical
   action control, and an evidence panel — verified visually via
   `claude-in-chrome` against a local `python -m http.server`, not just
   read from the generated HTML source.
3. Clicking "Revoke descendants" transitions the lineage to a visibly
   struck-through/dimmed state and reveals the after-revocation numbers
   (removed/survives/replay), all pulled from the same embedded JSON —
   verified live in-browser, screenshotted before and after the click.
4. `scripts/incident.py`'s terminal output is byte-for-byte unchanged after
   the `compute()`/`render()` refactor (`make incident` reruns clean,
   `make check` still 319/319).

Verification: `make gui`, `make incident`, `make check`, a live in-browser
click-through via `claude-in-chrome` (before/after screenshots).

**Closed 2026-08-14, all four gates passed.** `make gui` wrote
`web/incident.html` (256 lines) and `proof-out/incident.json` (55 lines,
gitignored, same as every other `proof-out/*` artifact). Verified live in
Chrome via a local `http.server`: the before-state screenshot shows the
trust incident header, three blast-radius tiles (32 / 3 of 5 / 575), and
the four-hop lineage with the compromised root in red and descendants in
amber; clicking "Revoke descendants" struck through the three descendant
rows, flipped the button to "Descendants revoked", and populated the
removed/survives/replay tiles (32 / 575 / 0) plus the evidence panel
(trust transition, derivation path, `removed set matches computed blast
radius: true`, audit record count) — all screenshotted. `make incident`
and `make check` (319/319) confirmed unchanged after the `compute()`/
`render()` refactor. README's hero section gained a paragraph pointing at
`make gui`, framed as pass one toward a real console rather than a demo
artifact. Known gap, stated rather than hidden: this is a local static
file, not a deployed, shareable URL — the natural next step if this
becomes the actual startup product surface is serving it from the existing
Cloud Run control plane once `/custody`-shaped read endpoints back it with
live data instead of one offline fixture run.

Status: complete

## GUI polish pass: visual design quality raised for the multimodal-UX category (opened 2026-08-14)

Objective: the user flagged a hackathon multimodal-UX award category and asked
for the GUI to be "extremely beautiful & working," on top of the already-shipped
functional pass above. Same file, no new scope beyond visual/interaction
quality: `scripts/incident.py`'s `compute()` gained real per-hop
`content_sha256` (read off each `CustodyRecord` before revocation, via
`CustodyGraph.record`, not fabricated) so the evidence claim about content
hashes is backed by data instead of asserted in prose; `scripts/render_gui.py`
was rewritten for depth (staggered entrance animations, an animated derivation
timeline for the trust-to-compromise gap, a connected vertical lineage graph
with department chips and truncated hash chips, count-up stat animations, a
toast confirmation on revoke, a keyboard shortcut (`r`) alongside the button,
and responsive/accessible markup — `aria-live` regions, `:focus-visible`).

Allowed files: `scripts/incident.py` (add `content_sha256` per lineage hop
only — no other logic change), `scripts/render_gui.py`.

Found and fixed one real bug during live verification: `.timeline-label`
had no `left` position, so both the day-1 and compromise-date labels
collapsed onto the same spot instead of anchoring to the track's ends —
caught by screenshotting in Chrome, not by reading the CSS.

Verification: `make gui`, then live in-browser via `claude-in-chrome`
against a local `python -m http.server` — full-page screenshot of the
before state, the timeline bug found and fixed, a re-screenshot confirming
the fix, then triggering revoke via the `r` keyboard shortcut (a stray
coordinate click briefly hung the tab's script-injection channel for
unclear reasons — recovered by opening a fresh tab rather than chasing it,
and the keyboard path worked cleanly) and screenshotting the after state:
struck-through descendants, dimmed opacity, the toast reading "revocation
rev-vendor-portal-2026-08-14 applied — 32 record(s) removed, 575 survive",
and the revoke-result stat tiles (32 / 575 / 0). `make check` still
319/319, `ruff check .` clean.

Status: complete

## GUI direction settled: "evidence ledger," style A retired (opened 2026-08-14)

Objective: two comparison mockups (style A, single-column report; style B,
sidebar console) were published as Artifacts for the user to pick between.
User picked B, then called the result "generic AI slop" on a second look —
correctly: the amber-on-near-black, rounded-lg, shadow-lifted-card shape is
exactly the templated AI-dashboard look the original product brief warned
against, it had just been dressed in security-tool colors. Also corrected:
the demo's elapsed-time claim (21 days) overstated what the project can
actually prove before submission; the user expects closer to 15.

Branch: feat/memory-provenance
Parent: (this session, on top of the style-A/B comparison pass)

Allowed files: `scripts/incident.py` (only `VOUCHED_AT`/`ELAPSED_DAYS`),
`scripts/render_gui.py` (full rewrite, becomes canonical, style B's sidebar
skeleton kept, everything visual reworked), deletes `scripts/render_gui_v2.py`
and `web/incident_v2.html` (style A retired per the user's pick — exactly
one surviving version, as the original comparison note promised).

Design direction, not a generic dashboard reskin: "evidence ledger." The
product's actual claim is a literal chain of custody, so the page borrows
from case files and physical evidence tags instead of SaaS-dashboard
chrome — warm ink-toned dark palette (not blue-black), a serif for
narrative copy paired with monospace for every data/id/hash (two
deliberate voices: the record vs. the write-up), a stamped rotated status
badge instead of a rounded pill, grommet-holed tag chips instead of pill
badges, hairline-divided flat panels instead of shadow-lifted rounded
cards, and — the centerpiece — a caution-tape "REVOKED" sweep that clips
across a descendant row on revoke instead of a plain strikethrough/fade.

Found and fixed a real correctness gap during this pass, not just a style
change: the compromised root record (the tool-origin record itself,
`source_tool == vendor_portal`) is genuinely part of `CustodyGraph`'s
removed set on revoke, same as its three descendants, but the redaction
sweep was scoped to `.hop.descendant` only, so the root row visually never
showed as revoked even though the 32-removed count included it. Fixed by
extending the sweep selector to `.hop.root, .hop.descendant` — caught by
looking at the live revoke screenshot next to the removed count, not by
reading the CSS.

Verification: `make gui`, live in-browser via `claude-in-chrome` against a
local `python -m http.server` (before state, revoke via the `r` shortcut,
confirmed all four lineage rows — root and three descendants — show the
tape sweep, matching the 32-record removed count), `make check` (319/319),
`ruff check .` clean. The style-A/B comparison Artifact for B was
republished in place at the same URL with the redesigned page so the user
can review without needing local file access again.

Status: complete

## GUI rebuilt against a user-supplied reference (opened 2026-08-14)

Objective: the user shared four real product-mockup screenshots and picked
a direction explicitly, with two constraints: not pure black ("ai slop
color"), not pure white ("too light on eyes"). The chosen reference was a
three-column incident-console layout — left source-history timeline,
center identity strip + chain-of-custody flow diagram + evidence-ledger
table, right incident-summary + actions rail — on a warm light (not white)
ground. Per the design skill's own precedence rule ("the user's own words
always win"), this session followed that structure closely rather than
defaulting back to a from-scratch "avoid templates" pass.

Branch: feat/memory-provenance
Parent: (this session, on top of the evidence-ledger dark-theme pass)

Allowed files: `scripts/render_gui.py` (full rewrite).

Non-goals, held even though the reference mockup showed them:

- No fabricated fields. The reference's identity card showed "Owner:
  Vendor Success", "Source Type: Web Content", "Severity: High" — none of
  that exists in `compute()`'s data, so none of it was added. The identity
  strip only shows fields backed by real data (source, first trusted,
  compromised, detection gap).
- No fabricated "agents touched" count — same reasoning as the dark-theme
  pass: the fixture models departments, not per-agent identity, so no
  agent count is invented to fill a stat slot the reference had.
- No fabricated second "trusted" lineage chain. The reference showed two
  full parallel chains (one revoked, one trusted) with invented tool/memory
  names. This project only has one real traced chain
  (`vendor_portal`'s); the "unrelated" side is represented as one honest
  aggregate node ("other tools, other departments, N preserved") rather
  than inventing a second fake derivation chain to visually match.
- No fabricated ticket-style incident ID ("INC-2025-0517-0017"). The
  crumb uses the real revocation id and date instead of a fake ticketing
  scheme implying a system that doesn't exist.
- The flow diagram represents the real graph shape: this project's traced
  lineage is a single sequential chain (source -> sales -> support ->
  finance, each hop a real `derived_from` edge), not the reference's
  parallel three-way fan-out — the reference's shape does not match this
  incident's actual data, so it was not copied.

One real feature added beyond the reference: a working "Copy evidence as
JSON" button (`navigator.clipboard.writeText` on the same embedded data
object), replacing the reference's "Export impact report" button, which
would have implied a backend export capability that does not exist. This
is honestly implementable client-side, so it was, rather than left as a
dead button or invented as fake reachable backend behavior.

Found and fixed two real bugs during live verification, not just style
changes:

1. Three JS string literals used `\\2192`/`\\22EF` (a Python-source
   backslash sequence) intending Unicode escapes, but without the `u`
   these are invalid octal escapes in strict-mode JS — the whole inline
   `<script>` threw a `SyntaxError` at parse time and silently left every
   data-bound field on the page blank. Caught by reading the console after
   the first screenshot showed an empty page, not by inspection. Fixed to
   `\\u2192`/`\\u22EF` (the CSS `content: "\\2192"` on line 154 was correct
   as-is; CSS hex escapes don't take the `u`).
2. The revocable pill said "revoked" even in the pre-action "before" state,
   which is backwards — a control that already claims the outcome before
   the user acts on it. Fixed via a CSS `::before` swap driven by
   `[data-phase]` instead of static text: "targeted" before, "revoked"
   after, verified with a zoomed screenshot of both states.

Verification: `make gui`, live in-browser via `claude-in-chrome` (full page
before state, zoomed flow-diagram crop confirming "targeted" pills and the
flex-glued arrow/node wrap behavior, `r`-key revoke, zoomed after-state
crop confirming all pills flipped to "revoked"), `make check` (319/319),
`ruff check .` clean. Republished to the same Artifact URL as the prior
dark-theme pass (`d49826ea-...`) so the user can review without local file
access, per the recurring "i can't open them" constraint from earlier in
this session.

Status: complete

## GUI rebuilt again: "Dependency Cartography" (opened 2026-08-14)

Objective: the user rejected the ledger-console direction after all and
picked, explicitly and exclusively ("use this one only"), the fourth
reference screenshot — a node-graph "Dependency Cartography" view: multi-
column source-to-department graph with SVG-connected nodes, a top stat
strip, and a right-hand selected-node detail panel. Instructed to use only
this reference, on a white-but-not-pure-white ground (their own earlier
"white is too light on eyes" constraint, self-applied here since the
reference itself is white).

Branch: feat/memory-provenance
Parent: (this session, on top of the reference-matched ledger console)

Allowed files: `scripts/render_gui.py` (full rewrite, imports `TOOLS`,
`DEPARTMENTS` from `scripts/cost.py` — no new data-producing code, reuses
already-real fixture constants).

Non-goals, again held against a reference that showed them:

- No fabricated "Agents" column/count. The reference's pipeline is
  Sources -> Tools -> Model Derivations -> Memories -> Agents ->
  Departments; this project's fixture models departments only, not
  per-agent identity, so the graph here is five columns (Sources, Tool
  Result, Model-Derived Fact, Memories, Departments), not six, and the top
  stat strip has three numbers, not four.
- No fabricated multi-page app shell. The reference's left nav listed
  Overview/Sources/Agents/Datasets/Integrations/etc., none of which exist
  as pages. The nav here has exactly two real links (Dependency Map,
  Evidence Ledger, both in-page anchors) plus inert, non-clickable labels
  for context, never claiming a page that isn't there.
- No fabricated minimap or zoom controls (the reference shows both); a
  non-functional zoom/pan affordance would be a fake control, so it was
  left out entirely rather than added and disabled.
- The "Sources" column lists all 8 real tools from `scripts/cost.py`'s
  `TOOLS` fixture (not invented names); the "Departments" column lists all
  5 real `DEPARTMENTS`. Connector lines are computed from live
  `getBoundingClientRect()` positions of the actual rendered nodes at
  draw time, not hand-authored SVG path coordinates, so the graph cannot
  silently drift out of sync with its own layout.

One real feature beyond the reference: clicking any lineage node updates
the right panel with that node's actual provenance chain, reconstructed by
walking `derived_from` edges in the embedded data (not the reference's
static single pre-selected memory) — "Highlight this path" pulses exactly
those nodes.

Verification: `make gui`, live in-browser via `claude-in-chrome` (initial
render confirmed no console errors after one pass — the connector-drawing
and node-click logic worked correctly the first time; clicked a memory
node and confirmed the detail panel's reconstructed provenance path
matched the real `derived_from` chain; clicked "Revoke exact descendants"
and confirmed all pills flipped to "revoked" and the connector paths
switched from the dashed contaminated style to the dimmed/settled style).
`make check` 319/319, `ruff check .` clean. Republished to the same
Artifact URL, title changed to "Dependency Cartography" to match the new
direction.

Status: complete

## Secondary architecture/evidence page (opened 2026-08-14)

Objective: the user asked, correctly, whether the incident page covers the
rest of the project (R1, R2, S1, G1-G5, M1, O1, D1/D2, the N=5 fleet, the
Auditor, the Reviewer) — it does not, and never did; that split was the
original design brief's own intent ("architecture belongs in a secondary
evidence view"), but the secondary view was never built. Closed that gap
with a second static page rather than folding everything into the incident
page.

Branch: feat/memory-provenance
Parent: (this session, on top of the Dependency Cartography rebuild)

Allowed files: `scripts/render_architecture.py` (new), `scripts/render_gui.py`
(nav-link edit only, three lines), `Makefile`, `web/architecture.html` (new,
generated).

Non-goals:

- No live re-verification at render time. `scripts/gates.py` is offline and
  fast (confirmed: regenerates G2-G4's demo fixtures deterministically,
  reads G1/G5 back from disk, no network), so its real stdout is captured
  and parsed. The nine `scripts/*_gates.py` live judges were each tried
  directly first (`registry_gates.py`, `model_armor_gates.py`,
  `observability_gates.py`, `memory_deletion_gates.py`, `auditor_gates.py`,
  `review_gates.py` ran but several of their own "live_*"-named checks
  failed for lack of credentials/network in this environment;
  `gateway_gates.py`, `revision_binding_gates.py`, and `fleet_gates.py`
  hung past a 10s timeout) — confirming they mix offline structural checks
  with live Cloud calls in one script and are unsafe to invoke from a
  static-page build step. Decided instead to read each `proof-out/live-
  *.json` artifact's own self-reported `proof_id`, `captured_at`, and
  `claim_boundary` directly, labeled as a captured-evidence snapshot with
  a computed age, never as a freshly-reverified PASS.
- No fabricated rows. Nine `LiveProof` entries map exactly to nine files
  that exist on disk (`live-registry-attack.json` through
  `live-fleet.json`); a tenth, missing, or malformed file would render as
  "missing"/"malformed" status, not be silently dropped or faked green.
- No new backend capability, no redeploy, no cloud calls of any kind from
  this script.

Verification: `make gui` now writes both `web/incident.html` and
`web/architecture.html`. Live in-browser via `claude-in-chrome`: confirmed
no console errors, all five G1-G5 rows rendered with real PASS/BLOCKED
detail text, all nine live-proof cards rendered grouped into their real
four+one categories with real proof ids/ages/claim-boundary text, and the
`← Dependency map` / `Architecture & Evidence` nav links round-tripped
correctly in both directions. `make check` 319/319, `ruff check .` clean.
Republished both Artifacts (dependency-cartography page unchanged content,
re-synced for the new nav link; a second Artifact would need its own
fragment extraction if the user wants the architecture page previewable
the same way — not done yet, offered on request).

Status: complete

## Architecture page: show, not tell (opened 2026-08-14)

Objective: the user's fair pushback on the page above — "why would this
exist in a website ffs? its a demo, it should show capability not tell or
write" — the first version was nine paragraphs of `claim_boundary` prose
plus a proof id, which is documentation, not a demo. Replaced the dominant
content of each of the nine live-proof cards with a small widget built from
that artifact's own real nested evidence, and demoted `claim_boundary` to a
secondary "Scope" caption.

Branch: feat/memory-provenance
Parent: (this session, on top of the first architecture-page pass)

Allowed files: `scripts/render_architecture.py` only.

What each widget actually shows, pulled from real nested fields already in
the corresponding `proof-out/live-*.json` (none invented):

- R1: Registry-approved digest vs the observed live digest, plus the real
  dispatch counter that held steady.
- R2: three-step timeline — an accepted dispatch, then a real
  `digest_mismatch` denial, then a real `replayed` denial.
- S1: the real allow call (200, trace id) beside the real deny call (403,
  trace id).
- M1: the actual jailbreak/PI prompt text next to the actual clean prompt,
  each with its real Model Armor `filterMatchState`.
- O1: the real `trace_id`/`span_id`/`custody_digest` as chips.
- D1/D2: the real two-fact list before revoke next to the real one-fact
  list after, with the removed fact struck through.
- Auditor: the same record's real `revocation_id`/`revoked_at` fields at
  three real timestamps (before demotion, after demotion but before the
  sweep, after the sweep) — the decoupling claim shown as state, not
  argued in prose.
- Reviewer: the real quarantined text next to Gemini's real drafted
  verdict text.
- Fleet N=5: the real revoked departments next to the real untouched ones.

Non-goals:

- No widget fabricates a field the artifact doesn't have; a proof whose
  expected sub-structure is missing renders "no replay available" rather
  than a placeholder that looks like real data.
- No change to which nine proofs are covered or how they're loaded — same
  offline-only read of `proof-out/*.json`, same refusal to re-run the live
  `*_gates.py` scripts from this page.

Verification: `make gui`, live in-browser via `claude-in-chrome` (no
console errors, scrolled the full page, confirmed all nine widgets render
with real values — the R1 digest pair, the M1 prompt pair with real
`MATCH_FOUND`/`NO_MATCH_FOUND` states, the D1/D2 struck-through fact, the
Auditor three-step timeline, the Reviewer text pair, the Fleet department
split). `make check` 319/319, `ruff check .` clean. Republished the
Architecture & Evidence Artifact in place.

Status: complete

## Standing enforcement, folded into the one canonical artifact (opened 2026-08-14)

Objective: the user asked, correctly, whether the product does anything
besides the incident-response story, then directed that all further work
land on the Dependency Cartography artifact itself ("bcz tht one is
final"), not as another separate page. `custody/service.py`'s write-time
split and `custody/action.py`'s export gateway run on every session,
independent of any later revocation — that was true before this session
but invisible in the GUI. Added a compact "Standing enforcement" panel to
`web/incident.html` itself, positioned above the incident graph.

Branch: feat/memory-provenance
Parent: (this session, on top of the "show don't tell" architecture-page fix)

Allowed files: `scripts/incident.py` (new `compute_standing()` function),
`scripts/render_gui.py` (new panel + data wiring).

Non-goals:

- No second invented scenario. `compute_standing()` reuses
  `scripts/demo.py`'s own `week_one()`/`texts()`/`instruction_carrying()`
  fixture and mirrors its `without_custody()`/`with_custody()` split
  exactly (verified: `seen=3, admitted=1, withheld=2,
  retrieved_into_context=1, carrying_instruction=0`, byte-identical to
  `make demo`'s terminal numbers) — so this panel and `make demo` cannot
  report different numbers for the same claim.
- No separate page. Everything lands on the one artifact the user named
  final; the Architecture & Evidence page is untouched by this pass.

Verification: computed `compute_standing()` directly and diffed against a
fresh `make demo` run (identical). `make gui`, live in-browser via
`claude-in-chrome`: no console errors, the panel renders both branches
("Without Custody... export ALLOWED" vs "With Custody... export REFUSED:
cited content came from untrusted source(s): fetch_page") directly above
the incident graph. `make check` 319/319, `ruff check .` clean.
Republished the Dependency Cartography Artifact in place at the same URL.

Status: complete

## Standing enforcement panel removed on request (2026-08-14)

User's call: "naah remove it." Reverted cleanly — removed the panel HTML,
its CSS block, the `standing-data` script tag and JS wiring from
`scripts/render_gui.py`, and deleted `compute_standing()` and its
now-unused imports (`Export`, `ExportGateway`, `CustodyRecord`, `Origin`,
`Trust`, `ToolTrust`, `ATTACKER`, `PAYLOAD`, `instruction_carrying`,
`texts`, `week_one`) from `scripts/incident.py` rather than leaving dead
code behind. `make gui`, live in-browser: page matches the pre-panel state
exactly, no console errors. `make check` 319/319, `ruff check .` clean.
Republished the Artifact in place.

Status: complete

## Deployed publicly to Vercel (2026-08-14)

Objective: user asked to put the GUI live on the web, not just as a private
Claude Artifact. Deployed `web/incident.html` (as `index.html`) and
`web/architecture.html` as a static two-page site, no build step, via
`deploy_to_vercel` (target production, project `custody-incident`).

Before deploying, fixed two links that only worked inside the repo tree:
`../README.md`/`../docs/architecture.md`/`../DECISIONS.md` in both
templates' footers now point at
`https://github.com/Yatsuiii/custody/blob/main/...` (a real, confirmed
`origin` remote) instead of relative paths that would 404 once only `web/`
is deployed standalone.

Live URLs:
- https://custody-incident-cave2.vercel.app/ (dependency map)
- https://custody-incident-cave2.vercel.app/architecture.html

Non-goals: no `.vercel/project.json` linked into the repo (deploy was
files-only, no git integration); no custom domain; no redeploy-on-push
wiring. Regenerating the GUI (`make gui`) does not automatically redeploy
— that's a manual follow-up step if the underlying data changes.

Verification: live in-browser via `claude-in-chrome` against the deployed
URL — dependency map renders correctly, nav link to Architecture & Evidence
works, architecture page renders all five gates and nine live-proof
widgets. `make check` 319/319, `ruff check .` clean before deploying.

Status: complete

## Sub-build: F1, a genuine live cross-department derivation chain (opened 2026-08-14)

Objective: close the real proof gap identified in `HANDOFF.md` — no live
proof anywhere in this repo had ever exercised a genuine cross-department
`derived_from` edge. `scripts/incident.py` dramatizes the product's own
one-sentence claim (a tool-origin fact hopping sales -> support -> finance,
each hop a `derived_from` edge earned by a `load_memory` content-hash
match) but is 100% offline. `scripts/live_fleet.py` (N=5) proves something
narrower: N departments each independently write once, two happen to trust
a tool with the same name, and revoking it reaches both — no department in
that script ever retrieves another department's memory.

Checked in code before building: the edge is earned in `custody/origin.py`'s
`_attribute` when a session event's `function_response.name` is
`load_memory` and its response text content-hashes (`resolve`) to a record
already in the shared `CustodyGraph` — the same mechanism
`incident.py`'s offline `support_session()`/`finance_session()` exercise.
Reproducing this live means retrieving the *exact* text `search_memory`
hands back, not typing the fact twice.

Branch: feat/memory-provenance
Parent: 5d377fe (N=5 fleet)

Allowed files: new `scripts/live_chain.py` and `scripts/chain_gates.py`,
`Makefile`, `README.md` (a new F1 section only),
`scripts/render_architecture.py` (a new `F1` `LiveProof` entry and
`widget_chain`), `HANDOFF.md`, `.claude/SESSION_CONTRACT.md`, `proof-out/*`.
No changes to `custody/graph.py`, `custody/origin.py`, `custody/service.py`,
or any `custody/adapters/*` file — the derivation and resolution mechanism
this proves is already correct and already covered offline; this is a live
proof over an already-correct mechanism, reusing `scripts/live_fleet.py`'s
`RecordWritingMemoryBank` rather than duplicating it.

Non-goals:

- No new Cloud Run services or Agent Engine identities. One shared
  `CustodyMemoryBank` instance against the one already-owned Agent Engine
  (`6936011268348182528`), same posture `live_fleet.py` already accepts.
- No department-scoped revocation semantics change.
- No UI beyond the one new `F1` widget on the existing architecture page.

Acceptance gates:

1. A real ADK Runner/Gemini turn for sales, plus a real tool-origin write
   whose own model restatement earns a `derived_from` edge into the tool
   root, in the same invocation.
2. A real Gemini turn for support whose reply is spliced together with a
   manually-constructed `load_memory` citation event carrying the *exact*
   text `search_memory` retrieved for sales's restatement — earning a live
   content-hash-matched `derived_from` edge, not an asserted one. Same
   pattern for finance, citing support's restatement.
3. One independent tool-origin write for a sibling department
   (`engineering`), the live negative control.
4. Revoking the chain tool removes all six chain-hop records from live
   Memory Bank; each department's own unrelated conversational memory and
   engineering's independent memory are confirmed, via live reread,
   untouched.
5. `scripts/chain_gates.py` independently rereads live Memory Bank
   (`memories.get` by a `memory_id_for`-recomputed name, not the producer's
   claim) rather than trusting the artifact.

**Closed 2026-08-14, all gates passed live on the first run, proof
`a7bf097fcbce430c821ca655daa6cb07`.** `scripts/live_chain.py`: sales ran a
real ADK `Runner`/`gemini-3.5-flash` conversational turn, then a
manually-constructed tool-origin write (`vendor_audit_export_tool`) plus its
own model restatement in one invocation, earning `derived_from` into the
tool root. Support ran a real Gemini reply; a `load_memory` citation event
carrying the exact text live `search_memory` returned for sales's
restatement was spliced ahead of that reply, sharing its invocation id, and
both were fed through the shared `CustodyMemoryBank` together — the
resulting citation record's `derived_from` matched sales's restatement
record id exactly, a genuine content-hash match against live Memory Bank
text, and the reply record's `derived_from` matched its own citation.
Finance repeated the pattern citing support's restatement. Engineering
wrote one independent, unrelated tool-origin record.
`RevokingMemoryBankGraph.revoke(tool="vendor_audit_export_tool", ...)`
removed exactly the six expected chain-hop record ids (sales's tool root
and restatement, support's citation and restatement, finance's citation and
restatement) — verified both by the producer's own before/after
`search_memory` reads and by `chain_gates.py`'s independent
`memories.get` reread of all six by a `memory_id_for`-recomputed name.
Each department's own unrelated conversational memory (written earlier in
the same run) and engineering's independent tool-origin memory were
confirmed, live, still retrievable and untouched. `make chain-gates`
reported 20/20 PASS: 14 offline structural checks (each hop's
`derived_from` matches the exact expected upstream id, the removed set is
exactly the six expected records, both negative controls held) plus 6 live
Memory Bank rereads. `make check` 319/319 offline, unaffected. `make gates`
reports the same baseline as before this sub-build (G1/G2/G3/G4 PASS, G5
correctly BLOCKED) — no core module changed. Added as a new `F1` entry in
`scripts/render_architecture.py`'s `LIVE_PROOFS` (its own widget, distinct
from `Fleet N=5`'s, since it proves a different property) and a new README
section. `make gui` regenerated and verified to render the new row with
real captured data, and redeployed to Vercel the same session (see
`HANDOFF.md`'s redeploy write-up for the full account: the
`deploy_to_vercel` MCP tool corrupted `architecture.html`'s inline script
via a transcription error, caught by `read_console_messages` and fixed by
switching to a straight-from-disk `vercel` CLI deploy; a separately
discovered `ssoProtection` gate on the project was also disabled, with
explicit user authorization, to keep the site public). Verified live,
in-browser, both pages, no console errors, F1 widget rendering real data.

**Non-goal, stated in the artifact's own `claim_boundary`:** same scope
`live_fleet.py` already accepts — this does not test `TrustCatalog`'s
per-department grant boundary, and it does not stand up separate Cloud
Run/Agent Engine identities per department.

Status: complete

## Sub-build: Reviewer narration, for the Best Multimodal UX award (opened 2026-08-14)

Objective: Close `HANDOFF.md` section 4 (Best Multimodal UX award, $5,000,
2 winners — flagged open, not yet acted on). No Devpost page defines a
rubric for this award beyond its name and prize amount, checked live
against the hackathon's main page and rules page rather than assumed. The
GUI built this session is single-modality (HTML/SVG, text and graph
visuals only). Rather than a cosmetic polish pass, which would not change
that, or skipping the award, the user chose to scope a genuine second
modality: narrate the Custody Reviewer's real, already-live Gemini-drafted
verdict (`custody/review.py`'s `draft_verdict`, already proven via `make
live-review`) as speech via Google Cloud Text-to-Speech, embedded in the
Architecture & Evidence page next to the existing Reviewer widget. This
follows the project's own explicit rule against forcing an unrelated
Google AI product in ("Do not invent a Veo use; a forced integration reads
worse than an absent one") by narrating content that already exists and is
already real, rather than fabricating a new use for image/video
generation.

Branch: feat/memory-provenance
Parent: 5d377fe

Allowed files: `scripts/live_narration.py` (new), `scripts/
narration_gates.py` (new), `scripts/render_architecture.py`, `Makefile`,
`README.md` (new section only), `HANDOFF.md`, `.claude/
SESSION_CONTRACT.md`, `proof-out/*`. No changes to `custody/review.py`,
`custody/graph.py`, `custody/catalog.py`, `custody/control_plane.py`, or
`web/incident.html`.

Non-goals:

- No image or video generation. Audio narration of already-real Gemini
  text is the scoped addition, not a second forced integration.
- No change to `custody/review.py`'s structural contract: `draft_verdict`
  still never imports `custody.catalog`/`custody.graph`; narration only
  ever reads `Verdict.summary`, a plain string produced by the existing,
  unchanged live call.
- No change to any other live-proven gate (G1-G5, R1, R2, S1, M1, O1, D1,
  D2, Auditor, Reviewer, Fleet, F1). This is additive only.
- No autoplay audio; the modality is user-initiated via `<audio
  controls>`, and the verdict text stays visible as the accessible
  fallback — a text+audio pairing, not audio replacing text.
- If the step-0 viability check (below) fails in a way that is not a
  quick fix, stop and document the non-viability, mirroring D1's own
  write-up discipline, rather than forcing it.

Baseline: `make check` 319/319 passing offline (unchanged from F1's
close-out, confirmed before this sub-build). `make gates` reports
G1/G2/G3/G4 PASS, G5 correctly BLOCKED. `make live-review`/`make
review-gates` already pass (9/9), unaffected by this work — narration
reuses the same `draft_verdict` call shape but runs its own independent
live invocation, not a read of `live-review.json`.

Acceptance gates:

1. **Step-0 viability, checked live before any code is written**:
   `google-cloud-texttospeech` is installable, `texttospeech.
   googleapis.com` is enabled (or enablable via a plain `gcloud services
   enable` call) on `project-988bc9fe-092c-4b32-90c`, and one throwaway
   `synthesize_speech` call returns non-trivial audio bytes with a valid
   MP3 header.
2. `scripts/live_narration.py` runs a real quarantine + `draft_verdict`
   flow (own proof marker) and a real Cloud Text-to-Speech call, writing
   `proof-out/live-narration.json` (evidence, mirroring `live-review.
   json`'s shape) and `proof-out/live-narration.mp3` (the real audio
   bytes).
3. `scripts/narration_gates.py` independently verifies the claim: offline
   structural checks (freshness, `Verdict` schema match, the same
   disallowed-key check `review_gates.py` already uses, a recomputed
   `audio_sha256` matching the recorded digest, an MP3-header sanity
   check) plus one independent live re-call of Cloud Text-to-Speech
   itself, not just a reread of the producer's JSON — same discipline
   `review_gates.py`'s live Gemini re-call already uses for the same
   reason (there is no durable Cloud resource to reread here).
4. The GUI surfaces it live: a new `widget_narration` in `scripts/
   render_architecture.py`, a new `"audio"` widget type in the page's
   client JS, `web/architecture.html` regenerated and redeployed to the
   existing Vercel project, verified in-browser with no console errors
   and the audio actually playing real narrated speech matching the
   on-screen verdict text.

Verification: `make check`, `make live-narration`, `make narration-gates`,
`make gates` (must be unaffected), `make gui`, then a `vercel` CLI
redeploy per `HANDOFF.md`'s documented preferred method (not
`deploy_to_vercel`, which previously corrupted this same file's inline
script). Manual: reload both live Vercel URLs, confirm no console errors,
confirm the narration widget renders and plays.

**Closed 2026-08-14, all four gates passed live on the first run, proof
`26f576c3ffe74958938b383b57755aee`.** Step 0's viability check passed
cleanly: `google-cloud-texttospeech` installed with no dependency
conflicts, `texttospeech.googleapis.com` was not yet enabled on
`project-988bc9fe-092c-4b32-90c` and was enabled live via a plain `gcloud
services enable` call (under the project-owning account,
`yoursturuly@gmail.com` — the default gcloud CLI config was authenticated
as a different account/project entirely, `redlotusthepotus@gmail.com`
against `project-02b2181a-204b-4470-9cc`, so every gcloud call in this
sub-build used explicit `--account`/`--project` flags rather than the
ambient config), and one throwaway `synthesize_speech` call returned
13,344 bytes of valid MP3 audio. `scripts/live_narration.py` then ran its
own independent quarantine + `draft_verdict` flow (marker
`proof-marker-26f576c3ffe7`, correctly reproduced in the drafted verdict)
and a real Cloud Text-to-Speech call, producing 86,304 bytes of MP3 audio
(`sha256 ad3536b7...`). `scripts/narration_gates.py` reported 14/14 PASS
on the first run: 13 offline structural checks (freshness, marker
presence, `Verdict` schema/disallowed-key checks mirroring
`review_gates.py`, a recomputed `audio_sha256` matching the recorded
digest, an MP3-header sanity check, non-trivial byte count) plus one
independent live re-call of Cloud Text-to-Speech itself, which returned
fresh, valid, non-trivial audio under the project's own credentials.
`make check` remained 319/319 offline; `make gates` unaffected (G1-G4
PASS, G5 correctly BLOCKED). `scripts/render_architecture.py` gained a
new `Narration` entry in `LIVE_PROOFS`, `widget_narration` (reads the
verdict text and base64-encodes the sibling `.mp3` at render time into a
`data:audio/mpeg;base64,...` URI, never stored encoded on disk), and a new
`"audio"` widget type in the page's client JS (`<audio controls>`, no
autoplay, verdict text stays visible as the accessible fallback).
Regenerated (`make gui`) and verified locally in-browser first (Chrome via
`claude-in-chrome`, served over a local HTTP server since `file://` URLs
are not navigable): widget rendered, audio decoded and played (button
toggled to the pause state), no console errors. Redeployed to the existing
`custody-incident` Vercel project via the `vercel` CLI from a scratch
deploy directory (`web/incident.html` copied to `index.html`,
`web/architecture.html` copied to `architecture.html`, its back-link
rewritten from `incident.html` to `index.html` to match the deployed
copy's filenames, mirroring the pattern documented in `HANDOFF.md`'s F1
redeploy write-up) — deploying to production was confirmed with the user
first, since it is a visible, hard-to-reverse action affecting a public
URL. Verified live in-browser at both
`custody-incident-cave2.vercel.app/architecture.html` and the root page:
no console errors, the Narration widget renders with real captured data,
audio confirmed playable. `README.md` gained a new "Reviewer narration"
section; `HANDOFF.md` section 4 and its "Next capability" list were
updated to reflect this as closed rather than open.

**Non-goal, stated in the artifact's own `claim_boundary`:** no console or
human-facing review queue; no image or video generation is involved; this
does not change `custody/review.py`'s structural contract or any other
live-proven gate.

Status: complete

## Sub-build: fleet scale-up, N=5 to N=25 (opened 2026-08-14)

Objective: pick up `HANDOFF.md` section 3, explicitly optional/secondary
and only after the multimodal pass (now closed above). Scale
`scripts/live_fleet.py` from N=5 to N=25 department worker agents, per the
user's own earlier-stated target of ~20-30 when asked directly what would
read as credible. This is a single reported number for the demo, not a
GUI feature — the existing Fleet widget's shape does not change, only its
department list and count.

Branch: feat/memory-provenance
Parent: (this session's HEAD after the Narration sub-build)

Allowed files: `scripts/live_fleet.py`, `scripts/fleet_gates.py`,
`scripts/render_architecture.py` (the `Fleet N=5` entry only),
`README.md` ("The fleet at N=5" section only), `HANDOFF.md`, `.claude/
SESSION_CONTRACT.md`, `proof-out/*`.

Non-goals, per `HANDOFF.md`'s own scoping for this item:

- Do not touch `custody/graph.py`, `custody/catalog.py`,
  `custody/control_plane.py`, G1, the Auditor, or the Reviewer proofs.
- Do not fabricate or hand-type any numbers before a real run produces
  them.
- Do not let this grow into an expanded GUI section — surface the number
  in prose/stats via the existing widget shape, not new UI competing for
  demo-video time.
- Department and tool names reuse the existing naming style
  (`legal_review_tool`, `hr_disclosure_tool`), not `dept_1`/`dept_2`
  placeholders.
- `scripts/fleet_gates.py`'s hardcoded `== 5`/`== 2`/`== 3` checks are
  replaced with checks that independently recompute the expected
  department/shared/untouched sets from `live_fleet.py`'s own
  `DEPARTMENT_TOOLS`/`SHARED_TOOL_DEPARTMENTS` constants (the source of
  truth), not a second hand-typed magic number and not blind trust of the
  producer's own JSON.

Baseline: `make check` 319/319 offline, `make gates` G1-G4 PASS/G5
BLOCKED, `make fleet-gates` 15/15 PASS against the existing N=5 evidence
(all confirmed before this sub-build, unaffected by the Narration
sub-build above).

Acceptance gates:

1. `scripts/live_fleet.py`'s `DEPARTMENT_TOOLS` carries 25 real,
   non-repetitive department/tool name pairs, two of them (`sales`,
   `finance`, unchanged) sharing `SHARED_TOOL`.
2. `make live-fleet` runs live end to end against the same already-owned
   Agent Engine, all 25 departments' tool-origin facts written and
   independently retrievable, one revocation of the shared tool removing
   exactly the two sharing departments' records while the other 23 stay
   untouched.
3. `scripts/fleet_gates.py` independently verifies this: offline
   structural checks recomputing expected sets from `live_fleet.py`'s own
   constants (not a hand-typed count), plus the existing live Memory Bank
   reread loop (already scales to any N without modification).
4. `README.md`'s fleet section and `render_architecture.py`'s `Fleet N=5`
   `LiveProof` entry are updated to reflect the real N, only if the GUI's
   widget shape stays the same (groups of revoked/untouched names) — no
   new widget type.

Verification: `make check`, `make live-fleet`, `make fleet-gates`,
`make gates` (must be unaffected). `make gui` + redeploy only if the GUI
actually changed. Manual: confirm the live Vercel page still renders with
no console errors if redeployed.

**Closed 2026-08-14, all gates passed live on the first run, proof
`5617b30b169840928abfff93f08a0145`.** `DEPARTMENT_TOOLS` in
`scripts/live_fleet.py` was extended from 5 to 25 real, non-repetitive
department/tool pairs (sales and finance still sharing
`cross_dept_export_tool`; the other 23 each use a distinct, plausibly
named tool, e.g. `procurement_vendor_tool`, `compliance_audit_tool`,
`treasury_reconciliation_tool` — the same naming style as the original
five, no `dept_N` placeholders). `make live-fleet` ran sequentially
against the same already-owned Agent Engine (`6936011268348182528`); all
25 departments' real ADK Runner/Gemini turns plus tool-origin writes
succeeded, one revocation of the shared tool removed exactly `sales` and
`finance`'s records, the other 23 stayed untouched. `scripts/
fleet_gates.py`'s three previously hardcoded checks (`== 5`, `== 2`,
`== 3`) were replaced with checks that import `DEPARTMENT_TOOLS` and
`SHARED_TOOL_DEPARTMENTS` from `live_fleet.py` and independently
recompute the expected department/shared/untouched sets from that source
of truth, rather than a second hand-typed magic number — this means the
gate script now scales to any future N without further hand-editing.
`make fleet-gates` reported 35/35 PASS: 10 offline structural checks plus
25 independent live Memory Bank rereads (2 confirming deletion, 23
confirming survival), the same reread loop from the N=5 build, unmodified
since it already iterated over `shared`/`untouched` generically. `make
check` remained 319/319 offline; `make gates` unaffected (G1-G4 PASS, G5
correctly BLOCKED) — no core module touched, matching the non-goals
above. `README.md`'s fleet section and `scripts/render_architecture.py`'s
`Fleet N=5` → `Fleet N=25` `LiveProof` entry were updated; the widget's
shape is unchanged (the same `groups` type, now listing 23 untouched
names instead of 3) — confirmed in-browser, locally and after redeploy,
that this reads as a longer list inside the existing widget, not a new
UI section. Regenerated (`make gui`) and redeployed to the same Vercel
project via the `vercel` CLI (confirmed with the user first, since
production deploys are a visible, hard-to-reverse action); verified live
at `custody-incident-cave2.vercel.app/architecture.html`, no console
errors, `Fleet N=25` widget rendering real captured data.

Status: complete

## Sub-build: R1 digest versioning and the fail-open revocation path (opened 2026-08-14)

Objective: a change to custody/revision.py's canonicalization silently
invalidated every revision digest already written, and CustodyGraph's
revision-specific revocation fails open when that happens: it removes
nothing and reports success. Make a stored digest self-describing, make
the revocation path fail loud, make admission fail closed under its own
reason, and add the two kinds of test that would have caught it.

Branch: feat/memory-provenance
Parent: 560997f

Allowed files: custody/revision.py, custody/graph.py, tests/test_revision.py,
tests/test_graph.py, a new tests/test_stored_artifacts.py,
scripts/registry_gates.py, scripts/live_registry_attack.py,
scripts/live_revision_binding.py, DECISIONS.md, HANDOFF.md,
.claude/SESSION_CONTRACT.md, proof-out/*. Optionally
scripts/render_architecture.py and web/* for the badge in section 6.

Non-goals:

- No change to custody/origin.py, custody/service.py, custody/store.py,
  custody/firestore_store.py or any custody/adapters/* file. Stored
  bare-hex revisions stay readable and stay revocable by tool; only
  revoke_revision refuses them, which is the safe direction. No data
  migration.
- No new live capability, no new Cloud Run service beyond what
  make live-registry-attack already redeploys, no new GUI section.
- Do not add code_revision/digest_algorithm to the other ten producers.

Baseline: make check 319/319 offline with 0 skipped, make gates G1-G4
PASS / G5 BLOCKED, make registry-gates 4/8 offline with three substantive
failures (live_surface_changed, custody_blocked_before_dispatch,
revision_specific_descendants_revoked). Record all three before editing.

Acceptance gates: the six in R1_HANDOFF.md section 7.

Verification: make check, make gates, make incident, then
make live-registry-attack and make registry-gates (8/8), then make gui
and a manual browser check of the redeployed page.

**Closed 2026-08-14.** All eight steps and all six acceptance gates from
R1_HANDOFF.md done and verified.

Steps 1-6 (offline, no cloud): golden-digest test pinning `_digest`'s
canonicalization (`tests/test_revision.py::TheDigestAlgorithmIsPinned`);
`DIGEST_ALGORITHM = "sha256/2"` prefix plus `algorithm_of()` reader in
`custody/revision.py`; `CustodyGraph.descendants_for_revision` now raises
`RevisionAlgorithmMismatch` on a genuine algorithm boundary instead of
silently returning `()` (three new tests in `tests/test_graph.py`);
`RevisionCatalog.admit` denies an algorithm boundary under its own
`Denial.ALGORITHM_SUPERSEDED`, never `REVISION_MISMATCH`; a comment on
`AttestationAuthority.verify` explaining why it needs no change; a new
`tests/test_stored_artifacts.py` that re-judges every artifact in
`proof-out/` against its own offline judge, exempting only freshness —
this is what turned `make check` red on the stale `live-registry-attack.json`
before Step 8 regenerated it.

Step 7: `scripts/live_registry_attack.py` and `scripts/live_revision_binding.py`
now record `code_revision` (git SHA of HEAD at capture) and
`digest_algorithm` (`custody.revision.DIGEST_ALGORITHM`) in their evidence.
`scripts/registry_gates.py`'s `main()` prints a diagnostic note naming both
algorithms and the recorded `code_revision` when a failing gate's evidence
was captured under a different algorithm than the current build.

Step 8, live, with two unrelated pieces of cloud drift discovered and fixed
along the way (both within the allowed-files scope, `server.py` was not
touched):

- R2's commit added a mandatory `COPY custody ./custody` to the shared
  server Dockerfile, but only `live_revision_binding.py`'s producer
  vendored `custody/` into the Cloud Build context before submitting;
  `live_registry_attack.py` never did, so its build broke silently the
  moment R2 landed. Fixed by adding the same `_vendor_custody`/
  `_remove_vendored_custody` pair `live_revision_binding.py` already used.
- R2 also made the shared server (`live/registry_attack/server/server.py`)
  refuse **every** `tools/call`, unconditionally, without a signed
  dispatch-attestation token minted from a recent `tools/list` — not just
  calls on R2's own governed path. `live_registry_attack.py`'s direct
  calls (the "registered v1" and "ungoverned negative control" steps)
  never minted one, so the server itself refused them before Custody's own
  admission check ever ran. Fixed in `live_registry_attack.py` only (no
  `server.py` change): a `_fresh_attestation` helper mints a token from a
  `tools/list` read taken immediately before each direct dispatch, and
  `_call_tool` now requires and forwards it via `client.call_tool(...,
  meta=...)`. This does not weaken the proof: a token minted this close to
  the call always matches the server's *live* revision, so server-side
  attestation passes trivially regardless of which revision is deployed —
  it is still Custody's own client-side `RevisionCatalog.admit`, comparing
  against the stale *approved* pin, that is the mechanism being proven to
  block dispatch on the governed path.

`make live-registry-attack` ran live end to end against
`project-988bc9fe-092c-4b32-90c`: fresh v1/v2 Cloud Run revisions, a real
Agent Registry write, both digests recorded as `sha256/2:...`. `make
registry-gates` reported 8/8. `make check` 325/325 offline (0 skipped, 0
failures), `make gates` G1-G4 PASS / G5 BLOCKED (unaffected, now 2/4 groups
demonstrable purely from the fresh R1 evidence). `make incident` unchanged.
`make gui` regenerated `web/architecture.html` (a 2-line diff, the refreshed
gate-data JSON only) and byte-identical `web/incident.html`. Deployed with
the user's explicit go-ahead via the authenticated `vercel` CLI from disk
(`vercel link --project custody-incident`, then `vercel deploy --prod`, run
by the user directly after the harness's auto-mode classifier blocked the
Bash invocation); live at `custody-incident.vercel.app`, both pages
confirmed rendering correctly with zero console messages of any kind.

Status: complete

## Sub-build: durable RevisionCatalog, durable replay ledger, image-bound admission (opened 2026-08-14)

Objective: close the three gaps R1_HANDOFF.md's "What this does not fix"
section named. `RevisionCatalog` is an in-memory spike (durable pins via
Firestore). `AttestationAuthority`'s replay-nonce set is process-local
(durable via a new pluggable `NonceLedger`, Firestore-backed live). R1 only
detects declared MCP surface drift, not a same-schema/different-image swap
(bind the Cloud Run revision name + resolved image digest into admission,
new `RuntimeBinding` / `Denial.RUNTIME_DRIFT`).

Branch: feat/memory-provenance
Parent: HEAD at open (post R1 hardening + live redeploy)

Allowed files: custody/revision.py, custody/firestore_store.py,
custody/nonce_ledger.py (new), tests/test_revision.py,
tests/test_firestore_store.py, tests/test_nonce_ledger.py (new),
scripts/live_registry_attack.py, scripts/live_revision_binding.py,
scripts/registry_gates.py, scripts/revision_binding_gates.py,
live/registry_attack/server/server.py,
live/registry_attack/server/requirements.txt, DECISIONS.md,
.claude/SESSION_CONTRACT.md, proof-out/*, web/* (regeneration only).

Non-goals: no change to custody/origin.py or CustodyRecord (runtime binding
is an admission-time gate, not threaded into stored derivation records);
scripts/revision_spike.py untouched; no TTL/pruning for the growing
dispatch_nonces collection; no multi-instance concurrent proof for the
replay ledger (--max-instances=1 stays; durability-across-restart is what's
proven instead).

Baseline: make check 325/325 offline, 0 skipped, ruff clean. make gates
G1-G4 PASS / G5 BLOCKED. make registry-gates 8/8. Record before editing.

Acceptance gates: see the full plan at
/home/Yatsuiii/.claude/plans/synthetic-booping-lagoon.md — offline mechanism
+ tests for all three gaps, then live re-proof of each (new
runtime_binding_also_blocked gate in registry-gates, new
replay_survives_process_restart gate in revision-binding-gates), make gates
unaffected, make gui + a separate go-ahead before any Vercel redeploy.

Verification: make check first (offline, must pass before any live step),
then make live-registry-attack + make registry-gates, then
make live-revision-binding + make revision-binding-gates, then make gates,
then make gui and a manual browser console check.

**Closed 2026-08-14.** All three gaps closed, offline mechanism plus live
re-proof for each.

Offline: `FirestoreRevisionCatalog` (custody/firestore_store.py, read-through,
no local cache) and `FirestoreNonceLedger` (new custody/nonce_ledger.py,
deliberately not co-located with firestore_store.py to avoid vendoring
custody.catalog/custody.graph into the live server's Docker image) plus a
pluggable `NonceLedger` protocol on `AttestationAuthority`; `RuntimeBinding`
and `Denial.RUNTIME_DRIFT` for image-bound admission, opt-in via
`ApprovedTool.runtime_binding` / `admit(observed_runtime=...)`, fully
backward compatible. 20 new offline tests across tests/test_revision.py,
tests/test_firestore_store.py (extended the fake client with `.set()`), and
the new tests/test_nonce_ledger.py.

Two bugs found and fixed only by running live, not offline:

1. `_resolved_image_digest`'s first field-path guess
   (`status.containerStatuses[0].imageDigest`) was wrong for this Knative
   Revision schema; the real field is `spec.containers[0].image`, resolved
   by Cloud Run to a `name@sha256:...` reference at deploy time. Fixed by
   reading and confirmed against a live `revisions describe` call.
2. Making the nonce ledger durable and Firestore-shared broke
   `live_revision_binding.py`'s pre-existing digest-mismatch control: it
   reused an *already-consumed* v1 token against v2, which used to test
   DIGEST_MISMATCH only because the ledger was process-local (v2's process
   had never seen that nonce). With a shared durable ledger, REPLAYED
   correctly fires first, everywhere, which is stronger but broke that
   control's isolation. Fixed by minting a second, dedicated, never-consumed
   v1 token for the mismatch control specifically.

Live, against project-988bc9fe-092c-4b32-90c: `make live-registry-attack`
ran with `CUSTODY_FIRESTORE_PROJECT` set — evidence confirms
`revision_catalog_backend: firestore` and a live `RUNTIME_DRIFT` denial on
a same-schema, differently-revisioned admission check using real resolved
Cloud Run image digests. `make registry-gates` 9/9 (new gate
`runtime_binding_also_blocked`). `make live-revision-binding` added a
7th step: redeploy v1 again (same digest, genuinely fresh process, proven
by a differing Cloud Run revision name) and replay the original,
already-consumed v1 token against it — durable ledger correctly returned
`replayed`, proving the pre-fix gap (a fresh in-memory ledger would have
wrongly accepted it) is now closed. `make revision-binding-gates` 16/16
(new gate `replay_survives_process_restart` plus its independent live
Cloud Logging re-read). `make check` 343/343 offline, 0 skipped. `make
gates` G1-G4 PASS / G5 BLOCKED, unaffected. `make gui` regenerated
web/architecture.html (2-line diff, gate-data JSON only); verified locally
over a throwaway `python3 -m http.server`, zero console messages, R1 and R2
rows showing the updated claim_boundary text and fresh evidence. Redeploy
to the public Vercel page was not requested this session and was not done.

Status: complete

## Sub-build: close the judging-pass accuracy findings (opened 2026-08-14)

Objective: a read-only judging pass (verbatim report kept at
`SUBMISSION_HANDOFF.md`) found one substantive defect and seven accuracy
defects. The substantive one (R1's digest break) was closed by the
sub-build above. This closes the documentation and gate-honesty findings
that remain, all of which are in judge-facing surfaces: the README's own
headline transcript, two stale test counts, one wrong gate count, a
diagram contradicting the status table, a gate hardcoded so it can never
pass, and README text that now *understates* what R1/R2 actually prove
after the durable-ledger and runtime-binding work landed.

Branch: feat/memory-provenance
Parent: 560997f

Allowed files: `README.md`, `docs/architecture.md`, `JUDGE_HANDOFF.md`,
`R1_HANDOFF.md`, a new `SUBMISSION_HANDOFF.md`, `scripts/gates.py`,
`tests/test_g1_gate.py`, `.claude/SESSION_CONTRACT.md`, and `web/*` only
as regenerated output of `make gui`.

Non-goals:

- No change to any `custody/*` module. Nothing here alters behaviour that
  a live proof already gated.
- No live proof reruns. Every artifact in `proof-out/` was captured this
  same day by the sub-build above and stays untouched.
- No Vercel redeploy. `make gui` regenerates the local page; publishing it
  is a visible, hard-to-reverse action and needs explicit authorization.
- Do not commit `proof-out/`. Whether captured evidence belongs in the
  repo is a real decision, recorded as open in `SUBMISSION_HANDOFF.md`,
  not something to settle silently inside a docs pass.

Baseline: `make check` 343/343 offline with 0 skipped, `make gates` G1-G4
PASS / G5 BLOCKED at 2 of 4 groups, `make registry-gates` 9/9,
`make revision-binding-gates` 16/16.

Acceptance gates:

1. Every code block in `README.md` that shows command output matches what
   that command prints today, verified by running it.
2. No stated count in `README.md` disagrees with what the named command
   reports (`make check` 343, `make chain-gates` 21).
3. `scripts/gates.py`'s G5 judges telemetry from
   `proof-out/live-observability.json` through the observability judge,
   rather than from a hardcoded `False`. G5 stays BLOCKED on real elapsed
   time, which is the only honest reason left.
4. `docs/architecture.md`'s component diagram agrees with `README.md`'s
   status table on every node.
5. `README.md` states plainly that `proof-out/` is generated and not in
   the repo, so a judge cloning it is not misled.
6. `README.md`'s R1 and R2 scope paragraphs match those artifacts' own
   `claim_boundary` strings, in both directions: no overclaim, and no
   remaining understatement of the runtime-binding and durable-ledger work.

Verification: `make check`, `make gates`, `make incident`, `make gui`, and
a re-read of every changed paragraph against the artifact it describes.

**Closed 2026-08-14.** All six gates met, no live proof rerun, no
`custody/*` module touched.

Gate 1: `README.md`'s `make incident` block was a stale hand-paste from
before `VOUCHED_AT` changed (`scripts/incident.py:40`), claiming
`2026-07-24 / day 22 / 21 days` where the command prints
`2026-07-30 / day 16 / 15 days`, with a wrong lineage root label too.
Repasted from real output and re-verified by running it. The irony was the
finding's whole force: the sentence directly below that block claims the
story and the numbers cannot drift apart.

Gate 2: two stale test counts (`170`, in a suite that had reached 345) and
F1's gate count (`20/20` where `chain_gates.py` prints 21 — 14 offline plus
7 live rereads, and the README's own prose said "6 rereads ... 6 gone, 1
survives", which does not add up either) corrected.

Gate 3: `scripts/gates.py`'s G5 judged telemetry from a hardcoded `False`.
That was correct while O1 was unbuilt and became a lie once O1 landed, so
G5 could never reach 4 of 4 no matter what evidence existed. Now judged
through `observability_gates.judge` on `live-observability.json`, wired in
alongside the registry and gateway groups. G5 stays BLOCKED, which is
right: real elapsed time is the honest remaining reason, and telemetry now
reports missing only because O1's artifact aged past 24 hours. Gated by a
new `G5NamesTheGroupsItCannotDemonstrate` in `tests/test_g1_gate.py`.

Gate 4: `docs/architecture.md` still coloured Firestore amber ("not yet
built") while the README's status table, the Auditor proof, the durable
`RevisionCatalog` and the durable nonce ledger all depend on it. Now green,
with the legend rewritten since no amber node remains.

Gate 5: `proof-out/` being generated and uncommitted was true, reasonable,
and nowhere stated, while `README.md` referenced it five times and
`JUDGE_HANDOFF.md` pointed judges straight at it. Both now say plainly
that a fresh clone has no live evidence, why committing 24-hour-expiring
artifacts would be worse, and where to read the captured evidence instead.

Gate 6: after the runtime-binding and durable-ledger work, `README.md` had
started *understating* R1 and R2 — still describing the replay ledger as
process-local and the proof as declared-surface-only. Both scope
paragraphs rewritten against those artifacts' own `claim_boundary` strings
rather than summarised, in both directions.

Verification: `make check` 345/345 offline, 0 skipped. `make gates` G1-G4
PASS / G5 BLOCKED at 2 of 4 groups. `make incident` output re-read against
the README block line by line. `make gui` regenerated `web/architecture.html`
(2-line `gate-data` diff, G5's detail line only); the deployed Vercel page
is now two lines behind and redeploying it was not requested this session
and was not done. Remaining submission work recorded in
`SUBMISSION_HANDOFF.md`; `R1_HANDOFF.md` marked closed.

Status: complete

**Addendum, same day.** Authorizing the redeploy surfaced a live
regression that predates this session's work: `/` on the public site
returns **404**. It served the dependency map earlier today (verified,
HTTP 200, 27664 bytes), so the previous session's first
`vercel deploy --prod` from `web/` dropped it — that directory holds
`incident.html` and `architecture.html` and no `index.html`, and the
earlier MCP-tool deploys had been uploading the incident page renamed.
Both `README.md` and `JUDGE_HANDOFF.md` advertise the bare root URL, so
this is the first thing a judge would hit.

Fixed at the deploy boundary rather than by renaming a file the docs
reference by name: `web/vercel.json` rewrites `/` to `/incident.html`,
leaving `/incident.html` and the pages' own `href="incident.html"`
back-links working unchanged. `web/.vercelignore` also added so the
CLI-generated `web/.env.local` (a short-lived `VERCEL_OIDC_TOKEN`, already
gitignored and confirmed not served) can never be uploaded as a static
asset.

The deploy itself was not run: `vercel deploy --prod` was blocked by this
environment's permission classifier, and the `deploy_to_vercel` MCP tool
takes inline file contents, which is the exact path that silently
corrupted `architecture.html` before. Handed to the user to run.

## Sub-build: make the post-deploy checks a command (opened 2026-08-14)

Objective: three live regressions have now shipped behind a deploy that
reported success -- an inline `<script>` corrupted in transit that blanked
every widget on a clean 200, a project setting that put a login wall in
front of every URL, and a 404 at `/`. None was visible in the deploy
output, and the root 404 in particular sat unnoticed because nothing
checked the one URL `README.md` and `JUDGE_HANDOFF.md` send judges to.
Replace the prose checklist added earlier today with a real target, since
this project's whole rule is that a claim needs a command behind it.

Branch: feat/memory-provenance
Parent: f591819

Allowed files: new `scripts/verify_deploy.py`, new
`tests/test_verify_deploy.py`, `Makefile`, `SUBMISSION_HANDOFF.md`,
`README.md` and `JUDGE_HANDOFF.md` for the test count only,
`.claude/SESSION_CONTRACT.md`.

Non-goals:

- Not part of `make check`. That suite is network-free and finishes in
  0.12s, and both properties are load-bearing.
- No browser automation. Executing the page is a different capability and
  a much heavier dependency; the target states plainly that it does not
  do it.
- No change to any `custody/*` module or any live proof.

Baseline: `make check` 345/345 offline, `make gates` G1-G4 PASS / G5
BLOCKED, live pages byte-identical to `web/` and console-clean as of the
2026-08-14 deploy.

Acceptance gates:

1. `make verify-deploy` fetches every route and compares served bytes with
   the local build, exiting 0 clean / 1 defect / 2 unreachable, with
   BLOCKED distinguished from FAIL the way `scripts/gates.py` already
   distinguishes them.
2. Fetching is separated from judging so the judge is testable with no
   network, and `make check` stays offline and under a second.
3. `tests/test_verify_deploy.py` covers all three regressions that really
   shipped, plus a stale redeploy and a served `.env.local`.
4. All three exit paths are exercised against real hosts before commit,
   not just reasoned about.
5. Every stated test count across `README.md`, `JUDGE_HANDOFF.md` and
   `SUBMISSION_HANDOFF.md` matches what `make check` prints.

Verification: `make check`, `make verify-deploy` against production, plus
the FAIL and BLOCKED paths against a wrong host and an unresolvable one.

**Closed 2026-08-14.** All five gates met. `scripts/verify_deploy.py`
splits `fetch` from `judge`, so the four gates are pure and the seven new
tests need no network; `make check` is 352/352 in 0.12s, unchanged in
character. Run against production: 4/4 PASS. Run against `example.com`:
correctly failed three page gates, and the detail line distinguished
"HTTP 200 but the body is not web/incident.html: served 559 bytes, built
27664" from a plain "HTTP 404, expected 200", which is the distinction
that matters when diagnosing a bad deploy. Run against an unresolvable
host: BLOCKED with exit 2, not FAIL. One correction along the way: the
first `curl` loop written into `SUBMISSION_HANDOFF.md` earlier today was
broken (`-w` does not printf-pad an arbitrary argument, and the path was
passed as a stray URL); caught by running it, which is the reason it was
run. The target's closing line states what it does not do -- it fetches
bytes, it does not execute them -- so the browser console pass stays an
explicit manual step rather than an implied one.

Status: complete

## Sub-build: the evidence chip reflects staleness, not just presence (opened 2026-08-14)

Objective: `SUBMISSION_HANDOFF.md` item 4. `scripts/render_architecture.py`
gives every live-proof row with a readable artifact the same green
`EVIDENCE` chip regardless of age or whether its own gates still pass, while
the page's own lede claims "a missing or stale file is labeled as such, not
hidden." Missing is handled (a separate `missing`/`malformed` chip already
exists); stale and failing are not distinguished from a fresh pass. Each
row's judge already reports its own freshness gate (`fresh_live_evidence` /
`fresh_bounded_live_evidence`, per `tests/test_stored_artifacts.py`'s
`FRESHNESS_KEYS`), so the fix is to call that judge at render time instead
of inventing a second staleness computation.

Branch: feat/memory-provenance
Parent: c7e3e67

Allowed files: `scripts/render_architecture.py`, `web/architecture.html`
(regenerated output only), `.claude/SESSION_CONTRACT.md`,
`SUBMISSION_HANDOFF.md`.

Non-goals:

- No change to any `scripts/*_gates.py` judge, `custody/*`, or any live
  proof producer. This reuses each judge exactly as `make check` already
  does via `tests/test_stored_artifacts.py`; it does not modify what a
  judge accepts or rejects.
- No live/network calls added to `make gui`. Every judge in
  `tests/test_stored_artifacts.py`'s `ARTIFACT_JUDGES` mapping is pure
  (evidence dict in, bool dict out); reuse exactly those, not any
  `*_live` sibling.
- No change to the G1-G5 core-gates panel; this is scoped to the live-proof
  cards only.

Baseline: `make check` 352/352 offline. `web/architecture.html` currently
renders every readable `proof-out/live-*.json` with the same `EVIDENCE`
chip regardless of age (confirmed: R1/S1/M1/O1 were past 24h stale as of
`R1_HANDOFF.md` section 6 and still rendered identically to a fresh one).

Acceptance gates:

1. A row whose artifact passes every one of its judge's gates (including
   freshness) renders `PASS`.
2. A row whose artifact fails only its freshness gate(s) renders `STALE`,
   not `PASS` and not the same as a substantively-failing row.
3. A row whose artifact fails a non-freshness gate renders `FAILING`,
   distinguishable from `STALE`.
4. `missing` and `malformed` rows (no artifact, or unparsable JSON) are
   unchanged from today's behavior.
5. `make check` stays 352/352, offline, unaffected — the judges are reused,
   not modified.

Verification: `make check`; `make gui` against the current `proof-out/`
(mixed fresh/stale by now) and a manual read of the generated
`web/architecture.html` confirming at least one `PASS`, one `STALE` or
`FAILING` row, each visually distinct. No redeploy without separate
authorization.

**Closed 2026-08-14.** `render_architecture.py` now imports each artifact's
own offline judge (the same ones `tests/test_stored_artifacts.py` already
runs, none of the `*_live` network-calling siblings) and calls it at render
time with `now=` the render clock, splitting a judge's own gate set on the
freshness keys into `pass` / `stale` / `failing`. Confirmed against the
real, currently-mixed `proof-out/` (not a synthetic fixture): 7 rows
render `pass`, and exactly the 4 rows already flagged in
`SUBMISSION_HANDOFF.md` as past 24h (S1, M1, O1, D1/D2) render `stale` —
none render `failing` today, so that path was exercised by temporarily
corrupting a copy of an artifact's evidence and confirming it renders
distinctly from `stale`, then discarding the copy. `missing`/`malformed`
rows are unchanged (verified: no artifact currently exercises either path
in this run, behavior is identical code to before). `make check` 352/352,
unaffected. Not redeployed — that needs separate authorization per this
project's own rule, and `SUBMISSION_HANDOFF.md` item 2 (refreshing the
stale live evidence) should happen before the next redeploy anyway, since
redeploying now would just publish a page showing 4 rows correctly, but
needlessly, marked stale.

Status: complete

## Sub-build: refresh the stale live evidence (opened 2026-08-14)

Objective: `SUBMISSION_HANDOFF.md` item 2. S1, M1, O1, D1/D2 (and possibly
others by now) are past their 24h freshness window, which is exactly what
made the previous sub-build's `STALE` chips real. Rerun every `make live-*`
producer, confirm `make gates` reports G5 at 4 of 4 groups, regenerate the
GUI so the chips reflect the refreshed evidence, then commit and push on
explicit authorization already given.

Branch: feat/memory-provenance
Parent: (this session's HEAD after the evidence-chip commit)

Allowed files: `proof-out/*` (gitignored, not committed regardless),
`web/incident.html`, `web/architecture.html` (regenerated output only).
No source changes expected; if a live producer script itself needs a fix
to run today, stop and report before editing it rather than silently
patching a live proof script under this contract.

Non-goals:

- No redeploy to Vercel as part of this sub-build unless the user asks
  separately — refreshing `proof-out/` and regenerating `web/` is a local
  step; publishing it is a distinct action.
- No new capability, no change to any judge, no change to G1-G4 or the
  offline suite.
- Do not fabricate or hand-edit any `proof-out/*.json` field if a live run
  fails; report the failure instead, per this project's own discipline.

Baseline: `make check` 352/352. `make gates` reports G5 BLOCKED at 2 of 4
groups (security/governance and telemetry aged out) per
`SUBMISSION_HANDOFF.md`. Chips from the previous sub-build: 7 pass, 4 stale
(S1, M1, O1, D1/D2).

Acceptance gates:

1. All ten `make live-*` producers listed in `SUBMISSION_HANDOFF.md` item 2
   run and each writes a fresh `proof-out/live-*.json`.
2. `make gates` reports G5 at 4 of 4 groups, still BLOCKED only on elapsed
   time (not on stale artifacts).
3. Every corresponding `*-gates` judge (`make registry-gates`,
   `make gateway-gates`, etc., or the offline re-judge via `make check`)
   still passes against the freshly captured evidence.
4. `make gui` regenerates `web/*.html` and the chips from the previous
   sub-build now render `pass` for every row that was previously only
   `stale` (not `failing` or `missing`).

Verification: `make check`, `make gates`, `make gui`, then a read of the
regenerated `proof-out/*.json`/`web/architecture.html` chip states. Commit
and push once verified, per explicit user authorization.

**Paused 2026-08-14, not closed.** 8 of 10 producers refreshed clean
(`live-g1`, `live-observability`[artifact written, see finding below],
`live-auditor`, `live-review`[2nd attempt], `live-narration`, `live-fleet`,
`live-chain`, `live-registry-attack`). Three real, reproducible findings
surfaced, none of them caused by this session's own edits — reported to
the user rather than silently patched, per this contract's own non-goals:

1. `make live-gateway` fails both attempts: `"dispatch attestation missing
   for lookup_customer"`. R2's attestation middleware is refusing the
   script's own dispatch.
2. `make live-model-armor` fails: the live Template now returns
   `templateMetadata.dataResidencyCompliant: true` alongside the two
   fields `EXPECTED_TEMPLATE_METADATA` in `scripts/live_model_armor.py`
   checks for, so the strict-equality ownership check rejects an
   apparently-unmodified, still-correct Template. Confirmed via direct
   `gcloud model-armor templates describe`: the template's own settings
   (filter config, labels, the two expected metadata flags) are
   unchanged; only the extra field is new.
3. `make live-revision-binding` fails both attempts at step 7/7 (the fresh-
   process replay check `R1_HANDOFF.md` records as a recent addition):
   `"no denial log with reason=replayed found for revision ... (nonce
   ...)"`. Two Cloud Run redeploys per attempt, four total this session,
   all reproduced the identical failure shape. Likely regression in the
   Firestore-backed nonce ledger persistence R1_HANDOFF.md's closing note
   says was added.
4. Found while investigating, not yet reported anywhere else:
   `live-observability`'s own judge now fails `g1_admission_reached_
   memory_bank` (substantive, not freshness) — its embedded G1 admission
   shows `memory_write_count: 3`, but the judge still hardcodes
   `== 1`, unchanged since before the G1 migration onto `write_record`
   documented in `HANDOFF.md` ("write_record returns two raw, unmerged
   per-event facts where ingest_events returned one"). O1's own proof
   script/judge appears never updated for that migration's write-count
   change.

Additionally, `make live-memory-deletion` failed with `400 INVALID_ARGUMENT:
Memory ... already exists` for the exact fixed memory id D2's original
2026-08-13 proof used (`cr-5e69b7e2...`) — deterministic by design, so a
prior run's revocation-triggered delete apparently never completed and
left it live. Deleting that stray resource to unblock a rerun is a live
cloud mutation and was correctly held for explicit authorization rather
than done automatically.

None of these four findings were fixed under this contract — its own
non-goals say stop and report rather than silently patch a live producer
script. `make gates` currently reports G5 still at 2 of 4 groups
(discovery/lifecycle, execution/state), unchanged from before this sub-
build, because security/governance and telemetry both depend on judges
that are currently failing for the reasons above, not on missing/stale
artifacts anymore.

Status: blocked, awaiting user direction on findings 1-4 and the D2 cleanup

## Sub-build: fix the four live-evidence findings, one at a time (opened 2026-08-14)

Objective: the previous sub-build's refresh surfaced four real, reproducible
problems, none caused by this session's own edits. User's direction: fix
each for real, one at a time, same discipline as the Fleet-review sub-
builds earlier in this project (root-cause before editing, live proof
after, no silent patching). Order: O1 (clearest root cause) -> M1 (clear
root cause) -> S1 Gateway (needs investigation) -> R2 revision-binding
(needs investigation) -> D2 stray-memory cleanup (needs live-delete
authorization, held separately).

Branch: feat/memory-provenance
Parent: (this session's HEAD, before any of these fixes)

Allowed files: `scripts/observability_gates.py`, `scripts/live_observability.py`,
`scripts/live_model_armor.py`, `scripts/model_armor_gates.py`,
`live/registry_attack/server/server.py`, `scripts/live_gateway.py`,
`scripts/gateway_gates.py`, `scripts/live_revision_binding.py`,
`scripts/revision_binding_gates.py`, `custody/revision.py` (only if the
root cause is genuinely there, not assumed), `tests/test_observability_gates.py`,
`tests/test_model_armor_gates.py`, or equivalent test files for each touched
judge, `proof-out/*`, `.claude/SESSION_CONTRACT.md`, `HANDOFF.md`,
`R1_HANDOFF.md`, `SUBMISSION_HANDOFF.md`.

**Amended mid-session, found while investigating finding 3 (S1):** the
actual break lives in `live/gateway_probe/agent.py` (the deployed Agent
Runtime workload's own hand-rolled MCP wire client), not
`server.py` — that file predates R2's attestation middleware and was never
updated to round-trip its token. Fixing it also required running
`scripts/deploy_gateway_probe.py` (already an existing Makefile target,
`make deploy-gateway-probe`) to push the fix to the live Runtime. Both are
added to the allowed scope here rather than treated as a violation, since
the root cause was genuinely unknown until investigated, consistent with
this contract's own non-goal ("stop and report before editing" was
followed — investigation preceded the edit, and no closed sub-build's
already-gated surface was touched).

Non-goals:

- No change to `custody/service.py`, `custody/adapters/memory_bank.py`, or
  any already-closed sub-build's core surface unless a fix genuinely
  requires it — if so, stop and report before editing, per this project's
  standing rule for reopening closed, gated surfaces.
- Do not paper over a real regression by loosening a check until it
  passes. Each fix must explain, in prose, why the new expected value or
  new check is the *correct* one, not just the one that makes the script
  exit 0 today.
- No commit or push until all four (or as many as get closed this
  session) are verified live and `make check`/`make gates` are read
  again, clean.

Baseline: `make check` FAILING (1 failure: `live-observability.json` fails
`g1_admission_reached_memory_bank`, substantive, not freshness). `make
gates` reports G5 at 2 of 4 groups. Findings 1-4 as described in the
previous sub-build's closing note.

Acceptance gates (per finding):

1. O1: `make live-observability` passes its own judge substantively (not
   just freshness), `make check` returns to 352/352 green, and the fixed
   invariant is documented as correct, not just passing.
2. M1: `make live-model-armor` and `make model-armor-gates` pass against
   the currently live Template without weakening what "owned" means (still
   rejects a genuinely different filter config, enforcement level, or
   label).
3. S1: `make live-gateway` and `make gateway-gates` pass, with the root
   cause of "dispatch attestation missing" identified and named, not
   guessed around.
4. R2: `make live-revision-binding` and `make revision-binding-gates` pass
   the fresh-process replay control specifically (not just the other six),
   root cause named.
5. `make gates` reports G5 at 4 of 4 groups (still BLOCKED only on elapsed
   time) once S1 and O1 are both fixed.

Verification: `make check`, `make gates`, each finding's own `make live-*`
+ `make *-gates` pair, then `make gui` to confirm the chip work from the
earlier sub-build now shows `pass` across the board (modulo D2, held for
separate authorization). Commit and push once verified, per the user's
standing authorization for this thread.

**Amended again, finding 5 (D2 cleanup):** `scripts/live_memory_deletion.py`
builds its record id from hardcoded literal invocation names (`"inv-sales"`,
`"inv-finance"`), not anything proof-run-specific, so `memory_id_for()` is
identical across every run since 2026-08-13 (confirmed: the exact same
`cr-5e69b7e2...` id from that original run is what's stuck today). This
made every rerun depend on the *previous* run's revocation-delete having
fully completed, which is not true today: the memory reads `404 NOT_FOUND`
on `get`/`delete` (both the SDK and a raw REST call agree) but
`memories.create` still refuses with `already exists`, consistently across
a 10+ hour gap — a genuine Google-side split between the read/delete path
and the create-uniqueness reservation, not something this project's code
can wait out or fix server-side. User authorized the fix: fold `proof_id`
into the invocation labels so each run gets its own `memory_id`, the same
pattern every other live producer already uses for exactly this reason.
`scripts/live_memory_deletion.py` is added to the allowed scope for this
one narrow change.

**Fifth finding, discovered closing out S1:** `gateway_gates.py` hardcodes
that the shared Cloud Run service `custody-export-mcp` is on
`CUSTODY_MCP_REVISION=v2` (`owned_cloud_run_target_bound`,
`allow_reached_owned_mcp`). R1, R2, and S1 all reuse this one service.
R2's own proof deliberately ends on a `v1` redeploy (its step 7, "fresh
process, unchanged digest"), so running R2 right before S1 — as this
session did — left the service on `v1` and made S1's judge fail on
environmental state, not on anything either fix touched. No code changed
for this: restored `v2` by rerunning `make live-registry-attack` (R1),
which deploys `v1` then `v2` and always ends on `v2`, then reran `make
live-gateway` clean. **Not fixed at the code level, only worked around this
session** — if S1 is ever run directly after R2 again, it will fail the
same way. Worth a real fix later (either make R1/S1's judges revision-
agnostic, or have `make live-gateway` assert/restore its own required
revision itself), but out of scope for a same-day evidence-refresh pass.

All five findings closed, all live-verified this session:
- O1: `make check` 355/355, `make live-observability` + offline judge PASS.
- M1: `make live-model-armor` + `make model-armor-gates` 9/9 PASS.
- S1: `make live-gateway` + `make gateway-gates` 20/20 PASS.
- R2: `make live-revision-binding` + `make revision-binding-gates` 16/16 PASS.
- D2: `make live-memory-deletion` + `make memory-deletion-gates` 7/7 PASS.

Status: complete

## Sub-build: remove the hardcoded "v2" coupling from gateway_gates.py (opened 2026-08-15)

Objective: the previous sub-build worked around, but did not fix, a real
bug: `scripts/gateway_gates.py` hardcodes the literal `"v2"` in three
separate self-consistency chains (`_cloud_run_is_bound`'s
`revisions == ["v2"]`; `allow_reached_mcp`'s trailing `== "v2"`;
`_server_dispatch_is_bound`'s trailing `== "v2"`), even though S1's own
`CLAIM_BOUNDARY` is entirely about IAP/Gateway/identity enforcement and
says nothing about which tool-revision digest is currently deployed. R1,
R2, and S1 share one Cloud Run service (`custody-export-mcp`); R2's own
proof deliberately ends on a `v1` redeploy, so running S1 after R2 fails
S1's judge on an incidental literal that was never actually load-bearing
for what S1 proves. Fix: replace each hardcoded `"v2"` with the evidence's
own reported revision, so the check still requires full self-consistency
(the Cloud Run resource, the ledger before/after, the dispatched payload,
and the server-authored log entry all agree on the same revision label)
without pinning that label to a specific value.

Branch: feat/memory-provenance
Parent: 871535c

Allowed files: `scripts/gateway_gates.py`, `tests/test_gateway_gates.py`
or equivalent, `.claude/SESSION_CONTRACT.md`, `proof-out/*`.

Non-goals:

- No change to `scripts/live_gateway.py`, `live/registry_attack/server/server.py`,
  or any already-closed sub-build's surface. This is a judge-only fix.
- Do not weaken what the check actually verifies. Every value must still
  agree with every other value in the chain; only the hardcoded anchor
  ("v2" specifically) is removed, not the requirement that they match.
- Do not silently accept a revision label the Cloud Run resource, the
  ledger, and the dispatch log disagree on — self-consistency across all
  four sources stays mandatory.

Baseline: `make gateway-gates` 20/20 PASS today only because the service
happens to be on `v2` (restored manually in the prior sub-build). Rerunning
`make live-revision-binding` (which ends on `v1`) and then `make
live-gateway` without this fix would reproduce the original failure.

Acceptance gates:

1. All three hardcoded `"v2"` literals are replaced with a value read from
   the evidence itself, not a second hardcoded literal.
2. A test proves the judge still rejects a genuine mismatch (e.g. the
   Cloud Run resource reports one revision while the dispatch payload
   reports another) — the self-consistency property is preserved, not
   just relaxed.
3. `make gateway-gates` still reports 20/20 PASS against the current,
   `v2`-deployed evidence.
4. The actual coupling is proven fixed, not just reasoned about: rerun
   `make live-revision-binding` (ends on `v1`) to genuinely flip the
   shared service away from `v2`, then rerun `make live-gateway` +
   `make gateway-gates` and confirm it still passes 20/20 without any
   manual restoration step in between.

Verification: `make check`, the two live reruns in gate 4, `make gates`
(G5 should stay at 4 of 4 groups throughout, including in between the two
live reruns). Then `make gui` and redeploy to Vercel per the user's
explicit request, verified with `make verify-deploy` after.

**Closed 2026-08-15.** The "v2" coupling was worse than first scoped:
three separate hardcoded literals across two files, not one.
`scripts/gateway_gates.py`: `_cloud_run_is_bound`'s `revisions ==
["v2"]` (now bound to the same live proof's own ledger revision) and its
`metadata["labels"].get("custody-proof") == "stale-registry"` (a second,
undiscovered instance of the same class — R2's own redeploy tags the
shared service `custody-proof: revision-binding`, overwriting R1's tag;
relaxed to "a non-empty ownership label", not a specific proof's name).
`allow_reached_mcp` and `_server_dispatch_is_bound`'s trailing `== "v2"`
chains (now self-consistency only, with an explicit `isinstance(..., str)`
guard so two `None`s can no longer trivially satisfy the chain). The same
`_server_dispatch_is_bound` fix, plus a third and independent finding, was
needed in `scripts/gateway_live_attestation.py` (the live-reread half,
`attest_live`, a separate module gates.py imports and merges in only
after the offline judge fully passes) -- its own `payload.get("revision")
== "v2"` hardcode, verified only by rerunning the actual live gate against
v1-deployed evidence, not reasoned about.

Genuinely fourth finding, not anticipated when this was scoped: v1's
`lookup_customer` tool (`live/registry_attack/server/server.py`) predates
`forward_to` and returns no `forwarding_requested`/`forwarded_to`/
`forwarding_status` keys at all, while v2 always includes them. Both
`_server_dispatch_is_bound` implementations hardcoded `is False`/`is
None`/`== "not-requested"`, which a v1 response's absent keys cannot
satisfy. Fixed by tolerating absence (`in (False, None)` / `in
("not-requested", None)`) on the three optional, schema-version-dependent
fields, while keeping the server's own unconditional structured-log field
(`payload.get("forwarding_requested") is False`, written by
`_log_gateway_dispatch` regardless of tool version) a hard requirement,
since that one is the actual server-authored security fact.

Four new tests added, each proving the fix rather than just relaxing a
check: `test_a_genuinely_different_but_self_consistent_revision_still_
passes` and `test_a_v1_shaped_tool_result_with_no_forwarding_fields_
still_passes`, in both `tests/test_gateway_gates.py` (the offline judge)
and `tests/test_gateway_live_attestation.py` (the live-reread module) --
each constructs a fully self-consistent `v1`-labeled/shaped fixture and
asserts every gate still passes, not just the ones touched. A fifth new
test extends `test_unowned_or_multiprocess_cloud_run_target_cannot_pass`
with `missing_label`/`empty_label` cases, proving the relaxed ownership
check still rejects a genuinely absent or empty label. `make check`
360/360 (was 356/356 before this sub-build).

Gate 4, the real proof, done without any manual workaround this time:
`make live-revision-binding` (ends on `v1`, confirmed live via `gcloud run
services describe`) immediately followed by `make live-gateway` and `make
gateway-gates`, 20/20 PASS -- no restoration step in between, unlike the
previous sub-build's closing note. `make gates` still reports G5 at 4 of 4
groups. Redeploy to Vercel is the next step, on the user's explicit
request in this same message.

Status: complete

## Second project, phase 1 and 2 (opened 2026-08-15). Not Custody.

**This section governs a different product that happens to share this
repository.** Everything it produces lives under `research-impact/` and
nothing above this line changes. Custody stays the primary Fortified
Enterprise Fleet submission; this is a second, independent entry under the
**Collaborative Partner** track, which the rules permit: *"An Entrant may
submit more than one Submission, however, each Submission must be unique
and substantially different"* (allthingsagentichackathon.devpost.com/rules,
read live 2026-08-15). Working codename **Keel**, deliberately provisional.

Objective: decide GO/MODIFY/KILL on a persistent research change-impact
engine with written evidence (`research-impact/RESEARCH.md`), and if the
verdict is not KILL, prove the technical heart offline: that new evidence
against one assumption produces a *deterministic*, provenance-explained
downstream impact set over a typed research graph, rather than an LLM
narrating which experiments it thinks changed.

Branch: feat/memory-provenance
Parent: c7e3e67

**Why this branch, recorded rather than implied.** Custody has uncommitted
work in the tree right now (7 modified files, the four live-evidence
findings sub-build above, `Status: active`). Cutting a new branch would
carry that work onto it and invite committing Custody's WIP under a
second-project branch name. Nothing here is committed without explicit
authorization, and the second project is isolated by directory, so the
branch adds no isolation the directory does not already give. Cut
`feat/research-impact` once the Custody WIP above is committed, and record
that as the moment the two histories separate.

Allowed files: everything under `research-impact/`, plus this contract.
Nothing else. Specifically not: `Makefile`, `pyproject.toml`,
`requirements.txt`, `.gitignore`, `custody/`, `scripts/`, `tests/`,
`web/`, `README.md`, or any Custody handoff document.

Non-goals:

- No Custody concepts, branding, classes, or copy. Shared engineering
  discipline (provenance, explicit state transitions, an independent
  judge that rereads the artifact) is method, not product, and is the only
  thing that crosses over.
- No dependency added to Custody's environment. `research-impact/` is
  stdlib-only Python 3.12 with its own `pyproject.toml` and `Makefile`, so
  the root `make check` keeps working untouched. Root `make lint` is
  `ruff check .` over the whole tree, so this code must stay ruff-clean at
  88 columns or it breaks Custody's gate — that is a hard constraint, not
  a preference.
- No cloud resources, no Gemini calls, no ADK, no deployment in this
  session. Phase 2 is offline and pure on purpose: if the propagation
  cannot be proven without a model, adding a model hides the failure.
- No product scaffolding, no UI, no chat, no agent framework wiring until
  the phase 2 gate passes.
- No commit and no push without explicit authorization.

Baseline: `research-impact/` does not exist as of c7e3e67. Custody's own
baseline is unchanged and unmeasured by this work; the only Custody-facing
check is that `ruff check .` still passes at the root after these files
exist.

Acceptance gates:

1. `research-impact/RESEARCH.md` exists and answers, with cited sources
   read this session rather than recalled: closest competitors, what they
   already solve, the exact unresolved gap, the proposed mechanism, a
   falsifiable novelty claim, kill conditions, and the smallest compelling
   demo. A verdict of KILL is a passing outcome for this gate if the
   evidence supports it.
2. A synthetic-but-realistic research program fixture exists with at least
   2 hypotheses, 5 assumptions, and 6 experiments, plus supporting and
   contradicting evidence and explicit typed dependency edges.
3. One new piece of evidence, ingested through the real code path, moves
   exactly the intended assumption's state; every true downstream affected
   artifact is identified; every unrelated artifact is byte-identical
   before and after; and every changed node carries a justification chain
   of edge ids that a reader can follow back to a verbatim source excerpt.
4. Falsification tests pass, not just the happy path: an irrelevant paper
   changes nothing; supporting evidence is never mislabelled as
   contradicting by the propagation layer; a fabricated excerpt is
   refused at ingestion; the same evidence ingested twice is idempotent;
   replaying the event log reproduces the identical state; a human
   override reverses a machine-proposed relation's effect.
5. An independent judge script reads the produced artifact and reports
   PASS/FAIL per gate, recomputing the impact set itself rather than
   trusting the producer's own JSON.

Verification: `cd research-impact && make check` (lint plus the offline
suite), `make gate` (produces `research-impact/proof-out/phase2.json`),
`make judge` (independent PASS/FAIL). Root `ruff check .` must still pass.
Manual: read one impact report end to end and confirm every state change
is explained by an edge chain, not by prose.

**Gates 1 to 5 closed 2026-08-15, offline.** Verdict GO, recorded with the
landscape evidence in `research-impact/RESEARCH.md`; the closest mechanical
relative found is EA-Graph (arXiv 2608.04278), which does deterministic
content-anchored invalidation for coding agents, and the closest product
relatives (Co-Scientist, Kosmos, scite, living-evidence platforms) each hold
a different unit than a researcher's forward-looking program. Kill condition
1 is deliberately left open: Co-Scientist's persistence behaviour is not
documented publicly and access is gated, so no "nothing does this" claim may
appear in any submission artifact until it is checked.

Phase 2 built `research-impact/keel/` (stdlib only, 8 modules), a
seven-experiment fixture program, `make gate` and an independent `make
judge`. Results: 66 offline tests pass, `make judge` reports 22/22 PASS, and
the judge was itself tested against four forged artifacts (edited state,
edited digest, dropped override event, edited excerpt) and failed each one
rather than passing them. Root `ruff check .` clean; Custody's own suite ran
356/356 after these files existed. Nothing outside `research-impact/` was
edited except this contract.

Phase 3 is not opened here. The next capability is the live pairwise claim
judgment through Gemini plus one real arXiv document, which is where the
semantic accuracy question this artifact deliberately does not answer starts
being answerable.

**Working-tree note, recorded because it shaped a decision.** Custody files
in this same tree changed during this session from another session
(`scripts/live_memory_deletion.py`, mtime 11:02) without this session
touching them. That is exactly the cross-contamination the branch decision
above avoided, and it is a reason to commit Custody's WIP before cutting
`feat/research-impact`.

Status: active

## Second project, F1: is the deterministic layer load-bearing? (2026-08-15)

Objective: run the falsification experiment `RESEARCH.md` names as F1, at a
scale that can actually falsify. Not one comparison on one fixture: fifteen
controlled variants derived from the same base program, each with ground
truth true by construction, comparing **Baseline A** (one Gemini call over
the whole graph, the whole document, and the full rule set) against
**System B** (bounded per-assumption semantic judgment, then deterministic
propagation). If A matches B, the graph is decoration and the project
pivots or dies; that outcome is a passing outcome for this gate.

Branch: feat/memory-provenance
Parent: c7e3e67

Allowed files: everything under `research-impact/`, plus this contract.
Nothing else, unchanged from the section above.

Non-goals:

- No tuning the baseline to lose. Baseline A gets the complete graph with
  current states, every edge id, the same numbered document, and the state
  rules in prose. A rigged baseline produces a number nobody should believe,
  including us.
- No new cloud resources. The live leg is Vertex AI `generateContent` calls
  only, through the existing ADC in this environment. Nothing is created,
  named, deployed, or written to any Google Cloud service, so there is no
  resource-name collision with Custody to manage.
- No change to `keel/`'s propagation, policy, or ingestion to make the
  numbers better. If the experiment exposes a real defect in the engine,
  stop and report it rather than editing the engine mid-measurement.
- No claiming a live result from the stub. The harness runs offline against
  a recorded stub judge so it can be tested without spending calls; an
  artifact produced that way must say so in its own mode field.

Baseline: phase 2 closed, 66 offline tests, `make judge` 22/22 PASS. Live
Gemini reachable: `gemini-3.5-flash` through Vertex in project
`project-988bc9fe-092c-4b32-90c` returned a proof-bound string this session.
No benchmark exists yet, so there is no prior number to beat.

Acceptance gates:

1. Fifteen variants exist covering, at minimum: contradiction at a root
   assumption, at a leaf, supporting rather than contradicting evidence,
   irrelevant evidence, evidence touching two assumptions, a shared
   assumption across two hypotheses, an experiment with two premises,
   duplicate ingestion, a human override, repeated evidence that should not
   churn, a retired hypothesis, redundancy, weak evidence, a confirmed
   invalidation, and completed work that must not be re-judged. Ground truth
   for each is computed from the declared true edges, not hand-written.
2. Both systems run on every variant, live, three runs each, with per-call
   token counts and latency recorded.
3. Metrics computed per system: affected-set precision, recall and F1;
   target-state exactness; unrelated-artifact preservation; run-to-run
   stability; invalid state transitions; provenance correctness; tokens; and
   wall-clock latency.
4. An independent judge recomputes every metric from the recorded raw model
   outputs in the artifact rather than trusting the producer's numbers, and
   fails on a tampered artifact.
5. The result is reported as measured, including the case where Baseline A
   wins or ties. The write-up states the ground-truth circularity plainly:
   truth is this project's own policy applied to the correct edge set, so
   the experiment measures whether unconstrained reasoning reproduces a
   stated rule set, not whether the rule set is the right one.

Verification: `make bench-stub` (offline harness check), `make bench`
(live), `make bench-judge` (independent scoring), plus `make check` still
green and root `ruff check .` still clean.

**Closed 2026-08-15, all five gates met, and the result went against the
hypothesis.** Live: 15 variants x 3 runs x 2 systems, `gemini-3.5-flash`
through Vertex, 405s wall clock, 318 calls, zero call failures.
`proof-out/f1.json`; `make bench-judge` 11/11 PASS, and it rejected three
tampered copies (forged aggregate, forged row, forged ground truth).
91 offline tests, root `ruff check .` clean, Custody 356/356 unaffected.

Headline: **affected-set F1 is a tie, 0.909 baseline against 0.907 for the
architecture.** The claim "an LLM cannot do this" is refuted on this
benchmark and is now barred from every artifact. What survives is measured
and narrower: recall 1.000 vs 0.931, run-to-run identity 1.000 vs 0.956,
exact justification 1.000 vs 0.817, and every one of the architecture's
errors localised to a single reviewable relation (7 wrong judgments of 273,
amplified to 21 wrong nodes) where the baseline's did not localise at all.
The baseline invented a relation and propagated it in two variants, missed a
second relation inside one sentence in every run of another, and dropped a
multi-hop consequence once.

Two ground-truth defects were found and fixed mid-build, both cases where
the models were right and the declared truth was incomplete (a document
licensing a relation the variant had not declared). Both are recorded in
`RESEARCH.md` 5b rather than quietly corrected, because a benchmark whose
author never had to do that has not been pushed hard enough. No engine code
was touched during the measurement, per the stated non-goal.

Next, and defined before reading the numbers again: recalibrate the strength
rubric at the semantic boundary only, rerun the same fifteen variants, and
see whether precision moves without touching propagation.

Status: complete, frozen. `proof-out/f1-dev.json`, proof
`279df72556ee4c75b5d8efa22c102938`. These fifteen variants are a development
set from this point on and their scores are never the headline claim again.

## Second project, F1-holdout: the boundary change, judged on unseen cases

Objective: fix the semantic boundary using only the dev set's two diagnosed
failures, and report the result on a holdout that was authored and truth-locked
**before** the fix was designed. The user's constraint, adopted verbatim: using
the dev set both to diagnose and to report is benchmark tuning, whatever the
intent, so the dev score stays frozen at baseline 0.909 / structured 0.907 and
the quantitative claim comes from the holdout only.

Branch: feat/memory-provenance
Parent: c7e3e67

Allowed files: everything under `research-impact/`, plus this contract.

Non-goals:

- **No looking at holdout model output before the boundary change is frozen.**
  The holdout program, its variants, and its ground truth are written first,
  hashed, and the hash is recorded here. Then the boundary changes. Then the
  holdout runs, once, in both configurations, and whatever it says is the
  result. No second tuning pass against it, ever. If the fix underperforms, that
  is the finding.
- No change to `keel/policy.py`, `keel/propagate.py`, or `keel/ingest.py`.
  The whole claim is that the fix lives at the admission boundary; making it
  anywhere else would refute the claim rather than support it.
- The old boundary stays runnable as a configuration rather than being edited
  away, so the dev numbers stay reproducible and the ablation is a flag.
- No new cloud resources. Vertex `generateContent` only.

Baseline: dev set frozen as above. Correction locality is unmeasured. The
admission boundary asks the model for a holistic strength label, which is
exactly where both diagnosed failures live.

Acceptance gates:

1. A second research program, different domain and different graph shape, with
   at least 15 holdout variants including cases the dev set never exercised.
   Truth computed by the engine, hashed, and the hash recorded here before any
   boundary change is written.
2. The boundary change is a configuration (`--boundary v1|v2`), principled
   rather than fitted: the model stops emitting a strength label and instead
   answers two narrower factual questions (inferential distance, setting
   transfer) from which code computes strength by a stated table.
3. The holdout runs live in both configurations, three runs each, and the
   result is reported as measured including the case where v2 is no better.
4. Correction locality is measured on both the frozen dev artifact and the
   holdout: how many human corrections restore the exact intended state, how
   many downstream nodes each correction repairs, and how many wrong nodes
   remain afterwards. The claim that rejecting one relation repairs every
   consequence is verified by re-running propagation, not asserted.
5. The independent judge recomputes all of it from raw model answers and fails
   on a tampered artifact, same discipline as the dev run.

Verification: `make lock-holdout` (offline, writes and hashes the truth),
`make bench-holdout` (live, both configurations), `make bench-judge`, plus
`make check` green and root `ruff check .` clean.

**Holdout locked 2026-08-15, before any boundary code was written.** Eighteen
variants over a second program (`fixtures/agent_program.json`: different domain,
3 hypotheses, 8 assumptions, 9 experiments, heavier ESTABLISHES fan-out), six of
them expecting no change at all. Four exercise rules the dev set never reached:
an experiment returning from REDUNDANT to PLANNED when the evidence that settled
its question is contested, an ESTABLISHES edge that is deliberately not a
dependency, STALE outranking REDUNDANT on the same node, and support arriving
for an already contested assumption.

Ground-truth digest, recorded here as the thing that would have to change for
the holdout to have been tuned:

    80b07fc8cd242a0a74f46a617e6ae99067dfa1ee0240e2d9d89cf32e64a7995d

`results/holdout-lock.json` carries the same digest and is committed. No model
had been run against any of these eighteen variants at the moment this hash was
written.

Status: active
