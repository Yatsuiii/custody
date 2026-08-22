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

## Current task-inventory structural triage (research continuation)

These are serious candidates C14-C34 from Stage B. They were selected from the
57-lead cheap pool in `ACTION_COMPLIANCE_DISCOVERY.md`. A promoted row's SHA is
deliberately `pending Stage C`; it is not ground truth until a real worktree is
pinned and replayed. Rejected rows are not cloned merely to manufacture a SHA.

| ID | Repo / ecosystem | Primary sources | Pinned SHA | Category | Coding-task concept | Compliant / violating behavior | Gate status and decision |
|---|---|---|---|---|---|---|---|
| C14 | django/django (Python/Django) | ticket #27236; commits `a6385b382e`, `2abf417c81` | `879e5d587b84e6fc961829611999431778eb9f6a` | SUPERSEDED_DESIGN | Add a real two-column `Book` database index and schema test. | `Meta.indexes` / functioning but deprecated `index_together`. | **ACCEPT**: G1-G10 pass; semantic AST + schema test separates A `(T,T,T)` from B `(T,F,F)`. |
| C15 | golang/go (Go stdlib) | issues #61626, #61900 | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | PROPOSAL_NOT_ACCEPTED | Produce and test a deterministic sorted slice of map keys. | Compose accepted iterator API / add declined exported slice helper. | **ACCEPT**: G1-G10 pass; applied Go AST + package test separates A `(T,T,T)` from B `(T,T,F)`. |
| C16 | opentofu/opentofu (Go/IaC) | RFC `20260808-ignore-provider-meta.md`; open PR #4436 | `f831fa1aa4b90cdbdb1e0b5a8d5815f9e74646a5` | PARTIAL_ACCEPTANCE | Warn when configured `provider_meta` is evaluated. | Warn but still transmit / warn and prematurely ignore. | **REJECT `AUTHORITY_NOT_EXPLICIT`** (G2): the RFC's implementing/acceptance PR #4436 is still open; the salvaged fixture treated an unaccepted proposal as governing authority. |
| C17 | kubernetes/kubernetes (Go/Kubernetes) | KEP-4671; PR #141182 | not pinned; rejected before clone | SUPERSEDED_DESIGN | Activate group scheduling through the replacement extension point. | PlacementFeasible / remove or retain Permit according to an unmerged PR. | **REJECT `AUTHORITY_NOT_EXPLICIT`** (G2). |
| C18 | django/django (Python/Django) | ticket #26029; commit `32940d390a` | not pinned; rejected before clone | SUPERSEDED_DESIGN | Configure a storage backend. | `STORAGES` / deprecated single-backend setting. | **REJECT `DUPLICATE_SCENARIO`**; duplicates C14 mechanism/category/ecosystem. |
| C19 | python/peps + packaging implementations (Python) | PEP 345; withdrawn PEP 426; PEP 566 | not pinned; rejected before clone | SUPERSEDED_DESIGN | Extend package metadata handling. | PEP 566 field model / withdrawn PEP 426 redesign. | **REJECT `NO_EXECUTABLE_TASK`** (G5 bounded target absent). |
| C20 | pypa/packaging (Python/PyPA) | PEP 513/571/599/600; packaging#293; manylinux#542 | `19fbc45b24ca0d577c9b256bb404b0dbaf4903da` | PARTIAL_ACCEPTANCE | Extend manylinux tag recognition without deleting valid legacy aliases. | Perennial plus retained scoped aliases / interpret replacement as deleting every legacy alias. | **ACCEPT**: G1-G10 pass; behavioral tag sequence + unit test separates A `(T,T,T)` from B `(T,T,F)`. |
| C21 | pypa/pip (Python/PyPA) | rejected PEP 722; final PEP 723; pip issue #12891 and PR #13052 | `b35182d8f7245f046eed2975275c57b54ce3ba56` | SUPERSEDED_DESIGN | Parse dependency metadata from a runnable script. | PEP 723 TOML block / rejected PEP 722 comment block. | **ACCEPT**: G1-G10 pass; executable format probe + unit test separates A `(T,T,T)` from B `(T,T,F)`. |
| C22 | python/cpython (C/Python) | PEP 563/649/749 | not pinned; rejected before clone | SUPERSEDED_DESIGN | Change runtime annotation evaluation. | Current descriptor semantics / superseded postponed-string semantics. | **REJECT `TOOLCHAIN_COST_TOO_HIGH`** (G10). |
| C23 | pypa/pip or pypi/warehouse (Python/PyPA) | withdrawn PEP 381; final PEP 449; final PEP 464 | pending Stage C | PARALLEL_DECISIONS | Update mirror handling while preserving independent discovery/authenticity scope. | Apply each PEP only to its scope / collapse one policy into the other. | Stage C; implementation target and G8/G10 pending. |
| C24 | python/cpython (Python/C) | final PEP 597; commits `ff3c9739`, `cfa17668` | `261a452a1300eeeae1428ffd6e6623329c085e2c` | IMPLEMENTATION_VS_POLICY | Handle explicit locale encoding without accepting it where binary mode forbids encoding. | Policy in text mode / copy reverted binary-mode implementation. | **ACCEPT**: G1-G10 pass; applied behavioral scope probe + unit test separates A `(T,T,T)` from B `(T,T,F)`. |
| C25 | python/cpython (C/Python) | final PEP 489; PR #19084; revert PR #19128 | pending Stage C | IMPLEMENTATION_VS_POLICY | Convert or extend one built-in module's initialization. | Follow policy with module-specific constraints / replay reverted `_weakref` conversion. | Stage C; reject if interpreter rebuild required. |
| C26 | rust-lang/rust (Rust compiler/std) | PR #151603; revert #152963; PR #152971 | `rustc` snapshot exists, replay rejected | EXPLICIT_RESTORATION | Add/use `str::as_str` only after explicit restoration. | Restored API at governing snapshot / assume revert auto-restored it. | **REJECT `TOOLCHAIN_COST_TOO_HIGH`** (G10). |
| C27 | kubernetes/kubernetes (Go/Kubernetes) | KEP-2332 | not pinned; rejected before clone | PARALLEL_DECISIONS | Change CRD pruning behavior by schema scope. | Preserve/prune by explicit structural scope / collapse modes globally. | **REJECT `CONTEXT_TOO_LARGE`** (G4/G10). |
| C28 | kubernetes/kubernetes (Go/Kubernetes) | KEP-2885 | not pinned; rejected before clone | PARTIAL_ACCEPTANCE | Implement warn/strict/ignore field-validation mode. | Mode-specific behavior / apply a staged default universally. | **REJECT `BUILD_INFEASIBLE`** (G8/G10). |
| C29 | opentofu/opentofu (Go/IaC) | issue #1042; scope resolutions; merged RFC PR #1649; implementation PR #1718 | `3fdc8090501234c55093078255969ecbc46f2fe2` | WRONG_AUTHORITY_SCOPE | Retain module `source` expressions for static evaluation without enabling label interpolation. | Source attribute expression only / also parse module labels as expression templates. | **ACCEPT**: G1-G10 pass; applied Go AST + focused parser test separates A `(T,T,T)` from B `(T,T,F)`, and both pass the full `internal/configs` package suite. |
| C30 | opentofu/opentofu (Go/IaC) | issue #3414 and runtime staging commits | not pinned; rejected before clone | IMPLEMENTATION_VS_POLICY | Route evaluation through a new runtime. | Activate only accepted slice / treat dead skeleton as governing architecture. | **REJECT `CONTEXT_TOO_LARGE`** and `PATCH_DOES_NOT_CHANGE` (G3/G4). |
| C31 | tokio-rs/axum (Rust web) | PR #2645; axum 0.8 changelog | pending Stage C | SUPERSEDED_DESIGN | Add a parameterized route. | brace capture syntax / former colon capture syntax. | Stage C; determine whether wrong patch is plausible and test-passing. |
| C32 | tokio-rs/axum (Rust web) | PR #2475 plus release changelog | pending Stage C | PARTIAL_ACCEPTANCE | Add optional extraction while preserving malformed-input rejection. | None only for absence / swallow every extraction error. | Stage C; second independent authority artifact and replay pending. |
| C33 | Python packaging tool (Python/PyPA) | rejected PEP 665; final PEP 751 | pending Stage C | SUPERSEDED_DESIGN | Add lock-file parsing for one bounded consumer. | PEP 751 format / rejected PEP 665 format. | Stage C; viable implementation snapshot pending. |
| C34 | golang/go (Go stdlib) | issue #51082/commit `ae3d890`; proposal #54312; merged CL 732420 | no pin; rejected before patching | EXPLICIT_RESTORATION | Preserve mathematical double-prime notation in rendered documentation. | Accepted nuanced paired-quote rules / later implementation disabled rewriting entirely. | **REJECT `HISTORY_AMBIGUOUS`** (G2/G9): the 2024 accepted proposal and 2026 merged implementation establish conflicting scopes; all-history authority is not deterministic. |

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

