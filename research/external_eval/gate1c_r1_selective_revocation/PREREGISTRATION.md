# Gate 1C-R1 — Selective Receipt Revocation Preregistration

Status: frozen preregistration only. **NO IMPLEMENTATION and NO EXECUTION in
this session.**

## Experiment identity and lineage

```text
experiment_id = EXT_GATE1C_R1_SELECTIVE_RECEIPT_REVOCATION
family = GATE1C_SELECTIVE_RECEIPT_REVOCATION
parent_design_commit = 3b27797aa0fb20d6207ecd3881bbcbabf3580ca2
preserved_invalid_attempt = 5e47b9fabadd932812978959cbd9c5b1d3cc3d58
branch = research/external-gate1c-r1-selective-revocation-falsifier
```

The preregistration SHA is the commit containing these documents and must be
discovered from the repository/remote at execution time. It must not be
copied from a prompt or retroactively changed.

The original Gate 1C identity remains invalid and is not rerun. Its failure
was pre-arm selector construction; no treatment or scorer result existed.

## Hypothesis and single authorized change

The frozen Gate 1C hypothesis is unchanged: the existing authenticated root
identity can support selective revocation without compromising affected-root
safety or unrelated utility.

The only R1 change is the construction lifecycle of the candidate selector:
mutable `SecurityRecord` objects are never inserted into a set; the same
preselected roots are converted to the same canonical immutable `RootKey`
tuples first. The R3 root-bound verifier, selector interpretation, and every
security rule remain frozen.

This correction was selected solely from the observed pre-treatment
`TypeError: unhashable type: 'dict'`. No arm, action, scorer, metric, or
efficacy result was observed.

## Frozen source and authority boundary

The existing P2 receipt schema, issuer authentication, durable root identity,
support/dependency closure, R0 negative control, and root-bound candidate are
unchanged. The external context remains the pinned model-free artifact:

```text
repository = yedidel/mem-inv-bench
commit = 63f1359d677efbe1a65b982b2a54cabfec97f1e1
attack = code/laundering.py::tool_echo
model_calls = 0
api_cost = $0
```

Neither arm receives scorer truth, payload-semantic labels, `true_origin`, or
case labels. No payload classifier, LLM, or production service is permitted.

## Frozen cases and graph

Use exactly the Gate 1C graph and cases: issuer-wide R0; bounded roots
`R_PRE`, `R_BAD_1`, `R_BAD_2`, `R_POST`, `R_OTHER`; descendants
`D_PRE`, `D_BAD1`, `D_BAD2`, `D_POST`, `D_OTHER`, `D_MIX`; cross-agent revoked
forwarding; record-ID reissue; revoked-receipt copy; sibling; old-generation;
and the frozen escape controls. No case is added, removed, or made easier.

## Pretreatment gates

Before any arm/action/scorer operation, R1 must verify:

1. design and lineage commits are present and the branch/remote identity is
   frozen;
2. the external pin and receipt schema match Gate 1C;
3. the graph has `16` records, `16` unique IDs, and `5` authenticated roots;
4. the selector manifest names exactly `R_BAD_1` and `R_BAD_2`;
5. exactly `2` immutable unique `RootKey` tuples are produced;
6. no mutable record/dict/list is in the selector;
7. issuer signing authority is unavailable to the relay;
8. scorer is unreachable from treatment code;
9. no payload-semantic or case-label authority branch exists;
10. `model_calls = 0`, API cost is `$0`, and protected production paths are
    unchanged.

Any failure is `INVALID` before treatment. R1 must not patch-and-continue.

## Security metrics and gates

All raw Gate 1C metrics and denominators remain unchanged:

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

The candidate requires complete affected recall and zero affected ACT, full
unrelated/pre-compromise/post-remediation utility, zero mixed/cross-agent/
escape/generation false ACT, zero historical rewrites, and two matching
normalized traces. The exact frozen mappings remain
`SELECTIVE-REVOCATION-SUPPORTED`, `SELECTIVITY-FAIL`,
`DEPENDENCY-REPRESENTATION-GAP`, `RECEIPT-SCHEMA-GAP`, `KILL`, or `INVALID`;
no partial pass is introduced.

## No implementation authorization

This document freezes only the corrected lifecycle contract. Do not create
`run.py`, `result.json`, `RESULT.md`, `ADAPTER_AUDIT.md`, or an `execution/`
directory under the R1 package in this session. Do not modify the Gate 1C
design files, the invalid original runner, Architecture A, P2, or production
Custody.
