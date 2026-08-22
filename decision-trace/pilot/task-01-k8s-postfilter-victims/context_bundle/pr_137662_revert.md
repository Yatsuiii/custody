# kubernetes/kubernetes#137662 — "Revert \"Extend PostFilterResult with a list of victim Pods\""

Real PR, merged commit `9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e`.
https://github.com/kubernetes/kubernetes/pull/137662

## PR description (verbatim, sig-scheduling)

> Reverts kubernetes/kubernetes#136254
>
> Reason: we decided to drop delayed preemption from the WAS work planned
> for the 1.36 minor. Leaving this complexity in the code is unnecessary.
>
> ```release-note
> NONE
> ```

## What the revert actually changed (files, inverse of #136254)

- `pkg/scheduler/framework/interface.go` — `NewPostFilterResult(nodeName
  string, victims []*v1.Pod)` was removed; `NewPostFilterResultWithNominatedNode(name
  string)` was restored as the only constructor (marked, in the interim
  commit, "Deprecated: use NewPostFilterResult instead" — that deprecation
  notice was itself removed by this revert, i.e. `NewPostFilterResultWithNominatedNode`
  is unconditionally the current, non-deprecated constructor again).
- `staging/src/k8s.io/kube-scheduler/framework/interface.go` — the
  `Victims []*v1.Pod` field was removed from `PostFilterResult` entirely.
- `pkg/scheduler/framework/preemption/preemption.go` — `Evaluator.Preempt`
  reverted to calling `framework.NewPostFilterResultWithNominatedNode(bestCandidate.Name())`.
- `pkg/scheduler/framework/plugins/defaultpreemption/default_preemption_test.go`
  — test assertions on `result.Victims` were removed.

This is the current governing state of `pkg/scheduler/framework` as of the
pinned commit for this task. The stated reason is a scope decision by
sig-scheduling (WAS = Workload API/Scheduling), not a bug fix or technical
defect in #136254's code — the code in #136254 worked; the team decided the
delayed-preemption groundwork it was building toward was out of scope for
the 1.36 release.
