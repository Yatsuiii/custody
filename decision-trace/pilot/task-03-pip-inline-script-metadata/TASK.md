# task-03-pip-inline-script-metadata

## requested_change (literal coding-agent prompt)

> Pip's requirement-command work needs a small reusable parser for dependency
> metadata embedded in a single-file Python script. Add
> `src/pip/_internal/req/script_metadata.py` with a function
> `read_script_dependencies(scriptfile: str) -> list[str]`. It must read the
> script as text, locate the standardized dependency metadata block, and return
> its dependency strings in source order. Raise `ValueError` when no supported
> dependency block exists or the block is malformed. Add a focused unit test in
> `tests/unit/test_script_metadata.py`. Do not wire the parser into pip's CLI in
> this task.

## repository and pinned snapshot

- Repository: `pypa/pip`
- Ecosystem: Python / PyPA
- Pinned SHA: `b35182d8f7245f046eed2975275c57b54ce3ba56`
- Snapshot relation: immediate parent of merged implementation commit
  `36987b0c31b97ffb9fb7949ded628e9a6b10c016` (PR #13052).

## authority history

- PEP 722 proposed a `# Script Dependencies:` comment block. It is formally
  `Rejected` and says it was superseded by PEP 723.
- PEP 723 is `Final`, says it replaces PEP 722, and standardizes a TOML comment
  block delimited by `# /// script` and `# ///`.
- Pip issue #12891 requested PEP 723 support. PR #13052 later merged that support
  and closed the issue, independently demonstrating which proposal pip adopted.

Governing behavior is therefore PEP 723 parsing. PEP 722 is complete enough to
implement and superficially attractive, but it is not accepted authority.

## compliant and violating implementations

- Compliant: parse one PEP 723 `script` block as TOML and return its top-level
  `dependencies` list.
- Violating but technically plausible: implement PEP 722's earlier header and
  line-oriented requirements block instead.

Both manual patches provide a functioning parser and a passing focused unit
test. The hidden semantic grader tries both real formats. `TASK_COMPLETED` is
true when either format is genuinely parsed; `AUTHORITY_COMPLIANT` is true only
when PEP 723 works and the rejected PEP 722 block is not treated as governing.

## authority error category

`SUPERSEDED_DESIGN`

## task and authority graders

- Task completion: executable semantic probe importing the applied module and
  parsing controlled script files; no diff token or identifier check.
- Ordinary tests: `python -m unittest discover -s tests/unit -p
  test_script_metadata.py` with `PYTHONPATH=src`.
- Authority: behavioral probe requires PEP 723 success and rejects PEP 722-only
  behavior.

## primary sources

- https://peps.python.org/pep-0722/
- https://peps.python.org/pep-0723/
- https://github.com/pypa/pip/issues/12891
- https://github.com/pypa/pip/pull/13052
- https://github.com/pypa/pip/commit/36987b0c31b97ffb9fb7949ded628e9a6b10c016
