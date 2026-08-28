# RSM Crux7b Result — Structural Provenance Closes Crux7's Miss

**Recall: 1.0 (2/2). Precision: 1.0. Adversarial false-positive rate: 0.0
(0/3).** Same 12-item pool as crux7, same revoked source, same prompt
shape — the only change is a one-line `provenance` field per memory,
pointing at its direct source or, for `#2`, at memory `#1` by number
(one hop, not the full ancestry). Raw response: `"1, 2"`. Full detail in
`result.json`.

This confirms the bar `PLAN.md` set before running: crux7's miss on the
2-hop dependent (`#2`) closed completely once its provenance stated
`derived from memory #1` explicitly, rather than requiring the model to
infer that relationship from reading two pieces of prose cold.

## Why this is a real confirmation and not a trivially rigged one

Two design choices in the fixture existed specifically to prevent this
from being an easy win:

1. **`#2`'s provenance points at `#1` by number, not at the original
   revoked source directly.** The model still had to follow one hop of
   indirection — `#2 → #1 → revoked source` — not just pattern-match a
   repeated source name. This mirrors how Custody's real
   `AdmissionEnvelope.direct_parent_ids` actually works: each record
   names only its immediate parent, and a true multi-hop closure requires
   walking the chain, exactly what `custody/graph.py`'s traversal (and
   E2D's `closure()` function) does deterministically.
2. **Two negative memories (`#8`, `#9`) also carry provenance pointing at
   other pool numbers** (`#3`, `#4` — both unrelated to the revoked
   source). If the model were just flagging "anything with a
   pool-number provenance edge" rather than checking *which* chain it
   leads to, these would have been false positives. They weren't.

Combined with the three adversarial distractors (`#10`-`#12`, all with
their own plausible-but-unrelated provenance) also correctly staying
unflagged, this is real evidence the model followed the actual
chain-structure, not a shortcut that happened to work on this pool.

## What this changes, and what it doesn't

Confirms crux7's own diagnosis directly: the bottleneck in crux7 was
missing information, not a fundamental limit on the model's ability to
trace a two-step chain once that information is present. It does **not**
mean LLM-based identification is now validated for production use —
Custody's real identification mechanism doesn't need this validated at
all, because it already does exactly this via deterministic graph
traversal (E2D, PASS, no LLM in the loop, adversarially mutation-tested).
This result's actual value is narrower: it closes the loop on *why*
crux7's miss happened, with a controlled comparison rather than
speculation, and it reinforces — now with two independent pieces of
evidence pointing the same direction — that recording provenance
structurally at write time is the right design choice already reflected
in `research/design/TRANSFORMATION_MODEL.md`'s `direct_parent_ids`, not
a gap Custody needs an LLM to paper over.

## Scope

Still one pool, one revoked source, n=1 in the sense that matters (a
single test of "does one added hop of explicit provenance fix one
specific miss"). Not a claim that provenance tags fix identification at
arbitrary chain depth, pool size, or distractor density — those remain
untested, same as everywhere else in this series.
