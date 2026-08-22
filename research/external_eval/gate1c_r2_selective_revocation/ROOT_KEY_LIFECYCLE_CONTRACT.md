# Gate 1C-R2 RootKey Lifecycle Contract

This is the only R2 runner correction. It repairs alias-to-durable-record
resolution in the pre-treatment RootKey check. It does not alter RootKey
semantics, selector meaning, authority resolution, or any scored case.

## Frozen namespaces

The graph uses two explicit namespaces:

```text
ROOT_ALIASES:   alias -> durable record ID
OBJECTS_BY_ALIAS: alias/case name -> SecurityRecord
RECORDS_BY_ID:  durable record ID -> SecurityRecord
```

For the five roots:

```text
R_PRE   -> ROOT-01
R_BAD_1 -> ROOT-02
R_BAD_2 -> ROOT-03
R_POST  -> ROOT-04
R_OTHER -> ROOT-05
```

The canonical resolver must take an alias, look up its durable ID in
`ROOT_ALIASES`, resolve that ID in `RECORDS_BY_ID`, and assert that the resolved
record's `record_id` equals the manifest value. It must never use a durable ID
as a key in `OBJECTS_BY_ALIAS`.

## RootKey

The key is exactly the frozen R1 contract:

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

`PolicyKey` is the existing immutable tuple. The selector contains two such
tuples for `R_BAD_1` and `R_BAD_2`; it never contains a `SecurityRecord`, dict,
or list. No `repr()`, object identity, Python hash value, payload, action
target, scorer field, or case label is part of identity.

## Required lifecycle

```text
build frozen graph
  -> derive RECORDS_BY_ID without changing records
  -> resolve all five root aliases and assert IDs
  -> derive five RootKeys
  -> verify deterministic/collision-free RootKeys
  -> derive exactly two selected keys (R_BAD_1/R_BAD_2)
  -> verify selector manifest without treatment/scorer
  -> evaluate unchanged R0 and root-bound arms
```

The resolver is a pure namespace/identity operation. It does not construct a
new record, mutate the graph, issue a receipt, revoke authority, evaluate an
action, or read scorer state.

## Pretreatment assertions

R2 must stop before treatment unless all assertions hold:

- `16` graph records and `16` unique durable IDs;
- `5` authenticated roots resolve through the explicit resolver;
- reconstructing each RootKey twice yields identical tuples;
- the five RootKeys are unique and hashable;
- changing an identity-bearing receipt/root field changes its key;
- changing non-identity metadata does not change its key;
- selected aliases are exactly `R_BAD_1`, `R_BAD_2`;
- selected keys are exactly `2` and unique;
- `R_PRE`, `R_POST`, and `R_OTHER` are not selected;
- mutable selector members, treatment calls, and scorer reads are `0`.

A failed assertion is `INVALID` before either arm. Unexpected resolver errors
are not converted into security decisions.
