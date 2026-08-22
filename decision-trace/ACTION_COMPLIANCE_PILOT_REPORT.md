# DecisionTrace Action-Compliance: Phase 11 Pilot Report

Scope: machinery validation only, per the user's explicit framing — this
pilot does NOT estimate DecisionTrace's comparative performance. n=1
task, 1 run per arm. No statistical claim about Arm C beating Arm A/B is
made or supportable from this data, and none is claimed below.

## 1. Candidate tasks attempted

9 total: 1 kubernetes/kubernetes scheduler task carried through to
completion, plus 8 rejected candidates across kubernetes/kubernetes,
rust-lang/rust, and pypa/packaging (research agent details below).

## 2. Tasks rejected before agent outputs, and why

All 8 rejected before any comparative agent output existed (logged in
`ACTION_COMPLIANCE_LEDGER.md`, "Pilot exclusion log"):

1. rust-lang/rust PR #149375/revert #154930 (const-checks) — rustc
   bootstrap-from-source infeasible in-session (many GB, 30-90+ min);
   gates 5/8 (tests actually run, worktree actually replayable)
   couldn't be verified, only asserted.
2. rust-lang/rust PR #148937/revert #150096 (`BorrowedBuf`) — same
   rustc-bootstrap infeasibility.
3. kubernetes/kubernetes PR #127300/revert #128694 (kubelet
   `doPodResizeAction`) — `pkg/kubelet`'s transitive Go dependency graph
   (CRI, cgroups, runtimes) not verified buildable in the sparse pattern
   within budget.
4. kubernetes/kubernetes PR #140448/revert #140990 (client-go
   `EventBroadcaster`) — real, buildable, but the revert's stated reason
   is a test-race bugfix, not an organizational scope/design decision;
   fails requirement 3 in spirit (no real authority distinction, just
   normal code-review correctness).
5. kubernetes/kubernetes PR #137274 (`maxLength` stability revert) —
   real revert but a single enum change with no behavioral/generated-code
   difference; fails requirement 3 (authority distinction doesn't
   causally change code).
6. kubernetes/kubernetes PR #139008 (KEP-5832 PodGroup admission plugin
   full revert) — degenerates to "add nothing" vs. "re-add an entire
   plugin," not two comparably-sized plausible patches differing on one
   causal marker; also answerable correctly by an agent that never
   reasons about authority at all.
7. pypa/packaging PR #828 (PEP 639 License scope note) — real, but the
   only evidence is a single PR review comment, not a documented decision
   with competing alternatives; fails requirement 2 (thin evidence).
8. Broad kubernetes/kubernetes search for "closing this in favor of" /
   PROPOSAL_NOT_ACCEPTED candidates — no clean, code-substantial example
   surfaced within the time budget.

None were forced through to hit the 5-8 target. This is the single
biggest honest finding of this pilot — see point 15/16.

## 3. Tasks that passed all structural gates

