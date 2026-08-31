# Custody Hackathon Hardening Audit

Date: 2026-08-21
Branch: `hardening/fleet-track-pre-submission`
Lane: agentic developer tooling — fleet-wide provenance, containment, and recovery
Phase: Phase 1 audit complete; implementation changes were not yet applied when this audit was written.

## Artifact and baseline

This audit is the first artifact for the hardening session. The implementation
artifact will be a small, reviewable diff plus deterministic tests. The final
artifact will also include `SUBMISSION_VALIDATION.md`.

The worktree was already dirty before this branch was created. Existing changes
to `web/architecture.html`, `web/incident.html`, untracked web pages, research
directories, and submission documents are preserved and are not treated as part
of this hardening diff.

Read before editing:

- `README.md`, `docs/architecture.md`, `DECISIONS.md`, `HANDOFF.md`,
  `EVALUATION_GUIDE.md`, `SUBMISSION_HANDOFF.md`, and the submission draft.
- `Makefile`, `Dockerfile`, `pyproject.toml`, `requirements.txt`, and
  `web/vercel.json`.
- The core in `custody/`, the live proof producers and judges in `scripts/`,
  the incident/demo scripts, and the tests in `tests/`.
- The repository's APOSD and DDIA guidance.

Baseline checks, run before implementation:

| Check | Result |
| --- | --- |
| `make check` | PASS — ruff clean; 376 tests pass in 0.146s |
| `make incident` | PASS — 32 descendants, 575 unrelated records survive |
| `make cost` | PASS — 600-record fixture; exact descendants preserve 560 records versus a blunt purge |
| `make demo` | PASS — ungoverned export allowed; governed export refused |
| `make revoke` | PASS — cross-department chain revoked; replay idempotent |
| `make isolate` | PASS — cross-department vouch attempts refused |
| `make gates` | 3 PASS, 0 FAIL, 2 BLOCKED; G1 is older than 24h and G5 lacks fresh elapsed-time evidence |

The current ignored live artifacts were captured on 2026-08-17. They are useful
for architecture understanding, but are not fresh enough to call current live
evidence on 2026-08-21. The final validation must keep that distinction.

## Exact Fleet-track story

The official All Things Agentic Hackathon framing for the Fortified Enterprise
Fleet track is a scalable network of institutional agents connected to
enterprise infrastructure, with cross-department cataloging, weeks-long
asynchronous context, production data, and compliance/security controls. The
required stack includes Gemini 3.5 or newer, a Google agent framework, and
Google Cloud infrastructure. The judging weights are Innovation & Operational
Utility 40%, Architectural Discipline & Tech Stack 30%, and Demo & Production
Readiness 30%.

Custody's strongest matching story is:

> A vendor tool trusted by a large heterogeneous agent fleet is discovered to
> be compromised after its output has propagated through shared persistent
> state. Custody reconstructs the cross-agent lineage, revokes exactly the
> affected descendants, preserves unrelated state, and lets healthy operation
> continue.

The memorable sentence should stay:

> Custody can trace a poisoned memory through an AI-agent fleet and surgically
> undo the damage without resetting everything.

This keeps the visible product large. The moat underneath is the provider-
independent graph of source observations, agent-produced state, cross-agent
retrievals, derived state, and revocation decisions.

## Architecture understood

### Current fleet topology

| Layer | Current evidence | Assessment |
| --- | --- | --- |
| Offline fleet fixture | `scripts/cost.py`: 5 departments, 8 tools, 40 sessions per department, 600 memory records | Strong deterministic scale/utility fixture; not an agent-runtime proof by itself |
| Incident narrative | `scripts/incident.py`: sales → support → finance, plus 5-department background state; exact descendant walk and clean survivors | Strong 30-second thesis proof; offline and deliberately synthetic |
| Live fleet | `scripts/live_fleet.py`: 25 named department workers; real ADK `Runner`/Gemini turn per department; one shared `CustodyMemoryBank` and Memory Bank engine; one shared tool used by sales and finance; 23 independent tools | Strong fleet-wide reach and selective deletion proof; single shared process/engine boundary is explicit |
| Live causal chain | `scripts/live_chain.py`: sales, support, finance plus engineering negative control; six chain-hop records; two `load_memory` content-hash edges; one revocation | Strong live lineage proof; citation events are structurally constructed around real Gemini turns, as stated by its claim boundary |
| Trust/control | `custody/catalog.py`, `revision.py`, `control_plane.py`; Registry/revision, Gateway, Model Armor, Scheduler/Auditor, Firestore, and Observability proof paths | Substantive Google integration, but each live proof has its own scope and freshness window |
| Recovery | `CustodyGraph.revoke`, `RevokingMemoryBankGraph`, Firestore/SQLite replay, idempotent revocation | Strong selective recovery primitive; external actions are not themselves graph nodes |

