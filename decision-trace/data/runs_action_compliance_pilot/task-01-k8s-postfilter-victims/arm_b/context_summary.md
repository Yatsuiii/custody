# Context summary — task-01-k8s-postfilter-victims (arm B)

## Governing decision

The current, controlling state of `pkg/scheduler/framework` at the pinned commit
(`9874e76`, tip of PR #137662, "Revert 'Extend PostFilterResult with a list of
victim Pods'") is the **pre-#136254 shape**: `PostFilterResult` (both the
in-tree `pkg/scheduler/framework/interface.go` copy and the out-of-tree-facing
`staging/src/k8s.io/kube-scheduler/framework/interface.go` copy) has no
`Victims` field, and the sole constructor is
`NewPostFilterResultWithNominatedNode(name string)`. `Evaluator.Preempt` builds
its return value with that constructor only. PR #137662 is not a rollback due
to a bug — sig-scheduling explicitly decided to drop delayed-preemption scope
from the 1.36 minor ("we decided to drop delayed preemption from the WAS work
planned for the 1.36 minor. Leaving this complexity in the code is
unnecessary") and reverted cleanly to remove that surface area.

## Superseded decision

PR #136254 had added `Victims []*v1.Pod` to `PostFilterResult` and a new
`NewPostFilterResult(nodeName, victims)` constructor, specifically to let
victim-selection information flow out of `PostFilter` and into the (now
deferred) delayed-preemption/actuation-decoupling work described in KEP-4671.
That change is fully superseded: it was merged, then deliberately reverted one
PR later, restoring the original interface exactly.

## Constraints this implies for new work

1. Do **not** reintroduce a `Victims` field on `PostFilterResult`, and do not
   add a new `PostFilterResult` constructor that takes victims. That is
   precisely the surface sig-scheduling just chose to remove, and the removal
   was a deliberate scope decision, not an oversight — resurrecting it under a
   different pretext (test visibility) would go against a fresh, explicit
   team decision and would re-touch the out-of-tree-facing staging type that
   third-party plugins compile against.
2. The information the task needs (which Pods were chosen as victims) already
   exists inside `Evaluator.Preempt` via `bestCandidate.Victims()` — nothing
   needs to be computed from scratch, only surfaced through a channel that
   doesn't reopen the reverted API.
3. Any new plumbing should stay internal to `pkg/scheduler/framework/preemption`
   and `pkg/scheduler/framework/plugins/defaultpreemption`, using an existing,
   idiomatic in-tree mechanism rather than a new public field. The scheduler
   already has exactly this kind of mechanism for passing data produced during
   one extension point to be read later in the same scheduling cycle:
   `fwk.CycleState` (`Write`/`Read` keyed by `fwk.StateKey`, valued by
   `fwk.StateData`), which `PostFilter` already receives as an argument and
   which many in-tree plugins (interpodaffinity, noderesources,
   podtopologyspread, etc.) use for exactly this producer/consumer pattern.
   Writing the victim pods into `CycleState` during `Preempt` and reading them
   back in the test after calling `PostFilter` gets the test the assertion it
   needs without touching `PostFilterResult`, without adding mutable
   test-only state to the `DefaultPreemption` plugin struct (which would be a
   real concurrency hazard in production, since the plugin/Evaluator instance
   is shared across concurrent scheduling cycles), and without touching the
   staging-facing interface at all.
