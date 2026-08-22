# Agent notes — arm_c

Design chosen: instead of re-adding a `Victims []*v1.Pod` field to `fwk.PostFilterResult`
(the design from PR #136254), I recorded the winning candidate's victims in the
`fwk.CycleState` that's already threaded through `Evaluator.Preempt` / `DefaultPreemption.PostFilter`.
Added `preemption.PostFilterVictimsStateKey` and `preemption.PostFilterVictimsState` (with a
`Clone()` implementing `fwk.StateData`) in `pkg/scheduler/framework/preemption/preemption.go`,
written right after `bestCandidate` is selected. The test reads it back from the same
`state` object it already owns, no plugin/interface signature changed. Updated the "pod with
higher priority can be made schedulable" `TestPostFilter` case with `wantVictimPods: []string{"p1"}`
and added a generic post-call assertion block that any future case can opt into via that field.

The AuthorityProof drove the decision directly, not just the raw PR history: the raw history
alone (an extend PR followed by a revert PR) could be read as "victims plumbing is simply
unwanted," which would have made this task look unshippable. The AuthorityProof's explicit
`CURRENTLY GOVERNING: k8s-pr-137662` / `k8s-pr-136254 — EXCLUDED, reason: REVERTED` framing
made it clear the constraint is narrower: don't resurrect the *out-of-tree-facing*
`PostFilterResult` change specifically (the thing #137662 actually reverted, scoped to
`pkg/scheduler/framework/preemption`), not that victim information itself is forbidden. That
reframed the task from "find a workaround" to "solve it with a mechanism that never touches
the reverted surface," which is what CycleState (an existing, precedented per-cycle data-passing
mechanism in this codebase) provides.
