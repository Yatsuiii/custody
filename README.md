# Custody

Chain of custody for agent memory.

An agent reads a supplier page in week one. The page carries an instruction, not
information. Nothing happens. In week three an ordinary request retrieves what
was remembered, and customer records leave the building.

```
$ make demo

  WITHOUT CUSTODY
    week 1  memories written                3
    week 3  retrieved into instruction context 3
            of those, carrying the injected instruction: 2
    export to compliance-archive@external.example: ALLOWED

  WITH CUSTODY
    week 1  events seen 3, admitted 1, withheld 2
            quarantined: tool     from fetch_page
            quarantined: derived  from fetch_page
    week 3  retrieved into instruction context 1
            of those, carrying the injected instruction: 0
    export to compliance-archive@external.example: REFUSED
            cited content came from untrusted source(s): fetch_page
```

The instruction reached instruction-eligible context in the first run and never
entered memory in the second. **What changed is the memory path, not the model.**

## The gap this fills

ADK gives every memory an author. From `memory/memory_entry.py`, a `MemoryEntry`
carries `content`, `custom_metadata`, `id`, `author`, `timestamp`. And
`events/event.py` documents `Event.author` as *"'user' or the name of the agent,
indicating who appended the event to the session."*

Both answer **who put this here**. Neither answers **where the content came
from**. So text a user typed and text scraped from a hostile page are
indistinguishable once they are in memory, which is the precondition for
[OWASP ASI06](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

Custody adds origin and derivation on top of Memory Bank, through the existing
`BaseMemoryService` port, without modifying anything.

```python
from custody.adapters.adk import CustodyMemoryBank

memory = CustodyMemoryBank(downstream=VertexAiMemoryBankService(...))
```

That is the whole integration.

## What it costs a compromised tool

A tool your fleet trusted turns out to be compromised. Without a derivation
graph, "which memories descended from it" is not a hard question, it is an
unanswerable one. So the options are purge everything, purge every department
that touched it, or leave the poisoned lineage in place.

```
$ make cost

  600 memory records. 'vendor_portal' is found compromised.

  response                                 destroyed   survives
  ------------------------------------------------------------
  purge the whole app                          600          0  (0%)
  purge every department that used it          600          0  (0%)
  remove exactly the descendants                40        560  (93%)
```

That headline is the flattering case, so the same command prints the
sensitivity. Restricting the tool to fewer departments moves the saving from
93% down to 19%, and even at a single department a per-user purge destroys 20%
of fleet memory to remove 1%.

What does not move with the fixture is the granularity, and it is the actual
claim: **with no derivation recorded the smallest unit you can safely purge is a
user. With it, the unit is a record.**

## How it decides

Origin is read off the event graph, never inferred by a model.
`Event.get_function_responses()` makes "this text arrived from a tool" a
structural fact. Each content part is `USER`, `MODEL`, `TOOL`, or `DERIVED`.

**`DERIVED` is the one that matters.** A model turn following an untrusted tool
response inside the same invocation inherits the distrust, because when an agent
summarises a hostile page the summary is what survives into memory and the raw
response is discarded. Labelling only raw tool output would protect nothing.
`InMemoryMemoryService` makes this concrete: it indexes `part.text` only, so a
raw `function_response` is stored and never retrieved. The laundered restatement
is not merely also dangerous, it is the only retrievable form.

Content that cannot be attributed is refused rather than stored as trusted.
Absence of evidence is never a clean bill of health.

## Cross-department isolation

```
$ make isolate

  -- adversarial attempts --
    sales -> support: REFUSED
        sales cannot vouch for support's tools
    support -> sales: REFUSED
        support cannot vouch for sales's tools

  -- sales vouches for its own tool --
    sales trusts crm_lookup: True
    support trusts crm_lookup: False
```

Trust earned in one department does not leak into another's writes, and nothing
quarantined in one is visible from the other.

## Retroactive revocation

```
$ make revoke

    before revocation: 5 record(s)
        sales-inv-1:0:0          user     trusted
        sales-inv-1:1:0          tool     trusted
        sales-inv-1:2:0          model    trusted <- ('sales-inv-1:1:0',)
        support-inv-1:0:0        tool     trusted <- ('sales-inv-1:2:0',)
        support-inv-1:1:0        model    trusted <- ('support-inv-1:0:0',)

    demoting crm_lookup
    revocation rev-2026-08-N: removed 4 record(s)
    after revocation: 1 record(s)
        sales-inv-1:0:0          user     trusted

    replay: 0 further record(s) removed, 1 revocation record(s) total
```

Three derivation hops, across a department boundary, through a real
`load_memory` retrieval rather than a synthetic edge. The user's own question,
unrelated to the tool, survives. Replaying the revocation removes nothing
further and appends no second audit record.

## Spin up

Python 3.12. The core imports no SDK, so the full suite runs with no cloud
account and no network.

```bash
git clone <this repo> && cd custody
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

make check     # ruff, then 170 tests, none skipped
make demo      # the poisoning scenario, with Custody and without
make cost      # what a compromised tool destroys, with the graph and without
make revoke    # retroactive revocation across departments, and a replay
make isolate   # two departments, one catalog, no shared trust unless earned
```

`google-adk` is the core integration dependency, and it is what the conformance tests
need: they build genuine `google.adk.events.Event` objects and run the core over
them, so the duck-typed core is proved against the real SDK rather than against
stand-ins written in this repo.

Skip the install and the SDK conformance tests report skips rather than
pretending. The pure core remains runnable without cloud credentials.

## Architecture

[Diagrams](docs/architecture.md): what the system is made of, and the path a
piece of content takes from arriving in a tool response to being refused an
export.

Four layers, and the boundary that matters is between deciding facts and
deciding what they mean.

| Layer | File | Role |
| --- | --- | --- |
| Origin labelling | `custody/origin.py` | pure function, no model, no I/O |
| Derivation graph | `custody/graph.py` | traversal and revocation |
| Enforcement | `custody/service.py` | splits a session before the write |
| Export gateway | `custody/action.py` | egress must cite trusted memory |
| Trust catalog | `custody/catalog.py` | per-department grants |
| Revision admission | `custody/revision.py` | pins MCP tool definitions and blocks drift before dispatch |
| Durable stores | `custody/store.py` | offline SQLite fake, survives a restart |
| Live durable store | `custody/firestore_store.py` | Firestore-backed, same ports, deployed for G5 |
| ADK shell | `custody/adapters/adk.py` | `BaseMemoryService` ADK accepts |

Enforcement happens at the **write**, not at retrieval. Memory Bank derives
memories server-side, so a stored memory is not byte-identical to any event and
cannot be matched back to a custody record afterwards; a memory derived from
mixed-trust events has no single origin at all. Splitting before the write also
sidesteps `search_memory` having no filter parameter.

## Status, honestly

| | |
| --- | --- |
| Core, verified against real google-adk 2.6.3 | **built**, 170 tests |
| Derivation graph and retroactive revocation | **built** |
| Cross-department isolation | **built** |
| Durable stores surviving a restart | **built**, SQLite |
| Cloud Run control plane, Gemini 3.5 on Vertex, ADK to live Memory Bank | **built**, `make live-g1` |
| Agent Registry and live stale-tool admission | **built**, `make live-registry-attack` |
| Agent Runtime, Agent Identity, and enforced Agent Gateway IAP | **built**, `make live-gateway` |
| Model Armor content screening | **built**, `make live-model-armor` |
| Agent Observability | **not built** |

Nothing in this table moves to built without a command that demonstrates it.

### Live G1 proof

Authenticate `gcloud` and Application Default Credentials into the ignored
`.gcloud/` directory, then reuse the provisioned Agent Engine:

```bash
CLOUDSDK_CONFIG="$PWD/.gcloud" \
CUSTODY_PROJECT=project-988bc9fe-092c-4b32-90c \
CUSTODY_AGENT_ENGINE_ID=6936011268348182528 \
make live-g1

make gates
```

`make live-g1` uses a fresh proof id and scope every time. It verifies the
deployed Cloud Run health and trigger, receives an exact proof-bound response
from Gemini 3.5 Flash through Vertex AI, then runs a real ADK agent whose
after-agent callback writes one clean session through Custody into Memory Bank.
The independent judge reads `proof-out/g1.json`; a failed rerun removes the old
artifact, and evidence older than 24 hours returns to BLOCKED.

### Live stale-Registry proof

```bash
CLOUDSDK_CONFIG="$PWD/.gcloud" \
CUSTODY_PROJECT=project-988bc9fe-092c-4b32-90c \
make live-registry-attack

make registry-gates
```

The proof deploys a v1 FastMCP tool to Cloud Run, uploads its actual
`tools/list` response to Agent Registry, and successfully calls it through the
endpoint read back from Registry. It then deploys a forwarding-capable v2 to
the same URL without updating Registry. The negative control dispatches v2;
Custody recomputes the live definition digest, emits `revision_mismatch`, and
blocks before the server counter moves. Revision-specific revocation removes
only the lineage rooted in the live v1 call result and preserves the v2 branch.
The independent judge recomputes both digests and binds the graph roots to the
live call-result hashes. This proves declared MCP surface drift, not a
behavior-only binary change with an identical `tools/list` definition. The
surface read and a later allowed dispatch are not cryptographically atomic. The
live Gateway proof below governs a registered tool name, but it does not bind a
revision digest to dispatch; closing that time-of-check/time-of-use window still
requires revision attestation at the Gateway or server. The demonstrated
mismatch path is fail-closed because it never reaches dispatch.

### Live Agent Gateway proof

```bash
make setup-gateway

GOOGLE_APPLICATION_CREDENTIALS="$PWD/.gcloud/application_default_credentials.json" \
CUSTODY_PROJECT=project-988bc9fe-092c-4b32-90c \
make deploy-gateway-probe

CLOUDSDK_CONFIG="$PWD/.gcloud" make live-gateway

CLOUDSDK_CONFIG="$PWD/.gcloud" make gateway-gates
```

The deployed custom Agent Runtime has `AGENT_IDENTITY` and is bound to the
regional `custody-fleet-egress` Agent Gateway. The proof installs one
proof-owned, server-expiring IAM condition:

```cel
api.getAttribute('iap.googleapis.com/mcp.toolName', '') == '' ||
(request.time < timestamp('<10-minute-expiry>') &&
 api.getAttribute('iap.googleapis.com/mcp.toolName', '') == 'lookup_customer')
```

The empty-name clause is unconditional, so MCP handshake/non-tool traffic stays
admitted independent of the tool lease; only the registered `lookup_customer`
admission is time-boxed. After IAM convergence the proof runs four controls
under this one policy and its restored safe-deny successor: an allowed
`lookup_customer` call while the lease is live; a `custody_policy_canary` call
under the same live lease, which the exact tool-name match denies before
dispatch (this is what proves a narrow admission rather than a broad
historical allow); a `lookup_customer` call after the server-side
`request.time` boundary passes, denied before dispatch even though the empty
name clause is still open; and a final `lookup_customer` call after the policy
is restored to the safe canary/deny condition. The dedicated proof policy
refuses to overwrite unrelated bindings, uses the current etag on every write,
and restores the no-registered-tool state on any failure. The owned,
single-instance Cloud Run ledger moves exactly once, for the allowed call, and
does not move for any of the three denied calls; the successful tool result
names the same process. Cloud Logging independently records `tools/call` as
`ALLOWED/200` for the admitted call and `DENIED/403` for each denied call,
under four distinct W3C trace IDs. Admin Activity records the
initial→allow→deny etag chain.

`make gateway-gates` rejects stale or broadened claims, dry-run/fail-open
extensions, wrong resources or identities, non-exact IAM policies (including
the schema-v1 shape that expired the handshake clause along with the tool
lease), fabricated dispatch results, changed server instances, reversed
transitions, and unbound or duplicate logs. It then performs authenticated
read-only Google Cloud readbacks of the fixed project resources, final deny
policy, Runtime, Cloud Run target, and exact Gateway/Audit log insert IDs.
This proves one owned Runtime-to-Gateway-to-MCP path. It does not prove all
egress is covered, govern unclassified non-tool traffic, repair stale Registry
metadata, bind a tool revision atomically, or delete revoked descendants from
live Memory Bank.

**S1 passed live again on 2026-08-13 against schema v2**, proof
`e2b9f562fa3a48249054b977b5779a21`. Cloud Run revision
`custody-export-mcp-00009-wp2` moved from dispatch count 0 to 1 for the one
allowed call and stayed at 1 through the canary, expiry, and final deny
controls. `make gateway-gates` reported twenty PASS results across the offline
judge and the independent live Google Cloud attestation.

### Live Model Armor proof

```bash
CLOUDSDK_CONFIG="$PWD/.gcloud" make live-model-armor

CLOUDSDK_CONFIG="$PWD/.gcloud" make model-armor-gates
```

Model Armor has no ADK module and no client library, same as Agent Gateway;
the proof is a routed call against one owned Template
(`custody-approved-tool-ingress`) with its PI-and-jailbreak filter enabled at
`MEDIUM_AND_ABOVE`. The producer validates the Template's exact configuration,
then issues two proof-bound `sanitizeUserPrompt` calls: a jailbreak-style
payload embedding the proof ID, and an unrelated clean payload embedding the
same proof ID. Model Armor blocks the first
(`MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK`, "The prompt violated Prompt
Injection and Jailbreak filters.") and allows the second
(`MODEL_ARMOR_SANITIZATION_VERDICT_ALLOW`). Both calls are independently
logged server-side because the Template has `logSanitizeOperations` enabled;
the exact prompt text in each Cloud Logging entry is what ties a log line to
one proof run, the same role a trace ID plays in the Gateway proof.

`make model-armor-gates` rejects a drifted or unowned Template, a malicious
control that wasn't actually blocked, a clean control that was wrongly
matched, a log entry reused between the two controls, and a log entry outside
the proof's time window or bound to another template/region. It then
independently rereads the Template and both log entries (by their
server-issued insert IDs) from Google Cloud using code-owned resource
identifiers, never ones the artifact supplies. This proves content screening
for one owned Template; it does not screen any traffic Custody has not
explicitly routed through it, and it does not gate MCP tool admission or IAP.
Model Armor and origin/derivation are complementary, not the same claim: a
memory can be admitted by Custody's origin rules and still be screened by
Model Armor before it ever reaches that path, and neither one substitutes for
the other.

**M1 passed live on 2026-08-13**, proof `4af5a4b8d3244c3c80054c15b69e58ad`.
`make model-armor-gates` reported nine PASS results across the offline judge
and the independent live Google Cloud attestation.

### G5's elapsed-time clock, in progress

G5 needs one custody record with genuine timestamps spanning from first
deploy to filming, not fast-forwarded. That cannot be produced in one
sitting, so this is a status, not a pass/fail gate. `custody/firestore_store.py`
backs the derivation graph with Firestore (Native mode, `us-central1`), same
ports as the offline SQLite store; the control plane's `POST /auditor`
(idempotent per UTC day) seeded one fixed synthetic record on 2026-08-13 and
a daily Cloud Scheduler job keeps the heartbeat going. Durability across a
real Cloud Run cold start is already verified: the seed record's admission
timestamp was byte-identical after forcing a new revision. What's still
open: enough real days need to pass, then the record gets revoked near
filming and `scripts/scheduler_gates.py` (not yet written; building a judge
before there is a multi-day span to judge would have nothing real to check)
independently proves the whole span.

**A stated bet, not a finding:** no enterprise incident data exists for memory
poisoning. It has formal standing as OWASP ASI06 and demonstrated attack success
rates in research, but recognised and demonstrated is not the same as happening
to customers. Long-term memory adoption is also early: 2 of 34 official ADK
sample agents use a memory service at all.

## Prior work

`google-adk` and the Vertex AI SDK are consumed unmodified. Everything else is
new work created during the submission period.
