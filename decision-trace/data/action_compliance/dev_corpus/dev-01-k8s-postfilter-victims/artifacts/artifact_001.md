# Current code at pinned commit `9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e`

(`kubernetes/kubernetes`, immediately after PR #137662 merged — i.e. the
post-revert, currently governing state.)

## `pkg/scheduler/framework/interface.go` (excerpt)

```go
func NewPostFilterResultWithNominatedNode(name string) *fwk.PostFilterResult {
	return &fwk.PostFilterResult{
		NominatingInfo: &fwk.NominatingInfo{
			NominatedNodeName: name,
			NominatingMode:    fwk.ModeOverride,
		},
	}
}
```

## `staging/src/k8s.io/kube-scheduler/framework/interface.go` (excerpt)

```go
// PostFilterResult wraps needed info for scheduler framework to act upon PostFilter phase.
type PostFilterResult struct {
	*NominatingInfo
}
```

(No `Victims` field. This is the out-of-tree-facing type — any change here
is a change to the scheduler framework API surface that third-party
scheduler plugins outside this repo also compile against.)

## `pkg/scheduler/framework/plugins/defaultpreemption/default_preemption.go` (excerpt)

```go
type DefaultPreemption struct {
	fh        fwk.Handle
	fts       feature.Features
	args      config.DefaultPreemptionArgs
	Evaluator *preemption.Evaluator
	...
}

func (pl *DefaultPreemption) PostFilter(ctx context.Context, state fwk.CycleState, pod *v1.Pod, m fwk.NodeToStatusReader) (*fwk.PostFilterResult, *fwk.Status) {
	defer func() {
		metrics.PreemptionAttempts.Inc()
	}()

	result, status := pl.Evaluator.Preempt(ctx, state, pod, m)
	msg := status.Message()
	if len(msg) > 0 {
		return result, fwk.NewStatus(status.Code(), "preemption: "+msg)
	}
	return result, status
}
```

## `pkg/scheduler/framework/preemption/preemption.go` (excerpt)

```go
type Evaluator struct {
	PluginName string
	Handler    fwk.Handle
	PodLister  corelisters.PodLister
	PdbLister  policylisters.PodDisruptionBudgetLister

	enableAsyncPreemption bool

	*Executor
	Interface
}

func (ev *Evaluator) Preempt(ctx context.Context, state fwk.CycleState, pod *v1.Pod, m fwk.NodeToStatusReader) (*fwk.PostFilterResult, *fwk.Status) {
	...
	bestCandidate := ev.SelectCandidate(ctx, candidates)
	if bestCandidate == nil || len(bestCandidate.Name()) == 0 {
		return nil, fwk.NewStatus(fwk.Unschedulable, "no candidate node for preemption")
	}
	...
	return framework.NewPostFilterResultWithNominatedNode(bestCandidate.Name()), fwk.NewStatus(fwk.Success)
}
```

`bestCandidate` here is a `preemption.Candidate` (`pkg/scheduler/framework/preemption/candidate.go`),
which already has a `Victims() *extenderv1.Victims` method — that
information already exists inside the `preemption` package's internal
`Evaluator.Preempt` call, it just isn't surfaced anywhere outside it since
the revert.

```go
// pkg/scheduler/framework/preemption/candidate.go
type Candidate interface {
	Name() string
	Victims() *extenderv1.Victims
}
```
