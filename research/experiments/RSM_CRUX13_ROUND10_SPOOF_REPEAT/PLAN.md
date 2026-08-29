# RSM Crux13 — Repeat Round 10's Naive Spoofed `server_access` Case

## Question

Round 10's naive run missed the spoofed `server_access` case's M2b: it
returned SURVIVE even though the purported independent support was a
laundered restatement of the revoked HR record and M2b should RETRACT.
Round 12 repeated Round 10's honest `vendor_onboarding` condition and did
not reproduce its one-call false positive. This round measures the
unreplicated spoofed condition with five exact naive repetitions.

The domain, prompt, model, endpoint, parser, and labels are frozen before
the first model call. This repeats the isolated call condition itself; it
does not repeat Round 10's full four-domain batch or add the skeptical
condition.

## Baseline

- Round 10 naive `server_access`: M1 RETRACT, M2a RETRACT, M2b incorrectly
  SURVIVE — 2/3 correct for this domain.
- Round 10 naive pooled result: 10/12, including this spoofed M2b miss.
- Model and endpoint: `gemini-3.5-flash` through Vertex AI project
  `project-988bc9fe-092c-4b32-90c`, location `global`.

## Hypothesis

The Round 10 spoofed M2b miss may be a sample-specific flip rather than a
stable failure. Repeating the unchanged call will show whether M2b's
SURVIVE error recurs, disappears, or alternates with the expected RETRACT.

## Changed variable

Repetition only within this frozen condition: five sequential calls use
the exact Round 10 naive prompt and `server_access` domain text, the same
model/endpoint, the same exact parser, and the same ground-truth labels.
No retries, prompt changes, context additions, or post-hoc relabeling are
allowed. An API or parse failure remains an explicit result record.

## Metrics and acceptance bar

For every repetition and pooled across repetitions, report:

- exact correct/total judgment accuracy for M1, M2a, and M2b;
- M2b false negatives (`SURVIVE` when the frozen ground truth is
  `RETRACT`);
- per-position accuracy and complete-call count;
- missing verdicts, transport errors, and raw responses;
- mean, population variance, and population standard deviation of the
  complete-call accuracy values and the M2b-false-negative indicators.

The experiment is valid only if all five calls complete, the fixture is
unchanged, the exact source condition checks pass before the first model
call, and every raw response or error is recorded. Interpretation is
precommitted:

- Any repeated M2b false negative means the Round 10 miss recurs; report
  its exact count and rate.
- Zero repeated M2b false negatives means the miss did not recur in this
  five-call sample; it does not erase the original miss or establish
  robustness.
- Mixed outcomes are observed sampling variance in this exact condition.
- Fewer than five complete calls make the result inconclusive; do not
  substitute another scenario.

## Kill condition

If the fixture, prompt, parser, or expected labels must be changed after
seeing a response, this round is invalid. A clean repeat is not grounds
for claiming the naive judge is robust, and a repeated miss is not grounds
for building semantic repair.

## Artifact lineage

- Frozen input and ground truth: `fixture.json`.
- Source prompt/parser baseline:
  `RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py`.
- Raw five-call evidence and computed metrics: `result.json`.
- Human-readable interpretation: `RESULT.md`.
