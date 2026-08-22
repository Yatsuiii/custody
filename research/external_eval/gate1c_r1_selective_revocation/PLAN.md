# Gate 1C-R1 — Selective Receipt Revocation

Status: preregistration only. No runner, result, adapter, prototype, or
production change is authorized in this session.

## Identity and lineage

- Experiment family: `GATE1C_SELECTIVE_RECEIPT_REVOCATION`
- Experiment identity: `EXT_GATE1C_R1_SELECTIVE_RECEIPT_REVOCATION`
- Parent design/preregistration: Gate 1C design commit
  `3b27797aa0fb20d6207ecd3881bbcbabf3580ca2`
- Preserved invalid attempt: Gate 1C execution commit
  `5e47b9fabadd932812978959cbd9c5b1d3cc3d58`
- Invalid-attempt status: `INVALID_RUNNER_SELECTOR_CONSTRUCTION`
- New branch: `research/external-gate1c-r1-selective-revocation-falsifier`

The invalid attempt remains evidence under its original identity. R1 is a new
identity because the first attempt reached no arm, action decision, scorer
read, metric, or security result.

## Frozen question and baseline

The Gate 1C question remains whether authenticated receipt-root revocation can
remove authority supported by compromised roots while preserving unrelated,
pre-compromise, and post-remediation authority.

The two frozen arms remain:

| Arm | Frozen behavior |
|---|---|
| `R0_ISSUER_WIDE` | Gate 1C/R3 issuer-wide revocation negative control |
| `R3_RECEIPT_ROOT_BOUND` | root-bound revocation over authenticated receipt/dependency identity |

The same immutable graph, P2 receipt schema, support closure, transformations,
generation rules, action gateway, scorer boundary, metrics, denominators,
verdict precedence, and kill conditions are used by both arms.

## Observed invalid-attempt root cause

The original runner completed its preflight and entered `build_run(1)`. It
constructed the candidate selector with:

```python
revoked_roots = {objects["R_BAD_1"], objects["R_BAD_2"]}
```

The values are mutable `SecurityRecord` instances containing dictionary-valued
fields, so Python raised:

```text
TypeError: unhashable type: 'dict'
```

This occurred before either revocation arm was evaluated. No security outcome
was observed and the original runner is not patched or rerun.

## Single authorized R1 change

R1 changes only selector construction/lifecycle handling:

1. Construct the same graph and resolve the same two authenticated roots.
2. Convert each selected root to the already-frozen immutable `RootKey`.
3. Store those tuple keys in the candidate selector set.
4. Pass the resulting key set to the unchanged root-bound verifier.

The canonical key remains exactly the Gate 1C key, using fields already present
in the P2 receipt and durable lineage:

```text
RootKey = (
    issuer_id,
    receipt_id,
    upstream_record_id,
    upstream_object_commitment,
    PolicyKey,
    granting_generation,
    root_record_id,
)
```

No new receipt field, selector meaning, revocation selector, or authority rule
is introduced.

## Selector-construction lifecycle

The future runner must keep these phases separate:

1. **Graph construction:** create the frozen records, receipts, parent edges,
   and support roots exactly once.
2. **Root resolution:** authenticate each selected receipt and resolve its
   immutable root record identity.
3. **Selector construction:** derive two immutable `RootKey` tuples for
   `R_BAD_1` and `R_BAD_2`; reject missing, duplicate, or non-canonical keys.
4. **Selector dry-run gate:** verify the selector manifest without evaluating
   an arm, action, or scorer.
5. **Arm evaluation:** run the unchanged R0 and root-bound arms against the
   same graph.

The selector constructor must never hash a mutable `SecurityRecord`, list, or
dictionary. It must not inspect payload bytes or receive scorer labels,
compromise booleans, or case names as security inputs.

## Pretreatment selector gate

Before any treatment or scorer call, the R1 runner must verify:

- frozen graph records: `16`;
- unique graph records: `16`;
- authenticated roots: `5`;
- selected revoked roots: `2` (`R_BAD_1`, `R_BAD_2`);
- derived selector keys: `2`;
- selector keys unique: `2`;
- every key is an immutable tuple of the frozen fields;
- no `SecurityRecord` object is present in the selector;
- no payload/scorer/case-label field participates in a key.

Any failure is `INVALID` before arm evaluation. The gate produces no treatment
or efficacy result.

## Frozen graph and semantics

The graph remains the Gate 1C graph: roots `R_PRE`, `R_BAD_1`, `R_BAD_2`,
`R_POST`, and `R_OTHER`; derived records `D_PRE`, `D_BAD1`, `D_BAD2`, `D_POST`,
`D_OTHER`, `D_MIX`; the cross-agent, record-reissue, revoked-receipt-copy,
generation, sibling, and escape controls. It remains `16` unique records and
`5` authenticated roots.

R0 revokes the issuer. The candidate revokes only the authenticated keys for
`R_BAD_1` and `R_BAD_2`. Authority resolution, support closure, multi-parent
requirements, cross-agent forwarding, generation freshness, and historical
immutability are unchanged from the frozen Gate 1C design.

## Acceptance and kill conditions

The future R1 execution uses the exact Gate 1C targets: affected descendants
must lose ACT with complete recall; unrelated, pre-compromise, and
post-remediation receipt-backed authority must remain usable; mixed and
cross-agent dependencies cannot wash a revoked root; escape controls remain
DENY; generation checks remain fail-closed; historical rewrites are zero; and
two normalized runs reproduce.

The frozen mappings remain:

- `SELECTIVE-REVOCATION-SUPPORTED` only when every target and reproducibility
  gate passes;
- `SELECTIVITY-FAIL` when safety holds but required selectivity/utility fails;
- `DEPENDENCY-REPRESENTATION-GAP` if the frozen graph cannot retain the root
  dependency;
- `RECEIPT-SCHEMA-GAP` if safe execution would require a new receipt field;
- `KILL` for affected unauthorized ACT or the stated safety/selectivity
  contradiction;
- `INVALID` for a pre-treatment lifecycle/fixture/scorer boundary failure.

## No result shopping and no implementation

The correction was selected from the pre-treatment Python TypeError. No arm,
action, scorer, or metric result existed in the invalid attempt. R1 may not
change a mechanism in response to an efficacy outcome. This package authorizes
no execution in the current session.
