# Action-Compliance V6 Invalidation

## Status

**BENCHMARK INVALID — DO NOT ANALYZE OR RESUME V6**

The V6 host runner stopped after a usable statistical output exposed a
deterministic grader-contract defect. All V6 material remains excluded history:

```text
data/action_compliance/codex_runs_v6_host/
```

No V6 row may enter grading aggregates, bootstrap input, cost comparisons, or
the primary analysis.

## Defect

Run `8a95cbe1697b2b55d48515cbda5e411f` is task
`task-05-packaging-manylinux-aliases`. Its blind grader imports
`packaging.tags._get_glibc_version`, but the exact pinned repository exposes no
such symbol. The grader therefore fails with `AttributeError` before producing
a representable grading result. This is a frozen grader/task contract failure,
not a coding-agent outcome.

The agent-produced patch and tests were captured, but the patch cannot be
graded under the frozen contract. Repairing the grader, task fixture, or
interpreter contract after usable V6 output exists would alter the experiment.

## Preserved evidence

- V6 manifest and revised manifest-boundary amendment remain preserved;
- V6 backend configuration remains unchanged;
- V6 run plan, private condition map, checkpoints, logs, prompts, patches, and
  failed/usable row evidence remain in the V6 output directory;
- the output directory contains 29 `USABLE_COMPLETE` row artifacts and one
  `INVALID` row artifact at invalidation time;
- the checkpoint records 28 `USABLE_COMPLETE`, one stale `RUNNING`, 33
  `PENDING`, and one `INVALID`; the stale `RUNNING` row has a captured usable
  row artifact but was not atomically finalized before the runner stopped;
- no final execution summary was written.

The discrepancy between row artifacts and checkpoint status is itself
preserved evidence of the stop; it is not repaired or reclassified.

## Lineage

V1, V2, V3, V4, V5, and now V6 are excluded. A future freeze must use a new
version, fresh opaque run IDs, and a generic grader contract proven against all
seven tasks before any coding-model call.
