# E2D-EXT3 Plan — Legacy/Unclassifiable Timestamp Fallback

`research/design/DYNAMIC_TRUST_MODEL.md`: "An unclassifiable record for
the targeted source is never interpreted as outside the window. The safe
fallback is configurable only between: 1. whole-source quarantine/
revocation; or 2. `LEGACY_UNKNOWN` quarantine pending review." This tests
that requirement. Does not modify E2D's frozen scenario or gates.

## Baseline check, run first, reported honestly either way

Before building a fallback, the unmodified E2D mechanism (`RevocationController`,
`select_roots`) was run directly against a root with `admitted_at = None`.
It raises `TypeError` on the `<=` comparison — a crash, not a silent
fail-open. That is a safe direction to fail in (nothing gets wrongly
authorized), but it is not the graceful behavior the design specifies, and
in this codebase's `effective_cap` (fixed in E2D's own adversarial review),
an uncreated plan makes *every* record under *any* active window read
`NONE` indefinitely, not just the legacy source's records — a availability
cost broader than the design's own "whole-source" fallback describes. This
extension implements the design's actual specified fallback (whole-source
quarantine) instead of leaving the crash as the de facto behavior.

## Fixture: E2D's fixture, plus one unclassifiable root

- `E-LEGACY-1`: a `vendor_portal.lookup` `ORIGIN` root,
  `admitted_at = None` (unclassifiable — simulates a legacy/in-memory
  record with no authoritative server `create_time`, per
  `DYNAMIC_TRUST_MODEL.md`'s "Authoritative timestamp requirement").

## Fallback under test: whole-source quarantine

When any record targeted by a window's `(source_id, operation_id)` has an
unclassifiable timestamp, the whole source/operation is treated as
in-scope for that activation — every record from `vendor_portal.lookup`
becomes a root candidate, not just ones literally inside `[start, end)`.

## Required outcomes

- `E-LEGACY-1` is affected (it is never interpreted as outside the window
  merely because its time can't be compared).
- **The escalation cost is real and visible.** `E-BENIGN-1` and
  `E-BENIGN-IDENTITY-1` — normally outside `W1`'s time range and
  unaffected in every prior fixture — become affected too, because
  whole-source escalation does not distinguish "provably outside the
  window" from "inside" once any record from that source is
  unclassifiable. This is the design's own named tradeoff, not a bug;
  the test asserts it happens, not that it's avoided.
- **Escalation does not leak across sources.** `E-MAL-1`/`E-MAL-PARA-1`
  (a different, unvouched source) and `E-RELAY-1` (a different source)
  remain unaffected by `vendor_portal.lookup`'s escalation.
- The mechanism does not crash; it produces a definite plan.

## What this does not test

`LEGACY_UNKNOWN` quarantine (fallback option 2, an alternative to
whole-source quarantine) is not implemented or tested here — only option
1. Huge/manifest-based parent lists remain untested after this extension.
