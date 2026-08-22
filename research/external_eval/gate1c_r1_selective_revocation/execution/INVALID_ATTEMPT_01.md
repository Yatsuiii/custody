# Gate 1C-R1 Invalid Attempt 01

Status: `INVALID` before arm evaluation. This is preserved as a runner
pre-treatment failure; no R1 security result exists.

## Frozen identity

- Experiment: `EXT_GATE1C_R1_SELECTIVE_RECEIPT_REVOCATION`
- Preregistration: `223fedaa8a36eff6d273f5c26e11ffd18d76114a`
- Branch: `research/external-gate1c-r1-selective-revocation-falsifier`
- Parent design: `3b27797aa0fb20d6207ecd3881bbcbabf3580ca2`
- Preserved original Gate 1C attempt: `5e47b9fabadd932812978959cbd9c5b1d3cc3d58`

## Pretreatment boundary

The frozen branch/remote/document preflight passed. The runner loaded the
frozen R3 implementation and began the RootKey preflight after constructing
the frozen graph. No R0 or root-bound arm was called.

## Exact runner failure

The RootKey preflight treated the alias-to-record mapping as keyed by durable
record ID and raised:

```text
KeyError: 'ROOT-01'
```

The mapping is keyed by the frozen aliases (`R_PRE`, `R_BAD_1`, `R_BAD_2`,
`R_POST`, `R_OTHER`). This is an implementation error in the pre-treatment
selector check, not a revocation or security outcome.

## Result boundary

- arm evaluations: `0`
- action decisions: `0`
- scorer reads: `0`
- metrics/result: none
- model calls/API cost: `0` / `$0`
- production paths: unchanged

Per the frozen R1 contract, this attempt is not patched or rerun under the
same identity.
