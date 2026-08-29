# RSM Crux14 — Repeat Round 10's Full Naive Batch

## Question

Round 10's naive four-domain run produced two different errors in one
batch: it missed the spoofed `server_access` M2b and falsely retracted the
honest `vendor_onboarding` M2b. Round 13 repeated the spoofed call in
isolation and found the miss in all five repetitions. This round repeats
the entire Round 10 naive four-domain sequence, preserving the original
domain order, to measure whether batch context or ordering changes the
observed pattern.

The four domains, their order, prompt, parser, model, endpoint, and labels
are frozen before the first model call. This repeats the naive batch only;
Round 10's skeptical condition is deliberately not included.

## Baseline

- Round 10 naive full batch: 10/12 judgments correct.
- In source order, the per-domain results were:
  `server_access` 2/3 (spoofed M2b false negative), `cfo_approval` 3/3,
  `vendor_onboarding` 2/3 (honest M2b false positive), and
  `flight_compensation` 3/3.
- Model and endpoint: `gemini-3.5-flash` through Vertex AI project
  `project-988bc9fe-092c-4b32-90c`, location `global`.

## Hypothesis

The isolated Round 13 result may not fully represent the original batch
because call order or neighboring domains could affect the observed
behavior. Repeating the exact four-domain naive sequence will show whether
the two Round 10 errors recur, disappear, or vary across complete batches.

## Changed variable

Repetition only: five sequential executions of the exact Round 10 naive
four-domain batch, with domains in the original order
(`server_access`, `cfo_approval`, `vendor_onboarding`,
`flight_compensation`). Each batch makes four independent generation calls
through one client, then the next batch begins. No skeptical calls,
retries, prompt changes, order randomization, or post-hoc relabeling are
allowed.

## Metrics and acceptance bar

For every call, every batch, every domain, and pooled across the 20 calls,
report:

- exact correct/total judgment accuracy for M1, M2a, and M2b;
- per-domain and pooled accuracy;
- spoofed `server_access` M2b false negatives (`SURVIVE` when ground truth
  is `RETRACT`);
- honest `vendor_onboarding` M2b false positives (`RETRACT` when ground
  truth is `SURVIVE`);
- complete batches/calls, missing verdicts, transport errors, and raw
  responses;
- mean, population variance, and population standard deviation for
  complete-batch accuracy, complete-call accuracy, and both tracked M2b
  error indicators.

The experiment is valid only if all five four-domain batches complete, the
ordered fixture and exact source prompt checks pass before the first model
call, and every raw response or error is recorded. Interpretation is
precommitted:

- Repeated `server_access` false negatives or `vendor_onboarding` false
  positives are reported with exact counts and rates.
- Zero recurrence means only that the error did not recur in this five-batch
  sample; it does not erase Round 10 or establish robustness.
- Mixed outcomes are observed variance in this exact full-batch execution.
- Fewer than five complete batches make the result inconclusive; do not
  substitute another scenario or silently pool incomplete batches as a
  clean replication.

## Kill condition

If the fixture, prompt, parser, order, or expected labels must be changed
after seeing a response, this round is invalid. A stable failure is evidence
against the naive judge on this tested condition, not grounds to build a
semantic repair mechanism. A clean batch is not grounds to claim general
robustness.

## Artifact lineage

- Frozen ordered input and ground truth: `fixture.json`.
- Source prompt/parser/batch order: `RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py`.
- Raw 20-call evidence and computed metrics: `result.json`.
- Human-readable interpretation: `RESULT.md`.
