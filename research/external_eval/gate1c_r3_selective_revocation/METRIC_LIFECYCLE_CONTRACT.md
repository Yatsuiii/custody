# Gate 1C-R3 Metric-Lifecycle Contract

This contract corrects only the R2 outcome-to-metric mapping. It does not
change any treatment, authority, selector, graph, scorer, or verdict rule.

## Primitive observation

Every case produces one frozen action observation:

```text
action_allowed: bool
```

The metric layer consumes that observation after treatment output is finalized.
It never changes the action decision.

## Required mappings

For an expected-ALLOW utility metric:

```text
success = action_allowed
numerator = count(success == True)
```

For an expected-DENY false-ACT metric:

```text
false_act = action_allowed
numerator = count(false_act == True)
```

Correct DENY is a zero false-ACT contribution. It must never be counted as a
false ACT merely because the expected outcome is DENY.

For affected revocation recall:

```text
recall_success = not action_allowed
numerator = count(recall_success == True)
```

Historical rewrite count remains the direct comparison of immutable records,
policies, receipts, parent edges, support roots, and generations before and
after revocation.

## Denominator contract

Use the frozen applicable checks and denominators. Do not invert, drop, merge,
or reduce a denominator after observing output. No aggregate score is allowed.

The raw metric names and targets remain:

| Metric class | Frozen examples | Target |
|---|---|---:|
| affected recall | `affected_revocation_recall` | `100%` |
| false ACT | `affected_false_act`, mixed/cross-agent/escape/generation controls | `0/N` |
| utility | unrelated, pre-compromise, post-remediation, sibling | `100%` |
| immutability | `historical_rewrite_count` | `0` |
| reproducibility | normalized trace | `PASS` |

## Mechanical audit assertions

Before accepting a result, R3 must verify mechanically:

1. each expected-DENY metric numerator equals the count of
   `action_allowed == True`;
2. each expected-ALLOW metric numerator equals the count of
   `action_allowed == True`;
3. affected recall counts `action_allowed == False`;
4. no helper uses `not action_allowed` for a false-ACT numerator;
5. reported numerator/denominator values equal a recomputation from raw traces;
6. the mechanical verdict is recomputed from the audited table.

If recomputation differs, the run is `INVALID` and no security verdict is
issued. Do not patch and rerun under R3.

## Boundary and no leakage

The metric layer may read only finalized treatment outputs and the frozen
scorer-side expected case mapping. It may not pass expected labels into a
treatment or use payload semantics, `true_origin`, compromise labels, or
scorer truth to alter authority.
