# Gate 1C-R2 Equivalence Audit

Status: design-only. No R2 runner or result exists.

## Allowed normalization

R1 and R2 may differ only by:

1. experiment identity and branch;
2. lineage and preservation references;
3. the recorded R1 pre-treatment failure;
4. explicit alias-to-durable-record namespace resolution in the RootKey
   preflight;
5. the associated resolver-only dry-run assertions.

No security-relevant normalization is allowed.

## Required equivalence

The following remain identical to R1 and the frozen Gate 1C design:

- P2 receipt schema and RootKey fields;
- issuer, authentication, relay separation, and authority dependencies;
- roots `R_PRE`, `R_BAD_1`, `R_BAD_2`, `R_POST`, `R_OTHER`;
- all `16` graph records, durable IDs, parentage, support roots, and topology;
- R0 issuer-wide negative control;
- R3 receipt-root-bound candidate selector meaning;
- affected, unrelated, temporal, mixed-parent, cross-agent, reissue, receipt
  copy, sibling, generation, and historical-immutability cases;
- scorer/runtime separation and no payload-semantic authority;
- metrics, denominators, PASS/KILL mappings, and failure taxonomy;
- two clean normalized traces, `model_calls = 0`, and API cost `$0`;
- pinned external context `yedidel/mem-inv-bench` commit
  `63f1359d677efbe1a65b982b2a54cabfec97f1e1` and its frozen tool-echo path.

## Single-variable comparison

| Concern | R1 | R2 | Difference class |
|---|---|---|---|
| RootKey fields | frozen tuple | same tuple | none |
| selector meaning | revoke keys for R_BAD_1/R_BAD_2 | same | none |
| root resolution | values of alias map indexed in alias-keyed object map | explicit alias -> ID -> record resolver | lifecycle only |
| graph/records | frozen 16-record graph | unchanged | none |
| arms/verifier | unchanged R0/root-bound | unchanged | none |
| metrics/gates | frozen | unchanged | none |

The R2 resolver only prevents the R1 `KeyError: 'ROOT-01'`. It cannot change
which authenticated roots are selected or how authority is resolved.

## No result shopping

R1 produced no arm, action, scorer, metric, or efficacy result. The R2 change
was selected solely from that pre-treatment namespace error. No mechanism is
changed in response to a security outcome.

## Validity decision

The R2 preregistration is valid only while the resolver correction is the
complete difference and the package contains no executable artifacts.
