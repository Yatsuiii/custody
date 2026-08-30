# E2D-EXT1 Plan — Window Widening

E2D's frozen fixture (`research/experiments/E2D_DESIGN_FALSIFIER/`) does not
exercise window widening, which `research/design/DYNAMIC_TRUST_MODEL.md`
names as a required behavior:

> A wider correction creates a new generation. [...] Widening produces a new
> generation whose affected set is a superset. [...] New generation processes
> only the newly added closure plus any previously incomplete work.

This is operationally realistic: a first incident report is narrow, and a
correction widens it once more is known. This extension tests that specific
behavior. It does not modify E2D's frozen scenario, metrics, or gates —
per `DESIGN_FALSIFIER.md`'s own rule, changing a fixture creates a new
experiment number, which is exactly what this is.

## Fixture: E2D's fixture, plus one new root

Everything in E2D's `PLAN.md` fixture, unchanged, plus:

- `E-VENDOR-3`: a third `vendor_portal.lookup` `ORIGIN` root,
  `admitted_at = 2026-08-20T09:00:00Z` — outside generation 1's window
  `[2026-08-12T00:00:00Z, 2026-08-19T00:00:00Z)`, inside a widened
  generation 2 window `[2026-08-12T00:00:00Z, 2026-08-22T00:00:00Z)`.
- `E-VENDOR-3-PARA`: `summarize_v1` (`FREEFORM`) over `E-VENDOR-3`,
  `admitted_at = 2026-08-20T09:05:00Z`.

## Sequence

1. Run generation 1 exactly as E2D does: activate `W1` (end
   `2026-08-19T00:00:00Z`), apply repair to completion. `E-VENDOR-2` and
   `E-SYN-ACT-ACT` become affected, as in E2D.
2. Widen: report a correction that `W1`'s true end is
   `2026-08-22T00:00:00Z`. This must produce generation 2, not overwrite
   generation 1's record.
3. Recompute roots and closure for generation 2 against the wider window.

## Required outcomes

- **Superset.** `affected_ids(generation 2) ⊇ affected_ids(generation 1)`.
  Concretely: `E-VENDOR-2` and `E-SYN-ACT-ACT` remain affected, and
  `E-VENDOR-3` is newly affected. `E-VENDOR-3-PARA` is capped `INFORM`
  regardless of window state (it's `FREEFORM`), so it is not a required
  member of the affected *closure* the same way `E-VENDOR-3` is, but its
  support must include `E-VENDOR-3` correctly.
- **No reprocessing of completed outcomes.** Generation 1's outcomes for
  `E-VENDOR-2` and `E-SYN-ACT-ACT` (`DELETED`) must be preserved unchanged
  in generation 2's plan, not recomputed or duplicated.
- **New generation, old record preserved.** The generation-1 window record
  must still exist with `state = SUPERSEDED`, not be erased or mutated in
  place. A generation-2 record exists with `state = ACTIVE`.
- **Unaffected sibling stays unaffected.** `E-BENIGN-1` and
  `E-BENIGN-IDENTITY-1` (admitted 2026-08-05/06, outside even the widened
  window) remain `LIVE` and `ACT`-eligible under generation 2.
- **No narrowing side effect.** Widening never re-enables anything that was
  already blocked; it can only add, never remove, from the affected set.

## What this does not test

Overlapping windows from *different* incident reports (union-at-evaluation,
per `DYNAMIC_TRUST_MODEL.md`), `LEGACY_UNKNOWN` timestamp fallback, and
huge/manifest-based parent lists remain untested after this extension too —
named here so they aren't silently forgotten, not run in this pass.