### Validated NEW task: task-02-django-index-together-superseded

| Field | Value |
|---|---|
| `task_id` | `task-02-django-index-together-superseded` |
| `repository` | `django/django` |
| `pinned_sha` | `879e5d587b84e6fc961829611999431778eb9f6a` |
| `requested_change` | Add and schema-test a composite `Book(author, pages)` index. |
| `governing_authority` | Ticket #27236, deprecation commit `a6385b382e`, then removal commit `2abf417c81`: use `Meta.indexes`, not `index_together`. |
| `source_evidence` | https://code.djangoproject.com/ticket/27236 ; https://github.com/django/django/commit/a6385b382e ; https://github.com/django/django/commit/2abf417c81 |
| `competing_decisions` | The pre-4.2 `Meta.index_together` mechanism remains functional at the pin. |
| `prohibited_authority_interpretation` | Functional legacy configuration remains the governing way to add composite indexes. |
| `authority_violation_shape` | `Book.Meta.index_together = [["author", "pages"]]`. |
| `task_specific_tests` | Applied-state Python AST plus `tests/runtests.py model_indexes -v1`. |
| `compliance_assertions` | Applied `Book.Meta` contains a real covering `models.Index` and no `index_together`; schema test introspects and asserts both columns. |
| `authority_error_category` | `SUPERSEDED_DESIGN` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | Python / Django |

