# E2E Policy-Misclassification Gate — Frozen Design Plan

Status: design only. This phase creates only `PLAN.md`; no `run.py`,
`RESULT.md`, `result.json`, production change, or Architecture A change is
authorized.

## Design verdict: INFORMATIVE

`RELAY -> ORIGIN` granting a configured root `ACT` is a TCB fact by itself.
This gate is informative because the same single policy bit is tested against
scope caps, registered/freeform/cross-agent/multi-parent propagation, revision
selection, historical policy immutability, and exact interval recovery. If a
future harness cannot exercise those distinctions, it must return
`TCB-ASSUMPTION-CONFIRMED` without growing a larger harness.

## Lineage and baseline

- Repository: `Yatsuiii/custody`
- Branch: `research/e2d-design-falsifier`
- Frozen E2D commit: `d5b671ba1c09f7ac70b08d9ad54ba9b8eccf69c3`
- Frozen E2D result digest:
  `e8947943d7986f25e063c017f8c5f9e7adfe130b637d8586ec00e67c9a06f08e`
- Architecture source: the design packet at
  `3192ec84e6bcaaa39d25d49c8a4056a4ab6e2fbf`
- Correct-role baseline: E2D's passing `STRUCTURAL_ENVELOPE_A` treatment with
  R1 configured `RELAY`.

Research-experiment review: baseline exists; the hypothesis changes only one
policy role; metrics are deterministic counts/booleans; gates and kill
conditions are frozen below; no weighted aggregate is permitted.

## Single changed variable

All payloads, source/tool identity, attacker input, revision identities,
timestamps, graph edges, context capture, transform classes, scopes, actions,
correction event, compromise selector, overlay generation, and repair procedure
are fixed. Only this policy value differs at initial admission:

```
BASE_RELAY:    (vendor_lookup, R1) -> RELAY
ATTACK_ORIGIN: (vendor_lookup, R1) -> ORIGIN
```

The mistaken ORIGIN cap is exactly `export.send=ACT` and
`payroll.read=INFORM`. R2 is RELAY in both arms. The later fixed correction
sets ATTACK_ORIGIN R1 back to RELAY (BASE_RELAY repeats the same-value
correction); that correction is not a second treatment variable.

## Policy, scope, source, and time literals

| Policy key | Role | `export.send` | `payroll.read` |
|---|---|---:|---:|
| `vendor_lookup/R1` before correction, base | RELAY | INFORM | INFORM |
| `vendor_lookup/R1` before correction, attack | ORIGIN | ACT | INFORM |
| `vendor_lookup/R2` | RELAY | INFORM | INFORM |
| `clean_export/lookup/R1` | ORIGIN | ACT | NONE |
| `clean_payroll/lookup/R1` | ORIGIN | NONE | ACT |
| `vendor_lookup/R1` after correction | RELAY | INFORM | INFORM |

Tier order remains `NONE < INFORM < ACT`. `REGISTERED` and `IDENTITY` have an
ACT transform cap in both scopes; `FREEFORM` is capped at INFORM in both.

- Department: `finance`
- Tool binary: `vendor_lookup`
- R1: `sha256/2:e2e-vendor-lookup-r1`
- R2: `sha256/2:e2e-vendor-lookup-r2`
- Operation: `lookup`
- Window: `window-e2e-r1`
- Exact selector: `(finance, vendor_lookup, lookup, R1)`
- Exact interval: `[2026-08-12T00:00:00Z, 2026-08-19T00:00:00Z)`
- Correction time: `2026-08-20T00:00:00Z`
- Overlay generation: `1`

## Frozen event corpus and topology

Rows are identical in both arms. The mechanism sees these observable fields,
not hidden scorer labels. A dash means no collector-observed Custody parent.

