# Gate 1B-R2 — Invalid Attempt 01 Preservation

Status: `INVALID_RUNNER_CRYPTOGRAPHIC_EXCEPTION`. This preserves the first R2
attempt and is not a security result.

## Lineage and runner evidence

- R2 preregistration: `e6333991f8813059ad334576d2fcbc0fd9afbdf4`
- Branch: `research/external-gate1b-r2-provenance-falsifier`
- Pinned external source: `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1`
- Runner: `research/external_eval/gate1b_r2_provenance/execution/run.py`
- Runner SHA-256: `3194eb0ba860550592d479021bdea1ffbc66ec3cf94cd8eea0c05976e30595e1`

The frozen root/PYTHONPATH launcher and separate import-only preflight passed.
The 27-record dry-run also passed:

```text
authoritative IDs = 27
unique IDs = 27
expected insertions = 27
MEM-REVOKED-DESC = 1
```

## Failure boundary

Treatment began. The runner completed earlier baseline work in the first case
and reached the forged-receipt control. During B6P2 receipt verification, the
invalid Ed25519 signature escaped the verifier instead of becoming a frozen
deny outcome:

```text
cryptography.exceptions.InvalidSignature
```

No scorer evaluation occurred and no result artifact was written. No B6P2
security endpoint, benign/tool_echo score, forgery score, transformation score,
multi-parent score, generation score, or revocation score exists. Scorer reads
were `0`; no mechanical security verdict exists; model/API cost was `$0`.

This is a runner/adapter exception after treatment began, not evidence of an
unauthorized ACT and not a valid `COMPOSITION-SUPPORTED`, `COMPOSITION-FAILS`,
`NO-UTILITY-GAIN`, or `KILL` result.

## Integrity

- Pinned external checkout remained at the required commit and clean.
- Production diff under `custody/`, `tests/`, `live/`, `scripts/`, `web/`, and
  `research/design/`: empty.
- Frozen suite: `python -m unittest discover tests` — `381/381` passed.

The R2 runner and this preservation record remain evidence of an invalid
attempt. R2 is not patched or rerun under this identity.
