# Gate 1C-R3 — Selective Receipt Revocation Preregistration

Status: frozen preregistration only. **NO IMPLEMENTATION and NO EXECUTION in
this session.**

## Identity and lineage

```text
experiment_id = EXT_GATE1C_R3_SELECTIVE_RECEIPT_REVOCATION
family = GATE1C_SELECTIVE_RECEIPT_REVOCATION
parent_r2_preregistration = 552cf23336a0a222364c247e61c7263f84e56f60
preserved_r2_invalid_attempt = 40e33a7c0b75afd4f9e63816caa136368ecd7c1b
parent_gate1c_design = 3b27797aa0fb20d6207ecd3881bbcbabf3580ca2
branch = research/external-gate1c-r3-selective-revocation-falsifier
```

The R3 preregistration SHA is the commit containing these documents and must
be discovered from the repository/remote at execution time. It must not be
copied from a prompt or changed after freezing.

R2 remains preserved as an invalid post-treatment metric-boundary attempt. It
is not patched or rerun, and its emitted `KILL` is not an efficacy conclusion.

## Frozen question and single correction

R3 asks the unchanged Gate 1C question: can authenticated receipt-root
revocation remove compromised-root authority while preserving unrelated,
pre-compromise, and post-remediation authority?

The sole correction is the outcome-to-metric mapping specified in
`METRIC_LIFECYCLE_CONTRACT.md`. It corrects R2's inversion of expected-DENY
false-ACT metrics. It does not modify treatment outputs, RootKeys, selector
semantics, graph, cases, scorer, thresholds, or verdict gates.

## Frozen source and boundary

```text
repository = yedidel/mem-inv-bench
commit = 63f1359d677efbe1a65b982b2a54cabfec97f1e1
attack_context = code/laundering.py::tool_echo
model_calls = 0
api_cost = $0
```

Treatments receive no scorer truth, `true_origin`, compromise labels, case
meaning, or payload-semantic authority signals. Compromise discovery remains
out of scope; only explicit authenticated roots are supplied for revocation.

## Frozen graph, arms, and cases

Use the unchanged `16`-record graph and all Gate 1C cases. Run the same
`R0_ISSUER_WIDE` and `R3_RECEIPT_ROOT_BOUND` arms on the same graph, with the
same alias resolver, RootKey, support closure, generation rules, and historical
immutability checks. No case is added, removed, or made easier.

## Pretreatment gates

Before treatment, R3 must verify the R2 resolver/RootKey gates: `16` records,
`16` unique durable IDs, `5` authenticated roots, five deterministic unique
RootKeys, exactly two selected keys for `R_BAD_1`/`R_BAD_2`, zero mutable
selector members, unchanged P2 schema, no scorer access, and model/API cost
`0`/`$0`.

Any failure is `INVALID` before treatment. No patch-and-continue is allowed.

## Frozen metric mapping and mechanical gates

For every expected-ALLOW utility metric, count `action_allowed == True`.
For every expected-DENY false-ACT metric, count `action_allowed == True` as the
false-ACT numerator. For affected recall, count `action_allowed == False`.
Recompute the entire reported table from raw action traces before applying the
unchanged verdict mapping.

The unchanged raw metrics are:

```text
affected_revocation_recall
affected_false_act
unrelated_receipt_utility
pre_compromise_utility
post_remediation_utility
mixed_parent_false_act
cross_agent_revoked_false_act
record_reissue_escape_false_act
revoked_receipt_copy_false_act
sibling_receipt_utility
generation_false_act
historical_rewrite_count
reproducible_trace
```

`SELECTIVE-REVOCATION-SUPPORTED`, `SELECTIVITY-FAIL`,
`DEPENDENCY-REPRESENTATION-GAP`, `RECEIPT-SCHEMA-GAP`, `KILL`, and `INVALID`
retain their exact R2 meanings. No aggregate score or denominator reduction is
allowed.

If recomputed metrics differ from reported metrics, R3 is `INVALID` and must
not produce a security verdict.

## No implementation authorization

Do not create `run.py`, `result.json`, `RESULT.md`, `ADAPTER_AUDIT.md`, or an
`execution/` directory under the R3 package in this session. Do not modify R2,
the Gate 1C design, P2, Architecture A, or production Custody.
