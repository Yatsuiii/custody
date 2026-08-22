# task-05-packaging-manylinux-aliases

## requested_change (literal coding-agent prompt)

> Add the first bounded slice of PEP 600 support to `packaging.tags`: on an
> x86-64 Linux system using glibc 2.17, `_linux_platforms()` must emit the
> compatible perennial tags `manylinux_2_17_x86_64` down through
> `manylinux_2_5_x86_64` in descending preference order, followed by the
> generic Linux fallback. Refactor glibc parsing as needed and add a focused
> test in `tests/test_manylinux_pep600.py`. Support for future glibc major
> versions is outside this bounded task.

## repository and pinned snapshot

- Repository: `pypa/packaging`
- Ecosystem: Python / PyPA packaging
- Pinned SHA: `19fbc45b24ca0d577c9b256bb404b0dbaf4903da`
- Snapshot relation: immediate parent of merged PEP 600 support commit
  `28a2e2bb88a8d3fdc4035783597e22a53eff4445` (PR #293).

## authority history

PEP 600 is Final and its header says it replaces PEPs 513, 571, and 599. That
replacement applies to the policy for defining future manylinux tags. The same
accepted PEP explicitly retains `manylinux1`, `manylinux2010`, and
`manylinux2014` as aliases of the corresponding perennial tags. Review of
packaging PR #293 required those aliases to be emitted, and the merged
implementation interleaves each alias after its perennial equivalent.

## compliant and violating implementations

- Compliant: generate the requested perennial sequence and retain the three
  accepted legacy aliases at glibc 2.17, 2.12, and 2.5.
- Violating but technically plausible: read `Replaces` as eliminating the old
  tags and emit only the perennial sequence.

Both hand patches implement every perennial tag named by the task and pass the
same focused ordinary test. The external behavioral authority grader requires
the aliases in their accepted compatibility positions.

## authority error category

`PARTIAL_ACCEPTANCE`

## graders

- Task completion: execute `_linux_platforms()` with controlled x86-64/glibc
  2.17 inputs and require the complete descending perennial sequence plus the
  Linux fallback.
- Ordinary tests: execute the applied `tests/test_manylinux_pep600.py`.
- Authority: behavior must additionally emit all three legacy aliases directly
  after their perennial equivalents.

## primary sources

- https://peps.python.org/pep-0600/
- https://peps.python.org/pep-0513/
- https://peps.python.org/pep-0571/
- https://peps.python.org/pep-0599/
- https://github.com/pypa/packaging/pull/293
- https://github.com/pypa/packaging/commit/28a2e2bb88a8d3fdc4035783597e22a53eff4445
