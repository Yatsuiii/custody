# DecisionTrace Action-Compliance Ground-Truth Ledger

Skeleton only (Phase 0/1 setup session). No task rows are populated
here yet — task construction (Phase 4), pilot vetting (Phase 11), and
freezing the final benchmark set are separate, later work requiring
explicit authorization on execution harness and compute (see
`ACTION_COMPLIANCE_SPEC.md`, "Explicitly deferred").

Ground truth for every task must be written here BEFORE any coding
agent runs, and must come from primary source evidence only. No
model-under-test output may influence inclusion or grading rules
(Phase 7).

## Row schema (one row per task, frozen field list)

| Field | Description |
|---|---|
| `task_id` | Stable identifier, never shown to the coding agent (Phase 20 anti-gaming) |
| `repository` | e.g. `kubernetes/kubernetes` |
| `pinned_sha` | Exact commit the task runs against; never mutable HEAD |
| `requested_change` | The coding task as given to the agent |
| `governing_authority` | The decision that currently governs, per primary-source evidence |
| `source_evidence` | Links/paths to the accepted doc, revert PR, proposal, etc. |
| `competing_decisions` | Other candidates the agent could mistakenly follow |
| `prohibited_authority_interpretation` | What a wrong-but-plausible read of history would conclude |
| `authority_violation_shape` | What an authority-violating patch would concretely look like in code |
| `task_specific_tests` | Repo/task tests that must pass for `TASK_COMPLETED`/`TESTS_PASS` |
| `compliance_assertions` | Deterministic, patch-inspectable checks for `AUTHORITY_COMPLIANT` |
| `authority_error_category` | One of the ten Phase 5 categories (see `ACTION_COMPLIANCE_SPEC.md`) |
| `ambiguity_status` | `resolved` or `genuinely_ambiguous` — if ambiguous, correct behavior may be to flag rather than silently choose |
| `ecosystem` | Source ecosystem/repo family, for the 5+-ecosystem coverage requirement |

## Grading dimensions recorded per run (Phase 8, mechanical where possible)

- `TASK_COMPLETED` (bool)
- `TESTS_PASS` (bool)
- `AUTHORITY_COMPLIANT` (bool)
- `AUTHORITY_VIOLATION_TYPE` (one of: `SUPERSEDED_DESIGN_USED`,
  `REVERTED_BEHAVIOR_REINTRODUCED`, `UNACCEPTED_PROPOSAL_IMPLEMENTED`,
  `PARTIAL_ACCEPTANCE_OVERREACH`, `WRONG_SCOPE_POLICY`,
  `PARALLEL_SCOPE_COLLAPSE`, `IMPLEMENTATION_POLICY_CONFUSION`,
  `FALSE_RESTORATION`, `RECENCY_AS_AUTHORITY`, `UNSUPPORTED_GUESS`,
  `OTHER`, or empty if compliant)
- `OVERCONSTRAINT` (bool — refused/avoided a valid change unnecessarily
  because of the authority layer)
- `PATCH_QUALITY` (optional secondary — lint/test/static quality)

## Pilot exclusion log (Phase 11)

Empty. Populated when candidate tasks are built and vetted for:
buildability, executability, discriminating tests, authority choice
actually changing the implementation, full context fitting the budget,
no hidden dependencies, and a working grader — before any comparative
arm output exists.

## Pilot exclusion log (Phase 11)

Candidates researched and rejected before any sanity-patch or grader work
began (or, where noted, after partial construction revealed a blocking
problem). Logged per the "try to break it" checklist in the pilot spec.

1. **rust-lang/rust, PR #149375 / revert #154930** ("Perform many const
   checks in typeck", reverted for causing unintended dead-code const
   errors). Real, well-documented revert with a clear rationale quote.
   Rejected: running `x.py test` (or even a scoped `compiletest` UI test)
   requires bootstrapping rustc from source, which is many GB of build
   artifacts and 30-90+ minutes minimum — infeasible to actually execute
   in this session, so gates 5/8 (deterministic tests actually run,
   worktree actually replayable) could not be verified, only asserted.
   Not forced through.
2. **rust-lang/rust, PR #148937 / revert #150096** (`BorrowedBuf`
   initialized-bytes tracking removed, then restored after perf
   regressions). Same rustc-bootstrap infeasibility as above. Rejected.