1: `task-01-k8s-postfilter-victims` (kubernetes/kubernetes,
`REVERTED_DESIGN`). All 10 required properties verified (not asserted):
real pinned commit `9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e`; real,
`gh`-fetched PR text for both #136254 and #137662 plus the KEP it cites
(kubernetes/enhancements#5730, confirmed merged); the authority
distinction causally changes the correct patch (compliant vs. violating
sanity diffs differ on a specific, checkable marker); full context
bundle is ~180 lines, well within a small context budget; deterministic
Go tests exist and run; the grader mechanically discriminates compliance
from the diff alone; a technically-plausible-but-wrong patch (patch B)
was hand-constructed and confirmed to trigger the violation check;
`worktree_setup.sh` reruns cleanly (verified 5 times this session: 1
original build + 3 arm runs + 3 independent re-grades); no task ID or
grading assertion leaks into the agent-facing prompt; ground truth
(`TASK.md`, ledger row) was written and reviewed before any patch or
grader code was written.

## 4. Repositories / ecosystems

kubernetes/kubernetes only survived to a full task. rust-lang/rust and
pypa/packaging were investigated (real candidates found, real evidence
verified) but rejected on feasibility/evidence-thinness grounds before
construction completed — see point 2. **This pilot did not achieve
2-3 ecosystems as scoped**; it achieved 1 verified ecosystem plus 2
ecosystems' worth of rejected attempts. Flagged as a real gap, not
smoothed over.

## 5. Scenario category for each

`task-01`: `REVERTED_DESIGN`. The 8 rejected candidates spanned
`REVERTED_DESIGN` (5 of 8), one attempted `WRONG_SCOPE`-adjacent
bugfix-revert (rejected as not a real authority case), one attempted
scope-note case (rejected for thin evidence), and one attempted
`PROPOSAL_NOT_ACCEPTED` search that found nothing usable. No
`SUPERSEDED_DESIGN`, `PROPOSAL_NOT_ACCEPTED`, `WRONG_SCOPE`, or
`PARTIAL_ACCEPTANCE` task survived to completion this pilot — coverage
across categories, required by the full benchmark's GO gate condition 7
("advantage in >=3 distinct categories"), is currently 1 of 10
categories proven constructible.

## 6. Sanity-patch discrimination (task-01)

Confirmed correct, independently re-verified this session (not just
trusting the construction agent's self-report — re-ran the grader
myself against fresh worktrees):

```
PATCH A (compliant):   TASK_COMPLETED=True  TESTS_PASS=True  AUTHORITY_COMPLIANT=True
PATCH B (violating):   TASK_COMPLETED=True  TESTS_PASS=True  AUTHORITY_COMPLIANT=False
  (reason: diff modifies forbidden shared-interface file(s))
```

Clean discrimination on the one dimension that matters
(`AUTHORITY_COMPLIANT`), with `TASK_COMPLETED`/`TESTS_PASS` correctly
staying constant across both (both patches achieve the literal test
goal; only the mechanism differs) — this is exactly the shape a good
task should have.

One real weakness found and worth flagging for the full build: the
`TASK_COMPLETED` check currently matches on any added line containing a
`want*victim*`/`expect*victim*` identifier that isn't a bare
declaration/assignment — it would be satisfied by a **comment** mentioning
that identifier next to real usage, not just genuine assertion code. I
independently `grep`-verified all three arm patches contain real
`cmp.Diff(...)`-based assertions, not comment-only mentions, so this
didn't produce a false positive here, but the grader's `TASK_COMPLETED`
check should be tightened (require the identifier inside an `if`/`cmp.Diff`
call, not just "declared and read somewhere") before the full run.

## 7. Average clone/setup/reset time

Not cleanly isolated from total agent wall-clock this session (a real
instrumentation gap for the full run). Qualitatively: `worktree_setup.sh`
(sparse + blob-filtered fetch of ~30 staging modules for Go module
resolution, no full clone) completed within seconds to low tens of
seconds per invocation in my own centralized re-grading pass, run 3
times back-to-back. Resulting worktree size: ~168-195MB (not multi-GB).
Full end-to-end per-arm wall time (setup + read + edit + build + test,
see point 8) was 4.7-5.3 minutes; setup is a minority of that, most time
is spent in the agent's own read/edit/test iteration loop.

## 8. Average coding-agent runtime

Arm A: 316.2s (5.3 min), 33 tool calls, 96,338 tokens.
Arm B: 283.6s (4.7 min), 26 tool calls, 79,240 tokens.
Arm C: 303.2s (5.1 min), 35 tool calls, 84,297 tokens.
Mean: ~301s (5.0 min), ~31.3 tool calls, ~86,625 tokens per run.

Pilot task-construction agent (not a benchmark run — one-time harness
work): 1093.9s (18.2 min), 96 tool calls, 183,447 tokens.

## 9. Token/API cost per run

Reported in tokens (above), not dollars — this session runs under a
Claude Code subscription context, not metered per-token API billing, so
a dollar figure would need a separate lookup against current published
per-token API pricing for whatever model is chosen for the real
execution harness (Section 15). Order-of-magnitude planning number:
~85-96K tokens per single-arm run for this task's context size (~180-line
bundle). Larger/more complex tasks in the full 30-50 set should be
expected to cost more per run, not less.

