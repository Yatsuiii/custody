# Custody recovery handoff, 2026-08-13 (R2/D2 live and committed, G5 clock running)

This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

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
- **D2 (selective live Memory Bank deletion, new this session):**
  `proof-out/live-memory-deletion.json`, `make memory-deletion-gates` 7/7
  PASS. A second, additive, opt-in write path
  (`custody/adapters/memory_bank.py`) makes revoked records genuinely
  deletable from live Memory Bank. G1's own `ingest_events` write path is
  unchanged and not covered by this mechanism — see "Known limitations."

A seventh, G5's elapsed-time record, is **started and running, structurally
cannot be "complete" until real calendar time passes** — see below.

README.md and `.claude/SESSION_CONTRACT.md` are authoritative for all claim
text; do not restate any of it from memory, read them.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- Commits landed: `df334f1` (S1 fix + accumulated G1/R1 work), `94bcad4`
  (M1), `68f1b88` (G5 persistence/Scheduler start), `9c4174b` (O1),
  `7f7ea00` (**R2 + D2, this session**).
- Working tree is clean as of this handoff. Confirm with `git status` before
  assuming otherwise — do not trust this line if time has passed.
- None of these commits are pushed. Do not push without explicit
  authorization.

```sh
git status --short --branch
git diff --check
git log -8 --oneline --decorate
```

## Previously proven state, do not redo

- G1, R1, S1, M1, O1, R2, D2 as above.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  correctly BLOCKED — its elapsed-time requirement is real, not a bug).

Known limitations that must remain explicit unless new direct evidence changes
them:

- **G1's `ingest_events` write path still cannot have its memories deleted
  selectively.** D2 solved this for a *second, additive* write path
  (`custody/service.py`'s `RecordWriter`, backed by
  `memories.create(config={"memory_id": memory_id_for(record.id)})`), proven
  live end to end. G1's live ADK Runner flow, its Cloud Run proof, and every
  memory it has already written through `ingest_events` are **unchanged** and
  remain outside what D2's mechanism can delete. This is the one gap in the
  "fix the gaps" ask below that is real, scoped, and actionable — see "Next
  capability."
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

**Non-goal, stated in every artifact:** G1's `ingest_events` flow, its Cloud
Run proof, and anything already written through it are unchanged and remain
outside what this mechanism can delete. Migrating G1 onto this path was
explicitly scoped out — see "Next capability."

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
  new `write_record` path. Do not imply G1's own memories became deletable.
- Cloud Run and the control plane are public because they are synthetic proof
  services. Do not generalize that posture to production customer data.
- All synthetic IDs and `example.invalid` addresses are controls. Do not use
  external targets or real customer data.
- Keep TOOL call roots structural. Never let a model label provenance, trust,
  revision admission, or policy outcomes.

## Next capability

With R2, D2, and G5's clock all landed, remaining scoped work:

1. **Confirm G5's natural Scheduler fire** (`2026-08-14T06:00:02Z` UTC, see
   above) — a quick log check, not a build task. Do this first if it's now
   past that time.
2. **Migrate G1 onto the D2 write path** (the one real, deferred gap):
   rework G1's live ADK Runner flow (`scripts/live_memory_bank.py`,
   `custody/adapters/adk.py`) to use `AgentEngineMemoryBank`/`RecordWriter`
   instead of `ingest_events`, so G1's own memories become selectively
   deletable too. This was explicitly scoped out of the D2 session because
   it reworks a deadline-critical, already-passing live gate — it needs its
   own session contract, its own live re-proof of G1 end to end (Cloud Run +
   Gemini + ADK Runner + the new write path), and a clear-eyed check of
   whether losing Memory Bank's own server-side derivation (one summarized
   memory per session, replaced by one raw fact per admitted record) changes
   retrieval quality in a way worth documenting either way.
3. `scripts/scheduler_gates.py`, once there is a real multi-day span to
   judge — not yet, would have nothing to check.
4. Revoke the G5 seed record near filming, via the existing `/revoke`
   endpoint, once enough real elapsed time has passed.

Before starting #2 as a fresh session, update `.claude/SESSION_CONTRACT.md`
with a contract scoped to that specific piece, per the global evidence-gated
protocol — do not reuse D2's already-closed D1/D2 gates for a scope this
different.

### Ready-to-use prompt for #2 (G1 migration)

> Migrate G1's live write path from `ingest_events` to the D2 write path
> (`custody/adapters/memory_bank.py`'s `AgentEngineMemoryBank`/
> `RecordWriter`), so memories G1's own ADK Runner writes become selectively
> deletable, the same way D2 already proved for a standalone session. Read
> `HANDOFF.md`'s "D2: what was built" and "Next capability" sections first,
> and `DECISIONS.md` #2 for the full live history of what was tried and
> rejected before D2's path was found to work. Scope this with a session
> contract in `.claude/SESSION_CONTRACT.md` first (objective + 2-4
> acceptance gates: G1 still runs live end to end on the new path; a
> revoked G1-written record's memory is verifiably gone from
> `search_memory`; no regression to G1's existing admitted/withheld counts
> or Gemini/Cloud Run behavior). Decide and document, live-verified not
> assumed, whether losing Memory Bank's own session-level derivation (one
> summarized memory per session under `ingest_events`, versus one raw fact
> per admitted record under `write_record`) changes retrieval quality, and
> say so either way rather than silently absorbing the change. Confirm with
> the user before the first live Cloud Run redeploy, same discipline as
> every other live gate in this project.
