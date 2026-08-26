# Action-Compliance Test/Interpreter Contract V6

## Status

V6 is the frozen pre-model execution contract following the prior invalidated
statistical runs. It changes execution plumbing only. All benchmark prompts,
contexts, summaries, AuthorityProofs, task definitions, graders' semantic
checks, and statistical rules remain frozen.

No V6 statistical model call is permitted until the 14 sanity replays and the
63-cycle model-free orchestration/storage gates pass.

## Single source of truth

`scripts/setup_action_compliance_full_worktree.py` creates a complete pinned
worktree and writes `.decisiontrace_setup_metadata.json`. It owns:

- `interpreter`;
- the complete `test_command` argv list;
- `test_cwd`;
- `test_env`; and
- `test_runner`, the language-specific observation mode.

The runner and every task grader consume this metadata verbatim. No consumer
reconstructs a command from a task name or guesses a host interpreter.

The contract version is `test-command-v2`. Supported observation modes are
`django-runtests`, `pytest`, `cpython-unittest`, `go-test`, and `cargo-test`.

## Outcome normalization

`scripts/action_compliance_test_contract.py` maps the process result to one of:

- `executed_with_tests`: the declared runner reports one or more tests and
  their pass/fail result;
- `executed_zero_tests`: the declared runner explicitly reports zero tests;
- `test_build_failed`: the declared command reached a language build phase but
  compilation prevented tests from running;
- `test_collection_failed`: a Python test runner reached collection and failed
  before running tests;
- `test_command_error`: the declared command could not address its target;
- `test_timeout`: the declared command exceeded its timeout; or
- `unknown`: the output is not representable by the frozen mode.

`NO_TESTS_RAN` is true only for `executed_zero_tests`. `TESTS_PASS` is true
only for `executed_with_tests` with exit code 0. Build failures and collection
failures are known negative outcomes, not zero-test passes and not unknown.

Rows with an unparseable grader result or `unknown` test status are marked
`INVALID`; the V6 runner stops and preserves the freeze rather than repairing
it after a model output exists.

## Corrected focused commands

The two Python tasks whose model-created focused tests use pytest now use
pytest explicitly while suppressing unrelated repository-level configuration:

- task-03: `python -m pytest -q -o addopts= --confcutdir=tests/unit tests/unit/test_script_metadata.py`;
- task-05: `python -m pytest -q tests/test_manylinux_pep600.py`.

This does not change the requested coding task or its semantic grader. It
ensures the test file the agent was asked to add is actually exercised without
requiring unrelated pip test plugins.

The Django, CPython, Go, and Cargo commands retain their task-specific frozen
behavior and are now consumed identically by the independent verifier and
grader.

## Required gates

1. Seven task contracts resolve exact pinned SHAs, complete non-sparse trees,
   executable interpreters, and commands beginning with those interpreters.
2. All 14 sanity patches capture tracked and new files with the staged binary
   diff, produce the expected authority outcomes, execute tests, and reset
   clean.
3. The classifier regression suite covers pass, fail, zero-test, build-fail,
   collection-fail, and command-error cases.
4. The 63-row model-free orchestration consumes the contract verbatim and
   makes zero model calls.
5. Production diff is empty before the V6 manifest is frozen.
