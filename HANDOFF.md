# Custody recovery handoff, 2026-08-14 (fleet review closed: Provenance Auditor, Custody Reviewer, and N=5 department agents all landed)

This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

## Start here if you are the next session

The user asked, on request, to review the "fleet" section of the hackathon
product-mapping table against actual code, then build the gaps found for
real, one at a time, each closed with its own live proof and its own
handoff so work can continue in a fresh Claude session. Three gaps were
found (`.claude/SESSION_CONTRACT.md`, "Fleet review, 2026-08-14" section);
user's stated order: **Auditor, then Reviewer, then N agents.** All three
are now closed; the user chose N=5 for the third.

1. **Provenance Auditor — closed 2026-08-14**, live-proven. See below.
2. **Custody Reviewer — closed 2026-08-14**, live-proven. See below.
3. **N department worker agents — closed 2026-08-14**, live-proven, N=5.
   See below. All three fleet-review findings are now closed.

## Provenance Auditor: closed 2026-08-14, live-proven

`/vouch` grants trust; `/demote` (new) withdraws it, with the same
cross-department refusal rule (`custody/catalog.py`'s `TrustCatalog.demote`,
mirroring `request`). Demotions are durably logged
(`custody.firestore_store.FirestoreDemotionLog`, create-fails-if-exists,
replay-on-construction, same pattern as `FirestoreAuditorLog`). The
existing daily Cloud Scheduler `/auditor` tick (G5's heartbeat) now also
sweeps every outstanding demotion through `CustodyGraph.revoke`,
deterministically — no LLM anywhere in this path, consistent with the
project's own "no model decides a fact" rule. `CustodyGraph.revoke`'s
existing idempotency (keyed on the demotion's own deterministic id) meant
no second bookkeeping table was needed.

Redeployed `custody-control-plane` to Cloud Run revision
`custody-control-plane-00004-ttb` (same service, same env, same posture,
user-authorized live during the session — the original scoping did not
anticipate needing a redeploy). Live proof (`make live-auditor`, proof
`668ad6bb08384da889c76a008e6a218d`, `proof-out/live-auditor.json`): demote
a live tool, confirm via an immediate `GET /custody/{id}` reread that
*nothing* is revoked yet (the async gap is real, not simulated), trigger
`/auditor`, confirm via a second, independent live reread
(`scripts/auditor_gates.py`, its own `gcloud`-derived URL, not the
producer's) that the record now carries the swept revocation.
`make auditor-gates` reports 9/9 PASS. 310/310 offline tests pass
(`tests/test_catalog.py`, `tests/test_control_plane.py`,
`tests/test_firestore_store.py` all extended). Full write-up in
`.claude/SESSION_CONTRACT.md`'s "Sub-build: real Provenance Auditor"
section and `README.md`'s new "The Provenance Auditor" section.

**Side effect worth knowing:** the redeploy meant `proof-out/g1.json` was
regenerated too (`make live-g1`), since G1's own evidence had recorded the
now-superseded Cloud Run revision. `make gates` reports G1 PASS against
the fresh evidence, revision `custody-control-plane-00004-ttb`. No other
G1 behavior changed.

## Custody Reviewer: closed 2026-08-14, live-proven

`custody/review.py` (new module) closes the fleet-review finding that the
only live Gemini call in the repo was a connectivity echo
(`scripts/live_g1.py`'s `_gemini_proof`, asked to return a fixed string).
`draft_verdict` takes one `Quarantined` item (`custody/service.py`) and an
injected `explain` callable, returning a `Verdict` (`department`,
`source_tool`, `summary`, `drafted_at`) — no trust or origin field, and the
module imports neither `custody.catalog` nor `custody.graph`, checked by
both a unit test and an AST-parse test in `tests/test_review.py` (5 new
tests, 315/315 offline total) so a future edit that wires either import
back in fails the suite rather than silently opening a fact-deciding path.

No control-plane or Cloud Run change was needed: the quarantine item is
produced in-process by the same `ControlPlane.ingest` logic G2 already
proves offline, so the only new live surface is the Gemini call itself.
`make live-review` (proof `22d187b18ff54ccd809c7eeff52e6394`,
`proof-out/live-review.json`): an ungranted tool's response carrying a
per-run random marker is quarantined, then `gemini-3.5-flash` through
Vertex AI is given that exact text and asked to draft a verdict. The
response correctly explained the attempted export and reproduced the
marker, proving the call read the specific quarantined content rather than
echoing a fixed string. `make review-gates` reports 9/9 PASS: 8 offline
structural checks plus one independently issued, separate Gemini call
under the project's own credentials at judge time (there is no durable
Cloud resource to reread here, so the independent check re-makes the live
call instead of re-reading one, the same substitution O1 made for Cloud
Trace storage). Full write-up in `.claude/SESSION_CONTRACT.md`'s
"Sub-build: real Custody Reviewer" section and `README.md`'s new "The
Custody Reviewer" section.

**Non-goal, stated in the artifact and every write-up:** no console or
human-facing review queue exists yet. A verdict is read from
`proof-out/live-review.json`; any resulting demotion or revocation still
goes through the existing `/demote`/`/revoke` endpoints, driven by a
human.

## N department worker agents: closed 2026-08-14, live-proven, N=5

Only one live ADK agent had ever run before this, once per proof script,
one department per invocation — the fleet's own claim, that a compromised
tool is "identified and pulled ... across every department, agent and
session," had never been exercised at N>1. Checked in code before
scoping, not assumed: `CustodyGraph.revoke` (`custody/graph.py`) matches
descendants by tool name alone, and `CustodyRecord` carries no department
field at all — intended, matching the claim above, but untested at scale.

`scripts/live_fleet.py` (new) runs five live department worker agents
(`sales`, `legal`, `hr`, `finance`, `engineering`), each a real ADK
`Runner`/`gemini-3.5-flash` conversational turn plus one tool-origin
write, through the exact `CustodyMemoryBank` -> `AgentEngineMemoryBank`/
`write_record` wiring G1 already proved. All five share one
`CustodyMemoryBank` instance (one process-wide `CustodyGraph`, mirroring
production, not five isolated ones) against the one already-owned Agent
Engine `6936011268348182528` — no new Cloud Run services or Agent Engine
identities; Memory Bank's own `{app_name, user_id}` scoping is what
separates the five departments. `sales` and `finance` independently trust
and invoke a tool with the *same name*, `cross_dept_export_tool`; `legal`,
`hr`, and `engineering` each use a distinct tool name. No changes to
`custody/graph.py`, `custody/catalog.py`, `custody/origin.py`,
`custody/control_plane.py`, or any `custody/adapters/*` file — this is a
proof-at-scale build over already-correct, already-tested mechanisms, not
a new one.

Live proof (`make live-fleet`, proof
`2f5461ce99ba46aebe7f43ac72595612`, `proof-out/live-fleet.json`): all five
departments' tool-origin facts are written and independently retrievable;
one revocation of the shared tool (`RevokingMemoryBankGraph.revoke`)
removes exactly `sales` and `finance`'s tool-origin memories from both
departments, while `legal`, `hr`, and `engineering`'s own memories stay
retrievable, untouched. `make fleet-gates` (new,
`scripts/fleet_gates.py`) reports 15/15 PASS: 10 offline structural
checks plus 5 independent live Memory Bank rereads (`memories.get` by a
`memory_id_for`-recomputed name, not the producer's claim — 2 confirming
deletion, 3 confirming survival). `make check` 315/315 offline, unaffected.
`make gates` reports the same baseline as before this sub-build (G1/G2/G3/G4
PASS, G5 correctly BLOCKED). Full write-up in `.claude/SESSION_CONTRACT.md`'s
"Sub-build: N department worker agents" section and `README.md`'s new "The
fleet at N=5" section.

**Non-goal, stated in the artifact and every write-up:** this does not test
`TrustCatalog`'s per-department grant boundary (a department cannot
vouch/demote another's tool) — that is already proven offline and live,
unchanged, by the Provenance Auditor sub-build above. This build proves the
derivation graph's cross-department revocation *reach* instead, a
different, previously-unproven property.

## Lane and artifact

Lane: agentic security infrastructure, built as an evidence-gated systems
project for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet.

Six capabilities are complete and independently judged:

- G1 (Cloud Run/Vertex/ADK/Memory Bank) and R1 (stale Registry): complete
  before the S1/M1/O1 session began.
- S1 (Gateway): `proof-out/live-gateway.json`, `make gateway-gates` 20/20 PASS.
- M1 (Model Armor): `proof-out/live-model-armor.json`, `make model-armor-gates`
  9/9 PASS.
- O1 (Observability): `proof-out/live-observability.json`,
  `make observability-gates` 7/7 PASS.
- **R2 (dispatch-bound attestation, new this session):**
  `proof-out/live-revision-binding.json`, `make revision-binding-gates`
  13/13 PASS. Closes R1's own stated gap: an allowed `tools/call` is now
  cryptographically bound, server-side, to the `tools/list` read that
  authorized it.
- **D2 (selective live Memory Bank deletion):**
  `proof-out/live-memory-deletion.json`, `make memory-deletion-gates` 7/7
  PASS. A second, additive, opt-in write path
  (`custody/adapters/memory_bank.py`) makes revoked records genuinely
  deletable from live Memory Bank.
- **G1 migration onto D2's write path (new this session, 2026-08-14):** G1's
  live ADK Runner now writes through `AgentEngineMemoryBank`/`write_record`
  instead of `ingest_events`. Found and fixed a real integration gap first:
  `custody/adapters/adk.py`'s `_SessionRebuilding` never proxied
  `write_record`, so `CustodyMemoryBank` (what the real `Runner` sees) could
  not have reached D2's path regardless of downstream, until fixed. Live
  end to end against Agent Engine `6936011268348182528`:
  `proof-out/g1.json`, `make gates` reports G1 PASS reading the new shape.
  Also proves selective deletion through G1's own wiring (a tool-origin
  write, confirmed retrievable, then confirmed gone after its tool is
  revoked, sibling conversational memory untouched) and answers the
  retrieval-quality question live rather than assuming it: `write_record`
  returns two raw, unmerged per-event facts where `ingest_events` returned
  one Memory-Bank-synthesized fact. See `DECISIONS.md` #2 and
  `README.md`'s deletion section for the full write-up.

An eighth, G5's elapsed-time record, is **started and running, structurally
cannot be "complete" until real calendar time passes** — see below.

README.md and `.claude/SESSION_CONTRACT.md` are authoritative for all claim
text; do not restate any of it from memory, read them.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- Commits landed: `df334f1` (S1 fix + accumulated G1/R1 work), `94bcad4`
  (M1), `68f1b88` (G5 persistence/Scheduler start), `9c4174b` (O1),
  `7f7ea00` (R2 + D2), `0b4a816` (G1 migration onto D2's write path),
  `f9e19cd` (Provenance Auditor), `ce54bad` (Custody Reviewer).
- **Working tree carries uncommitted N-agent fleet work as of this
  handoff**: `scripts/live_fleet.py`, `scripts/fleet_gates.py`,
  `Makefile`, `README.md`, `.claude/SESSION_CONTRACT.md`, `HANDOFF.md`,
  and `proof-out/live-fleet.json`. Not yet committed — commit only on
  explicit user authorization, same rule as every other checkpoint here.
  Confirm with `git status` before assuming otherwise; do not trust this
  line if time has passed.
- None of the landed commits are pushed. Do not push without explicit
  authorization.

```sh
git status --short --branch
git diff --check
git log -8 --oneline --decorate
```

## Previously proven state, do not redo

- G1, R1, S1, M1, O1, R2, D2, the Provenance Auditor, the Custody
  Reviewer, and the N=5 department fleet, as above.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  correctly BLOCKED — its elapsed-time requirement is real, not a bug).

Known limitations that must remain explicit unless new direct evidence changes
them:

- **Closed 2026-08-14: G1's live ADK Runner now writes through D2's path
  and its memories are selectively deletable.** Any memory G1 wrote earlier
  through the old `ingest_events` path (before this session) remains
  outside what D2's mechanism can delete — that history does not
  retroactively become deletable, only writes from this migration onward.
- Behavior-only drift with identical `tools/list` is outside R2's claim by
  design — would need the server to attest its own running code identity, a
  materially different problem, deliberately not attempted.
- R2's replay ledger and D2's write path are correct per-process; nothing
  here claims multi-instance replay safety beyond the single-owned-instance
  scope R1/S1 already required.
- O1 does not independently verify Cloud Trace's own span storage — this
  project's Cloud Trace v1 API returns no default trace bucket for any trace
  exported to it, and v2 has no read endpoint. The independently-verified
  claim is the trace ID/span ID/digest binding recorded in Cloud Logging, not
  Cloud Trace storage. Do not claim more than that.
- The Gateway proof covers one owned Agent Runtime identity, one registered MCP
  projection, and four controlled calls. The Model Armor proof covers one
  owned Template and two controlled calls. Neither proves fleet-wide coverage.

## Owned Google Cloud scope

```text
project id:      project-988bc9fe-092c-4b32-90c
project number:  742122658452
region:          us-central1
organization:    521713171342

Agent Gateway:   custody-fleet-egress
AuthzExtension:  custody-fleet-iap-enforced
AuthzPolicy:     custody-fleet-request-authz
Registry service: custody-export-mcp
Registry MCP projection:
  agentregistry-00000000-0000-0000-8247-c8250af4b9b8
Agent Runtime (Gateway probe):
  projects/742122658452/locations/us-central1/reasoningEngines/5289382654590844928
Agent Runtime (G1/O1/D2):
  projects/742122658452/locations/us-central1/reasoningEngines/6936011268348182528
Registered Runtime Agent:
  agentregistry-00000000-0000-0000-5b70-78deb73916d5
Runtime principal:
  principal://agents.global.org-521713171342.system.id.goog/resources/aiplatform/projects/742122658452/locations/us-central1/reasoningEngines/5289382654590844928
MCP endpoint (custody-export-mcp, now serving R2's attestation middleware):
  https://custody-export-mcp-anexdhueiq-uc.a.run.app/mcp
  (last live revisions: custody-export-mcp-00011-rm5 / -00012-8kz; the
  service accepts CUSTODY_ATTESTATION_SECRET and
  CUSTODY_ATTESTATION_TTL_SECONDS env vars now, in addition to the existing
  CUSTODY_MCP_REVISION)
Model Armor Template:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/templates/custody-approved-tool-ingress
Control plane (Cloud Run, public):
  https://custody-control-plane-742122658452.us-central1.run.app
Firestore database:
  projects/project-988bc9fe-092c-4b32-90c/databases/(default), Native mode, us-central1
Cloud Scheduler job:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/jobs/custody-g5-auditor
Observability Cloud Logging log:
  projects/project-988bc9fe-092c-4b32-90c/logs/custody-observability
```

Repo-local Google credentials/configuration live under ignored `.gcloud/`.
Never print, copy, or commit credential contents.

**Live IAP resting state (S1's projection), last confirmed 2026-08-13:** exact
safe deny — `api.getAttribute('iap.googleapis.com/mcp.toolName', '') in
['custody_policy_canary', '']`. Re-read before any future mutation, never
assume it.

## R2: what was built (dispatch-bound attestation)

Scope: close R1's own stated gap — an allowed `tools/call` was not
cryptographically bound to the `tools/list` read that authorized it, and
IAP's static CEL conditions cannot carry a per-request digest across two
separate calls, so only the owned MCP server could close this, not the
Gateway.

`custody/revision.py` gained `mac`, `SurfaceAttestation`, and
`AttestationAuthority` (mint/verify, HMAC-signed, short-TTL, single-use
nonce, stdlib-only). `live/registry_attack/server/server.py` gained
`SurfaceAttestationMiddleware`: mints a token per tool on every
`tools/list`, and on `tools/call` recomputes the tool's live digest at the
instant of dispatch and refuses to run it on any digest mismatch, expiry, or
replay, before the tool body executes.

**A real implementation bug was found and fixed mid-build, not guessed at
against live infra:** the obvious channel, `MiddlewareContext.message.meta`,
does not carry the caller's token. FastMCP's own `tools/call` dispatcher
(`fastmcp/server/server.py`, `_call_tool_middleware`) rebuilds
`CallToolRequestParams(name=key, arguments=arguments)` from scratch before a
middleware ever sees it, discarding the request's real `_meta`. The token
only survives in the low-level MCP SDK's `request_ctx` contextvar, read via
`Context.request_context.meta`. Root-caused by reproducing in-process
(`fastmcp.Client(server.mcp)`, no live Cloud Run needed) before touching
live infra a second time.

`ToolSurface.from_tools_list` (`custody/revision.py`) now strips `_meta`
before computing a tool's revision digest — otherwise R2's own per-call
token would make every read's digest different, breaking R1's stability
guarantee. Regression test:
`test_per_response_meta_does_not_change_a_revision`.

Live proof: `scripts/live_revision_binding.py` deploys v1, mints a token,
positive-dispatches, replays the same token (refused, `REPLAYED`),
redeploys to v2, presents the stale v1 token (refused, `DIGEST_MISMATCH`,
dispatch count unmoved), then dispatches normally with a fresh v2 token.
`scripts/revision_binding_gates.py` independently rereads both denial log
entries and both Cloud Run revisions from Google Cloud by their own
server-issued identifiers.

**Non-goal, stated in every artifact:** closes the declared-surface TOCTOU
only. A behavior-only change under an identical `tools/list` remains
undetected — would need the server to attest its own running code identity.
Replay state is process-local, same single-instance scope R1/S1 already
require.

## D2: what was built (selective live Memory Bank deletion)

Scope: G3 proves revocation across `CustodyGraph`, but has never deleted the
underlying memory from live Memory Bank. Checked live twice against Agent
Engine `6936011268348182528` and closed as not viable through G1's
`ingest_events` write path: the API returns no created-memory name, and a
metadata-based consolidation guard (`REQUIRE_EXACT_MATCH`) also failed live
— two records with different `custody_record_id` metadata still collapsed
into one memory.

On request, a different write path was tested live instead of reasoned
about: `agent_engines.memories.create(config={"memory_id": <id>})` does not
share that consolidation behavior. Built as a **second, additive, opt-in**
write path:

- `custody/memory_bank.py`: `memory_id_for(record_id)`, a pure hash mapping
  a `CustodyRecord.id` to a valid Memory Bank `memory_id` — no stored state,
  always recomputable.
- `custody/service.py`: `RecordWriter` protocol.
  `CustodyMemoryService.add_session_to_memory` writes one record at a time
  through `downstream.write_record` when a downstream offers it; falls back
  to the existing whole-session `add_session_to_memory` otherwise. Every
  existing downstream (offline fakes, G1's `ingest_events` adapter) is
  **unchanged**.
- `custody/adapters/memory_bank.py`: `AgentEngineMemoryBank` (writes via
  `memories.create`) and `RevokingMemoryBankGraph` (wraps any graph's
  `revoke`, then deletes each removed record's memory by the same computed
  name).

Live proof (`scripts/live_memory_deletion.py`): one session writes two
trusted, different-tool records; both retrievable via `search_memory`;
revoking one tool deletes exactly its memory; a subsequent `search_memory`
no longer returns it while the sibling tool's memory is untouched.
`scripts/memory_deletion_gates.py` independently recomputes `memory_id_for`
for both records rather than trusting the producer's claim.

**Non-goal, as originally scoped:** at the time D2 was built, migrating G1
onto this path was explicitly deferred. **Done in the next session,
2026-08-14** — see "G1 migration" below. Content G1 wrote before that
migration, through the old `ingest_events` path, remains outside what this
mechanism can delete.

## G1 migration: G1's own writes are now selectively deletable

Scope: close the one gap D2 deliberately left open — G1's live ADK Runner
still wrote through `ingest_events`, so nothing it wrote could be
selectively deleted, even though D2's mechanism existed.

**A real integration bug was found and fixed first, not assumed away.**
`custody/adapters/adk.py`'s `_SessionRebuilding` — the wrapper
`CustodyMemoryBank` (the ADK-facing shell a real `Runner` requires) puts
between `CustodyMemoryService` and any downstream — proxied only
`add_session_to_memory` and `search_memory`. `CustodyMemoryService`'s own
capability detection (`getattr(self.downstream, "write_record", None)`)
runs against `self.downstream`, which for `CustodyMemoryBank` is always a
`_SessionRebuilding` instance, so a real ADK `Runner` could never have
reached `write_record` regardless of which downstream `CustodyMemoryBank`
was given. Fixed additively: `_SessionRebuilding.__post_init__` now sets
`self.write_record = inner.write_record` only when the wrapped downstream
offers it. Confirmed safe by usage: only `scripts/live_memory_bank.py` and
tests using `InMemoryMemoryService` (which never offers `write_record`)
construct `CustodyMemoryBank`.

`scripts/live_memory_bank.py`'s `prove_adk_memory_bank` now builds its
downstream from `AgentEngineMemoryBank` instead of the removed
`ingest_events`-based `BlockingAgentPlatformMemoryBank`. The real
Runner/Gemini/conversational leg is unchanged in shape and behavior. A
second, direct write — one real ADK event carrying a trusted tool's
`function_response`, admitted through the same `CustodyMemoryBank`
instance — proves selective deletion through G1's actual wiring: the
conversational turn's records carry no `source_tool` and so cannot be
targeted by `revoke(tool=...)`, so this tool-origin write is what makes the
claim demonstrable, the same shape D2 already proved standalone.

Live proof (`make live-g1`, evidence in `proof-out/g1.json`): the tool-origin
memory is retrievable via `search_memory` before its tool is revoked, and
gone afterward, while the untooled conversational memories stay untouched.
`make gates`'s G1 judge (`scripts/gates.py`) was updated to match the new
evidence shape and now also independently recomputes `memory_id_for` for
the revoked record rather than trusting the producer's claim, plus checks
the before/after `search_memory` results directly — the same discipline
`memory_deletion_gates.py` already used for D2. Reported PASS against this
session's live evidence.

**Retrieval quality, decided and documented live, not assumed:** the
pre-migration baseline (`ingest_events`) returned one Memory-Bank-synthesized
fact merging both admitted events' content ("Sales exports require a
signed approval, and the audit identifier is b888ba0c..."). The
post-migration path (`write_record`) returns two separate, unmerged, raw
per-event facts instead — no cross-event synthesis, by design, since
`write_record` trades Memory Bank's own server-side consolidation for a
deterministic per-record `memory_id`. This is the exact tradeoff
`DECISIONS.md` #2 named before it was made: real, and now measured.

**Non-goal, stated in every artifact:** memories G1 wrote before this
migration, through the old `ingest_events` path, are unchanged and remain
outside what this mechanism can delete.

## G5: what was built, and why it can't be "done" yet

Started 2026-08-13. Firestore (Native mode, `us-central1`) backs the
derivation graph (`custody/firestore_store.py`). Cloud Scheduler job
`custody-g5-auditor` (daily, `0 6 * * *` UTC, `POST /auditor`) is `ENABLED`.

**Checked this session:** the job's one manual "run now" trigger from the
prior session did succeed — logged at `2026-08-13T12:00:44Z`, HTTP 200,
`insertId 6a7db1ed00084c8dae8758ee`. Its **natural first scheduled fire is
`2026-08-14T06:00:02Z`** (per `gcloud scheduler jobs describe`); actual UTC
at the time of this handoff is `2026-08-13T18:54Z`, so that fire has **not
yet happened** — this is not a bug, it is real elapsed time not having
passed yet. Re-check after that time with:

```sh
CLOUDSDK_CONFIG="$PWD/.gcloud" gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="custody-control-plane" AND httpRequest.userAgent="Google-Cloud-Scheduler"' \
  --project=project-988bc9fe-092c-4b32-90c --freshness=2d --order=desc --limit=5 --format=json
```

Look for a second entry, timestamp near `2026-08-14T06:00Z`, without the
`custody-cold-start-check` label (that label marks the earlier manual
trigger only).

Deliberately not built yet: revoking the seed record (must happen near
filming, not now) and `scripts/scheduler_gates.py` (a judge for a
multi-day span, before enough days have elapsed, would have nothing real to
check). Neither is fixable by code today; both need calendar time.

## Evidence and claim discipline

- Admin Activity authenticates policy transitions but omits historical CEL
  condition text; scope and post-expiry 403 controls are the falsifiable
  evidence for S1's semantics, not the log text itself.
- O1's independently-verified claim is a Cloud Logging entry, not Cloud
  Trace storage. Say so exactly; do not round up to "verified in Cloud Trace."
- R2's independently-verified claim is two Cloud Logging denial entries plus
  two Cloud Run revision descriptions, not a claim about IAP or the Gateway.
- D2's independently-verified claim covers only records written through the
  new `write_record` path. As of the 2026-08-14 G1 migration, G1's live
  Runner is one of those writers too — do not imply memories G1 wrote
  *before* that migration became retroactively deletable; they did not.
- Cloud Run and the control plane are public because they are synthetic proof
  services. Do not generalize that posture to production customer data.
- All synthetic IDs and `example.invalid` addresses are controls. Do not use
  external targets or real customer data.
- Keep TOOL call roots structural. Never let a model label provenance, trust,
  revision admission, or policy outcomes.

## Next capability

With R2, D2, the G1 migration, the Provenance Auditor, the Custody
Reviewer, the N=5 fleet, and G5's clock all landed, all three fleet-review
findings are closed. Remaining scoped work:

1. **Confirm G5's natural Scheduler fire** (`2026-08-14T06:00:02Z` UTC, see
   above) — a quick log check, not a build task. Do this first if it's now
   past that time.
2. `scripts/scheduler_gates.py`, once there is a real multi-day span to
   judge — not yet, would have nothing to check.
3. Revoke the G5 seed record near filming, via the existing `/revoke`
   endpoint, once enough real elapsed time has passed.
4. Regenerate `proof-out/g1.json` before filming — G1 evidence expires
   after 24 hours, same discipline as every other live gate here.
5. `proof-out/live-review.json` and `proof-out/live-fleet.json` also expire
   after 24 hours, same discipline — regenerate with `make live-review` and
   `make live-fleet` before filming.
