# Gate 1B-R3 — Fail-Closed Signature Verification Correction

Status: preregistration/design only. R3 is not executed in this session.

## Identity and lineage

- Experiment ID: `EXT_GATE1B_R3_AUTHORITY_RECEIPT`
- Branch: `research/external-gate1b-r3-provenance-falsifier`
- Parent R2 preregistration: `e6333991f8813059ad334576d2fcbc0fd9afbdf4`
- Preserved R2 invalid attempt: `5bf3586173eef8c38249c7737ee9cf0661bf2840`
- Parent Gate 1B design: `cd75a059052229916980f1b992d48bd1e8c6eb9c`
- Failure classification: `INVALID_CRYPTOGRAPHIC_VERIFIER_BOUNDARY`

R2 passed import and fixture preflights, then entered treatment and stopped on
the forged-receipt case when the expected Ed25519 verification failure escaped
the receipt-verification boundary. No scorer result or security verdict was
produced. R2 remains preserved and is not patched or rerun.

## Single authorized R3 correction

R3 may change only the handling of the expected
`cryptography.exceptions.InvalidSignature` outcome at the receipt verifier
boundary. The verifier must map that exception to the already-frozen normal
invalid-receipt result:

```text
receipt_authenticated = False
effective receipt authority = NONE
consequential ACT = DENY
reason = RECEIPT_SIGNATURE_INVALID
```

No signed bytes, canonical serialization, receipt field, issuer key,
verification key, object commitment, PolicyKey, generation, scope, revision,
receipt identity, or authority rule changes.

## Exact fixture evidence

The frozen forged fixture uses:

```text
issuer_signature = "00" * 64
```

This is a correctly shaped 64-byte Ed25519 signature input represented by 128
hex characters. It is cryptographically invalid for the signed receipt and is
not changed in R3. The cryptographic primitive rejected it correctly; R2's
adapter failed only to normalize the rejection.

## Total-function boundary

The receipt verifier is total for the expected signature-validity outcomes:

- valid signature: continue all existing receipt checks;
- `InvalidSignature`: return the normal invalid-receipt result, never raise;
- any other unexpected exception: remain an invalid runner and stop; do not
  catch broad `Exception` or hide programmer/API/canonicalization failures.

## Preserved security experiment

R3 retains the exact R2/Gate 1B source, `tool_echo` attack, benign control,
vendor relay, P2 receipt, issuer/relay separation, B1/B6/B6P2/B3 baselines,
cases A–O, transforms, generation, multi-parent, revocation, scorer boundary,
metrics, denominators, reproducibility, model cost, and KILL/utility gates.
The 27-record fixture dry-run and `MEM-REVOKED-DESC == 1` gate remain unchanged.

## Pre-treatment requirements

Before treatment, R3 must pass local/remote lineage verification, repository
import preflight, the crypto-only preflight in `CRYPTO_CONTRACT.md`, the pinned
external source check, scorer/issuer/payload guards, and the 27/27 fixture
gate. A failure is `INVALID` before treatment.

## No execution in this session

This plan creates no runner, result, RESULT.md, or adapter audit. A future R3
authorization must preserve R2's invalid evidence and must not patch or rerun
R2 under its identity.
