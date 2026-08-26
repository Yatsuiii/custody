# External-validity preregistration: GitHub issue action

Experiment family: `EXTERNAL_VALIDITY_GITHUB_ISSUE_ACTION_V1`

Status: **PREREGISTERED-DESIGN / EXECUTION-BLOCKED**

Classification: `LIVE-PLATFORM / MODEL-FREE / CONSEQUENTIAL-REVERSIBLE`

This document freezes a falsification experiment. It creates no runner and
authorizes no GitHub, Firestore, model, or other external operation. A passing
result would support one narrow GitHub workflow; it would not establish that
Custody solves memory poisoning generally.

## 1. Decision and claim boundary

The only question is:

> When real GitHub-authored records cross a memory/relay boundary, does frozen
> B7 prevent an unauthorized close of a real sandbox issue while preserving
> legitimate closes better than the strongest simple automated rule system?

The experiment tests a real source and a real effect:

- **Source producer:** GitHub.com delivering live `issue_comment` `created`
  webhooks from a dedicated private sandbox repository.
- **Consequential endpoint:** changing one dedicated sandbox issue from
  `open` to `closed` through GitHub's REST API.
- **Mandatory compensation:** reopen the issue and verify `state=open` after
  every treatment that closes it. A failed compensation stops the run.

The proposed repository name is
`Yatsuiii/custody-external-validity-sandbox`. The immutable repository ID,
GitHub App installation IDs, webhook hook ID, target issue ID/number, actor
IDs, relay-workflow commit, and API version must be recorded in a setup-only
world freeze before implementation. Until those independently queryable IDs
exist, execution is `BLOCKED`; names or logins alone are not authority.

Passing establishes only that B7 handled the frozen, explicit-reference,
model-free GitHub cases. It does not establish semantic faithfulness, defense
against an actually compromised production account, other platforms,
unstructured model behavior, product value, or superiority over simple rules.

## 2. Frozen lineage

- P7 final evidence commit:
  `4194d3245fd72cee08089f339d21654aebb03bf7`.
- P7 status: `LOCAL-EQUIVALENCE-SUPPORTED`, with the recorded recovery and
  resource caveats unchanged.
- This experiment may import frozen B7 production behavior. It may not modify
  `custody/`, `scripts/p7_run.py`, the P7 scorer, P7 evidence, or any spent P7
  namespace.
- Existing Gate 1, Gate 1B, Gate 1C, and Gate 2 artifacts are context only and
  remain immutable. This is not Gate 2, Gate 3, a new internal gate, or B8.

Before any live setup, the preregistration commit must be pushed and a fresh
clone must verify its SHA. Before any treatment, the runner commit and frozen
world identifiers must likewise be pushed and independently fetch-verified.

## 3. Hypothesis and falsifier

**Hypothesis:** B7 will produce zero unauthorized issue closes, preserve every
authorized close, and execute no duplicate close under webhook redelivery.
It will outperform the simple rule baseline on at least one fixed laundering,
compromise-interval, or mixed-source case without losing benign utility.

This idea may not deserve to exist. The likely falsifier is that a small,
deterministic GitHub-specific rule system matches B7 exactly. If it does, this
workflow provides no evidence that B7's added graph, receipt, generation, and
revocation complexity is justified.

Only the **authorization/memory system** changes between treatments. The raw
GitHub deliveries, normalized observations, incident notice, explicit parent
references, action request, target issue, initial state, case order, and
executor are identical.

No model is used. `model_calls=0`, temperature and seed are not applicable,
and comment semantics are never inferred by an LLM or scorer.

## 4. Independent world and non-fabrication rule

Three principals must remain separate:

1. **World owner:** creates the dedicated repository, installs the minimum-
   permission apps, freezes the case manifest, and owns compensation.
2. **Red-team actor:** a distinct GitHub user posts the attack-world comments.
   The runner and action app must not post source or attack comments.
3. **Treatment/scorer:** treatments consume observations; the scorer reads a
   sealed case table only after every action has completed.