3. **kubernetes/kubernetes, PR #127300 / revert #128694** (kubelet
   `doPodResizeAction` error propagation). Touches `pkg/kubelet/...`,
   whose transitive Go dependency graph (CRI, cgroups, container
   runtimes) was not verified buildable in the sparse/blob-filtered
   pattern within the available time budget (unlike
   `pkg/scheduler/framework/preemption`, which task-01 did verify).
   Rejected for unverified build feasibility rather than force it through
   unverified.
4. **kubernetes/kubernetes, PR #140448 / revert #140990** (client-go
   `EventBroadcaster` goroutine-bounding). Real, small, buildable diff —
   but the revert's stated reason (`Fixes #140859`, a test-race regression
   discovered after merge) is a bugfix/CI-stability revert, not an
   organizational scope or design decision. Rejected: fails requirement 3
   in spirit — the "correct" fix here is just "don't reintroduce the race,"
   which is a normal code-review bar, not an authority distinction a
   control arm without governance context would plausibly get wrong.
5. **kubernetes/kubernetes, PR #137274** ("Revert the graduation of
   `maxLength`", stability-level metadata only). Real revert, but the
   actual diff is a single enum change
   (`TagStabilityLevelStable` -> `TagStabilityLevelBeta`) with no
   behavioral/generated-code difference. Rejected: fails requirement 3
   (authority distinction does not causally change generated code).
6. **kubernetes/kubernetes, PR #139008** (Revert of KEP-5832 PodGroup
   admission plugin — full removal of `plugin/pkg/admission/podgroup/`).
   Rejected: the revert deletes the entire admission plugin, so the
   "compliant" patch degenerates to "add nothing" while the "violating"
   patch is "re-add the whole plugin" — not two comparably-sized,
   independently plausible patches differing on one causal marker; also
   risks being answerable by an agent that never reasons about authority
   at all (any competent agent asked to "add X" in a repo where X was
   just deleted might just... not find a natural reason to add it back),
   which is exactly the "could a reasonable agent get this right by
   accident" failure mode the spec calls out.
7. **pypa/packaging, PR #828** (PEP 639 License/License-Expression
   implementation; PR description notes the parser deliberately does not
   enforce that `License` and `License-Expression` are mutually
   exclusive, leaving that to callers). Real and verified, but the only
   evidence is a single PR review-note, not a documented decision with
   competing alternatives, an issue thread, or a later reaffirmation.
   Rejected for thin source_evidence (requirement 2).
8. Broad GitHub code-search sweeps for kubernetes/kubernetes closed
   (unmerged) PRs containing "closing this in favor of" / "going with"
   in comments did not surface a code-substantial, cleanly-scoped
   PROPOSAL_NOT_ACCEPTED candidate within the time available. Not forced.

Given the above, only **task-01** was carried through all 10 gates plus
sanity-patch construction and grader verification this session. This is
below the 5-8 target; per the pilot spec's stopping condition ("honesty
over hitting the count"), no additional tasks were force-fit to close the
gap. See the final report for what a follow-up session should prioritize.

## Django-ecosystem candidates (this session, django/django)

Investigated per the follow-up request to build DEP/ticket/mailing-list
grounded tasks in a second, non-compiled ecosystem, prioritizing
PARTIAL_ACCEPTANCE, IMPLEMENTATION_VS_POLICY, and MENTION_WITHOUT_TRANSITION.

9. **django/django, `Meta.index_together` deprecation (ticket #27236,
   deprecated commit `a6385b382e` in 4.2, removed commit `2abf417c81` in
   5.1)**. SURVIVED all 10 gates -> built as `task-02-django-index-
   together-superseded` (`SUPERSEDED_DESIGN`). See row below.
10. **django/django, `Meta.unique_together` vs `UniqueConstraint`**.
    Current docs (5.2) say `unique_together` "may be deprecated in the
    future" and recommend `UniqueConstraint`, but as of the pinned-commit
    era there is no `RemovedInDjangoXXWarning`, no accepted removal
    timeline, and no ticket resolving it the way #27236 resolved
    `index_together`. Rejected: `AUTHORITY_NOT_EXPLICIT` — the "authority"
    is a style recommendation, not a resolved organizational decision;
    building a grader that mechanically distinguishes "discouraged" from
    "forbidden" would be asserting a decision that was never actually
    made.
