# RSM Crux5 — Entangled Inference (the actually-hard fusion shape)

Crux4 tested repair on model-fused text, but every generated sentence
turned out to be additive ("X, and Y") — the easier fusion shape from the
original brainstorm. This test forces the harder shape it named:
`f2(A,B)` — a stated *conclusion* that depends on both facts jointly, not
a compound sentence with a findable seam. If a poisoned data point (B)
was the only evidence for a threshold being crossed, the derived memory
doesn't repeat B's number — it states a *conclusion* ("requires CFO
approval," "is approved for onboarding") that silently assumed B was
true. There's no literal token to strip here. Repair means correctly
withdrawing or hedging the conclusion, not deleting a clause.

## Fixture: 6 cases, each a rule (A) + a disputed value (B) + an implied conclusion

Every case has the same shape: A states a threshold rule, B states a
specific value later found unreliable, and the conclusion is whichever
side of the rule's threshold B's value falls on. Ground truth, fixed
before any call: after B is revoked, the conclusion is no longer
supportable and must not be asserted as settled fact. B's source text
itself flags it as later-unreliable ("a source later found compromised")
so the *generation* step has a legitimate reason to still assert the
conclusion (it doesn't yet know B is bad) while the *repair* step, told
explicitly that B is now revoked, should not.

Full list of rules/values/conclusion-phrases in `fixture.json`.

## Method

1. **Generate.** Ask Gemini to state, in one sentence, what conclusion
   follows from the rule and the (at-generation-time-still-trusted)
   value — forcing an inference, not a restatement. Record `fused_memory`.
2. **Sanity check.** A separate strict classifier call (see below)
   confirms the generated conclusion actually asserts the expected
   conclusion phrase as settled fact. If not, the case is invalid.
3. **Repair.** Told B is now revoked, ask for a corrected version.
4. **Score.** The same strict classifier call checks whether the
   *repaired* text still asserts the conclusion confidently (leak) or
   correctly withdraws/hedges it (clean).

## A real methodological limitation, stated before running

Unlike crux4's literal-token check, scoring here needs a judgment call
("is this conclusion still asserted as settled fact, or has it been
correctly withdrawn/hedged") that a plain substring match can't make —
the repaired text's exact wording will vary. This uses a third,
independent Gemini call as a narrow binary classifier (confident-assertion
vs. not), which reintroduces the kind of semantic judgment crux1-3 already
found real limits in, for the *scoring* step specifically, not the
generation/repair steps. This is a real circularity risk this experiment
cannot fully rule out on its own. Mitigation: at least 3 cases are
spot-checked by hand against the classifier's verdict before the result
is reported, and any disagreement is stated explicitly, not smoothed over.

## Bar, stated before seeing results

If the leak rate here is meaningfully higher than crux4's 0% — the
conclusion keeps getting asserted even after the disputed value is
revoked — that's the sharpest possible confirmation of the original
impossibility-boundary argument: a model can strip an additive clause
reliably, but doesn't reliably know to *retract an inference* it already
committed to once the evidence for it is gone. If the leak rate stays
low, that would be a second genuinely positive result worth a larger,
better-controlled follow-up before believing it fully.
