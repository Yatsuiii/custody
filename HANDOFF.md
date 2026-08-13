# Custody recovery handoff, 2026-08-13 (S1/M1/O1 live, G5 clock started)

This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

## Lane and artifact

Lane: agentic security infrastructure, built as an evidence-gated systems
project for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet.

Four capabilities are complete and independently judged:

- G1 (Cloud Run/Vertex/ADK/Memory Bank) and R1 (stale Registry): complete
  before this session's work began.
- S1 (Gateway): `proof-out/live-gateway.json`, `make gateway-gates` 20/20 PASS.
- M1 (Model Armor): `proof-out/live-model-armor.json`, `make model-armor-gates`
  9/9 PASS.
- O1 (Observability): `proof-out/live-observability.json`,
  `make observability-gates` 7/7 PASS.

A fifth, G5's elapsed-time record, is **started but structurally cannot be
"complete" today** — see below.

README.md and `.claude/SESSION_CONTRACT.md` are authoritative for all claim
text; do not restate any of it from memory, read them.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- Three commits landed this session so far: `df334f1` (S1 fix + accumulated
  G1/R1 work), `94bcad4` (M1), `68f1b88` (G5 persistence/Scheduler start).
  None pushed.
- **The O1 work below is NOT yet committed.** Check `git status` before
  assuming otherwise.
- Do not push without explicit authorization.

```sh
git status --short --branch
git diff --check
git diff --stat
git log -8 --oneline --decorate
```

## Previously proven state, do not redo

- G1, R1, S1, M1, O1 as above.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  correctly BLOCKED — its elapsed-time requirement is real, not a bug).

Known limitations that must remain explicit unless new direct evidence changes
them:

- CustodyGraph revocation does not delete live Memory Bank descendants.
- The admitted surface-read to dispatch path has a TOCTOU window and is not
  cryptographically atomic.
- Behavior-only drift with identical `tools/list` is outside the revision claim.
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
Agent Runtime (G1/O1):
  projects/742122658452/locations/us-central1/reasoningEngines/6936011268348182528
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
Observability Cloud Logging log:
  projects/project-988bc9fe-092c-4b32-90c/logs/custody-observability
```

Repo-local Google credentials/configuration live under ignored `.gcloud/`.
Never print, copy, or commit credential contents.

**Live IAP resting state (S1's projection), confirmed 2026-08-13:** exact safe
deny — `api.getAttribute('iap.googleapis.com/mcp.toolName', '') in
['custody_policy_canary', '']`. Re-read before any future mutation, never
assume it.

## O1: what was built, and a real environment limit found along the way

Scope: extend the G1 live ADK Runner call with an explicit OTel span
carrying the admitted `CustodyRecord`'s exact `content_sha256` digest as a
`custody.digest` attribute, exported to Cloud Trace, so "a quarantine is
reproducible from a trace" becomes a checkable claim.

**What was found:** ADK's GCP trace exporter
(`google.adk.telemetry.google_cloud.get_gcp_exporters(enable_cloud_tracing=
True)`) genuinely works for writing spans — but two real problems had to be
diagnosed and worked around before it did:

1. `get_gcp_exporters` silently returns empty hooks (no span processor at
   all, no error) when `google.auth.default()`'s second return value
   (`project_id`) is `None`, which it is for this project's user-account ADC.
   Fixed by passing `google_auth=(credentials, PROJECT)` explicitly, and by
   setting `gcp.project_id` on the OTel `Resource` — the export endpoint
   (`telemetry.googleapis.com/v1/traces`) rejects a request whose resource
   lacks that attribute with a 400 and the body `Resource is missing
   required attribute "gcp.project_id"`, which only surfaces if you inspect
   the raw HTTP response text yourself; the OTel exporter's own error message
   is just "Failed to export span batch code: 400, reason: Bad Request".
2. **Independent readback of a Cloud Trace span is not possible in this
   project via any API found.** `cloudtrace.googleapis.com/v1/projects/{p}/
   traces/{id}` returns `404 "_Trace bucket not found in project"` for every
   trace this producer exported, even well after ingestion delay. The v2 API
   (`cloudtrace.googleapis.com/v2`) has `traces:batchWrite` and
   `traces.spans.createSpan` only — no read or list method exists in its
   discovery document at all. This looks like the classic default trace
   storage bucket was never provisioned for this project and there is no
   public API to create one (likely only auto-created by visiting the Cloud
   Trace section of the Console UI, which cannot be done headlessly).

**Resolution, confirmed with the user:** pivoted the independently-verified
claim to Cloud Logging. The producer still creates and exports the real OTel
span (so "a span carrying this digest was created and an export was
attempted without error" is true), but the falsifiable, independently
rereadable fact is a structured Cloud Logging entry the producer writes
itself, carrying the exact trace ID, span ID, and digest together. This is
the same `gcloud logging read`-based mechanism every other live proof in this
repo already uses, so the independent judge (`scripts/observability_gates.py`)
follows the same pattern as `model_armor_gates.py`: offline coherence check,
then live attestation by rereading the log entry via its server-issued
insert ID from Google Cloud, using code-owned resource identifiers.
`CLAIM_BOUNDARY` in both `scripts/live_observability.py` and
`scripts/observability_gates.py` states this limitation explicitly — do not
strengthen the claim to imply Cloud Trace storage was verified.

**A second, unrelated bug this surfaced while reverifying S1:** rerunning
`make gateway-gates` hours after the original S1 proof failed on
`live_gateway_configuration`, because the Agent Gateway resource's own
`etag`/`updateTime` had changed server-side (Google's own reconciliation, not
a real configuration change) between the proof and the reread. Fixed with a
`_config_matches` helper in `scripts/gateway_live_attestation.py` that
excludes `etag`/`updateTime` from the equality comparison, mirroring the
existing `_runtime_matches` pattern that already excludes one SDK-enriched
field. Regression test:
`test_server_side_etag_and_update_time_drift_does_not_fail_rereading`. If a
future rereview finds `live_registry_runtime_target` or
`live_final_deny_policy` failing for the same reason (Cloud Run/IAP resources
also carry volatile metadata), apply the same fix there — it was not
preemptively applied to those since they were not observed failing.

`scripts/live_memory_bank.py`'s `prove_adk_memory_bank` gained one new
returned field, `admitted_digests` (the exact digests of every trusted
admitted record from that run) — purely additive, does not change any
existing G1 gate logic or behavior.

## G5: what was built, and why it can't be "done" yet

Started 2026-08-13 in the previous part of this session (commit `68f1b88`).
Firestore (Native mode, `us-central1`) now backs the derivation graph
(`custody/firestore_store.py`: `FirestoreCustodyGraph`, `FirestoreAuditorLog`,
mirroring `custody/store.py`'s SQLite replay pattern). `CustodyRecord` and
`Revocation` gained optional `admitted_at`/`revoked_at` fields, never set by
the pure core, only stamped by a durable store from its own server-assigned
write time. The control plane gained `POST /auditor` (idempotent daily
heartbeat, seeds one fixed record `g5-elapsed-time-seed` on the very first
invocation ever) and `GET /custody/{id}`. Deployed with
`CUSTODY_FIRESTORE_PROJECT` set and `max-instances=1`; durability across a
real forced cold start was verified live (byte-identical `admitted_at`).
Cloud Scheduler job `custody-g5-auditor` (daily, 06:00 UTC) is `ENABLED`.

**Confirm next session** that the Scheduler job actually fired at its first
natural run (2026-08-14T06:00Z) — the manual "run now" trigger did not show
up in Cloud Run logs within the previous session's verification window,
likely eventual-consistency lag right after job creation, not a real
failure, but it was not confirmed. Check via:

```sh
CLOUDSDK_CONFIG="$PWD/.gcloud" gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="custody-control-plane" AND httpRequest.userAgent="Google-Cloud-Scheduler"' \
  --project=project-988bc9fe-092c-4b32-90c --freshness=2d --order=desc --limit=5 --format=json
