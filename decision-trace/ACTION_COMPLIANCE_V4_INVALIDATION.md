# DecisionTrace Action-Compliance Experiment — V4 Invalidation

**Date:** 2026-08-26  
**Lane:** optimization/research engineering / evidence-gated agentic developer tooling  
**Disposition:** **BENCHMARK INVALID — FIX BEFORE CONCLUDING**

## Decision

V4 is permanently excluded from statistical analysis. No V4 row may be
graded, unblinded, bootstrapped, used in a cost comparison, or joined to the
private condition map.

This invalidation follows the frozen V4 harness-defect policy: after usable
statistical output exists, a deterministic defect in test interpretation or
grading infrastructure requires stopping all new runs and invalidating the
freeze. Repair-and-resume is prohibited.

## Evidence preserved

The complete V4 evidence remains at:

`data/action_compliance/codex_runs_v4_host/`

Preserved material includes the 63 row directories, captured patches, prompts,
Codex logs, usage metadata, grading outputs, test-verification outputs, and
checkpoint state. The checkpoint contains 63 `USABLE_COMPLETE` row statuses.
The host summary reported 63 usable rows and no final-run infrastructure
failures; this status means that a model output and patch were captured. It
does **not** mean that the row is valid statistical evidence.

The checkpoint's legacy `stop_reason` still contains an earlier disk-guard
message even though the final row inventory is complete. That state was not
rewritten or used to manufacture a completion claim; it is preserved as part
of the excluded V4 evidence.

The earlier V1, V2, V3, and Claude pilot material remains excluded history and
is not incorporated here.

## Deterministic defect

The generic test/interpreter contract and its result classifier do not reliably
represent the frozen test commands used by all seven tasks. The runner marks a
row `USABLE_COMPLETE` after model output and patch capture even when the
grader is unparseable or the test result is zero-test/unknown. This violates
the requirement that executable grader evidence determine the recorded
outcome.

The 63-row audit found:

| Field | Count |
|---|---:|
| Captured rows / `USABLE_COMPLETE` | 63 |
| Parseable grader outputs | 57 |
| Unparseable grader outputs | 6 |
| Tests classified as executed | 36 |
| `NO_TESTS_RAN=true` | 16 |
| Unknown test-execution status | 11 |
| Approval prompts observed | 0 |

### Task-03

All 9 task-03 rows ran the frozen command and returned exit code 5 with:

```text
Ran 0 tests in 0.000s
NO TESTS RAN
```

The model-created `tests/unit/test_script_metadata.py` files were not
discovered by the frozen `unittest discover` command. This is a systematic
contract/discovery failure across all repetitions, not a usable task-level
metric.

### Task-05

All 9 task-05 rows were recorded with `TEST_EXECUTION_STATUS=unknown` despite
the command returning zero. Six of the nine task-05 grader invocations also
failed the required output parse. The runner therefore cannot distinguish a
real passing test execution from an unreported/ambiguous execution for this
task.

### Task-06

All 9 task-06 commands returned a Go build/test failure. At least the observed
cases contain ordinary compile errors, but the classifier records seven as
`executed_zero_tests` and two as `unknown` rather than representing the build
failure as an executed test-contract outcome. This further demonstrates that
the generic interpreter contract is not stable across languages and failure
modes.

## Why no analysis was performed

The following actions were intentionally not performed:

- no blind grading freeze;
- no condition-map join or unblinding;
- no run-level or task-level statistics;
- no bootstrap confidence interval;
- no strongest-control comparison;
- no GO-gate evaluation;
- no forensic taxonomy presented as experimental evidence.

The 63 V4 outputs are harness execution evidence only and must never be
treated as comparative results.

## Required future action

A new versioned freeze must correct the generic contract and runner before any
new model call. At minimum it must:

1. ensure each frozen command has a language-appropriate, deterministic
   execution classification, including zero-test, direct-script, and Go build
   failures;
2. retain `NO_TESTS_RAN` separately from `TESTS_PASS`;
3. reject or explicitly quarantine rows whose grader output is unparseable or
   whose required test status is unknown;
4. replay all 14 sanity patches and the complete 63-row model-free lifecycle
   under the new contract; and
5. start a completely fresh experiment with fresh opaque IDs. No V4 row,
   patch, grade, or usage record may be reused as statistical data.

Production code and benchmark content were not changed by this invalidation.
