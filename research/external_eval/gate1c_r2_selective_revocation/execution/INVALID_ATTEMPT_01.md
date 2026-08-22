# Gate 1C-R2 Invalid Attempt 01

Status: `INVALID`; preserve the raw attempt without interpreting its emitted
mechanical label as a security verdict. No patch-and-rerun is authorized under
R2.

## Frozen identity and preflights

- Experiment: `EXT_GATE1C_R2_SELECTIVE_RECEIPT_REVOCATION`
- Preregistration: `552cf23336a0a222364c247e61c7263f84e56f60`
- Branch: `research/external-gate1c-r2-selective-revocation-falsifier`
- R1 invalid preservation: `9dbf6b721057a02d674663d30656948a3af6faa1`
- Root resolution and RootKey preflights: PASS
- Graph: `16` records, `16` unique durable IDs, `5` authenticated roots
- Selector: `R_BAD_1`, `R_BAD_2`, exactly two unique immutable keys
- External pin/model preflights: PASS; model calls `0`, API cost `$0`

## Treatment boundary

Both frozen arms ran against two clean constructions of the same graph. Action
traces were produced and normalized traces matched. No exception escaped and
no security mechanism was changed during treatment.

## Post-treatment runner defect

The runner's shared `metric(runs, arm, case, allowed)` helper inverted every
expected-denial metric. For `allowed=False`, it counted `not action_allowed`
as the numerator. Consequently, correct DENY outcomes for mixed-parent,
cross-agent, reissue, revoked-copy, and generation controls were recorded as
false ACTs, and the runner emitted `KILL`.

The frozen metric contract requires false-ACT numerators to count
`action_allowed=True`; correct DENY must contribute zero. Therefore the emitted
metric table and mechanical label are invalid evidence, even though the raw
action traces are retained for audit.

## Result boundary and integrity

- raw result, normalized traces, and all four execution artifacts preserved;
- scorer reads: `0`;
- payload-semantic inspection: `false`;
- production paths unchanged;
- frozen tests: `381/381`;
- no valid Gate 1C-R2 security verdict exists.

This is a runner/metric-boundary failure after treatment, not evidence for
`KILL`, `SELECTIVITY-FAIL`, or `SELECTIVE-REVOCATION-SUPPORTED`.