The production control-plane path can inject `FirestoreCustodyGraph` through
`custody/control_plane.py`, but the ADK-facing `CustodyMemoryBank` currently
creates an in-memory graph internally. The live N=25 and live-chain proofs use
one shared in-process graph. This is acceptable for the captured proof boundary
but is not yet a complete multi-instance deployment contract.

## A. Fleet legitimacy

### What is real

- There are 25 named heterogeneous department roles in the live fleet proof,
  not repeated anonymous prompts.
- Each live department runs a real ADK/Gemini conversational turn and writes a
  tool-origin record through the same `CustodyMemoryBank` →
  `AgentEngineMemoryBank` path.
- Sales and finance independently use the same tool name, so one revocation
  must cross department scopes.
- The live chain has distinct sales, support, and finance roles, plus an
  engineering clean branch.
- Shared state is real at the graph/Memory Bank boundary: all live workers use
  one graph and one engine, with `{app_name, user_id}` Memory Bank scopes.
- Supervisor/control behavior exists in the control plane, including vouch,
  demote, scheduled sweep, revocation, quarantine, export gating, and durable
  audit state.

### Judge doubt to preempt

> “This is basically one agent repeated several times.”

The risk comes from two boundaries that the demo must say out loud:

1. The live fleet proof uses one process-wide `CustodyMemoryBank` and Memory
   Bank user scopes, not 25 independent Cloud Run identities.
2. The live chain uses real ADK/Gemini turns, but the `load_memory` citation
   event is constructed from the exact live retrieval text so the core's
   provider-neutral event contract can be exercised deterministically.

Those are honest limitations, not reasons to shrink the product. The demo must
lead with the fleet/control-plane behavior and show the exact provenance edges,
then state the boundary in the architecture slide.

### Fleet finding

- **P1 — evidence surface drift:** `web/fleet.html` is a hand-authored static
  page and `make gui` does not regenerate it from `proof-out/live-fleet.json`.
  It can therefore display “25 live agents” and “35/35 PASS” after evidence is
  stale or missing. Existing user-owned web changes are intentionally not
  overwritten in this session. Treat the page as a supporting visual only until
  it is made evidence-gated.

## B. Incident propagation

The current machine-represented path is valid:

1. A tool `function_response` becomes a `CustodyRecord` with `source_tool` and
   an immutable id.
2. A same-invocation model restatement becomes `DERIVED` and points to the
   predecessor through `derived_from`.
3. A later `load_memory` response is resolved by content hash against the
   shared graph and points to the prior record.
4. The consuming agent's restatement points to its retrieval record.
5. `CustodyGraph.descendants()` walks the graph independent of model provider,
   role, department, or number of hops.

Evidence:

- `tests/test_origin.py` proves same-invocation taint and derived edges.
- `tests/test_cross_session.py` proves a real governed retrieval bridges two
  departments and is later revoked.
- `scripts/incident.py` proves the sales → support → finance chain offline.
- `proof-out/live-chain.json` contains the six live chain records and the exact
  `derived_from` edges; its independent judge rereads Memory Bank by recomputed
  `memory_id`.

### Propagation finding

- **P1 — graph publication ordering:** `CustodyMemoryService.add_session_to_memory`
  currently adds trusted records to the graph before the downstream write
  completes. A Memory Bank outage can leave graph records for memories that
  never landed. This is a demonstrated correctness problem, not a speculative
  refactor, and it directly affects partial-agent failure/recovery.

## C. Selective recovery

The current semantics distinguish the required categories as follows:

| Category | Current behavior | Evidence |
| --- | --- | --- |
| Contaminated descendants | Walked from roots by `source_tool` and `derived_from` | `tests/test_graph.py`, `scripts/revoke.py` |
| Unrelated state | Not reachable from the compromised roots; survives | `tests/test_graph.py`, `scripts/incident.py`, live chain negative control |
| Affected agents/departments | Inferred from session/user scope in proofs and from record author/invocation | `scripts/live_fleet.py`, `scripts/live_chain.py` |
| Shared state with mixed ancestry | Conservative taint: any removed parent makes the mixed record removable | `test_a_record_with_two_parents_survives_unless_both_are_pulled` |
| Already-revoked state | Same revocation id returns the stored result; Memory Bank deletes tolerate 404 | `tests/test_graph.py`, `tests/test_agent_engine_memory_bank.py` |

