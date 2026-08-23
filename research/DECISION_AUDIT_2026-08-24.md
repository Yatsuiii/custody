# Custody Decision Audit — 2026-08-24

Status: `SUPERSEDED_BY_B7_PRODUCTION_INTEGRATION_DESIGN`

Lane: evidence-gated systems builder / research engineering

This is a decision artifact, not an experiment result. No benchmark, model, API,
cloud deployment, or production path was executed or modified.

## Scope and ground truth

The audit used the current worktree, local and `origin` research refs, and the
exact commits in the Gate 1B → Gate 1C → Gate 2 chain. The current branch is
`15d6dcb` (`research/external-gate2-mpbench`). The relevant valid commits are:

| Evidence | Exact source |
|---|---|
| Gate 1B-R3 valid receipt experiment | `f3eb51c` |
| Gate 1C-R3 valid selective-revocation experiment | `437fc2a` |
| Gate 2 frozen MPBench preregistration | `15d6dcb` |
| Gate 1B initial/R1/R2 invalid attempts | `b1ff1dd`, `d339f10`, `5bf3586` |
| Gate 1C initial/R1/R2 invalid attempts | `5e47b9f`, `9dbf6b7`, `40e33a7` |

`git ls-remote` matched the inspected local remote refs. Existing untracked
worktree material was preserved.

## 1. Evidence ledger

### Valid evidence

| Evidence | Result | Boundary |
|---|---|---|
| E0/E1 multi-parent lineage | 10/10 deterministic cases; 381/381 suite | synthetic/model-free local mechanism |
| Gate 1B-R3 | forged, replayed, wrong-scope, wrong-generation, and mixed/untrusted receipts denied; benign relay 2/2; cross-agent legitimate 2/2 | valid model-free receipt adapter; no model/API |
| Gate 1B-R3 revocation | affected descendants denied, but issuer-wide revocation collateralized benign/pre-existing/post-remediation utility | valid falsifier; `COMPOSITION-FAILS / REVOCATION_COLLATERAL` |
| Gate 1C-R3 | affected recall 4/4; affected false ACT 0/4; unrelated, pre-compromise, post-remediation utility 2/2; escape controls 0; history immutable | valid model-free selective-root adapter |
| E2H-R1E | real Firestore, independent writer/policy/gateway processes, restart reconstruction, contention, killed writer, partial admission, gateway race, stale cache, duplicate envelope, missing state, and recovery | valid real-persistence/process safety result; `INTEGRATION-FAIL-CONTAINED` because recovery missed the frozen 90-second liveness bound |
| E2A TMA-NM tool echo | current Custody accepted attacker tool echo like trusted content and reached the action path | valid external failure of the current interface |
| E2B/E2C transformed retrieval | malicious paraphrase was blocked only because benign paraphrase also lost exact-hash authority | valid external limitation; not laundering resistance |
| Gate 1B-R3 transform controls | `IDENTITY` and legitimate `REGISTERED` transformations preserved bounded authority; `FREEFORM` retained lineage but could not mint ACT | valid B7 model-free architectural distinction |

The Gate 1B-R3 and Gate 1C-R3 results are narrow mechanism results. They do
not establish a deployable source producer or external benchmark efficacy.

### Invalid or runner-failure evidence

These attempts are retained as invalid and contribute no security verdict:

| Attempt | Failure boundary |
|---|---|
| Gate 1B initial | duplicate fixture insertion before treatment |
| Gate 1B-R1 | import lifecycle failure before scoring |
| Gate 1B-R2 | uncaught `InvalidSignature` during forged-receipt handling |
| Gate 1C initial | unhashable selector before arm evaluation |
| Gate 1C-R1 | selector alias/record-ID mismatch before arm evaluation |
| Gate 1C-R2 | post-treatment metric helper inverted false-ACT accounting; raw traces retained, emitted `KILL` invalid |

No invalid runner label is evidence against Custody. It is also not evidence
for Custody.

### Evidence class ledger

