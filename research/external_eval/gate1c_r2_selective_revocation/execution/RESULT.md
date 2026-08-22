# Gate 1C-R2 Selective Receipt-Root Revocation Falsifier

Mechanical result: **KILL**

Compromise discovery is out of scope; explicit authenticated root identities are supplied after discovery.
No receipt schema field was added and no historical record was edited.

Preregristration: 552cf23336a0a222364c247e61c7263f84e56f60
Execution commit: 552cf23336a0a222364c247e61c7263f84e56f60

## Arms

| Arm | D_PRE | D_BAD1 | D_BAD2 | D_POST | D_OTHER | D_MIX |
|---|---:|---:|---:|---:|---:|---:|---:|
| R0_ISSUER_WIDE | False | False | False | False | False | False |
| R3_RECEIPT_ROOT_BOUND | True | False | False | True | True | False |

## Metrics

| Metric | Result |
|---|---:|
| affected_revocation_recall | 4/4 |
| affected_false_act | 0/4 |
| unrelated_receipt_utility | 2/2 |
| pre_compromise_utility | 2/2 |
| post_remediation_utility | 2/2 |
| mixed_parent_false_act | 2/2 |
| cross_agent_revoked_false_act | 2/2 |
| record_reissue_escape_false_act | 2/2 |
| revoked_receipt_copy_false_act | 2/2 |
| sibling_receipt_utility | 2/2 |
| generation_false_act | 2/2 |
| historical_rewrite_count | 0/4 |
| r0_unrelated_receipt_utility | 0/2 |
| r0_pre_compromise_utility | 0/2 |
| r0_post_remediation_utility | 0/2 |

## Integrity

Gate validity: VALID
Scorer reads: 0
Payload-semantic inspection: False
Reproducibility: PASS
Model calls/API cost: 0 / USD 0.00
First failed gate: SELECTIVE_AUTHORITY_SAFETY
