# DecisionTrace action-compliance falsification experiment (Phase 0/1 setup)

Opened 2026-08-22.

Objective: Stand up the preregistered DecisionTrace action-compliance
falsification experiment (Phase 0 freeze + Phase 1 preregistration only
for this session). This is a research experiment, separate from and does
not modify the frozen product. Does NOT include running the full
30-50 task, 3-arm, 2-3-run comparative experiment yet — that requires a
separate explicit scope/compute authorization (execution harness choice,
OSS repo clone/access, coding-agent budget, cost approval).

Branch: research/decisiontrace-action-compliance

Parent: 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6 (tip of
explore/decision-trace-v0, the merged authority-proof product commit)

Allowed files:
- decision-trace/ACTION_COMPLIANCE_PROTOCOL.md (new)
- decision-trace/ACTION_COMPLIANCE_SPEC.md (new)
- decision-trace/ACTION_COMPLIANCE_LEDGER.md (new, skeleton only this
  session — task ledger rows are populated in the pilot/full-build phase,
  not this session)
- decision-trace/.claude/SESSION_CONTRACT.md
- .claude/SESSION_CONTRACT.md (this file)
- decision-trace/scripts/verify_authority_freeze.py (new, guard script)

Non-goals (explicit, this session):
- Do not modify explore/decision-trace-v0 or any production code/config.
- Do not modify app/authority.py, app/collaborate.py, app/ui.py, or any
  authority-resolution test file (frozen; hash-guarded, not edited).
- Do not deploy, touch production Firestore, or change demo behavior.
- Do not run the full comparative experiment (Phases 2-19 of the
  external protocol) this session.
- Do not build/select the 30-50 task benchmark set this session beyond
  documenting the construction protocol and a ledger skeleton.
- Do not touch Custody.
- Do not push to remote until explicitly authorized.