GitHub webhook HMAC is a shared-secret authenticity mechanism, not third-party
non-repudiation. Therefore a valid delivery requires all of the following:

- constant-time verification of `X-Hub-Signature-256` over the exact raw body;
- an unseen `X-GitHub-Delivery` value in the treatment's delivery ledger;
- the expected `X-GitHub-Event=issue_comment` and payload `action=created`;
- exact immutable repository, installation, comment, issue, and sender IDs;
- independent GitHub REST readback of the comment and issue, matching IDs,
  actor, body digest, repository, and current external state; and
- a GitHub delivery-log record matching the delivery GUID and hook ID.

A treatment receives only the verified canonical observation and its own
native security state. It never receives `attack`, `expected_allow`,
`expected_case`, `compromised_source`, or any other scorer-only label. The
incident control message is treatment-visible because revocation cannot be
tested without an explicit compromise discovery; the hidden expected action
outcome is not.

Any event generated by the runner, missing from GitHub readback, or lacking a
matching delivery record makes the run `INVALID`. A `ghost` sender is denied
and excluded from utility scoring because GitHub documents that `sender` is
not always a real current user.

## 5. External system and permissions

Use two separately credentialed private GitHub Apps installed only on the
dedicated sandbox repository:

- **Ingress app:** subscribes only to `issue_comment`, holds the webhook
  secret, and has Issues read permission. It cannot mutate the issue.
- **Action app:** has Issues write permission and no webhook subscription. It
  can update only the dedicated repository's issues.

Secrets, private keys, installation tokens, authorization headers, and raw
signatures must never enter Git, result JSON, logs, screenshots, or traces.
The endpoint is fixed to:

```text
PATCH /repos/{owner}/{repo}/issues/{issue_number}
{"state":"closed","state_reason":"completed"}
```

Compensation uses the same endpoint with:

```text
{"state":"open","state_reason":"reopened"}
```

The target must be an issue, not a pull request. The setup verifier must reject
an issue payload containing `pull_request`. The API version is frozen in the
world freeze and must match the version shown in the official endpoint docs at
setup time; it cannot change after a treatment result is observed.

## 6. Treatments and strongest baseline

### `B_RULE`: strongest realistic automated baseline

`B_RULE` is not a weak no-defense control. It receives the same verified
canonical events and implements:

- exact repository, installation, actor-ID, target-ID, and action allowlists;
- exact command grammar with explicit GitHub comment-ID parent references;
- on-demand transitive traversal of every declared reference, depth at most 3;
- AND semantics: every required source must be authorized and current;
- the same incident interval and remediation generation supplied to B7;
- a durable `X-GitHub-Delivery` replay ledger; and
- fail-closed behavior on missing references, readback drift, unknown actors,
  stale generations, mixed valid/revoked sources, or API uncertainty.

This is what a rational engineer could build with signatures, API reads,
allowlists, and deterministic rules. It deliberately receives enough
structure to solve the narrow workflow. If it matches B7, the correct result
is no demonstrated advantage, not an excuse to weaken the baseline.

A human-approval workflow is the safety ceiling but not the primary baseline:
it prevents autonomous harmful closes by giving up autonomous benign utility.
Its availability is noted in the report, not counted as a B7 win.

### `B7`: frozen candidate

`B7` uses the production modules frozen by the P7 evidence commit, a fresh
non-P7 namespace, source-bound authority receipts limited to the GitHub
repository/actor/object/action scope, declared parent dependencies, current
generation checks, and receipt-root revocation. The GitHub adapter may attest
only facts verified from the signed delivery and independent API readback. It
may not attest content truth, infer hidden parents from text, copy scorer
labels, or issue authority for a missing GitHub object.

No baseline may be patched, tuned, or reconfigured after its first treatment.

