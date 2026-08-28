# RSM Crux2 Result — Sub-Claim-Level Attribution (Harder Test)

**16/19 (84.21%) sub-claim accuracy.** Live `gemini-3.5-flash`, one call
per case (10 cases, 19 sub-claim judgments), ground truth fixed before
any call. Lower than the first crux test's 95%, as expected — this
targets the actually-hard case (partial dependence within a composite
claim) directly, plus deliberately re-stresses the one weak spot found
before. Full detail in `result.json`.

| Metric | Value |
|---|---|
| Sub-claim accuracy | 16/19 = 84.21% |
| Recall on `depends_on_b = true` | 1.0 (still zero missed true dependencies) |
| Precision on `depends_on_b = true` | 0.667 (3 false positives) |
| Unparsed responses | 0 |

## The explicit-vs-ambiguous comparison did not replicate cleanly, and that's the real finding

`PLAN.md` predicted, before running: if explicit "either alone is
sufficient" language fixes the redundant-support case the first test
missed, that's an actionable, coherent result (LLM judgment works *given*
explicit support-mode declaration). The two matched pairs disagree with
each other:

- **Expense-approval pair** (`C8` explicit, `C9` ambiguous): replicates
  the hypothesis exactly. Explicit → correct. Ambiguous → wrong, same
  failure mode as the first test's `R2`.
- **Vendor-certification pair** (`C6` explicit, `C7` ambiguous): the
  **opposite**. Explicit → wrong. Ambiguous → correct.

A quick follow-up (not part of the precommitted fixture, run after
seeing this result specifically to diagnose it — flagged as such, not
folded into the scored metrics) asked the model to explain its reasoning
on `C6` and `C7` directly:

> **C6 (explicit, wrong):** *"If Source B is removed... the critical
> vendor risk policy stating that 'either certification alone is
> sufficient'... is also lost. Without this exact wording from Source B
> establishing the qualification rules, we would have no basis to
> conclude that Source A's SOC 2 audit alone is sufficient."*
>
> **C7 (ambiguous, correct):** *"Source A's statement... is independently
> sufficient to justify marking the vendor as 'security-vetted.'... Source
> B... merely serves as secondary, redundant proof."*

This reveals a real confound in the fixture: `C6`'s sufficiency rule was
written as part of source B's own sentence, so removing B removes the
rule that would have justified keeping the claim, along with the fact.
That's a fixture design mistake — the rule should have been given as
source-independent background policy, the way `C1`-`C5` and `C10`'s
`policy_context` field correctly do it.

**But this does not fully explain the result**, and reporting only the
tidy explanation would be cherry-picking. `C8` has the *exact same*
structural pattern — the sufficiency rule is bundled inside source B's
own sentence there too (*"...Company policy states either approval alone
is sufficient..."*) — and the model got `C8` right anyway. Same confound,
opposite outcome, no diagnosis run for that pair to explain the
difference. The honest conclusion is that the judge's behavior on
redundant-support cases is not fully explained by the confound alone;
there is real inconsistency across superficially similar cases that
this experiment doesn't resolve.

## What this changes from the first test's conclusion

The first test's finding was "95% accurate, one miss on the hardest
category, plausibly fixable by explicit declaration." This test's finding
is weaker and more concerning: even with explicit declaration, the
judge is not reliably correct on redundant-support cases, and the
inconsistency doesn't reduce cleanly to a single identifiable cause. That
is a harder problem than "the information isn't in the prose" — it
suggests the judgment itself is somewhat unstable in this specific
category, in ways not fully predictable from the case's structure.

## Scope and limitations of this experiment specifically

- The diagnostic follow-up on `C6`/`C7` was not precommitted and used a
  different prompt (reasoning-inclusive, matching the first test's
  format) than the scored run (bare YES/NO per sub-claim) — it explains
  *a* mechanism behind one wrong answer, not necessarily the general
  pattern, and is reported as exploratory, not as a scored result.
- 10 cases, 19 sub-claim judgments, 2 explicit/ambiguous pairs is a small
  sample. Neither "explicit language sometimes works" nor "the model is
  inconsistent on redundant support" should be taken as more than
  directional at this sample size.

## Recommendation

Reinforces, more strongly than the first test did, the recommendation
already given: this is not something to pursue inside the remaining
hackathon window, and not something to build claim-level repair on top
of without first resolving *why* the same manipulation produces opposite
results in superficially similar cases — which is real, unscoped research
work, not a prompt-engineering fix. Custody's shipped claim does not
depend on this working.