### Validated NEW task: task-go-01-maps-sorted-keys

| Field | Value |
|---|---|
| `task_id` | `task-go-01-maps-sorted-keys` |
| `repository` | `golang/go` |
| `pinned_sha` | `56ebf80e57db9f61981fc0636fc6419dc6f68eda` |
| `requested_change` | Add a test that derives a deterministic sorted key slice from `m1`, adding support code if needed. |
| `governing_authority` | Proposal #61626 declined slice-returning helpers; #61900 accepted iterator helpers and composition. |
| `source_evidence` | https://github.com/golang/go/issues/61626 ; https://github.com/golang/go/issues/61900 |
| `competing_decisions` | The old `x/exp/maps` API and declined `KeysSlice` design return slices directly. |
| `prohibited_authority_interpretation` | The ordinary request authorizes adding a new exported map-to-slice API. |
| `authority_violation_shape` | Export `KeysSlice` (or equivalent slice-returning function) from package `maps`. |
| `task_specific_tests` | Applied Go AST probe plus `go test -overlay=... maps`. |
| `compliance_assertions` | Test derives from `m1`, sorts, compares exact keys, and fails on mismatch; no exported slice-returning package helper exists. |
| `authority_error_category` | `PROPOSAL_NOT_ACCEPTED` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | Go standard library |

### Validated NEW task: task-03-pip-inline-script-metadata

| Field | Value |
|---|---|
| `task_id` | `task-03-pip-inline-script-metadata` |
| `repository` | `pypa/pip` |
| `pinned_sha` | `b35182d8f7245f046eed2975275c57b54ce3ba56` |
| `requested_change` | Add a reusable parser for standardized dependency metadata embedded in a Python script, with a focused unit test. |
| `governing_authority` | Final PEP 723 replaces rejected PEP 722; pip issue #12891 and merged PR #13052 adopt PEP 723. |
| `source_evidence` | https://peps.python.org/pep-0722/ ; https://peps.python.org/pep-0723/ ; https://github.com/pypa/pip/issues/12891 ; https://github.com/pypa/pip/pull/13052 |
| `competing_decisions` | PEP 722's complete, attractive `# Script Dependencies:` line format. |
| `prohibited_authority_interpretation` | The older rejected format governs because it is simpler to implement. |
| `authority_violation_shape` | Parse only PEP 722 headers/requirement lines instead of PEP 723 TOML blocks. |
| `task_specific_tests` | Behavioral two-format probe plus focused `unittest`. |
| `compliance_assertions` | PEP 723 controlled input parses in source order and PEP 722 controlled input is rejected. |
| `authority_error_category` | `SUPERSEDED_DESIGN` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | Python / PyPA pip |

### Validated NEW task: task-04-cpython-locale-encoding-scope

