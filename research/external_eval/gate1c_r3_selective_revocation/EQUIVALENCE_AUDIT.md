# Gate 1C-R3 Equivalence Audit

Status: design-only. No R3 runner or result exists.

## Allowed normalization

R2 and R3 may differ only by:

1. experiment identity, branch, and lineage references;
2. preservation of the invalid R2 attempt;
3. the explicit metric-lifecycle contract and independent metric recomputation
   check.

No treatment or security-semantic normalization is permitted.

## Required exact equivalence

The following remain unchanged:

- R2/R1 alias-to-durable-record resolver;
- P2 receipt schema and RootKey fields;
- issuer, authentication, relay separation, and support/dependency closure;
- the frozen `16`-record graph and all roots/parentage;
- R0 issuer-wide and R3 root-bound arms;
- affected, utility, mixed-parent, cross-agent, reissue, revoked-copy,
  sibling, generation, and historical-immutability cases;
- scorer boundary, no payload-semantic authority, and compromise discovery
  remaining out of scope;
- raw metrics, denominators, thresholds, PASS/KILL mappings, and reproducibility;
- external pin `yedidel/mem-inv-bench` at
  `63f1359d677efbe1a65b982b2a54cabfec97f1e1`;
- model calls `0` and API cost `$0`.

## Single-variable comparison

| Concern | R2 | R3 | Difference class |
|---|---|---|---|
| action observations | frozen `action_allowed` | same | none |
| expected-ALLOW metric | correct count | same | none |
| expected-DENY metric | inverted in invalid runner | count `action_allowed=True` | metric lifecycle only |
| authority/selector | frozen | unchanged | none |
| graph/cases | frozen | unchanged | none |
| verdict gates | frozen | unchanged | none |

R3 does not reinterpret R2's raw action traces as a security result. It only
prevents the known metric inversion from converting correct DENY outcomes into
false ACT counts.

## No result shopping

R2's `KILL` label was rejected because the metric table violated the frozen
contract. R3 changes accounting solely because the error was mechanically
identified after treatment; it does not alter a security mechanism or select
a more favorable case.

## Validity rule

R3 is valid only if raw-trace recomputation equals every reported metric and the
same frozen gate mapping is then applied. Otherwise classify `INVALID` and stop.
