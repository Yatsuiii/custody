# E2H Durable Authority Integration

Verdict: **INTEGRATION-FAIL-CONTAINED**

Preregistration: `ce5c8b172d70e537c0c60e3bced9b6670f7bb92b`; PLAN immutable: `True`.

## Experiment review

Baseline: E2G logical G3 model.
Hypothesis: durable process boundaries preserve dependency freshness and fail closed.
Changed variable: Firestore persistence plus independent W/P/G processes.

## Metrics

| Metric | Result |
|---|---:|
| `durable_control_allows` | 1/1 (1.000) |
| `post_restart_dependency_recall` | 2/2 (1.000) |
| `post_policy_change_false_act_permits` | 0/5 (0.000) |
| `partial_admission_false_act_permits` | 0/1 (0.000) |
| `gateway_race_false_act_permits` | 0/1 (0.000) |
| `stale_cache_false_act_permits` | 0/1 (0.000) |
| `duplicate_authoritative_envelopes` | 0/1 (0.000) |
| `retry_conflicts_correct` | 1/1 (1.000) |
| `multi_parent_recall_after_restart` | 1/1 (1.000) |
| `authority_dependency_recall_after_restart` | 2/2 (1.000) |
| `legitimate_refresh_allows` | 1/1 (1.000) |
| `historical_rewrite_count` | 0/6 (0.000) |
| `fail_closed_missing_state` | 5/5 (1.000) |
| `audit_trace_complete` | 8/8 (1.000) |
| `post_kill_partial_authoritative_records` | 0/1 (0.000) |
| `immediate_post_kill_false_act_permits` | 0/1 (0.000) |
| `recovery_contention_events` | 3/1 (3.000) |
| `recovery_contention_false_act_permits` | 0/3 (0.000) |
| `recovery_completed_within_bound` | 0/1 (0.000) |
| `recovery_duplicate_envelopes` | 0/1 (0.000) |
| `recovery_historical_rewrites` | 0/1 (0.000) |
| `reproducible_event_trace` | 1/1 (1.000) |

## Integrity

Canonical result digest: `857bc75833067612ff3f8b77d49d59728dfd4c5adfc3c9ed554ff1c5a25280ae`
Ground-truth leakage scan: `[]`
Cleanup complete: `True`

No production Custody code or shipping collections were modified.
