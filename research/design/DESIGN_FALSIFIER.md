# Design Falsifier — Preregistered Before Implementation

No implementation or result exists in this phase. This document freezes the
next experiment's variable, fixtures, metrics, and stop conditions before any
experimental mechanism code is authorized.

## Baseline

Current Custody at commit `040c28c36d10a6c89144a19e01b0eae77a88ec64`
(`research/design-mechanism-v0` parent), including the E1 multi-parent fix and
the measured E2A/E2B/E2C behavior. The full no-drift baseline is 381 passing
unit tests.

## Hypothesis

With the event corpus, graph topology, source policies, action requests, and
timestamps fixed, replacing only the current attribution/authority mechanism
with Architecture A's structural admission envelope will:

1. preserve complete ancestry across byte-changing transformations;
2. produce zero action-authority amplification;
3. block the exact closure of a later bounded compromise window; and
4. preserve an outside-window sibling.

Free-form paraphrases are expected to retain support and informational utility,
not `ACT`.

## Single changed variable

```
mechanism = CURRENT_CUSTODY | STRUCTURAL_ENVELOPE_A
```

The treatment is one architecture switch behind the same experimental port.
All fixtures, record ids, operation roles, policy caps, transform classes,
admission times, compromise window, requested action scope, and fault-injection
points are identical. No LLM, network service, embedding, fuzzy match, or
content classifier participates.

Changing a fixture to make the treatment pass creates a new experiment number;
it does not amend this preregistration.

## Frozen scenario

Use deterministic UTC admission times and these six required elements in one
shared graph:

1. **Trusted-tool echo:** a configured `RELAY` operation returns attacker data
   with no observable upstream record. The runtime name is vouched.
2. **Benign paraphrase:** an `ACT` origin root is exposed to a `FREEFORM`
   transform that emits changed wording.
3. **Malicious paraphrase:** a `NONE` root is exposed to the same `FREEFORM`
   transform shape and emits changed wording.
4. **Multi-parent synthesis:** a `REGISTERED` transform consumes two `ACT`
   roots; a second variant consumes one `ACT` and one `NONE` root.
5. **Later compromise:** after all outputs exist, declare a compromise window
   containing one formerly `ACT` origin root and activate repair.
6. **Unaffected sibling:** the same source has a root outside the window, with
   an identity descendant that does not share affected support.

The interval is `[2026-08-12T00:00:00Z, 2026-08-19T00:00:00Z)`. The affected
root is admitted on August 15; the sibling is admitted on August 5. Record ids
and input manifests are fixed literals in the future `PLAN.md`.

## Expected treatment outcomes

| Element | Required Architecture A outcome |
|---|---|
| Tool echo | includes `UNKNOWN_CONTEXT`; effective tier is at most `INFORM`; `export.send` denied |
| Benign paraphrase | direct parent/support retained; tier `INFORM`; informational retrieval succeeds; action denied |
| Malicious paraphrase | hostile root remains in support; tier `NONE`; action denied |
| Two-`ACT` registered synthesis | both direct parents present; `ACT` only in scopes permitted by both parents and transform |
| `ACT`+`NONE` synthesis | both parents present; tier `NONE`; no amplification |
| Later compromise | in-window root and every descendant become `BLOCKED`; effective tier `NONE` |
| Unaffected sibling | remains `LIVE`; outside-window identity descendant remains action-eligible |
| Repair attempt | no unchanged record gains authority; any restored output has a new id and envelope |

## Metrics

- `direct_parent_recall`: declared ground-truth parent edges found / expected
  parent edges, over all transformed records.
- `affected_recall`: ground-truth affected records blocked / all ground-truth
  affected records after window activation.
- `false_act_permits`: action requests allowed when the expected tier is below
  `ACT`.
- `same_record_authority_increases`: records whose effective tier rises without
  a new record id.
- `benign_inform_retained`: whether the benign paraphrase remains available on
  the informational path with its support.
- `outside_sibling_preserved`: whether both outside-window sibling records stay
  live and their valid scoped action is allowed.
