# Gate 1C-R2 Adapter Audit

Status: VALID

R2 uses the explicit ROOT_ALIASES -> RECORDS_BY_ID resolver before deriving
the same frozen RootKeys. The R0 arm uses issuer-wide revocation; the candidate
uses only the two authenticated keys for R_BAD_1 and R_BAD_2. No payload bytes,
scorer truth, compromise labels, or `true_origin` values enter treatment.

Receipt schema changed: False
Scorer reads: 0
Payload-semantic inspection: False
Relay signing key absent: True
