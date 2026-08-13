# Custody recovery handoff, 2026-08-13 (post schema-v2 Gateway proof)

This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

## Lane and artifact

Lane: agentic security infrastructure, built as an evidence-gated systems
project for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet.

The Gateway artifact this file previously tracked as in-progress is now
**complete and independently judged**. `proof-out/live-gateway.json` (schema
v2, proof `e2b9f562fa3a48249054b977b5779a21`) exists and `make gateway-gates`
reports twenty PASS results (twelve from the offline judge, eight from
independent live Google Cloud attestation). README.md and
`.claude/SESSION_CONTRACT.md` were updated from this evidence and are
authoritative for the S1 claim text; do not restate S1 from memory, read them.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- HEAD: `8dae6a0` (`Rewrite the handoff against the current state...`)
- Origin is at the same commit.
- The tree is intentionally dirty with all work from this and the prior
  session. Nothing has been committed or pushed. Do not commit or push without
  explicit authorization.
- Preserve every unrelated/preexisting modification. Inspect with:

```sh
git status --short --branch
git diff --check
git diff --stat
git log -5 --oneline --decorate
```

The main new/untracked Gateway files are:

```text
live/gateway/
live/gateway_probe/agent.py
scripts/setup_gateway.py
scripts/deploy_gateway_probe.py
scripts/live_gateway.py
scripts/gateway_gates.py
scripts/gateway_live_attestation.py
tests/test_gateway_gates.py
tests/test_gateway_live_attestation.py
tests/test_live_gateway_producer.py
tests/test_registry_attack_server_logs.py
```

The MCP server used by both the stale-Registry proof and Gateway proof is
`live/registry_attack/server/server.py`. Do not remove its existing revision
or forwarding behavior; it was not touched in this pass.

## Previously proven state, do not redo

- G1 is complete: live Cloud Run, Gemini/Vertex, ADK, and Memory Bank evidence.
- Live stale Agent Registry proof (R1) is complete.
- `make registry-gates` independently judges that artifact: 8/8 PASS.
- `make revision-spike` passes all five revision gates.
- **S1 (Gateway) is complete**, schema v2, `make gateway-gates`: 20/20 PASS.
  See "What changed in this session" below for exactly what was fixed to get
  here; do not re-litigate it.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  expected — see below).

Known limitations that must remain explicit unless new direct evidence changes
them:

- CustodyGraph revocation does not delete live Memory Bank descendants.
- RevisionCatalog and some approval state are application-side.
- The admitted surface-read to dispatch path has a TOCTOU window and is not
  cryptographically atomic.
- Behavior-only drift with identical `tools/list` is outside the revision claim.
- Model Armor and submission-grade Observability remain unproven (this is the
  expected G5 BLOCKED reason, not a regression).
- The Gateway proof covers one owned Agent Runtime identity, one registered MCP
  projection, and four controlled calls (allow, tool-scope-canary, expiry,
  final deny). It does not prove all fleet egress is covered.

## Owned Google Cloud scope

