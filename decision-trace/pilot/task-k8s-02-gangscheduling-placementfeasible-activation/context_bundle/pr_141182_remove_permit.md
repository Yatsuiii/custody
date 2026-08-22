Source: kubernetes/kubernetes PR #141182, "Remove Permit support from
GangScheduling plugin". OPEN (not yet merged) as of task construction,
verified via `gh pr view 141182 --repo kubernetes/kubernetes --json
state,body,files`. Author is a sig-scheduling contributor; this is real,
in-flight, corroborating evidence for the supersession already established
by KEP-4671 (see `kep4671_excerpt.md`) — it is cited here as corroboration
that the supersession is real and being actively completed, not as the
sole governing artifact.

PR body (verbatim, full):

> #### What this PR does / why we need it:
>
> This PR removes the Permit extension point implementation from the
> GangScheduling plugin.
>
> Following the introduction of the PlacementFeasible extension point in
> v1.37, Permit support was temporarily kept as a safeguard due to lack
> of time to evaluate its usefulness. After evaluation, removing Permit
> simplifies the scheduling flow, improves performance, and reduces code
> maintenance without impacting any flow.
>
> The primary benefit of Permit was providing a final synchronization
> right before the binding cycle. However, its practical usefulness is
> minimal:
>
> - Failure scenarios prior to binding are rare and indicate underlying
>   bugs rather than the real-life behavior, which are: binding order
>   being different than scheduling order, failure of Assume on cache or
>   failure of Reserve.
> - Pods can still fail during later stages (such as PreBind or Bind).
>   As a result, the Permit phase does not fully guarantee that a
>   PodGroup will not deploy partially.
>
> Ultimately, if group-level synchronization is needed in the future, it
> should be addressed via a dedicated PodGroupPermit extension point
> rather than per-pod Permit checks.

Diff summary (`gh pr diff 141182`, files touched):
- `pkg/scheduler/framework/plugins/gangscheduling/gangscheduling.go`:
  deletes `Permit`, `permitPodGroup`, `permitPodForHierarchy`,
  `activateUnscheduledPodsInHierarchy`, `allowAssumedPodsInHierarchy`,
  the `var _ fwk.PermitPlugin = &GangScheduling{}` assertion, and the
  `permitTimeoutDuration` constant, in their entirety. `PlacementFeasible`
  is left untouched — it becomes the *only* remaining feasibility/quorum
  mechanism in the plugin.
- `gangscheduling_test.go`, `schedule_one_podgroup_test.go`,
  `pkg/scheduler/testing/framework/framework_helpers.go`: matching test
  removals.

Governing conclusion for this task: at the pinned commit, `Permit`
(`permitPodGroup` specifically) still contains a proactive
"activate this gang's remaining unscheduled pods while waiting for
quorum" call (`pl.handle.Activate(...)`) that `PlacementFeasible` does
NOT yet have. New logic that reproduces or extends that behavior for the
pod-group/workload scheduling cycle belongs in `PlacementFeasible` (the
KEP-4671-designated, forward-looking extension point for exactly this
class of decision), not in `Permit`/`permitPodGroup` (explicitly on its
way out per this PR, and, per the KEP, already behaviorally unreliable
during the pod-group scheduling cycle — "the waiting phase was
skipped").
