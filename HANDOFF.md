# Custody recovery handoff, 2026-08-13 (post S1/M1 proofs, G5 clock started)

This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

## Lane and artifact

Lane: agentic security infrastructure, built as an evidence-gated systems
project for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet.

Three capabilities are complete and independently judged:

- S1 (Gateway): `proof-out/live-gateway.json`, `make gateway-gates` 20/20 PASS.
- M1 (Model Armor): `proof-out/live-model-armor.json`, `make model-armor-gates`
  9/9 PASS.
- R1 (stale Registry) and G1 (Cloud Run/Vertex/ADK/Memory Bank) were already
  complete before this session.

A fourth, G5's elapsed-time record, is **started but structurally cannot be
"complete" today** — see below.

README.md and `.claude/SESSION_CONTRACT.md` are authoritative for all claim
text; do not restate any of it from memory, read them.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- Two commits landed this session: `df334f1` (S1 fix + accumulated G1/R1
  work) and `94bcad4` (M1). Neither pushed.
- **The G5 persistence/Scheduler work below is NOT yet committed.** Check
  `git status` before assuming otherwise.
- Do not push without explicit authorization.

```sh
git status --short --branch
git diff --check
git diff --stat
git log -5 --oneline --decorate
```

## Previously proven state, do not redo

- G1, R1, S1, M1 as above.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  correctly BLOCKED — its elapsed-time requirement is real, not a bug).

Known limitations that must remain explicit unless new direct evidence changes
them:

- CustodyGraph revocation does not delete live Memory Bank descendants.
- The admitted surface-read to dispatch path has a TOCTOU window and is not
  cryptographically atomic.
- Behavior-only drift with identical `tools/list` is outside the revision claim.
- Agent Observability (O1) remains unproven — reachability was confirmed this
  session (`google.adk.telemetry.google_cloud.get_gcp_exporters`) but nothing
  was built. See "Next capability" below.
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
Agent Runtime:
  projects/742122658452/locations/us-central1/reasoningEngines/5289382654590844928
Registered Runtime Agent:
  agentregistry-00000000-0000-0000-5b70-78deb73916d5
Runtime principal:
  principal://agents.global.org-521713171342.system.id.goog/resources/aiplatform/projects/742122658452/locations/us-central1/reasoningEngines/5289382654590844928
MCP endpoint:
  https://custody-export-mcp-anexdhueiq-uc.a.run.app/mcp
Model Armor Template:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/templates/custody-approved-tool-ingress
Control plane (Cloud Run, public):
  https://custody-control-plane-742122658452.us-central1.run.app
Firestore database:
  projects/project-988bc9fe-092c-4b32-90c/databases/(default), Native mode, us-central1
