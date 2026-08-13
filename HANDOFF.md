# Custody recovery handoff, 2026-08-13 (post schema-v2 Gateway + Model Armor proofs)

This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

## Lane and artifact

Lane: agentic security infrastructure, built as an evidence-gated systems
project for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet.

Both the Gateway (S1) and Model Armor (M1) artifacts this file previously
tracked as in-progress/not-started are now **complete and independently
judged**:

- `proof-out/live-gateway.json` (schema v2, proof
  `e2b9f562fa3a48249054b977b5779a21`); `make gateway-gates` reports twenty PASS
  results (twelve offline judge, eight independent live attestation).
- `proof-out/live-model-armor.json` (proof
  `4af5a4b8d3244c3c80054c15b69e58ad`); `make model-armor-gates` reports nine
  PASS results (six offline judge, three independent live attestation).

README.md and `.claude/SESSION_CONTRACT.md` were updated from this evidence
and are authoritative for the S1/M1 claim text; do not restate either from
memory, read them.

The last commit (`df334f1`, see `git log -1`) landed all accumulated G1/R1/S1
work. M1 was built and evidenced after that commit and is **not yet
committed** as of this handoff — check `git status` before assuming otherwise.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- Origin is one commit behind local HEAD (`df334f1` is not pushed).
- Nothing has been pushed. Do not push without explicit authorization.
- Preserve every unrelated/preexisting modification. Inspect with:

```sh
git status --short --branch
git diff --check
git diff --stat
git log -5 --oneline --decorate
```

The Model Armor files added after the last commit:

```text
scripts/live_model_armor.py
scripts/model_armor_gates.py
tests/test_model_armor_gates.py
tests/test_live_model_armor_producer.py
```

The MCP server used by both the stale-Registry proof and Gateway proof is
`live/registry_attack/server/server.py`. Do not remove its existing revision
or forwarding behavior; it was not touched in this pass.

## Previously proven state, do not redo

- G1 is complete: live Cloud Run, Gemini/Vertex, ADK, and Memory Bank evidence.
- Live stale Agent Registry proof (R1) is complete.
  `make registry-gates`: 8/8 PASS. `make revision-spike`: 5/5 PASS.
- **S1 (Gateway) is complete**, schema v2, `make gateway-gates`: 20/20 PASS.
- **M1 (Model Armor) is complete**, `make model-armor-gates`: 9/9 PASS.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  expected — missing telemetry and a Cloud Scheduler elapsed-time record, not
  a regression; Model Armor being live no longer changes this, it folds into
  the already-complete security/governance group).

Known limitations that must remain explicit unless new direct evidence changes
them:

- CustodyGraph revocation does not delete live Memory Bank descendants.
- RevisionCatalog and some approval state are application-side.
- The admitted surface-read to dispatch path has a TOCTOU window and is not
  cryptographically atomic.
- Behavior-only drift with identical `tools/list` is outside the revision claim.
- Submission-grade Agent Observability remains unproven (this is the expected
  G5 BLOCKED reason, not a regression).
- The Gateway proof covers one owned Agent Runtime identity, one registered MCP
  projection, and four controlled calls (allow, tool-scope-canary, expiry,
  final deny). It does not prove all fleet egress is covered.
- The Model Armor proof covers one owned Template and two controlled
  `sanitizeUserPrompt` calls. It does not screen traffic Custody has not
  explicitly routed through that Template, and it does not gate MCP tool
  admission or IAP — those remain separate, additive claims.

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
Model Armor Template:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/templates/custody-approved-tool-ingress
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

**Model Armor Template `custody-approved-tool-ingress`** was found already
provisioned in the project (created 2026-08-13T05:24:35Z, before this
session), with `piAndJailbreakFilterSettings` at `MEDIUM_AND_ABOVE` and
`logSanitizeOperations`/`logTemplateOperations` enabled, labeled
`custody-proof: approved-tool-ingress`. Nothing in the repo referenced it
before this session. Confirmed with the user and reused as the owned M1
Template rather than creating a new one. It is read-only from the proof's
perspective — `sanitizeUserPrompt` calls do not mutate the Template — so there
is no lease/etag/CAS state machine to reason about here, unlike Gateway's IAP
policy.

## What changed in this session (2026-08-13)

Two pieces of work, in order. Full narrative detail (exact bugs, exact fixes)
is preserved in `git log` commit `df334f1` and the diff itself; this section
is a summary so a future agent does not need to re-derive it.