## 10. Reproducible patch capture

Yes. All three arms independently ran `git diff` inside their isolated
worktree and wrote a clean unified diff to a fixed, pre-agreed path
(`data/runs_action_compliance_pilot/task-01-k8s-postfilter-victims/arm_{a,b,c}/patch.diff`).
All three diffs applied cleanly via `git apply` in my independent
re-grading pass (fresh worktree each time), confirming the capture
mechanism is reproducible, not just self-reported by the agent that
produced it.

## 11. Tests executing safely in isolated worktrees

Yes. Each arm worked in its own separate directory
(`arm_{a,b,c}_worktree` under the session scratchpad), no shared mutable
state between arms, `go test` ran against real package test suites with
no network/production access implied. My independent re-grading used
three additional fresh worktrees, entirely separate from the arms'
own, and got matching results — confirms isolation and determinism.

One friction point (not a safety issue): worktrees start in detached
HEAD, which trips this project's global evidence-gate pre-edit hook
(requires a named branch + `.claude/SESSION_CONTRACT.md`). Arm B's agent
worked around this by creating a local branch and a throwaway session
contract inside its own isolated worktree — harmless (doesn't touch the
pinned commit or any tracked file outside the two allowed files) but
should be handled by the harness itself for the full run (e.g.
pre-create a branch in `worktree_setup.sh`) rather than left to each
coding agent to improvise.

## 12. Grader ambiguity

One found (Section 6): `TASK_COMPLETED`'s identifier check could in
principle be satisfied by a comment rather than real usage. Otherwise no
ambiguity — `AUTHORITY_COMPLIANT`'s forbidden-file/forbidden-pattern
check is unambiguous and diff-only, no LLM judgment involved anywhere in
grading.

## 13. Prompt leakage

None found. The task prompt given to all three arms (verified — I wrote
these prompts myself, identical requested_change text across arms) never
names `task-01`, never states which PR is "correct," never quotes the
grader's forbidden-file/forbidden-pattern check. Arm C's additional
AuthorityProof block states the governing decision and exclusion
reason (exactly what the frozen resolver would produce for a real
product user) but does not name the specific grading assertion.

## 14. Runtime/tooling problems

- `gh` CLI (authenticated) worked reliably for all real PR/issue
  verification during task construction.
- Sparse + blob-filtered clones worked as designed — no full clones of
  kubernetes/kubernetes were done at any point.
- kubernetes' `go.work` multi-module layout meant even one scheduler
  subpackage required sparse-checking out ~30 `staging/src/k8s.io/*`
  modules for Go module resolution (not vendoring, not full history) —
  worth knowing for time-budgeting the full run, not a blocker (final
  worktree size stayed under 200MB, testable in seconds).
- The evidence-gate pre-edit hook friction in isolated worktrees
  (Section 11) should be designed around explicitly in the full harness.
- rustc's from-source bootstrap cost ruled out rust-lang/rust as a
  near-term ecosystem for this harness pattern entirely — any Rust task
  in the full benchmark needs either a prebuilt-toolchain strategy or
  tasks scoped to pure-Rust crates that don't require rebuilding rustc
  itself (e.g. a library crate with its own CI, not compiler internals).

## 15. Recommended coding-agent execution backend for the full run

Based on this pilot: the pattern used here — a fresh, isolated
general-purpose coding-agent invocation per arm per task, working in a
`worktree_setup.sh`-produced sparse/blob-filtered checkout, self-capturing
a `git diff`, graded centrally and independently afterward — worked
cleanly end to end for real Go code in a real large monorepo, with
reproducible capture and safe isolation. Recommend keeping this pattern
for the full run, with two concrete fixes: (1) pre-create a named branch
in `worktree_setup.sh` so agents don't need to work around the evidence
hook themselves; (2) tighten `TASK_COMPLETED` grading per-task to require
identifier usage inside a real conditional/comparison call, checked
per-task the way this pilot did by hand (Section 6), not assumed
reusable across tasks without re-verification.