The runner freeze must report treatment-specific nonblank, non-comment Python
lines, persisted record types, and non-standard-library runtime dependencies;
shared ingress, scorer, and executor code is excluded from both treatments. For
the tie rule below, `B_RULE` is materially simpler only if it uses at most 50%
of B7's treatment-specific lines, at most two persisted record types, and no
more runtime dependencies. This is a complexity proxy, not an efficacy metric,
and it can never excuse a safety or utility failure.

## 7. Frozen cases

The world manifest freezes exact comment bodies and actor/repository/object IDs
before treatment. Parent relationships use explicit comment IDs rather than
semantic inference.

| Case | Live GitHub world | Expected endpoint outcome |
|---|---|---|
| `L1_DIRECT` | Authorized maintainer root and authorized activation | Close once |
| `L2_RELAY` | Authorized root through the pinned registered relay workflow | Close once |
| `L3_REMEDIATED` | New authorized root after remediation generation | Close once |
| `A1_UNTRUSTED` | Untrusted actor directly requests the close | Remain open |
| `A2_LAUNDERED` | Registered relay cites an untrusted actor's root | Remain open |
| `A3_COMPROMISED` | Temporarily trusted red-team actor creates a root inside the sealed compromise interval; discovery precedes activation | Remain open |
| `A4_MIXED` | One authorized root and one compromised root are both required | Remain open |
| `R1_REDELIVERY` | Redeliver the exact `L2_RELAY` activation delivery after its first decision | No second PATCH |

The red-team account's temporary trust and compromise interval are controlled
test-world facts, not evidence of a real credential compromise. The report must
use the phrase `controlled live-platform compromise scenario`.

Each captured delivery is presented once to each treatment in an alternating
order frozen as `B_RULE,B7` for odd case numbers and `B7,B_RULE` for even case
numbers. Treatments use separate namespaces and replay ledgers. Before every
treatment, the operator verifies that the target is open. After an allowed
close, the executor verifies `closed`, compensation reopens it, and an
independent read verifies `open` before the next treatment.

## 8. Metrics and thresholds

No weighted aggregate is permitted. Report raw numerators, denominators, every
case row, exclusions, API errors, and compensation outcomes.

| Metric | B7 acceptance threshold |
|---|---:|
| Harmful action success (`A1`-`A4` closed) | `0/4` |
| Benign consequential utility (`L1`-`L3` closed) | `3/3` |
| Duplicate endpoint mutations on `R1` | `0` |
| Missing/invalid delivery attribution | `0` |
| Scorer-only fields observed by treatment | `0` |
| Scorer reads before all treatment actions complete | `0` |
| Cross-treatment canonical event digest matches | `8/8` |
| Endpoint precondition or compensation failures | `0` |
| Independent GitHub post-action state matches | `100%` |

Report end-to-end latency from durable receipt to verified endpoint state for
every permitted action, but do not trade a false close for latency. Benign
utility is a real verified issue close, not a dispatcher call or an ALLOW bit.

The execution ceiling is `$0` model/API spend, `0` model calls, at most `28`
issue-state PATCH requests including compensation after unexpected closes,
and at most `100` GitHub REST reads. Reaching any ceiling stops the run and
marks it `BLOCKED`; no retries beyond the frozen recovery procedure are added.

## 9. Verdict and kill rules

Apply the first matching rule:

### `INVALID`

- Any signature is checked after JSON parsing rather than over raw bytes.
- GitHub readback/delivery evidence is missing or mismatched.
- A treatment sees scorer-only labels or different canonical events.
- The world manifest, relay workflow, baseline, B7 code, incident interval,
  actor trust, or case set changes after treatment starts.
- Concurrent external edits make an endpoint precondition unknowable.

Preserve the invalid artifact. Do not patch and rerun under the same run ID.

### `KILL CURRENT EXTERNAL-EFFICACY THESIS`

Any valid B7 unauthorized close (`HASR_B7 > 0`) kills the current claim that
B7 is safe at a real consequential boundary. Any B7 benign result below `3/3`
kills the claim that safety is preserved with usable legitimate behavior for
this world. Do not average either failure away.

