# E2F Policy-Admission TOCTOU — Frozen Design Plan

Status: design and preregistration only. This file is the complete E2F
artifact for this phase. No `run.py`, `result.json`, or `RESULT.md` is
authorized yet; Architecture A and production Custody remain unchanged.

## Design verdict: INFORMATIVE

E2F is informative because the E2D/E2E artifacts establish immutable bound
authority but do not define ordinary policy freshness at admission or action.
The six fixed orderings below distinguish start snapshots, admission freshness,
action freshness, ABA generations, retry identity, and the final gateway race.
If an implementation cannot score those distinctions without hidden policy
semantics, its mechanical result must be `TCB-SEMANTICS-UNDEFINED`; the plan
must not be enlarged to manufacture a result.

## Lineage and baseline

- Repository: `Yatsuiii/custody`
- Branch base: `research/e2e-policy-misclassification`
- Frozen E2E execution commit: `4b99bfab58ae292892c32e472841aaf6952d3ce6`
- E2E preregistration commit: `baba4f8fb54a7573d7882cfeda2283e4cc50347f`
- E2E result digest: `b11eb1d44d26bc47d7ed3090fd27903c899633767b4d9e19c72ac0f8fa631470`
- Architecture source commit: `3192ec84e6bcaaa39d25d49c8a4056a4ab6e2fbf`

Baseline is a single operation admitted and authorized while one policy
snapshot remains current. The hypothesis is that a policy-version-aware
admission/action contract can make every stale ordering deterministic without
rewriting the historical envelope or silently creating a second envelope.
The sole treatment axis is event ordering; payload, identity, graph, scopes,
revisions, and all record identifiers are fixed.

## Frozen fixture and policy literals

One operation is used in every variant:

| Field | Frozen value |
|---|---|
| operation | `vendor_lookup` |
| source/tool | `vendor_lookup` |
| revision | `R1` |
| record id | `e2f-r1-root` |
| payload | `Acme settlement account: ACCT-TEST-22.` |
| scope | `export.send` |
| direct parents | none |
| transform class | root/origin admission |
| admission output | the same `output_id` in every arm |

Policy snapshots are immutable values with an exact version and monotonically
increasing generation:

| Snapshot | Role | `export.send` | Generation |
|---|---|---:|---:|
| `v1` | `ORIGIN` | `ACT` | `1` |
| `v2` | `RELAY` | `INFORM` | `2` |
| `v3` | `ORIGIN` | `ACT` | `3` |

`v3` is semantically equal to `v1` but is a distinct policy generation. The
mechanism receives the actual snapshot/version/generation and never receives a
race-case label or expected outcome.

## Candidate policy-version semantics

The alternatives are compared before implementation. “Race remaining” means
the stale state that could still reach a consequential gateway.

| Candidate | Safety property | Operational cost | Replay semantics | Auditability | Race remaining | Existing Architecture A implication |
|---|---|---|---|---|---|---|
| S1 — START-SNAPSHOT | Operation retains the start policy for admission and action | Lowest; no revalidation | Simple start-version replay | Strong historical record | Policy downgrade after start can still authorize ACT | Immutable bound fields are compatible, but action freshness is unspecified |
| S2 — ADMISSION-CURRENT | Durable admission rejects a start version that is no longer current | Medium; admission must read/compare current policy | Retry must re-read current policy | Strong; rejected attempts need a reason | A policy change after admission can still leave old action authority | Admission binding is compatible; post-admission action rule is absent |
| S3 — ACTION-CURRENT | Historical bound authority is retained, but consequential action requires the exact current policy generation | Medium; gateway performs a current-generation check | Replay preserves the envelope and re-evaluates freshness | Strong; bound and effective authority are separate | Only the final check can race; it must compare-and-decide atomically in the logical model | E2D/E2E overlays imply effective state, but ordinary policy freshness is not defined |
| S4 — GENERATION-LEASE | Admission/action requires a lease or token valid for the exact generation | Highest; lease lifecycle and expiry | Lease replay and renewal become additional state | Strong but more operational metadata | Lease expiry/renewal races remain | Not specified by existing design documents |

## Selected minimum semantics: S3 ACTION-CURRENT

S3 is the minimum defensible semantics for the research claim. S1 permits a
policy downgrade to authorize a consequential action. S2 closes admission but
does not close E2F-C or E2F-F, where an already admitted envelope reaches the
gateway after a policy change. S4 adds lease machinery not needed to test the
specific stale-admission/action boundary.

The frozen S3 contract is:

1. At operation start, capture `start_policy_version` and
   `start_policy_generation`.
2. At durable admission, persist those values, the immutable bound role/caps,
   and an authoritative `policy_version` in the AdmissionEnvelope. A stale
   attempt may be admitted as an auditable historical record, but it must be
   marked `STALE_AT_ADMISSION` and is never silently treated as current.
