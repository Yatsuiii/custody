# RSM Crux13 Result — Round 10 Naive Spoofed `server_access` Miss Recurs

## Experiment review

Verdict: valid.

Baseline: Round 10's naive `server_access` call was 2/3 correct. It
returned SURVIVE for M2b even though the purported independent support was
a laundered restatement of revoked source B, so the frozen ground truth is
RETRACT. Round 10's naive pooled result was 10/12.

Hypothesis: the Round 10 spoofed M2b miss might be a sample-specific flip
rather than a stable naive failure. Five unchanged repetitions test whether
that miss recurs.

Changed variable: repetition only within the frozen condition. The exact
Round 10 spoofed `server_access` domain, naive prompt, model/endpoint,
parser, and labels were used. No retry, context change, or post-hoc
relabeling was performed. This is an isolated repetition of the call
condition, not a repeat of Round 10's full four-domain batch.

## Result

All five calls completed with no transport errors or missing verdicts. The
model returned M1=RETRACT and M2a=RETRACT every time, but M2b=SURVIVE every
time against the frozen M2b=RETRACT label.

| Repetition | M1 | M2a | M2b | Correct | Complete |
|---|---|---|---|---:|---|
| 1 | RETRACT | RETRACT | SURVIVE | 2/3 | yes |
| 2 | RETRACT | RETRACT | SURVIVE | 2/3 | yes |
| 3 | RETRACT | RETRACT | SURVIVE | 2/3 | yes |
| 4 | RETRACT | RETRACT | SURVIVE | 2/3 | yes |
| 5 | RETRACT | RETRACT | SURVIVE | 2/3 | yes |
| **Pooled** |  |  |  | **10/15** | **5/5** |

Per-position accuracy was M1 **5/5**, M2a **5/5**, and M2b **0/5**.
The M2b false-negative count was **5/5 (100%)**. The pooled exact
judgment accuracy was **10/15 (66.67%)**. Every parsed response was
complete and unambiguous under the frozen parser; the reasons varied
slightly but consistently treated the central badge-provisioning record as
independent support.

The complete-call per-call accuracy vector was
`[2/3, 2/3, 2/3, 2/3, 2/3]`: mean `0.6666666666666666`, population
variance `0.0`, and population standard deviation `0.0`. The M2b
false-negative indicator vector was `[1, 1, 1, 1, 1]`: mean `1.0`,
population variance `0.0`, and population standard deviation `0.0`.

## Interpretation

The Round 10 spoofed M2b miss recurred in all five exact isolated
repetitions. In this condition, the naive judge's error is repeatable rather
than an observed sampling flip. This supports the Round 10 threat-model
finding: a self-described independent check can cause the naive judge to
preserve a claim whose only real support is the revoked source.

This does not establish a general error rate. It is five calls from one
model on one hand-built spoof, and it does not repeat the full Round 10
four-domain batch or test the skeptical prompt. The zero within-condition
variance therefore means consistent behavior in this condition, not general
robustness. It is also not grounds to build semantic repair; the result is
evidence against treating the naive judge as a trustworthy independence
authority.

## Frozen-condition verification

Before any Round 13 model call, the copied domain was checked for exact
content equality with `RSM_CRUX10_SPOOFED_INDEPENDENCE/fixture.json`'s
`domains[0]` entry, and the copied `NAIVE_PROMPT` was checked for exact
equality with Round 10's prompt constant. The fixture was not changed after
the run. Its SHA-256 is:

`1b809e494c70bceef3607547799469d338850e9c7eb55e4e807e7f38071b6138`

The prompt SHA-256 is:

`5be0ec763c4572350174d0b58b7daaff41dd1dedc81a70c43fb7635a4d0294e2`

Full raw responses, parsed verdicts, labels, errors, and computed metrics
are in `result.json`.

## Remaining gaps

- Five repetitions are too small to estimate a population error rate.
- Only `gemini-3.5-flash` and one spoof shape were tested.
- This isolates the exact call condition; possible full-batch ordering or
  context effects were not measured.
- The skeptical prompt was deliberately not run in this round.