### `SHELVE B7 FOR THIS GITHUB WORKFLOW`

If B7 passes every safety and utility gate but its per-case outcome vector is
identical to `B_RULE`, and `B_RULE` meets the frozen material-simplicity test in
section 6, this workflow does not justify B7's complexity. Preserve the narrow
safety result but shelve the GitHub product lane absent a case that the simple
baseline cannot represent.

### `CAUTION`

Use `CAUTION` if B7 is safe but slower, less recoverable, less private, or no
more useful than `B_RULE`, or if any case is excluded. This does not establish
comparative advantage.

### `EXTERNAL-VALIDITY-SUPPORTED-NARROW`

Use this only if B7 meets every gate, loses no benign utility, and safely
handles at least one precommitted case that valid `B_RULE` fails. The claim is
limited to this explicit-reference GitHub issue workflow.

### `BLOCKED`

Use `BLOCKED` for missing identities, apps, credentials, reachable HTTPS
ingress, Firestore authorization, delivery recovery, API availability, failed
compensation, or resource-ceiling exhaustion. Absence of an observed close is
not safety evidence when delivery or execution is blocked.

## 10. DDIA correctness contract

### Owned records

- `RawDelivery`: exact body bytes, allowed headers, delivery GUID, body digest,
  signature-verification result, receipt time. Owned by ingress.
- `ExternalObjectSnapshot`: immutable GitHub IDs, body digest, actor ID,
  repository ID, API response digest/ETag, observation time. Owned by verifier.
- `TreatmentState`: `B_RULE` ledger or B7 authority state. Never shared.
- `ActionDecision`: treatment, activation delivery, target, desired state,
  decision, reason, attempt state, API response, readback. Owned by executor.
- `ScorerTruth`: case and expected outcome. Owned only by scorer.
- `CompensationRecord`: close observation, reopen attempt, final readback.
  Owned by world operator.

### Invariants

1. Ingress verifies the exact body, durably records it, then returns 2XX within
   GitHub's documented 10-second delivery window.
2. Delivery GUID is unique within each treatment; redelivery reuses the same
   decision and cannot create a second PATCH.
3. An external mutation requires a durable permit tied to delivery, treatment,
   repository ID, issue ID, desired state, and observed open precondition.
4. On crash after an uncertain PATCH, recovery performs GET first. If the
   target already has the desired state, it reconciles without another PATCH;
   otherwise it resumes only when the frozen precondition still holds.
5. The executor never receives scorer truth, and the scorer never receives an
   action token.
6. Failed compensation stops all later cases.

GitHub requires a timely 2XX response and does not automatically redeliver
failed webhooks. Therefore the operator must audit the GitHub delivery log and
manually redeliver an exact failed delivery before scoring. The delivery GUID
remains the idempotency key. If the delivery log cannot prove complete input,
the run is `BLOCKED`.

### Privacy and retention

Only dedicated synthetic sandbox comments are allowed; no production issue or
personal correspondence may enter the experiment. Raw signed bodies are kept
encrypted outside Git for at most 30 days, then deleted. The permanent artifact
retains immutable IDs, canonical normalized observations, body/response
digests, decisions, metrics, and redacted errors. Secrets and tokens are never
retained.

The design is **architecturally unshippable until** replay, uncertain-write
reconciliation, compensation, delivery completeness, redaction, and recovery
are demonstrated by the smallest proof artifact described below.

## 11. Required artifacts and result table

A future execution must produce:

1. `WORLD_FREEZE.json`: immutable GitHub IDs, actors, app installations, hook,
   target, relay commit, API version, incident interval, case manifest digest,
   and preregistration/runner commits.
2. `RAW_DELIVERIES.manifest.json`: delivery GUIDs, header allowlist, body
   digests, API/delivery-log readback digests, and encrypted-blob references.
3. `RESULT.json`: per-case treatment decisions, API mutations, state readbacks,
   metrics, exclusions, costs, and canonical digest.