## 16. Cost projections (token/time only — no dollar figure computed, see Section 9)

Using this pilot's single-task, single-arm averages (~301s runtime,
~86,625 tokens, ~31.3 tool calls per run) as a lower-bound proxy — real
tasks in the full 30-50 set will vary in size and some (larger
codebases, harder authority distinctions) will cost more:

| Scale | Total runs | Est. wall time (fully parallel) | Est. wall time (serial) | Est. total tokens |
|---|---:|---:|---:|---:|
| 30 tasks x 3 arms x 3 runs | 270 | ~5 min (bottlenecked by slowest run, if fully parallelized) | ~22.6 hours | ~23.4M |
| 40 tasks x 3 arms x 3 runs | 360 | ~5 min (same, if fully parallelized) | ~30.1 hours | ~31.2M |
| 50 tasks x 3 arms x 3 runs | 450 | ~5 min (same, if fully parallelized) | ~37.6 hours | ~39.0M |

Full parallelization across 270-450 simultaneous agent runs is unlikely
to be practical (rate limits, machine/orchestration limits, shared Go
module cache contention if run on one host) — real wall time will fall
somewhere between the fully-parallel and fully-serial figures depending
on how much concurrency the chosen execution backend actually supports.
This table should be treated as an order-of-magnitude planning input,
not a commitment, and should be re-derived once 2-3 more pilot tasks
from a second/third ecosystem exist (single-task-derived averages are a
thin basis for projecting a 30-50 task budget).

## GO / REWORK / KILL recommendation — for the HARNESS, not for DecisionTrace

**REWORK.** Not KILL: everything the pilot was actually built to prove —
isolated, resettable worktrees; reproducible patch capture; a grader
that mechanically and correctly discriminates a compliant patch from a
plausible-but-authority-violating one; clean context-bundle sizing; no
prompt leakage — worked, and worked cleanly, on the one task that made
it all the way through construction. Not GO: only 1 of the targeted 5-8
tasks survived, only 1 of the required diversity categories
(`REVERTED_DESIGN`) is proven constructible, and only 1 of the targeted
2-3 ecosystems produced a surviving task. A GO gate that requires
"advantage in >=3 distinct authority-error categories" cannot even be
attempted with the current task set. Before spending the compute for a
real 30-50 task run: build 4-7 more tasks specifically targeting the
missing categories (`SUPERSEDED_DESIGN`, `PROPOSAL_NOT_ACCEPTED`,
`WRONG_SCOPE`/`PARALLEL_DECISIONS`, and, if a clean real example exists,
`PARTIAL_ACCEPTANCE`), and add at least one more ecosystem where a full
build/test cycle is actually feasible without a multi-hour toolchain
bootstrap (kubernetes/kubernetes proved feasible; rust-lang/rust did
not, in its current from-source-bootstrap form). The mechanism is sound;
the task inventory is not yet close to sufficient to run the
preregistered GO gate meaningfully.

## Explicit answer to the standing question

At n=1, no statistically meaningful answer is possible, and none is
claimed. Descriptively, on this single task: all three arms (full
context; full context + self-written summary; full context +
AuthorityProof) independently avoided the authority violation and
produced a compliant, test-passing patch — none of the three reintroduced
the reverted `PostFilterResult.Victims` design. Arm C's own notes
(Section 4/`arm_c/agent_notes.md`) describe the AuthorityProof as
reframing the task from "is victim plumbing wanted at all" to "solve it
without touching the specifically reverted surface" — a plausible
mechanism for why a proof could help on harder cases, but this is one
data point where a capable model got it right unaided too, so it is not
evidence of a compliance-rate difference. That question needs the full
task set (or at minimum several more diverse tasks with real difficulty
variance) with 2-3 runs per arm, not this pilot.
