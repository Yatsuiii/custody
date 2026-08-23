# B7 Production-Equivalence Test Plan

Status: `FROZEN-DESIGN-DRAFT — DO NOT IMPLEMENT OR EXECUTE`

## Experiment review

Verdict: `VALID-DESIGN`, pending implementation.

Baseline: frozen B7 outcomes from Gate 1B-R3 (`f3eb51c`), Gate 1C-R3
(`437fc2a`), and durable safety outcomes from E2H-R1E (`56c4198`).

Hypothesis: moving the already validated B7 semantics from isolated research
adapters into production Custody APIs preserves every frozen safety, utility,
selectivity, generation, cross-agent, and durable-process outcome.

Single changed variable: mechanism implementation boundary—research adapter
versus production `custody/` modules. Source objects, receipts, PolicyKeys,
generations, caps, parent graphs, transform classes, revocation selectors,
actions, and expected outcomes remain frozen.

Metrics: exact per-case action outcomes, dependency/root recall, utility,
false-ACT counts, historical rewrites, durable safety, reproducibility, and
leakage checks. No weighted aggregate.

Kill condition: any unsafe allow, missing required parent/root/dependency,
historical authority rewrite, legacy ACT, scorer leakage, test-side authority
calculation, or inability to exercise the production API.

Artifact lineage: result records production commit, design-file digests,
fixture digest, public API/module digests, normalized traces, test command, and
Firestore namespace when the durable slice is authorized. It does not import
or execute `research/` runners.

## Production interfaces under test

Names may change only for a clearly better existing-project name; semantics may
not change:

```text
AdmissionGate.admit_source(source_event, output)
AdmissionGate.admit_identity(parent_id, output)
AdmissionGate.admit_registered(transform_ref, parent_ids, output)
AdmissionGate.admit_freeform(parent_ids, output)
AuthorityGateway.execute(action_request, cited_record_ids, dispatcher)
RevocationController.revoke_receipt_roots(revocation_id, root_keys)
AuthorityStore.read_record/read_dependencies/read_current_policy/read_root_state
```

`CustodyMemoryService` and adapters call these same public interfaces. The test
does not instantiate internal evaluator classes or inject effective caps.

## External-world fixture

The local suite uses immutable, pre-signed source event fixtures under
`tests/fixtures/b7/`:

- source-object claims;
- P2 receipts;
- issuer public key/trust configuration;
- PolicyKey snapshots/generations; and
- transport envelopes.

The fixture carries no expected allow/deny, attack class, or scorer truth.
Expected outcomes live in a separate assertion table loaded only after all
production actions finish.

Tests may mutate presented bytes to create forgery, wrong-object, wrong-scope,
wrong-revision, stale-generation, and replay inputs. Tests may not re-sign those
mutations, compute an effective cap, select a root from a malicious label, or
pass an expected decision to production.

For P7, static fixtures are insufficient: the deployed source service must emit
the signed event at runtime. The live runner may request an owned object and
observe the result, but may not mint the receipt.

## Frozen cases

| ID | Construction through production public APIs | Required result |
|---|---|---|
| A1 | attacker-controlled tool echo from a relay, no source receipt | action DENY; false ACT 0 |
| A2 | legitimate source-owned object plus valid P2 forwarded by the same relay | action ALLOW; benign utility 1 |
| B | mutate issuer signature on an otherwise identical receipt | DENY `RECEIPT_SIGNATURE_INVALID` |
| C | present a valid receipt with a different source object/root | DENY object/root mismatch |
| D | present `payroll.read` or another valid receipt at `export.send` | DENY scope/PolicyKey mismatch |
| E | advance exact PolicyKey generation before action | DENY stale generation; envelope unchanged |
| F | replay a valid unrelated receipt for another source object/record | DENY receipt/root mismatch |
| G | admit IDENTITY over one current valid parent | bounded ALLOW; exact support preserved |
| H | invoke a configured REGISTERED transform over current valid parents | bounded ALLOW; all parent and transform dependencies present |
| I | produce FREEFORM output over an ACT parent | INFORM retained; consequential action DENY |
| J | REGISTERED over one clean and one missing/invalid/stale required parent | DENY; clean parent cannot wash invalid support |
| K | forward valid support agent A -> agent B through configured operations | bounded ALLOW; no new root receipt |
| L | revoke a required root, then evaluate a cross-agent descendant | DENY `REVOKED_AUTHORITY_ROOT` |
| M1 | selectively revoke two authenticated bad RootKeys | every bad descendant DENY |
| M2 | evaluate pre-compromise sibling | ALLOW |
| M3 | evaluate independently issued post-remediation replacement | ALLOW |
| M4 | evaluate unrelated receipt/root | ALLOW |
| M5 | copy revoked receipt/root evidence to a new record | DENY; no escape |
| N | commit records/dependencies, terminate W/P/G, reconstruct with fresh processes from Firestore | exact parents/support/dependencies recalled; current legitimate action ALLOW |
| O | gateway reads candidate, revocation commits at the barrier, gateway performs final authoritative check | DENY; no post-revocation false ACT |
| P | kill writer during transaction; inspect state; evaluate action; retry with fresh writer | no partial authoritative record, immediate DENY, duplicate envelopes 0, history rewrites 0; recovery duration reported separately |

