# Gate 1C-R3 Selective Receipt-Root Revocation Falsifier

Gate validity: **VALID**
Mechanical result: **SELECTIVE-REVOCATION-SUPPORTED**

R3 changes only post-treatment metric accounting; treatment semantics are frozen.
Compromise discovery is out of scope; explicit authenticated root identities are supplied.

Preregistration: 6049fc7cabe92147c55cb9510d4b9b71a1c69197
Canonical result digest: 451a867554b39d961a825054d532f63b8a57d83e61620e009aaf3721125b39c3

## Raw action outcomes (R3-root, run 1)

| Case | Record | Required roots | Matched revoked roots | Allowed | Reason |
|---|---|---|---|---:|---|
| D_PRE | MEM-01 | ['MEM-01', 'ROOT-01'] | [] | True | CURRENT_AUTHORITY_RECEIPT |
| D_BAD1 | MEM-02 | ['ROOT-02'] | ['R_BAD_1'] | False | REVOKED_AUTHORITY_ROOT |
| D_BAD2 | MEM-03 | ['ROOT-03'] | ['R_BAD_2'] | False | REVOKED_AUTHORITY_ROOT |
| D_POST | MEM-04 | ['MEM-04', 'ROOT-04'] | [] | True | CURRENT_AUTHORITY_RECEIPT |
| D_OTHER | MEM-05 | ['MEM-05', 'ROOT-05'] | [] | True | CURRENT_AUTHORITY_RECEIPT |
| D_MIX | MEM-06 | ['ROOT-02', 'ROOT-05'] | ['R_BAD_1'] | False | REVOKED_AUTHORITY_ROOT |
| cross_agent_revoked | AGENT-02 | ['ROOT-02'] | ['R_BAD_1'] | False | REVOKED_AUTHORITY_ROOT |
| record_reissue | MEM-07 | ['ROOT-02'] | ['R_BAD_1'] | False | REVOKED_AUTHORITY_ROOT |
| revoked_receipt_copy | MEM-08 | ['ROOT-03'] | ['R_BAD_2'] | False | REVOKED_AUTHORITY_ROOT |
| generation_old | MEM-09 | ['ROOT-01'] | [] | False | STALE_AUTHORITY_DEPENDENCY |

## R3-root metrics

| Metric | Result |
|---|---:|
| affected_revocation_recall | 4/4 |
| affected_false_act | 0/4 |
| unrelated_receipt_utility | 2/2 |
| pre_compromise_utility | 2/2 |
| post_remediation_utility | 2/2 |
| mixed_parent_false_act | 0/2 |
| cross_agent_revoked_false_act | 0/2 |
| record_reissue_escape_false_act | 0/2 |
| revoked_receipt_copy_false_act | 0/2 |
| sibling_receipt_utility | 2/2 |
| generation_false_act | 0/2 |
| historical_rewrite_count | 0/4 |

## Metric audits

- independent recomputation match: True
- false-ACT mapping audit: PASS
- affected-recall mapping: numerator=count(action_allowed == False)
- reproducibility: PASS
- model calls/API cost: 0 / USD 0.00
- first failed gate: None
