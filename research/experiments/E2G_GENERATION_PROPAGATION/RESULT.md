# E2G Generation Propagation Result

Verdict: **GENERATION-COMPOSITION-ROBUST**

This report is generated from `result.json`; it does not select the verdict.

## Variant outcomes

- E2G_A: R_OLD=DENY
- E2G_B: C_REG=DENY
- E2G_C: C_AGENT=DENY, C_GRANDCHILD=DENY
- E2G_D: C_MIX=DENY
- E2G_E: C_FREE=DENY
- E2G_F: C_BEFORE=ALLOW, C_BEFORE=DENY
- E2G_G: C_ABA=DENY
- E2G_H: C_NEW=ALLOW
- UNRELATED_POLICY_CONTROL: R_CLEAN=ALLOW, C_NEW=ALLOW

## Metrics

| Metric | Result |
| --- | ---: |
| `direct_stale_root_denied` | 1/1 (1.0) |
| `fresh_child_stale_parent_false_act_permits` | 0/6 (0.0) |
| `cross_agent_stale_dependency_preserved` | 2/2 (1.0) |
| `mixed_parent_stale_dependency_preserved` | 1/1 (1.0) |
| `freeform_support_preserved` | 1/1 (1.0) |
| `preexisting_child_invalidated_after_parent_policy_change` | 1/1 (1.0) |
| `aba_dependency_false_accepts` | 0/1 (0.0) |
| `legitimate_refresh_allows` | 1/1 (1.0) |
| `unrelated_policy_update_preserved` | 1/1 (1.0) |
| `direct_parent_recall` | 8/8 (1.0) |
| `authority_dependency_recall` | 8/8 (1.0) |
| `historical_rewrite_count` | 0/11 (0.0) |
| `audit_trace_complete` | 9/9 (1.0) |
| `deterministic_replay_match` | 1/1 (1.0) |

## Integrity

- Ground-truth leakage: `True`.
- PLAN immutable: `True`.
- Deterministic replay: `True`.
- Historical rewrites: `0/11`.
- First failed invariant: `None`.

## Limitation

This deterministic model does not establish production catalog/cache atomicity, distributed persistence, or gateway integration.

## Next gate

If the frozen gates pass, the next authorized research step is a separate persistence/integration experiment. It is not implemented here.
