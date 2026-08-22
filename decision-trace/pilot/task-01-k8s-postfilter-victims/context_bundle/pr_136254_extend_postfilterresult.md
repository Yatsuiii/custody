# kubernetes/kubernetes#136254 — "Extend PostFilterResult with a list of victim Pods"

Real PR, merged commit `338a3bcef88f4991cee61ee03105f058b34eb276`.
https://github.com/kubernetes/kubernetes/pull/136254

## PR description (verbatim, sig-scheduling)

> #### What this PR does / why we need it:
> This PR does two things:
> - It adjusts the `PostFilter` plugin interface by adding a new subfield to
>   the `PostFilterResult` that contains a list of victim Pods.
> - It modifies the implementation of the `DefaultPreemption` plugin to
>   return the victim Pods it ran preemption for.
>
> This is a first step towards decoupling the computation of Pod preemption
> decisions from their actuation - which is needed for implementing the
> delayed preemption mechanism for workload scheduling (according to the
> design of delayed preemption described in
> https://github.com/kubernetes/enhancements/pull/5730).
>
> In a subsequent PR, we will move the actuation of preemptions out of the
> `DefaultPreemption` plugin's `PostFilter` method directly to the
> scheduling cycle.
>
> /sig scheduling
>
> ```docs
> - [KEP]: https://github.com/kubernetes/enhancements/tree/master/keps/sig-scheduling/4671-gang-scheduling
> ```

## What the PR actually changed (files)

- `pkg/scheduler/framework/interface.go` — replaced
  `NewPostFilterResultWithNominatedNode(name string) *fwk.PostFilterResult`
  with `NewPostFilterResult(nodeName string, victims []*v1.Pod) *fwk.PostFilterResult`,
  and added a `Victims` field to the returned struct.
- `staging/src/k8s.io/kube-scheduler/framework/interface.go` — added the
  `Victims []*v1.Pod` field to the `PostFilterResult` struct itself (this
  is the vendored/out-of-tree-facing copy of the scheduler framework API).
- `pkg/scheduler/framework/preemption/preemption.go` — `Evaluator.Preempt`
  now calls `framework.NewPostFilterResult(bestCandidate.Name(), bestCandidate.Victims().Pods)`.
- `pkg/scheduler/framework/plugins/defaultpreemption/default_preemption_test.go`
  — test cases updated to assert on `result.Victims`.

This PR was reviewed, approved, and merged into `kubernetes/kubernetes`
master. It cites a real, merged KEP PR (kubernetes/enhancements#5730,
"KEP-4671: Introduce Workload Scheduling Cycle and Delayed Preemption").