Cases A–M run against deterministic local and fake-store ports. N–P additionally
run against an isolated real Firestore namespace with independent executable
processes after explicit execution authorization.

## Exact metrics and gates

| Metric | Denominator / target |
|---|---|
| `tool_echo_false_act` | A1: 0/1 |
| `benign_relay_utility` | A2: 1/1 |
| `forgery_binding_false_act` | B–F: 0/5 |
| `identity_utility` | G: 1/1 |
| `registered_utility` | H: 1/1 |
| `freeform_false_act` | I: 0/1 |
| `mixed_required_parent_false_act` | J: 0/1 |
| `cross_agent_utility` | K: 1/1 |
| `cross_agent_revoked_false_act` | L: 0/1 |
| `affected_revocation_recall` | every M1 bad descendant denied / all expected bad descendants |
| `selective_utility` | M2–M4: 3/3 |
| `revocation_escape_false_act` | M5: 0/1 |
| `direct_parent_recall` | exact expected tuples for G–L / all G–L records |
| `support_root_recall` | exact expected sets for G–L / all G–L records |
| `authority_dependency_recall` | exact expected sets for G–L / all G–L records |
| `historical_rewrite_count` | 0 across every envelope/policy change/revocation |
| `legacy_false_act` | 0 across all pre-B7 fixtures |
| `post_restart_recall` | N: all records/dependencies reconstructed |
| `action_revocation_race_false_act` | O: 0/1 |
| `post_kill_partial_authoritative_records` | P: 0/1 |
| `immediate_post_kill_false_act` | P: 0/1 |
| `duplicate_authoritative_envelopes` | N–P: 0 |
| `recovery_completed_within_90_seconds` | P: report 0/1 or 1/1 unchanged; not folded into safety |
| `normalized_trace_reproducibility` | two clean runs: 1/1 |
| `scorer_reads_before_actions_complete` | 0 |

### Equivalence supported

All required ALLOW/DENY outcomes match, all recall sets are exact, unsafe
numerators are zero, historical rewrites and contradictory envelopes are zero,
legacy ACT is zero, normalized traces reproduce, and leakage checks pass.

The 90-second recovery result is reported separately. A miss preserves
`SAFETY-SUPPORTED / RECOVERY-LIVENESS-LIMITED`; it prevents a bounded-recovery
claim but does not turn zero false ACTs into a security failure.

### Equivalence failed

Any required legitimate A2/G/H/K/M2–M4 ALLOW is lost while safety remains
closed. Report the exact utility/selectivity loss; do not average it away.

### Security kill

Any A1/B–F/I/J/L/M1/M5/O/P unsafe ALLOW, missing required dependency, copied
receipt escape, stale-generation allow, history rewrite, contradictory envelope,
or legacy ACT is a production-integration `KILL` pending root-cause review.

### Invalid

Any scorer/expected-field leakage, research-runner import, test-side authority
calculation, unhandled runner exception before final traces, production API
bypass, or post-result patch under the same run identity invalidates the run.

## No self-fulfilling tests

Forbidden test patterns:

- reimplementing `min(NONE, INFORM, ACT)` to feed an expected cap into
  production;
- computing support closure in a helper and passing it to admission;
- constructing a `VerifiedReceipt` or `AdmissionEnvelope` directly;
- selecting revocation roots from case labels or expected affected records;
- setting `transform_class=REGISTERED` on a generic caller payload;
- patching current policy/revocation reads to return expected decisions;
- importing classes/functions from Gate 1B, Gate 1C, E2D–E2H, or another
  research runner.

Allowed test behavior:

- serve source objects and immutable signed events;
- call public source/transform/revocation/action interfaces;
- impose deterministic process barriers and failures;
- inspect persisted documents, decisions, and external dispatcher calls; and
- score final traces against a separately held expected table.

## Leakage/static audits

Before treatment:

1. recursively scan runtime fixtures and production constructor arguments for
   forbidden scorer/attack keys;
2. assert no treatment object references the expected-outcome structure;
3. scan the production-equivalence test for imports from `research`;
4. scan test helpers for envelope/effective-cap/root-closure construction; and
5. confirm the relay fixture has no issuer private key.

After every action finalizes, enable the scorer and record its first read.

## Commands, outputs, and cost boundary

Planned local proof commands after implementation authorization:

```text
python -m unittest tests.test_b7_production_equivalence
python -m unittest discover -s tests
ruff check custody tests scripts live
```

The real Firestore N–P command must use an isolated explicit namespace and
fresh W/P/G subprocesses, preserve the E2H cleanup discipline, and never touch
shipping collections. No model, embedding, benchmark, or paid API call is part
of production equivalence.

Canonical outputs:

- `proof-out/b7-production-equivalence.json`;
- `proof-out/b7-production-equivalence.md`;
- normalized action/dependency/revocation traces; and
- a separate recovery-liveness section.

No command in this plan is authorized by this design session.
