# E2D-EXT3 Result — Legacy/Unclassifiable Timestamp Fallback

**Verdict: PASS.** All 8 checks in `PLAN.md` hold. A record with no
authoritative admission time (`admitted_at = None`, simulating a legacy
in-memory record) is correctly never treated as outside the window; the
implemented fallback (whole-source quarantine, `DYNAMIC_TRUST_MODEL.md`
option 1) escalates root selection to the whole `vendor_portal.lookup`
source once any of its records is unclassifiable, correctly affecting the
legacy record itself and — as the design's own named tradeoff — the
previously-safe outside-window sibling too, without leaking to unrelated
sources.

Full detail in `result.json`.

## Baseline check, reported honestly

Before implementing a fallback, the unmodified E2D mechanism was run
directly against this fixture. It **crashes** (`TypeError`, comparing
`None` to a timestamp string) rather than silently granting authority —
a safe direction to fail in, but not the graceful behavior the design
specifies. Worth naming precisely: in this codebase's `effective_cap`
(the fail-closed fix from E2D's own adversarial review), an activation
that never produces a plan makes *every* record under *any* active window
read `NONE` indefinitely — broader collateral than the design's own
"whole-source" fallback describes, since it isn't scoped to the
problematic source at all. This extension replaces that crash with the
design's actual specified behavior.

## Adversarial check on this result specifically

The concern: does `legacy_record_affected` actually test anything, or
would it trivially pass regardless of correctness? Checked directly by
building the natural wrong shortcut — silently skip any record with an
unclassifiable timestamp instead of escalating, which is exactly the
"interpreted as outside the window" failure `DYNAMIC_TRUST_MODEL.md`
explicitly forbids. Under that mutation, `E-LEGACY-1` comes out
*unaffected* (wrong). The actual mechanism under test correctly affects
it. Confirms the check has real discriminating power for the specific
failure mode it's named for.

## What this does not test

`LEGACY_UNKNOWN` quarantine (`DYNAMIC_TRUST_MODEL.md`'s alternative
fallback option 2) is not implemented or tested — only whole-source
quarantine (option 1). Huge/manifest-based parent lists remain untested
after all four E2D runs (core + three extensions) to date.

## Scope

Same scope limit as every prior E2D run: validates the design on a
constructed fixture, does not touch `custody/*.py`, does not establish
that a real production admission path (Firestore `create_time`, SQLite,
in-memory) correctly reports `None`/unclassifiable in exactly the cases
`DYNAMIC_TRUST_MODEL.md`'s "Authoritative timestamp requirement" section
names.