| Class | What exists | What does not exist |
|---|---|---|
| Synthetic/model-free | E0/E1, Gate 1B-R3, Gate 1C-R3, local receipt fixture | model-mediated transformation and production fault coverage |
| Real-cloud/deployment | E2H-R1E demonstrated safety across real Firestore and independent W/P/G processes; the existing live MCP server also demonstrates a deployment-owned signer for dispatch-surface attestations | no deployment-owned source service yet emits a B7 object-bound authority receipt; E2H-R1E recovery missed 90 seconds |
| External | TMA-NM/MEM-INV-Bench, Sleeper, MPBench, MemSecBench, MemLineage, PACT, MCP/C2PA/webhook primary artifacts | no external benchmark natively joins source identity, object-bound authority, memory derivation, and action outcome |
| Benchmark-interface limitation | MPBench has dataset only; TMA-NM exposes scenario/origin metadata; Sleeper has no authenticated issuer; MemSecBench has no public artifact located | no legitimate B7 authority producer for native external evaluation |
| Still untested | B7 through production Custody APIs; object-bound source receipt emission; complete production context capture; operational recovery latency; buyer pain and willingness to pay | evidence required for an end-to-end B7 deployment claim and a startup claim |

## 2. Claim status

Status labels are scoped to the evidence boundary; “proven” never means proven
in a real deployment.

| Claim | Status | Reason |
|---|---|---|
| Provenance survives derivation | `PARTIALLY-SUPPORTED` | old exact-match Custody has the E2C transform cliff; B7 separately preserves bounded authority through `IDENTITY` and legitimate `REGISTERED` transformations while `FREEFORM` deliberately cannot manufacture ACT |
| Trusted relay cannot launder authority | `FALSIFIED` for current/old Custody; `PROVEN` for the bounded B7 adapter | E2A tool echo passed current Custody; Gate 1B-R3 B6+P2 preserved benign relay 2/2 while harmful tool echo and forgery/replay/scope/generation controls stayed at zero false ACT |
| Forged/replayed provenance is rejected | `PROVEN` in bounded model-free adapter | Gate 1B-R3 and Gate 1C-R3 controls; no real issuer |
| Generation freshness | `PROVEN` in bounded model-free adapter | stale-generation controls denied; production clock/event ordering is untested |
| Multi-parent support preservation | `PROVEN` in bounded local mechanism | E0/E1 and Gate 1C-R3 mixed-parent controls; transform attribution remains unresolved |
| Cross-agent propagation | `PARTIALLY-SUPPORTED` | valid local cross-agent allow/deny paths; no real agent framework with independently signed source events |
| Selective retrospective revocation | `PROVEN` in bounded model-free adapter | Gate 1C-R3: affected recall 4/4, unrelated utility 2/2, escape controls 0 |
| Benign utility preservation | `PARTIALLY-SUPPORTED` | narrow local controls preserve utility; external transformations expose collateral exact-match failure |
| Durable/process-boundary enforcement | `PARTIALLY-SUPPORTED` | E2H-R1E supported safety across real Firestore and independent processes under restart, contention, partial writes, races, stale caches, duplicate envelopes, missing state, and killed writers; `recovery_completed_within_bound` failed 0/1 under the frozen 90-second window |
| Real-world memory-poisoning efficacy | `BLOCKED` | current external interface failed E2A; corrected B7 cannot be supplied by the released benchmark world without an issuer |
| Deployability of provenance producer | `BLOCKED` | no benchmark-author or deployment-owned producer is currently integrated |
| Operational usability | `UNTESTED` | no operator, latency, connector, key-rotation, or incident-response evidence |
| Advantage over simpler baselines | `PARTIALLY-SUPPORTED` | selective revocation beats issuer-wide revocation in the local falsifier; no buyer-side comparison against RBAC, RAG filters, approvals, or gateway policy |

## 3. External-source audit

### Benchmark and paper artifacts