The mixed-ancestry behavior is intentionally conservative and currently
justified by the write-time security contract: a state item with one poisoned
parent is not trusted merely because another parent is clean. Custody does not
claim independent-evidence adjudication. The demo must describe “selective by
lineage,” not “semantic truth resolution.”

### Recovery finding

- **P1 — durable graph seam is incomplete at the ADK adapter:** the deployed
  control plane can use Firestore, but the standard ADK `CustodyMemoryBank`
  path has no way to receive a durable/shared graph. Multiple wrapper
  instances would otherwise create separate provenance histories. This is a
  narrow dependency-injection gap, not a reason to replace the graph or
  Memory Bank.

## D. Hackathon spectacle

### Strong points

- The 30-second incident is legible: trusted source → delayed compromise →
  blast radius → exact descendants removed → clean state survives.
- The output and GUI show a meaningful asymmetry: 32 affected versus 575
  preserved in the incident fixture, and 2 revoked versus 23 untouched in the
  live N=25 proof.
- The memorable capability is not detection alone; it is deterministic,
  cross-agent blast-radius reconstruction plus surgical deletion.
- ADK is a real `BaseMemoryService` integration, not a wrapper around ordinary
  chat. Gemini 3.5 on Vertex AI powers live agent turns and the Reviewer, while
  provenance decisions remain model-independent.
- Google Cloud integration is substantive across ADK, Vertex AI Memory Bank,
  Cloud Run, Firestore, Agent Registry, Gateway, Model Armor, Scheduler, and
  Observability, with proof-specific claim boundaries.

### Weak points

- The primary GUI currently opens on the incident page; the N=25 fleet page is
  secondary and static.
- `make incident` is intentionally offline and its day-1/day-16 timestamps are
  fixture narrative, not live elapsed time. `make gates` correctly keeps G5
  blocked until real time and fresh proof exist.
- The live N=25 proof is sequential and expensive. It is appropriate as a
  captured proof artifact, not as the first action in a live judge demo.
- The product has many proof surfaces. Showing all of them would dilute the
  single Fleet story; only incident → chain → containment → clean survivor
  should be primary.

### Spectacle findings

- **P1 — stale/live boundary can embarrass judging:** live proof artifacts are
  older than the 24-hour freshness window. Refresh G1, fleet, and chain proofs
  before filming; do not convert stale artifacts into PASS.
- **P2 — action visibility:** `ExportGateway` guards egress but actions are not
  persisted as graph nodes. The current thesis only requires recovery of
  state/descendants, so adding action lineage now would be a scope expansion.

## E. Demo reliability

### Existing safeguards

- Core checks are offline and fast; 376 tests pass without a cloud account.
- Demo fixtures are deterministic (`random.Random(seed=7)` in `scripts/cost.py`).
- Repeated revocation is idempotent.
- Memory Bank writes pin `memory_id`, and live deletion derives the target from
  the record id rather than search or content matching.
- Live proof producers delete stale output before a failed rerun, and independent
  judges reread proof artifacts rather than trusting producer assertions.
- Firestore/SQLite replay and failure-injection tests cover restart, timeout,
  malformed surface, and unavailable Memory Bank paths.

### Reliability findings

- **P1 — phantom graph state on downstream failure:** selected for immediate
  fix.
- **P1 — partial distributed-memory contract:** the ADK wrapper's default graph
  is process-local; selected for an additive durable-graph injection seam, not
  a migration.
- **P1 — static fleet page can claim stale proof:** left untouched because it is
  pre-existing user work and changing it safely would require an evidence-page
  decision; document as a pre-submission gate.
- **P2 — proof freshness is operational, not automated:** the offline suite
  cannot refresh Google evidence. The final runbook must require fresh proof
  checks before filming.
- **P2 — live fleet is sequential:** 25 model calls increase cost and time.
  Keep the captured N=25 proof secondary; use the deterministic offline incident
  as the live narrative fallback.
- **P2 — live chain's manually spliced citation event:** technically valid for
  the provider-neutral core contract, but must remain clearly disclosed.

No P0 finding was observed. The baseline has no test failure, startup failure,
missing-directory failure, or flaky ordering failure in the offline path.

## Adversarial scenario review

