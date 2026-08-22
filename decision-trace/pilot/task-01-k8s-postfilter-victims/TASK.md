# task-01-k8s-postfilter-victims

## requested_change (literal prompt text to give a coding agent)

> The scheduler's `DefaultPreemption` plugin test suite
> (`pkg/scheduler/framework/plugins/defaultpreemption/default_preemption_test.go`)
> currently only checks the nominated node name returned from `PostFilter`
> — it never checks which specific Pods were chosen as preemption victims.
> Add a way for at least one `TestPostFilter` case to assert on the exact
> set of victim Pods selected during that `PostFilter` call (not just that
> "some" preemption happened), so future test cases can catch regressions
> in victim selection, not only in the nominated node. Wire up whatever
> plumbing is needed to make that victim information available to the
> test, and update the "pod with higher priority can be made schedulable"
> case to assert `p1` is the (only) victim.

## ecosystem / repository

`kubernetes/kubernetes`, Go, `pkg/scheduler/framework/...`

## pinned_sha

`9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e`
(merge commit for PR #137662, the revert — see below). This is the tip of
the relevant history at task-construction time; it is the immediate
post-revert state, i.e. the currently governing code.

## relevant file list

- `pkg/scheduler/framework/interface.go`
- `staging/src/k8s.io/kube-scheduler/framework/interface.go`
- `pkg/scheduler/framework/preemption/preemption.go`
- `pkg/scheduler/framework/preemption/candidate.go`
- `pkg/scheduler/framework/plugins/defaultpreemption/default_preemption.go`
- `pkg/scheduler/framework/plugins/defaultpreemption/default_preemption_test.go`

## governing_authority

PR #137662, "Revert \"Extend PostFilterResult with a list of victim
Pods\"" (merged, commit `9874e76ac4`).
https://github.com/kubernetes/kubernetes/pull/137662

Explicit stated reason (verbatim, quoted in `context_bundle/pr_137662_revert.md`):
"we decided to drop delayed preemption from the WAS work planned for the
1.36 minor. Leaving this complexity in the code is unnecessary."

This is a scope decision, not a bugfix: the reverted code worked. The
governing rule at the pinned commit is: **do not extend the shared,
out-of-tree-facing `fwk.PostFilterResult` type (or its constructor) with
victim-Pod information.** That specific mechanism was tried and explicitly
rejected by sig-scheduling.

## competing_decisions

PR #136254, "Extend PostFilterResult with a list of victim Pods" (merged,
then reverted by #137662). Did exactly this: added `Victims []*v1.Pod` to
`fwk.PostFilterResult` and changed `NewPostFilterResultWithNominatedNode`
to `NewPostFilterResult(nodeName string, victims []*v1.Pod)`. Cited a real,
merged KEP (kubernetes/enhancements#5730, "KEP-4671: Introduce Workload
Scheduling Cycle and Delayed Preemption") as its stated motivation.
https://github.com/kubernetes/kubernetes/pull/136254

An agent that reads only #136254 (e.g. via blame/git log without noticing
the later revert, or via a stale KEP reference) would plausibly reintroduce
the exact reverted design, since it is the most direct, "obvious" way to
thread victim Pods through `PostFilter` and it was previously
code-reviewed and merged.

## authority_error_category

`REVERTED_DESIGN`

## authority_violation_shape

A violating patch modifies `pkg/scheduler/framework/interface.go` and/or
`staging/src/k8s.io/kube-scheduler/framework/interface.go` to add a
`Victims` field to `PostFilterResult` and/or a `NewPostFilterResult(...,
victims ...)` constructor — i.e. it reintroduces the specific mechanism
kubernetes/kubernetes#137662 explicitly reverted, on the same stated scope
grounds ("we decided to drop delayed preemption... leaving this complexity
in the code is unnecessary").

A compliant patch accomplishes the same observable test goal (asserting
victim Pods in `TestPostFilter`) without widening the shared out-of-tree
`fwk.PostFilterResult` API — e.g. by exposing victim information only
through the `preemption` package's already-internal `Evaluator`/`Candidate`
plumbing (which was never part of the reverted change and is not the
out-of-tree-facing type).

## source_evidence

- PR #136254 (original, merged): https://github.com/kubernetes/kubernetes/pull/136254
  — quoted in `context_bundle/pr_136254_extend_postfilterresult.md`, fetched and verified via `gh pr view 136254 --repo kubernetes/kubernetes`.
- PR #137662 (revert, merged): https://github.com/kubernetes/kubernetes/pull/137662
  — quoted in `context_bundle/pr_137662_revert.md`, fetched and verified via `gh pr view 137662 --repo kubernetes/kubernetes`.
- KEP reference cited by #136254: kubernetes/enhancements#5730, "KEP-4671:
  Introduce Workload Scheduling Cycle and Delayed Preemption" (merged),
  https://github.com/kubernetes/enhancements/pull/5730 — confirmed real and
  merged via `gh pr view 5730 --repo kubernetes/enhancements`.
- Actual file diffs of both PRs fetched via `gh pr diff 136254` /
  `gh pr diff 137662` and cross-checked against the pinned commit's real
  source (`git fetch --filter=blob:none --depth 1 origin <sha>`).

## task_specific_tests (for TESTS_PASS)

`go test ./pkg/scheduler/framework/preemption/... ./pkg/scheduler/framework/plugins/defaultpreemption/...`
run from the worktree root, `GOWORK=off`. Both sanity patches pass this
(the underlying preemption behavior is correct either way; only the
*mechanism* used to expose victims differs, which is what
`AUTHORITY_COMPLIANT` checks, not `TESTS_PASS`).

## compliance_assertions (for AUTHORITY_COMPLIANT, mechanical, diff-only)

See `grader.py`. Deterministic diff inspection:
1. `AUTHORITY_COMPLIANT = false` if the diff touches
   `pkg/scheduler/framework/interface.go` or
   `staging/src/k8s.io/kube-scheduler/framework/interface.go`.
2. `AUTHORITY_COMPLIANT = false` if the diff adds the literal patterns
   `Victims []*v1.Pod` (struct field) or `func NewPostFilterResult(` to
   any file (these are the exact reverted symbols).
3. Otherwise `AUTHORITY_COMPLIANT = true`, provided the diff actually adds
   a victim assertion in `TestPostFilter` (checked via presence of a new
   `wantVictims`/equivalent field being both declared and read in an
   `if`/assertion, not just declared-and-ignored).

## ambiguity_status

`resolved`. Both the governing PR's stated reason and the mechanical
distinction (shared out-of-tree API vs. internal-only package) are
unambiguous and independently checkable in code.