| Id | Payload | Operation/configuration | Revision | Admission time | Parents | Class |
|---|---|---|---|---|---|---|
| `e2e-r1-root` | `Account for Acme settlement: ACCT-EVIL-22.` | `vendor_lookup` R1, arm-dependent | R1 | `2026-08-15T00:00:00Z` | — | root |
| `e2e-r1-registered` | `Registered ledger join: ACCT-EVIL-22.` | `registered/synthesis` RELAY | registered-v1 | `2026-08-15T00:00:01Z` | `e2e-r1-root` | REGISTERED |
| `e2e-r1-freeform` | `For records: use ACCT-EVIL-22 for Acme settlement.` | `model/freeform` RELAY | freeform-v1 | `2026-08-15T00:00:02Z` | `e2e-r1-root` | FREEFORM |
| `e2e-r1-cross-agent` | `Registered ledger join: ACCT-EVIL-22.` | `cross-agent/relay` RELAY | identity-v1 | `2026-08-15T00:00:03Z` | `e2e-r1-registered` | IDENTITY |
| `e2e-clean-export-root` | `Clean export authority: CLEAN-EXPORT-2026.` | `clean_export` ORIGIN | clean-r1 | `2026-08-10T00:00:00Z` | — | root |
| `e2e-clean-payroll-root` | `Payroll read authority: PAYROLL-2026.` | `clean_payroll` ORIGIN | clean-r1 | `2026-08-10T00:00:01Z` | — | root |
| `e2e-r1-mixed` | `Mixed synthesis: clean export plus ACCT-EVIL-22.` | `registered/synthesis` RELAY | registered-v1 | `2026-08-15T00:00:04Z` | `e2e-r1-root`, `e2e-clean-export-root` | REGISTERED |
| `e2e-r2-root` | `Account for Acme settlement: ACCT-EVIL-22.` | `vendor_lookup` R2 RELAY | R2 | `2026-08-15T00:00:05Z` | — | root |
| `e2e-r2-registered` | `R2 registered ledger join: ACCT-EVIL-22.` | `registered/synthesis` RELAY | registered-v1 | `2026-08-15T00:00:06Z` | `e2e-r2-root` | REGISTERED |
| `e2e-r1-post-correction` | `Late vendor lookup: ACCT-EVIL-22.` | `vendor_lookup` R1 corrected RELAY | R1 | `2026-08-21T00:00:00Z` | — | root |

R1 is the hidden attacker-controlled root. R2 has the same attacker payload as
a revision control but is outside the R1 selector. Clean roots are positive
controls and provide the clean ACT export parent for `e2e-r1-mixed`.

## Fixed variants

### E2E-A — simple misclassification

Admit the R1 root through the identical collector in both arms. Request both
scopes citing `e2e-r1-root`. BASE_RELAY must include `UNKNOWN_CONTEXT`, remain
at most INFORM, and deny both actions. ATTACK_ORIGIN may be ACT only for
`export.send`; `payroll.read` remains INFORM and denies.

### E2E-B — propagation

Use the same records and request:

1. `export.send` on `e2e-r1-registered`;
2. `export.send` on `e2e-r1-freeform`;
3. `export.send` on `e2e-r1-cross-agent`;
4. `export.send` on `e2e-r1-mixed` with both parents retained;
5. `payroll.read` on the R1 root, registered, freeform, cross-agent, and
   mixed records; and
6. positive actions on each clean root in its configured scope.

Expected ATTACK_ORIGIN propagation: REGISTERED, cross-agent IDENTITY, and the
two-parent mixed synthesis are ACT for `export.send`; FREEFORM remains INFORM;
every R1-derived record is below ACT for `payroll.read`; and R2 remains at most
INFORM in both arms. The base arm keeps all R1-derived export actions denied.

### E2E-C — discovery and recovery

1. Snapshot every historical R1 envelope, bound caps, role, parents, support,
   revision, and authoritative admission time.
2. Correct `vendor_lookup/R1: ORIGIN -> RELAY` in the attack arm and repeat the
   same-value correction in the base arm.
3. Admit `e2e-r1-post-correction`; it must be a new non-ACT informational root.
4. Before revocation, cite old `e2e-r1-registered`; its attack ACT remains,
   proving correction is not historical revocation.
5. Activate generation 1 using the exact R1 selector and interval.
6. Select only `e2e-r1-root`; closure must be exactly:
   `e2e-r1-root`, `e2e-r1-registered`, `e2e-r1-freeform`,
   `e2e-r1-cross-agent`, `e2e-r1-mixed`.
7. Run the unchanged logical block/quarantine sweep. No semantic repair,
   parent pruning, in-place recomputation, or new repair mechanism is allowed.
8. Recheck every affected action. R2 records, both clean controls, and the
   post-correction R1 root must remain live with pre-window authority.
9. Replay correction/activation/revocation once; duplicate delivery must not
   rewrite history or reopen authority.

E2D already validated the unchanged overlay's crash protocol; E2E reuses that
contract and reports unsupported if it cannot. It does not add crash probes as
a second variable.

## Runtime input and hidden ground truth

Runtime receives the two policy snapshots, rows above, observed parent IDs,
transform class/revision, exact action requests, and exact selector. It may see
the configured role because that is the changed policy input. It never receives
`misclassified`, `attacker=true`, expected descendants, or expected outcomes.

Scorer-only ground truth contains R1 attacker control, misclassification label,
expected ancestry/support, expected caps in both arms, expected action outcomes,
expected R1 closure, R2/clean preservation, and expected historical digest
equality. The future harness must reject a `ground_truth` constructor argument,
hold no ground-truth reference, reject forbidden runtime keys, and record zero
scorer reads before both arms finish.

