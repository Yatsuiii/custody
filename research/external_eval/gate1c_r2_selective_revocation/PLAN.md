# Gate 1C-R2 — Selective Receipt Revocation

Status: preregistration only. No runner, result, adapter, prototype, or
production change is authorized in this session.

## Identity and lineage

- Experiment family: `GATE1C_SELECTIVE_RECEIPT_REVOCATION`
- Experiment identity: `EXT_GATE1C_R2_SELECTIVE_RECEIPT_REVOCATION`
- Parent R1 preregistration: `223fedaa8a36eff6d273f5c26e11ffd18d76114a`
- Preserved R1 invalid-attempt commit: `9dbf6b721057a02d674663d30656948a3af6faa1`
- Parent Gate 1C design: `3b27797aa0fb20d6207ecd3881bbcbabf3580ca2`
- New branch: `research/external-gate1c-r2-selective-revocation-falsifier`

R1 remains invalid and is not rerun. Its pre-treatment failure produced no arm,
action, scorer, metric, or security result.

## Frozen question and arms

R2 retains the Gate 1C question: can authenticated receipt-root revocation
remove compromised-root authority while preserving unrelated, pre-compromise,
and post-remediation authority?

The arms remain unchanged:

| Arm | Definition |
|---|---|
| `R0_ISSUER_WIDE` | issuer-wide revocation negative control |
| `R3_RECEIPT_ROOT_BOUND` | authenticated RootKey-bound revocation candidate |

Both arms use the same immutable graph, P2 schema, support closure,
transforms, generation rules, scorer, metrics, denominators, and gates.

## R1 failure and exact root cause

R1 completed the frozen branch/document preflight and entered the RootKey
preflight. Its runner represented roots in two namespaces:

```text
root_ids = {alias -> durable_record_id}
objects = {alias -> SecurityRecord, case_name -> SecurityRecord}
```

The preflight incorrectly used a durable ID from `root_ids.values()` as a key
into `objects`, which is keyed by aliases. The first lookup raised:

```text
KeyError: 'ROOT-01'
```

No arm or scorer path was reached. This is a selector-construction lifecycle
error, not evidence about revocation safety or selectivity.

## Single authorized R2 correction

R2 changes only namespace resolution in the pre-treatment RootKey check:

1. The graph builder retains the existing alias-to-durable-ID manifest.
2. A canonical `records_by_id` view is derived from the already-built records.
3. Every root alias is resolved through one explicit helper that asserts the
   alias maps to the expected durable record ID.
4. RootKey derivation receives the resolved `SecurityRecord` and its receipt.

The RootKey field set and selector meaning are unchanged. No graph record,
parent edge, receipt field, dependency, action rule, or revocation selector is
added, removed, or renamed.

## Pretreatment gates

Before any arm/action/scorer operation, R2 must verify:

- branch/local/remote preregistration identity is frozen;
- all four R2 design documents are present and immutable;
- the frozen external pin and P2 schema match;
- graph records: `16`;
- unique durable record IDs: `16`;
- authenticated roots: `5`;
- all five aliases resolve to the expected durable IDs;
- five deterministic, unique, immutable RootKeys are produced;
- exactly two selector keys are produced for `R_BAD_1` and `R_BAD_2`;
- `R_PRE`, `R_POST`, and `R_OTHER` are not selected;
- no scorer or treatment call occurred;
- no payload-semantic or case-label authority branch exists;
- model calls/API cost are `0`/`$0` and protected production paths are clean.

Any failure is `INVALID` before arm evaluation. R2 does not patch-and-continue
after a failed preflight.

## Frozen outcomes and gates

R2 keeps every Gate 1C case, raw metric, denominator, PASS/FAIL mapping, and
KILL condition. A valid candidate must obtain complete affected recall and zero
affected ACT, retain unrelated/pre-compromise/post-remediation utility, reject
mixed and cross-agent washing/escape, preserve generation freshness and
historical immutability, and reproduce its normalized trace twice.

The only possible change from R1 is whether the pre-treatment resolver reaches
those already-frozen checks. No efficacy outcome has been observed.

## No implementation authorization

This package freezes R2 only. Do not create `run.py`, `result.json`,
`RESULT.md`, `ADAPTER_AUDIT.md`, or an `execution/` directory under the R2
package in this session. Do not modify R1, the Gate 1C design, P2,
Architecture A, or production Custody.
