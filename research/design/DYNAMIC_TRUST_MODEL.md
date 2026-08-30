# Dynamic Trust and Interval Revocation Model

The minimum interval mechanism does not rewrite historical trust. It appends a
compromise window, selects direct source roots admitted in that window, and
makes their descendant closure ineffective through a durable overlay.

## Time semantics

The canonical interval is half-open:

```
[start, end) where start < end
```

Both boundaries are UTC RFC 3339 instants. A security report stated with
inclusive or coarse dates is widened conservatively before storage—for example,
"days 12-18 inclusive" becomes the start of day 12 through the start of day
19. Overlapping windows are evaluated as their union.

The coordinate is **authoritative admission time**, not a claim about when an
upstream compromise physically began. This is the time at which a source output
entered Custody's durable boundary. An external source-time estimate must be
widened by known clock and ingestion-delay uncertainty before it becomes an
admission-time window. The first falsifier uses a deterministic admission
clock; production cannot assume zero delay.

## Persisted records

```
RevocationWindow(
    id,
    department,
    source_id,
    operation_id | *,
    revision_id | *,
    start,
    end,
    reported_at,
    evidence,
    supersedes | None,
    generation,
    state,
)
```

`state` is `ACTIVE` or `SUPERSEDED`; superseding never erases the old record.
A wider correction creates a new generation. A narrower correction does not
automatically re-enable old content; restoration follows the replacement rules
in `REPAIR_SEMANTICS.md`.

Each window also has an idempotent repair plan keyed by its generation:

```
RepairPlan(window_id, generation, graph_high_watermark,
           root_ids, affected_ids, per_record_outcome, phase)
```

The plan is evidence and recovery state, not a caller-maintained cache.

## Authoritative timestamp requirement

Current Firestore records obtain `admitted_at` from document `create_time` and
therefore meet the basic clock requirement. Current in-memory records have
`None`, and the SQLite JSON path does not assign an independent server time.
Legacy/missing/caller-supplied timestamps are **unclassifiable**.

An unclassifiable record for the targeted source is never interpreted as
outside the window. The safe fallback is configurable only between:

1. whole-source quarantine/revocation; or
2. `LEGACY_UNKNOWN` quarantine pending review.

Neither fallback may report interval precision. A production rollout therefore
requires a timestamp migration gate; the design does not fabricate historical
times during backfill.

## Root selection

For window `W`, direct affected roots are:

```
Roots(W) = {
    r |
      r is an ORIGIN root record
      and r.department == W.department
      and r.source_id == W.source_id
      and operation/revision filters match
      and W.start <= r.admitted_at < W.end
}
```

Only direct source roots qualify. A derived record that happens to retain a
convenience `source_tool` field is not selected by its own admission time; it is
reached through its direct-parent edges. This avoids confusing "when a summary
was stored" with "when the compromised source contribution entered."

The affected set is the graph's descendant closure from `Roots(W)`. E1 already
demonstrates that the existing breadth-first walk handles multiple parents once
they are present. Architecture A changes root selection and operational state,
not the graph-theoretic closure.

## Write and revocation ordering

The safety boundary is an active overlay consulted by admissions and action
decisions. Physical deletion is asynchronous cleanup.

1. **Activate intent.** Atomically create/reuse the `RevocationWindow`, advance
   the revocation generation, and mark it `ACTIVE` before starting a sweep.
2. **Close the action race.** Gateways read the current generation and compute
   effective authority against active windows. A stale or unavailable
   generation fails closed for consequential actions.
3. **Take a high-watermark.** Record the immutable graph position used to build
   the first plan. Select roots and compute their closure.
4. **Persist the plan.** Store roots and affected ids before applying downstream
   mutations. Recomputing the same generation must produce the same set for the
   same high-watermark.
5. **Apply idempotently.** Mark records blocked, remove them from active indexes
   and downstream memory, and record one outcome per id.
6. **Catch concurrent writes.** Every admission after activation checks both
   its own root admission time and its parent support against active windows.
   A matching write is born blocked. The worker advances the high-watermark
   until no unprocessed matching records remain.
7. **Complete cleanup.** `phase=COMPLETE` means every planned target has a
   terminal outcome and the high-watermark is caught up. The window remains an
   active policy fact; completion never makes its roots effective again.

This ordering permits a crash to delay deletion but not to reopen action
authority.

## Read path and freshness

- Consequential action checks require the latest revocation generation. A cache
  entry is keyed by `(record_id, generation)` and cannot be reused after the
  generation advances.
- Informational reads may lag physical deletion, but returned records carry
  their blocked status and cannot serve as action citations.
- An explanation query returns the bound caps, direct parents, root support,
  matching window/generation, and repair outcome. "Why is this blocked?" must
  be answerable without reconstructing old policy from current state.

## Window updates and conflicts

- Duplicate requests with the same id and payload are no-ops.
- The same id with different payload is a conflict, never an overwrite.
- Widening produces a new generation whose affected set is a superset.
- Overlapping windows from different incident reports union at evaluation.
- Narrowing or retracting a report requires explicit adjudication and new
  replacement records; old blocked content is not silently resurrected.
- A whole-source revocation is represented as the same selector with unbounded
  time, preserving one mechanism rather than a special second path.

## Failure modes and required behavior

| Failure | Required behavior |
|---|---|
| Crash after intent, before plan | Active generation blocks actions; replay builds the plan |
| Crash during downstream deletion | Per-record outcomes resume idempotently; overlay remains effective |
| Duplicate repair delivery | Same window/generation and record outcome return unchanged |
| Missing parent during closure | Mark graph inconsistent, include the dependent record conservatively, and do not complete the plan |
| Record with missing authoritative time | Whole-source or `LEGACY_UNKNOWN` quarantine; never count as outside-window |
| Stale gateway/cache | Deny consequential action until current generation is observed |
| New write derived from affected parent | Admission envelope is stored blocked and added to the plan |
| Window later widens | New generation processes only the newly added closure plus any previously incomplete work |
| Downstream deletion unavailable | Record remains logically blocked; plan stays incomplete and retries |

## Schema evolution

Envelope and window records carry schema versions. New readers must understand
the previous version before writes switch; old readers must not treat unknown
authority fields as trusted. Legacy records coexist as `LEGACY_UNKNOWN` and use
coarse fallback. No backfill may infer parent ids, operation roles, action
scopes, or admission times from text.

## Data ownership

- The admission store owns record/envelope identity and authoritative time.
- The policy catalog owns source roles and scope caps by version.
- The revocation controller owns windows, generations, plans, and outcomes.
- Downstream memory is a materialized consumer, not the source of authority.

These boundaries keep one source of truth per fact and make replay/recovery
testable in the falsifier.
