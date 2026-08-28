# E2D-EXT4 Result — Manifest-Based (Huge) Parent Lists

**Verdict: PASS.** All 10 checks in `PLAN.md` hold. A manifest-admitted
output with a correct count and digest behaves identically to the same
derivation admitted inline (same cap, same support) — the manifest path
is not a separate, weaker mechanism. A tampered digest and a manifest
referencing a nonexistent record both correctly admit as `INCOMPLETE`
(`INFORM`, `UNKNOWN_CONTEXT` in support, zero declared parents retained),
never a partial expansion and never a fresh trusted root.

Full detail in `result.json`.

## Adversarial check on this result specifically, and why it matters here more than in the other extensions

Built the natural wrong shortcut: a manifest expander that silently
proceeds with whatever chunk ids happen to resolve, ignoring count/digest
verification entirely — exactly "silently truncated," which
`TRANSFORMATION_MODEL.md` names explicitly as forbidden. Ran it against
the missing-chunk case (a manifest referencing `E-BENIGN-1` — real,
`ACT`-capped — and `E-DOES-NOT-EXIST` — not in the graph at all).

**Result: `ACT`.** Not `INFORM`, not `INCOMPLETE` — a full `ACT`-capped
output, derived from a manifest whose declared reference set could not be
verified, because the naive path silently dropped the one id it couldn't
resolve and computed authority from what was left. This is a genuine
authority leak, not a hypothetical: an attacker (or a corrupted/truncated
manifest in transit, which is exactly the threat `TRANSFORMATION_MODEL.md`
names) could reference a real trusted parent plus a fabricated one, and a
naive implementation would grant full authority anyway. The mechanism
under test correctly refuses this (`missing_chunk_is_incomplete`,
`missing_chunk_no_partial_parents` both hold). This is the sharpest,
highest-consequence finding across all four E2D runs to date — the other
extensions' mutation failures were "wrong scope" (over- or
under-blocking); this one is "wrong authority."

## What this does not test

This closes the fourth and last gap named across E2D's own `RESULT.md`
and EXT1-3. Neither `DYNAMIC_TRUST_MODEL.md` nor `TRANSFORMATION_MODEL.md`
claims this set of four is exhaustive — a fresh reading of both docs
could surface more.

## Scope

Same scope limit as every prior E2D run: validates the design on a
constructed fixture, does not touch `custody/*.py`, does not establish
that a real production manifest-expansion path (whatever storage/transport
actually carries chunked parent references) implements count/digest
verification the way this fixture assumes it does.
