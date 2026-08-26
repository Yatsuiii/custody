# Action-Compliance Test-Interpreter Contract V3

## Status

This is a pre-model infrastructure artifact for the replacement experiment.
No Codex statistical call is permitted until the contract verification and
sanity replay recorded in `data/action_compliance/test_interpreter_contract_v3/`
pass.

V2 was invalidated after its first usable output because the independent test
verifier hardcoded the host Python interpreter while task-02 dependencies were
installed in the worktree virtualenv. That produced a false infrastructure
state: the task grader used Django's `.venv`, while independent verification
reported `ModuleNotFoundError: No module named django`.

## Contract

`scripts/setup_action_compliance_full_worktree.py` is the sole owner of test
interpreter resolution. After checkout and dependency preparation it writes
`.decisiontrace_setup_metadata.json` in the worktree with:

- `contract_version`: `test-command-v1`
- `grader_interpreter`: executable used to invoke the frozen Python grader
- `interpreter`: executable or command name used by the test runner (`.venv/bin/python`,
  `go`, or `cargo`)
- `test_command`: complete argv list, beginning with `interpreter`, executed
  verbatim by independent verification
- `test_cwd`: worktree-relative working directory
- `test_env`: exact task test environment additions
- `interpreter_kind`: explicit provenance such as `worktree_venv`,
  `pinned_host_python`, `setup_host_python`, or `non_python_test_runner`
- `pinned_sha`, `full_worktree`, and `sparse_checkout` invariants

The production runner reads this file for both `_grader_args` and `_test_spec`.
It does not independently infer `.venv`, select a task-specific host Python, or
reconstruct a test command from task branches. The command recorded by setup is
the command executed by verification.

The frozen task semantics are preserved. For example, task-02 records its
Django `tests/runtests.py model_indexes -v1` command through the venv launcher;
it is not silently changed to pytest. The Go task records its existing overlay
test command through `go`.

The setup metadata is ignored through `.git/info/exclude`, so it is not part of
the coding-agent patch. It survives reset/cleanup and is recreated for every
fresh worktree.

## Required gates

1. All seven full pinned worktrees emit valid metadata with exact SHA and no
   sparse checkout.
2. Every declared interpreter exists or resolves on `PATH`, and every complete
   command begins with that interpreter.
3. The task-02 focused test executes through its worktree `.venv`, with no
   host-environment `ModuleNotFoundError`.
4. All 14 frozen sanity patches are captured, graded, independently tested,
   and reset clean using the contract consumers.
5. The replay reports zero model calls.

Failure of any gate blocks a new statistical freeze. This contract change is
generic infrastructure; it contains no task prompt, context, grader logic, or
statistical design change.

## Model-free gate result

The V3 replay recorded at
`data/action_compliance/test_interpreter_contract_v3/results.json` passed:

- 7/7 interpreter contracts resolved against exact pinned SHAs
- 14/14 sanity patches captured with the staged binary-diff contract
- 14/14 grader invocations parsed and returned the expected authority result
- 14/14 independent test commands executed; zero-test and failed-test states
  remain distinct from `TESTS_PASS`
- task-02 used its worktree `.venv/bin/python` and ran 31 tests successfully on
  the compliant patch
- every worktree reset clean after each case
- `model_calls=0`

This is a passed pre-model gate. It does not authorize reuse of V2 output or
resume V2. A new protocol/manifest freeze is still required before any V3
statistical execution.
