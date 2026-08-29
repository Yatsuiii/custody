# RSM Crux14 Result — Round 10 Naive Batch Pattern Recurs

## Experiment Review

Verdict: valid.

Baseline: Round 10's naive four-domain batch scored 10/12. In source
order, it missed spoofed `server_access` M2b and falsely retracted honest
`vendor_onboarding` M2b; `cfo_approval` and `flight_compensation` were
correct.

Hypothesis: the isolated Round 13 spoof replication might not represent the
original batch sequence. Repeating the exact four-domain naive sequence
would show whether neighboring calls or order changed either error pattern.

Changed variable: repetition only. Five sequential executions used the
exact Round 10 naive prompt, the four source domains in source order, the
same model/endpoint, the same parser, and the same labels. The skeptical
condition was not run. There were no retries, order changes, or post-hoc
relabels.

Metric: exact judgment accuracy, per-domain and pooled; complete calls and
batches; the spoofed `server_access` M2b false-negative rate; the honest
`vendor_onboarding` M2b false-positive rate; and population variance of
complete-batch accuracy, complete-call accuracy, and both error indicators.

## Result

All five batches completed: 20 calls, 60 judgments, zero transport errors,
and zero missing verdicts. Every batch scored 11/12. The model returned
M1=RETRACT and M2a=RETRACT for every domain in every batch. For M2b, it
returned SURVIVE for the three honest domains every time, but also returned
SURVIVE for spoofed `server_access` every time, where the frozen label was
RETRACT.

| Batch | `server_access` | `cfo_approval` | `vendor_onboarding` | `flight_compensation` | Batch total |
|---:|---:|---:|---:|---:|---:|
| 1 | 2/3 | 3/3 | 3/3 | 3/3 | 11/12 |
| 2 | 2/3 | 3/3 | 3/3 | 3/3 | 11/12 |
| 3 | 2/3 | 3/3 | 3/3 | 3/3 | 11/12 |
| 4 | 2/3 | 3/3 | 3/3 | 3/3 | 11/12 |
| 5 | 2/3 | 3/3 | 3/3 | 3/3 | 11/12 |
| **Pooled** | **10/15** | **15/15** | **15/15** | **15/15** | **55/60** |

Per-position accuracy was M1 **20/20**, M2a **20/20**, and M2b **15/20**.
The spoofed `server_access` M2b false-negative count was **5/5 (100%)**.
The honest `vendor_onboarding` M2b false-positive count was **0/5 (0%)**.
All 20 calls were complete; all five batches contained the same one
judgment error, so **0/5 batches were entirely correct**.

The complete-batch accuracy vector was
`[11/12, 11/12, 11/12, 11/12, 11/12]`: mean
`0.9166666666666666`, population variance `0.0`, and population standard
deviation `0.0`. The complete-call accuracy vector, in source order and
repeated five times, was
`[2/3, 1, 1, 1, 2/3, 1, 1, 1, 2/3, 1, 1, 1, 2/3, 1, 1, 1, 2/3, 1, 1, 1]`:
mean `0.9166666666666666`, population variance
`0.02083333333333334`, and population standard deviation
`0.14433756729740646`. The server false-negative indicator vector was
`[1, 1, 1, 1, 1]` with mean `1.0`, population variance `0.0`, and
population standard deviation `0.0`. The vendor false-positive indicator
vector was `[0, 0, 0, 0, 0]` with mean `0.0`, population variance `0.0`,
and population standard deviation `0.0`.

The raw reasons varied slightly but consistently treated the central
badge-provisioning system as independent support for `server_access` M2b.
The three honest M2b cases were consistently treated as surviving on their
independent support. No parser ambiguity was found.

## Kill/continue decision

The result confirms the Round 13 isolated finding under the original
four-domain call order: the naive judge's spoofed `server_access` failure
recurred in every batch. The unchanged `vendor_onboarding` false positive
from Round 10 did not recur in this full-batch sample, consistent with its
zero recurrence in Round 12. The five-batch result is evidence of a
repeatable naive failure on this spoof shape, not a general error-rate
estimate and not grounds to build semantic repair.

Because each domain was still sent as its own stateless generation call,
this tests call sequence and client reuse, not a single prompt containing
all four domains. It also does not establish that order is causal: the
order was held fixed rather than randomized.

## Frozen-condition verification

Before any Round 14 model call, the copied four-domain array was checked
for exact content equality and exact order against
`RSM_CRUX10_SPOOFED_INDEPENDENCE/fixture.json`, and the copied
`NAIVE_PROMPT` was checked for exact equality with Round 10's prompt
constant. The fixture was not changed after the run. Its SHA-256 is:

`fdb0cc1cc323cfc2edee43b64793f84c72a24c0558525d8a6a3816d498a27b1d`

The prompt SHA-256 is:

`5be0ec763c4572350174d0b58b7daaff41dd1dedc81a70c43fb7635a4d0294e2`

Full raw responses, parsed verdicts, frozen labels, errors, and computed
metrics are in `result.json`.

## Missing evidence

- Five batches are too small to estimate a population error rate.
- Only `gemini-3.5-flash` and one spoof shape were tested.
- Fixed order does not test randomized ordering or prove an order effect.
- The skeptical prompt and a second model were deliberately not run.
