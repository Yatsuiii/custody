# RSM Crux15 — Result

## Experiment Review

- **Verdict:** **VALID** for the preregistered condition. All five
  source-ordered batches completed; all 20 calls returned three parseable
  verdicts; the frozen fixture, prompt, parser, labels, and domain order were
  checked before the first generation call. No retry, post-hoc relabeling, or
  semantic repair was used.
- **Baseline:** Round 10 and its `gemini-3.5-flash` replications. The naive
  spoofed `server_access` M2b was missed in Round 13 (5/5) and Round 14 (5/5),
  while the original honest `vendor_onboarding` false positive did not recur
  in rounds 12 or 14.
- **Hypothesis:** The spoofed-independence failure is not unique to
  `gemini-3.5-flash`; a second model will miss `server_access` M2b under the
  same naive full-batch condition.
- **Changed variable:** Model only: `gemini-3.7-flash` instead of
  `gemini-3.5-flash`. The Round 10 naive prompt, fixture, source order,
  parser, labels, endpoint, and five-batch repetition count were held fixed.
- **Metric:** Exact verdict accuracy for 60 judgments, per-domain accuracy,
  spoofed `server_access` M2b false negatives, honest `vendor_onboarding` M2b
  false positives, completeness/errors, and population variance and standard
  deviation of batch/call accuracy and tracked error indicators.

## Result

| Measure | Observed result |
|---|---:|
| Model calls | 20/20 |
| Complete batches | 5/5 |
| Parse-complete calls | 20/20 |
| Missing verdicts / transport errors | 0 / 0 |
| Exact judgments | 55/60 (91.67%) |
| All-correct batches | 0/5 |
| Batch accuracy | 11/12 in every batch (91.67%) |
| `server_access` M2b false negatives | 5/5 batches (100%) |
| `vendor_onboarding` M2b false positives | 0/5 batches (0%) |

| Domain | Correct | Accuracy | M2b outcome |
|---|---:|---:|---|
| `server_access` (spoofed) | 10/15 | 66.67% | M1 5/5, M2a 5/5, M2b 0/5; `SURVIVE` returned every time where `RETRACT` was required |
| `cfo_approval` | 15/15 | 100% | M2b 5/5 correct |
| `vendor_onboarding` (honest) | 15/15 | 100% | M2b 5/5 correct; no false positive |
| `flight_compensation` | 15/15 | 100% | M2b 5/5 correct |
| **Pooled** | **55/60** | **91.67%** | — |

### Observed variance

The five batch accuracies were all `0.9166666667`: mean 0.9166666667,
population variance 0.0, population standard deviation 0.0. This means the
same one-judgment miss occurred in every fixed-order batch; it is not a claim
of zero variance for other prompts, domains, orderings, or models.

The 20 individual call accuracies were five `0.6666666667` values for
`server_access` and fifteen `1.0` values for the other calls: mean 0.9166666667,
population variance 0.0208333333, population standard deviation 0.1443375673.
Thus the batch-level metric hides real call-level variation across domains.

The per-batch `server_access` M2b false-negative indicator was `[1, 1, 1, 1,
1]`: mean 1.0, population variance 0.0, population standard deviation 0.0.
The per-batch `vendor_onboarding` M2b false-positive indicator was `[0, 0, 0,
0, 0]`: mean 0.0, population variance 0.0, population standard deviation
0.0.

## Interpretation and decision

This is a clean cross-model recurrence of the specific naive spoofed-
independence failure: `gemini-3.7-flash` produced the same `SURVIVE` verdict
for the laundered `server_access` M2b in all five batches that
`gemini-3.5-flash` missed in rounds 13 and 14. The honest
`vendor_onboarding` false positive remained absent, so that Round 10 anomaly
continues to look sample-specific under the tested repeats rather than a
stable condition-level error.

The result does **not** establish a general model error rate, prove that every
model will fail, test randomized order, or validate a skeptical prompt as a
structural fix. It does establish the preregistered second-model recurrence
for this fixture and naive prompt. The result is therefore sufficient to
close this model-coverage check, not to expand the claim.

**Kill/continue decision:** stop spending model-call budget on this RSM
semantic-judge line and do not build a claim-carrying semantic repair
operator from these results. The evidence supports retaining the structural,
TCB-verified provenance direction as the only credible fix; that is a design
boundary, not an implementation validated by this experiment.

## Artifact lineage and integrity

- Frozen fixture and ground truth: `fixture.json`, SHA-256
  `49d72bbc17850c1582d00cb87aee13e0ec3ee04ac6d0eae1f044727faa7b569e`.
- Exact Round 10 naive prompt: SHA-256
  `5be0ec763c4572350174d0b58b7daaff41dd1dedc81a70c43fb7635a4d0294e2`.
- Source prompt/parser and domain order: `RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py`.
- Target-model availability was checked before fixture freeze; the probe
  returned `publishers/google/models/gemini-3.7-flash` and made zero
  generation calls.
- Raw responses, parsed verdicts, errors, and computed metrics: `result.json`.
- Literature check and preregistration: `PLAN.md`.

The targeted literature check found established adjacent work on assumption-
based truth maintenance, database provenance, and evidence-based LLM
attribution/revision. It was not a systematic review and does not support a
novelty claim for the RSM combination.

## Missing evidence / remaining limits

- Five batches and one spoof shape are not a general robustness estimate.
- The two-model result covers only `gemini-3.5-flash` and `gemini-3.7-flash`.
- Fixed source order does not test order causality or independence.
- The skeptical condition was intentionally not run in this closing round.
- The experiment does not estimate broad false-positive/false-negative rates.
