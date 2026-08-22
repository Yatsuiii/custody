# Gate 1B to Gate 1B-R1 Equivalence Audit

Status: preregistration audit; no R1 execution performed.

## Normalization permitted

The comparison normalizes only:

1. experiment ID (`EXT_GATE1B_MISSING_PROVENANCE_PRIMITIVE` to
   `EXT_GATE1B_R1_AUTHORITY_RECEIPT`);
2. R1 branch and invalid-attempt lineage;
3. fixture-construction ownership, one-insertion enforcement, and dry-run
   manifest checks.

No treatment result was observed in the invalid attempt, so no efficacy-driven
change is present or permitted.

## Security-equivalence matrix

| Security-relevant surface | Original Gate 1B | R1 | Result |
|---|---|---|---|
| External repository/commit | `yedidel/mem-inv-bench@63f1359d677efbe1a65b982b2a54cabfec97f1e1` | identical | EQUIVALENT |
| Attack | `code/laundering.py::tool_echo` | identical | EQUIVALENT |
| Benign control | trusted source value through `vendor_lookup` | identical | EQUIVALENT |
| Relay | `vendor_lookup` | identical | EQUIVALENT |
| Source issuer | policy-authorized upstream source | identical | EQUIVALENT |
| Receipt fields/binding | issuer, key, object/claim commitment, PolicyKey, generation, scope, cap, revision, identity/version, authentication | identical | EQUIVALENT |
| Authentication | real issuer authentication; relay cannot mint | identical | EQUIVALENT |
| B1/B6/B6P2/B3 baselines | frozen definitions and native boundaries | identical | EQUIVALENT |
| IDENTITY | preserve receipt/dependency | identical | EQUIVALENT |
| REGISTERED | retain all parents/support; no exact-byte requirement | identical | EQUIVALENT |
| FREEFORM | support auditable, no consequential ACT | identical | EQUIVALENT |
| Cross-agent | forwarding cannot mint/amplify root authority | identical | EQUIVALENT |
| Generation | exact PolicyKey/granting generation freshness; ABA denied | identical | EQUIVALENT |
| Multi-parent | union all parents/dependencies; no washing | identical | EQUIVALENT |
| Revocation selector/topology | same source closure and unrelated control | identical | EQUIVALENT |
| Scorer/runtime boundary | scorer hidden; no `true_origin`/labels in B6/B6P2 | identical | EQUIVALENT |
| Metrics/denominators | original Gate 1B fixed metrics | identical | EQUIVALENT |
| Verdict/KILL precedence | original KILL/CAUTION/GATE-CLEAR/INVALID rules | identical | EQUIVALENT |
| Model/API cost | 0 / $0 | identical | EQUIVALENT |

## Normalized difference result

The only differences are identity/lineage and the pre-treatment fixture
ownership rule that prevents a record from being registered twice. The
revocation graph remains:

```text
ROOT-REVOKED -> MEM-REVOKED-DESC
ROOT-UNRELATED -> MEM-UNRELATED-DESC
```

No record is renamed, removed, duplicated intentionally, or reparented to
change a security outcome. `MEM-REVOKED-DESC` expected insertion count is one
in both the intended original topology and R1; the original attempt failed
because the runner violated that intended invariant.

## Pre-treatment validity checks

R1 must stop before treatment unless all of these pass:

1. parent design SHA is verified;
2. invalid-attempt preservation commit is verified;
3. external source/attack commit and path are pinned;
4. fixture manifest IDs are unique;
5. `MEM-REVOKED-DESC` appears exactly once;
6. issuer key is distinct and inaccessible to the relay;
7. scorer is unreachable from mechanism inputs;
8. B6/B6P2 contain no `true_origin` or equivalent scorer field;
9. no payload-semantic or case-label branch exists in security code;
10. production diff is empty and model calls remain zero.

These checks add no authority and run before any treatment action. A failed
check is `INVALID`, not a security result and not permission to change the
fixture.

## Audit conclusion

`PREREGISTRATION-VALID`: R1 is a single-variable runner-executability
correction. All A–O security cases, attack/control semantics, receipt and
issuer rules, baselines, transformations, generation/revocation/multi-parent
semantics, metrics, denominators, and verdict/KILL gates remain frozen.

No treatment or scorer result has previously been observed, and R1 must not be
executed in this session.