| Artifact | Actual producer and authority | B7 status | Fatal limitation |
|---|---|---|---|
| MPBench, `Digital-Trust-Lab/mp-bench@6886880a7c29625e0109e0ad91d0e095029f1577`, Apache-2.0 | adversarial/benign dataset records; no authenticated source service | `NO-AUTHORITY-PRODUCER` | dataset adaptation; no official target agent, scorer, provider, seeds/config, or benign retrieval oracle |
| Hidden in Memory / Sleeper, `ivaxi0s/LLM-agent-memory-poisoning@70de017714abd6d12bb4681e93437461ba6f9a19` | Inspect harness, external manager, memory manager, source datasets; no authenticated issuer | `NO-AUTHORITY-PRODUCER` | native IR/RR/AUR and runnable action regime, but external manager is not automatically an authority issuer |
| TMA-NM / MEM-INV-Bench, `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1`, MIT | benchmark monitor/origin metadata and scenario labels | native `ORACLE-ONLY`; future declared adapter `INSTRUMENTABLE-WITH-DECLARED-ADAPTER` | `true_origin`/scenario metadata is not an independently owned runtime producer; common-observed B7 is unavailable |
| MemSecBench, arXiv:2607.27080 | no public corpus/harness artifact located | `BLOCKED` | cannot pin or run; do not recreate locally |

The current finding is therefore a genuine `EXTERNAL-INSTRUMENTATION-GAP`, not
a Custody security result. The existing MPBench Gate 2 preregistration remains
frozen and untouched; its $29.36 adaptation would not answer the missing
authority question.

### Real producer candidates beyond the benchmarks

| Candidate | Exact artifact/version | What it authenticates | B7/usefulness assessment | Integration, cost, fatal limitation |
|---|---|---|---|---|
| MemLineage | arXiv:2605.14421; `amurlaniakea/memlineage@73e770478f044323052a402795690c9d4e62f804`; AGPL-3.0-or-later | Ed25519 signature over memory entry fields; frozen key registry binds signer to a principal; derivation IDs are recorded | `INSTRUMENTABLE-WITH-DECLARED-ADAPTER`: a real deployment source service could own a registered key, but this repo’s `MemoryStore.write(content, source)` is a local caller-driven store, not an independently operated source service | medium/high engineering, $0 offline; AGPL and no benchmark-native independent source/service symmetry; signature authenticates issuer/key and bytes, not truth of the issuer’s backend |
| MCP | official Server Tools specification `2025-06-18` | transport authorization identifies the server/client boundary; `structuredContent` and output schema provide structure, not an object signature | deployment surface only; `NO-AUTHORITY-PRODUCER` as a base protocol. A specific MCP server can become a legitimate producer only by publishing and operating an object-bound signing contract | low/medium adapter effort, $0 prototype; standard says tool annotations are untrusted and does not bind result semantics to an authority receipt |
| Stripe webhooks | official “Receive Stripe events” and signature-verification artifacts, accessed 2026-08-24; no source-repo commit | Stripe signs each event with endpoint secret; timestamp is signed and replay tolerance is specified | strongest concrete source boundary for a deployment pilot, but not a memory benchmark. Benign and attacker HTTP deliveries can be symmetric at the receiver; only Stripe-originated events carry valid authority | low/medium, $0 test-mode prototype; source events are already business-authoritative, so this tests source authentication more than memory-poisoning semantics |
| C2PA | C2PA Technical Specification v2.4 | signer identity, signed claims, manifest, and hard content binding | real object-bound provenance for content assets; `INSTRUMENTABLE-WITH-DECLARED-ADAPTER` for an agent ingesting signed documents, not native B7 memory/action evaluation | medium, $0 inspection; no memory lifecycle, revocation/repair, or consequential agent endpoint; does not assert that signed content is true |
| PACT (Provenance-Aware Capability Contracts) | arXiv:2605.11039; no official paper-linked implementation located in this audit | provenance is supplied as an oracle to the runtime monitor | `ORACLE-ONLY`; useful related work, not a source producer | high/model-backed; its stated deployment bottleneck is provenance inference/contract synthesis |

The only candidate that could plausibly support a future external evaluation is a
deployment-owned service using a signed event contract (for example a real
webhook or a source API whose operator owns the signing key). None is currently
present in an externally authored memory-poisoning benchmark. MemLineage is the
closest memory artifact, but its published implementation does not establish
that boundary by itself.

