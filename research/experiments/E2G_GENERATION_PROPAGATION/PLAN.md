# E2G — Generation Propagation

Status: frozen preregistration/design only. No implementation or production
change is authorized by this document.

## 1. Lineage and question

Experiment ID: `E2G_GENERATION_PROPAGATION`.

Parent evidence is E2F, verdict `TOCTOU-ROBUST`, executed at
`07eb279cc97816a599cd630fd2b45ba03076d3ef`, from preregistration
`5527f3190dc0b4180c1fbdd3f91d13237104e809`. Its canonical result digest is
`f5d0afba0d5ed73d60da11c64607fec92ace128c2f4e678d7633f50483531dab`.

E2F tested action-current freshness when the action cited the stale record
itself. E2G tests whether that freshness composes through a new derived
record: can a current-generation child make a required upstream grant from an
older generation actionable again? Payload, source/tool, revision, context,
output IDs, transform classes, topology, action requests, and policy values
are fixed by this plan. This is a deterministic logical model, not proof of
Firestore, Cloud Run, multi-region, or production gateway atomicity.

## 2. Candidate models and selected minimum

The following are evaluated before implementation; they are not four scored
treatments.

| Model | Safety and races | Derivation, audit, cost, disposition |
| --- | --- | --- |
| G1 child-local generation | A current child can launder a stale parent; fails after parent changes and can hide ABA. | O(1), no new field, but violates no-amplification. Naive baseline to falsify. |
| G2 effective-parent at admission | Stops inheritance from a parent already stale at admission, but a child admitted before a later parent change remains ACT unless action rechecks it. | Parent reads at admission; replayable and auditable, but fails E2G-F and later hops. |
| G3 support-root freshness at action | Every required authority grant is compared with the current generation of its own policy key. Stale support is non-actionable through every hop. | Immutable history, exact ABA handling, O(N) dependency lookup, deterministic audit/replay. Selected minimum. |
| G4 dependency generation vector | Materializes G3's dependency set and compares it at action. | Same semantics as G3 with storage/cache complexity; optimization, not required for this gate. |

Selected semantics: **G3 — SUPPORT-ROOT FRESHNESS AT ACTION**. It is the
minimum model that prevents laundering, handles policy changes after child
admission, preserves multi-parent support, and keeps policy invalidation
selective. Existing Architecture A `Support(RootRef)` plus immutable root
envelope policy metadata is enough for a logical dependency view. If an
implementation cannot resolve a retained root to its granting generation, the
mechanical result is `SEMANTICS-GAP`, not an invented value.

## 3. Policy keys and frozen literals

Canonical `PolicyKey` is
`(department, source, operation, revision, action_scope)`. Generations are
monotonic **per policy key**, not global; unrelated policy updates must not
invalidate vendor records.

Scored key `vendor_lookup/R1`:

| version | generation | role | export.send |
| --- | ---: | --- | --- |
| v1 | 1 | ORIGIN | ACT |
| v2 | 2 | RELAY | INFORM |
| v3 | 3 | ORIGIN | ACT |

v3 is semantically equal to v1 but generation-distinct. Clean key
`clean_registry/R1` remains ACT. Include unrelated `payroll_lookup/R9` g5 to
g6; it must not stale vendor or clean authority. Registered, identity/relay,
and freeform transform operation keys remain current and unchanged. Their own
operation generation is distinct from source-policy generations that grant
input authority.

Use payload `Acme settlement account: ACCT-TEST-22.` No attacker, malicious,
or semantic-quality label is runtime-visible.

Roots:

* `R_OLD`: vendor key, admitted under v1/g1, bound `export.send=ACT`.
* `R_CLEAN`: clean key, current throughout, bound `export.send=ACT`.
* `R_NEW`: a new vendor root admitted under v3/g3 for legitimate refresh.

Use deterministic record IDs and logical admission sequence numbers only.

## 4. Authority dependencies and exact rule

For each action scope, derive (without changing production schema):

```text
AuthorityDependency(
    policy_key,
    granting_generation,
    root_record_id,
    action_scope,
)
```

