# Gate 1C Invalid Attempt 01

Status: `INVALID`; preserved exactly. No corrected rerun is authorized under
this experiment identity.

## Lineage and preflights

- Experiment: `EXT_GATE1C_SELECTIVE_RECEIPT_REVOCATION`
- Design/preregistration SHA: `3b27797aa0fb20d6207ecd3881bbcbabf3580ca2`
- Branch: `research/external-gate1c-selective-revocation-falsifier`
- R3 preregistration: `8822dae5fda2566d24e0d4115173d360df722eec`
- R3 execution commit: `f3eb51cbdd52eca0f30f9989311f944b5ee50c35`
- lineage/design, pinned-source, receipt-schema, graph, issuer/relay, and
  model-free preflights: PASS
- graph preflight: 16 unique records, 5 authenticated roots, no new receipt
  fields

## Failure boundary

The exact launcher entered `main()`, completed `preflight()`, and began the
first `build_run(1)`. It failed while constructing the in-memory root selector
set before `evaluate_arm()` was called:

```text
revoked_roots = {objects["R_BAD_1"], objects["R_BAD_2"]}
TypeError: unhashable type: 'dict'
```

No R0 or root-bound arm evaluated a record. No action decision, scorer read,
metric, or security result exists. No result artifact is manufactured from this
partial run.

## Integrity

- model calls: `0`
- API/model cost: `$0`
- scorer reads: `0`
- production diff: empty
- frozen unit suite: `381/381`
- R3 artifacts: unchanged

This is an implementation/lifecycle failure, not `SELECTIVITY-FAIL`,
`RECEIPT-SCHEMA-GAP`, `KILL`, or evidence for either revocation arm. The
runner is intentionally not patched or rerun under Gate 1C.