## 4. Startup reality check

The mechanism is technically coherent but has no buyer evidence. The following
wedges are hypotheses, not market validation.

| Rank | Buyer / pain | Why ordinary controls fail | What Custody installs | Proof before payment | Friction / failure mode |
|---|---|---|---|---|---|
| 1 | Agent-platform or security owner running MCP tools with shared memory; tool output or stale memory can authorize an external action | OAuth/RBAC authenticates caller and tool, while RAG filters inspect content; neither proves the record’s issuing service or derivation/revocation state | MCP/source-event adapter plus memory-write and action-gateway interception | one sandbox trace set with attacker tool echo, benign retrieval, revocation, and action denial; near-zero unsafe allows, high benign utility, bounded latency | each source server must sign; buyer may classify this as prompt-injection middleware or prefer approval gates |
| 2 | CRM/support/sales automation owner where revoked customer or policy facts can drive outbound messages or updates | access control governs who acts, not whether the fact is current, revoked, or inherited from a compromised record | sidecar at CRM/webhook ingestion and outbound action gate | real source events, a revoked-record replay, benign utility, audit explanation, and recovery procedure | connectors, key ownership, compliance review; human approval may be cheaper |
| 3 | Agent-to-agent/delegation platform owner; downstream agents trust relayed outputs from upstream tools | bearer credentials/capabilities identify a principal but usually do not bind an individual returned object and its derivation | signed object envelope and relay verifier, with scoped generation/revocation checks | cross-agent test with independent source service, relay, laundering transform, and consequential endpoint | no common standard; integration becomes bespoke; if no high-value action is gated, provenance is observability rather than a budget item |

The hostile startup conclusion is that Custody currently looks more like a
specialized security mechanism than a product. The decisive unknown is not
whether the mechanism can be built; it is whether a buyer controls a real source
boundary and will pay to make that boundary emit and maintain attestations.

## 5. Research contribution assessment

There is a defensible narrowed contribution: object-bound authority, multi-parent
derivation preservation, and selective retrospective root revocation are shown
in a reproducible model-free mechanism boundary. The result is strengthened by
the external failure showing why trusted-tool identity and exact-content/lineage
heuristics are insufficient.

It is not yet a full end-to-end benchmark or deployment contribution. The
missing pieces are a B7 object-bound producer, integration through production
Custody APIs, complete production context capture, bounded recovery liveness,
and a real behavioral evaluation. MemLineage and PACT also reduce any claim of
novelty for origin binding or argument-level provenance; the plausible novelty
is the specific revocation/derivation composition, not provenance itself.

## 6. Superseding next move

`B7_PRODUCTION_INTEGRATION_DESIGN`

The earlier `USER-VALIDATION` sequencing recommendation is withdrawn. The
validated B7 candidate has not yet been exercised through production Custody
APIs, while E2H-R1E already supplies more durable/process evidence than the
original audit credited. The next bounded task is therefore a design-only map
from frozen B7 semantics into existing production modules. No B8 mechanism,
benchmark execution, or production edit is authorized by this correction.

## 7. Kill conditions

Kill Custody rather than add another gate if any of these become true:

- no independent source owner will emit object-bound events for a real workflow;
- the 8–10 person validation sprint produces no recurring costly incident and no
  pilot/trace commitment;
- a real producer integration cannot preserve benign utility without requiring
  scorer-like labels or unacceptable latency/operational burden;
- ordinary RBAC, RAG filtering, audit logs, or human approval match the safety
  and utility envelope at lower integration cost;
- a valid deployment test shows selective revocation or generation freshness
  fails under retries, crash recovery, or concurrent source/action updates; or
- the narrowed research result cannot be distinguished from MemLineage/TMA-NM/
  PACT beyond implementation detail.

## Audit controls

- Gate 2/MPBench was not modified or executed.
- Gate 1 and production paths were not modified.
- No model/API/cloud credits were spent.
- No scorer-only field, `true_origin`, attack label, expected memory, or
  benchmark truth was used to mint a receipt.
