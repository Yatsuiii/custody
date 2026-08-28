# RSM Crux9 — Does Cascading Repair Correctly Stop at Redundant Support?

Crux3 showed a single-hop judgment can distinguish "sole support" from
"redundant support" (0/8 vs 4/8 leak). Crux6 showed cascading repair can
correctly propagate a retraction two hops deep when every downstream memory
has no other support (0/5 leak at both hops). Neither round tested the
combination that actually matters for Custody's flagship claim — the F1
demo's "preserve unaffected descendants, not just direct dependents" pitch —
because crux6's chain had no branch point: every downstream memory's *only*
support was the thing above it.

This round adds that branch point. Four domains, each with:

- **B**: the source that gets revoked.
- **M1**: depends only on B. Ground truth: should retract.
- **M2a**: depends only on M1 (pure cascade, no other support). Ground
  truth: should retract, matching crux6.
- **M2b**: depends on M1 **and** an independent fact **C**, unrelated to B,
  that on its own already supports M2b's conclusion. Ground truth: should
  **survive** — C alone is sufficient, so M2b's conclusion does not
  actually depend on the revoked chain even though M1 is one of its two
  named supports.

This is the same "redundant support survives" pattern as crux3, but now
inside a repair-cascade prompt that also has to correctly retract M2a in
the same pass — testing whether the model's cascade logic degrades into
"anything downstream of a retracted memory retracts" (over-broad, the
thing Custody's structural design explicitly avoids) once there's a real
branch to get wrong.

## Fixture: 4 domains x 3 memories = 12 judgments, all in one repair pass per domain

1. **cfo_approval**: B = vendor invoice claiming amount over threshold.
   C = independently verified signed purchase order, also over threshold.
2. **server_access**: B = personnel clearance record (compromised).
   C = separate biometric badge audit, done independently.
3. **vendor_onboarding**: B = vendor's own self-attestation of security
   compliance. C = an existing client's independent reference check.
4. **flight_compensation**: B = airline's own delay log (disputed).
   C = an independent passenger-submitted timestamp log.

Each domain gets one repair call, given B's revocation notice and the
three memories (M1, M2a, M2b) each with their own stated support (M1: B
only; M2a: M1 only; M2b: M1 and C). The model is asked, per memory,
whether it should retract, or survive because independent support
remains.

## Bar, stated before running

Correct per-domain judgment: M1 retract, M2a retract, M2b survive. Full
success = 12/12 correct across all four domains. A model that retracts
anything touching the revoked chain (M1, M2a, and M2b all retract) reproduces the
over-broad "revoke the whole subtree" behavior Custody's structural
mechanism (E2D, PASS) already achieves without any LLM — that would mean
the semantic layer adds no precision beyond what's already shipped, which
is a legitimate and informative outcome, not a failure of the test itself.
The interesting result is whether the model preserves M2b's real
distinction, or collapses it under cascade pressure.
