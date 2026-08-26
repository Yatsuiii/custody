# V2 Phase 9 invalidation

**HARNESS EXECUTION FROM INVALIDATED V2 FREEZE — EXCLUDED**

V2 Phase 9 is invalidated and must not be resumed or analyzed. All V2
comparative material is preserved under:

`data/action_compliance/invalidated_v2_test_discovery_run/`

The archive contains the V2 run plan, fresh condition map, resume state, first
usable patch, model logs, grader output, test verification, V2 protocol, V2
backend configuration, V2 backend hash, and V2 manifest checksum file.

## Trigger

The first usable V2 output was run ID
`f1fba26dcf594d8ed0b1525106851ad5`, task
`task-02-django-index-together-superseded`. Its full-worktree patch capture
passed, but the independent test verifier invoked:

```text
/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python runtests.py model_indexes -v1
```

The V2 setup had installed Django into the task worktree's `.venv`, while the
verifier used the system Python. The verifier therefore recorded:

```text
ModuleNotFoundError: No module named 'django'
TESTS_EXECUTED=false
TEST_EXECUTION_STATUS=unknown
```

The frozen task grader used the venv and reported `TESTS_PASS=true`, exposing a
generic harness inconsistency between independent test verification and grader
execution. This is a deterministic test-discovery infrastructure defect after
usable comparative output began.

## Exclusion and disposition

V2 produced 1 usable Codex output and no complete statistical dataset. A second
Codex call was interrupted immediately after the defect was detected; it has no
usable output. No remaining scheduled V2 runs were continued.

The V2 output and failed/in-flight attempt are excluded from the final dataset,
grading table, bootstrap input, cost comparison, and primary analysis. V2 must
not be repaired and resumed. Any future experiment requires a new freeze with a
generic test-interpreter contract fixed before model execution.
