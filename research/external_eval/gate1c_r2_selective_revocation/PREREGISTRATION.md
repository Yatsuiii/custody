# Gate 1C-R2 — Selective Receipt Revocation Preregistration

Status: frozen preregistration only. **NO IMPLEMENTATION and NO EXECUTION in
this session.**

## Identity and lineage

```text
experiment_id = EXT_GATE1C_R2_SELECTIVE_RECEIPT_REVOCATION
family = GATE1C_SELECTIVE_RECEIPT_REVOCATION
parent_r1_preregistration = 223fedaa8a36eff6d273f5c26e11ffd18d76114a
preserved_r1_invalid_attempt = 9dbf6b721057a02d674663d30656948a3af6faa1
parent_gate1c_design = 3b27797aa0fb20d6207ecd3881bbcbabf3580ca2
branch = research/external-gate1c-r2-selective-revocation-falsifier
```

The R2 preregistration SHA is the commit containing these documents and must
be discovered from the repository/remote at execution time. It must not be
copied from a prompt or changed after freezing.

R1 remains preserved as `INVALID` before arm evaluation. It is not patched or
rerun, and no security result was observed.

## Frozen question and single change

R2 asks the same Gate 1C question: can authenticated receipt-root revocation
remove compromised-root authority while preserving unrelated,
pre-compromise, and post-remediation authority?

The sole authorized change is explicit alias-to-durable-record resolution in
the RootKey preflight. R1's alias/record namespace mismatch is corrected by a
resolver that verifies the manifest and then derives the same frozen RootKeys.

Unchanged: receipt schema, RootKey fields, selector meaning, graph topology,
support/dependency semantics, R0, root-bound candidate, scorer, metrics,
denominators, PASS/KILL conditions, external pin, model-free boundary,
Architecture A, and production Custody.

## Frozen source and boundary

```text
repository = yedidel/mem-inv-bench
commit = 63f1359d677efbe1a65b982b2a54cabfec97f1e1
attack_context = code/laundering.py::tool_echo
model_calls = 0
api_cost = $0
```

No treatment receives payload-semantic labels, scorer truth, `true_origin`,
case labels, or compromise booleans. Compromised root IDs are the same frozen
post-discovery interface; compromise detection itself is out of scope.

## Frozen graph and cases

Use the unchanged `16`-record graph with five authenticated roots:
`R_PRE`, `R_BAD_1`, `R_BAD_2`, `R_POST`, and `R_OTHER`. Keep all frozen derived,
mixed-parent, cross-agent, reissue, revoked-copy, sibling, generation, and
historical-immutability cases. No case is added, removed, or made easier.

## Pretreatment requirements

Before either arm, action, or scorer operation:

1. verify the R2 branch, local/remote SHA, and four frozen R2 documents;
2. verify the R1 preservation commit and frozen R1/design lineage;
3. verify the external source pin and unchanged P2 schema;
4. build the graph and derive `RECORDS_BY_ID` without mutation;
5. resolve all five aliases to their expected durable IDs;
6. construct five deterministic, unique, immutable RootKeys;
7. select exactly two keys for `R_BAD_1` and `R_BAD_2`;
8. prove `R_PRE`, `R_POST`, and `R_OTHER` are not selected;
9. prove no mutable selector member, scorer read, payload-semantic branch,
   relay signing key, production diff, or model call exists.

Any failure is `INVALID` before treatment. Do not patch-and-continue under R2.

## Arms and mechanical gates

Run both frozen arms on the same immutable graph:

- `R0_ISSUER_WIDE`: current issuer-wide negative control;
- `R3_RECEIPT_ROOT_BOUND`: revoke only the two selected RootKeys.

All Gate 1C raw metrics and denominators remain unchanged:

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

The same exact mappings remain: `SELECTIVE-REVOCATION-SUPPORTED` only if every
target passes and two traces match; `SELECTIVITY-FAIL` for utility/selectivity
loss; `DEPENDENCY-REPRESENTATION-GAP` for lost support identity;
`RECEIPT-SCHEMA-GAP` for any required new field; `KILL` for affected ACT or
the frozen safety/selectivity contradiction; and `INVALID` for pre-treatment
or unexpected runner failures.

## No implementation authorization

Do not create `run.py`, `result.json`, `RESULT.md`, `ADAPTER_AUDIT.md`, or an
`execution/` directory under the R2 package in this session. Do not modify R1,
the Gate 1C design, P2, Architecture A, or production Custody.
