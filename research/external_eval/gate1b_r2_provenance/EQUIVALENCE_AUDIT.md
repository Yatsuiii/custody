# Gate 1B-R1 to Gate 1B-R2 Equivalence Audit

Status: preregistration audit only; R2 has not executed.

## Permitted normalization

Only these differences are allowed:

1. experiment ID and branch/lineage;
2. R1 invalid-attempt preservation reference;
3. explicit repository-root `PYTHONPATH` launch contract;
4. import-only preflight before fixture construction/treatment.

## Security-equivalence matrix

| Surface | R1 | R2 | Result |
|---|---|---|---|
| External source/commit | `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1` | identical | EQUIVALENT |
| Attack/control | exact `tool_echo` and benign control | identical | EQUIVALENT |
| Relay/issuer | `vendor_lookup` forwards; source issues P2 | identical | EQUIVALENT |
| Receipt fields/binding/Ed25519 | frozen P2 object-bound receipt | identical | EQUIVALENT |
| Baselines | B1, B6, B6P2, contextual B3 | identical | EQUIVALENT |
| Cases | A–O | identical | EQUIVALENT |
| IDENTITY/REGISTERED/FREEFORM | frozen transform behavior | identical | EQUIVALENT |
| Cross-agent | forwarding without root minting/amplification | identical | EQUIVALENT |
| Generation | exact PolicyKey/granting-generation freshness | identical | EQUIVALENT |
| Multi-parent | preserve all parents/dependencies; no washing | identical | EQUIVALENT |
| Revocation | same selector/topology/immutability/collateral rules | identical | EQUIVALENT |
| Scorer boundary | hidden scorer; no labels/`true_origin` in B6/B6P2 | identical | EQUIVALENT |
| Payload semantics | prohibited | identical | EQUIVALENT |
| Metrics/denominators | frozen R1 values | identical | EQUIVALENT |
| KILL/verdict gates | frozen R1 precedence | identical | EQUIVALENT |
| Model/API cost | `0 / $0` | identical | EQUIVALENT |

## Root-only difference

R1 failed because the nested script invocation did not make the repository
root importable. R2 adds only the launcher/import contract and an import-only
preflight. No production package layout or security decision receives a new
field. R1's successful 27-record fixture correction remains unchanged.

## Required audit checks

Before R2 treatment, verify the source/attack pin, B6/B6P2 lack of
`true_origin`, scorer isolation, issuer/relay key separation, no payload or
case-label branch, and the 27/27 fixture gate. A failure is `INVALID`, not a
security result. After any treatment begins, no correction or rerun is allowed
under this R2 identity.

## Conclusion

`PREREGISTRATION-VALID`: R2 is a runner-lifecycle correction only. All
security-relevant behavior, cases, metrics, denominators, and verdict/KILL
gates are frozen equivalent to R1 and the parent Gate 1B design.
