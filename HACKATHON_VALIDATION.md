# Custody Hackathon Validation

Date: 2026-08-21
Branch: `hardening/fleet-track-pre-submission`
Lane: agentic developer tooling — fleet-wide provenance, containment, and recovery

This is the post-hardening validation artifact. It records what is proven
offline, what is supported by a captured live artifact, and what is currently
blocked by stale or missing external evidence.

## Current freeze result — 2026-08-21

Verdict: **not yet frozen for recording**. The integrated code and all required
live Fleet proofs are green. The local evidence page has been refreshed from
the fresh artifacts, but the public deployment needs an explicit production
redeploy before it is current. Browser-console smoke and G5's real elapsed-
time requirement also remain open.

### Integration

- `origin/feat/memory-provenance` fast-forwarded from `2bb9312` to
  `b05a14d2dbe915f884932671ccc06d17195652ac`.
- `origin/hardening/fleet-track-pre-submission` remains at the same commit.
- No generated `proof-out/` artifacts were committed. The unrelated dirty web,
  research, and submission files remain outside this hardening diff.

### Offline verification

| Check | Result |
| --- | --- |
| `make check` | PASS — ruff clean; 377 tests |
| `make hardening-check` | PASS |
| `make incident` | PASS — 32 affected; 575 unrelated memories survive |
| `make cost` | PASS — 600 records; exact revocation destroys 40 and preserves 560 |
| `make demo` | PASS — governed export refused; 2/3 events withheld |
| `make revoke` | PASS — 4 descendants removed; replay removes 0 further |
| `make isolate` | PASS — cross-department vouches refused |
| `git diff --check` | PASS |

### Fresh live evidence

| Proof | Fresh result |
| --- | --- |
| G1 | PASS — captured `2026-08-21T14:42:40.505264Z`, proof `6ce6b42b843c4cab99566ac70cc0c036`; Cloud Run, Gemini 3.5/Vertex, ADK, and Memory Bank verified |
| N=25 fleet | PASS — captured `2026-08-21T14:46:28.058572Z`, proof `991d0617ec3b48dc8625da82af1e5ee7`; 25 named workers, sales/finance exact revocation, 23 survivor departments |
| F1 chain | PASS — captured `2026-08-21T14:47:28.231330Z`, proof `a1a80717b315451dae99d4c27d69d27d`; sales → support → finance, six exact descendants removed, engineering survives |
| `make fleet-gates` | PASS — 35/35, including independent live rereads |
| `make chain-gates` | PASS — 21/21, including independent live rereads |
| `make gates` | 4 PASS, 0 FAIL, 1 BLOCKED; G5 is 1/4 groups and blocked on real elapsed time |

### Deployment

- `make gui` refreshed the local incident/evidence pages from the fresh
  `proof-out/` artifacts. Fleet N=25 and F1 now show their 2026-08-21 proof
  IDs; other unrefreshed proof rows correctly render as stale.
- `make verify-deploy`: **BLOCKED pending redeploy** — 3/4 checks pass at
  `https://custody-incident-cave2.vercel.app`; root, incident, and
  `/.env.local` pass, while public `architecture.html` is the previous build
  (27270 bytes served versus 27242 locally).
- `/fleet.html` and `/timeline.html` return 200, but remain static visual
  pages and are not current live-evidence surfaces.
- No redeploy was performed: the documented production command is a public
  write requiring explicit approval. Browser-console execution was not
  available in this environment and remains a manual pre-recording check.

### Cold judge dry run

- P0: none found.
- P1: production redeploy of the refreshed evidence page and manual
  browser-console/UI smoke are still required; G5 remains blocked and must be
  stated, never presented as passed.
- P2: static fleet/timeline pages should remain visual-only; no code change is
  justified beyond the narrow evidence refresh already made.

Weighted judge score: **86/100** — Innovation & Operational Utility 36/40,
Architectural Discipline & Tech Stack 26/30, Demo & Production Readiness
24/30. Supporting reads: Fleet legitimacy 9/10, multi-agent depth 9/10,
security/recovery differentiation 10/10, Google stack credibility 8/10,
memorability 9/10. The single highest-leverage action is to approve the
documented production redeploy, rerun `make verify-deploy`, perform the manual
browser smoke check, and then record the incident sequence below.

### Exact recording sequence

1. Open the Dependency Cartography page and show the heterogeneous fleet and
   trusted `vendor_portal` source.
2. Show the machine-readable sales → support → finance lineage, including the
   clean engineering branch.
3. Announce delayed discovery of compromise and compute the blast radius:
   32 affected, 575 unrelated memories preserved.
4. Revoke exact descendants; show the six-hop chain/affected state disappear
   while unrelated state remains.
5. Quickly show `make demo` refusing an export citing untrusted content and
   replay/idempotency removing nothing further.
6. Show one fresh live evidence row and the Google stack: ADK, Gemini/Vertex,
   Memory Bank, Firestore, and the control plane. State the shared
   process/graph claim boundary honestly.
