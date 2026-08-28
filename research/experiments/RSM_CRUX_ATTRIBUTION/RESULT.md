# RSM Crux Falsifier Result

**19/20 (95%) accuracy.** Live `gemini-3.5-flash` via Vertex AI, one call
per case, scored against precommitted ground truth, no post-hoc
relabeling. Full detail in `result.json`.

| Metric | Value |
|---|---|
| Accuracy | 19/20 = 95.00% |
| Recall on `depends_on_b = true` | 1.0 (8/8 — zero false negatives) |
| Precision on `depends_on_b = true` | 0.889 (8/9 — one false positive) |
| Category accuracy | a_only 1.0, b_only 1.0, joint 1.0, **redundant 0.75**, distractor 1.0 |
| Adversarial-category misses | `R2` (redundant support) |

## The one miss is the informative part, not the noise

`R2`: an expense report approved by both the employee's manager and,
separately, the Finance department. Ground truth (as constructed):
*redundant* — either approval alone should be sufficient, so removing
Finance's sign-off shouldn't invalidate "the report is approved."

The model said YES (depends on B) with this reasoning: *"Without the
Finance department's approval, the expense report cannot be verified as
fully approved and eligible for reimbursement."*

That's not a reasoning failure. It's a **legitimate alternative reading**
of the same English sentence — real corporate expense policy often
*does* require both manager and Finance sign-off jointly, not either
alone. The fixture's prose doesn't disambiguate "these two approvals are
independently sufficient" from "these two approvals are jointly
required" — because natural language often doesn't carry that
information at all. A human reading the same two sentences cold would
plausibly make the same call the model did.

This is exactly the ambiguity the brainstormed RSM proposal itself
predicted would need explicit `support_mode` (`ALL_REQUIRED` vs
`ANY_SUFFICIENT`) declared *at claim-creation time*, not inferred later
from prose. The miss here isn't "the LLM judge is 95% reliable, good
enough" — it's a concrete demonstration that the 5% failure mode is
structural: redundancy-vs-conjunction is frequently **not recoverable
from natural language after the fact**, no matter how good the judge is,
because the information was never encoded in the text to begin with.

## What this does and does not establish

**Does establish:** for cases where dependency actually turns on causal/
topical relevance (four of five tested categories — a_only, b_only,
joint, distractor), a live LLM judge is highly reliable (100% on those
four categories, 100% recall overall — it never misses a real
dependency, which is the safety-critical direction for a revocation
system). That's a genuinely positive signal for the easier 80% of the
problem.

**Does not establish:** that an LLM judge can reliably resolve *redundant
support* semantics from prose alone — the one category that matters most
for RSM's actual value proposition (avoiding unnecessary collateral
revocation when independent support survives). This one experiment can't
distinguish "the model got unlucky on this one case" from "this is a
structural ambiguity that would recur," and 4 cases per category is too
few to know which.

## Verdict against the bar stated in advance

`PLAN.md` stated before running: accuracy below ~85%, or any miss on
category 4/5, would mean the crux assumption doesn't hold reliably
enough to build on without a non-semantic-inference verification layer.
Accuracy is 95%, clearing that number — but there *was* a category 4
(redundant) miss, and the qualitative reason for it points at a
structural gap, not a fixable prompt issue. Taking the numeric threshold
alone as a pass while ignoring the miss's actual cause would be
cherry-picking the metric that looks good and ignoring the one that
doesn't; both were precommitted, and both count.

**Net read:** the crux assumption partially holds. An LLM judge is
reliable for causal/topical dependence judgments, which is real,
positive signal — but it doesn't resolve the redundant-support case
RSM's pitch depends on most, and the failure mode looks structural
(information genuinely absent from prose) rather than a matter of a
better prompt or a bigger model. Building claim-level repair on top of
LLM-judged support without also solving explicit support-mode
declaration at write time (which brings back the original design
question of how memories get created with that structure in the first
place — not a small addition) would inherit this gap directly.

## Recommendation

Not a KILL — the signal on 4/5 categories is genuinely strong. But not a
BUILD either. The next cheap step, if this is pursued further, is not "improve
the prompt" — it's testing whether `support_mode` can be reliably
*declared* at claim-creation time (a different, more tractable question
than inferring it post-hoc), which is a separate experiment from this
one. This result does not change the recommendation from the prior
conversation turn: this is a real, promising research thread, and it
does not belong in the remaining hackathon window. Custody's shipped
claim (structural support revocation, FREEFORM capped at INFORM) does
not depend on this working.
