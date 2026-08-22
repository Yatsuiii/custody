# Binary-mode implementation history

Primary sources:

- https://github.com/python/cpython/commit/ff3c9739bd69aa8b58007e63c9e40e6708b4761e
- https://github.com/python/cpython/commit/cfa176685a5e788bafc7749d7a93f43ea3e4de9f

On 2021-03-31, `ff3c9739...` changed both the Python and C `open()` guards so
binary mode accepted `encoding="locale"`. Its commit message framed the change
as making the value usable everywhere that `encoding=None` was allowed.

Later the same day, `cfa17668...` explicitly reverted that commit and restored
the unconditional rule that binary mode rejects every non-`None` encoding.
The final PEP remained in force; only the over-broad implementation was
reverted.
