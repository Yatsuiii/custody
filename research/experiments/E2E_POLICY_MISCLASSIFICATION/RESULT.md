# E2E Policy-Misclassification Result

Final verdict: **POLICY-FAIL-CONTAINED**.
Canonical result digest: `d8811ff7d3bcce9e046682f6b3b9636112755f98de8dcb57debd9449b9840f1d`.

The result is generated from `result.json`; the report does not select the verdict.

## Control and treatment

Control uses RELAY; treatment changes only vendor_lookup/R1 to ORIGIN.

Treatment direct export result: `ALLOW`.

Treatment post-recovery false ACT permits: `0/5`.

## Metrics
- `misclassified_root_act_permit`: 1/1 (value `1.0`)
- `propagated_false_act_permits`: 3/3 (value `1.0`)
- `affected_descendant_recall_after_revoke`: 5/5 (value `1.0`)
- `unaffected_revision_preserved`: 2/2 (value `1.0`)
- `unaffected_scope_preserved`: 5/5 (value `1.0`)
- `freeform_cap_contained`: 1/1 (value `1.0`)
- `historical_policy_rewrite_count`: 0/9 (value `0`)
- `post_revoke_false_act_permits`: 0/5 (value `0`)
- `repair_collateral_count`: 0/5 (value `0`)

## Recovery

Selected roots: `['e2e-r1-root']`.

Affected closure: `['e2e-r1-root', 'e2e-r1-registered', 'e2e-r1-freeform', 'e2e-r1-cross-agent', 'e2e-r1-mixed']`.

Historical rewrite count: `0`.

## First failed security property

`misclassified_root_act_permit`.

## Leakage and limitations

Ground-truth leakage check passed: `True`.

This is a logical Architecture A experiment, not a production-readiness or memory-poisoning claim.

## Next gate

Only an explicitly authorized follow-up research experiment may proceed; no mitigation or production integration is authorized by this result.