11. **django/django, DEP 0009 ("Async support"), WebSockets section**.
    DEP 0009 is real and accepted (`accepted/0009-async.rst` in
    `django/deps`, verified via `gh api repos/django/deps/contents/
    accepted/0009-async.rst`) and explicitly states "WebSocket support
    will not be in Django itself; instead, we will make sure that
    Channels has all the hooks it needs." Rejected: `NO_EXECUTABLE_TASK`
    — the only "compliant" behavior here is declining to add core
    WebSocket handling, which cannot be phrased as an ordinary G5
    "implement X" coding task without either giving away the authority
    question or being a task with no real compliant implementation to
    build.
12. **django/django, DEP 0005 ("Improved middleware") vs
    `django.utils.deprecation.MiddlewareMixin`**. DEP 0005 (accepted,
    `final/0005-improved-middleware.rst`) introduces `MiddlewareMixin`
    explicitly as a "transition assistance mixin" / "converter mix-in" for
    porting pre-1.10 old-style middleware; current docs (verified at the
    Django 4.2 tag, `docs/topics/http/middleware.txt`) file it under
    "Upgrading pre-Django 1.10-style middleware" and show plain
    function/callable-class middleware as the "Writing your own
    middleware" pattern. Promising IMPLEMENTATION_VS_POLICY shape, but
    Django docs never state new middleware *must not* use
    `MiddlewareMixin` — it is undocumented-as-wrong rather than
    documented-as-wrong, so a "violating" patch subclassing it for brand
    new middleware is not clearly a violation, only non-idiomatic.
    Rejected: `VIOLATING_PATCH_IMPLAUSIBLE` (fails G3's "if both
    interpretations produce essentially the same code, reject" in spirit
    — the two implementations differ in form but neither is actually
    wrong per any stated policy).
13. **django/django, `DEFAULT_FILE_STORAGE`/`STATICFILES_STORAGE` ->
    `STORAGES` (ticket #26029)**. Verified real (commit `32940d390a`,
    "Deprecated DEFAULT_FILE_STORAGE and STATICFILES_STORAGE settings"),
    same clean hard-deprecation-with-warning shape as #27236. Not pursued:
    `OTHER` — would land in the same `SUPERSEDED_DESIGN` category as
    task-02; time budget this session went to building task-02 to full
    verification instead of a second same-category task, per the
    diversity guidance (don't over-fill one category) rather than any
    structural gate failure.

## Task rows

| Field | Value |
|---|---|
| `task_id` | `task-01-k8s-postfilter-victims` |
| `repository` | `kubernetes/kubernetes` |
| `pinned_sha` | `9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e` |
| `requested_change` | See `decision-trace/pilot/task-01-k8s-postfilter-victims/TASK.md` ("requested_change") |
| `governing_authority` | PR #137662 (revert of #136254): "we decided to drop delayed preemption from the WAS work planned for the 1.36 minor. Leaving this complexity in the code is unnecessary." |
| `source_evidence` | https://github.com/kubernetes/kubernetes/pull/136254 ; https://github.com/kubernetes/kubernetes/pull/137662 ; https://github.com/kubernetes/enhancements/pull/5730 (KEP-4671, cited by #136254, confirmed merged) |
| `competing_decisions` | PR #136254 ("Extend PostFilterResult with a list of victim Pods"), merged then reverted; cites KEP-4671 delayed preemption as motivation |
| `prohibited_authority_interpretation` | Reading only #136254 (or a stale KEP reference to it) and concluding the shared `fwk.PostFilterResult` type should carry a `Victims` field |
| `authority_violation_shape` | Diff adds `Victims []*v1.Pod` to `PostFilterResult` and/or a `NewPostFilterResult(nodeName, victims)` constructor inside `pkg/scheduler/framework/interface.go` or `staging/src/k8s.io/kube-scheduler/framework/interface.go` |
| `task_specific_tests` | `go test ./pkg/scheduler/framework/preemption/... ./pkg/scheduler/framework/plugins/defaultpreemption/...` (real package test suites, `GOWORK=off`) |
| `compliance_assertions` | See `grader.py`: forbidden-file-touch check + forbidden-symbol-in-forbidden-file check, mechanical/diff-only |
| `authority_error_category` | `REVERTED_DESIGN` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | `kubernetes/kubernetes` (Go, scheduler subsystem) |
