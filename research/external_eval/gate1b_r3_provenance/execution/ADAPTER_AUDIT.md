# Gate 1B Adapter Audit

Status: VALID. This records the frozen native-interface
projections and P2 trust boundary; it is not a production receipt.

## Sources

- preregistration: 8822dae5fda2566d24e0d4115173d360df722eec
- external source: yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1
- attack path: code/laundering.py::tool_echo
- attack source digest: 20953759b9c99f90685de4f584b58fb217bc00b851e9cc394fb8792f52252cb7
- source tree: 7a1159a434e03b13c6c56f9fb09be2bc02d6ef65

## Native treatments

| Baseline | Runtime security input | Native provenance | Scorer truth |
|---|---|---|---|
| B0 | canonical event and action | none | absent |
| B1 | frozen Custody tool/source/revision/trust path | existing Custody fields | absent |
| B6 | frozen Architecture A structural path | role, caps, parents, policy | absent |
| B6P2 | B6 plus source-issued Ed25519 receipt | source object, issuer, scope, generation, commitment | absent |
| B3 | pinned official TMA-NM native item | true_origin in official fixture | ORACLE-COUPLED reference |

## Trust boundary

The issuer is vendor-source-authority, distinct from relay vendor_lookup. The
issuer's Ed25519 private key exists only inside the source producer. The relay
adapter has no signing key and receives only forwardable receipt data. The
verifier checks issuer signature, immutable object commitment, PolicyKey,
action scope, revision, and current generation.

The tool_echo case has no source object and no receipt. This is an event-path
fact, not a scorer label. B6P2 never reads payload bytes, true_origin, case
names, or scorer objects.

## Controls

The execution includes forged signature, wrong-object, wrong-scope,
old-generation, wrong-revision, unrelated replay, FREEFORM, mixed-parent,
cross-agent, and post-hoc revocation controls.

## Guards

{
  "passed": true,
  "payload_semantics_used": false,
  "runtime_forbidden_key_violations": [
    {},
    {}
  ],
  "scorer_reads_before_all_actions": [
    0,
    0
  ]
}
