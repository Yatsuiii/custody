# E2D-EXT4 Plan — Manifest-Based (Huge) Parent Lists

`research/design/TRANSFORMATION_MODEL.md`: "`input_manifest_id` is used
only when the bounded inline parent list is too large. The manifest is
immutable, count-checked, and content-digested. [...] Parent ids are
never silently truncated. [...] If manifest expansion is unavailable,
exceeds the configured verification bound, or any chunk is missing, the
output becomes `INCOMPLETE`." Not tested by E2D or EXT1-3. Does not modify
E2D's frozen scenario or gates.

## Mechanism under test

A manifest-admitted output declares `(chunks, declared_count,
declared_digest)` instead of an inline `direct_parent_ids` tuple.
Admission must:

1. expand every chunk to a flat list of parent ids;
2. verify the expanded count equals `declared_count`;
3. verify `sha256(sorted(expanded_ids))` equals `declared_digest`;
4. verify every expanded id actually exists in the graph (no dangling
   reference); and
5. only if all four hold, proceed as an ordinary derivation over the
   expanded parents (same meet/support computation as the inline path) —
   otherwise admit as `INCOMPLETE` (`INFORM` cap, `UNKNOWN_CONTEXT` in
   support), never a fresh trusted root and never a silent partial
   expansion.

## Fixture: E2D's fixture, admitted via manifest instead of inline

Three cases, reusing E2D's existing roots as the parents being referenced
(`E-BENIGN-1` = `ACT`, `E-VENDOR-2` = `ACT`, `E-MAL-1` = `NONE`):

1. **`E-MANIFEST-OK`**: chunks `[["E-BENIGN-1", "E-VENDOR-2"],
   ["E-MAL-1"]]`, correct declared count (3) and digest. Must behave
   identically to an inline `REGISTERED` derivation over the same three
   parents: `cap = min(merge_v1_cap, ACT, ACT, NONE) = NONE`, support is
   the union of all three closures.
2. **`E-MANIFEST-DIGEST-MISMATCH`**: same chunks and count, but a
   deliberately wrong declared digest (as if a chunk were tampered with
   in transit). Must become `INCOMPLETE`, never fall back to computing
   from whatever expanded successfully.
3. **`E-MANIFEST-MISSING-CHUNK`**: chunks reference a parent id that does
   not exist in the graph (`E-DOES-NOT-EXIST`). Must become `INCOMPLETE`,
   not silently proceed with only the ids that do resolve.

## Required outcomes

- `E-MANIFEST-OK`'s cap and support exactly match what an inline
  `admit_derived` over the same three parents would produce — the
  manifest path is not a different, weaker mechanism.
- `E-MANIFEST-DIGEST-MISMATCH` and `E-MANIFEST-MISSING-CHUNK` both admit
  as `INCOMPLETE`: capped `INFORM`, `UNKNOWN_CONTEXT` in support, and
  critically — the *declared* parent ids (or the ones that did resolve)
  do **not** silently become the effective support set. A naive
  implementation might expand what it can and proceed with a partial,
  smaller-than-declared parent set; that is exactly the "silently
  truncated" failure the design forbids.
- Neither failure case falls back to treating the output as a fresh,
  parentless trusted root.

## What this does not test

This is the last of the four gaps named across E2D and EXT1-3. No further
named gaps remain from `DYNAMIC_TRUST_MODEL.md`/`TRANSFORMATION_MODEL.md`
after this one, though neither document claims to be exhaustive.
