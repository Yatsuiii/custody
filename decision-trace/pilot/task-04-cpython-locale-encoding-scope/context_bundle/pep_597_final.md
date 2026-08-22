# PEP 597 governing scope

Primary source: https://peps.python.org/pep-0597/

- Status: Final; Python version 3.10.
- The specification makes `"locale"` a valid `encoding` value for
  `io.TextIOWrapper`.
- `open()` reaches that text wrapper for text mode.
- The rationale says `"locale"` is not a codec alias because the locale may
  change at runtime and because `TextIOWrapper` has device-encoding behavior.

This is a text-encoding feature. It does not establish an encoding parameter
for binary streams.
