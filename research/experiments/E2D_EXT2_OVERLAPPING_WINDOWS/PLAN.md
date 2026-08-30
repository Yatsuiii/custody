# E2D-EXT2 Plan — Overlapping Windows From Separate Incident Reports

`research/design/DYNAMIC_TRUST_MODEL.md`: "Overlapping windows from
different incident reports union at evaluation." This is distinct from
E2D-EXT1's widening: widening bumps *one* window's generation; this tests
*two separate, independent* `RevocationWindow` records (different ids,
possibly reported by different people, at different times) whose union
determines effective authority. Does not modify E2D's frozen scenario or
gates — a new experiment number per `DESIGN_FALSIFIER.md`'s own rule.

## Fixture: E2D's fixture, plus a deliberate gap

Everything in E2D's `PLAN.md` fixture, unchanged, plus:

- `E-GAP-1`: a `vendor_portal.lookup` `ORIGIN` root,
  `admitted_at = 2026-08-19T12:00:00Z` — deliberately placed in the gap
  *between* `W1`'s end (`2026-08-19T00:00:00Z`) and `W2`'s start
  (`2026-08-21T00:00:00Z`, below). This is the sharpest check: a naive
  implementation might treat two windows' union as one merged interval
  spanning from the earlier start to the later end, which would
  incorrectly sweep this record in. The correct union treats the two
  intervals as genuinely disjoint.
- `E-VENDOR-W2`: a `vendor_portal.lookup` `ORIGIN` root,
  `admitted_at = 2026-08-21T09:00:00Z` — inside `W2`'s range.
- `E-SYN-BOTH`: `merge_v1` (`REGISTERED`) over `E-VENDOR-2` (affected via
  `W1`) and `E-VENDOR-W2` (affected via `W2`) —
  `admitted_at = 2026-08-21T09:05:00Z`. Its support intersects both
  windows' closures independently; it must be blocked by the union
  regardless of which window is evaluated first.

## Two independent windows

- `W1`: exactly E2D's window, `vendor_portal.lookup`,
  `[2026-08-12T00:00:00Z, 2026-08-19T00:00:00Z)`, reported
  `2026-08-20T00:00:00Z`.
- `W2`: a **separate incident report**, same source/operation,
  `[2026-08-21T00:00:00Z, 2026-08-24T00:00:00Z)`, reported
  `2026-08-25T00:00:00Z`. Not a widening of `W1` — a distinct window id,
  activated independently, both simultaneously `ACTIVE`.

## Required outcomes

- `E-VENDOR-2` and `E-SYN-ACT-ACT` (from E2D's own scenario) remain
  affected via `W1`.
- `E-VENDOR-W2` becomes affected via `W2`.
- `E-SYN-BOTH` is affected (support intersects both windows'
  closures — the union catches it regardless of which window "owns" the
  block).
- **`E-GAP-1` remains unaffected and `ACT`-eligible.** This is the
  required-negative case: the gap between the two windows must not be
  swept in by a sloppy union implementation.
- `E-BENIGN-1`/`E-BENIGN-IDENTITY-1` (outside both windows entirely)
  remain unaffected, as in every prior fixture.
- Deactivating (or never activating) either window alone must not affect
  the other window's own closure — independence, not just union at the
  effective-cap layer.

## What this does not test

`LEGACY_UNKNOWN` timestamp fallback and huge/manifest-based parent lists
remain untested after this extension too.
