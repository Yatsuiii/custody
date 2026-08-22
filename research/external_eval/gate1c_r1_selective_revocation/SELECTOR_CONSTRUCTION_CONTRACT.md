# Gate 1C-R1 Selector-Construction Contract

This contract is the only behavioral correction permitted for R1. It converts
the invalid attempt's mutable-object construction failure into deterministic
construction of the same frozen root selector. It does not change revocation
semantics.

## Inputs and outputs

Input:

- the already-built Gate 1C immutable graph;
- the two preselected authenticated root records `R_BAD_1` and `R_BAD_2`;
- their verified P2 receipts and durable root record IDs.

Output:

```text
revoked_root_keys: set[RootKey]
```

where `RootKey` is the exact existing Gate 1C tuple:

```text
(
    receipt.issuer_id,
    receipt.receipt_id,
    receipt.upstream_record_id,
    receipt.upstream_object_commitment,
    tuple(receipt.policy_key),
    receipt.granting_generation,
    root_record.record_id,
)
```

The output set contains exactly two keys. It is not a set of records.

## Ownership and lifecycle invariant

The graph builder owns record construction. The selector builder owns only
canonical key derivation. The verifier owns selector lookup. No helper may
implicitly insert a record or substitute a different root.

The required order is:

```text
build_graph
  -> resolve/authenticate R_BAD_1 and R_BAD_2 roots
  -> derive immutable RootKeys
  -> dry-run selector manifest
  -> evaluate R0 and R3-root arms
```

Selector construction must complete before any action or scorer path. A
construction error is an invalid runner state, not a security result.

## Canonical-key requirements

The constructor must:

1. verify a receipt is present for each selected root;
2. use the authenticated receipt fields and durable root record ID already
   required by Gate 1C;
3. normalize `PolicyKey` to its existing immutable tuple representation;
4. reject mutable values in the key;
5. reject duplicate keys and a key count other than two;
6. verify the key manifests correspond to `ROOT-02` and `ROOT-03` without
   making those aliases part of security decisions;
7. return a deterministic set/manifest suitable for canonical hashing.

The constructor may not use payload bytes, action target text, `compromised`,
`bad_interval`, `expected_allow`, `expected_deny`, `true_origin`, scorer state,
or a case label.

## Dry-run manifest

The pre-treatment manifest must record only normalized structural facts:

| Check | Required value |
|---|---:|
| frozen graph records | `16` |
| unique graph records | `16` |
| authenticated roots | `5` |
| selected roots | `2` |
| unique RootKeys | `2` |
| mutable objects in selector | `0` |
| treatment/scorer calls | `0` |

The manifest must include the canonical key digest and root IDs, but not
payload semantics or hidden scorer truth. Any mismatch stops R1 before arm
evaluation.

## Error handling

The R1 correction addresses only the known `TypeError` caused by putting a
mutable `SecurityRecord` in a set. Missing receipts, duplicate keys,
non-canonical fields, or unexpected exceptions remain invalid pretreatment
conditions. Do not broaden an exception handler into a deny-all fallback.

The R3 verifier and the root-bound authority decision are otherwise reused
unchanged. No new receipt field or revocation state is added.
