# RSM Crux6 — Cascading Repair Through a Derivation Chain

Every prior round tested single-hop repair: one memory, its direct source
revoked, repair told exactly what was revoked. Real Custody derivation
chains are multi-hop by design — F1's own live proof is sales writes a
tool-origin fact, support derives from it, finance derives from support's
restatement, three hops, and revoking the root correctly pulls all three.
This test asks the same question crux4/5 asked, but one hop removed: if
a downstream memory M2 was derived from M1 (not from the original revoked
source directly), and M1 gets correctly repaired/retracted, does repairing
M2 — told only that *M1* was revised, never given the original root cause
— also correctly retract? This is the harder, more realistic case: at
each hop, repair only has its immediate parent's corrected state, not the
full causal history back to the original poisoned root.

## Fixture: crux5's 5 cases (dropping `tenure_pricing` for scope), each extended one hop

For each case: `rule` + `value_at_write_time` generate `M1` exactly as in
crux5. A new `downstream_role` and `downstream_prompt` generate `M2` —
a distinct memory, written by a different department/agent, that cites
only `M1`'s conclusion (never the original rule or value_at_write_time).
`revocation_notice` (same as crux5) repairs `M1`. A new step repairs `M2`
using **only the repaired M1 text**, not the original revocation_notice —
this is the actual cascading mechanism under test.

## Method

1. Generate `M1` (as crux5).
2. Generate `M2`, derived from `M1` only.
3. Classify both assert their conclusion phrase (validity gate for both).
4. Repair `M1` using `revocation_notice` (as crux5).
5. **Repair `M2` using only the repaired `M1` text** as the "upstream fact
   has been revised" signal — no access to the original rule, value, or
   revocation_notice.
6. Classify both repaired texts for their respective conclusion phrases.

## Metrics

- **Hop-1 leak rate**: same as crux5, reported for comparison.
- **Hop-2 leak rate**: the number this test exists for — does correct
  retraction propagate when M2's repair never sees the original cause,
  only the corrected parent.
- **Cascade failures specifically**: cases where hop-1 repaired correctly
  but hop-2 did not — the exact failure mode a real multi-hop system
  would need to prevent.

## Bar, stated before seeing results

If hop-2 leak rate is meaningfully higher than hop-1's, that's a real,
actionable finding distinct from anything crux1-5 found: correct
single-hop repair does not imply correct cascading, and a production
mechanism would need each hop's repair to explicitly consume its parent's
revision, not assume propagation happens for free. If hop-2 stays low
like hop-1, that's a second-order positive result worth noting but not
overweighting given the small, hand-built fixture every round in this
series shares.