Baseline: `git log --oneline -1` on this branch is 9bdec25 (or a
descendant produced only by this session's own doc commits);
`sha256sum decision-trace/app/authority.py decision-trace/app/collaborate.py
decision-trace/app/ui.py` matches the values recorded in
ACTION_COMPLIANCE_PROTOCOL.md.

Acceptance gates:
1. research/decisiontrace-action-compliance exists, branched exactly
   from 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6, not pushed.
2. ACTION_COMPLIANCE_PROTOCOL.md records the frozen authority-resolver
   file hashes, frozen experimental settings, and exists before any
   task discovery.
3. ACTION_COMPLIANCE_SPEC.md preregisters the primary hypothesis,
   compliant-success metric, and the strict GO gate, unedited after
   this session (future edits require a new session-contract entry).
4. scripts/verify_authority_freeze.py exits nonzero if any frozen
   file's hash changes.
5. Production branch explore/decision-trace-v0 is untouched (verified
   by diff).

Verification: `git diff origin/explore/decision-trace-v0 -- decision-trace/app`
shows no changes; `python decision-trace/scripts/verify_authority_freeze.py`
exits 0; `git merge-base --is-ancestor 9bdec25e9a9e3aee157e5f73b2c78e690fc343e6 HEAD`
exits 0.

Status: complete (Phase 0/1 only — protocol/spec/ledger-skeleton/guard
script written and verified; see result below)

Result: `ACTION_COMPLIANCE_PROTOCOL.md`, `ACTION_COMPLIANCE_SPEC.md`,
`ACTION_COMPLIANCE_LEDGER.md` (skeleton), and
`scripts/verify_authority_freeze.py` written on
`research/decisiontrace-action-compliance` (parent 9bdec25, verified via
`git merge-base --is-ancestor`). Guard script confirmed passing (9/9
frozen authority files match). `git diff origin/explore/decision-trace-v0
-- decision-trace/app` empty — production untouched. Nothing committed
or pushed. User chose to scope the next phase down to a Phase 11 pilot
(5-8 candidate tasks, 1-2 ecosystems) rather than jumping to the full
30-50 task / 360-run comparative experiment, which still needs a
separate execution-harness/compute decision.

## DecisionTrace action-compliance: Phase 11 pilot — machinery validation only (opened 2026-08-22, revised per user's detailed pilot spec same day)

Objective: NOT to estimate DecisionTrace's performance. Only to prove
the benchmark machinery itself is valid, per the user's explicit Phase
11 spec. Build 5-8 candidate coding tasks across 2-3 real OSS
ecosystems. For every task, before any comparative arm output exists,
require all 10 of: (1) pinned real commit; (2) real source-grounded
decision history; (3) authority distinction materially changes correct
code; (4) control receives ALL relevant context; (5) deterministic
task-completion tests; (6) deterministic/mechanical authority-compliance
checks; (7) a technically-valid-but-non-authoritative patch is actually
constructible; (8) task resets/replays reliably in an isolated worktree;
(9) no task-specific answer leaks into prompts; (10) ground truth
written and frozen before any arm runs. Diversity target: one
superseded-design, one reverted-design, one proposal-not-accepted, one
wrong/parallel-scope, one partial-acceptance-if-a-clean-example-exists.
Do NOT cherry-pick for DecisionTrace-favorable cases — actively try to
break the benchmark (reject tasks where the authority distinction
doesn't causally change the patch, where the grader can't mechanically
discriminate, where "all context" doesn't actually fit, or where the
control is artificially disadvantaged). For each surviving task, build
two hand-constructed sanity patches (A: compliant, B: authority-
violating-but-plausible) BEFORE any model run; the grader must accept A,
reject B, and score task correctness independently, or the task is
invalid. Only after sanity gates pass, run ONE coding-agent invocation
per arm per task (not 2-3) purely to validate execution plumbing — these
outputs are pilot-only and must never feed the final statistical result.

Branch: research/decisiontrace-action-compliance
Parent: HEAD (the Phase 0/1 freeze commit-state above, still
uncommitted)

Allowed files:
- decision-trace/ACTION_COMPLIANCE_LEDGER.md (populate pilot task rows)
- decision-trace/pilot/ (new — per-task pinned snapshots, source
  evidence, sanity patches A/B, grader scripts)
- decision-trace/data/action_compliance/pilot/ (new — pilot-only,
  explicitly separate from any future final-benchmark data path)
- decision-trace/data/runs_action_compliance_pilot/ (new — one-run-only
  pilot agent outputs, explicitly separate from final run data)
- decision-trace/.claude/SESSION_CONTRACT.md, .claude/SESSION_CONTRACT.md
- decision-trace/ACTION_COMPLIANCE_PILOT_REPORT.md (new — the 16-point
  report specified by the user, ending in a GO/REWORK/KILL
  recommendation for the harness, not for DecisionTrace itself)

Non-goals:
- Do not modify app/authority.py, app/collaborate.py, app/ui.py, or any
  frozen authority test file (still hash-guarded).
- Do not clone full multi-GB repositories where a shallow/sparse
  pinned-commit fetch suffices.
- Do not proceed to the full 30-50 task / 3-run comparative benchmark
  automatically — stop after the pilot report.
- Do not reuse pilot model outputs in any final benchmark result.
- Do not touch production or Custody.
- No commit/push without explicit authorization.

Baseline: scripts/verify_authority_freeze.py exits 0.

Acceptance gates:
1. 5-8 candidate tasks attempted across 2-3 ecosystems; each surviving
   task satisfies all 10 required properties above, verified not
   asserted.
2. Sanity patches A/B built and graded correctly (accept A, reject B,
   independent correctness score) before any model run, for every
   surviving task.
3. Exactly one run per arm per task, explicitly stored under the
   pilot-only data paths above.
4. ACTION_COMPLIANCE_PILOT_REPORT.md covers all 16 points the user
   specified (attempted/rejected/passed counts, ecosystems, scenario
   categories, sanity-patch discrimination result, timing, cost,
   reproducibility, isolation safety, grader ambiguity, leakage,
   tooling problems, backend recommendation, and cost projections for
   30/40/50 tasks x 3 arms x 3 runs), ending in one GO/REWORK/KILL call.
5. scripts/verify_authority_freeze.py still exits 0 at the end.

Verification: re-check every cited PR/commit/KEP link is real; confirm
task rejections are logged with reasons before any agent output existed
for that task; confirm pilot data never lands under a path implying
final-benchmark status.

Status: complete

Result: 1 task (`task-01-k8s-postfilter-victims`, REVERTED_DESIGN,
kubernetes/kubernetes) survived all 10 gates out of 9 candidates
investigated; 8 rejected with logged reasons (mostly rustc-bootstrap
infeasibility, thin evidence, bugfix-not-governance reverts). Sanity
patches A/B built and independently re-graded by me (not just trusted
from the construction agent): grader correctly discriminates
AUTHORITY_COMPLIANT=true/false. One run per arm (A/B/C) executed for
plumbing validation only, independently re-graded against fresh
worktrees, all three compliant/test-passing — descriptive only, no
statistical claim made (n=1). Full 16-point report written to
`ACTION_COMPLIANCE_PILOT_REPORT.md`, recommendation REWORK (harness
validated, task inventory far short of the diversity/count needed for
the preregistered GO gate). Nothing committed or pushed. User's
follow-up instruction: do NOT run more comparative arms yet; run a
task-discovery-only sweep instead (next entry).

## DecisionTrace action-compliance: large-scale task discovery sweep (opened 2026-08-22)

Objective: per the user's explicit follow-up spec, this session expands
TASK INVENTORY ONLY. Investigate at least 20-30 NEW candidate
histories/tasks across at least 5 ecosystems, targeting a minimum of 6
fully valid tasks (preferably 8-12) covering at least 5 of the 9 target
authority-error categories (missing so far: SUPERSEDED_DESIGN,
PROPOSAL_NOT_ACCEPTED, PARTIAL_ACCEPTANCE, WRONG_AUTHORITY_SCOPE,
PARALLEL_DECISIONS, IMPLEMENTATION_VS_POLICY, EXPLICIT_RESTORATION,
MENTION_WITHOUT_TRANSITION; have REVERTED_DESIGN already). Do not
over-fill with reverts — target no category above ~30% of the final set
if enough valid cases exist. Every candidate gets a ledger row
(including rejections, classified per the user's rejection taxonomy),
whether it survives or not. Every surviving candidate gets hand-built
compliant (A) and violating (B) sanity patches, graded by the frozen
mechanical grader, before being counted as valid. Strongly prefer tasks
where the violating patch ALSO passes ordinary functional tests (the
strongest DecisionTrace case: technically valid code that still
violates authority). Tighten the TASK_COMPLETED grading weakness found
in the pilot (identifier-in-comment false-positive risk) per task.

Branch: research/decisiontrace-action-compliance
Parent: HEAD (the Phase 11 pilot commit-state above, still uncommitted)

Allowed files:
- decision-trace/ACTION_COMPLIANCE_LEDGER.md (every candidate, valid or
  rejected, gets a row)
- decision-trace/pilot/task-<NN>-<slug>/ (new, one dir per surviving
  candidate — TASK.md, grader.py, worktree_setup.sh, sanity patches,
  context_bundle/)
- decision-trace/.claude/SESSION_CONTRACT.md, .claude/SESSION_CONTRACT.md
- decision-trace/ACTION_COMPLIANCE_TASK_DISCOVERY_REPORT.md (new — the
  30-point report the user specified, ending in one of GO/REWORK/KILL
  for the task inventory itself)

Non-goals (hard, explicit):
- DO NOT run Arm A, Arm B, or Arm C (or any comparative coding-agent
  invocation) at any point this session — no model-under-test output
  may exist while tasks are being selected, to prevent case selection
  bias. This is the single most important constraint of this session.
- Do NOT change ACTION_COMPLIANCE_PROTOCOL.md or ACTION_COMPLIANCE_SPEC.md
  (GO thresholds, arms, primary metric, fairness requirements) — frozen.
  If a genuine bug unrelated to outcomes is found in either, document it
  and ask, do not silently fix it.
- Do NOT modify app/authority.py, app/collaborate.py, app/ui.py, or any
  frozen authority test file (still hash-guarded).
- Do NOT touch production or Custody.
- Do NOT proceed to a full comparative run even if enough tasks survive
  — stop and report the inventory once the sweep is done.
- No commit/push without explicit authorization.

Baseline: scripts/verify_authority_freeze.py exits 0; existing
task-01 pilot task and its ledger row/data remain untouched (this
session adds new tasks, does not modify task-01's artifacts).

Acceptance gates:
1. At least 20 new candidates investigated across at least 5 ecosystems,
   every one logged in the ledger (valid or rejected, with rejection
   taxonomy code if rejected).
2. Structural gates G1-G10 (per the user's spec) verified, not asserted,
   for every candidate counted as valid.
3. Every valid candidate has hand-built sanity patches A/B, graded, with
   the required TASK_COMPLETED/TESTS_PASS/AUTHORITY_COMPLIANT pattern
   confirmed (A: all true; B: AUTHORITY_COMPLIANT false, ideally
   TASK_COMPLETED/TESTS_PASS still true).
4. ACTION_COMPLIANCE_TASK_DISCOVERY_REPORT.md covers all 30 points the
   user specified, ending in exactly one of: GO — TASK INVENTORY VALID /
   REWORK — MORE VALID TASKS REQUIRED / KILL — REAL AUTHORITY-SENSITIVE
   CODING TASKS TOO SCARCE, plus an explicit yes/no answer to "did we
   find enough real situations where the organizational decision
   changes what a coding agent should actually implement?"
5. scripts/verify_authority_freeze.py still exits 0 at the end; no Arm
   A/B/C output exists anywhere under this session's new files.

Verification: grep the entire session's new output for any coding-agent
patch/diff that isn't a hand-built sanity patch (there should be none);
re-check a sample of cited PR/RFC/proposal links are real; confirm
category/ecosystem distribution matches what's reported.

Status: active

---

# DecisionTrace: port authority-proof engine into the product

Opened 2026-08-22.

Objective: Product-integration session. Port the general authority-proof
architecture developed and validated on `research/decisiontrace-authority-
proof` (checkpoint `f417acf`, live-integration-verified at `96cc921`) into
the actual DecisionTrace product, without touching the frozen submission
branch. Minimum required product changes: scope-local authority semantics,
`partial_acceptance` support, deterministic `AuthorityProof` generation,
a Gemini explanation layer that narrates but never decides authority, and
Firestore persistence compatible with existing production records. Wire
this into the existing collaborative worker story (Evidence Scout ->
Lifecycle Resolver -> Provenance Challenger -> Gemini Reconciler) and the
smallest possible judge-facing UI addition. No new benchmark, no Custody
changes, no research dataset ported into the product, no application
rewrite beyond the authority path.

Branch: integration/decisiontrace-authority-proof
Parent: 1c33d3de169ebbdb874992e9383b632d163b2658
(`explore/decision-trace-v0`, the frozen hackathon submission — never
developed on directly, remains the rollback point)

Allowed files:
- `decision-trace/app/authority.py` (new — ported from research, port
  audit determines exact scope)
- `decision-trace/app/models.py` (edit — `partial_acceptance` field)
- `decision-trace/app/graph.py` (edit — structured `lifecycle_events`
  field, matching research)
- `decision-trace/app/store.py` (edit — round-trip fix for the new
  field, both JSON and Firestore paths)
- `decision-trace/app/collaborate.py` (edit — wire the authority
  resolver into the Lifecycle Resolver/Provenance Challenger/Gemini
  Reconciler worker story; add an authority-explanation path)
- `decision-trace/app/loader.py` (edit — assign `related_components` to
  loaded frozen-benchmark decisions; found during Phase 10 demo replay
  that the loader never set a scope at all, so `_resolve_authority_for_
  candidates` could never produce an `AuthorityProof` for any real demo
  decision. Minimal, deterministic scope derivation only — no new fields
  on the source JSONL, no re-mining)
- `decision-trace/app/memory.py` (edit — `propose_reconsideration`'s
  candidate must inherit the target decision's `related_components` so
  the reconsideration becomes a visible, correctly-excluded
  `PROPOSED_NOT_ACCEPTED` candidate in the target's own AuthorityProof,
  per Phase 7's reconsideration demo requirement; no change to
  `RECONSIDERS` not being a lifecycle edge, so governing truth is still
  unaffected)
- `decision-trace/app/ui.py` (edit — minimal "CURRENTLY GOVERNING / WHY
  THIS GOVERNS / View full authority proof" addition only, no redesign)
- `decision-trace/app/tests/**` (new/edit — port relevant adversarial +
  regression tests, add product-integration tests)
- `decision-trace/README.md` (edit — remove/replace any 76%-vs-57%-style
  superiority claim with the architectural positioning sentence)
- `decision-trace/.claude/SESSION_CONTRACT.md`, this file
- `decision-trace/PORT_PLAN.md` (new — Phase 2 audit/plan, written
  before any product code changes)
- `decision-trace/INTEGRATION_DECISION.md` or equivalent final-report doc
  (new, end of session)

Non-goals:
- No new benchmark, no new dataset, no rescoring, no prospective-
  superiority claim.
- Do not port benchmark data, prospective runs, research score files,
  failure-mining artifacts, research-only scripts, or old falsifier
  experiments from the research branch.
- Do not touch Custody.
- Do not develop directly on `explore/decision-trace-v0`.
- Do not merge this branch into the frozen product without explicit
  authorization (research/audit only this session; recommendation, not
  action).
- Do not replace the existing production Cloud Run deployment; a preview
  revision/service only, and only after local gates are green.
- Do not push unless explicitly authorized.
- Do not add product features unrelated to the authority-proof path.

Baseline: `git log -1 --format=%H` on this branch ==
`1c33d3de169ebbdb874992e9383b632d163b2658`; `app/authority.py` does not
exist on this branch pre-port (confirmed); `app/requirements.txt` here
matches the research branch's (google-genai, google-cloud-firestore,
numpy, streamlit, pytest) — confirmed byte-identical.

Acceptance gates:
1. `PORT_PLAN.md` written and the minimum-diff port scope decided before
   any product file is edited.
2. Ported authority engine passes an adversarial test suite (ported/
   adapted from research) covering scope-locality, proposal/supersession/
   revert/parallel-scope/partial-acceptance semantics.
3. `AuthorityProof` reaches the Gemini explanation layer without Gemini
   gaining any authority-deciding responsibility (tested).
4. Old 76%-vs-57% superiority claim removed from judge-facing product
   copy (README/UI), replaced with the architectural positioning
   sentence, not a new number.
5. Full product suite green under the correct `.venv` interpreter, real
   integrations exercised (Firestore, Gemini, GitHub), backward
   compatibility with pre-existing (no `partial_acceptance`) Firestore
   records proven without mutating production data.

Verification: `source .venv/bin/activate` (or `.venv/bin/python`
explicitly) for every test run; full suite count recorded; real
Firestore/Gemini/GitHub integration results recorded; local demo replay
of the delayed-preemption scenario; preview deployment (not production)
smoke-tested if reached.

Status: active

---

# Archived — closed, superseded by the entry above

# DecisionTrace: Gemma bonus integration — killed, documenting the decision

Updated 2026-08-17.

Objective: Gemma integration was attempted and killed (no budget, no free
path exists). Update `decision-trace/HANDOFF.md` and project memory to
record the finding accurately so a future session doesn't re-attempt it
without checking budget first, and confirm cleanup (deleted API key, no
leftover cost-bearing artifacts) is complete.

Branch: explore/decision-trace-v0
Parent: unchanged — Firestore/Cloud Run/submission-docs work from earlier
sessions this week, all still uncommitted.

Allowed files: `decision-trace/HANDOFF.md` (status update only), project
memory files under
`/home/Yatsuiii/.claude/projects/-run-media-Yatsuiii-Windows-SSD-custody-search-2/memory/`.
No app code — `vertex.py`, `ingest.py`, `test_ingest.py` are untouched by
the Gemma attempt and stay that way.

Non-goals: no edits to `BUILD_SCOPE.md`, `RESULTS.md`, `decisions.jsonl`,
or the frozen pipeline scripts; no touching `failure-mining/`,
`research-impact/`, `contribution-gate/`, `research-access/`, or
Custody's `feat/memory-provenance`; no new GCP credentials/spend; no
commit/push without explicit authorization.

Baseline: what was tried and found this session — Vertex AI: 404 on
every Gemma publisher-model path across 4 regions (self-host-only, real
GPU cost, not attempted). Gemini Developer API: enabled
`generativelanguage.googleapis.com`, created a scoped API key
(`decisiontrace-gemma-extraction`), confirmed real model names
(`gemma-4-26b-a4b-it`, `gemma-4-31b-it`) and that the key authenticated,
but every generation call failed `429: prepayment credits depleted`
(Gemma's own paid billing bucket, separate from Vertex). Web search
confirmed Gemma isn't on the Gemini API free tier (only Gemini 2.5
Flash/Flash-Lite are free). User has no budget. API key deleted
(`gcloud services api-keys delete`, confirmed via `deleteTime` in the
response); local `.env.gemma` removed; no code written; no cost
incurred.

Acceptance gates:
1. `decision-trace/HANDOFF.md` documents the Gemma kill decision (what
   was tried, why it failed, that cleanup is complete) so a future
   session has the finding, not just a stale "do this" line item.
2. Project memory (`decisiontrace_hackathon_rubric.md`) reflects the same
   finding, so it isn't re-suggested without checking budget/free-path
   status fresh.
3. `git status`/checksums confirm no falsifier file, and no app code
   file, was touched by this session.

Verification: read `HANDOFF.md` back to confirm the Gemma section is
accurate and doesn't overstate/understate what was actually tried.
Confirm via `gcloud services api-keys list` that no `decisiontrace-*` key
remains active in the project.

Status: active