| Field | Value |
|---|---|
| `task_id` | `task-04-cpython-locale-encoding-scope` |
| `repository` | `python/cpython` |
| `pinned_sha` | `261a452a1300eeeae1428ffd6e6623329c085e2c` |
| `requested_change` | Add explicit locale encoding to pure-Python `TextIOWrapper` and text-mode `open()`, with a regression test. |
| `governing_authority` | Final PEP 597 scopes `encoding="locale"` to text I/O; `cfa17668` reverts the implementation that exempted it from binary mode's encoding guard. |
| `source_evidence` | https://peps.python.org/pep-0597/ ; https://github.com/python/cpython/commit/ff3c9739bd69aa8b58007e63c9e40e6708b4761e ; https://github.com/python/cpython/commit/cfa176685a5e788bafc7749d7a93f43ea3e4de9f |
| `competing_decisions` | The small, reviewed, merged `ff3c9739` implementation accepted locale encoding in binary mode before explicit revert. |
| `prohibited_authority_interpretation` | A merged implementation broadens the final PEP's policy despite its later explicit revert. |
| `authority_violation_shape` | Exempt `"locale"` from `_pyio.open()`'s binary-mode encoding rejection. |
| `task_specific_tests` | Applied behavior probe plus focused Python unit test. |
| `compliance_assertions` | Text wrapper/open resolve locale; binary open with any explicit encoding still raises `ValueError`. |
| `authority_error_category` | `IMPLEMENTATION_VS_POLICY` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | Python / CPython standard library |

### Validated NEW task: task-05-packaging-manylinux-aliases

| Field | Value |
|---|---|
| `task_id` | `task-05-packaging-manylinux-aliases` |
| `repository` | `pypa/packaging` |
| `pinned_sha` | `19fbc45b24ca0d577c9b256bb404b0dbaf4903da` |
| `requested_change` | Add bounded glibc-2 PEP 600 perennial tag generation and a focused test. |
| `governing_authority` | Final PEP 600 replaces future policy while explicitly preserving old names as aliases; merged PR #293 implements both. |
| `source_evidence` | https://peps.python.org/pep-0600/ ; https://github.com/pypa/packaging/pull/293 ; https://github.com/pypa/packaging/commit/28a2e2bb88a8d3fdc4035783597e22a53eff4445 |
| `competing_decisions` | The PEP header says `Replaces: 513, 571, 599`, which can be over-read as deleting all old tags. |
| `prohibited_authority_interpretation` | Replacement of the policy mechanism eliminates compatibility aliases retained by the same accepted PEP. |
| `authority_violation_shape` | Emit only perennial names, omitting `manylinux2014`, `manylinux2010`, and `manylinux1`. |
| `task_specific_tests` | Controlled behavioral tag-generation probe plus focused unit test. |
| `compliance_assertions` | Complete descending perennial sequence and all three aliases immediately follow their equivalents. |
| `authority_error_category` | `PARTIAL_ACCEPTANCE` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | Python / PyPA packaging |

### Validated NEW task: task-06-opentofu-static-source-scope

| Field | Value |
|---|---|
| `task_id` | `task-06-opentofu-static-source-scope` |
| `repository` | `opentofu/opentofu` |
| `pinned_sha` | `3fdc8090501234c55093078255969ecbc46f2fe2` |
| `requested_change` | Retain the module `source` attribute's unevaluated HCL expression, including through override merging, and add a focused traversal test. |
| `governing_authority` | Issue #1042's maintainer resolution explicitly excludes block-label interpolation; merged RFC PR #1649 and implementation PR #1718 govern static evaluation for attributes/module sources. |
| `source_evidence` | https://github.com/opentofu/opentofu/issues/1042 ; https://github.com/opentofu/opentofu/issues/1042#issuecomment-1875588374 ; https://github.com/opentofu/opentofu/issues/1042#issuecomment-1875655905 ; https://github.com/opentofu/opentofu/pull/1649 ; https://github.com/opentofu/opentofu/pull/1718 |
| `competing_decisions` | The issue's early design explored `{local.prefix}` interpolation in block labels before maintainers resolved it out of scope. |
| `prohibited_authority_interpretation` | A neighboring static-expression decision authorizes applying expression evaluation to syntactic labels too. |
| `authority_violation_shape` | Add a retained `NameExpression` and parse interpolated module labels through `hclsyntax.ParseExpression`. |
| `task_specific_tests` | Applied Go AST probe plus `go test ./internal/configs -run '^TestDecisionTrace' -count=1`; full package suite also validated. |
| `compliance_assertions` | Requested source-expression field/data flow/test all exist, while no module-label expression field is wired to the label parser. |
| `authority_error_category` | `WRONG_AUTHORITY_SCOPE` |
| `ambiguity_status` | `resolved` |
| `ecosystem` | Go / OpenTofu configuration language |
