# RSM Crux11 Result — Five-Repeat Variance Probe

## Experiment Review

Verdict: valid

Baseline: Round 5 previously reported 0/6 repair leaks after 6/6 valid
generations; round 9 previously reported 12/12 correct judgments.

Hypothesis: repeating the same model, prompts, fixtures, and scoring rules
would reveal whether those clean single-call results changed under nominally
identical sampling.

Changed variable: repetition only. Five sequential repetitions were run for
each frozen source round. No new scenario, prompt, parser, or ground-truth
label was introduced.

Metric: round-5 generation validity and leak/clean outcome; round-9 exact
judgment accuracy. Per-repetition rates use population variance across the
five observed repetition rates. Missing or malformed outputs would have been
reported separately.

Result: all 140 successful live calls completed with no API errors, missing
verdicts, or invalid generations. The binary outcomes did not vary in this
sample: round 5 was 30/30 clean among 30/30 valid generations, and round 9
was 60/60 correct.

Kill/continue decision: the selected clean controls show no observed label
variance at five repetitions, but the variance question is not closed. The
round-10 naive flip remains real evidence that stability may depend on the
condition. Do not treat this result as a license to add a new scenario or
build a semantic repair mechanism.

Missing evidence: only two hand-built fixtures, five repetitions, one model,
and one prompt family were tested. Round 10's exact naive condition was not
repeated here. Round-5 scoring still uses a second Gemini semantic classifier,
so classifier circularity remains.

## Execution note

The first sandboxed invocation attempted 50 calls but failed before reaching
Gemini because OAuth DNS resolution was unavailable:

`TransportError: HTTPSConnectionPool(host='oauth2.googleapis.com', port=443):
Max retries exceeded ... Failed to resolve 'oauth2.googleapis.com'`

Those are transport failures, not model evidence, and are not included in
the scored totals below. With approved network access, the exact same
fixture and runner completed successfully. The fixture was not edited between
the two attempts; the successful artifact records its SHA-256 as
`d9472875d95195330fe1450817854fe389706c427a33bdd69f6927b5b3957da8`.

## Round-5 repeated entangled-inference control

Every repetition produced 6/6 generation-valid cases, 6/6 clean repairs, and
0/6 leaks:

| Repetition | Valid generations | Clean repairs | Leaks | Errors |
|---|---:|---:|---:|---:|
| 1 | 6/6 | 6/6 | 0/6 | 0 |
| 2 | 6/6 | 6/6 | 0/6 | 0 |
| 3 | 6/6 | 6/6 | 0/6 | 0 |
| 4 | 6/6 | 6/6 | 0/6 | 0 |
| 5 | 6/6 | 6/6 | 0/6 | 0 |
| **Pooled** | **30/30** | **30/30** | **0/30** | **0** |

Per-case counts were identical: `cfo_approval`, `server_access`,
`vendor_onboarding`, `order_discount`, `tenure_pricing`, and
`flight_compensation` each produced 5/5 valid, clean repairs and 0/5 leaks.

The per-repetition leak-rate vector was
`[0/6, 0/6, 0/6, 0/6, 0/6]`. Its mean was `0.0`, population variance was
`0.0`, and population standard deviation was `0.0`. This is zero observed
variance, not a proof that the underlying leak probability is zero.

The generated and repaired wording changed between calls. Inspection of all
30 repaired records found explicit withdrawal language (typically “can no
longer be confidently asserted”), and all 30 repair classifiers returned
`ANSWER: NO`. No output-level ambiguity was found in this sample.

## Round-9 repeated redundant-cascade control

Every repetition produced 12/12 correct judgments and 4/4 fully correct
domains:

| Repetition | Correct judgments | Accuracy | Fully correct domains | Missing/error calls |
|---|---:|---:|---:|---:|
| 1 | 12/12 | 12/12 | 4/4 | 0 |
| 2 | 12/12 | 12/12 | 4/4 | 0 |
| 3 | 12/12 | 12/12 | 4/4 | 0 |
| 4 | 12/12 | 12/12 | 4/4 | 0 |
| 5 | 12/12 | 12/12 | 4/4 | 0 |
| **Pooled** | **60/60** | **60/60** | **20/20** | **0** |

Per domain, each of `cfo_approval`, `server_access`,
`vendor_onboarding`, and `flight_compensation` was correct 15/15 across
five repetitions. Each memory position was also correct 20/20: position 1
(`M1` retract), position 2 (`M2a` retract), and position 3 (`M2b` survive).

The per-repetition accuracy vector was
`[12/12, 12/12, 12/12, 12/12, 12/12]`. Its mean was `1.0`, population
variance was `0.0`, and population standard deviation was `0.0`.

All 20 raw responses contained the three parseable verdict lines. Their
reasons varied in wording but consistently cited the revoked B/M1 chain for
positions 1–2 and the independent C evidence for position 3. No parser or
semantic ambiguity was found on inspection.

## Comparison with round 10 and honest bottom line

Round 10's naive condition still matters: it missed the spoofed support and
also produced an unplanned honest-case false positive, despite round 9's
single call on the clean condition being correct for that domain. Round 11
does not reproduce that naive/adversarial condition; it repeats rounds 5 and
9 as clean controls. Therefore the correct conclusion is:

- **Observed in Round 11:** zero label variance across five repeats of both
  selected controls, with exact pooled results of 30/30 clean round-5 repairs
  and 60/60 correct round-9 judgments.
- **Not established:** that Gemini's semantic repair judgments are stable in
  general, that round 10's flip was a one-off, or that the skeptical/naive
  independence problem is bounded.

The requested variance probe is complete for the selected controls. The next
highest-information follow-up would be repeating round 10's exact naive
`vendor_onboarding` condition, rather than treating these clean-control
results as a general robustness bound.

Full raw model responses, classifier outputs, per-case labels, hashes, and
per-repetition metrics are in `result.json`.
