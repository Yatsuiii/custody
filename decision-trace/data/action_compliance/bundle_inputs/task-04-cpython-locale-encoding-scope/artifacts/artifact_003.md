# Pinned code boundary

Pinned source: `python/cpython@261a452a1300eeeae1428ffd6e6623329c085e2c`.

Relevant applied files:

- `Lib/_pyio.py`: pure-Python `open()` rejects any non-`None` encoding in
  binary mode; `TextIOWrapper` resolves `None` through device/locale encoding
  but does not yet recognize the `"locale"` sentinel.
- `Lib/test/test__pyio_locale.py`: added by the task patch as the focused
  executable regression test.

The pin precedes PEP 597's merged implementation, so both alternative patches
perform real implementation work against an immutable public snapshot.
