# Research Access Operator: investigated 2026-08-15, packet leg dropped

The idea: tell it the dataset you need, and it owns the administrative journey
to authorised access. Eligibility, data use limitations, the packet, the
institutional approvals, the revisions, the renewal and the close-out.

**Verdict on the falsifiable leg: DROP**, on thresholds registered before the
scenarios were written. Given the published rules, `gemini-3.7-flash` caught
**21 of 21** planted defects, invented **zero** identifiers, and raised **zero**
false alarms on the clean control.

## What was tested, and against what

Eight dbGaP access requests, seven carrying one planted defect each, one clean.
Every defect is wrong according to a specific published NIH requirement, quoted
in `probe/scenarios.py` next to the scenario that violates it, so a disagreement
about grading is a disagreement with NIH's text rather than with me.

| scenario | planted defect | caught |
| --- | --- | --- |
| S1 | research use inconsistent with the dataset's limitation | 1.00 |
| S2 | collaborator at another institution, needs their own request | 1.00 |
| S3 | department chair substituted for the Signing Official | 1.00 |
| S4 | dataset requires local IRB approval, applicant skipping it | 1.00 |
| S5 | plan to share files beyond those permitted to handle them | 1.00 |
| S6 | four-year project, one-year access, no renewal plan | 1.00 |
| S7 | linking to a registry to recontact participants | 1.00 |
| S8 | nothing wrong (control) | 0.00 false alarms |

Fabrication 0.000. Completeness 0.667, which turned out to be **my metric being
wrong rather than the model**: the only field ever missing was `personnel`, in
exactly the scenarios where the researcher never named anyone, and the model
left it empty and listed it under unknowns instead of inventing names. That is
the behaviour you would want. The metric was penalising the right answer.

## The help was maximal, and that is the point

The model was handed the published requirements in the prompt and a fixed enum
of blocking-issue codes to choose from. Both inflate the score and both are
disclosed. The design is deliberate: a failure *with* that much help would have
been conclusive proof of a gap. Success with it does not prove the model would
cope with a real application spanning thirty datasets and ambiguous consent
groups, and this write-up does not claim that.

What it does establish is that the burden has moved. To justify building the
packet leg, someone would now have to construct a harder version and show it
fails. That is another day of work before any product exists, with sixteen days
on the clock.

## What survives, and why it is not enough

The leg this probe cannot test is the one the idea was really about: carrying a
request through weeks of institutional back-and-forth between the researcher,
the IRB, the security office, the Signing Official and the DAC, surviving
returned revisions, then renewing or closing out a year later.

Three problems with building on that, in order of severity:

1. **It cannot be verified.** There is no ground truth for "would this have been
   approved" without a real Data Access Committee. Every falsifier would be
   self-graded, and self-graded is the one thing this project has refused all
   the way through.
2. **It is what the incumbents sell.** Huron and Kuali market exactly workflow
   routing, notifications, status and electronic execution. The differentiator
   was supposed to be the intelligent packet, and the packet is solved.
3. **The demo would be mocked institutions.** A judge watching a four-minute
   video of an agent corresponding with fictional signing officials is watching
   an assertion, not a proof.

## Kept for the record

`probe/scenarios.py` carries the eight scenarios with the NIH requirement each
one violates. `proof-out/f5.json` holds all 24 packets. The thresholds are in
`.claude/SESSION_CONTRACT.md`, written before the scenarios existed.
