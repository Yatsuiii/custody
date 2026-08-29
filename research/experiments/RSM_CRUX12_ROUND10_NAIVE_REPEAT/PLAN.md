# RSM Crux12 — Repeat Round 10's Naive Vendor Case

## Question

Round 10's naive run produced an honest-case false positive for
`vendor_onboarding`'s M2b: it retracted a memory that should survive on
genuinely independent support. Round 9's clean run on the same
vendor-onboarding condition got M2b right. This round repeats that exact
naive prompt/domain condition five times to measure whether the false
positive recurs.

This isolates the `vendor_onboarding` call itself. It does not add the
skeptical condition, change the domain text, or introduce a new scenario.
The prompt template, interpolation fields, model, endpoint, parser, and
ground-truth labels are copied from Round 10 and frozen in this directory.

## Baseline

- Round 10 naive `vendor_onboarding`: M1 RETRACT, M2a RETRACT, M2b
  incorrectly RETRACT — 2/3 correct for this domain.
- Round 9's all-honest condition: `vendor_onboarding` was 3/3 correct,
  including M2b SURVIVE.
- Model and endpoint: `gemini-3.5-flash` through Vertex AI project
  `project-988bc9fe-092c-4b32-90c`, location `global`.

## Hypothesis

The Round 10 false positive may be sampling variance rather than a stable
naive failure. Repeating the unchanged call will show whether M2b's
honest-support judgment stays RETRACT, stays SURVIVE, or flips between
the two.

## Changed variable

Repetition only: five sequential calls to the exact Round 10 naive
`vendor_onboarding` prompt. The fixture, prompt, model, location, and
regex parser do not change between repetitions. No retries are performed;
transport and parse failures remain explicit records.

## Metrics and bar

For each call and pooled across calls, report:

- exact correct/total judgment accuracy for M1, M2a, and M2b;
- M2b false positives (`RETRACT` when ground truth is `SURVIVE`);
- per-position accuracy and complete-call count;
- missing verdicts, model errors, and raw reasons;
- mean, population variance, and population standard deviation of the
  five per-call accuracy values and the five M2b-false-positive indicators.

The experiment is valid if all five calls complete, the same frozen
fixture is used, and every response or error is recorded. Interpretation
is precommitted:

- Any repeated M2b false positive means the Round 10 naive failure
  recurs; report its exact count and rate.
- Zero repeated M2b false positives means the Round 10 failure did not
  recur in this five-call sample; it does not erase the original miss.
- Mixed M2b outcomes establish observed sampling variance in this exact
  condition.
- Fewer than five usable calls make the result inconclusive; do not
  substitute a new scenario or edit the fixture.

## Kill condition

If the fixture, prompt, parser, or expected labels must be changed after
seeing a response, this round is invalid. A clean repeat is not grounds
for claiming the naive condition is robust, and a repeated miss is not
grounds for building a semantic repair mechanism.

## Artifact lineage

- Frozen input and ground truth: `fixture.json`.
- Source prompt/parser baseline:
  `RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py`.
- Raw five-call evidence and computed metrics: `result.json`.
- Human-readable interpretation: `RESULT.md`.
