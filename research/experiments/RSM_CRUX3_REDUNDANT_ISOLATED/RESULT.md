# RSM Crux3 Result — Redundant Support, Isolated and Properly Controlled

**Explicit: 0/8 false positives (0%). Ambiguous: 4/8 false positives
(50%).** Live `gemini-3.5-flash`, one call per case, 16 cases, ground
truth fixed before any call (all 16 are genuinely redundant support by
construction). Full detail in `result.json`.

This is a materially cleaner result than crux2's, and resolves the
contradiction crux2 left open.

| Metric | Value |
|---|---|
| Explicit false-positive rate | 0/8 = 0.0% |
| Ambiguous false-positive rate | 4/8 = 50.0% |
| Overall accuracy | 12/16 = 75.0% |
| Domains where explicit correct AND ambiguous wrong | 4/8 |
| Domains where both correct | 4/8 |
| Domains where explicit wrong | 0/8 |

## The confound fix worked — explicit declaration is now clean

With the sufficiency rule given as genuinely separate `policy_context`
(never bundled inside the removable source B, unlike crux2's `C6`),
explicit declaration went **8 for 8**. Every single explicit case was
judged correctly. That's not "mostly reliable" — it's a clean signal
that once the ambiguity is actually removed from the input (not just
gestured at), the judge handles it perfectly at this sample size.

This resolves crux2's open contradiction: `C6`'s failure there wasn't
evidence that explicit declaration doesn't work — it was evidence that
*declaration bundled inside a source that gets deleted along with the
fact it's justifying* doesn't work, which is a fixture design problem,
not a judge reliability problem. Properly isolated, explicit declaration
does exactly what the original brainstormed proposal said it should.

## Ambiguous cases: not random, domain-dependent

50% isn't noise-shaped — it splits cleanly by domain. `vendor_cert`,
`license_compliance`, `qa_testing`, and `incident_witness` were all
judged correctly *even without* explicit declaration (the model defaults
to "passing an audit/test/verification once is enough," which happens to
match ground truth). `expense_approval`, `background_check`,
`insurance_claim`, and `kyc_identity` were all judged incorrectly (the
model defaults to "an official approval/verification chain requires
every step," which is also a completely reasonable prior — many real
corporate policies genuinely work that way). Without explicit
declaration, the judge isn't unreliable in some fuzzy sense — it's
falling back on a domain-specific prior about which category of process
is typically conjunctive vs. redundant, and that prior is right about
half the time by construction of this fixture, not by some inherent
50/50 randomness.

## What this changes about the standing recommendation

Genuinely, meaningfully: **this is a positive result for the narrow
question it tests.** Combined with crux1/crux2's finding that
non-redundant attribution (a-only, b-only, joint, distractor, and
composite sub-claims) is already reliable at 95-100% *without* needing
explicit declaration, the fuller picture is:

> An LLM judge is reliable for claim-dependence attribution across the
> board, **provided** redundant-support cases carry an explicit,
> separately-declared sufficiency rule at claim-creation time. Without
> that declaration, redundant cases fall back to an unreliable,
> domain-dependent prior.

That is close to exactly what the original brainstormed proposal said
was necessary ("for high-assurance paths, sufficiency needs
deterministic support semantics defined when the memory is created")
and close to what Custody's own existing `AUTHORITY_MODEL.md` already
does structurally for its `REGISTERED` transform class (an explicit,
policy-owned cap, not inferred from prose). The design implication is
narrow and actionable: **claim-creation must capture support-mode
explicitly** (redundant vs. required) as structured metadata, not leave
it to be inferred later from natural language. The judge doesn't need to
solve the ambiguity at repair time if the ambiguity is never allowed to
exist unresolved at write time.

## What this does not establish

- Still a small sample (8 domains, 1 case each per variant) — a larger
  run would strengthen confidence further, though 0/8 vs 4/8 is already
  a clear enough gap to act on directionally.
- Doesn't test whether support-mode metadata can be captured reliably
  *at write time* in a real pipeline (i.e., who or what declares
  `policy_context`, and whether that declaration process itself is
  trustworthy) — that's a different question from whether the judge can
  *use* it correctly once present, which is what this test measured.
- Doesn't change that this remains outside the current hackathon
  window's scope; it changes the *shape* of what further work would need
  to prove (write-time support-mode capture, not repair-time semantic
  judgment) if this is ever picked back up.
