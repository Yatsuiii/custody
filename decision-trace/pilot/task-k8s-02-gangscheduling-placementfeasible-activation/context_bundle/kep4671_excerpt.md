Source: kubernetes/enhancements, keps/sig-scheduling/4671-gang-scheduling/README.md
(KEP-4671, "Gang scheduling"), fetched via
`gh api repos/kubernetes/enhancements/contents/keps/sig-scheduling/4671-gang-scheduling/README.md`.
Excerpt below is from the KEP's "Workload Scheduling Cycle" design-details
section (approximately lines 1247-1297 of the fetched README.md at HEAD).

---

> Gang Scheduling is currently implemented as a plugin, meaning the `minCount`
> constraint is enforced at the plugin level. The proposed Workload Scheduling
> Cycle algorithm needs to know if this constraint is met to decide whether to
> commit the results. Initially, the Workload Scheduling Cycle reused the
> existing `Permit` extension point. However, because its usage was
> inconsistent (the waiting phase was skipped and `Permit` behaved differently
> depending on the cycle phase) and because we needed a fast rejection path, we
> propose a new extension point dedicated to checking `PodGroup` feasibility:
>
> ```go
> // PlacementFeasiblePlugin is an interface for plugins that are called after
> // each pod in a pod group is evaluated.
> // It is used to determine if a pod group is schedulable, may become
> // schedulable or will not become schedulable regardless of the scheduling
> // result of the remaining pods in the pod group.
> type PlacementFeasiblePlugin interface {
>   fwk.Plugin
>   // PlacementFeasible is called after each pod in a pod group is evaluated.
>   ...
>   PlacementFeasible(ctx context.Context, placementCycleState fwk.PlacementCycleState, podGroupInfo fwk.PodGroupInfo, placementProgress PlacementProgress) *fwk.Status
> }
> ```
>
> The `PlacementFeasible` is called after each pod being evaluated during the
> Workload Scheduling Cycle (during step 4. of the algorithm above), regardless
> of whether the pod succeeded or not.

Key point: the KEP explicitly states that reusing `Permit` for pod-group
feasibility checking during the (multi-pod) Workload Scheduling Cycle was
tried first and abandoned specifically because `Permit`'s behavior was
inconsistent in that cycle ("the waiting phase was skipped"). `PlacementFeasible`
is the dedicated, purpose-built replacement for that role in the pod-group
scheduling cycle. `Permit` itself is not deleted by this KEP (it still exists
for the ordinary pod-by-pod scheduling cycle at the time of writing), but it is
explicitly superseded as the mechanism for workload/pod-group-cycle
feasibility/quorum decisions.
