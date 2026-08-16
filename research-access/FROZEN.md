# Frozen 2026-08-16

Not abandoned, not resumed. Closed research, not part of the Custody
submission.

**The thesis.** A Research Access Operator would navigate controlled-access
data requests (dbGaP and similar) where the failure mode is an agent inventing
eligibility facts it was never given.

**Why it stopped: DROP.** Eight scenarios built from verified NIH requirement
text, with deterministic scoring and regex fabrication detection over the raw
answers. **21 of 21 traps caught, zero fabrication.** The model declined to
invent institutional signing officials, IRB determinations or personnel it had
not been told about. The anti-fabrication product had nothing to prevent.

A metric bug found mid-run is worth remembering: completeness initially
penalised the model for leaving `personnel` blank when the scenario named
nobody, i.e. it scored correct behaviour as a failure. Caught because the
number was implausibly bad, not because anything flagged it.

This was a paper exercise throughout. No contact was made with dbGaP, NIH,
eRA Commons or any institution.
