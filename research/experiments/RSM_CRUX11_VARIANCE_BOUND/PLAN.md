# RSM Crux11 — Bound Sampling Variance in Clean Rounds

## Question

Round 10 exposed a live variance problem: its naive `vendor_onboarding`
case produced a false positive even though round 9's identical
domain/prompt got that case right. This round asks whether the clean
single-call results from rounds 5 and 9 are stable enough to treat as
mechanism evidence, or whether they are only individual samples.

This is deliberately a replication round, not a new scenario. It repeats
the frozen round-5 entangled-inference fixture and the frozen round-9
redundant-cascade fixture with the same model, prompt text, parsing rules,
and case order. The only changed variable is repetition.

## Baseline

- Round 5: 0/6 repair leaks after 6/6 generations were classified as
  confidently asserting the expected conclusion.
- Round 9: 12/12 judgments correct across four domains; every domain was
  fully correct.
- Model and endpoint: `gemini-3.5-flash` through Vertex AI project
  `project-988bc9fe-092c-4b32-90c`, location `global`.

The copied fixtures and expected labels in `fixture.json` are frozen before
any model call. The runner preserves the source rounds' prompt templates
and parsers rather than introducing a new semantic scorer.

## Hypothesis

The prior clean results may contain nonzero sampling variance. Five
independent sequential repetitions per round should expose whether any
case-level verdict, aggregate accuracy, or round-5 generation-validity
rate changes under the same nominal input. A zero-miss repeat does not
prove stability; it only sets an observed upper bound at this sample size.

## Metrics

For round 5, report for every repetition and pooled across repetitions:

- generation-valid cases, with the existing classifier-based validity
  rule;
- clean repairs and leaks among valid generations;
- invalid generations, model errors, and missing classifier verdicts;
- per-case clean/leak/invalid/error counts.

For round 9, report for every repetition and pooled across repetitions:

- exact correct/total judgment accuracy;
- complete-domain count;
- per-domain and per-memory-position accuracy;
- model errors and missing verdicts.

For both rounds, report the empirical mean, population variance, and
population standard deviation of the per-repetition accuracy metric, plus
the exact per-case outcome counts. Missing or malformed outputs are
reported separately and never treated as a clean success.

## Precommitted acceptance and interpretation bar

The experiment is valid only if all five repetitions of both frozen
fixtures complete, the runner records every model response (or explicit
error), and no fixture or ground-truth field is edited after the first
model call. The result is informative either way:

- If every completed round-5 valid case is clean and every round-9
  judgment is correct in all five repetitions, report **no observed
  variance in this 5-repeat sample**, not proof of robustness.
- If any valid round-5 repair leaks, any expected round-5 generation is
  invalid, or any round-9 judgment changes, report **variance or a miss
  observed** and stop treating the prior single-call headline as stable.
- If an API or parsing failure prevents five complete repetitions, report
  the round as **inconclusive/blocked** and do not add a new scenario to
  compensate.

No result from this round authorizes a production implementation, a merge
to `main`, or a novelty claim.

## Kill condition

If the copied prompt, fixture, or scoring contract must be changed after
seeing a result, this round is invalid and must be discarded rather than
repaired post hoc. If repeated clean results remain too sparse to
estimate meaningful variance, the correct next action is to state that
the bound is weak—not to manufacture a stronger claim or expand scope.

## Artifact lineage

- Ground truth: this directory's `fixture.json`, copied from the committed
  round-5 and round-9 fixtures before any Round 11 model call.
- Prompt/scoring baseline: `RSM_CRUX5_ENTANGLED_INFERENCE/run.py` and
  `RSM_CRUX9_REDUNDANT_CASCADE/run.py` at the pre-round-11 branch tip;
  their prompt text and parsing behavior are reproduced in `run.py`.
- Raw evidence and per-repetition metrics: `result.json`.
- Human-readable interpretation: `RESULT.md`.
