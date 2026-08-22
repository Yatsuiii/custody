# Gate 1C — Frozen R3 Failure Trace

Status: failure localization and design evidence only. No Gate 1C runner or
mechanism exists. Gate 1B-R3 is preserved and is not rerun.

## Frozen evidence

- Experiment: `EXT_GATE1B_R3_AUTHORITY_RECEIPT`
- R3 preregistration: `8822dae5fda2566d24e0d4115173d360df722eec`
- R3 execution commit: `f3eb51cbdd52eca0f30f9989311f944b5ee50c35`
- Mechanical result: `COMPOSITION-FAILS`
- First failed gate: `REVOCATION_COLLATERAL`
- R3 source: `research/external_eval/gate1b_r3_provenance/execution/`

R3 completed both normalized runs. The affected descendant was denied in both
runs and no historical record changed. The unrelated receipt-backed control
was also denied in both runs, so selective revocation was not demonstrated.

## Actual revocation path

The frozen runner stores revocation state as an issuer-wide set:

```text
DurableState.revoked_issuers = {issuer_id}
```

The revocation fixture executes the equivalent of:

```text
state.revoked_issuers.add("vendor-source-authority")
```

`ReceiptVerifier.verify` checks `receipt.issuer_id in state.revoked_issuers`
before checking the receipt's upstream object, commitment, PolicyKey, scope,
or generation. A match returns `REVOKED_RECEIPT_ISSUER`.

This is selector R0 (issuer-wide revocation), not receipt-root revocation.

## Affected lineage trace

| Field | Frozen R3 value |
|---|---|
| action record | `MEM-REVOKED-DESC` |
| direct parents | `ROOT-REVOKED` |
| support roots | `ROOT-REVOKED` |
| authority dependency | kind `authority`; root `ROOT-REVOKED`; receipt `65056c55167e9a5037eaccd9`; PolicyKey `finance/vendor_lookup/lookup/R1/export.send`; granting generation `1` |
| root receipt issuer | `vendor-source-authority` |
| root upstream record | `SRC-BENIGN-A` |
| root object commitment | `bbe404f9d97da998250c205c47e3afeb6c941d4bad8700978ac41fe825abcaf1` |
| root PolicyKey | `(finance, vendor_lookup, lookup, R1, export.send)` |
| root generation | `1` |
| revocation selector | `issuer_id = vendor-source-authority` |
| selector match | `true` |
| final decision | `DENY`, reason `REVOKED_RECEIPT_ISSUER` |

## Unrelated lineage trace

| Field | Frozen R3 value |
|---|---|
| action record | `MEM-UNRELATED-DESC` |
| direct parents | `ROOT-UNRELATED` |
| support roots | `ROOT-UNRELATED` |
| authority dependency | kind `authority`; root `ROOT-UNRELATED`; receipt `5753d9919c8248112d9b93fc`; PolicyKey `finance/clean_registry/lookup/R1/export.send`; granting generation `1` |
| root receipt issuer | `vendor-source-authority` |
| root upstream record | `SRC-CLEAN` |
| root object commitment | `e03ddb574a3ed858fa316d7a7f965e1176592f32d81ecb8d4665508515f63106` |
| root PolicyKey | `(finance, clean_registry, lookup, R1, export.send)` |
| root generation | `1` |
| revocation selector | `issuer_id = vendor-source-authority` |
| selector match | `true` |
| final decision | `DENY`, reason `REVOKED_RECEIPT_ISSUER` |

## First indistinguishability point

The two lineages are distinguishable in durable evidence before revocation:
receipt IDs, upstream record IDs, object commitments, PolicyKeys, support roots,
and authority dependencies all differ. They become indistinguishable at the
first verifier check that tests only the issuer-wide revocation set. The
verifier returns before consulting any of those root-specific fields.

Therefore the causal failure is **issuer-wide revocation**, not a missing P2
receipt field and not a support-closure loss. The R3 dependency graph retains
the information needed to target a root; the selected revocation predicate
discarded that distinction.

## Scope of conclusion

This trace localizes the R3 collateral failure. It does not implement or prove
a selective selector. A future Gate 1C must test root-bound revocation and the
bounded-compromise and escape controls defined in its preregistration.