| Scenario | Current result | Evidence / disposition |
| --- | --- | --- |
| 1. A → M1 → B/C → M2 → D | Pass for sequential chains and cross-department retrieval; live chain proves sales → support → finance | `tests/test_cross_session.py`, `scripts/live_chain.py`; no new schema needed |
| 2. Clean branch preservation | Pass | Mixed-parent and unrelated-root tests; live engineering negative control |
| 3. Independent X and Y evidence | Conservative removal if one parent is poisoned; not an evidence-weighting system | Existing graph test documents the semantics; no unsupported “clean knowledge survives” claim |
| 4. Long-delay discovery | Offline narrative only; live elapsed-time proof is separately G5 and currently blocked/stale | Keep timestamps labeled as fixture data; do not fake elapsed time |
| 5. Repeated revocation | Pass and idempotent | Graph, durable-store, control-plane, and Memory Bank deletion tests |
| 6. Cross-role propagation | Pass in offline and live chain paths | `scripts/incident.py`, `scripts/live_chain.py` |
| 7. Partial fleet failure | Write failure currently raises but can leave graph state ahead of persistence | Selected fix plus regression test |

## DDIA review

Chosen data-system direction: retain the existing append-only custody records,
`derived_from` edges, and provider-neutral `CustodyGraph`; publish records to
the graph only after the downstream memory write succeeds; make the graph an
optional injected dependency of the ADK shell so Firestore-backed deployments
can share the same graph port.

Key invariants:

1. A record is not eligible for cross-session resolution until its downstream
   memory write has completed successfully.
2. Retried `memory_id`-pinned writes remain idempotent, so a timeout after a
   committed write can be safely retried before graph publication.
3. The default constructor remains in-memory and behavior-compatible.
4. Revocation continues to use the existing deterministic traversal and
   idempotency contract.
5. A model provider does not decide provenance, trust, or graph reachability.

Rejected alternatives:

- Replacing the graph with a new database or orchestration framework: too much
  regression risk and no improvement to the narrow proof.
- Making mixed evidence automatically safe: unsupported by the current
  write-time semantics and would weaken containment.
- Adding a new action/effect ledger: valuable future work, but outside this
  pre-submission slice.
- Making every live proof call 25 agents during judging: expensive and less
  reliable than captured evidence plus a deterministic offline narrative.

DDIA verdict: **risky but shippable for the stated proof boundary before the
selected fix; not a complete multi-instance production contract until the
durable graph seam is exposed and used.** The selected additive seam reduces
that risk without migrating the live demo.

## APOSD decision

The changed module boundary is the memory-service admission boundary. The
complexity belongs in `CustodyMemoryService`, which already owns the ordering
between quarantine, downstream persistence, and graph publication. The ADK
adapter should only pass the graph capability through; it should not duplicate
the policy.

No pass-through or special-general mixture is introduced by the selected
changes. The existing static fleet page remains a known evidence-surface smell,
but is not rewritten in this branch.

## Selected changes — maximum three

### 1. Publish provenance only after successful downstream persistence

Files: `custody/service.py` plus deterministic failure tests.

Why: fixes the demonstrated phantom-record bug and closes the partial-agent
failure hole. It preserves all successful behavior, keeps retry/idempotency in
the existing writer, and does not alter taint or revocation semantics.

Acceptance gates:

- A failed trusted write raises and leaves the graph unchanged.
- A successful write still adds exactly the trusted records and preserves
  retrieval lineage.
- An untrusted session still never reaches the writer or graph.
- `make check`, `make incident`, `make revoke`, and `make isolate` remain green.

### 2. Expose an additive graph-injection seam through `CustodyMemoryBank`

Files: `custody/adapters/adk.py` plus adapter tests.

Why: lets a deployed ADK fleet use the existing Firestore graph or another
shared graph implementation through the explicit `provenance_graph` capability,
without replacing the ADK adapter or changing the default offline behavior.
This makes the fleet-wide control-plane boundary explicit and testable while
preserving the existing `graph()` accessor.

Acceptance gates:

- Existing constructor behavior remains unchanged.
- Two adapter instances given one graph resolve shared cross-session lineage.
- The injected graph is the same graph returned by `graph()` and used by
  revocation callers.
- No cloud dependency is added to the core and the full offline suite remains
  green.

### 3. Add a single local hardening preflight target and validation artifact

Files: `Makefile` and `SUBMISSION_VALIDATION.md`.

Why: make the pre-submission proof loop repeatable without changing the demo or
adding a network dependency. It will run the existing offline checks and point
to the explicit fresh-live-proof steps, claim boundaries, and failure modes.

Acceptance gates:

- One command runs the offline hardening checks.
- The validation document records the Fleet, causality, recovery, scale,
  better-model, provider-switch, and judge-memory tests.
- Freshness is reported honestly; missing/stale cloud artifacts are BLOCKED,
  never PASS.

Intentionally not selected: rewriting the fleet UI, adding a second memory
store, adding semantic evidence adjudication, or migrating the live N=25/chain
proof to Firestore in this session.
