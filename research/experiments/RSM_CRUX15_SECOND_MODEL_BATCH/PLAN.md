# RSM Crux15 — Second-Model Replication of Round 10's Naive Batch

## Question

Round 13 and Round 14 showed that `gemini-3.5-flash` repeatedly misses the
spoofed `server_access` M2b, while Round 12 and Round 14 did not reproduce
Round 10's honest `vendor_onboarding` false positive. The remaining
load-bearing uncertainty is model coverage: does the naive spoof failure
survive on a second model, or is it specific to the first model?

This is the closing planned RSM model round. It repeats Round 10's naive
four-domain call sequence in source order for five batches, changing only
the model to the preselected `gemini-3.7-flash`. The skeptical condition is
not run and no new scenario is introduced.

## Baseline

- Round 10 naive full batch on `gemini-3.5-flash`: 10/12 judgments correct;
  spoofed `server_access` M2b was a false negative and honest
  `vendor_onboarding` M2b was a false positive.
- Round 13 isolated `server_access` replication on `gemini-3.5-flash`:
  10/15, with the spoofed M2b false negative in 5/5 calls.
- Round 14 source-ordered full-batch replication on `gemini-3.5-flash`:
  55/60, with the spoofed M2b false negative in 5/5 batches and the honest
  `vendor_onboarding` false positive in 0/5 batches.
- Target model: `gemini-3.7-flash`, verified before fixture freeze with
  `client.models.get` returning `publishers/google/models/gemini-3.7-flash`
  in Vertex project `project-988bc9fe-092c-4b32-90c`, location `global`.
  That availability check made no generation call.

## Pre-call literature check

This was a targeted primary-source check, not a systematic review. It is
recorded before the generation run so the series does not imply novelty
without checking adjacent work.

- [de Kleer, *An assumption-based TMS* (Artificial Intelligence, 1986)](https://www.sciencedirect.com/science/article/pii/0004370286900809)
  establishes assumption-set-based truth maintenance and retraction as
  prior art for maintaining beliefs under changing assumptions.
- [Buneman, Khanna, and Tan, *Why and Where: A Characterization of Data Provenance* (ICDT, 2001)](https://homepages.inf.ed.ac.uk/opb/papers/ICDT2001.pdf)
  formalizes source influence and source location for query-derived data.
- [Green, Karvounarakis, and Tannen, *Provenance Semirings* (PODS, 2007)](https://www.cs.ucdavis.edu/~green/papers/pods07.pdf)
  gives an algebraic representation for recording and tracking provenance
  through positive queries.
- [Rashkin et al., *Measuring Attribution in Natural Language Generation Models* (Computational Linguistics, 2023)](https://aclanthology.org/2023.cl-4.2/)
  defines AIS for checking generated statements against an independent,
  provided source.
- [Gao et al., *RARR: Researching and Revising What Language Models Say, Using Language Models* (2022)](https://arxiv.org/abs/2210.08726)
  is adjacent post-hoc work that retrieves attribution evidence and revises
  unsupported generated text.
- [Min et al., *FActScore* (EMNLP, 2023)](https://aclanthology.org/2023.emnlp-main.741/)
  evaluates long-form generations by decomposing them into atomic facts and
  checking support from reliable sources.

The verified conclusion is that ATMS, data provenance, and evidence-based
LLM attribution/revision are established areas. This targeted search does
not establish an identical prior system for the exact RSM combination, and
it is not enough for a novelty claim. The RSM series remains exploratory
evidence about a particular semantic judge, not a novel architecture claim.

## Hypothesis

The naive spoofed-independence failure is not unique to
`gemini-3.5-flash`. A second model will reproduce the `server_access` M2b
false negative under the exact same four-domain batch, while the honest
`vendor_onboarding` false positive may or may not recur.

## Changed variable

Model only: five sequential executions of the exact Round 10 naive
four-domain batch, with domains in the original order
(`server_access`, `cfo_approval`, `vendor_onboarding`,
`flight_compensation`). The fixture content, prompt, parser, endpoint,
labels, and repetition count are fixed. No retries, prompt changes, order
randomization, skeptical calls, or post-hoc relabeling are allowed.

## Metrics and acceptance bar

For every call, batch, domain, and pooled result, report:

- exact correct/total judgment accuracy for M1, M2a, and M2b;
- per-domain and pooled accuracy;
- spoofed `server_access` M2b false negatives (`SURVIVE` when ground truth
  is `RETRACT`);
- honest `vendor_onboarding` M2b false positives (`RETRACT` when ground
  truth is `SURVIVE`);
- complete batches/calls, missing verdicts, transport errors, and raw
  responses;
- mean, population variance, and population standard deviation for
  complete-batch accuracy, complete-call accuracy, and both tracked error
  indicators.

The experiment is valid only if all five batches complete, the exact source
fixture/order/prompt checks pass before the first generation call, and every
raw response or error is recorded.

Precommitted interpretation:

- `server_access` false negative 5/5 is clean cross-model recurrence.
- `server_access` false negative 0/5 is clean non-recurrence and indicates
  model dependence; it does not rescue `gemini-3.5-flash` or justify
  semantic repair.
- 1–4/5 is mixed model behavior and therefore inconclusive; do not average
  it into a clean pass, and ask before spending on a further round.
- Any vendor false-positive count is reported separately; it cannot cancel
  the spoof result.

## Kill/close condition

If the fixture, prompt, parser, order, labels, or selected model must be
changed after seeing a response, this round is invalid. Regardless of the
model result, do not build a claim-carrying memory or semantic repair
operator from this evidence. A clean second-model result closes the model
coverage question only for this condition; a repeated or mixed failure
closes no general error-rate claim.

## Artifact lineage

- Frozen ordered input and ground truth: `fixture.json`.
- Source prompt/parser/batch order: `RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py`.
- Target-model availability probe: pre-freeze `client.models.get` check for
  `gemini-3.7-flash`; no generation call.
- Raw 20-call evidence and computed metrics: `result.json`.
- Literature note and human-readable preregistration: this `PLAN.md`.
- Human-readable result and closeout interpretation: `RESULT.md`.