For a derived record M:

```text
Dependencies(M) = union(Dependencies(P1), ..., Dependencies(Pn))
                  + M's transform-operation dependency
Support(M) = union(Support(P1), ..., Support(Pn))
```

Direct parent IDs and all support roots are retained; no weak parent is
dropped. The transform dependency says whether the transform is currently
permitted. Inherited dependencies say whether the resulting authority is
fresh. FREEFORM remains capped at INFORM.

For record M and scope s, action evaluation is deterministic:

1. Read immutable bound caps, transform cap, parents, support, dependencies,
   and M's own operation-policy key/generation.
2. If M's own operation generation is not current, effective action authority
   is `NONE`.
3. For every required dependency at s, compare its immutable
   `granting_generation` to the current generation for its exact `policy_key`.
   Any mismatch makes inherited ACT authority stale and sets effective
   authority for a consequential action to `NONE`; bound history is not
   rewritten.
4. If all required dependencies are current, apply the canonical meet
   `min(bound_cap, transform_cap, effective_caps(P1), ..., effective_caps(Pn))`
   under `NONE < INFORM < ACT`. An INFORM record cannot authorize ACT.
5. Emit bound/current versions and generations, dependency freshness,
   effective cap, and reason (`STALE_AUTHORITY_DEPENDENCY` or
   `POLICY_GENERATION_MISMATCH`, otherwise the current-generation reason).

This separates immutable bound authority from currently usable authority.
Policy changes invalidate old children transitively at action time; only a new
v3 admission creates a legitimate refresh.

## 5. Frozen variants and topology

Every variant uses the same runtime-visible fixtures. Only the stated ordering
and derived admissions differ.

* **E2G-A:** create `R_OLD` at v1/g1; advance vendor to v2/g2; action root,
  expected deny (direct stale-root control).
* **E2G-B:** under g2 create `C_REG=REGISTERED(R_OLD)`; action must deny.
* **E2G-C:** under g2 create
  `R_OLD -> C_REG -> C_AGENT (IDENTITY/RELAY) -> C_GRANDCHILD (REGISTERED)`;
  action both cross-agent/depth-three descendants; stale dependency survives.
* **E2G-D:** under g2 create `C_MIX=REGISTERED(R_OLD,R_CLEAN)`; preserve both
  parents/support roots; clean parent cannot wash stale parent.
* **E2G-E:** under g2 create `C_FREE=FREEFORM(R_OLD)`; preserve stale
  support, cap INFORM, and deny export.send.
* **E2G-F:** while v1/g1 is current create `C_BEFORE=REGISTERED(R_OLD)`;
  advance to v2/g2; action must now deny without envelope rewrite.
* **E2G-G:** advance to v3/g3 (semantic values equal v1); a descendant still
  depending on vendor g1 must deny (no semantic ABA shortcut).
* **E2G-H:** under v3/g3 create `R_NEW`, then `C_NEW=REGISTERED(R_NEW)`;
  legitimate current authority may allow ACT.
* Unrelated control: advance only payroll g5 to g6; current vendor/clean
  authority remains usable.

The stale-derived ACT-action denominator is exactly six:
`C_REG`, `C_AGENT`, `C_GRANDCHILD`, `C_MIX`, `C_BEFORE`, and the ABA
descendant. `C_FREE`, `R_OLD`, and `C_NEW` are separate controls.

## 6. Runtime/scorer separation

Future execution must use separate immutable `RuntimeFixture` and
`ScorerGroundTruth` structures. Runtime may contain records, parent IDs,
actual policy snapshots/generations, transform classes, current policy state,
and action requests. It must not contain `stale_root`, `expected_deny`,
`laundering_case`, expected support/affected records, or a scorer verdict.
The scorer is not read until all variants finish. Recursive forbidden-key and
object-reference checks are mandatory; leakage invalidates the run.

## 7. Preregistered metrics

Emit numerator/denominator/value for every metric; no weighted aggregate:

