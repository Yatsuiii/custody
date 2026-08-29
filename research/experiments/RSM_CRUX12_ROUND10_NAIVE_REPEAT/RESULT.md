# RSM Crux12 Result — Round 10 Naive Vendor Case Did Not Recur

## Experiment Review

Verdict: valid

Baseline: Round 10's naive `vendor_onboarding` call was 2/3 correct. It
incorrectly returned RETRACT for M2b even though genuinely independent C
support meant M2b should SURVIVE. Round 9's corresponding clean call got
all three judgments correct.

Hypothesis: the Round 10 M2b false positive might be sampling variance
rather than a stable naive failure. Repeating the unchanged prompt/domain
would show whether M2b stays SURVIVE or flips back to RETRACT.

Changed variable: repetition only. Five sequential calls used the exact
Round 10 `NAIVE_PROMPT`, the exact `vendor_onboarding` domain text, the
same model/endpoint, and the same regex parser. The other Round 10
domains and the skeptical condition were not run.

Metric: exact three-position judgment accuracy and the M2b false-positive
rate, with per-call raw responses, missing verdicts, and transport errors
recorded. Per-call accuracy and the binary M2b-false-positive indicator
also have their population variance reported across the five calls.

Result: all five calls completed with no errors or missing verdicts. All
five returned M1=RETRACT, M2a=RETRACT, and M2b=SURVIVE: 15/15 judgments
correct and 0/5 M2b false positives.

Kill/continue decision: the Round 10 honest-case false positive was not
replicated in this five-call exact prompt/domain sample. The original miss
remains real evidence; this result is not evidence that the naive judge is
robust in general and does not justify building semantic repair.

Missing evidence: five calls are a small sample, only one model and one
prompt are tested, and this probe isolates the vendor call rather than
repeating the full four-domain batch. The round-10 spoofed `server_access`
miss was not part of this replication.

## Frozen-condition verification

Before any Round 12 model call, the copied domain was checked for exact
content equality with `RSM_CRUX10_SPOOFED_INDEPENDENCE/fixture.json`'s
`vendor_onboarding` entry, and the copied `NAIVE_PROMPT` was checked for
exact equality with Round 10's prompt constant. The fixture remained
unchanged throughout the run. Its SHA-256 is:

`40c7259fa30fab9b7fe11ed3cc91fa228d26dadd5b20b904a8ed692cfd27de70`

## Repeated result

| Repetition | M1 | M2a | M2b | Correct | Complete |
|---|---|---|---|---:|---|
| 1 | RETRACT | RETRACT | SURVIVE | 3/3 | yes |
| 2 | RETRACT | RETRACT | SURVIVE | 3/3 | yes |
| 3 | RETRACT | RETRACT | SURVIVE | 3/3 | yes |
| 4 | RETRACT | RETRACT | SURVIVE | 3/3 | yes |
| 5 | RETRACT | RETRACT | SURVIVE | 3/3 | yes |
| **Pooled** |  |  |  | **15/15** | **5/5** |

Per-position accuracy was 5/5 for M1, 5/5 for M2a, and 5/5 for M2b.
The M2b false-positive count was **0/5 (0%)**. The per-call accuracy
vector was `[3/3, 3/3, 3/3, 3/3, 3/3]`: mean `1.0`, population variance
`0.0`, population standard deviation `0.0`. The M2b-false-positive vector
was `[0, 0, 0, 0, 0]`, with mean `0.0`, population variance `0.0`, and
population standard deviation `0.0`.

The raw reasons varied slightly in wording but consistently identified the
revoked self-attestation/B chain as sufficient to retract M1 and M2a, and
the genuinely independent client reference/C as sufficient for M2b to
survive. No parser or output-level ambiguity was found.

## Honest bottom line

Round 10's `vendor_onboarding` false positive did not recur in five exact
naive prompt/domain repetitions. Combined with Round 11's 5/5 clean
round-9 repetitions, this strengthens the interpretation that the original
honest-case false positive was a sample-specific flip. It still does not
bound the naive judge's general error rate: the sample is only five calls,
and the exact Round 10 spoofed case remains untested by this replication.

Full raw responses, parsed verdicts, exact labels, hashes, and metrics are
in `result.json`.