3. At a consequential action, compare the envelope's exact policy generation
   with the active generation. Semantic equality of caps or role is not enough.
4. A mismatch produces effective `NONE` for the consequential action and a
   deterministic deny reason such as `POLICY_GENERATION_MISMATCH`; the bound
   envelope is not rewritten.
5. The final gateway decision is one logical compare-and-decide step. If the
   generation advances before that step commits, the result is `DENY`.
6. An idempotent retry for an existing `output_id` returns the original
   envelope only when all policy-bound fields match. A different policy-bound
   value is a durable conflict, never a second logical envelope.

This is a research contract, not a claim that production Firestore, Cloud Run,
or Agent Gateway already implements it.

## Frozen event ordering variants

Each variant uses the same record, payload, policy literals, action scope, and
ground truth. Only the ordering of policy read, policy update, admission, and
action changes.

### E2F-A — no-race control

`t0 v1 active -> t1 operation reads v1 -> t2 output produced -> t3 envelope
admitted under v1 -> t4 action checked while v1/generation 1 is current`.

Expected S3 result: envelope `LIVE`, bound/effective `ACT`, action `ALLOW`,
reason `CURRENT_GENERATION_MATCH`.

### E2F-B — policy changes before admission

`t0 v1 active -> t1 operation reads v1 -> t2 admin commits v2 -> t3 output
produced -> t4 admission attempts with v1 -> t5 action requested`.

Under selected S3, admission succeeds as an auditable
`STALE_AT_ADMISSION` envelope with bound `ACT`, but the action is `DENY` with
`POLICY_GENERATION_MISMATCH`. If an implementation rejects admission instead,
it must record the exact fail-closed reason and still satisfy the no-stale-ACT
gate; the scorer does not treat rejection as an unreported exception.

### E2F-C — policy changes after admission, before action

`t0 v1 active -> t1 operation starts -> t2 envelope admitted under v1 -> t3
admin commits v2 -> t4 action requested using the old envelope`.

The old envelope's policy version and bound caps remain unchanged. Its action
is `DENY` under S3. This explicitly separates immutable history from current
effective usability; E2E's historical immutability result alone is not enough.

### E2F-D — policy flaps / ABA

`t0 v1 -> t1 operation reads v1 -> t2 v2 commits -> t3 v3 commits -> t4
admission/action occurs`.

Although v3 has the same role/cap values as v1, generation 3 is not generation
1. A v1-bound operation must not be accepted as current merely because the
policy values look equal. The action is `DENY` unless a new exact-generation
admission has occurred.

### E2F-E — duplicate/retry

The first attempt for `e2f-r1-root` reads v1. v2 commits before that admission
completes; the v1 attempt then reaches durable admission, and a retry for the
same output id arrives under v2.

The first durable envelope wins. The retry must report a policy-bound conflict
(`RETRY_POLICY_CONFLICT`) rather than create a second envelope. If the first
attempt never durably commits, the retry may create the sole v2 envelope; the
result must state which durable write won and remain idempotent on replay.

### E2F-F — concurrent action check

The gateway reads the v1-bound record while v1 is current. Before its final
authorization step, the active generation advances to v2. The final logical
compare must return `DENY`, record the generation mismatch, and never publish
an `ALLOW` based on the stale read.

No compromise-window revocation is used in E2F. This is ordinary policy
evolution, not E2E incident response.

## Runtime/scorer separation

Runtime input contains only actual policy snapshots, policy version/generation,
operation start version, admission version, immutable envelope fields, and
action requests. It must not contain keys or labels equivalent to
`race_case`, `expected_allow`, `stale_is_bad`, `scorer_verdict`, or
`expected_failed_invariant`.

Scorer-only ground truth contains the selected S3 outcome for each ordering,
the expected freshness decision, expected conflict behavior, and expected
invariant status. The future harness must assert that runtime fixture
dictionaries contain no forbidden labels, that the mechanism constructor has
no ground-truth parameter/reference, and that the scorer reads ground truth
only after every variant completes.

## Key invariants

- **F1 — IMMUTABLE HISTORY:** an admitted envelope's policy version, generation,
  role, bound caps, parents, support, payload digest, and admission time are
  never rewritten.
- **F2 — NO STALE ADMISSION AMBIGUITY:** every stale admission is either the
  explicitly marked S3 `STALE_AT_ADMISSION` record or a deterministic,
  reasoned rejection; no implicit policy choice is allowed.
- **F3 — NO ABA CONFUSION:** v1 -> v2 -> v3 remains distinguishable by exact
  version and generation even when v3 is semantically equal to v1.
- **F4 — RETRY CONSISTENCY:** one output id cannot produce contradictory
  policy-bound envelopes; same-value replay is idempotent and differing values
  are conflicts.
