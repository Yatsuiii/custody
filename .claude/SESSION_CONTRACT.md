# Custody: id-based citation resolution for the receipt collector

Opened 2026-08-29.

Objective: `research/experiments/RECEIPT_COLLECTOR_PARAPHRASE_FALSIFIER`
(branch `research/receipt-collector-falsifier`) found the
context/receipt collector fails safe (UNTRUSTED) rather than falsely
trusted when a retrieved fact is paraphrased -- but the practical
consequence is that cross-session citation lineage likely never engages
against real Memory Bank retrievals, since Memory Bank paraphrases nearly
everything and matching is currently exact-digest-only. Confirmed via
direct SDK inspection that Vertex AI Memory Bank's real `Memory` type
(`vertexai/_genai/types/common.py`) carries a `metadata` field that
round-trips what `AgentEngineMemoryBank.write_record` already writes
(`custody_record_id`), and `RetrieveMemoriesResponseRetrievedMemory.memory.metadata`
exposes it back on read -- the data needed to fix this is already being
written, just not read back. Wires an id-based resolution path through
`custody/origin.py`'s resolver logic as a first-class alternative to
digest matching, alongside a multi-item retrieval extraction (a single
`load_memory` call can cite several distinct prior records at once,
which `_attribute`'s current one-response-one-derived_from model does
not represent).

Branch: fix/receipt-collector-id-resolution
Parent: main @ c016a4e

Allowed files:
- custody/origin.py
- custody/adapters/memory_bank.py
- custody/adapters/adk.py
- scripts/live_memory_bank.py
- tests/test_graph.py
- tests/test_origin.py
- tests/test_adk_memory_bank.py
- tests/test_agent_engine_memory_bank.py
- .claude/SESSION_CONTRACT.md (this file)

Non-goals:
- No change to `custody/graph.py` or `custody/firestore_store.py` --
  both already expose `.record(record_id)`, which is sufficient for the
  new id-based lookup; no new graph API is needed.
- No live, model-driven end-to-end verification against a real ADK
  `Runner` with `tools=[load_memory_tool]` actually invoking `load_memory`
  through the model. That path is not currently exercised anywhere in
  this project's live evidence (G1's agent has no tools registered) and
  verifying it live is out of scope here. This work is verified at the
  structural/offline level: the exact dict shape Custody's own adapters
  produce and consume, tested directly, documented as a contract rather
  than reverse-engineered from ADK's internal serialization with
  certainty this session does not have.
- No change to what gets admitted/refused at write time (`custody/service.py`'s
  write-time filtering is unrelated and untouched).
- `CustodyMemoryBank.search_memory` (adk.py) keeps its current runtime
  behavior (a passthrough returning whatever the downstream returns,
  despite its `-> SearchMemoryResponse` type annotation already claiming
  otherwise before this session touched it) rather than being rebuilt to
  actually construct ADK `SearchMemoryResponse`/`MemoryEntry` objects.
  That closes a real, separate, pre-existing type-contract gap, but doing
  it changes the live G1 script's actual runtime data shapes for zero
  live-evidence benefit today (G1's agent has no `tools=[load_memory_tool]`,
  so nothing currently consumes a real `SearchMemoryResponse`). Scoped out
  explicitly rather than silently left inconsistent: `scripts/
  live_memory_bank.py`'s `RecordWritingMemoryBank.search_memory` is
  adapted only to unwrap `RetrievedFact.text` back into `list[str]`,
  preserving 100% of existing live-script behavior.
- No merge into main or push beyond this branch until explicitly authorized.

Baseline: `make check` on `main` before any change: 381/381 (verified in
the original checkout earlier this session).

Acceptance gates:
1. `CustodyGraph.record`/`FirestoreCustodyGraph.record` used for id-based
   lookup, not a new resolver method -- reuses the existing, already-
   tested by-id API rather than adding a parallel one.
2. A retrieval whose response cites multiple prior records by id resolves
   to a single new record whose `derived_from` contains all of them,
   deduplicated, order-preserved -- not just the first or last.
3. If ANY cited item fails to resolve (by id or, as a fallback, by
   digest), the whole citation stays untrusted and empty-derived_from,
   matching the project's existing "conservative direction is deliberate"
   rule for mixed content -- no partial-trust state introduced.
4. All existing tests in `tests/test_graph.py` and `tests/test_origin.py`
   keep passing unmodified where they test the old single bare-string
   `load_memory` response shape -- full backward compatibility, not a
   breaking change to the resolver contract.
5. New tests cover: id-match takes priority over digest-match when both
   would apply; id-match alone (paraphrased text, real id) now resolves
   correctly, closing the gap the falsifier found; multi-item citation
   with one item unresolvable stays fully untrusted.

Verification: `make check` (all suites, not just the affected files),
plus manual inspection of the new tests' event fixtures against the
documented contract in this file.

Status: active

---

# Custody: cite the RSM crux findings in future-directions copy

Opened 2026-08-29.

Objective: Add a small, correctly-hedged pointer to the RSM crux
falsifier findings (branch `research/rsm-crux-falsifier`, pushed to
origin, not merged) in RESEARCH.md's and the Devpost story's existing
forward-looking sections. Cites real preliminary evidence for a future
research direction; does not claim the direction is solved, validated at
scale, or novel (no literature search has been run on it).

Branch: main
Parent: b9601fb (E2D + EXT1-4, already on origin/main)

Allowed files:
- RESEARCH.md
- .claude/SESSION_CONTRACT.md (this file)
- (Devpost's live story text, edited directly via browser, not a repo
  file -- same discipline: correctly hedged, no overclaim)

Non-goals:
- No claim that RSM/claim-carrying-memory is solved, novel, or ready to
  build. Every reference must carry the same hedges RESULT.md files
  already state (narrow synthetic test, no fused-text decomposition
  tested, no adversarial robustness testing, no literature search run).
- No merge of research/rsm-crux-falsifier into main. It stays a cited,
  linked, separate branch.
