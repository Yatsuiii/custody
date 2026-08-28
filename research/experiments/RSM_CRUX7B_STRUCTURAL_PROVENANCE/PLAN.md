# RSM Crux7b — Same Pool, With Explicit Provenance Tags

Direct follow-up to crux7's miss: memory #2 (the 2-hop dependent) wasn't
flagged when the pool was plain text with no recorded chain. This tests
the fix crux7's own `RESULT.md` argued for: does recall become reliable
once each memory carries an explicit, structural `derived_from`-style
provenance tag — matching what Custody's real design already records at
write time (`AdmissionEnvelope.direct_parent_ids`, per
`research/design/TRANSFORMATION_MODEL.md`), rather than asking the model
to reconstruct the chain from reading text cold.

This is not testing whether structural traversal works — E2D and its four
extensions already proved that deterministically, with no LLM in the loop
at all. This tests something narrower and specific to the LLM-judgment
side of the crux series: does adding a one-line provenance annotation to
each pool item change crux7's recall, and does it hold precision on the
adversarial distractors even when they *also* carry (unrelated) provenance
text that could look superficially similar.

## Fixture: crux7's exact pool, plus one `provenance` field per item

Every pool item, text and label unchanged from crux7. Added: a one-line
`provenance` string per item, given to the model alongside the text.

- `#1`: provenance points directly at the revoked source's own record
  (the Sarah Chen personnel update).
- `#2`: provenance points at `#1` by number — *not* at the original
  revoked source directly, mirroring how a real derivation graph records
  only the direct parent, not the full ancestry, at each edge.
- `#3`-`#9` (unrelated negatives): each gets its own real, unrelated
  provenance (their actual crux5/6 source facts), including two that are
  themselves derivation edges pointing at other pool numbers, so the
  model has to actually check *which* chain a provenance edge leads to,
  not just notice that a provenance field exists.
- `#10`-`#12` (adversarial negatives): each gets plausible but unrelated
  provenance (e.g. `#11`, about James Park, points at a separate,
  different personnel record), keeping the adversarial pressure real
  rather than trivially defeated by the mere presence of a provenance tag.

## Method

Same single-call format as crux7, with each pool line now
`{num}. {text} [provenance: {provenance}]`. Same identify prompt, same
scoring.

## Bar, stated before seeing results

If recall reaches 1.0 (both #1 and #2 correctly flagged) while precision
holds at 1.0 including the adversarial cases, that directly confirms
crux7's own conclusion: the bottleneck was missing structural information,
not an inherent judgment limit, and it closes cleanly once that
information is present in even a minimal, one-line form. If #2 is still
missed even with its provenance explicitly stating `derived from #1`,
that would be a genuinely surprising negative result worth real scrutiny
of the prompt and model before drawing further conclusions.
