# Gate 1C-R1 Equivalence Audit

Status: design-only audit. No R1 runner or result exists.

## Normalization allowed

The Gate 1C design and Gate 1C-R1 specification may differ only after
normalizing:

1. experiment identity (`EXT_GATE1C_R1_SELECTIVE_RECEIPT_REVOCATION`);
2. branch and lineage references;
3. the preserved invalid-attempt record;
4. selector-construction ownership/lifecycle;
5. the pre-treatment immutable selector-manifest check.

No other normalization is permitted.

## Required exact equivalence

The following remain byte/semantic-equivalent to the frozen Gate 1C design:

- R3 failure diagnosis: `SELECTOR-TOO-COARSE`;
- P2 receipt schema and all receipt fields;
- issuer, signing key, relay separation, and signature verification;
- Gate 1C graph topology, record IDs, parentage, and support roots;
- roots `R_PRE`, `R_BAD_1`, `R_BAD_2`, `R_POST`, `R_OTHER`;
- `D_PRE`, `D_BAD1`, `D_BAD2`, `D_POST`, `D_OTHER`, `D_MIX`;
- cross-agent, record-reissue, revoked-copy, sibling, generation, and escape
  controls;
- R0 issuer-wide negative control;
- R3 receipt-root-bound selector meaning and authority resolution;
- transformation, generation, multi-parent, cross-agent, and revocation
  semantics;
- historical immutability requirement;
- scorer/runtime separation and no payload-semantic authority;
- raw metrics, denominators, thresholds, verdict precedence, and KILL gates;
- two clean runs, normalized digest, `model_calls = 0`, and API cost `$0`.

The pinned external context remains `yedidel/mem-inv-bench` at commit
`63f1359d677efbe1a65b982b2a54cabfec97f1e1`, with the previously frozen
`code/laundering.py::tool_echo` source and digest. No external attack or
benign-control semantics are changed.

## Single-variable audit

| Concern | Gate 1C | Gate 1C-R1 | Equivalent? |
|---|---|---|---|
| selector meaning | root-bound `RootKey` set | same root-bound `RootKey` set | yes |
| selector inputs | existing authenticated receipt/root fields | same fields | yes |
| selector container construction | attempted set of mutable records before key derivation | immutable tuple keys before set insertion | lifecycle only |
| graph/parentage | frozen Gate 1C graph | unchanged | yes |
| verifier/action logic | frozen R3/root-bound behavior | unchanged | yes |
| metrics/gates | frozen Gate 1C | unchanged | yes |

The only causal difference is that R1 reaches the already-specified arms by
constructing the same selector from immutable keys. It cannot improve or
weaken the candidate's authority semantics.

## Invalid-attempt boundary

The preserved Gate 1C attempt failed at:

```text
revoked_roots = {objects["R_BAD_1"], objects["R_BAD_2"]}
TypeError: unhashable type: 'dict'
```

This happened before `evaluate_arm()`, action decisions, scorer reads, or
metrics. R1 is therefore an execution-lifecycle correction, not a
result-dependent change.

## Validity decision

`PREREGISTRATION-VALID` if and only if this audit remains the complete
security-equivalence diff and the package contains no executable artifacts.
Otherwise the R1 package must not be executed.
