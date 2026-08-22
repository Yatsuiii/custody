# E2F Policy Admission TOCTOU

Verdict: **TOCTOU-ROBUST**.

Canonical result digest: `f5d0afba0d5ed73d60da11c64607fec92ace128c2f4e678d7633f50483531dab`.

Selected semantics: `S3_ACTION_CURRENT`.

## Variant outcomes
- `E2F_A`: `ALLOW`; reason `CURRENT_GENERATION_MATCH`
- `E2F_B`: `DENY`; reason `POLICY_GENERATION_MISMATCH`
- `E2F_C`: `DENY`; reason `POLICY_GENERATION_MISMATCH`
- `E2F_D`: `DENY`; reason `POLICY_GENERATION_MISMATCH`
- `E2F_E`: `DENY`; reason `POLICY_GENERATION_MISMATCH`
- `E2F_F`: `DENY`; reason `POLICY_GENERATION_MISMATCH`

## Metrics
- `stale_admission_attempts`: 3/3 (value `1.0`)
- `stale_admissions_accepted`: 3/3 (value `1.0`)
- `stale_act_permits`: 0/5 (value `0`)
- `aba_false_accepts`: 0/1 (value `0`)
- `retry_policy_conflicts`: 1/1 (value `1`)
- `duplicate_envelope_count`: 0/1 (value `0`)
- `action_generation_mismatches`: 1/1 (value `1`)
- `historical_rewrite_count`: 0/6 (value `0`)
- `audit_trace_complete`: 6/6 (value `1.0`)
- `deterministic_replay_match`: 1/1 (value `1`)

## Integrity

PLAN immutable: `True`.

Ground-truth leakage guard passed: `True`.

Historical rewrite count: `0`.

This logical SQLite experiment makes no production atomicity or readiness claim.

## Next gate

Any further experiment requires separate preregistration and authorization.
