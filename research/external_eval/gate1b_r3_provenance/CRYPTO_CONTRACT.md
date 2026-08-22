# Gate 1B-R3 Cryptographic Verifier Contract

This contract defines the only R3 correction and its pre-treatment check.

## Receipt-verification boundary

For the existing signed receipt bytes and frozen Ed25519 public key:

```text
verify_receipt_signature(receipt, public_key)
```

must behave as follows:

| Input outcome | Boundary result | Security effect |
|---|---|---|
| signature verifies | authenticated = true; continue existing checks | no change |
| `cryptography.exceptions.InvalidSignature` | authenticated = false; reason `RECEIPT_SIGNATURE_INVALID` | receipt authority NONE; consequential DENY |
| any other unexpected exception | exception remains visible to runner | INVALID/STOP, not swallowed |

R3 must catch exactly `InvalidSignature`. It must not use
`except Exception: deny`, alter canonical serialization, replace the key,
weaken object binding, or add an attack/case label.

## Frozen forged fixture

The R2/R3 forged receipt uses the unchanged signature string `"00" * 64`.
`bytes.fromhex` yields 64 bytes, so this is a correctly shaped Ed25519
signature input. Verification rejects the signature cryptographically because
it does not authenticate the frozen receipt message under the issuer key. The
fixture is not malformed at a different API layer and must not be rewritten.

## CRYPTO_PREFLIGHT

Before any benchmark fixture, defense, action, or scorer execution, start a
separate process under the frozen R3 environment and use neutral synthetic
bytes only:

1. create a local Ed25519 keypair;
2. sign fixed neutral bytes;
3. call the exact R3 verifier boundary and require valid authentication;
4. alter the message or signature;
5. call the same boundary;
6. require no exception escapes, `authenticated = false`, and reason exactly
   `RECEIPT_SIGNATURE_INVALID`.

This check must not use the Gate 1 attack, benign payload, scorer truth,
fixture IDs, receipt authority fields, or any baseline. It must not write a
result. Required marker: `CRYPTO_PREFLIGHT=PASS`.

## Existing preflights retained

The future R3 run still requires the R2 repository-root import preflight and
the 27-record dry-run before treatment. The crypto preflight is additive as an
environment/API contract check only; it does not change any security case.
