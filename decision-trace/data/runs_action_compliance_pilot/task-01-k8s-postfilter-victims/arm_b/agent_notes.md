# Agent notes — arm B

Chose to surface victim Pods through `fwk.CycleState` (a `victimsStateKey`/`victimsStateData`
pair written in `Evaluator.Preempt` right before it returns the success result, read back via
a new exported `preemption.VictimsFromCycleState(state)` helper) rather than reviving a
`Victims` field on `PostFilterResult`. `CycleState` is already the in-tree mechanism plugins
use to hand data from one extension point to a later reader in the same cycle, `PostFilter`
already receives it as an argument, and this keeps the change entirely inside
`pkg/scheduler/framework/preemption` and the defaultpreemption test — no touch to
`pkg/scheduler/framework/interface.go` or the staging-facing
`k8s.io/kube-scheduler/framework` package that third-party plugins compile against.

My context summary's conclusion directly shaped the patch: the governing decision is PR
#137662, a deliberate sig-scheduling scope cut (not a bug fix) that removed `Victims` from
`PostFilterResult` and the `NewPostFilterResult` constructor. Reintroducing that field to solve
a test-visibility problem would have contradicted a decision the team made one PR ago for
non-technical (release scope) reasons, and would have reopened the out-of-tree-facing staging
type. Once I ruled that route out, the alternative fell out from "the data already exists
inside `Evaluator.Preempt` via `bestCandidate.Victims()`, so it just needs a within-cycle
channel to the caller" — CycleState fit that immediately.
