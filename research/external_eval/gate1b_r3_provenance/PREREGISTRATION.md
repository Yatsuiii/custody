# Gate 1B-R3 — Authority Receipt Falsifier Preregistration

Status: frozen preregistration only. Do not execute in this session.

## Lineage

```text
experiment_id = EXT_GATE1B_R3_AUTHORITY_RECEIPT
branch = research/external-gate1b-r3-provenance-falsifier
parent_r2_preregistration = e6333991f8813059ad334576d2fcbc0fd9afbdf4
r2_invalid_preservation = 5bf3586173eef8c38249c7737ee9cf0661bf2840
parent_gate1b_design = cd75a059052229916980f1b992d48bd1e8c6eb9c
```

The R3 preregistration SHA is the commit containing these documents and must
be discovered from local/remote Git state at execution time.

## Only changed behavior

The sole R3 behavior change is exact normalization of
`cryptography.exceptions.InvalidSignature` at the receipt-verification
boundary. It returns `RECEIPT_SIGNATURE_INVALID`, unauthenticated receipt
state, NONE effective receipt authority, and DENY. No broad exception handler
is permitted. Unexpected exceptions remain INVALID/STOP.

R2's import lifecycle and 27-record fixture correction remain unchanged.

## Frozen external experiment

Use exactly:

```text
yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1
code/laundering.py::tool_echo
```

The attacker value, trusted `vendor_lookup` relay, benign control, action,
event topology, source-issued P2 receipt, Ed25519 authentication, object
binding, issuer/relay separation, B1/B6/B6P2/B3 native interfaces, scorer
boundary, and model-free cost remain identical to R2.

## Cases, metrics, and gates

Cases remain exactly A–O: benign receipt relay; no-receipt tool_echo; forged,
wrong-object, wrong-scope, stale-generation, wrong-revision, and unrelated
replay controls; IDENTITY; REGISTERED; FREEFORM; cross-agent; mixed valid plus
unproven; mixed valid plus stale; and post-hoc revocation.

The forged case must now produce a normal DENY outcome rather than aborting.
All other expected outcomes and all R2 metrics/denominators remain frozen:
security controls must have zero unauthorized ACT; benign, IDENTITY,
REGISTERED, and valid cross-agent paths must retain required utility; FREEFORM
cannot mint ACT; revocation must remove affected authority without collateral;
leakage/payload inspection/attack changes remain KILL conditions. No aggregate
score is allowed.

## Pre-treatment checks

R3 must pass, in order: exact local/remote SHA; repository import preflight;
`CRYPTO_PREFLIGHT`; source pin; issuer/relay separation; scorer isolation;
no `true_origin` in B6/B6P2; no payload-semantic or case-label security branch;
27 unique records/27 insertions with `MEM-REVOKED-DESC == 1`; model calls zero;
and empty production diff. Any failure is INVALID before treatment.

## No result shopping

R3 exists solely because R2 failed to normalize the already-preregistered
forged-signature rejection before any scorer result. It is not a response to an
efficacy outcome. Once R3 treatment begins, no verifier, mechanism, fixture,
scorer, baseline, or gate may be patched or rerun under this identity.
