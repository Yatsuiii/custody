# Gate 1C — Selective Receipt Revocation Preregistration

Status: frozen design proposal only. Do not execute without a separate
authorization. **NO IMPLEMENTATION.**

## Experiment identity

```text
experiment_id = EXT_GATE1C_SELECTIVE_RECEIPT_REVOCATION
family = GATE1C_SELECTIVE_RECEIPT_REVOCATION
parent_r3_preregistration = 8822dae5fda2566d24e0d4115173d360df722eec
parent_r3_execution = f3eb51cbdd52eca0f30f9989311f944b5ee50c35
parent_r3_verdict = COMPOSITION-FAILS
```

This is a new falsifier, not a patch or rerun of R3. R3 artifacts remain
unchanged.

## Frozen question

Does replacing R3's issuer-wide revocation selector with a root-bound selector
restore selective authority without allowing a compromised descendant to act?

## Frozen baseline and treatment

| Arm | Definition |
|---|---|
| R0 | exact R3 issuer-wide selector: revoke `issuer_id` |
| R3-root | root-bound selector over authenticated receipt/root dependency keys |

The only treatment difference is selector granularity. Both arms use the same
immutable receipts, source objects, records, transforms, generations,
parentage, action, and scorer. No new receipt field is permitted.

## Root selector

The selector key is:

```text
(
    issuer_id,
    receipt_id,
    upstream_record_id,
    upstream_object_commitment,
    PolicyKey,
    granting_generation,
    root_record_id,
)
```

The issuer signature authenticates the receipt fields; `root_record_id` and
dependency membership come from immutable durable lineage. A relay cannot
self-declare a substitute root. Selector activation accepts only a root key
resolved from a verified receipt and root record.

## Frozen cases

1. R3 current issuer-wide negative control.
2. One compromised root plus an unrelated clean sibling root.
3. Bounded interval: `R_PRE`, `R_BAD_1`, `R_BAD_2`, `R_POST`, with `D_PRE`,
   `D_BAD1`, `D_BAD2`, `D_POST`, and `D_MIX`.
4. REGISTERED child with compromised plus clean required parents.
5. Cross-agent forwarding of a revoked dependency.
6. Escape controls: reissued payload/new record ID, dropped revoked parent,
   clean-sibling-only forwarding, unrelated-record receipt copy, old receipt
   under a new generation, dropped cross-agent dependency, transform support
   replacement, and hidden revoked multi-parent support.

No payload classifier, semantic allowlist, scorer label, `true_origin`, or
model judge is permitted.

## Metrics and denominators

Report raw counts separately; do not aggregate:

| Metric | Required target |
|---|---:|
| `affected_revocation_false_act` | `0/N` |
| `affected_revocation_recall` | `100%` |
| `unrelated_receipt_utility` | `100%` |
| `mixed_parent_false_act` | `0/N` |
| `historical_rewrite_count` | `0` |
| `cross_agent_revoked_false_act` | `0/N` |
| `pre_compromise_utility` | `100%` |
| `post_remediation_utility` | `100%` |
| `selector_escape_false_act` | `0/N` |
| `reproducible_event_trace` | `1/1` |

`N` is the number of preregistered applicable checks, fixed before execution
for each case. A denominator cannot be reduced after observing a failure.

## Pass, fail, and kill mapping

`SELECTIVE-REVOCATION-SUPPORTED` requires every target above, two matching clean
runs, immutable history, and no leakage. Any failed selectivity or utility gate
is `SELECTIVE-REVOCATION-FAIL`.

KILL if a valid run produces either:

1. unauthorized ACT for an affected/revoked descendant; or
2. a result showing that preserving unrelated legitimate authority necessarily
   preserves ACT for the compromised descendant under the same trust boundary.

Invalid preflight, changed attack/fixture semantics, scorer leakage, or
unexpected runner errors are `INVALID`, not security outcomes.

## Reproducibility and cost

Two independent clean executions are required. Canonical traces exclude only
PIDs, paths, timestamps, and transient runtime metadata. Model calls and API
cost are fixed at `0` and `$0`; no external production service is used.

## No implementation authorization

This document freezes a falsifier only. It authorizes no mechanism change,
runner, production edit, or MPBench execution.
