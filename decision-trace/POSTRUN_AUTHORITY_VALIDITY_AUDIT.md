# Post-run Prospective Ground-Truth Validity Audit

Status: **MATERIAL DEFECT FOUND; DATASET NOT EDITED; NO RERUN PERFORMED**

## Trigger

Manual bilateral failure inspection after the raw runs and mechanical score exposed an inconsistent distinction between `UNRESOLVED` and `NO_GOVERNING_DECISION`. This audit records the defect without changing the frozen answer key or any model output.

## Affected checkpoints

| Checkpoint | Visible exact-scope state | Frozen key | Resolver | Both RAG arms |
|---|---|---|---|---|
| `python-paramspec-implementation-c2` | open implementation PR; accepted policy exists only in a separate policy scope | UNRESOLVED | UNRESOLVED | NO_GOVERNING_DECISION |
| `swift-coroutine-accessors-c2` | open implementation PR; accepted policy exists only in a separate policy scope | UNRESOLVED | UNRESOLVED | NO_GOVERNING_DECISION |

The source histories do not contain conflicting implementation authority. The only exact implementation-scope artifact is explicitly `OPEN`. Under the dataset's treatment of equivalent open-only PR histories (`kubernetes-pleg-default-c1`, `terraform-iam-role-chaining-c1`, `opentofu-minimal-image-docs-c1`, `envoy-ext-authz-empty-values-c1`, and `llvm-openmp-target-fast-c1`), the governing state is `NO_GOVERNING_DECISION`.

The difference is the presence of an accepted policy in a parallel scope. The frozen resolver's fallback returns `UNRESOLVED` whenever some eligible authority exists elsewhere but none is eligible in the requested exact scope. The answer key copied that fallback outcome for these two rows. That makes unrelated policy authority change the adjudicated state of an implementation scope, contrary to the benchmark's preregistered exact-scope and parallel-independence semantics.

## Materiality

Frozen-key mechanical score:

- DecisionTrace: 98/101
- primary RAG: 94/101
- difference: +4
- paired 90% CI: +1.0 to +6.9 points

Sensitivity only—**not an edited score**—if the two rows used the internally consistent `NO_GOVERNING_DECISION` state:

- DecisionTrace would lose two correct rows: 96/101
- both RAG arms would gain two correct rows: 96/101
- comparative accuracy would tie

The defect therefore creates the entire apparent statistically positive comparative advantage. It is material to the research question even though the strict +8/evidence GO gate already failed.

## Integrity decision

The frozen answer key, raw outputs, mechanical score, and 100,000-sample interval remain byte-preserved for inspection. They will not be repaired after results, and the systems will not be rerun. Because a mandatory ground-truth quality gate failed and materially changes the comparative conclusion, the final verdict is:

**BENCHMARK INVALID — FIX BEFORE CONCLUDING**

A future experiment must define `NO_GOVERNING_DECISION` versus `UNRESOLVED` independently of resolver fallback behavior, re-adjudicate all such rows before inference, and use fresh runs. These outputs cannot be recycled as a corrected prospective result.