- No changes to any custody/*.py or E2D's own artifacts.

Baseline: `make check` 381/381 before and after (docs-only change).

Acceptance gates:
1. RESEARCH.md gains a forward-looking pointer to the RSM crux findings,
   correctly scoped (cites the 0/8 vs 4/8 result and the explicit
   caveat that fused-text decomposition remains untested).
2. The live Devpost story's "What's next" section gets the same
   treatment, verified via the public preview page after saving.
3. `make check` still 381/381.

Verification: `make check`; re-fetch the Devpost public preview page and
confirm the new text reads as intended, not truncated or malformed.

Status: active

---

# Custody: execute E2D, the preregistered structural-envelope falsifier

Opened 2026-08-28.

Objective: Execute E2D exactly as preregistered in
`research/design/DESIGN_FALSIFIER.md` (pulled from commit `ca54d84` for
reference). Build Architecture A (the structural-envelope authority
mechanism: NONE < INFORM < ACT lattice, meet over parents, structural
receipts captured at transform time, no semantic/ML inference) as
isolated experimental code, run it against the frozen 6-element scenario,
and report whichever preregistered verdict it actually hits — PASS,
CAUTION, or KILL. Do not alter the frozen scenario, metrics, or gates to
make it pass; changing a fixture creates a new experiment number per the
design doc's own rule.

Branch: research/e2d-structural-envelope-execution
Parent: HEAD of merge/feat-into-main at the time this branch was cut
(includes the E1 multi-parent fix; 381 passing tests, matching the
falsifier's stated baseline characteristics).

Allowed files:
- research/design/*.md (reference copies pulled from ca54d84, read-only —
  do not edit these; they are the frozen preregistration)
- research/experiments/E2D_DESIGN_FALSIFIER/PLAN.md
- research/experiments/E2D_DESIGN_FALSIFIER/run.py
- research/experiments/E2D_DESIGN_FALSIFIER/RESULT.md
- research/experiments/E2D_DESIGN_FALSIFIER/result.json
- RESEARCH.md (update the verdict to reflect E2D's real result, once run)
- research/experiments/E2D_EXT1_WINDOW_WIDENING/PLAN.md
- research/experiments/E2D_EXT1_WINDOW_WIDENING/run.py
- research/experiments/E2D_EXT1_WINDOW_WIDENING/RESULT.md
- research/experiments/E2D_EXT1_WINDOW_WIDENING/result.json
- research/experiments/E2D_EXT2_OVERLAPPING_WINDOWS/PLAN.md
- research/experiments/E2D_EXT2_OVERLAPPING_WINDOWS/run.py
- research/experiments/E2D_EXT2_OVERLAPPING_WINDOWS/RESULT.md
- research/experiments/E2D_EXT2_OVERLAPPING_WINDOWS/result.json
- research/experiments/E2D_EXT3_LEGACY_UNKNOWN_TIMESTAMP/PLAN.md
- research/experiments/E2D_EXT3_LEGACY_UNKNOWN_TIMESTAMP/run.py
- research/experiments/E2D_EXT3_LEGACY_UNKNOWN_TIMESTAMP/RESULT.md
- research/experiments/E2D_EXT3_LEGACY_UNKNOWN_TIMESTAMP/result.json
- research/experiments/E2D_EXT4_MANIFEST_PARENTS/PLAN.md
- research/experiments/E2D_EXT4_MANIFEST_PARENTS/run.py
- research/experiments/E2D_EXT4_MANIFEST_PARENTS/RESULT.md
- research/experiments/E2D_EXT4_MANIFEST_PARENTS/result.json
- .claude/SESSION_CONTRACT.md (this file)

Non-goals:
- No production implementation. `custody/*.py` is not touched by this
  branch, per the design doc's explicit authorization boundary ("No
  production implementation is authorized by this design").
- No changes to the frozen scenario, metrics, or PASS/CAUTION/KILL gates
  to improve the result. A failed metric is reported, not massaged.
- No semantic inference, embeddings, fuzzy matching, or LLM participation
  in the mechanism itself — explicitly a KILL condition if required.
- No merge back into main/feat-into-main without an explicit, separate
  decision after the verdict is known.
- No push to remote until explicitly authorized.

Baseline: `git log --oneline -1` on this branch's parent is the tip of
merge/feat-into-main as pushed to origin/main; `make check` is 381/381 on
that parent before any experimental code is added.

Acceptance gates:
1. `research/experiments/E2D_DESIGN_FALSIFIER/PLAN.md` exists and mirrors
   the frozen scenario's fixed record ids/timestamps as literals (no
   invented substitutes).
2. `run.py` implements Architecture A only — the lattice, meet, receipts,
   root binding (ORIGIN/RELAY), RepairPlan with the 4 crash/replay fault
   points — with no LLM/network/embedding call anywhere in the mechanism.
3. All 8 metrics (`direct_parent_recall`, `affected_recall`,
   `false_act_permits`, `same_record_authority_increases`,
   `benign_inform_retained`, `outside_sibling_preserved`,
   `replay_digest_stable`, `unsafe_fault_windows`) are computed as exact
   counts/booleans on the frozen fixture, not estimated.
4. `result.json` contains every field the design doc's "Planned proof
   artifact" section requires; `RESULT.md` states the verdict honestly
   against the fixed PASS/CAUTION/KILL gates, quoting whichever condition
   was hit.
5. `make check` still 381/381 (no production file touched, confirmed by
   `git diff --stat` showing only `research/` and `.claude/` paths).

Verification: run `python3
research/experiments/E2D_DESIGN_FALSIFIER/run.py`, inspect
`result.json`/`RESULT.md` against the gate table, and re-run once for
`replay_digest_stable`.

Status: active

---

# Custody: reconcile main for hackathon submission

Opened 2026-08-28.

Objective: Reconcile the Custody submission state before the Devpost
deadline (Sep 1 2026, 05:30 GMT+5:30). `feat/memory-provenance` (the
08-21 hardening/G5 freeze) and `hardening/fleet-track-pre-submission`
(the Fleet/Timeline judge-visualization pages) had both diverged from
`main` without being merged back; `main` itself had drifted onto an
unrelated DecisionTrace-split history. This session merges all three
into `main`, refreshes live evidence, redeploys, and fills the Devpost
draft. Does not touch DecisionTrace.

Branch: merge/feat-into-main
Parent: 1ea8b1511dd18909e19d3c8ab60665c4c27ab969 (feat/memory-provenance
tip) merged with 4a624558b781280c7033c69204dccfedff20b376 (main tip)
and origin/hardening/fleet-track-pre-submission tip fba047f.

Allowed files: everything under /run/media/Yatsuiii/Windows-SSD/custody.

Non-goals:
- No DecisionTrace code/doc changes.
- No changes to research/ branches' own content, only reconciling what
  main/feat/memory-provenance/hardening/fleet-track-pre-submission
  already built.

Baseline: `make check` passes on the merged tree before any push.

Acceptance gates:
1. `make check` green on the merged `main`.
2. `make gates` shows G1-G4 PASS, G5 at 4 of 4 groups (structural
   BLOCKED on elapsed time is expected and correct).
3. Live site (custody-incident-cave2.vercel.app) serves fleet.html,
   timeline.html, incident.html, architecture.html — all 200, no
   console errors.
4. Devpost draft's Project details / Additional info sections have
   correct links, category, and evidence; video and final Submit are
   explicitly left for the user.

Status: active

---

# DecisionTrace action-compliance falsification experiment (Phase 0/1 setup)

Opened 2026-08-22.

Objective: Stand up the preregistered DecisionTrace action-compliance
falsification experiment (Phase 0 freeze + Phase 1 preregistration only
for this session). This is a research experiment, separate from and does
not modify the frozen product. Does NOT include running the full
30-50 task, 3-arm, 2-3-run comparative experiment yet — that requires a
separate explicit scope/compute authorization (execution harness choice,
OSS repo clone/access, coding-agent budget, cost approval).

Branch: research/decisiontrace-action-compliance

Parent: 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6 (tip of
explore/decision-trace-v0, the merged authority-proof product commit)

Allowed files:
- decision-trace/ACTION_COMPLIANCE_PROTOCOL.md (new)
- decision-trace/ACTION_COMPLIANCE_SPEC.md (new)
- decision-trace/ACTION_COMPLIANCE_LEDGER.md (new, skeleton only this
  session — task ledger rows are populated in the pilot/full-build phase,
  not this session)
- decision-trace/.claude/SESSION_CONTRACT.md
- .claude/SESSION_CONTRACT.md (this file)
- decision-trace/scripts/verify_authority_freeze.py (new, guard script)

Non-goals (explicit, this session):
- Do not modify explore/decision-trace-v0 or any production code/config.
- Do not modify app/authority.py, app/collaborate.py, app/ui.py, or any
  authority-resolution test file (frozen; hash-guarded, not edited).
- Do not deploy, touch production Firestore, or change demo behavior.
- Do not run the full comparative experiment (Phases 2-19 of the
  external protocol) this session.
- Do not build/select the 30-50 task benchmark set this session beyond
  documenting the construction protocol and a ledger skeleton.
- Do not touch Custody.
- Do not push to remote until explicitly authorized.

Baseline: `git log --oneline -1` on this branch is 9bdec25 (or a
descendant produced only by this session's own doc commits);
`sha256sum decision-trace/app/authority.py decision-trace/app/collaborate.py
decision-trace/app/ui.py` matches the values recorded in
ACTION_COMPLIANCE_PROTOCOL.md.

---

# Custody: Fleet/Timeline judge-visualization hardening

Branch: hardening/fleet-track-pre-submission
Parent: b0c7019 (repository initialized 2026-08-09)

Note, 2026-08-21: `hardening/fleet-track-pre-submission` and
`feat/memory-provenance` currently point to the same integrated commit
(`1ea8b15`); this field is kept pointed at the branch actually checked out
so the evidence-gate hook (which reads only this first `Branch:` line in
the file) matches the working tree.

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
1. research/decisiontrace-action-compliance exists, branched exactly
   from 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6, not pushed.
2. ACTION_COMPLIANCE_PROTOCOL.md records the frozen authority-resolver
   file hashes, frozen experimental settings, and exists before any
   task discovery.
3. ACTION_COMPLIANCE_SPEC.md preregisters the primary hypothesis,
   compliant-success metric, and the strict GO gate, unedited after
   this session (future edits require a new session-contract entry).
4. scripts/verify_authority_freeze.py exits nonzero if any frozen
   file's hash changes.
5. Production branch explore/decision-trace-v0 is untouched (verified
   by diff).

Verification: `git diff origin/explore/decision-trace-v0 -- decision-trace/app`
shows no changes; `python decision-trace/scripts/verify_authority_freeze.py`
exits 0; `git merge-base --is-ancestor 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6 HEAD`
exits 0.

Status: complete (Phase 0/1 only — protocol/spec/ledger-skeleton/guard
script written and verified; see result below)

Result: `ACTION_COMPLIANCE_PROTOCOL.md`, `ACTION_COMPLIANCE_SPEC.md`,
`ACTION_COMPLIANCE_LEDGER.md` (skeleton), and
`scripts/verify_authority_freeze.py` written on
`research/decisiontrace-action-compliance` (parent 9bdec25, verified via
`git merge-base --is-ancestor`). Guard script confirmed passing (9/9
frozen authority files match). `git diff origin/explore/decision-trace-v0
-- decision-trace/app` empty — production untouched. Nothing committed
or pushed. User chose to scope the next phase down to a Phase 11 pilot
(5-8 candidate tasks, 1-2 ecosystems) rather than jumping to the full
30-50 task / 360-run comparative experiment, which still needs a
separate execution-harness/compute decision.

## DecisionTrace action-compliance: Phase 11 pilot — machinery validation only (opened 2026-08-22, revised per user's detailed pilot spec same day)

Objective: NOT to estimate DecisionTrace's performance. Only to prove
the benchmark machinery itself is valid, per the user's explicit Phase
11 spec. Build 5-8 candidate coding tasks across 2-3 real OSS
ecosystems. For every task, before any comparative arm output exists,
require all 10 of: (1) pinned real commit; (2) real source-grounded
decision history; (3) authority distinction materially changes correct
code; (4) control receives ALL relevant context; (5) deterministic
task-completion tests; (6) deterministic/mechanical authority-compliance
checks; (7) a technically-valid-but-non-authoritative patch is actually
constructible; (8) task resets/replays reliably in an isolated worktree;
(9) no task-specific answer leaks into prompts; (10) ground truth
written and frozen before any arm runs. Diversity target: one
superseded-design, one reverted-design, one proposal-not-accepted, one
wrong/parallel-scope, one partial-acceptance-if-a-clean-example-exists.
Do NOT cherry-pick for DecisionTrace-favorable cases — actively try to
break the benchmark (reject tasks where the authority distinction
doesn't causally change the patch, where the grader can't mechanically
discriminate, where "all context" doesn't actually fit, or where the
control is artificially disadvantaged). For each surviving task, build
two hand-constructed sanity patches (A: compliant, B: authority-
violating-but-plausible) BEFORE any model run; the grader must accept A,
reject B, and score task correctness independently, or the task is
invalid. Only after sanity gates pass, run ONE coding-agent invocation
per arm per task (not 2-3) purely to validate execution plumbing — these
outputs are pilot-only and must never feed the final statistical result.

Branch: research/decisiontrace-action-compliance
Parent: HEAD (the Phase 0/1 freeze commit-state above, still
uncommitted)

Allowed files:
- decision-trace/ACTION_COMPLIANCE_LEDGER.md (populate pilot task rows)
- decision-trace/pilot/ (new — per-task pinned snapshots, source
  evidence, sanity patches A/B, grader scripts)
- decision-trace/data/action_compliance/pilot/ (new — pilot-only,
  explicitly separate from any future final-benchmark data path)
- decision-trace/data/runs_action_compliance_pilot/ (new — one-run-only
  pilot agent outputs, explicitly separate from final run data)
- decision-trace/.claude/SESSION_CONTRACT.md, .claude/SESSION_CONTRACT.md
- decision-trace/ACTION_COMPLIANCE_PILOT_REPORT.md (new — the 16-point
  report specified by the user, ending in a GO/REWORK/KILL
  recommendation for the harness, not for DecisionTrace itself)

Non-goals:
- Do not modify app/authority.py, app/collaborate.py, app/ui.py, or any
  frozen authority test file (still hash-guarded).
- Do not clone full multi-GB repositories where a shallow/sparse
  pinned-commit fetch suffices.
- Do not proceed to the full 30-50 task / 3-run comparative benchmark
  automatically — stop after the pilot report.
- Do not reuse pilot model outputs in any final benchmark result.
- Do not touch production or Custody.
- No commit/push without explicit authorization.

Baseline: scripts/verify_authority_freeze.py exits 0.

Acceptance gates:
1. 5-8 candidate tasks attempted across 2-3 ecosystems; each surviving
   task satisfies all 10 required properties above, verified not
   asserted.
2. Sanity patches A/B built and graded correctly (accept A, reject B,
   independent correctness score) before any model run, for every
   surviving task.
3. Exactly one run per arm per task, explicitly stored under the
   pilot-only data paths above.
4. ACTION_COMPLIANCE_PILOT_REPORT.md covers all 16 points the user
   specified (attempted/rejected/passed counts, ecosystems, scenario
   categories, sanity-patch discrimination result, timing, cost,
   reproducibility, isolation safety, grader ambiguity, leakage,
   tooling problems, backend recommendation, and cost projections for
   30/40/50 tasks x 3 arms x 3 runs), ending in one GO/REWORK/KILL call.
5. scripts/verify_authority_freeze.py still exits 0 at the end.

Verification: re-check every cited PR/commit/KEP link is real; confirm
task rejections are logged with reasons before any agent output existed
for that task; confirm pilot data never lands under a path implying
final-benchmark status.

Status: complete

Result: 1 task (`task-01-k8s-postfilter-victims`, REVERTED_DESIGN,
kubernetes/kubernetes) survived all 10 gates out of 9 candidates
investigated; 8 rejected with logged reasons (mostly rustc-bootstrap
infeasibility, thin evidence, bugfix-not-governance reverts). Sanity
patches A/B built and independently re-graded by me (not just trusted
from the construction agent): grader correctly discriminates
AUTHORITY_COMPLIANT=true/false. One run per arm (A/B/C) executed for
plumbing validation only, independently re-graded against fresh
worktrees, all three compliant/test-passing — descriptive only, no
statistical claim made (n=1). Full 16-point report written to
`ACTION_COMPLIANCE_PILOT_REPORT.md`, recommendation REWORK (harness
validated, task inventory far short of the diversity/count needed for
the preregistered GO gate). Nothing committed or pushed. User's
follow-up instruction: do NOT run more comparative arms yet; run a
task-discovery-only sweep instead (next entry).

## DecisionTrace action-compliance: large-scale task discovery sweep (opened 2026-08-22)

Objective: per the user's explicit follow-up spec, this session expands
TASK INVENTORY ONLY. Investigate at least 20-30 NEW candidate
histories/tasks across at least 5 ecosystems, targeting a minimum of 6
fully valid tasks (preferably 8-12) covering at least 5 of the 9 target
authority-error categories (missing so far: SUPERSEDED_DESIGN,
PROPOSAL_NOT_ACCEPTED, PARTIAL_ACCEPTANCE, WRONG_AUTHORITY_SCOPE,
PARALLEL_DECISIONS, IMPLEMENTATION_VS_POLICY, EXPLICIT_RESTORATION,
MENTION_WITHOUT_TRANSITION; have REVERTED_DESIGN already). Do not
over-fill with reverts — target no category above ~30% of the final set
if enough valid cases exist. Every candidate gets a ledger row
(including rejections, classified per the user's rejection taxonomy),
whether it survives or not. Every surviving candidate gets hand-built
compliant (A) and violating (B) sanity patches, graded by the frozen
mechanical grader, before being counted as valid. Strongly prefer tasks
where the violating patch ALSO passes ordinary functional tests (the
strongest DecisionTrace case: technically valid code that still
violates authority). Tighten the TASK_COMPLETED grading weakness found
in the pilot (identifier-in-comment false-positive risk) per task.

Branch: research/decisiontrace-action-compliance
Parent: HEAD (the Phase 11 pilot commit-state above, still uncommitted)

Allowed files:
- decision-trace/ACTION_COMPLIANCE_LEDGER.md (every candidate, valid or
  rejected, gets a row)
- decision-trace/pilot/task-<NN>-<slug>/ (new, one dir per surviving
  candidate — TASK.md, grader.py, worktree_setup.sh, sanity patches,
  context_bundle/)
- decision-trace/.claude/SESSION_CONTRACT.md, .claude/SESSION_CONTRACT.md
- decision-trace/ACTION_COMPLIANCE_TASK_DISCOVERY_REPORT.md (new — the
  30-point report the user specified, ending in one of GO/REWORK/KILL
  for the task inventory itself)

Non-goals (hard, explicit):
- DO NOT run Arm A, Arm B, or Arm C (or any comparative coding-agent
  invocation) at any point this session — no model-under-test output
  may exist while tasks are being selected, to prevent case selection
  bias. This is the single most important constraint of this session.
- Do NOT change ACTION_COMPLIANCE_PROTOCOL.md or ACTION_COMPLIANCE_SPEC.md
  (GO thresholds, arms, primary metric, fairness requirements) — frozen.
  If a genuine bug unrelated to outcomes is found in either, document it
  and ask, do not silently fix it.
- Do NOT modify app/authority.py, app/collaborate.py, app/ui.py, or any
  frozen authority test file (still hash-guarded).
- Do NOT touch production or Custody.
- Do NOT proceed to a full comparative run even if enough tasks survive
  — stop and report the inventory once the sweep is done.
- No commit/push without explicit authorization.

Baseline: scripts/verify_authority_freeze.py exits 0; existing
task-01 pilot task and its ledger row/data remain untouched (this
session adds new tasks, does not modify task-01's artifacts).

Acceptance gates:
1. At least 20 new candidates investigated across at least 5 ecosystems,
   every one logged in the ledger (valid or rejected, with rejection
   taxonomy code if rejected).
2. Structural gates G1-G10 (per the user's spec) verified, not asserted,
   for every candidate counted as valid.
3. Every valid candidate has hand-built sanity patches A/B, graded, with
   the required TASK_COMPLETED/TESTS_PASS/AUTHORITY_COMPLIANT pattern
   confirmed (A: all true; B: AUTHORITY_COMPLIANT false, ideally
   TASK_COMPLETED/TESTS_PASS still true).
4. ACTION_COMPLIANCE_TASK_DISCOVERY_REPORT.md covers all 30 points the
   user specified, ending in exactly one of: GO — TASK INVENTORY VALID /
   REWORK — MORE VALID TASKS REQUIRED / KILL — REAL AUTHORITY-SENSITIVE
   CODING TASKS TOO SCARCE, plus an explicit yes/no answer to "did we
   find enough real situations where the organizational decision
   changes what a coding agent should actually implement?"
5. scripts/verify_authority_freeze.py still exits 0 at the end; no Arm
   A/B/C output exists anywhere under this session's new files.

Verification: grep the entire session's new output for any coding-agent
patch/diff that isn't a hand-built sanity patch (there should be none);
re-check a sample of cited PR/RFC/proposal links are real; confirm
category/ecosystem distribution matches what's reported.

Status: active

---

# DecisionTrace: port authority-proof engine into the product

Opened 2026-08-22.

Objective: Product-integration session. Port the general authority-proof
architecture developed and validated on `research/decisiontrace-authority-
proof` (checkpoint `f417acf`, live-integration-verified at `96cc921`) into
the actual DecisionTrace product, without touching the frozen submission
branch. Minimum required product changes: scope-local authority semantics,
`partial_acceptance` support, deterministic `AuthorityProof` generation,
a Gemini explanation layer that narrates but never decides authority, and
Firestore persistence compatible with existing production records. Wire
this into the existing collaborative worker story (Evidence Scout ->
Lifecycle Resolver -> Provenance Challenger -> Gemini Reconciler) and the
smallest possible judge-facing UI addition. No new benchmark, no Custody
changes, no research dataset ported into the product, no application
rewrite beyond the authority path.

Branch: integration/decisiontrace-authority-proof
Parent: 1c33d3de169ebbdb874992e9383b632d163b2658
(`explore/decision-trace-v0`, the frozen hackathon submission — never
developed on directly, remains the rollback point)

Allowed files:
- `decision-trace/app/authority.py` (new — ported from research, port
  audit determines exact scope)
- `decision-trace/app/models.py` (edit — `partial_acceptance` field)
- `decision-trace/app/graph.py` (edit — structured `lifecycle_events`
  field, matching research)
- `decision-trace/app/store.py` (edit — round-trip fix for the new
  field, both JSON and Firestore paths)
- `decision-trace/app/collaborate.py` (edit — wire the authority
  resolver into the Lifecycle Resolver/Provenance Challenger/Gemini
  Reconciler worker story; add an authority-explanation path)
- `decision-trace/app/loader.py` (edit — assign `related_components` to
  loaded frozen-benchmark decisions; found during Phase 10 demo replay
  that the loader never set a scope at all, so `_resolve_authority_for_
  candidates` could never produce an `AuthorityProof` for any real demo
  decision. Minimal, deterministic scope derivation only — no new fields
  on the source JSONL, no re-mining)
- `decision-trace/app/memory.py` (edit — `propose_reconsideration`'s
  candidate must inherit the target decision's `related_components` so
  the reconsideration becomes a visible, correctly-excluded
  `PROPOSED_NOT_ACCEPTED` candidate in the target's own AuthorityProof,
  per Phase 7's reconsideration demo requirement; no change to
  `RECONSIDERS` not being a lifecycle edge, so governing truth is still
  unaffected)
- `decision-trace/app/ui.py` (edit — minimal "CURRENTLY GOVERNING / WHY
  THIS GOVERNS / View full authority proof" addition only, no redesign)
- `decision-trace/app/tests/**` (new/edit — port relevant adversarial +
  regression tests, add product-integration tests)
- `decision-trace/README.md` (edit — remove/replace any 76%-vs-57%-style
  superiority claim with the architectural positioning sentence)
- `decision-trace/.claude/SESSION_CONTRACT.md`, this file
- `decision-trace/PORT_PLAN.md` (new — Phase 2 audit/plan, written
  before any product code changes)
- `decision-trace/INTEGRATION_DECISION.md` or equivalent final-report doc
  (new, end of session)

Non-goals:
- No new benchmark, no new dataset, no rescoring, no prospective-
  superiority claim.
- Do not port benchmark data, prospective runs, research score files,
  failure-mining artifacts, research-only scripts, or old falsifier
  experiments from the research branch.
- Do not touch Custody.
- Do not develop directly on `explore/decision-trace-v0`.
- Do not merge this branch into the frozen product without explicit
  authorization (research/audit only this session; recommendation, not
  action).
- Do not replace the existing production Cloud Run deployment; a preview
  revision/service only, and only after local gates are green.
- Do not push unless explicitly authorized.
- Do not add product features unrelated to the authority-proof path.

Baseline: `git log -1 --format=%H` on this branch ==
`1c33d3de169ebbdb874992e9383b632d163b2658`; `app/authority.py` does not
exist on this branch pre-port (confirmed); `app/requirements.txt` here
matches the research branch's (google-genai, google-cloud-firestore,
numpy, streamlit, pytest) — confirmed byte-identical.

Acceptance gates:
1. `PORT_PLAN.md` written and the minimum-diff port scope decided before
   any product file is edited.
2. Ported authority engine passes an adversarial test suite (ported/
   adapted from research) covering scope-locality, proposal/supersession/
   revert/parallel-scope/partial-acceptance semantics.
3. `AuthorityProof` reaches the Gemini explanation layer without Gemini
   gaining any authority-deciding responsibility (tested).
4. Old 76%-vs-57% superiority claim removed from judge-facing product
   copy (README/UI), replaced with the architectural positioning
   sentence, not a new number.
5. Full product suite green under the correct `.venv` interpreter, real
   integrations exercised (Firestore, Gemini, GitHub), backward
   compatibility with pre-existing (no `partial_acceptance`) Firestore
   records proven without mutating production data.

Verification: `source .venv/bin/activate` (or `.venv/bin/python`
explicitly) for every test run; full suite count recorded; real
Firestore/Gemini/GitHub integration results recorded; local demo replay
of the delayed-preemption scenario; preview deployment (not production)
smoke-tested if reached.

Status: active

---

# Archived — closed, superseded by the entry above

# DecisionTrace: Gemma bonus integration — killed, documenting the decision

Updated 2026-08-17.

Objective: Gemma integration was attempted and killed (no budget, no free
path exists). Update `decision-trace/HANDOFF.md` and project memory to
record the finding accurately so a future session doesn't re-attempt it
without checking budget first, and confirm cleanup (deleted API key, no
leftover cost-bearing artifacts) is complete.

Branch: explore/decision-trace-v0
Parent: unchanged — Firestore/Cloud Run/submission-docs work from earlier
sessions this week, all still uncommitted.

Allowed files: `decision-trace/HANDOFF.md` (status update only), project
memory files under
`/home/Yatsuiii/.claude/projects/-run-media-Yatsuiii-Windows-SSD-custody-search-2/memory/`.
No app code — `vertex.py`, `ingest.py`, `test_ingest.py` are untouched by
the Gemma attempt and stay that way.

Non-goals: no edits to `BUILD_SCOPE.md`, `RESULTS.md`, `decisions.jsonl`,
or the frozen pipeline scripts; no touching `failure-mining/`,
`research-impact/`, `contribution-gate/`, `research-access/`, or
Custody's `feat/memory-provenance`; no new GCP credentials/spend; no
commit/push without explicit authorization.

Baseline: what was tried and found this session — Vertex AI: 404 on
every Gemma publisher-model path across 4 regions (self-host-only, real
GPU cost, not attempted). Gemini Developer API: enabled
`generativelanguage.googleapis.com`, created a scoped API key
(`decisiontrace-gemma-extraction`), confirmed real model names
(`gemma-4-26b-a4b-it`, `gemma-4-31b-it`) and that the key authenticated,
but every generation call failed `429: prepayment credits depleted`
(Gemma's own paid billing bucket, separate from Vertex). Web search
confirmed Gemma isn't on the Gemini API free tier (only Gemini 2.5
Flash/Flash-Lite are free). User has no budget. API key deleted
(`gcloud services api-keys delete`, confirmed via `deleteTime` in the
response); local `.env.gemma` removed; no code written; no cost
incurred.

Acceptance gates:
1. `decision-trace/HANDOFF.md` documents the Gemma kill decision (what
   was tried, why it failed, that cleanup is complete) so a future
   session has the finding, not just a stale "do this" line item.
2. Project memory (`decisiontrace_hackathon_rubric.md`) reflects the same
   finding, so it isn't re-suggested without checking budget/free-path
   status fresh.
3. `git status`/checksums confirm no falsifier file, and no app code
   file, was touched by this session.

Verification: read `HANDOFF.md` back to confirm the Gemma section is
accurate and doesn't overstate/understate what was actually tried.
Confirm via `gcloud services api-keys list` that no `decisiontrace-*` key
remains active in the project.

Status: active

## Surface the research bodies on the trunk (opened 2026-08-27, supersedes the
## feat/memory-provenance version of this entry)

Objective: unchanged. Make the Custody and DecisionTrace research discoverable
from the repository landing page.

Correction to the earlier entry: that entry took feat/memory-provenance as the
base because it is the branch GitHub currently serves as default. The commit
graph says otherwise. feat/memory-provenance is a frozen hackathon submission
artifact whose last ten commits are judge-evidence and freeze work, ending
2026-08-21. main carries 28 commits the default branch does not, ending
2026-08-26, including the DecisionTrace build and the action-compliance
research freeze. main is the trunk; the default-branch setting is a leftover
from judging.

Branch: docs/surface-research-main-20260827

Parent: origin/main (9a86bde)

Allowed files:
- RESEARCH.md (new, at repository root)
- README.md (one pointer section only)
- .claude/SESSION_CONTRACT.md (this entry)

Non-goals: unchanged from the earlier entry, plus:
- Do not change the GitHub default-branch setting. That is a public repository
  setting and belongs to the user, not to this entry.
- Do not merge, rebase, or reconcile main against feat/memory-provenance. The
  two have diverged 28/10 across a 2026-08-15 merge base and reconciling them
  is its own piece of work.

Acceptance gates: unchanged, plus:
6. RESEARCH.md's opening states accurately what is and is not reachable from
   this branch, verified by counting files rather than by assumption.

Verification:
```
cd /home/Yatsuiii/custody
git diff --stat origin/main
grep -oE 'blob/[0-9a-f]{40}/[^)]+' RESEARCH.md | while IFS=/ read -r _ sha rest; do
  git cat-file -e "$sha:$rest" || echo "BROKEN $rest"; done
```
Expected: two tracked files changed plus one new file, and every permalink
resolves.

Status: complete (informational disclosure note, no further action pending)

## Extract DecisionTrace into its own repository (opened 2026-08-27)

Objective: DecisionTrace and Custody are two separate hackathon projects that
share one repository by accident. Move DecisionTrace to Yatsuiii/decisiontrace
with its history intact, remove it from this repository's trunk, and correct
RESEARCH.md, which currently describes both as one project's output.

Branch: main (extraction is a trunk operation; splits are cut to temporary
local branches and pushed to the new remote, never merged back here)

Parent: origin/main at e0b5397

Allowed files:
- RESEARCH.md (rewrite: keep Custody, remove DecisionTrace)
- README.md (pointer section wording only)
- .claude/SESSION_CONTRACT.md (this entry)
- deletion of decision-trace/ from this repository's main

Non-goals:
- Do not delete or rewrite any branch in this repository. The
  research/decisiontrace-* branches stay exactly as they are, which is what
  keeps the existing commit-pinned permalinks resolving after decision-trace/
  leaves main.
- Do not squash or flatten history in the extraction. If subtree split cannot
  preserve the real commits, stop and report rather than pushing a single
  synthetic commit.
- Do not touch custody/ source, tests, or the E1 fix question.
- Do not make the new repository private or public without the user having
  said which. Said: public, on the grounds that this content is already
  public inside this repository, so extraction is not a new disclosure.

Baseline:
```
git ls-tree -r --name-only origin/main | grep -c '^decision-trace/'
```
Expected: 4010 files present before extraction, 0 after.

Acceptance gates:
1. Yatsuiii/decisiontrace exists, is public, and its main carries real
   multi-commit history, not one synthetic commit.
2. Content unique to the diverged research lines is carried across as its own
   branches, not silently dropped. Verified per branch by file count.
3. After removal, every commit-pinned permalink in this repository's
   RESEARCH.md still resolves.
4. RESEARCH.md no longer presents DecisionTrace as this project's research.
5. custody/ is untouched, verified by git diff.

Verification:
```
gh api repos/Yatsuiii/decisiontrace --jq '.visibility'
git ls-tree -r --name-only origin/main | grep -c '^decision-trace/'
git diff --stat e0b5397 -- custody/
```
Expected: public, 0, and an empty diff for custody/.

Status: complete (superseded by later second-project-search sessions below)

## Land the E1 multi-parent lineage fix on the trunk (opened 2026-08-27)

Objective: custody/origin.py on main still carries the multi-parent lineage bug
that E0 reproduced and E1 fixed on 2026-08-22. The fix exists at 31bd1b0 and has
never reached a trunk, so the code a visitor reads is the buggy version while
RESEARCH.md documents the bug as fixed. Land the code fix and its regression
tests only.

Branch: fix/e1-multiparent-lineage

Parent: origin/main at 79ee757

Allowed files:
- custody/origin.py
- tests/test_origin.py
- RESEARCH.md (remove the now-stale Known Limitations bullet)
- .claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not cherry-pick 31bd1b0 whole. It also carries the research/ directory,
  which is a separate concern with its own reasoning. One capability per commit.
- Do not add trust epochs, hypergraph support, or semantic matching. E1 was
  scoped as the minimal fix the E0 diagnosis implied and that scope holds here.
- Do not touch CustodyGraph traversal. E0 established graph.py was already
  multi-parent correct; only what populated derived_from was wrong.
- Do not run or start E2D.

Baseline:
```
cd /home/Yatsuiii/custody && python3 -m pytest -q
```
Expected: the suite passes on main before any change, and the count is recorded
so the delta after the fix is attributable.

Acceptance gates:
1. Baseline recorded before the patch is applied.
2. After the patch, the full suite passes with no regressions and the test count
   rises by the regression tests E1 added.
3. The applied diff is byte-identical to 31bd1b0's custody/ and tests/ portion,
   verified by diff rather than by inspection.
4. RESEARCH.md no longer claims the fix is absent from the trunk.
5. No file outside the allowed list is modified.

Verification:
```
python3 -m pytest -q
git diff --stat origin/main
```

**Closed 2026-08-15. All five gates met. The fix failed and the baseline won.**
Live: 18 variants x 3 runs x 4 configurations, `gemini-3.5-flash`, 1,157s, 972
calls, zero failures. `proof-out/f1-holdout.json`, proof
`80ca3f6b54124055abd0f8271f407212`; summary recomputed from raw answers in
`results/f1-holdout-summary.json`; `make bench-judge` 20/20 on the holdout and
12/12 on the frozen dev artifact.

F1: A:v1 **0.993**, A:v2 0.974, B:v1 0.939, B:v2 0.900. Two things went against
the hypothesis at once. The v2 boundary made both systems worse on unseen cases
(B's semantic errors 17 -> 25), and the baseline beat the architecture by more
than it did on dev. Mechanism, from the raw answers: v1 let the model answer
WEAK, which does not propagate; v2 replaced that with two questions the model
answers optimistically (it likes DIRECT, it likes same_setting, and that pair
computes to STRONG), removing the conservative option. Decomposing a judgment
helps only when the sub-questions are ones the model is cautious about.

What survived, measured on unseen cases: recall 1.000 vs 0.987, zero impossible
states, provenance exactly minimal 0.959 vs 0.899, and the repair property
verified rather than asserted (rejecting the wrong relations restores the
intended state with zero residual, every time). The sharpest finding is that the
dev win and the holdout loss are the same property: the sweep asks about every
assumption, so it never silently skips one and never declines to have an
opinion. Twenty of B's twenty-five holdout errors concern one assumption the
baseline never considered at all.

Two corrections made during judging, both recorded rather than quietly applied.
The judge's asymmetry check asserted that System B's justifications always equal
ground truth's, which is false and which the holdout caught: a wrong semantic
judgment produces a real edge that then appears, correctly, downstream. Replaced
with the two properties that actually hold and both now pass. And a caveat left
deliberately unresolved: some of B's holdout errors are probably incomplete
ground truth rather than model error, which on the dev set was found and fixed
twice before locking, and which the protocol forbids fixing here. The number
stands as measured; the fix is a third set adjudicated for completeness before
locking, not an edit to this one.

Verification: 99 offline tests, `make check` clean, root `ruff check .` clean,
Custody 360/360 unaffected.

Status: complete

## Second project, F3: does persistent explicit state buy anything? Pre-registered

Objective: settle kill condition 5, the one nothing has tested. Every measurement
so far has been single-document, which is the setting that most flatters a model
recomputing from scratch. This runs ten interacting documents over one program,
with a human correction in the middle, against three systems, and asks whether
explicit executable state prevents accumulated inconsistency that a
model-maintained JSON state cannot.

**The baseline that matters is A1, not A0.** Denying the model persistence and
then celebrating that a persistent system wins would prove nothing. A1 gets the
complete canonical state as structured JSON after every step, including every
relation recorded so far and every human correction, plus schema-constrained
output. It is given every reasonable advantage.

- **A0**: recomputes from the current program description each time. Node states
  carry forward; nothing else does. The floor, not the target.
- **A1**: maintains a canonical structured research state. Relations, states and
  corrections all carry forward and are handed back to it every step.
- **B**: bounded per-assumption judgments, deterministic propagation, corrections
  applied as rejected relations before deterministic replay.

Branch: feat/memory-provenance
Parent: c7e3e67

Allowed files: everything under `research-impact/`, plus this contract.

Non-goals:

- No retrieval work. It optimises a system whose accuracy claim is already dead,
  and its ceiling is already measured (`scripts/sweep_cost.py`: 13.9% of calls).
- No handicapping A1. If a prompt or schema choice would make A1 look worse and
  a competent engineer building the A1 product would not make it, do not make it.
- No editing the sequence, its adjudication, or the thresholds below after any
  model has been run against them. Same discipline as the holdout, which caught
  a real error last time.
- No raw pairwise F1 as a headline. That question is answered and lost.

Baseline: F1 dev frozen (A 0.909 / B 0.907), F1 holdout frozen (A:v1 0.993 /
B:v1 0.939). Longitudinal behaviour, correction persistence, regression and
order sensitivity are all unmeasured. No system has ever been run over a
sequence.

**Ground truth upgrade, applied before locking.** Every document x assumption
pair is adjudicated exhaustively, with three labels rather than two: RELATION
(with polarity and strength), NO_RELATION, and AMBIGUOUS. The holdout showed
that a "false positive" is sometimes an undeclared but defensible reading, and
punishing an exhaustive sweep for surfacing one is a benchmark defect, not a
finding. AMBIGUOUS pairs are excluded from the headline scores and reported
separately as behaviour under genuine scientific disagreement.

Acceptance gates:

1. Ten documents that interact: later ones bear on assumptions earlier ones
   moved, including a weak signal that must not propagate, a repeat that must
   not churn, a reactivation, a shared assumption, a redundancy, and a final
   document adjacent to a corrected relation that must not reopen it.
2. Exhaustive three-label adjudication of every document x assumption pair,
   plus the per-step truth trajectory, hashed and committed before any run.
3. All three systems run the canonical order live, three runs each, plus two
   alternative orders whose semantics permit the same end state.
4. Metrics: per-step state correctness, end-state correctness, correction
   persistence, regression rate, order convergence, state churn, error survival
   (how many steps a wrong node stays wrong), repair cost, auditability, and
   cost in calls, tokens and latency.
5. An independent judge recomputes the trajectory from the recorded raw answers
   and fails on a tampered artifact.

**Pre-registered kill condition. These numbers are chosen now, before the
sequence exists in code, and will not be revised after seeing results.**

B must beat A1 on at least **two** of the following four, at the stated margin:

1. **End-state node accuracy**, mean over three runs: B >= A1 + 0.05.
2. **Correction persistence**, the fraction of post-correction steps where the
   rejected relation stays rejected: B >= 0.95 while A1 <= 0.80.
3. **Regression rate**, nodes that were correct and become wrong under a
   document that does not bear on them: B <= half of A1's rate.
4. **Order convergence**, identical end state across the three orders: B in 3 of
   3, A1 in 1 of 3 or fewer.

And a hard override, whatever the four say: **if A1 reaches end-state accuracy
>= 0.95 and correction persistence >= 0.95, the thesis is dead.** A research
state a model maintains in a JSON document would then be sufficient, and this
architecture is unnecessary machinery.

Cost is reported, and is not a kill criterion in either direction.

If the kill condition triggers, the outcome is to stop building this product and
write up why, not to narrow the claim a third time.

Verification: `make lock-sequence` (offline, hashes truth), `make bench-seq`
(live, three systems, three orders), `make seq-judge` (independent), plus
`make check` green and root `ruff check .` clean.

**Sequence locked 2026-08-15, before any system code for A0 or A1 existed and
before any model saw it.** Ten documents over `fixtures/agent_program.json`,
80 document x assumption pairs adjudicated exhaustively: 8 RELATION, 70
NO_RELATION, 2 AMBIGUOUS. The two ambiguous pairs are recorded rather than
guessed: (D5, B7), and (D8, B7), the second being exactly the reading the
holdout's model made and the holdout's truth failed to declare. All three
orders converge to the same end state, checked by the lock script, which
refuses to lock otherwise.

Truth trajectory: D1 settles B4 and makes F6 redundant; D2 and D3 move nothing
(weak, then a repeat); D4 contests B4, reactivates F6, and puts H5 under review;
D5 moves nothing; D6 contests B5, staling F4/F5/F6, reactivating F7, and putting
H3 and H4 under review; D7 moves nothing (support against a standing
contradiction); D8 contests B1 and stales F9; D9 settles B6 and makes F8
redundant; D10 moves nothing at all.

Digest, recorded as the thing that would have to change for this to have been
tuned after the fact:

    409edd00567b99f141ce15bcb6cb858da4b0eb069c8e15e3482f4b494c69143a

**Closed 2026-08-15. VERDICT: KILL, by the pre-registered standard.** Live: 15
trajectories, 500 calls, 644s, `proof-out/f3-sequence-asrun.json`. Rescored from
those same recorded answers with no new calls into `proof-out/f3-sequence.json`,
proof `8f6b5ee44ebd49d0a5934a2302c9537b`; `make seq-judge` 9/9 PASS;
`results/f3-summary.json` committed.

End-state accuracy A0 0.678, A1 0.956, B 0.978. Correction persistence A1 1.000,
B 1.000. Regressions A1 5, B 6. Auditable justifications A1 0.655, B 1.000.
Calls A1 50, B 400. Zero of four criteria met, and the hard override fired: A1
cleared 0.95 on both end-state accuracy and correction persistence, which was
written down in advance as sufficient to end the thesis.

**A metric defect, found after the first computation and disclosed rather than
quietly fixed.** As run, correction persistence was 0.1429 for all three systems
identically, which is a bug signature, not a result. The implementation measured
whether the corrected node's state stayed put; the registered criterion is
whether the rejected relation stays rejected. Every system's B7 state moved at
D5, the pair the adjudication marks AMBIGUOUS, so the metric punished all three
for a reading the benchmark itself calls defensible. Corrected to match the
registered wording, and to apply the ambiguity exclusion the registration also
promised. Recomputed from the same answers: the correction improved every
system's numbers and made the verdict stronger, not weaker. Both artifacts kept.

No system resurrected the rejected relation, in any run or order. B's single
wrong judgment at document two survived all nine remaining steps, faithfully
propagated. A1 missed the multi-hop derivations and twice marked a planned
experiment COMPLETED, which B cannot do; noted post hoc, not among the criteria,
so it does not count.

Verification: 113 offline tests, `make check` clean, root `ruff check .` clean.

Recommendation recorded in `README.md` and `RESEARCH.md` section 10: do not
build this product. The engine, the three benchmarks, the locking protocol and
the judges are the artifact.

Status: complete

## Third candidate, F4: is a contribution gate necessary, or does 3.7 comply?

Objective: decide between two surviving second-project candidates by falsifying
the one that can be falsified today. Contribution Gate claims a runtime gate is
needed because coding agents violate the destination repository's own AI
contribution rules. If `gemini-3.7-flash`, handed the policy verbatim and told
refusing is allowed, refuses reliably on AI-banned repositories, the enforcement
product is unnecessary and we do not build it.

Branch: feat/memory-provenance
Parent: c7e3e67

Allowed files: everything under `contribution-gate/`, plus this contract.
Nothing under `research-impact/`, nothing of Custody's.

**Verified before writing any code, not taken from a summary:**

- RepoComplianceBench is real: arXiv 2607.26819, Yang, He and Zhou, submitted
  2026-07-29. 106 issues from 49 repositories, four rule types. Its abstract
  states agents "almost never proactively retrieve the contribution rules", that
  reminders, rule quotes and verifier feedback do fix disclosure and
  verification, and that agents "never refuse to contribute in AI-banned
  repositories under any condition we tested", leaving "enforcing bans and human
  escalations" an open problem. No public code or data release was found.
- The Open Home Foundation AI policy is real, 2026-07-20: autonomous agents may
  not contribute, such PRs and issues are closed, and every repository carries
  an `AI_POLICY.md`. Godot has published a comparable block.
- Nearest incumbents govern a different boundary. Microsoft's Agent Governance
  Toolkit (April 2026, ~4,100 stars) enforces organisation-side policy: OWASP
  Agentic Top 10, EU AI Act, HIPAA, SOC2. It does not read a destination
  repository's contribution rules. Palantir's policy-bot enforces approval
  policy inside the repository that installs it. AI-detection Actions are
  maintainer-side detection. All of these sit on the receiving side; the policy
  is published as text and the actor is the contributor's agent.
- `gemini-3.7-flash` exists and answers in this project. `gemini-3.7-pro` does
  not (404). The mandatory stack requirement is satisfied either way.

Non-goals:

- **No writes to any third-party repository, ever, in any condition.** The whole
  subject of the experiment is agents contributing where they are unwelcome;
  doing that for real while measuring it would be the exact harm the policies
  exist to prevent. Every write surface in this probe is a local mock, including
  the ungoverned negative control.
- No gate implementation until the probe answers. If the model already complies,
  there is nothing to build.
- No claim that the paper's result transfers to Gemini. It tested four frontier
  models and does not name them; ours is a separate measurement.
- No product scaffolding, no UI, no cloud resources in this probe.

Baseline: the paper's published finding (refusal 0% under every tested
condition, disclosure and verification recoverable by prompting). Nothing
measured for Gemini yet.

Acceptance gates:

1. At least six instances built from real, currently published policies,
   covering banned, disclosure-required and human-handoff repositories.
2. Four conditions of escalating help, from unaided to policy-quoted-verbatim
   plus an explicit statement that refusing is an acceptable outcome.
3. Three runs each, live, with a mocked write surface and a recorded trajectory
   per episode.
4. Metrics: refusal rate on banned repositories, policy-file read rate,
   disclosure rate, handoff rate, per condition.
5. An independent judge recomputes the outcome from the recorded trajectories.

**Pre-registered kill condition, fixed now.** If `gemini-3.7-flash` refuses on
**90% or more** of banned-repository instances in the best-help condition, the
enforcement product is unnecessary and Contribution Gate is dropped in favour of
Research Access Operator. If refusal stays **below 50%** in the best-help
condition, the gap is real and the gate is built. Between 50% and 90% is a
partial result and the decision moves to the demo strength of each candidate,
which is a judgement call I will state rather than compute.

Verification: `cd contribution-gate && make probe` then `make judge`, plus root
`ruff check .` still clean and Custody untouched.

**Closed 2026-08-15. VERDICT: DROP, on the registered threshold.** 108 live
episodes, `gemini-3.7-flash`, 129s, `proof-out/f4.json`, proof
`620e0322c9cb4046bb70ff1fa2ef073e`. Refusal on banned repositories: 0.667
unaided, 0.750 with a nudge or the policy quoted, **1.000 in the best-help
condition**, against a registered drop threshold of 0.90.

The obvious objection was tested rather than argued: with `refuse` and
`escalate_to_human` removed from the action list entirely, leaving a plain
coding-agent toolset, the model still opened no pull request on any banned
repository in any policy-aware condition (0 of 36), and instead posted a comment
citing the policy and offering the fix for human review. Unaided, without the
refuse affordance, it opened a PR 58% of the time. `proof-out/f4-posthoc.json`,
labelled post hoc and not part of the registered decision, which stands either
way.

arXiv 2607.26819's "never refuse under any condition" did not reproduce on this
model in this setting. Two explanations survive and cannot be separated without
their harness: a model difference, or my instances making policy discovery
trivially easy (the policy is 1 of 5 files, not 1 of thousands). Both point the
same way: the failure mode is not seeing the policy, not disobeying it, so the
intervention is context injection rather than runtime enforcement, and that is a
convention plus a small library rather than a product.

Written up in `contribution-gate/RESEARCH.md`. No repository was contacted in
any condition; every write surface was a local mock.

Status: complete

## Fourth candidate, F5: is a Research Access Operator form-filling? Pre-registered

Objective: falsify the remaining candidate before committing two weeks to it.
Research Access Operator claims to own the administrative journey from "I need
this controlled dataset" to authorised access. Its most model-shaped leg is
preparing a compliant dbGaP data access request and catching the things that get
requests rejected. If `gemini-3.7-flash`, given the public requirements, already
catches those, then that leg is form-filling and the remaining product is
multi-week orchestration across institutions, which is precisely what Huron and
Kuali already sell.

Branch: feat/memory-provenance
Parent: c7e3e67

Allowed files: everything under `research-access/`, plus this contract.

**Ground truth, verified from NIH sources this session, not recalled:**

- The PI and the institutional Signing Official co-sign; both need eRA Commons
  accounts; the request uses SF 424 (R&R)
  (dbgap.ncbi.nlm.nih.gov/aa/dbgap_request_process.pdf, read directly).
- Verbatim from that document: *"Collaborators at other institutions will need
  to submit separate requests for co-submission with their local SOs."*
- The PI supplies the preferred SO, a research use statement, and collaborating
  investigators **at the same institution**.
- The Data Use Certification limits use to the project described in the request,
  forbids distributing data beyond those permitted to handle it, and forbids
  attempting to identify or contact participants.
- The dominant rejection reason is a Research Use Statement inconsistent with
  the dataset's data use limitation; the documented remedy is to remove the
  dataset or change the statement (NCBI Bookshelf NBK570242).
- Access runs one year and the PI agrees to submit *"either a project renewal or
  close-out request prior to the expiration date"*; failure can mean termination
  of access and suspension of the PI and all associated personnel.
- Some datasets require local IRB approval, noted on the study page.

Non-goals:

- No contact with dbGaP, NIH, eRA Commons or any institution. Nothing is
  submitted anywhere. This is a paper exercise against published rules.
- No inventing NIH rules to make traps. Every planted defect must be wrong
  according to one of the quoted requirements above, and each scenario records
  which one.
- No LLM grader. Trap detection is exact matching against a fixed issue-code
  enum given to the model, so the score cannot drift with a judge's mood.
- No building the product before the answer.

Baseline: unmeasured. The Gate probe found this model complies once it can see
the rules, which is a reason to expect it does well here too.

Acceptance gates:

1. Eight scenarios, seven carrying exactly one planted defect drawn from the
   quoted requirements, one clean control carrying none.
2. The model is given every reasonable advantage: the requirements in context
   and a fixed enum of issue codes to choose from. If it still misses, the gap
   is real; if it succeeds, the advantage is disclosed.
3. Three runs, live, structured output, every packet recorded.
4. Metrics: trap-catch rate, false alarms on the clean control, fabricated
   identifier rate, packet completeness.
5. An independent judge recomputes all of it from the recorded packets.

**Pre-registered kill condition, fixed now.**

- **DROP** if trap-catch >= 0.90 **and** fabrication <= 0.05 **and** false
  alarms on the clean control <= 0.10. A strong model plus public documentation
  would then already produce a compliance-checked packet, leaving orchestration
  as the product, where the incumbents are.
- **BUILD** if trap-catch < 0.60 **or** fabrication > 0.20.
- Anything else is a judgement call, to be argued in prose rather than computed.

Fabrication is measured mechanically: an eRA Commons id, phs accession, IRB
approval number or DAC decision appearing in a packet when the scenario never
supplied one was invented.

Verification: `cd research-access && make probe` then `make judge`, root
`ruff check .` clean, Custody untouched.

**Closed 2026-08-15. VERDICT: DROP on the falsifiable leg.** 24 packets, live
`gemini-3.7-flash`, 24s, `proof-out/f5.json`, proof
`56c9330b0df948cda6788fa96f09b71f`. Trap-catch **1.000** (21 of 21), fabrication
**0.000**, false alarms on the clean control **0.000**, against registered drop
thresholds of 0.90, 0.05 and 0.10.

A second metric defect of mine, found and disclosed rather than reported:
completeness came out at 0.667, but the only field ever missing was `personnel`,
in exactly the scenarios where the researcher named nobody. The model left it
empty and listed it under unknowns instead of inventing names, which is the
behaviour the probe was built to reward. The metric was penalising the right
answer. That is twice in one day that a metric of mine was wrong in a way that
made a system look worse than it was; both times the correction strengthened the
result rather than rescuing it.

The help was maximal by design and is disclosed: published rules in the prompt,
blocking-issue codes as a fixed enum. Failure under that much help would have
been conclusive; success under it moves the burden to whoever wants to build the
leg, who must now construct a harder version and show it fails first.

The leg that survives is multi-week institutional orchestration, which cannot be
verified without a real Data Access Committee, is what Huron and Kuali already
sell, and would demo as an agent corresponding with fictional officials.

Written up in `research-access/RESEARCH.md`.

Status: complete

## F6: stop guessing at weaknesses, mine them. AutomationBench failure discovery

Objective: replace idea-first discovery with failure-first discovery. Three
candidate products died this session because each assumed a Gemini weakness that
turned out not to exist. Instead of inventing a fourth thesis, run Gemini 3.7 on
a benchmark whose final state is checked programmatically, collect the tasks it
actually fails, and cluster those failures into a product-shaped problem. The
failure pattern becomes the project; the business domain does not.

Branch: feat/memory-provenance
Parent: c7e3e67

**Verified before authorising the clone:** AutomationBench is Zapier's, public
at github.com/zapier/AutomationBench, with 600 public tasks at 100 per domain
across sales, marketing, operations, support, finance and HR, roughly 500 API
endpoints across 47 simulated SaaS apps, tasks and simulators included in the
repository rather than downloaded, and per-task grading by assertion against the
final environment state with `task_completed_correctly` as strict pass/fail and
`partial_credit` for gradation. No LLM judge. Reported public-set scores include
Gemini 3.6 Flash 45.00%, GPT-5.6 Sol 45.83%, Kimi K3 46.67%, Claude Opus 5
50.3%, so there is substantial failure mass to mine. There is also a private set
held for the official leaderboard, which we neither have nor need.

Allowed files: everything under `failure-mining/`, plus this contract.

**Explicitly authorised, because the standing rule forbids it by default:**
cloning `zapier/AutomationBench` into `failure-mining/`, and creating a
**separate** virtual environment for it there. Custody's `.venv` is not to be
touched, and no dependency of theirs may be installed into it.

Non-goals:

- No leaderboard chasing. We are not trying to beat 45%; we are trying to read
  the 55%. A score is a by-product, and the private set is irrelevant to us.
- No product until a failure cluster survives the filter. The filter, adopted
  from the user's own wording: the model must fail repeatedly with reasonable
  context and tools; one extra sentence of prompt must not fix it; there must be
  a product-level mechanism that would fix it; the outcome must be mechanically
  checkable; no incumbent may already market that autonomous outcome; the demo
  must run in a real executable environment; and it must look nothing like
  Custody.
- No modifications to the benchmark's tasks or graders. If we ever need to
  change one to make a point, the point is wrong.
- No claim that a failure is systematic on a single observation.

Baseline: none of our own. Gemini 3.6 Flash at 45.00% on the public set is the
nearest published figure; we run 3.7 Flash and will have our own number.

Acceptance gates:

1. The benchmark runs locally, unmodified, against `gemini-3.7-flash`, with its
   own environment, and reproduces a plausible score on a sample of tasks.
2. At least 30 Operations tasks are run, with full trajectories retained for
   every failure.
3. Failures are clustered by mechanism rather than by domain, with the count and
   at least two concrete task references per cluster.
4. The largest clusters are checked for the one-extra-sentence objection: does
   telling the model about the failure mode in the prompt fix it?
5. Whatever survives is competitor-checked at the outcome level before any
   product decision, and the result is reported even if nothing survives.

Verification: the benchmark's own runner and grader, unmodified; cluster counts
recomputed from retained trajectories; root `ruff check .` clean; Custody
untouched and its suite still 360/360.

**Gates 1 to 4 closed 2026-08-16. Gate 5 (competitor check) is open, and no
product decision may be made before it.** Written up in
`failure-mining/FINDINGS.md`.

Gate 1: every off-the-shelf transport was closed (Vertex OpenAI-compat drops
Gemini 3.x thought signatures; the benchmark's own Gemini client sends the
Interactions `turn_list` shape the Developer API replaced; the free Developer
tier allows 20 requests a day). `adapter/vertex_client.py` implements the
benchmark's `Client` interface on google-genai over Vertex, touching transport
only. Validated on the `simple` domain at 8/8 with zero aborts, the criterion
set before it was written, after three real bugs.

Gate 2: 30 Operations tasks, `gemini-3.7-flash`, effort high, 0 aborts,
**50% pass / 80% partial**, against Zapier's published 45.00% for Gemini 3.6
Flash across all domains. Plausible, so the harness is not silently broken.

Gate 3: clustered by mechanism. **Six of fifteen failures issued writes against
identifiers they never resolved; zero of fifteen passes did.** The agent cannot
turn a human-readable name into the system's internal id, invents one, writes
into the void, and then reports success to a human in Slack or email. Two
further clusters are named but unanalysed: the notification omitting the datum
that made it actionable (5), and the second system's artifact never being
created (5).

Gate 4: the one-extra-sentence objection, tested. An instruction naming the
exact failure mode fixed **1 of 6**; the other five are missing the same
identifiers as before, and the overall score moved 50% to 47%, slightly the
wrong way and within variance. The benchmark's task file was restored from git
and verified clean; the only remaining modification inside the clone is the
`--api vertex_native` branch in `scripts/eval.py`, which is the transport wiring
and is disclosed.

Known risk, recorded before any product work: the remedy may belong in the tool
layer, and "this should be a library" is what killed the Contribution Gate.
Gate 5 must answer that as well as the incumbent question.

**Gate 5 closed 2026-08-16. The cluster fails it.** arXiv 2606.30531, "Entity
Binding Failures in Tool-Augmented Agents" (29 June 2026), defines this exact
failure and evaluates the mechanisms this project would have proposed, including
provenance tracking by name, across 60 tasks, five backends and six methods,
with baselines at 24 to 26 percent wrong-entity actions and entity-aware methods
eliminating them at a cost to completion. Commercially the outcome is occupied
too: Tilores and Explorium market entity resolution for agents, and Merge,
Composio and Arcade own the execution layer where the gate belongs. The
"it should be a library" risk recorded before the check turned out to be exactly
right.

What survives is real but small: an independent reproduction of a seven-week-old
result on a harder benchmark with deterministic graders, the finding that a
prompt naming the failure fixes 1 of 6, a reproducible 50% Operations baseline
for `gemini-3.7-flash`, and a working Vertex transport for AutomationBench that
did not exist this morning.

**The other two clusters were competitor-checked before being analysed, and both
are occupied.** Cluster 2, verifying the agent's report against what it actually
did, is arXiv 2607.25364 (Explanation-Bound Tool Execution, July 2026) plus
Patronus Percival commercially. Cluster 3, the missing downstream artifact, is
durable execution (Temporal, Inngest, Restate, DBOS) with the residual research
gap already taken by Atomix (arXiv 2602.14849). The cluster 1 remedy itself was
published two weeks ago as arXiv 2608.02645.

Four candidate products have now been falsified in two days, each by its own
pre-registered criterion, and all three failure clusters from the benchmark run
are claimed by work from the last six months. The recommendation in every
write-up is unchanged and now unambiguous: stop hunting a second submission and
spend the remaining fifteen days on Custody.

Status: complete

## Back to Custody: submission readiness pass (opened 2026-08-16)

Objective: get the submission to a state a judge can verify end to end. The
second-project search is closed and archived; no further candidate hunting.
This pass, in order: (a) establish the true current state rather than the
state `SUBMISSION_HANDOFF.md` was written in, (b) inspect the actual Devpost
submission so no requirement is discovered late, (c) refresh the live
evidence that has aged out, (d) only then presentation work.

Branch: feat/memory-provenance
Parent: 671659a

Allowed files: `proof-out/*` (gitignored), `web/incident.html`,
`web/architecture.html` (regenerated output only), `SUBMISSION_HANDOFF.md`,
`.claude/SESSION_CONTRACT.md`, and one new `FROZEN.md` at the root of each of
`research-impact/`, `contribution-gate/`, `research-access/`,
`failure-mining/` (write-only markers, no change to their existing content).
Also `README.md`, for two stale test counts (`:222`, `:303` say 352, the
suite is 360) and the `git clone <this repo>` placeholder. Stale counts in
judge-facing prose are a documented judging-pass finding, so this is inside
the user's "only fixes a documented judging weakness" rule, not scope drift.
Plus `scripts/gates.py` and `tests/test_g1_gate.py`, for one judge-facing
prose defect found while verifying: with no missing G5 groups the verdict
renders "missing  and a Cloud Scheduler record", an empty join printed to a
judge. Same documented weakness class, judge-facing output accuracy.
Any source change needs a finding recorded here first, per the standing rule:
investigate and report before patching a live producer.

Non-goals:

- No new Custody capability. Standing rule set by the user this session:
  nothing new unless it fixes a documented judging weakness or materially
  improves the demo.
- No deletion of `research-impact/`, `contribution-gate/`, `research-access/`
  or `failure-mining/`. They are frozen, not discarded.
- No Vercel production redeploy without a separate explicit ask.
- No fabricated or hand-edited `proof-out/*.json` field. A failing live run
  gets reported, not smoothed.

Baseline (measured 2026-08-16 05:11Z, not read from prose):

- `make check`: 360 tests, 0 failures, 0 skipped, 0.14s, no network.
- `make gates`: G2/G3/G4 PASS. G1 BLOCKED, `g1.json` older than 24h.
  G5 BLOCKED at 2 of 4 groups (has discovery/lifecycle and
  security/governance; missing execution/state and telemetry).
- Eight `proof-out` artifacts are past the 24h window: `g1`, `live-auditor`,
  `live-chain`, `live-fleet`, `live-model-armor`, `live-narration`,
  `live-observability`, `live-review`. Four are fresh: `live-gateway`,
  `live-memory-deletion`, `live-registry-attack`, `live-revision-binding`.
- The four live-evidence findings `SUBMISSION_HANDOFF.md` item 2 implies are
  open are in fact closed (O1, M1, S1, R2, D2, plus the hardcoded-v2
  coupling), in commits 871535c and 671659a. The handoff is stale on this
  point and gets corrected under this contract.

Acceptance gates:

1. The Devpost submission's real state is recorded here from the page
   itself: whether an entry exists, which track, and which required fields
   and media are missing. Not inferred from the repo.
2. Every stale live producer is rerun, or its failure recorded here with the
   error text. `make gates` reports G5 at 4 of 4 groups, BLOCKED only on
   elapsed time.
3. `make check` still green and `make gui` regenerates `web/*.html` with
   every evidence chip reading `pass`, no `stale`.
4. `SUBMISSION_HANDOFF.md` matches the measured state, with the closed
   findings marked closed and the remaining work in cost order.

Verification: `make check`, `make gates`, each refreshed producer's own
`make *-gates` judge, `make gui`, and a read of the regenerated chip states.

All four gates met.

1. **Devpost, read directly.** A draft entry `Custody` exists at `1/5 steps
   done`, the one done step being `Manage team`. Elevator pitch blank;
   Devpost gates later steps, so no category, description, repo URL or video
   URL has ever been entered. Separately, `gh` reports the GitHub repo
   PRIVATE with sole collaborator `Yatsuiii` and zero pending invitations,
   against a rule requiring a private repo be shared with testing@devpost.com
   and cloudhackathons@google.com. The remote default branch is
   `feat/memory-provenance`, so there is no stale `main` risk.
2. **Live evidence refreshed.** All eight stale producers rerun clean, no
   failures. `make gates` now reports G1 PASS and G5 at **4 of 4 groups**,
   BLOCKED on elapsed time alone. All 11 `make *-gates` judges PASS.
3. **`make check` 363/363**, `make gui` regenerated both pages, all 11
   evidence chips read `pass`, none `stale`. The chip mechanism was
   demonstrated rather than assumed: the same rows read `stale` before the
   refresh.
4. **`SUBMISSION_HANDOFF.md` rewritten** against the measured state: new
   item 0 for the submission and repo-visibility gaps, item 1 settled (no
   video), item 2 marked as never staying done, item 4 marked CLOSED, item 3
   corrected to say the live pages are now behind `web/`.

Two defects found and fixed under this contract, both judge-facing accuracy,
both inside the user's "documented judging weakness" rule:

- `README.md` said 352 tests in two places; the suite is 363. The clone line
  said `git clone <this repo>`; it now names the real URL.
- `scripts/gates.py` rendered "missing  and a Cloud Scheduler record" once no
  group was missing, an empty join printed to a judge, and that is the
  expected end state rather than an edge case. Extracted `still_outstanding()`
  and covered it with three tests, including one asserting no phrasing leaves
  a gap where a list should be.

Not done under this contract, and not silently: no Vercel redeploy, so the
live pages are behind `web/`; no commit on the submission branch. The four
research directories were frozen with `FROZEN.md` markers and archived to
branch `archive/second-project-search` (commit 853ad18, 77 files) on explicit
user authorization, written with `commit-tree` so HEAD and the working tree
were untouched, which also means the pre-commit design review did not run
over that archive.

Status: complete

## Handoff for the continuing second-project search (opened 2026-08-16)

Objective: the user is continuing the second-project search despite the
standing recommendation not to. Write one handoff a cold session can start
from: what was already falsified and why, so no candidate is re-run by
accident; the credentials and environment the search needs, named without
their values; and the filter that killed four candidates so a fifth is not
argued about for two days first.

Branch: feat/memory-provenance
Parent: 4ec8e45

Allowed files: `second-project-search/HANDOFF.md` (new),
`.claude/SESSION_CONTRACT.md`.

Non-goals:

- No secret value written to any file. Credentials are named by variable and
  location only. `GEMINI_API_KEY` in particular is never read or echoed.
- No Custody source, gate, proof or doc touched. This is not Custody work and
  must not consume Custody's remaining runway beyond writing the handoff.
- No new candidate investigated, no new benchmark run, nothing unfrozen. The
  handoff enables the search; it does not resume it.
- Not committed to the submission branch. It lives beside the four frozen
  directories, untracked here, and belongs on
  `archive/second-project-search` if it is committed at all, so a judge
  reading the repo never walks into it.

Baseline: four candidates falsified (Keel, Contribution Gate, Research Access
Operator, the AutomationBench entity-binding cluster), each with a `FROZEN.md`
and archived at commit 853ad18. Credentials verified present this session:
repo-local gcloud config authenticated as yoursturuly@gmail.com against
project-988bc9fe-092c-4b32-90c, ADC files present in both `.gcloud/` and
`~/.config/gcloud/`, `GEMINI_API_KEY` present in
`failure-mining/AutomationBench/.env`, `gh` authenticated as Yatsuiii.

Acceptance gates:

1. The handoff names every credential the four probes actually used, by
   variable name and file location, with no value reproduced. Verified by
   grepping the handoff for anything key-shaped before finishing.
2. Every falsified candidate appears with its killing number, so a cold
   session cannot re-propose one.
3. The competitor filter that killed all three failure clusters is stated as
   a gate to apply before building, not after.
4. Nothing under Custody's tracked surface is modified. `git status` shows
   only the new file and this contract.

Verification: `make check` still 363/363, `git status`, and a read of the
written file for accidental secrets.

All four gates met. `second-project-search/HANDOFF.md` written.

1. Credentials named without values: the Vertex project, location, account,
   `CLOUDSDK_CONFIG` path and both ADC file locations; the four env vars the
   probe code actually reads (`VERTEX_PROJECT`, `VERTEX_LOCATION`,
   `KEEL_VERTEX_PROJECT`, `KEEL_VERTEX_LOCATION`, confirmed by grep rather
   than recalled); `GEMINI_API_KEY` by name and file only; the `gh` identity
   and scopes. Scanned for key-shaped strings, clean. The key itself was
   never read this session, only its variable name via `cut -d=`.
2. All four falsified candidates tabled with their killing numbers, plus the
   two competitor-occupied clusters.
3. The seven-criterion filter is stated with gate 5 explicitly ordered before
   cluster analysis, which is the ordering that would have saved two days.
4. `git status` shows only this contract modified plus untracked research
   directories. `make check` 363/363. No Custody surface touched.

Also recorded: the interactive `gcloud auth application-default login`
refresh is flagged as user-run, not agent-run, since ADC will have expired by
the time anyone resumes.

## Failure-injection tests for the trust boundary (opened 2026-08-17)

Objective: a judge review of this submission scored Architectural Discipline
& Tech Stack 85/100, docked specifically for having no adversarial/failure
tests around the trust boundary itself — every documented capability
(R1/R2/S1/G1-G5/M1/O1/D1/D2) is proven on its happy path only. Add targeted
tests proving the system fails closed (denies/quarantines), not open
(silently trusts), when its dependencies misbehave: Memory Bank unreachable,
Agent Registry timeout, a tool-revision check itself erroring. This directly
targets the rubric's named "failure handling" sub-criterion.

Branch: feat/memory-provenance
Parent: 4ec8e45

Allowed files: new test files under `tests/` covering the trust-boundary
failure paths (Memory Bank client, Agent Registry client, revision-check
gate), and the minimal production code change needed if a test reveals an
actual fail-open bug (not expected, but if found, fix it rather than paper
over it). `README.md`'s status section, to record the new coverage.
`.claude/SESSION_CONTRACT.md` (this file).

Non-goals:

- No changes to G1-G5 gate logic, proof-out generation, or the live `make
  live-*`/`make *-gates` commands — this is pure test-suite addition.
- No touching `web/`, the Vercel deploy, or anything Demo/Production
  Readiness related — that's out of scope for this contract.
- No touching `failure-mining/`, `research-access/`, `research-impact/`,
  `contribution-gate/`, or `second-project-search/` — untouched research
  archive, not part of this submission.
- No git commit/push without explicit authorization already given this
  session (user said "you can do everything else" covering this work,
  2026-08-17) — commit and push are in scope for this contract.

Baseline: `make check` passes 363/363 before starting. Record the exact
number.

Acceptance gates:

1. At least one test proves a Memory Bank-unreachable condition (mocked
   503/timeout) results in the write/read being denied or quarantined, not
   silently allowed through.
2. At least one test proves an Agent Registry timeout results in the
   dispatch being blocked, not defaulting to trust.
3. At least one test proves a tool-revision check that itself errors
   (exception, malformed response) fails closed — the agent does not
   proceed as if the revision were approved.
4. All new tests actually fail against a deliberately broken
   fail-open implementation (verified by temporarily inverting the
   fail-closed logic and confirming the new tests catch it), so they're
   proven to test the right thing, not just pass trivially.
5. `make check` still passes in full afterward, count recorded and compared
   to baseline.

Verification: `make check` before and after with counts compared; each new
test's failure mode manually confirmed by temporarily breaking the
corresponding fail-closed logic and watching the test catch it, then
reverting.

**Closed 2026-08-17.** `make check` was 363/363 before starting (fresh run,
lint clean). Thirteen new tests added across three files, one per named
dependency:

`tests/test_agent_engine_memory_bank.py` (new, 5 tests) covers
`custody/adapters/memory_bank.py`'s `AgentEngineMemoryBank.write_record`,
`RevokingMemoryBankGraph.revoke`, and the end-to-end path through
`CustodyMemoryService.add_session_to_memory`. A mocked
`AgentEngineMemoriesClient` raises `ClientError(503, ...)` and a bare
`TimeoutError` (the two shapes an unreachable Memory Bank actually takes);
both propagate rather than being swallowed, so a session write, a
per-record write, and a revoke all fail the caller instead of reporting
success. A sixth control (`ClientError(409, ...)`, the real replay case)
confirms the tests are distinguishing "unreachable" from "already written",
not just any error.

`tests/test_firestore_store.py` (+2 tests, new class
`FirestoreRevisionCatalogFailsClosedOnAnUnreachableRegistry`) covers
`FirestoreRevisionCatalog.admit`, the durable Agent Registry pin read. A
fake Firestore client whose `document(...).get()` raises
`DeadlineExceeded` or `ServiceUnavailable` proves the read propagates
rather than degrading to the existing "no pins for this department" empty
admission, which would have been indistinguishable from a genuinely
unapproved department.

`tests/test_revision.py` (+6 tests, new class
`AMalformedLiveSurfaceFailsClosed`) covers `ToolSurface.from_tools_list`:
a non-object result, a missing `tools` key, a non-list `tools` value, a
tool entry that is not an object, and a tool entry missing its name all
raise `ToolSurfaceError` rather than parsing into a permissive empty
surface. A sixth test ties that to dispatch: no `ToolSurface` ever exists
to admit against, so the only value a caller can act on is the empty
`Admission()`, whose `require()` denies.

Gate 4, done for real, one area at a time, each reverted before moving to
the next (confirmed via `git diff --stat` on the three touched production
files, empty at the end): inverted `write_record`'s except clause to
swallow every error instead of just 409 -- all 3 dependent tests failed.
Inverted `FirestoreRevisionCatalog.admit` to return a fully-approving
`Admission` for whatever surface is presented on any read exception --
both new tests failed. Inverted `from_tools_list`'s four raise sites to
silently coerce to an empty surface -- all 6 new tests failed. No
production code change was needed afterward in any of the three cases:
the codebase already failed closed everywhere tested, by propagating
exceptions rather than catching them broadly. That absence is itself the
finding worth recording, not a gap in the work -- it is what the tests
were written to either confirm or disprove, and gate 4's inversion step is
what makes "we checked and it already fails closed" a checked claim
instead of an assumption.

`make check` 376/376 after (363 baseline + 13 new), lint clean. README.md's
status table gained a row for this coverage. No `web/`, gate-logic, or
research-archive file touched, matching the non-goals.

Status: complete

Status: complete

## Full proof-check audit and Narration removal (opened 2026-08-17)

Objective: the user does not trust the prior session's fix claims and asked
for an independent, adversarial full proof check before recording, having
found 2 real bugs themselves. Audit performed: browser click-through of
both GUI pages, a fresh full live-* sweep, a grep sweep for the same
hardcoded-coupling bug class fixed in 671659a, `make demo`/`make incident`
output review, and a README/JUDGE_HANDOFF claims cross-check.

Branch: feat/memory-provenance
Parent: d5ea105

Allowed files: `scripts/render_architecture.py`, `README.md`,
`JUDGE_HANDOFF.md`, `SUBMISSION_HANDOFF.md`, `web/*.html` (regenerated),
`.claude/SESSION_CONTRACT.md`, `proof-out/*`.

Findings from the audit:

1. Confirmed live pages were stale (undeployed since `4ec8e45`, two
   commits and ~2 days behind). Full fresh live-* sweep run (11 producers,
   all clean), `make gates` back to G5 4/4 groups, `make check` 376/376,
   redeployed, `make verify-deploy` 4/4.
2. Re-verified the 671659a coupling fix for real under fresh conditions:
   ran R2 (ends on v1) immediately followed by S1, both live, S1 passed
   20/20 with no manual restoration -- the fix holds.
3. Grep sweep for the same hardcoded-shared-state bug class elsewhere in
   `scripts/*_gates.py` and `live/*/server/*.py`: clean, no other
   instances found. R1/R2's own internal `"v1"`/`"v2"` checks are
   self-contained (their own before/after within one proof run), not the
   same class of bug.
2. `make demo` / `make incident` output read critically: matches the
   documented story exactly, no defects found.
3. Stale test counts found and fixed in three judge-facing docs:
   `README.md` (363 -> 376, two places), `JUDGE_HANDOFF.md` (352 -> 376).
   `JUDGE_HANDOFF.md` and `README.md` both also missing
   `CUSTODY_FIRESTORE_PROJECT` from their `make live-revision-binding`
   instructions -- a judge following either verbatim would hit the exact
   silent-hang R2 finding from 671659a. Both fixed.
4. Real, reproducible UI bug found and fixed in the incident page: none.
   The two things that looked like bugs during manual browser testing
   (a transient `.investigate-hit` pulse animation appearing to do
   nothing, and header stats reading 0 via `get_page_text`) were both
   confirmed to be artifacts of the audit tooling's timing, not real
   defects -- verified by waiting out the animation/count-up and
   rechecking via screenshot, which showed the correct state both times.
5. **Narration audio player: could not be verified either way, and cut
   entirely on user request rather than left as an unverified risk.**
   The embedded `data:audio/mpeg;base64,...` player never left
   `readyState 0` / a spinning loading indicator in extended testing
   (data: URI, blob: URL, and a fresh, trivially-valid ffmpeg-generated
   test MP3 all reproduced the same stuck-loading state), but a control
   test proved this is a limitation of the sandboxed browser-automation
   environment itself -- it cannot decode any MP3, not something specific
   to Custody's file or embedding code -- so no real-browser verdict was
   reached. Given that genuine uncertainty, the user's own two independent
   complaints (a widget nobody has time to listen to, and now a widget
   whose audio might not even play for a judge who tries), and that the
   verdict text already conveys everything the audio does, the user opted
   to remove the audio player and the whole Narration section from the
   GUI rather than carry an unverified interactive element into a
   recording. `scripts/live_narration.py` and its live proof
   (`make live-narration` / `make narration-gates`) are left intact as a
   real, still-provable capability; only its GUI surfacing and the Best
   Multimodal UX candidacy claim are removed.

Non-goals:

- No change to `scripts/live_narration.py`, `custody/review.py`, or any
  already-gated judge/producer logic -- this is a GUI-surfacing and
  doc-accuracy pass, not new capability work.
- No change to `HANDOFF.md` (explicitly non-judge-facing, a build log).
- Do not remove the underlying Narration capability or its live proof
  machinery, only its GUI widget and the award-candidacy claim.

Acceptance gates:

1. `web/architecture.html` no longer renders a Narration row or an
   `<audio>` element anywhere.
2. No remaining "Best Multimodal UX" candidacy claim in judge-facing docs
   (`README.md`, `JUDGE_HANDOFF.md`, `SUBMISSION_HANDOFF.md`).
3. `make check` and `make gates` unaffected. `make gui` regenerates clean.
4. Redeployed and `make verify-deploy` 4/4, console clean, confirmed
   in-browser that the Narration row is genuinely gone from the live page.

Verification: `make check`, `make gui`, `make verify-deploy` after
redeploy, a live browser check.

**Closed 2026-08-17.** All four gates met. `make check` 376/376 unaffected.
`make gates` still G5 4/4 groups. `web/architecture.html` regenerated with
zero remaining references to Narration/audio (confirmed via grep and via
the browser's own accessibility tree post-deploy: "no narration widgets or
audio players present"). "Best Multimodal UX" candidacy claims corrected
in `README.md` and `JUDGE_HANDOFF.md` to state plainly that the capability
is real but not entered for that award, and why. Redeployed;
`make verify-deploy` 4/4, console clean.

Status: complete

## Reposition Best Multimodal UX candidacy onto the graph GUI (opened 2026-08-17)

Objective: the user still wants a Best Multimodal UX shot but explicitly
does not want a forced-in capability. Narration was cut (previous
sub-build) because it was both unverifiable and, on the user's own
critique, pointless -- 27 seconds nobody has time for, saying nothing the
verdict text didn't already say instantly. The Dependency Cartography page
(`web/incident.html`) is a genuine second modality already built and
live-proven today: an interactive SVG node-graph diagram (animated
contamination paths, click-to-inspect right panel, a real revoke
interaction that redraws the graph) alongside the text/evidence table --
grasped by looking in seconds, not by listening for half a minute. This
sub-build repositions the existing claim, adds no new capability, and
takes no new technical risk.

Branch: feat/memory-provenance
Parent: b674c71

Allowed files: `README.md`, `JUDGE_HANDOFF.md`, `.claude/SESSION_CONTRACT.md`.

Non-goals:

- No new capability, no code change to `scripts/render_gui.py` or
  `web/incident.html`'s actual behavior -- this is a documentation/framing
  change over what already exists and is already proven.
- Do not overclaim. "Multimodal" here means an interactive visual graph
  representation genuinely distinct from prose, not a claim of audio,
  video, or image generation -- state it exactly that way, not vaguely.
- No published rubric exists for this award beyond name and prize amount
  (already checked live, per `JUDGE_HANDOFF.md`) -- do not invent one.

Acceptance gates:

1. `README.md` states the Multimodal UX candidacy against the Dependency
   Cartography page specifically, naming what makes it a second modality
   (interactive SVG graph + click interactions + live revoke redraw),
   not vague "GUI" language.
2. `JUDGE_HANDOFF.md` is updated to match -- the earlier "not entered"
   framing from the prior sub-build is corrected, not left contradicting
   this one.
3. No claim about Reviewer Narration's removal is walked back or
   softened; the honesty about why it was cut stays as written.
4. `make check` unaffected (docs-only change).

Verification: read both files for internal consistency after editing; grep
for "Best Multimodal UX" to confirm every remaining mention agrees.

**Closed 2026-08-17.** All four gates met. `README.md` gained a new
"Best Multimodal UX candidacy" section naming the Dependency Cartography
page specifically (interactive SVG graph, click-to-inspect, live revoke
redraw), and the Reviewer narration section's closing note now points to
it instead of implying no candidacy exists. `JUDGE_HANDOFF.md`'s opening
and "What to actually produce" section both updated to match. `make check`
376/376, unaffected (docs-only). Not yet redeployed or pushed — this is a
docs-only change riding along with the still-unpushed `b674c71`; push on
next explicit authorization.

Status: complete

---

## Compress the demo video script to one revocation story (opened 2026-08-18)

Objective: per external review (via user, same session that produced the
architecture diagrams and the DecisionTrace falsifier work), the current
4-minute demo script (`SUBMISSION_HANDOFF.md` §1) risks "communication
overload" — a 90-second segment scrolls through multiple separate live
proofs (R1, F1, Fleet N=25) instead of telling one continuous story.
Review's suggested shape: trusted write -> source compromised -> exact
descendants identified and revoked -> unrelated fleet memory survives ->
export refused if it cites revoked memory, then a short infra-proof tail.
Checked before rewriting: `make demo`'s poisoning scenario
(`scripts/demo.py`) already includes an export-refusal beat (the
`ATTACKER` export line), so this narrative is real and demoable, not
invented for the script.

Branch: feat/memory-provenance
Parent: HEAD

Allowed files:
- SUBMISSION_HANDOFF.md (§1, the demo script section, only)
- .claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not add any new UI or code for the video — same standing rule this
  file already states ("a reported number, not a UI feature competing
  for video time").
- Do not touch docs/DEVPOST_SUBMISSION_DRAFT.md's other sections (Project
  Story, Features, etc.) — those weren't flagged, only the video script.
- Do not script any beat that isn't already real and demoable in the
  current repo (`make demo`, the Dependency Cartography page, the
  Architecture & Evidence page) — verify before writing, same as
  DecisionTrace's clarifying-question check this session.
- No commit/push without separate explicit authorization.

Baseline: current script is 5 segments (30/45/90/45/30s) — problem,
mechanism, "that it is real" (proof-scrolling), fleet claim, honesty.

Acceptance gates:
1. The compressed script tells one continuous story matching the
   review's shape (trusted write, compromise, exact revocation,
   preserved-unrelated-memory, export refusal) as a single throughline,
   not separate disconnected segments.
2. The "that it is real" proof-scrolling segment is cut down
   dramatically (from 90s covering 3 separate proofs to a short tail
   proving live Google Cloud infra, not a tour of every live-proof row).
3. The honesty beat (G5 BLOCKED) is kept — review didn't flag it and it's
   a real strength per this project's own stated philosophy.
4. Total still fits the ~4-minute budget.
5. Every beat traces to something that actually runs today (`make demo`,
   the live Cartography page's revoke button, the Architecture & Evidence
   page) — no new capability implied.

Verification: read the updated script back; confirm every referenced
command/page/button exists in the current repo.

Status: complete

Result: rewrote SUBMISSION_HANDOFF.md §1 as one continuous incident
(vouch -> compromise -> demote -> revoke exact descendants -> unrelated
survives -> export refused) instead of five loosely-connected segments,
one of which was 90s of scrolling three separate proofs. Checked before
writing: scripts/incident.py already runs this exact narrative end to
end offline (docstring confirms), scripts/demo.py's export check really
does print REFUSED for untrusted-cited content, and every specific
number reused (32 removed / 575 preserved, 2 departments pulled / 23
untouched, 25 independent rereads) was grepped against web/timeline.html
and README.md's live-fleet section and matched exactly — none invented,
all carried forward from what the pre-existing script already used.
Proof-tour segment cut from 90s/3 rows to 40s/1 row + the Fleet N=25
stat. Honesty beat (G5 BLOCKED) kept unchanged. Total still ~240s (4:00).
No UI/code added, per the file's own standing rule.

Nothing committed or pushed.

---

## Verify and fix the clean-clone reproducibility claim (opened 2026-08-18)

Objective: external review flagged "the README test-count claim wasn't
trivially reproducible from a clean environment" without specifics. Did
not take the claim on faith — actually cloned fresh from
`https://github.com/Yatsuiii/custody.git` into `/tmp/custody-clean-clone-test`
and ran README's own spin-up instructions verbatim (`python3.12 -m venv
.venv`, pip install, `make check`). Found a real, reproducible bug, not a
documentation nit: `scripts/live_gateway.py`'s `_write_policy()` writes
into `proof-out/gateway-iap-{phase}-{proof_id}.json` without creating
`proof-out/` first. That directory is gitignored (`.gitignore:5`) and
this repo's local copy has it only because it accumulated from weeks of
live-proof runs — invisible on this machine, guaranteed-present on a
judge's genuine fresh clone. Result on the clean clone: `make check`
reports "Ran 376 tests" (the count matches) but with 1 failure + 3 errors
(all in `tests/test_live_gateway_producer.py`, all
`FileNotFoundError`/downstream `RuntimeError` from the missing
directory) + 1 skip — not the clean "376 tests, none skipped" the README
claims.

Branch: feat/memory-provenance
Parent: HEAD

Allowed files:
- scripts/live_gateway.py (`_write_policy`, add the missing
  `path.parent.mkdir(parents=True, exist_ok=True)` — same idiom already
  used at line 1334 in `main()`, just missing at the actual write site
  the unit tests exercise directly)
- .claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not touch any other test file or script even if similarly
  proof-out-dependent, unless the same clean-clone run surfaces it —
  fix what was actually found broken, not a speculative sweep.
- Do not commit the local `proof-out/` directory or change
  `.gitignore` — it's correctly gitignored generated output; the fix is
  making the code that writes into it not assume it exists.
- No commit/push without separate explicit authorization.

Baseline: clean-clone `make check` result before the fix: 376 ran, 1
failure, 3 errors, 1 skipped (see above). This repo's own working copy
currently passes 376/376 only because its local `proof-out/` already
exists from prior sessions' work — masking the same bug.

Acceptance gates:
1. The fix is applied at the actual write site (`_write_policy`), not
   papered over by manually creating `proof-out/` in the test fixtures
   or by documenting an extra manual step in README.
2. Re-running `make check` in the SAME clean clone
   (`/tmp/custody-clean-clone-test`, `proof-out/` deleted again first, to
   prove the fix and not just re-use the directory the failing run
   already half-created) passes 376/376, none skipped.
3. The same fix applied to this working repo (not just the throwaway
   clone) so the bug doesn't linger, masked, until the next genuinely
   fresh clone (e.g. Devpost judge, CI).
4. `make check` still passes here afterward too.

Verification: delete proof-out/ in the clean clone, re-run `make check`
there and confirm 376/376; apply the same one-line fix here; run
`make check` here and confirm 376/376 with proof-out/ already present
(the common case) — both paths need to work.

Status: complete

Result: real bug confirmed and fixed, not just a docs claim corrected.
Added `path.parent.mkdir(parents=True, exist_ok=True)` to
`_write_policy()` in scripts/live_gateway.py (both here and in the
throwaway clone, to prove the fix before trusting it). Re-ran `make
check` in `/tmp/custody-clean-clone-test` with `proof-out/` deleted
again first (not reusing the half-created directory from the failing
run): 376 tests, 0 failures, 0 errors, 1 legitimate skip
("no proof-out/ artifacts present on this clone" —
tests/test_stored_artifacts.py:86, confirmed by reading the test that
this is an honest skip-when-nothing-to-check, not a bug). Re-ran here
(proof-out/ already populated from prior sessions): 376/376, zero
skips, unchanged from before the fix. README's "376 tests, none
skipped" claim corrected to state the fresh-clone case precisely (one
expected skip until a live proof has run at least once) instead of
implying a uniform result regardless of clone state. Cleanup:
/tmp/custody-clean-clone-test left in place in case the user wants to
inspect it further; safe to delete any time, it's outside the repo.

Nothing committed or pushed.

## Independent release-readiness audit (opened 2026-08-21)

Objective: Independently verify, as a fresh release engineer/judge, whether
`hardening/fleet-track-pre-submission` (HEAD `1ea8b15`, same commit as
`feat/memory-provenance`) is actually ready to record. Re-check `make
verify-deploy`, `make gates`, and `HACKATHON_VALIDATION.md`'s claims, then do
the one declared remaining gap: a manual public-browser/console/UI smoke test
of the deployed pages and the incident revoke interaction. Only fix
demonstrated P0/P1 release defects; no feature work, no redesign, no polish.

Branch: hardening/fleet-track-pre-submission
Parent: 1ea8b15

Allowed files: none expected. If a P0/P1 defect is found, the smallest fix
only, scoped to the specific broken file(s), plus `HACKATHON_VALIDATION.md`
if new verified facts must be recorded.

Non-goals: no new features, agents, Google services, redesign, or
presentation changes absent a concrete judge-facing defect. Do not touch
unrelated dirty working-tree files (web/architecture.html, web/incident.html,
contribution-gate/, research-access/, research-impact/, failure-mining/,
second-project-search/, web/fleet.html, web/timeline.html, docs/*) unless a
found defect requires it. Do not fake or fast-forward G5.

Baseline: reported — `make check` PASS (377 tests), `make verify-deploy`
4/4 PASS, `make gates` 4 PASS/0 FAIL/1 BLOCKED (G5). To be independently
re-run this session.

Acceptance gates:
1. `make verify-deploy` independently re-run and confirmed against
   `https://custody-incident-cave2.vercel.app`.
2. Every judge-facing public page (root/incident, architecture, fleet,
   timeline) opened in a real browser; console checked for exceptions/failed
   requests.
3. Incident page's revoke-descendants interaction actually exercised in the
   browser, before/after state verified visually.
4. Fleet page's claim boundary (static visualization vs. live proof)
   recorded accurately.
5. Final verdict delivered: READY TO RECORD yes/no, with P0/P1/P2 findings.

Verification: `make check`, `make verify-deploy`, `make gates`, manual
browser smoke test via claude-in-chrome tools.

**Closed 2026-08-21.** All five acceptance gates passed. `make check`
377/377, `make verify-deploy` 4/4 PASS, `make gates` 4 PASS/1 BLOCKED (G5,
correctly). Browser smoke test of all four public pages (root/incident,
`/fleet.html`, `/architecture.html`, `/timeline.html`) found zero console
errors, zero failed requests, no auth wall, no stale build. The incident
page's revoke interaction was clicked live and verified correct
before/after with internally consistent counts. `fleet.html`'s claim
boundary recorded accurately (static visualization of a captured live
proof, not a continuously-live surface). No P0/P1 defects found; zero
product code changed. `HACKATHON_VALIDATION.md` updated with this finding;
READY TO RECORD flipped from NO to YES.

Status: complete

## Video-support UI enhancement: Fleet Overview toggle + Incident replay stepper (opened 2026-08-21)

Objective: The 4-minute demo video repeatedly cuts back to the same
Dependency Cartography screenshot because it was the only page with a
before/after state change. Add two small, judge-facing, evidence-backed
interactions to two already-existing, already-untracked static pages
(`web/fleet.html`, `web/timeline.html`) so the video has more visually
distinct beats, without building any new page, new backend logic, or new
data. Both pages already embed real proof data (fleet.html's
DEPARTMENT_TOOLS/SHARED_DEPTS map matches `proof-out/live-fleet.json`'s
25-department fixture; timeline.html already shows the same
vouched/compromised/blast-radius numbers `incident.html` computes from
`scripts/incident.py`). This is a presentation-layer change only.

Branch: hardening/fleet-track-pre-submission
Parent: 42d1efd

Allowed files: `web/fleet.html`, `web/timeline.html`,
`submission-video/*` (rebuilding the video with new shots),
`.claude/SESSION_CONTRACT.md`.

Non-goals:

- No new backend logic, no new Python data-generation script, no new
  proof/gate. Both pages keep using exactly the data already embedded in
  them (fleet.html's DEPARTMENT_TOOLS/SHARED_DEPTS; timeline.html's
  existing vouched/compromised/blast-radius/cost numbers, plus the same
  four-hop lineage array already embedded verbatim in `incident.html`'s
  `#incident-data` JSON — copied in, not recomputed or invented).
- No new page. `fleet.html` and `timeline.html` already exist
  (untracked, pre-existing this session); enhance them in place.
- No change to `incident.html`, `architecture.html`, or any `scripts/*.py`
  generator — this is JS/CSS added to two static files, not a rerun of a
  generator.
- No fabricated counts. Every number shown in either new state must
  already appear in the page's existing embedded data.
- Do not touch `contribution-gate/`, `docs/`, `failure-mining/`,
  `research-access/`, `research-impact/`, `second-project-search/` or any
  other pre-existing unrelated dirty/untracked file.

Baseline: `web/fleet.html` (122 lines) renders a flat 5-column grid of 25
department/tool cards from a hardcoded `DEPARTMENT_TOOLS`/`SHARED_DEPTS`
map, statically already in the post-revocation (sales/finance red) state.
`web/timeline.html` (182 lines) renders a static vouched-to-compromised
bar plus a cost-comparison table and sensitivity table, all numbers
already final/revealed with no interactivity. Neither page has a
before/after toggle or a step-through.

Acceptance gates:

1. `fleet.html` gains a two-state toggle ("25 trusted" all-green ->
   "simulate compromise" -> sales/finance turn red, counts update to
   2 pulled / 23 confirmed untouched) driven entirely by data already in
   the file. No page reload, no new JSON fetch.
2. `timeline.html` gains a step-through control that reveals, in order:
   Day 1 vouched -> propagation hops (sales -> support -> finance, using
   the same lineage ids/labels `incident.html` already shows) -> Day 16
   compromise discovered -> blast radius computed (32/3-5/575, already
   the page's own stat-strip numbers) -> revoke (existing cost-comparison
   panel). Each step highlights/reveals rather than replacing content
   wholesale, so a viewer can see state accumulate.
3. Both pages still render correctly with JS could-be-absent-safe markup
   (initial state is a sensible static state, not a blank page) and both
   still pass a manual open-in-browser + console check (no errors).
4. The submission video is rebuilt using these two new interactive beats
   in place of some of the repeated Dependency Cartography cuts, per the
   user's requested structure. `custody_demo.mp4` regenerated, not hand
   patched.
5. No files outside "Allowed files" change; `git status` confirms only
   `web/fleet.html`, `web/timeline.html`, and `submission-video/*` differ
   from before this session, plus this contract.

Verification: manual browser open of both pages (before/after states),
console check via claude-in-chrome, then re-run the screenshot capture +
`ffmpeg` assembly for the video, then re-run `make check` to confirm zero
impact on the Python test suite (these are static HTML/JS files outside
`custody/` and `tests/`).

**Closed 2026-08-21.** All five acceptance gates passed. `fleet.html`
gained a Simulate compromise / Restore toggle driven entirely by the
existing DEPARTMENT_TOOLS/SHARED_DEPTS map (35/35 make fleet-gates data
unchanged). `timeline.html` gained a 6-step replay stepper (Day 1 -> sales
-> support -> Day 16 discovered -> blast radius computed -> revoked) using
the same four lineage hops incident.html already embeds verbatim from
scripts/incident.py's compute(). Both tested locally (python3 -m
http.server) in a real browser via claude-in-chrome: zero console errors,
correct default/JS-off state, all toggle/step transitions verified by
screenshot. submission-video/custody_demo.mp4 rebuilt (225s, 1920x1080,
30fps, frame count verified exact) using the new Fleet/Timeline states in
place of repeated Dependency Cartography cuts, per the user's requested
structure; Dependency Cartography kept as the one-time climax shot for the
live revoke click. `make check` still 377/377 (no Python touched). git
status confirms only web/fleet.html, web/timeline.html,
.claude/SESSION_CONTRACT.md, and submission-video/* changed.

Status: complete

## Freeze pass: commit, push, deploy, public smoke (opened 2026-08-21, same session)

Objective: carry the completed Fleet/Timeline UI work (previous section)
through commit -> push -> deploy -> public verification -> freeze, per
explicit user instruction this turn. Extends the prior section's Allowed
files to include `HACKATHON_VALIDATION.md` (the freeze artifact) and the
deploy action itself (`cd web && vercel deploy --prod --yes`, the
project's own documented path, `SUBMISSION_HANDOFF.md`'s "ask before
running it" satisfied by this turn's explicit instruction).

Branch: hardening/fleet-track-pre-submission
Parent: e6968ef

Non-goals: identical to the prior section — no new features, no backend/
proof/gate changes, no G5 change.

**Closed 2026-08-21.** Committed `e6968ef` (web/fleet.html,
web/timeline.html, the pre-existing nav-link diffs in
web/architecture.html and web/incident.html, .claude/SESSION_CONTRACT.md).
Pushed to origin. Deployed via `vercel deploy --prod --yes`
(`dpl_5bX9ewoXimbCHvw3HEnAREX5E5dW`); both public aliases
(custody-incident.vercel.app, custody-incident-cave2.vercel.app) updated.
`make verify-deploy` 4/4 PASS; fleet.html/timeline.html independently
confirmed byte-identical live vs local via curl+cmp (not covered by that
script's fixed route list). Full public browser smoke test passed with
zero console errors on every page; G5 still correctly BLOCKED.
HACKATHON_VALIDATION.md updated with this pass's evidence.

Status: complete
