# Gate 1 Adapter Audit

Generated from `result.json`; this artifact records the frozen native
interfaces and does not change any baseline or attack semantics.

Preregistration: `c561e253f97822d45d0a31bb68163738c6a36f4f`
External source: `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1`
Attack source digest: `20953759b9c99f90685de4f584b58fb217bc00b851e9cc394fb8792f52252cb7`

## Baseline projections

| Baseline | Runtime fields | Metadata provenance | Instrumentation |
|---|---|---|---|
| B0 | payload, tool_identity, operation, task, action_request, ordinary_metadata | canonical observed event only | NATIVE-RUNTIME |
| B1 | payload, tool_identity, source_tool, source_revision, operation, configured_trust, action_request, scope | frozen Custody collector/configuration | NATIVE-RUNTIME |
| B2 | content, item, edge_untrusted, asserts_value, action_request, scope | pinned generic lineage signal projection | NATIVE-RUNTIME |
| B3 | official_item, content, true_origin, origin, act_class, scope, t_write, item_id, corroborations, meta, looks_benign, edge_untrusted, indep_trusted, asserts_value, action_request | official pinned fixture/native monitor; true_origin is oracle-coupled | ORACLE-COUPLED |
| B6 | payload, tool_identity, source, operation, revision, operation_role, configured_caps, observed_parent_ids, transform_class, policy_generation, action_scope, action_request | frozen Architecture A collector/policy projection | NATIVE-RUNTIME |

## Native code paths

- B0 uses a deterministic memory store with no security gate.
- B1 invokes the frozen `custody.origin.take_custody`, `CustodyGraph`, and `ExportGateway` path.
- B2 invokes the pinned TMA-NM `authorized('lineage', ...)` comparator using only its generic edge signal projection.
- B3 invokes the pinned `build_items(..., 'tool_echo', ...)` and `authorized('tma_nm', ...)` functions. Its `true_origin` is produced by that official fixture and is labelled oracle-coupled.
- B6 uses only the frozen relay/unknown-context authority rule; it does not inspect payload text or consume B3 metadata.

## Boundary findings

The common attack is one trusted-tool relay carrying the attacker value.
B3 has a stronger native origin-labeling input than B0/B1/B2/B6, so no
equal-information claim is made. B3 is `NOT_APPLICABLE` in the shared
observation table.