- **F5 — ACTION FRESHNESS:** a consequential gateway cannot return `ALLOW` for
  a stale generation; a generation advance before final authorization fails
  closed.
- **F6 — AUDITABILITY:** every allow, deny, stale admission, rejection, and
  conflict records bound policy version, current policy version, bound/current
  generation, freshness decision, and reason.

## Preregistered metrics

No weighted score is permitted. Each metric emits raw numerator, denominator,
and value, with the following fixed denominators:

1. `stale_admission_attempts`: stale admission orderings observed / 3
   (`B`, `D`, `E`).
2. `stale_admissions_accepted`: stale attempts accepted as explicitly marked
   S3 historical records / the `stale_admission_attempts` denominator.
3. `stale_act_permits`: stale-generation consequential `ALLOW` decisions / 5
   stale action opportunities (`B` through `F`, excluding only A).
4. `aba_false_accepts`: v1-bound authority accepted as current after v1-v2-v3
   flap / 1.
5. `retry_policy_conflicts`: E2F-E retries with changed policy-bound fields
   that return the required conflict / 1.
6. `duplicate_envelope_count`: contradictory envelopes for `e2f-r1-root` / 1.
7. `action_generation_mismatches`: E2F-F generation advances detected and
   denied before final authorization / 1.
8. `historical_rewrite_count`: historical envelope policy-bound fields changed
   by policy updates / all historical envelopes.
9. `audit_trace_complete`: variant decisions containing all F6 fields / 6
   primary variant decisions.
10. `deterministic_replay_match`: canonical replay artifact matches / 1.

## Mechanical verdict gates

Evaluate in this order; RESULT.md must not choose the verdict.

### DESIGN-KILL

Use only if the selected Architecture A invariants are internally
contradictory—for example, the same immutable envelope must both retain its
historical bound fields and have those fields rewritten to satisfy action
freshness, or exact-generation identity cannot distinguish v1 from semantically
equal v3. A normal stale-policy denial or conflict is not DESIGN-KILL.

### TOCTOU-ROBUST

All six orderings obey S3: stale attempts are explicitly marked or deterministically
rejected; `stale_act_permits` is `0/5`; `aba_false_accepts` is `0/1`;
`retry_policy_conflicts` is `1/1`; `duplicate_envelope_count` is `0/1`;
`action_generation_mismatches` is `1/1`; `historical_rewrite_count` is zero;
`audit_trace_complete` is `6/6`; and `deterministic_replay_match` is `1/1`.

### TOCTOU-FAIL-CONTAINED

Stale records may be admitted under S3 and remain auditable, but no stale ACT
is actionable, no ABA acceptance or contradictory retry envelope occurs, and
all unaffected fields remain intact. This gate is used when the result is
security-contained but misses a non-safety S3 observability/state-label detail
(for example, stale admission is recorded as `LIVE` rather than explicitly
`STALE_AT_ADMISSION`).

### TOCTOU-FAIL

Any stale-generation `ALLOW`, ABA false accept, contradictory duplicate
envelope, missing required retry conflict, historical rewrite, failed final
generation recheck, or incomplete audit trace is sufficient. A deterministic
replay mismatch is also a failure.

### TCB-SEMANTICS-UNDEFINED

Use only if the implementation cannot determine which of S1-S4 is being tested
from the frozen plan and Architecture A state. Preserve the result as a
semantic limitation; do not silently choose a stronger policy after execution.

## Future proof-artifact schema

If implementation is later authorized, canonical JSON must include:

- `experiment_id`, `preregistration_commit`, `e2d_commit`,
  `experiment_source_digest`, `fixture_digest`, and `ground_truth_digest`;
- selected semantics and the candidate comparison table;
- every variant's ordered event log, policy snapshots, operation start state,
  admission attempt/decision, envelope fields, action request/decision,
  current/bound versions and generations, freshness reason, retry/conflict
  state, and F6 audit trace;
- all metrics with raw counts/denominators, mechanical verdict, first failed
  invariant, leakage guard, and deterministic replay digest comparison.

The artifact must distinguish immutable `bound_caps` from current
`effective_caps`, and historical policy correction from ordinary freshness.

## Frozen limitations

- This gate isolates policy ordering; it does not test role-selection quality,
  payload semantics, signatures, compromise-window revocation, or repair.
- A deterministic SQLite/local state machine would prove only logical ordering,
  not Firestore transactions, Cloud Run process races, multi-region
  consistency, or production Agent Gateway atomicity.
- Wall-clock timestamps are not the ordering authority; the event log and
  policy generation are. Any implementation must not use incidental scheduler
  timing as ground truth.
- The strongest ambiguity is whether existing Architecture A documents intend
  historical bound authority to remain actionable after ordinary policy
  evolution. S3 is the preregistered minimum candidate, not an assertion that
  production already has that contract.
