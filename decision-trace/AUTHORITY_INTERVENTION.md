# Preregistered single authority intervention

Written after the complete baseline was graded and before intervention code.
The baseline outputs and `data/authority/baseline_scores.json` are immutable.

## Baseline trigger

DecisionTrace scored 47/61 (77.0%) governing-decision accuracy versus RAG at
52/61 (85.2%). It failed every preregistered authority-advantage criterion.
The paired timeline bootstrap difference was -8.1 points with a 90% interval
of -25.0 to +8.5 points.

## Complete DecisionTrace miss forensics

| Checkpoint | Failure | Mechanism |
|---|---|---|
| `metadata-redesign-c3` | proposal/withdrawal promoted | generation |
| `metadata-redesign-c4` | missing PEP 566 | generation |
| `metadata-redesign-c5` | missing PEP 566 | generation |
| `manylinux-policy-c4` | parallel decisions collapsed | deterministic resolver |
| `manylinux-policy-c5` | missing PEP 600 | deterministic resolver |
| `metadata-1-1-c1` | missing PEP 241 | generation |
| `single-file-metadata-c3` | rejected PEP 722 promoted | generation |
| `pypi-mirror-split-c1` | withdrawn PEP 381 promoted | generation |
| `pypi-mirror-split-c3` | parallel decisions collapsed | deterministic resolver |
| `python-encoding-warning-c2` | policy/implementation collapsed | generation |
| `python-encoding-warning-c3` | policy/implementation collapsed | generation |
| `python-encoding-warning-c4` | policy/implementation collapsed | generation |
| `python-multiphase-init-c3` | policy/implementation collapsed | generation |
| `python-multiphase-init-c4` | policy/implementation collapsed | generation |

One additional row, `python-multiphase-init-c2`, had the correct governing ID
but omitted its evidence binding.

Taxonomy totals for authority misses: generation/presentation 11,
deterministic resolver 3. The evidence-only miss is evidence binding 1. There
were no ingestion/extraction, retrieval, ambiguous-ground-truth, or other
misses under the frozen mechanistic classifier.

## Hypothesis

If DecisionTrace resolves one authority scope deterministically, rejects
proposal/withdrawn/rejected records, and treats implementation lineages as
evidence rather than policy authority when an accepted policy is present,
then it will rescue the observed status, multi-target, narrow-scope, and
policy-versus-code failures without changing the dataset, RAG arm, prompts,
model, adapter inputs, or grader.

## Exactly one change

Add one deep module with one public operation:

`resolve_authority(decisions, authority_scope) -> AuthorityResolution`

The operation owns four rules:

1. `PROPOSED`, withdrawn/rejected terminal records, and superseded records are
   not eligible to govern. A merged rollback record remains eligible when it
   has an explicit `REVERTS` edge.
2. Exact authority scope is resolved before lifecycle replay. If the query has
   no exact scope but several accepted scopes are visible, return `UNRESOLVED`
   instead of guessing.
3. When an implementation record explicitly `IMPLEMENTS` an accepted policy,
   its implementation/revert lineage is excluded from the policy authority
   election. The code history remains evidence; it does not replace policy.
4. The selected ID/state is deterministic output. Gemini receives it as fixed
   fact and may explain it, but generation cannot select, replace, or omit it.

This is one authority-resolution intervention, not four features. The rules
are the internal policy of one deep module and its caller remains a single
operation.

## Expected rescued cases fixed before coding

Expected authority rescues: all 14 baseline authority misses listed above.
Expected evidence rescue: `python-multiphase-init-c2`. Expected regressions: 0.

The strongest uncertainty is broad-scope abstention. The safe rule is to
return `UNRESOLVED` whenever no exact scope matches but multiple eligible
authority scopes are visible; it does not infer a winner from semantic
similarity.

## Kill criterion

Kill this intervention as unsupported if any of the following occurs on the
single full rerun:

- fewer than 8 of the 14 preregistered authority misses are rescued;
- governing accuracy improves by less than 8 percentage points;
- any baseline-correct checkpoint regresses;
- any leakage/equivalence/protected-file gate fails; or
- implementing the rules requires reading ground truth, scenario labels, or
  failure labels at runtime.

Regardless of the post-intervention score, the untouched baseline remains the
headline comparison and determines whether an authority-advantage claim was
established.
