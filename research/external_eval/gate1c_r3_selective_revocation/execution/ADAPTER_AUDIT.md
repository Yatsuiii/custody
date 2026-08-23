# Gate 1C-R3 Adapter and Metric Audit

Gate validity: VALID
Mechanical verdict: SELECTIVE-REVOCATION-SUPPORTED

R0 is the issuer-wide negative control. R3-root matches only the two
authenticated RootKeys selected for R_BAD_1 and R_BAD_2. The same 16-record
graph is used for both arms. No receipt schema field was added and no
historical record was edited.

Raw traces are frozen before metrics. Expected-ALLOW utilities and
expected-DENY false-ACT metrics both count finalized action_allowed=True.
Affected recall counts action_allowed=False. Independent recomputation:
True.

Scorer reads: 0
Payload-semantic inspection: False
True-origin to treatment: False
Relay signing key absent: True
Model calls/API cost: 0 / USD 0.00