```

Deliberately not built yet: revoking the seed record (must happen near
filming, not now) and `scripts/scheduler_gates.py` (a judge for a multi-day
span, before any days have elapsed, would have nothing real to check).

**A known, accepted gap:** the control plane is fully public (`allUsers`
Cloud Run invoker), unchanged from its pre-existing G1 posture — Cloud Run
IAM is service-level, not per-route, and every other mutating endpoint was
already public before this session, so OIDC-gating only `/auditor` wasn't
achievable without splitting into a second service. Document it precisely as
a synthetic proof service, same posture as the Registry MCP server.

## Evidence and claim discipline

- Admin Activity authenticates policy transitions but omits historical CEL
  condition text; scope and post-expiry 403 controls are the falsifiable
  evidence for S1's semantics, not the log text itself.
- O1's independently-verified claim is a Cloud Logging entry, not Cloud
  Trace storage. Say so exactly; do not round up to "verified in Cloud Trace."
- The Cloud Run dispatch event (S1) and the Model Armor prompt-text
  correlation (M1) both exist to close replay/graft holes; do not weaken
  either to make a future proof "easier."
- Cloud Run and the control plane are public because they are synthetic proof
  services. Do not generalize that posture to production customer data.
- All synthetic IDs and `example.invalid` addresses are controls. Do not use
  external targets or real customer data. The G5 seed record's content is
  synthetic and stored as a SHA-256 digest, not raw text, in Firestore.
- Keep TOOL call roots structural. Never let a model label provenance, trust,
  revision admission, or policy outcomes. A Model Armor verdict, a Firestore
  document's `create_time`, and an OTel span's digest attribute are all facts
  Custody may read, never facts a model may relabel.

## Next capability

With S1, M1, O1 live and G5's clock started, remaining scoped work:

1. Confirm the Scheduler's first natural fire (see above) — quick check, not
   a build task.
2. `scripts/scheduler_gates.py`, once there is a real multi-day span to judge
   — not yet, would have nothing to check.
3. Revoke the G5 seed record near filming, via the existing `/revoke`
   endpoint, once enough real elapsed time has passed.
4. Live Memory Bank selective deletion, only if the actual API semantics
   preserve Custody's lineage contract — unexplored.

Before starting any of these as a fresh session, update
`.claude/SESSION_CONTRACT.md` with a contract scoped to that specific piece,
per the global evidence-gated protocol.