All live work is defensive and limited to these user-owned resources:

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
```

Repo-local Google credentials/configuration live under ignored `.gcloud/`.
Never print, copy, or commit credential contents.

**Live IAP resting state, confirmed 2026-08-13 after the successful S1 run:**
the dedicated projection's policy is at exact safe deny —

```cel
api.getAttribute('iap.googleapis.com/mcp.toolName', '') in ['custody_policy_canary', '']
```

Re-read the policy before any future mutation. Never assume it. The exact
command shape is encoded in `DedicatedIapPolicy.current()`.

## What changed in this session (2026-08-13)

The prior handoff left the project mid-recovery: a schema-v2 run
(`8030f2119417461bb9db9c4eb066ef64`) had been deliberately rejected because its
CEL expired the empty-name MCP-handshake clause together with the
`lookup_customer` lease, so a post-expiry call could fail before `tools/call`
and produce no log. Recovery from that run succeeded and left the policy at
exact safe deny; no cloud mutation was left in flight.

This session, in order:

1. **Fixed the CEL shape** in `scripts/live_gateway.py`
   (`TemporaryAdmission.expression`, `_TEMPORARY_ALLOW`) and
   `scripts/gateway_gates.py` (`allow_expression`) to the required
   independent-clause form:

   ```cel
   api.getAttribute('iap.googleapis.com/mcp.toolName', '') == '' ||
   (request.time < timestamp('<10-minute-expiry>') &&
    api.getAttribute('iap.googleapis.com/mcp.toolName', '') == 'lookup_customer')
   ```

   The empty-name clause no longer depends on `request.time`, so handshake
   passthrough survives the tool lease expiring. The parser now rejects the
   old all-expiring shape; both `tests/test_gateway_gates.py` and
   `tests/test_live_gateway_producer.py` assert this.
2. Added a bounded outer timeout around every `engine.async_query` call
   (`asyncio.wait_for`, `RUNTIME_QUERY_TIMEOUT_SECONDS`).
3. Gave `_gateway_logs` a bounded attempt count with transient-read recovery
   (it previously propagated `CalledProcessError`/`TimeoutExpired` instead of
   retrying, unlike its sibling log-polling functions).
4. Added the adversarial tests HANDOFF asked for: empty-name passthrough
   survives expiry, `lookup_customer` admitted before/denied after expiry,
   `custody_policy_canary` never admitted by the temporary lease, the old CEL
   shape is rejected, bounded runtime-query timeout, bounded+recovering log
   polling.
5. Ran `make check` and `git diff --check` clean, re-read the live IAP policy
   (confirmed exact safe deny), then ran `make live-gateway`. It failed — not
   on the CEL fix, but on two bugs the live run surfaced that the prior
   handoff had not anticipated:
   - **IAP etag base64-alphabet mismatch.** `gcloud iap web get-iam-policy`
     returns etags in the URL-safe alphabet (`-`/`_`); the same etag inside a
     raw Admin Activity audit payload was observed in the standard alphabet
     (`+`/`/`). Strict string equality between a policy readback and an audit
     log entry rejected a genuine match. Fixed with a `_canonical_etag`
     normalization applied at every readback-vs-audit-log comparison in both
     `scripts/live_gateway.py` (`_iap_audit_logs`) and
     `scripts/gateway_gates.py` (`_iap_audit_transition_is_bound`). Regression
     test: `test_etag_across_base64_alphabets_still_binds_the_audit_chain`.
   - **Dispatch-log clock-read ordering.** The offline judge required
     `dispatched <= logged` between the payload's self-reported
     `server_dispatched_at` and the log entry's own `timestamp` — two
     independent `datetime.now()` reads in the same server request, observed
     ~300 microseconds out of order. Relaxed to a skew tolerance
     (`_CLOCK_SKEW_BOUND = 1.0` second) in `scripts/gateway_gates.py`
     (`_server_dispatch_is_bound`) and the duplicated check in
     `scripts/gateway_live_attestation.py`.
   - Also in `gateway_live_attestation.py`: it assumed the MCP tool result was
     a flat `data` object; the live server actually returns the standard MCP
     envelope (`content` + `structuredContent`). Fixed to unwrap
     `structuredContent` when present. Regression test:
     `test_mcp_envelope_structured_content_shape_is_understood`.
6. Reran `make live-gateway` successfully (proof
   `e2b9f562fa3a48249054b977b5779a21`), then `make gateway-gates` (20/20),
   `make registry-gates` (8/8), `make revision-spike` (5/5), `make gates`
   (4 PASS / 0 FAIL / 1 BLOCKED — G5, expected), `make check` (205 tests), and
   `git diff --check`, all clean.
7. Updated `README.md` and `.claude/SESSION_CONTRACT.md` from the generated
   evidence. Did not touch anything else; did not commit or push.

Two pre-existing `C901` complexity violations were also fixed as a side effect
of editing `_apply_reconciled` (`scripts/live_gateway.py`), `_judge`
(`scripts/gateway_gates.py`), and a test fixture (`FakeCloud.json` in
`tests/test_gateway_live_attestation.py`) — the clean-code pre-commit/per-edit
hook blocks on these, and all three were pre-existing, not introduced here.

## Evidence and claim discipline

- Admin Activity authenticates the policy resource, actor, role/member, and
  etag transitions, but currently omits historical CEL condition/title. Do not
  claim the log itself contains the CEL. Scope and post-expiry 403 controls are
  the falsifiable behavioral evidence for those semantics.
- The Cloud Run dispatch event closes the old replay hole where a fabricated
  proof ID or ledger could be grafted onto genuine Gateway logs.
- Cloud Run is still public because it is a synthetic MCP proof service. Do not
  generalize that posture to production customer data.
- The stale Registry service remains pinned to its v1 read-only surface while
  Cloud Run serves v2. Do not update Registry during Gateway work.
- All synthetic IDs and `example.invalid` addresses are controls. Do not use
  external targets or real customer data.
- Keep TOOL call roots structural. Never let a model label provenance, trust,
  revision admission, or policy outcomes.

## Next capability after Gateway

Since the schema-v2 live proof and independent gates now pass, the next
highest-value missing Fleet capability is Model Armor. Observability follows
Model Armor; Agent Identity is already genuinely present in the Gateway proof,
but its claim must stay scoped to that Runtime. Live Memory Bank selective
deletion comes later and only if the actual API semantics preserve Custody's
lineage contract.

Before starting Model Armor: update `.claude/SESSION_CONTRACT.md` with a new
session contract scoped to that capability (objective, allowed files,
acceptance gates) per the global evidence-gated protocol — do not silently
broaden scope under the existing Gateway-scoped contract.
