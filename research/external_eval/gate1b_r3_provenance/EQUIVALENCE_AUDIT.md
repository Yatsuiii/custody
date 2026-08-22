# Gate 1B-R2 to Gate 1B-R3 Equivalence Audit

Status: preregistration audit only; R3 has not executed.

## Permitted normalization

Only these differences are allowed:

1. experiment identity and branch/lineage;
2. R2 invalid-attempt preservation reference;
3. normalization of the expected `InvalidSignature` outcome to the existing
   `RECEIPT_SIGNATURE_INVALID` deny path;
4. a neutral crypto-only preflight before treatment.

## Security-equivalence matrix

| Surface | R2 | R3 | Result |
|---|---|---|---|
| External source/attack | pinned `tool_echo` source and commit | identical | EQUIVALENT |
| Benign control/relay/action | frozen Gate 1B world | identical | EQUIVALENT |
| P2 receipt schema/serialization | unchanged | identical | EQUIVALENT |
| Issuer/key/object binding | source issuer, Ed25519, commitment binding | identical | EQUIVALENT |
| B1/B6/B6P2/B3 | frozen native interfaces | identical | EQUIVALENT |
| Cases | A–O | identical | EQUIVALENT |
| IDENTITY/REGISTERED/FREEFORM/cross-agent | frozen transforms | identical | EQUIVALENT |
| Generation/multi-parent/revocation | frozen semantics and selectors | identical | EQUIVALENT |
| Scorer boundary | hidden scorer; no `true_origin` in B6/B6P2 | identical | EQUIVALENT |
| Payload-semantic prohibition | prohibited | identical | EQUIVALENT |
| Metrics/denominators | frozen R2 | identical | EQUIVALENT |
| Utility/KILL/verdict gates | frozen R2 | identical | EQUIVALENT |
| Reproducibility/model/API cost | two clean runs; `0/$0` | identical | EQUIVALENT |
| Expected invalid signature | exception escaped (R2 failure) | exact exception maps to existing deny reason | AUTHORIZED CORRECTION ONLY |

## Boundary interpretation

R2 demonstrated a verifier API liveness defect: invalid cryptographic input
could abort treatment. It did not demonstrate forged receipt acceptance. R3
normalizes only this already-required invalid-receipt outcome and preserves the
R2 limitation as evidence. Unexpected errors remain visible and invalidate the
run.

## Pre-treatment audit gates

Before any R3 treatment, verify the R3 SHA/remote branch, import preflight,
`CRYPTO_PREFLIGHT`, source pin, scorer/issuer/payload guards, and the 27/27
fixture gate. A failed gate is INVALID before treatment. After treatment begins,
no result-dependent correction or rerun is allowed.

## Conclusion

`PREREGISTRATION-VALID`: R3 changes only the cryptographic verifier boundary
for the expected `InvalidSignature` condition plus a neutral preflight. All
security-relevant behavior, cases, metrics, denominators, and KILL gates remain
frozen equivalent to R2 and the parent Gate 1B design.
