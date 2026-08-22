# Gate 1C — Revocation Granularity Matrix

Status: analysis only; no selector is implemented.

The matrix distinguishes measured R3 behavior from preregistered expectations
for a future falsifier. No row is selected because it is expected to turn the
result green.

| Selector | Selector material | Affected recall | Unrelated collateral | Descendant completeness | Multi-parent / cross-agent | Generation / ABA | History | Bounded compromise | Storage / operations | Disposition |
|---|---|---:|---:|---|---|---|---|---|---|---|
| R0 issuer-wide | `issuer_id` | R3: 100% | R3: 100% collateral (`0/2` unrelated utility) | broad, not selective | blocks unrelated support too | does not distinguish receipts or generations | immutable | cannot express an interval | one issuer deny-list | measured negative control |
| R1 PolicyKey-wide | exact PolicyKey | expected high | collateral for every root under that key | complete for the key, overbroad within it | clean sibling under same key is lost | insufficient for same-key compromise windows | immutable | weak; key-wide | key deny-list | still too coarse |
| R2 key + generation | PolicyKey + `granting_generation` | expected high for a compromised generation | avoids other generations, but collateral remains within the generation | complete only if every dependency retains generation | can preserve other generations but cannot separate same-generation roots | generation-scoped; does not solve same-generation compromise or ABA by itself | immutable | cannot isolate two roots in one generation | generation deny-list | insufficient for bounded same-generation compromise |
| R3 receipt-root bound | authenticated root identity, then dependency closure | target: 100% | target: 0% | complete if all descendants retain required root dependencies | all required parents remain checked; forwarded dependencies cannot disappear | root key includes generation and receipt identity | immutable | supports a set of selected roots | root revocation set plus closure/index | selected minimum candidate |
| R4 bounded compromise set | frozen set/range of authenticated root keys | target: 100% for set | target: 0% outside set | closure over every selected root | mixed selected/unselected parents deny when both are required | combines root identity with generation/window; avoids ABA by exact key | immutable | directly represents `R_BAD_1..R_BAD_2` | selector set/range plus closure/index | temporal extension of R3, not a new receipt schema |
| R5 receipt-ID only | `receipt_id` alone | target possible only if dependencies retain it | target possible | incomplete if a derived record drops receipt ID or root link | cross-agent/root dropping can escape | receipt IDs help ABA but do not identify closure alone | immutable | set of IDs is expressible | ID deny-list plus reverse index | insufficient alone |

## Selected minimum

Gate 1C selects **R3 receipt-root-bound revocation**, represented by an
authenticated root dependency key composed only from already-frozen data:

```text
issuer_id
receipt_id
upstream_record_id
upstream_object_commitment
PolicyKey
granting_generation
root_record_id        # durable support/dependency identity
```

R4 is the required temporal use of R3: a bounded compromise is a frozen set of
these authenticated root keys, not a new receipt field. R5 is retained as an
escape control and is not selected because receipt identity without a retained
root/dependency closure is insufficient.

## Required resolution rule

At action time, every required authority-bearing support path must resolve to a
currently valid authenticated root. A revoked root invalidates the dependent
path; a clean sibling cannot wash it when both parents are required. A root
outside the selector remains usable. Historical receipts, records, parentage,
and support roots remain immutable.

The future experiment must measure this rule directly rather than infer it from
an aggregate score.