**1. Fixed and completed the schema-v2 Gateway proof (S1).** The prior handoff
left a rejected schema-v2 run whose CEL expired the empty-name MCP-handshake
clause together with the `lookup_customer` lease. Fixed the CEL to an
independent-clause shape (`... == '' || (request.time < timestamp(...) && ...
== 'lookup_customer')`) in `scripts/live_gateway.py` and
`scripts/gateway_gates.py`, added a bounded outer timeout around
`engine.async_query`, and gave `_gateway_logs` bounded/recovering polling. The
first live rerun then surfaced two bugs the CEL fix didn't touch: an IAP etag
base64-alphabet mismatch between `gcloud` readbacks (url-safe) and raw Admin
Activity payloads (standard) breaking audit-chain correlation, and the offline
judge assuming strict causal order between two independent same-process clock
reads ~300 microseconds apart. Both fixed with regression tests
(`_canonical_etag` normalization; a `_CLOCK_SKEW_BOUND` tolerance).
`gateway_live_attestation.py` also assumed a flat MCP result shape when the
live server actually returns the standard `content`/`structuredContent`
envelope — fixed to unwrap it. Result: `make live-gateway` succeeded, `make
gateway-gates` reported 20/20, all other gates (`registry-gates`,
`revision-spike`, `gates`, `check`) stayed green. README.md and
SESSION_CONTRACT.md updated from the evidence. All committed in `df334f1`.

**2. Scoped and built the Model Armor proof (M1).** Per this file's own prior
instruction, updated `.claude/SESSION_CONTRACT.md` with a Model Armor-scoped
objective and acceptance gates before writing code. Confirmed `gcloud
model-armor` reachability (`templates create/describe/list/update/delete`,
`sanitize-user-prompt`, `sanitize-model-response`). Discovered an
already-provisioned, unreferenced Template (see above); confirmed with the
user and reused it. Built `scripts/live_model_armor.py` (producer: validates
the owned Template, issues one proof-bound jailbreak/PI `sanitizeUserPrompt`
call expecting BLOCK and one proof-bound clean call expecting ALLOW, polls
Cloud Logging for the matching server-authored entries, writes
`proof-out/live-model-armor.json`) and `scripts/model_armor_gates.py`
(offline judge plus independent live attestation, mirroring the
producer/judge split used for R1/S1 but without the IAM-lease machinery,
since sanitize calls don't mutate the Template). Correlation between a proof
run and its Cloud Logging entry is by exact `sanitizationInput.text` equality
(the prompt embeds the proof ID), since Model Armor's API does not accept a
client-supplied trace ID the way IAP does. First live run passed all 9 gates
with no rework needed. Added `tests/test_model_armor_gates.py` (16 adversarial
offline + 4 live-attestation tests) and
`tests/test_live_model_armor_producer.py` (8 fault-injection tests). Ran
`make check` (233 tests), `make registry-gates`, `make revision-spike`, `make
gates`, and `git diff --check`, all clean. Updated README.md and
`.claude/SESSION_CONTRACT.md` from the evidence. Fixed a stale G5 message in
`scripts/gates.py` that still called Model Armor unbuilt, and fixed a
pre-existing `C901` complexity violation in `judge_g1` surfaced by the
clean-code hook while editing that file (extracted `_g1_cloud_run_errors`,
`_g1_gemini_errors`, `_g1_adk_run_errors`, `_g1_memory_bank_errors`).

**Not yet committed** — see git state above.

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
  revision admission, or policy outcomes. Model Armor's structured
  match/no-match verdict is a fact Custody may read, same as a CEL admission
  or a revision digest — never let a model relabel it either.

## Next capability after Gateway and Model Armor

The next highest-value missing Fleet capability is Agent Observability.
Agent Identity is already genuinely present in the Gateway proof, but its
claim must stay scoped to that Runtime. Live Memory Bank selective deletion
comes later and only if the actual API semantics preserve Custody's lineage
contract.

Before starting Observability: update `.claude/SESSION_CONTRACT.md` with a new
session contract scoped to that capability (objective, allowed files,
acceptance gates) per the global evidence-gated protocol — do not silently
broaden scope under the existing Gateway/Model-Armor-scoped contracts. Note
that G5 also needs a Cloud Scheduler record proving real elapsed time across
the whole project's timeline (an early-admitted, later-revoked custody
record), which is a separate concern from Observability itself and should not
be silently folded into the same contract without saying so.