- `replay_digest_stable`: equality of sorted envelopes, window, repair plan,
  outcomes, and action decisions after duplicate execution.
- `unsafe_fault_windows`: fault-injection points at which an affected citation
  can authorize an action.

Every metric is an exact count/boolean on deterministic fixtures. No statistical
test is appropriate for this falsifier.

## Crash and replay probes

Run the treatment with a forced process stop at each boundary:

1. after window intent, before plan;
2. after plan, before the first downstream block/delete;
3. midway through per-record repair; and
4. after replacement admission, before publication.

Restart from durable state and replay the same request. At every point the
action gateway must fail closed against the active generation, and the final
artifact must equal the no-fault run except for retry counters.

## Fixed verdict gates

### PASS

All of the following are required:

- `direct_parent_recall == 1.0`;
- `affected_recall == 1.0`;
- `false_act_permits == 0`;
- `same_record_authority_increases == 0`;
- `benign_inform_retained == true`;
- `outside_sibling_preserved == true`;
- `replay_digest_stable == true`;
- `unsafe_fault_windows == 0`; and
- the existing full suite remains 381/381 with no production-file diff.

### CAUTION

Security remains fail-closed—`affected_recall == 1.0`, zero false `ACT`
permits, zero same-record increases, and zero unsafe fault windows—but at least
one utility/selectivity property fails: the benign informational paraphrase is
lost, the outside-window sibling is conservatively blocked, or replay reaches a
safe but non-terminal repair state. Report the exact failed property; do not
average it into a score.

### KILL

Any one of the following stops the mechanism branch:

- an `INFORM`, `NONE`, incomplete, or affected record authorizes an action;
- any ground-truth affected descendant is missed;
- any declared parent is silently absent;
- unchanged content gains authority after parent pruning or window repair;
- a crash/retry opens an action-authority window; or
- the treatment requires semantic inference or tool-self-reported provenance
  to pass.

## Planned proof artifact

If a later session authorizes implementation, it must create only experimental
artifacts under:

```
research/experiments/E2D_DESIGN_FALSIFIER/
    PLAN.md
    run.py
    RESULT.md
    result.json
```

`result.json` must contain the baseline commit, experiment-source digest,
fixture digest, mechanism mode, every metric numerator/denominator, per-record
parents/caps/support/state, action decisions, fault-probe outcomes, and final
verdict. `RESULT.md` summarizes that generated artifact and links each claim to
its JSON field. No production implementation is authorized by this design.

## Result table

| Mechanism | Parent recall | Affected recall | False ACT permits | Benign info retained | Sibling preserved | Replay/fault safe | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Current Custody | Existing evidence: E1 multi-parent PASS; E2A echo FAIL; E2B/E2C transformed ancestry lost; no interval mechanism | not runnable | E2A: 1 measured | E2B: false | not runnable | not runnable | baseline characterized |
| Architecture A | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

## Artifact lineage

- E0/E1 graph evidence: `research/experiments/E0_CURRENT_LINEAGE_REPRO/`
  and `research/experiments/E1_MULTIPARENT_LINEAGE/`.
- E2A relay failure: `research/experiments/E2A_TMANM_TOOL_ECHO/`.
- E2B benign-collateral control: `research/experiments/E2B_TMANM_SUMMARIZE/`.
- E2C exact-match cliff: `research/experiments/E2C_EXACT_VS_TRANSFORMED/`.
- Design source: this packet on parent commit `040c28c`.

## Experiment Review

Verdict: valid (preregistered; execution not authorized)

Baseline: current Custody at `040c28c`, with measured E1/E2A/E2B/E2C behavior.

Hypothesis: the structural-envelope treatment satisfies the exact safety and
selectivity outcomes above.

Changed variable: `mechanism` only.

Metric: deterministic counts and booleans listed above.

Result: not run.

Kill/continue decision: continue only to this isolated experiment after
explicit authorization; any KILL condition ends the mechanism branch.

Missing evidence: complete context-id capture, authoritative timestamps outside
Firestore, crash-safe overlay implementation, and all treatment results.
