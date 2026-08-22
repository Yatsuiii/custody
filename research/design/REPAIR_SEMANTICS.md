# Repair Semantics

Repair changes whether a record is usable; it does not rewrite what happened.
Historical content, parent edges, bound authority, and admission time are
immutable.

## Record states

```
LIVE -> BLOCKED -> DELETED
                 -> SUPERSEDED
```

- `LIVE`: effective authority is computed normally.
- `BLOCKED`: an active window intersects support; effective authority is
  `NONE` for every action scope and the record is excluded from active memory.
- `DELETED`: payload is removed from downstream/active storage; a minimal
  tombstone retains ids and repair evidence subject to retention policy.
- `SUPERSEDED`: the old record stays blocked, but a newly executed transform
  produced a separate replacement record.

There is no transition from `BLOCKED` back to `LIVE` for the same record.

## Immediate containment

Once a revocation generation is active, every affected record is logically
`BLOCKED` before asynchronous deletion or recomputation starts. The action
gateway consults this logical state. A failed downstream delete therefore
creates an availability/cleanup problem, not a window in which the record can
authorize an action.

`INFORM` is an authority tier, not a repair state. An affected record does not
become safe merely by changing its tier label; it remains `BLOCKED`. A separate
review UI may show quarantined payload as evidence, but the active memory and
action paths do not consume it.

## Forbidden shortcut: pruning support in place

The following operation is invalid:

```
Support(M) := Support(M) - compromised_roots
Caps(M)    := meet(caps of survivors)
```

It can elevate unchanged content. If `M` originally met `NONE` and `ACT`, its
cap was `NONE`; removing the `NONE` parent would make the same bytes `ACT` even
though no transform re-ran. Meet is not invertible, and parent removal changes
the proposition's evidentiary basis. I8 forbids this.

## Deterministic repair policy

For each affected record in topological order:

1. **Direct compromised root:** keep blocked; delete payload from active and
   downstream memory; retain the minimal tombstone required for audit/replay.
2. **Identity relay of one affected parent:** keep blocked and delete it. A
   later retrieval may cite an unaffected source as a new identity record; the
   old relay is not relabeled.
3. **Derived record with no replay contract:** keep blocked, then quarantine or
   delete according to retention policy.
4. **Derived record with a registered deterministic replay contract:** replay
   the transform using only currently live inputs plus explicitly supplied
   clean replacements. If the replay completes with a valid, complete envelope,
   admit a **new id** and mark the old record `SUPERSEDED`.
5. **Free-form model output:** no automatic semantic repair. It may be generated
   again as a new `FREEFORM`/`INFORM` record, but cannot recover `ACT` merely by
   dropping a parent.

Re-execution must not silently change the transform definition. The replacement
envelope records the transform revision, policy version, old record id, and
replacement inputs.

## Mixed and weak contributions

If any support root is affected, the whole derived record is blocked—even when
the compromised parent contributed one small substring. This is deliberate
conservatism. Selectivity comes first from choosing the correct interval roots,
not from unverifiable semantic surgery inside one output.

The falsifier reports this collateral separately. A future field-level replay
mechanism may reduce it only if a registered transform can prove which output
fields depend on which parents.

## Unaffected siblings

A record whose support does not intersect the active window remains `LIVE`,
including a root from the same tool admitted outside the window. Descendants
supported only by those outside-window roots also remain live. This is the
minimum proof of interval selectivity and is a mandatory falsifier case.

## Partial failure and recovery

Repair is driven by the durable `RepairPlan` in
`DYNAMIC_TRUST_MODEL.md`:

- every per-record operation is keyed by `(window_id, generation, record_id)`;
- duplicate delete/quarantine/supersede deliveries return the recorded outcome;
- an error remains retryable and keeps the plan incomplete;
- the logical block remains active throughout;
- a replacement is published only after its new admission envelope is durable;
  and
- completion requires the graph high-watermark to be caught up and every target
  to have a terminal outcome.

If the graph is inconsistent or a required parent/timestamp is unavailable,
repair fails closed and the system is not allowed to report a precise,
completed sweep.

## Actions already taken

The design can report which prior action decisions cited a now-blocked record
only if those decisions retained citation ids. It does not roll back exports or
other irreversible effects. That remains red-team case T and is outside the
memory-repair claim. The repair artifact must state the count of impacted past
decisions rather than implying they were undone.

## Retention and deletion

Payload deletion and audit evidence have different retention needs. A tombstone
contains only record id, parent ids or their deletion-safe digests, source/
window ids, outcome, and timestamps—never the deleted payload. If policy
requires even those identifiers to disappear, the audit must record a
redacted-deletion event rather than retaining content by indirection.

## Required outcomes

Every affected record ends in exactly one auditable outcome:

| Outcome | Payload active? | Can authorize? | Replacement exists? |
|---|---:|---:|---:|
| `QUARANTINED` | no | no | no |
| `DELETED` | no | no | no |
| `SUPERSEDED` | old: no; new: yes if policy permits | old: no; new: recomputed | yes, new id |
| `RETRY_REQUIRED` | logically blocked | no | not yet |

There is no outcome named "recomputed in place."
