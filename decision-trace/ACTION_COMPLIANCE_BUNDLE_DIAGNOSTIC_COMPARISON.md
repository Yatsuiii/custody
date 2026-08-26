# Bundle-ingestion diagnostic comparison

Status: **post-freeze diagnostic only**

The bundle-derived Decision sets and AuthorityProof JSON files were hashed in
`data/action_compliance/bundle_runs/PRE_GROUND_TRUTH_SHA256.txt` before this
comparison.  This document was written only after that freeze.  No generated
Decision, proof, source bundle, grader, or task ground-truth file was changed
in response to the comparison.

## Result by task

| Task | Frozen records | Frozen extraction shape | Frozen proof | Diagnostic against human authority |
|---|---:|---|---|---|
| task-02 Django | 2 | two `IMPLEMENTED` records; no accepted lifecycle edge; one quote failure; requested scope echoed the full coding prompt | `NO_GOVERNING_DECISION` | unresolved because the extracted scope is not an authority scope and the model treated deprecation/removal as implementation records |
| task-go Go maps | 2 | two `ACCEPTED` records; four unverifiable quotes; scope is the test path | `NO_GOVERNING_DECISION` | unresolved because the requested test path is absent from decision scopes and evidence was rejected |
| task-03 pip | 3 | `SUPERSEDED` PEP 722, `ACCEPTED` PEP 723 with `SUPERSEDES`, `IMPLEMENTED` pip record with `IMPLEMENTS` | `NO_GOVERNING_DECISION` | lifecycle shape is source-supported, but no record covers the requested implementation path |
| task-04 CPython | 3 | `REVERTED` binary implementation, `IMPLEMENTED` restore with `REVERTS`, `ACCEPTED` PEP 597 | `NO_GOVERNING_DECISION` | lifecycle shape is partially source-supported, but the extracted scope is broader/different from the requested pure-Python scope |
| task-05 packaging | 3 | `ACCEPTED` PEP 600, `IMPLEMENTED` implementation, `PROPOSED` task record | `NO_GOVERNING_DECISION` | records include the policy and implementation distinction, but no exact `packaging.tags` scope was attached |
| task-06 OpenTofu | 3 | `ACCEPTED` issue scope, `IMPLEMENTED` RFC, `PROPOSED` task record with `IMPLEMENTS`; one quote failure | `NO_GOVERNING_DECISION` | requested scope was echoed as a coding paragraph, so exact-scope filtering discarded every record |
| task-07 axum | 2 | `ACCEPTED` policy and `IMPLEMENTED` trait implementation with `IMPLEMENTS` | `NO_GOVERNING_DECISION` | no exact requested extractor scope was attached |

All seven human-adjudicated tasks have a governing authority in the frozen
inventory, but all seven bundle-derived proofs are unresolved/no-governing.
This is an observed limitation of the generic extraction path, not a hidden
repair target.  It must remain in any later Arm-C result.

## Frozen-output rule

The comparison did not modify the adapter, rerun Gemini, alter a status/scope/
relationship, or substitute the ledger's expected governing ID.  A later
experiment therefore measures this exact product behavior, including the
possibility that a weak or unresolved proof harms Arm C.
