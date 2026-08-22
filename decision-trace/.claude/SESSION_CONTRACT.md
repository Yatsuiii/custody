Objective: discover and deeply validate a NEW DecisionTrace action-compliance
task inventory. Research only: no comparative Arm A/B/C runs, coding-agent
runs, production edits, deploys, pushes, Custody changes, or authority-resolver
changes.

Lane: optimization / research engineering.

Artifact: an evidence-backed, replayable inventory in
ACTION_COMPLIANCE_LEDGER.md plus per-task context, two human-authored sanity
patches, deterministic graders, captured results, and an explicit GO / REWORK /
KILL recommendation.

Starting branch: research/decisiontrace-action-compliance
Starting SHA: 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6
Salvage checkpoint: e94ba4a
Frozen production branch: explore/decision-trace-v0 (do not touch)

Baseline:
- Existing exposed pilot task task-01-k8s-postfilter-victims is a harness
  fixture only and is excluded from the new statistical inventory.
- The interrupted session left complete-looking Django and Go candidates,
  partial OpenTofu and Kubernetes candidates, and no Tokio artifact. None is
  accepted until independently replayed under the strengthened grader rule.

Hypothesis: among real coding tasks with complete history, current authority
changes the materially correct patch often enough to yield at least six NEW
replayable tasks across at least five categories and four ecosystems.

Acceptance gates:
1. Every accepted task passes G1-G10 with immutable source evidence and a
   bounded complete context bundle.
2. Every accepted task has two human-authored sanity patches; the compliant
   patch completes the task, passes feasible tests, and is authority-compliant,
   while the violating patch completes the task but is mechanically rejected
   for authority.
3. TASK_COMPLETED uses applied-state behavioral, semantic, AST, API-structure,
   or equivalent structural evidence. Identifier/comment/string presence alone
   is prohibited by ACTION_COMPLIANCE_GRADING.md.
4. At least 30 serious candidates are recorded before concluding scarcity.
   If fewer than six survive, stop without weakening gates.
5. Final inventory has >=6 NEW tasks, >=5 categories, >=4 ecosystems, replayed
   setup, clean leakage checks, and no category above roughly 30%.

Kill condition: after at least 30 serious candidates, fewer than six valid NEW
tasks means stop and report REWORK (3-5) or KILL (0-2) rather than force-fit
tasks.

Checkpoint rule: persist the ledger after about every five serious candidates
and after each completed ecosystem. Local research commits are allowed; never
push.

Status: active