| metric | exact denominator / target |
| --- | --- |
| `direct_stale_root_denied` | 1 (`R_OLD` denied after g2) / target 1 |
| `fresh_child_stale_parent_false_act_permits` | 6 stale-derived actions / target 0 |
| `cross_agent_stale_dependency_preserved` | 2 (`C_AGENT`,`C_GRANDCHILD`) / target 2 |
| `mixed_parent_stale_dependency_preserved` | 1 (`C_MIX`) / target 1 |
| `freeform_support_preserved` | 1 (`C_FREE`) / target 1 |
| `preexisting_child_invalidated_after_parent_policy_change` | 1 (`C_BEFORE`) / target 1 |
| `aba_dependency_false_accepts` | 1 / target 0 |
| `legitimate_refresh_allows` | 1 (`C_NEW`) / target 1 |
| `unrelated_policy_update_preserved` | 1 / target 1 |
| `direct_parent_recall` | 8 derived records (`C_REG`,`C_AGENT`,`C_GRANDCHILD`,`C_MIX`,`C_FREE`,`C_BEFORE`, ABA descendant, `C_NEW`), exact tuples / target 8 |
| `authority_dependency_recall` | same 8 records, exact dependency sets / target 8 |
| `historical_rewrite_count` | 11 envelopes (`R_OLD`,`R_CLEAN`, eight derived records, `R_NEW`) / target 0 |
| `audit_trace_complete` | 9 primary actions A, B, C_AGENT, C_GRANDCHILD, D, E, F, G, H / target 9 |
| `deterministic_replay_match` | 1 independent clean replay / target 1 |

## 8. Invariants and mechanical verdict gates

Required invariants are: immutable bound policy/caps/role/payload/parents/
support/admission metadata; no stale-derived ACT permit; transitive
invalidation of `C_BEFORE`; exact-generation ABA rejection; unrelated-key
selectivity; legitimate v3 refresh; complete parent/dependency/audit closure;
and deterministic replay.

Verdict precedence is fixed:

1. `DESIGN-KILL` only for an internal contradiction in the frozen
   requirements.
2. `GENERATION-COMPOSITION-ROBUST` iff all six stale-derived actions deny,
   `R_OLD` and `C_BEFORE` deny after g2, all support/dependency recalls are
   complete, ABA false accepts are 0/1, unrelated policy is preserved,
   legitimate refresh is 1/1, rewrites are 0, audit is 9/9, and replay is
   1/1.
3. `GENERATION-COMPOSITION-FAIL-CONTAINED` iff stale-derived ACT permits are
   zero but selectivity or utility fails (for example unrelated invalidation
   or blocked legitimate refresh), without contradiction.
4. `GENERATION-LAUNDERING-FAIL` iff any fresh descendant authorizes ACT from
   a required stale dependency, or dependency/ABA handling permits laundering.
5. `SEMANTICS-GAP` iff exact immutable granting generations cannot be resolved
   from retained support without an unpreregistered primitive.

The first failed invariant and verdict are computed mechanically; RESULT.md
may not choose them.

## 9. Future artifact schema and boundary

If execution is later authorized, create only `run.py`, `result.json`, and
`RESULT.md`. Canonical `result.json` must include:

```text
experiment_id, e2f_commit, e2f_result_digest,
experiment_source_digest, fixture_digest, ground_truth_digest,
selected_semantics=G3_SUPPORT_ROOT_FRESHNESS_AT_ACTION,
candidate_semantics_summary, policy_keys_and_snapshots,
records (parents, support, dependencies, bound/effective caps, transforms,
         operation generations, state), variants E2G_A..E2G_H,
actions and authority traces, metrics, historical_immutability,
leakage_guard, verdict, first_failed_invariant, canonical_result_digest
```

Use canonical JSON and logical sequence numbers only; no wall-clock metadata.

Strongest unresolved assumption: policy generations are durably authoritative
and every retained support root can be resolved to its exact policy key and
granting generation. This plan does not establish how a production catalog,
cache, or distributed gateway makes that lookup atomic. E2G execution is
worth authorizing only after this PLAN is committed and pushed unchanged.