7. Say: “Custody can trace a poisoned memory through an AI-agent fleet and
   surgically undo the damage without resetting everything.” State that G5 is
   still BLOCKED on real elapsed time.

READY TO RECORD: **NO — pending production redeploy and manual
browser-console/UI smoke.**

## Historical pre-refresh baseline

Verdict: **needs fresh live proof and a recorded demo before submission; the
offline implementation is green and the Fleet thesis is stronger.**

The official track asks for a scalable institutional-agent network with
cross-department cataloging, asynchronous persistent context, enterprise data
controls, Gemini 3.5+, a Google agent framework, and Google Cloud
infrastructure. Judging is 40% operational utility, 30% architecture/stack,
and 30% demo/production readiness. See the [official hackathon page](https://allthingsagentichackathon.devpost.com/).

## Checks run

| Command | Result |
| --- | --- |
| `make check` | PASS — ruff clean; 377 tests pass in 0.133s |
| `make hardening-check` | PASS — check plus incident, cost, demo, revoke, isolate, and gates preflight |
| `make incident` | PASS — 32 affected descendants; 575 unrelated records survive; replay is idempotent |
| `make cost` | PASS — 600-record fixture; exact revocation destroys 40 and preserves 560 |
| `make demo` | PASS — ungoverned export allowed; governed export refused; 2/3 events withheld |
| `make revoke` | PASS — cross-department chain removes 4 records; user record survives; replay removes 0 further |
| `make isolate` | PASS — cross-department vouches refused; trust/quarantine remain scoped |
| `make gates` | 3 PASS, 0 FAIL, 2 BLOCKED — G1 is older than 24h; G5 has no fresh elapsed-time proof |
| `make fleet-gates` | Structural gates PASS; freshness BLOCKED/FAIL because the captured artifact is from 2026-08-17 |
| `make chain-gates` | Structural gates PASS; freshness BLOCKED/FAIL because the captured artifact is from 2026-08-17 |
| `git diff --check` | PASS |

The test count increased from the 376-test baseline to 377 with one new shared-
graph adapter test. A targeted run of the 15 adapter/failure tests also passed.

## Fleet test

Status: **pass for the demonstrated claim boundary; current live status is
blocked until refreshed.**

Custody visibly represents more than repeated chatbot calls:

- `scripts/live_fleet.py` defines 25 named department roles.
- Each role runs a real Google ADK `Runner`/Gemini 3.5 conversational turn and
  a tool-origin write through the governed Memory Bank path.
- Sales and finance share one tool; one revocation removes exactly those two
  tool-origin memories while 23 unrelated departments retain theirs.
- `scripts/live_chain.py` adds sales → support → finance propagation and an
  engineering clean branch.

Boundary to state in the demo: the proof uses one shared process-wide graph,
one Memory Bank engine, and `{app_name, user_id}` scopes; it does not claim 25
independent Cloud Run identities. The live chain uses real ADK/Gemini turns and
constructs the `load_memory` citation event from the exact retrieved text so
the provider-neutral provenance core is exercised deterministically.

## Multi-agent causality test

Status: **pass offline and in the captured live-chain artifact; refresh needed
for a current live claim.**

The machine-represented path is:

```text
compromised tool response
  -> sales model-derived record
  -> support load_memory citation
  -> support derived record
  -> finance load_memory citation
  -> finance derived record
```

`CustodyRecord.derived_from` stores each edge. `CustodyGraph.descendants()`
walks those edges without depending on Gemini or any provider-specific graph
format. The captured `proof-out/live-chain.json` contains six chain-hop records,
and its structural judge confirms the exact parent relationships.

## Recovery test

Status: **pass for deterministic selective recovery.**

- The incident fixture computes the blast radius before mutation.
- Revocation removes roots and all meaningful descendants, not whole users or
  departments.
- Unrelated records remain live.
- Replaying the same revocation id is idempotent.
- `RevokingMemoryBankGraph` deletes the deterministic `memory_id` targets and
  tolerates already-gone memories.
- The hardening fix now publishes records to the graph only after downstream
  persistence succeeds, so an unavailable Memory Bank cannot create phantom
  provenance records.

Mixed ancestry remains conservative: a record with one poisoned parent is
removed even if another parent is clean. Custody currently provides lineage
containment, not semantic independent-evidence adjudication; that is an honest
and intentional boundary.

## Scale test

Status: **architecture and captured proof pass; fresh live proof required.**

The offline fixture handles 5 departments, 8 tools, 40 sessions per department,
and 600 records. The captured live proof handled 25 named department workers.
The new `provenance_graph` seam lets ADK shells share the existing graph port or
receive a durable Firestore-backed implementation without changing the default
offline constructor.

Expensive live model calls are not part of the first judging action. Use the
deterministic incident narrative first, then show the captured/fresh N=25 proof
as scale evidence.

## Better-model test

Status: **pass.**

If Gemini becomes much smarter, Custody remains useful. The risk is not only
poor reasoning; it is persistent state that has already crossed agent
boundaries. Provenance, blast-radius traversal, containment, revocation, and
recovery remain necessary regardless of model quality. Gemini drafts Reviewer
text, but it does not decide origin or trust.

## Provider-switch test

Status: **pass for the core contract.**

`custody/origin.py`, `custody/graph.py`, `custody/service.py`, and the graph
stores do not depend on Gemini-specific semantics. ADK is an integration shell;
the provenance record carries source, revision, content digest, and parent ids.
A different model provider can emit equivalent structural events while the
same security history and revocation graph remain intact.

## Google/Gemini/ADK integration test

Status: **substantive, with stale live artifacts needing refresh.**

- Gemini 3.5 Flash via Vertex AI powers live agent turns and Reviewer drafting.
- Google ADK `BaseMemoryService` is the governed integration port.
- Vertex AI Memory Bank is the persistent memory substrate.
- Cloud Run hosts the control plane and live MCP surface.
- Firestore backs the durable graph, revision catalog, demotion log, and
  dispatch replay state in the deployed control-plane paths.
- Agent Registry, Agent Gateway, Model Armor, Cloud Scheduler, and Agent
  Observability each have proof producers/judges with explicit boundaries.

The new adapter seam is additive: callers may pass
`provenance_graph=<shared-or-durable-graph>` to `CustodyMemoryBank`; callers
that omit it retain the previous in-memory behavior.

## Demo Gate

Verdict: **blocked for submission packaging, green for the offline proof.**

| Gate | Status | Evidence |
| --- | --- | --- |
| One-command demo | PASS | `make incident`; `make hardening-check` for the full offline loop |
| Setup instructions | PASS | `README.md` Spin up section |
| Expected output | PASS | `README.md`, `scripts/incident.py`, `scripts/revoke.py` |
| Verification command | PASS offline / BLOCKED live freshness | `make check`, `make gates`, `make fleet-gates`, `make chain-gates` |
| Failure mode | PASS | README and gate output distinguish FAIL from BLOCKED; stale evidence never passes |
| README demo path | PASS | README points to `make incident`, `make gui`, and the core demos |
| Screenshot/video artifact | BLOCKED | HTML pages and `web/exports/system-diagram.png` exist; demo video capture remains outstanding |

## Judge-memory test

The sentence to repeat after the demo:

> Custody can trace a poisoned memory through an AI-agent fleet and surgically
> undo the damage without resetting everything.

The proof order should be:

1. Show the fleet and the trusted source.
2. Show sales → support → finance propagation in the evidence ledger.
3. Announce the late compromise and compute the blast radius.
4. Revoke exact descendants.
5. Show the clean branch and unrelated fleet state still operating.
6. Close with ADK + Gemini/Vertex + Memory Bank + Firestore and the provider-
   independent graph boundary.

Do not lead with Model Armor, Registry, or a generic policy list; those support
the control plane but are not the remembered capability.

## Outcome ledger

### Decision 1

Decision: publish graph state only after successful downstream persistence.
Lane: fleet-wide provenance/recovery.
Artifact: `custody/service.py` and the Memory Bank outage regression test.
Acceptance gate: failed write leaves the graph empty; full suite remains green.
Result: `make check` PASS; the focused outage test passes.
Next action: keep downstream writes idempotent and rerun live Memory Bank proof.
Kill condition: any successful-path regression or duplicate graph publication.
Status: shipped

### Decision 2

Decision: expose optional shared/durable graph injection through the ADK shell.
Lane: agentic developer tooling / fleet control plane.
Artifact: `CustodyMemoryBank(provenance_graph=...)` and shared-graph test.
Acceptance gate: two banks resolve one cross-session lineage through one graph.
Result: targeted and full suites PASS.
Next action: wire a fresh deployed proof to the durable graph when the deployment path is ready.
Kill condition: default ADK behavior changes or Firestore graph cannot satisfy the existing port.
Status: shipped, deployment wiring pending

### Decision 3

Decision: make the offline pre-submission loop one command and record its claim boundaries.
Lane: Fleet-track demo reliability.
Artifact: `make hardening-check` and this validation file.
Acceptance gate: offline checks pass; stale external proofs remain BLOCKED.
Result: target exits 0 with 377 tests, deterministic demos, and 3 PASS/2 BLOCKED gate output.
Next action: refresh live G1/fleet/chain evidence and record the demo video.
Kill condition: preflight ever reports stale/missing live proof as PASS.
Status: shipped

## Known gaps and next highest-leverage action

- `web/fleet.html` remains a static, user-owned page that is not generated by
  `make gui`; do not rely on it as current proof until it is evidence-gated.
- The current live proof artifacts are stale as of 2026-08-21.
- G5's real elapsed-time requirement remains blocked until its clock has actually
  elapsed; no timestamp simulation is acceptable.
- The ADK durable-graph injection seam is available but is not a migration of
  the existing live N=25/chain scripts.
- No action/effect nodes or independent-evidence adjudication were added.

Next highest-leverage action: refresh `make live-g1`, `make live-fleet`, and
`make live-chain`, run their independent gates, then record one unedited demo
using the judge-memory sequence above.