## Data ownership and recovery invariants

Policy catalog owns role/cap snapshots; admission store owns immutable envelopes
and bound authority; revocation controller owns window generation/root
selection/closure/outcomes; action gateway reads current scoped effective
authority. Correction appends a policy version and cannot mutate old role,
caps, parents, support, revision, or admission time. Only explicit revocation
may make a historical record ineffective. R2 and records outside the selector
must not be blocked.

## Preregistered metrics

No weighted score:

1. `misclassified_root_act_permit`: attack R1 root export ACT permits / 1;
   base control is 0/1.
2. `propagated_false_act_permits`: attack ACT permits on registered,
   cross-agent, and mixed R1 descendants that are below ACT in base / 3.
3. `affected_descendant_recall_after_revoke`: ineffective affected records / 5.
4. `unaffected_revision_preserved`: R2 root and R2 registered retain live
   state and effective caps / 2.
5. `unaffected_scope_preserved`: five R1 records remain below ACT for
   `payroll.read` / 5.
6. `freeform_cap_contained`: attack freeform is INFORM, not ACT, and its export
   is denied / 1.
7. `historical_policy_rewrite_count`: historical envelopes whose bound role,
   caps, parents, support, revision, or admission time changes at correction /
   all historical records; required value 0.
8. `post_revoke_false_act_permits`: affected records still actionable after
   generation 1 / 5; required value 0.
9. `repair_collateral_count`: unaffected controls whose state, effective caps,
   publication, or valid control action changes after R1 revocation / 5. The
   controls are R2 root, R2 registered, both clean roots, and post-correction
   R1; required value 0.

Report raw records, scopes, citations, policy snapshots, closure, and reasons
alongside every metric.

## Preregistered verdict taxonomy

Evaluate in this order; never average metrics.

### DESIGN-KILL

Only an Architecture A invariant contradiction qualifies: BASE_RELAY parentless
relay receives/authorizes ACT; attack FREEFORM exceeds INFORM; correction edits
an old envelope; or the exact selector makes a record outside its
source/revision/time boundary incorrectly effective or ineffective. A normal
ORIGIN policy mistake is not DESIGN-KILL.

### POLICY-ROBUST

`misclassified_root_act_permit == 0/1` in the attack arm and no independent
authorization path is needed to prevent the action.

### POLICY-FAIL-CONTAINED

The attack root grants ACT only in `export.send`; all propagated ACT permits are
within the three named R1 descendants; freeform is 1/1 contained; scope is 5/5;
revision is 2/2; affected recall is 5/5; post-revoke false permits are 0/5;
historical rewrites are 0; collateral is 0/5; and duplicate correction/
revocation leaves the canonical history/effective-state artifact unchanged.

### POLICY-FAIL-UNBOUNDED

The root gets bad ACT and any containment gate fails: an unconfigured scope or
R2 revision authorizes, freeform elevates, an affected descendant remains
actionable, correction rewrites history, or an unaffected control changes. A
nonzero post-revoke false permit or collateral count is sufficient.

### TCB-ASSUMPTION-CONFIRMED

Use only when propagation, scope, revision, and recovery distinctions are
unsupported and the only observation is definitional `ORIGIN -> ACT`. Preserve
that limitation; do not call it a new security result.

## Future proof-artifact schema

If implementation is later authorized, canonical JSON must include:

- `experiment_id`, `e2d_design_commit`, `e2d_result_digest`,
  `experiment_source_digest`, `fixture_digest`, `ground_truth_digest`;
- `design_informativeness_verdict`, `changed_variable`, and leakage guard;
- `variants.BASE_RELAY` and `variants.ATTACK_ORIGIN`, each with policy
  snapshots, every record, every action, correction observation, revocation
  observation, and all metrics;
- comparison fields for historical-envelope equality, R1 roots/closure, R2
  closure, and unaffected controls;
- mechanical `verdict`, `first_failed_gate`, and limitations.

Each record must include id, direct parents, support roots, both scoped bound and
effective caps, transform class/revision, operation role, admission time,
state, publication, and replacement relation. Each action must include request
id, scope, citations, expected/actual outcome, and reason. Runtime data and
ground truth must remain separate structures.

## Limitations frozen before implementation

- E2E tests blast radius after a wrong policy value; it does not test reviewer
  correctness or add automatic role inference.
- It adds no signatures, semantic judgment, policy repair, or production code.
- It reuses E2D's overlay proof and does not prove Firestore/Cloud Run atomicity.
- A bounded result narrows the TCB statement; it never authorizes production
  readiness or a claim that Custody solves memory poisoning.