Cloud Scheduler job:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/jobs/custody-g5-auditor
```

Repo-local Google credentials/configuration live under ignored `.gcloud/`.
Never print, copy, or commit credential contents.

**Live IAP resting state (S1's projection), confirmed 2026-08-13:** exact safe
deny — `api.getAttribute('iap.googleapis.com/mcp.toolName', '') in
['custody_policy_canary', '']`. Re-read before any future mutation, never
assume it.

## G5: what was built this session, and why it can't be "done" yet

G5 requires "Cloud Scheduler running the Auditor daily from first deploy to
filming, with one custody record showing genuine timestamps across that span
including a memory admitted early and revoked later. Nothing fast-forwarded."
That is a calendar-time requirement, not a build requirement — it can only be
started, then must be left alone to accumulate real days.

**The blocker found and fixed:** `custody/control_plane.py` as previously
deployed was in-memory only — no volume, no Firestore — so its state does not
survive a Cloud Run cold start, let alone weeks. A DDIA-architect review (see
`git log` for the full review if needed; summary below) confirmed this made
G5 architecturally unshippable as-is and recommended the minimal fix.

**What changed:**

1. Enabled `firestore.googleapis.com` and `cloudscheduler.googleapis.com`.
   Created the Firestore database (Native mode, `us-central1`, default DB).
2. Added `admitted_at: str | None = None` to `CustodyRecord`
   (`custody/origin.py`) and `revoked_at: str | None = None` to `Revocation`
   (`custody/graph.py`). Both default `None` and are never set by the pure
   core — only a durable store stamps them, from its own server-assigned
   write time. `custody/store.py`'s SQLite serialization updated to match,
   backward-compatible with old rows.
3. Added a `record(record_id)` method to `CustodyGraph` (live records only;
   the pure graph deletes on revocation, so it cannot answer for revoked
   history — documented as a real limitation, not a bug).
4. New `custody/firestore_store.py`: `FirestoreCustodyGraph` (mirrors
   `SqliteCustodyGraph`'s replay-through-the-wrapped-class pattern, but
   Firestore-backed; create-fails-if-exists writes, `AlreadyExists` swallowed
   as success; replay order is each document's own server `create_time`, not
   insertion order) and `FirestoreAuditorLog` (one heartbeat document per UTC
   day, same idempotency discipline). Offline-tested against a fake Firestore
   client in `tests/test_firestore_store.py` — `make check` stays networkless.
5. `custody/control_plane.py` gained `POST /auditor` (idempotent daily
   heartbeat; seeds one fixed record, id `g5-elapsed-time-seed`, only on the
   very first invocation ever) and `GET /custody/{id}` (durable read-back:
   admission time, revocation id/time if any). `InMemoryAuditorLog` is the
   offline/local default; `_default_plane()` switches to
   `FirestoreCustodyGraph`/`FirestoreAuditorLog` when
   `CUSTODY_FIRESTORE_PROJECT` is set in the environment.
6. Granted the Cloud Run service account (`742122658452-compute@...`)
   `roles/datastore.user`. Redeployed the control plane
   (`gcloud run deploy --source=.`) with `CUSTODY_FIRESTORE_PROJECT` set and
   `max-instances=1` (required: two instances would each hold their own
   replayed graph and could diverge between reloads).
7. **Verified durability across a real cold start live**: called
   `POST /auditor` (seeded the record, `admitted_at` =
   `2026-08-13T11:55:24.745231+00:00`), forced a new Cloud Run revision
   (`custody-control-plane-00003-hd2`), then confirmed `GET
   /custody/g5-elapsed-time-seed` returned the byte-identical `admitted_at`
   and a repeat `POST /auditor` correctly reported `first_run: false`. This
   is the fact that actually falsifies (or, here, confirms) the design.
8. Created Cloud Scheduler job `custody-g5-auditor` (`us-central1`, cron
   `0 6 * * *` UTC, `POST /auditor`), state `ENABLED`. A manual "run now"
   trigger did not show up in Cloud Run logs within the verification window
   this session — most likely eventual-consistency lag right after job
   creation, not a real failure, since the job is correctly configured and
   the target endpoint is proven to work. **Confirm on next session** that
   the job actually fired at its first scheduled 06:00 UTC run
   (2026-08-14) via `gcloud logging read` for
   `httpRequest.userAgent="Google-Cloud-Scheduler"` on the control plane, or
   `gcloud scheduler jobs describe custody-g5-auditor --location=us-central1`
   for a populated `lastAttemptTime`/`status`.

**Deliberately deferred, do not start early:**

- Revoking the seed record. It must happen near filming, not now — the whole
  point is genuine elapsed time between admission and revocation.
- `scripts/scheduler_gates.py` (offline judge + live attestation, mirroring
  `model_armor_gates.py`). Building it before there is a multi-day span would
  have nothing real to judge. Build it once there is.

**A known, accepted gap:** the control plane is fully public (`allUsers`
Cloud Run invoker), unchanged from its pre-existing G1 posture. DDIA
recommended OIDC-gating the Auditor endpoint specifically; Cloud Run IAM is
service-level, not per-route, and `/sessions`, `/vouch`, `/revoke` were
already public and unauthenticated before this session, so gating only
`/auditor` was not achievable without splitting into a second service or
authenticating the whole demo control plane. Judged out of scope for this
pass. Document it precisely as a synthetic proof service, same posture as the
Registry MCP server — do not claim it as hardened.

**Time pressure, stated plainly:** if the seed record's span to revocation
ends up too short to read as "weeks of operations" on camera, the honest move
is to narrow the G5 wording in the submission, not to fake elapsed time.

## Evidence and claim discipline

- Admin Activity authenticates policy transitions but omits historical CEL
  condition text; scope and post-expiry 403 controls are the falsifiable
  evidence for S1's semantics, not the log text itself.
- The Cloud Run dispatch event (S1) and the Model Armor prompt-text
  correlation (M1) both exist to close replay/graft holes; do not weaken
  either to make a future proof "easier."
- Cloud Run and the control plane are public because they are synthetic proof
  services. Do not generalize that posture to production customer data.
- All synthetic IDs and `example.invalid` addresses are controls. Do not use
  external targets or real customer data. The G5 seed record's content is
  synthetic and stored as a SHA-256 digest, not raw text, in Firestore.
- Keep TOOL call roots structural. Never let a model label provenance, trust,
  revision admission, or policy outcomes. Model Armor's verdict and a
  Firestore document's `create_time` are both facts Custody may read, never
  facts a model may relabel.

## Next capability: Agent Observability (O1)

Scoped in `.claude/SESSION_CONTRACT.md` but not started. Reachability
confirmed: `google-adk` ships real GCP OTel export
(`google.adk.telemetry.google_cloud.get_gcp_exporters(enable_cloud_tracing=
True, ...)`); `opentelemetry-exporter-gcp-trace`/`-gcp-logging` are already
installed transitively; Cloud Trace API is already enabled. There is no
`gcloud trace traces describe` — independent live readback must hit the
Cloud Trace v1 REST API directly with a bearer token (same pattern
`gateway_live_attestation.py`'s `rest_json` already uses).

Plan: extend the G1 live ADK Runner call (`scripts/live_memory_bank.py`) with
an explicit OTel span wrapping the admitted session, carrying the exact
`content_sha256` of the admitted `CustodyRecord` as a span attribute
(`custody.digest`), exported to Cloud Trace. The claim is "a quarantine is
reproducible from a trace" — an independently reread trace must carry that
exact digest, not a value the offline judge merely trusts from an artifact.
Non-goal: this is additive telemetry on the already-passing G1 path; it must
not change G1's admitted/withheld counts or Memory Bank behavior.
