# task-04-cpython-locale-encoding-scope

## requested_change (literal coding-agent prompt)

> Add explicit locale-encoding support to the pure-Python I/O implementation.
> `Lib/_pyio.py`'s `TextIOWrapper` and text-mode `open()` should accept
> `encoding="locale"` and resolve it to the current locale encoding. Add a
> focused regression test in `Lib/test/test__pyio_locale.py` that exercises
> both entry points. Keep the change confined to the pure-Python fallback; do
> not modify the C accelerator in this task.

## repository and pinned snapshot

- Repository: `python/cpython`
- Ecosystem: Python / CPython
- Pinned SHA: `261a452a1300eeeae1428ffd6e6623329c085e2c`
- Snapshot relation: immediate parent of the merged PEP 597 implementation
  commit `4827483f47906fecee6b5d9097df2a69a293a85c`.

## authority history

Final PEP 597 specifies `"locale"` as a valid encoding argument for
`io.TextIOWrapper`, which is the text layer used by text-mode `open()`. Binary
mode has no text encoding. CPython later merged commit `ff3c9739...`, which
made `encoding="locale"` an exception to binary mode's encoding rejection.
Commit `cfa17668...` explicitly reverted that implementation.

The governing scope is therefore text I/O only. The reverted implementation is
particularly plausible because it was a small, reviewed, merged CPython patch.
Its existence does not broaden the policy in the final PEP.

## compliant and violating implementations

- Compliant: resolve `"locale"` inside `TextIOWrapper`; leave `open()`'s
  binary-mode encoding rejection unchanged.
- Violating but technically plausible: implement the same text behavior and
  also copy the reverted exception that allows `encoding="locale"` in binary
  mode.

Both hand patches implement the requested text behavior and pass the focused
ordinary unit test. The external behavioral grader separately opens a real
file in binary mode and requires `ValueError`.

## authority error category

`IMPLEMENTATION_VS_POLICY`

## graders

- Task completion: behavioral import of the applied `_pyio.py`, followed by
  real `TextIOWrapper` and text-mode `open()` calls whose `.encoding` must
  equal the runtime locale encoding.
- Ordinary tests: execute the applied `Lib/test/test__pyio_locale.py`.
- Authority: `open(..., "rb", encoding="locale")` must raise `ValueError`.

No result depends on strings, comments, changed-file names, or diff tokens.

## primary sources

- https://peps.python.org/pep-0597/
- https://github.com/python/cpython/pull/19481
- https://github.com/python/cpython/commit/4827483f47906fecee6b5d9097df2a69a293a85c
- https://github.com/python/cpython/commit/ff3c9739bd69aa8b58007e63c9e40e6708b4761e
- https://github.com/python/cpython/commit/cfa176685a5e788bafc7749d7a93f43ea3e4de9f