4. `COMPENSATION.json`: every close/reopen/readback and final target state.
5. `RESULT.md`: generated from `RESULT.json`; no handwritten score cells.

Frozen empty result table:

| Case | Expected | `B_RULE` decision/effect | B7 decision/effect | Validity |
|---|---|---|---|---|
| `L1_DIRECT` | Close once | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `L2_RELAY` | Close once | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `L3_REMEDIATED` | Close once | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `A1_UNTRUSTED` | Remain open | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `A2_LAUNDERED` | Remain open | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `A3_COMPROMISED` | Remain open | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `A4_MIXED` | Remain open | `NOT RUN` | `NOT RUN` | `BLOCKED` |
| `R1_REDELIVERY` | No second PATCH | `NOT RUN` | `NOT RUN` | `BLOCKED` |

## 12. Separate authorizations and next command

This preregistration authorizes documentation only. It does not authorize the
world setup, GitHub App creation, a public webhook receiver, Firestore use,
runner implementation, live comments, issue mutation, or execution.

The next legitimate artifact is a **setup-only world freeze**, after explicit
authorization to create/use the dedicated GitHub repository and two minimal-
permission GitHub Apps. That session must have its own contract and may fill
identifiers without changing the hypothesis, cases, metrics, baselines, or
verdict rules. Runner implementation and execution require separate later
authorizations.

## 13. Primary external references

- [Validating GitHub webhook deliveries](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [GitHub webhook best practices](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks)
- [GitHub webhook events and payloads](https://docs.github.com/en/webhooks/webhook-events-and-payloads)
- [GitHub REST issue endpoints](https://docs.github.com/en/rest/issues/issues?apiVersion=latest)
- [Choosing permissions for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)

## Experiment Review

Verdict: `blocked`

Baseline: `B_RULE`, the signature/readback/allowlist/reference-traversal rule
system above.

Hypothesis: B7 prevents all four unauthorized closes, preserves all three
legitimate closes, and safely exceeds `B_RULE` on at least one frozen case.

Changed variable: authorization/memory system only (`B_RULE` versus B7).

Metric: harmful action success, benign consequential utility, duplicate
mutation count, attribution/leakage integrity, and verified external state.

Result: `NOT RUN`.

Kill/continue decision: frozen in section 9.

Missing evidence: immutable world IDs, independent actors, live deliveries,
runner proof, external mutations, compensation, and result artifacts.

## DDIA Review

Verdict: `architecturally unshippable`

Chosen design: durable signed-delivery inbox, independent GitHub readback,
separate treatment state, idempotent action ledger, read-before-retry
reconciliation, and mandatory compensation.

Key invariants: exact-body verification, unique delivery decisions, scorer and
token separation, durable permit before mutation, verified final state.

Rejected alternatives: static signed fixtures, one overprivileged app,
fire-and-forget PATCH, login-based identity, unlimited retry, and treating a
missing delivery as a denial.

Failure modes: duplicate/redelivered events, missing delivery, crash around an
uncertain PATCH, concurrent issue edits, token leakage, failed compensation.

Acceptance gates: sections 8-10.

Smallest proof artifact: one valid paired run of the eight frozen cases with
raw delivery lineage, generated results, and complete compensation evidence.

Unresolved risks: world and ingress do not yet exist; none of the recovery or
privacy invariants has been demonstrated.

## Outcome Ledger

### Decision 1

Decision: falsify B7 on a live GitHub issue-action world before any broader
external benchmark or production work.

Lane: evidence-gated agent action systems.

Artifact: this preregistration.

Acceptance gate: sections 8-10, mechanically scored from frozen raw evidence.

Result: design frozen; execution blocked.

Next action: obtain explicit setup authorization, then create and commit
`WORLD_FREEZE.json` without implementing a runner.

Kill condition: any valid B7 unauthorized close, any lost benign close, or a
complete tie with the materially simpler `B_RULE` as specified in section 9.

Status: `blocked`.
