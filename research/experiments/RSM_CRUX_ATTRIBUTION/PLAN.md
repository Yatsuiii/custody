# RSM Crux Falsifier — Can an LLM Judge Counterfactual Claim Dependence

Before any design or build work on a "Repairable Semantic Memory" /
claim-carrying-memory architecture (brainstormed, not yet designed —
proposes decomposing derived memories into atomic claims with support
formulas, then using counterfactual regeneration to judge which claims
survive a source's revocation), this tests the one assumption everything
else depends on:

> Given a derived claim M and two contributing sources A and B, can an
> LLM reliably judge whether M's claim would change if B were removed —
> against known ground truth?

If this fails, claim-level repair is moot regardless of how the rest of
the architecture (support algebra, versioning, semantic checksums) is
designed, because all of it consumes this judgment as an input. This is
checked first and cheaply, per the project's own "prefer a small
falsification experiment over a large production implementation"
discipline, and its own precommitted-gates discipline: written before any
model call, not relaxed after seeing results.

## Fixture: 20 hand-constructed cases, 5 categories, 4 each

Ground truth fixed in `fixture.json` before any Gemini call. Categories,
chosen to be adversarial rather than easy:

1. **A-only dependence** (`depends_on_b = false`): B is present but
   irrelevant to M's specific claim.
2. **B-only dependence** (`depends_on_b = true`): M's claim exists only
   because of B.
3. **Joint/entangled** (`depends_on_b = true`): M's claim requires both A
   and B together; removing either invalidates it.
4. **Redundant support** (`depends_on_b = false`): A and B independently
   each support M; removing B alone leaves A sufficient. This is the
   hardest case for a shallow judge, since B genuinely *is* about the
   same claim, just not load-bearing once A is accounted for.
5. **Topical-but-irrelevant distractor** (`depends_on_b = false`): B is
   thematically or temporally adjacent to M but has no actual causal
   relationship to the specific claim in M. Tests false-positive rate —
   a judge that pattern-matches on topic similarity rather than
   reasoning about dependence will get these wrong.

8 of 20 cases have `depends_on_b = true` (categories 2, 3); 12 have
`depends_on_b = false` (categories 1, 4, 5).

## Method

For each case, `run.py` sends A, B, and M to `gemini-3.5-flash` via
Vertex AI (`project-988bc9fe-092c-4b32-90c`) with a single fixed prompt
asking: if B were discovered false/removed, would M's claim need to
change? YES/NO plus one-sentence reasoning. The response is parsed for a
YES/NO judgment and scored against `depends_on_b`, unmodified after the
fact.

## Metrics

- **Accuracy**: correct judgments / 20.
- **Precision** (on `depends_on_b = true`): of cases judged YES, fraction
  where ground truth is actually YES.
- **Recall** (on `depends_on_b = true`): of ground-truth YES cases,
  fraction judged YES.
- **False positive rate on category 4 and 5 specifically** (redundant
  support, distractor): these are the adversarial cases most likely to
  fool a shallow judge into a false YES. Reported separately, not
  averaged into the overall accuracy, because a judge that's fine
  overall but fails specifically on redundant-support and distractor
  cases has failed at the one thing that matters most for a repair
  mechanism (avoiding unnecessary collateral revocation).

## What would make this worth building on, stated before seeing results

No formal PASS/CAUTION/KILL gate is preregistered here the way E2D's was,
because this is explicitly a cheap pre-design check, not a falsifier for
a frozen mechanism. But stated in advance: overall accuracy below ~85%,
or any miss on category 4/5 (redundant support / distractor), would mean
the crux assumption does not hold reliably enough to build claim-level
repair on top of it without a much stronger (and non-semantic-inference-
based) verification layer — which would undercut the core value
proposition of "repair" over "just cap FREEFORM at INFORM and don't try."
