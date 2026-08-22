# Gate 1C-R3 — Selective Receipt Revocation

Status: preregistration only. No runner, result, adapter, prototype, or
production change is authorized in this session.

## Identity and lineage

- Experiment family: `GATE1C_SELECTIVE_RECEIPT_REVOCATION`
- Experiment identity: `EXT_GATE1C_R3_SELECTIVE_RECEIPT_REVOCATION`
- Parent R2 preregistration: `552cf23336a0a222364c247e61c7263f84e56f60`
- Preserved invalid R2 attempt: `40e33a7c0b75afd4f9e63816caa136368ecd7c1b`
- Parent Gate 1C design: `3b27797aa0fb20d6207ecd3881bbcbabf3580ca2`
- New branch: `research/external-gate1c-r3-selective-revocation-falsifier`

R2 is preserved exactly as an invalid post-treatment runner/metric-boundary
attempt. Its raw traces and emitted files are not reinterpreted or rerun.

## Frozen question and arms

R3 retains the Gate 1C question: can authenticated receipt-root revocation
remove compromised-root authority while preserving unrelated, pre-compromise,
and post-remediation authority?

The two arms remain unchanged:

| Arm | Definition |
|---|---|
| `R0_ISSUER_WIDE` | issuer-wide revocation negative control |
| `R3_RECEIPT_ROOT_BOUND` | authenticated RootKey-bound revocation candidate |

The same graph, P2 schema, RootKey fields, resolver, support closure,
transforms, generations, scorer, metrics, denominators, and verdict gates are
frozen.

## R2 failure localization

R2 completed preflights and both arms twice. Its action traces were produced,
but the shared metric helper implemented:

```text
if expected_allow is false:
    numerator += (not action_allowed)
```

That counts correct DENY outcomes as false ACTs. The runner consequently emitted
`KILL` for mixed-parent, cross-agent, reissue, revoked-copy, and generation
controls even though their raw action traces were DENY. The emitted metric table
and mechanical label are invalid evidence.

No security mechanism or treatment outcome is being changed in response to
R2; R3 corrects only this accounting boundary.

## Single authorized R3 change

R3 uses one explicit outcome-to-metric mapping:

- expected **ALLOW** utility metric: numerator is `action_allowed == True`;
- expected **DENY** false-ACT metric: numerator is also
  `action_allowed == True`;
- expected-DENY success is therefore `1 - action_allowed`, but it is not named
  or reported as false ACT;
- affected recall is `action_allowed == False`;
- historical rewrite count is the direct immutable-snapshot comparison.

No action decision, authority resolution, selector, graph, case, scorer,
threshold, or KILL rule changes.

## Frozen pretreatment and execution requirements

Before treatment, R3 must repeat the R2 resolver/RootKey gates: `16` records,
`16` unique durable IDs, `5` authenticated roots, five deterministic unique
RootKeys, exactly two selected keys for `R_BAD_1`/`R_BAD_2`, zero mutable
selector members, no scorer access, unchanged P2 schema, and model/API cost
`0`/`$0`.

If those pass, both frozen arms run on the same graph twice. No patch-and-rerun
is permitted after treatment begins.

## Frozen metrics and verdicts

The raw metrics remain exactly:

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

## No implementation authorization

This document freezes R3 only. Do not create `run.py`, `result.json`,
`RESULT.md`, `ADAPTER_AUDIT.md`, or an `execution/` directory under the R3
package in this session. Do not modify R2, Gate 1C design, P2, Architecture A,
or production Custody.
