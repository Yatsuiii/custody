Objective: Materialize only the inert GitHub-side setup precommitted by the
external-validity preregistration, and record its immutable identifiers before
any receiver, runner, relay, source delivery, or consequential action exists.

Lane: evidence-gated agent action systems.

Branch: research/external-validity-github-issue-prereg-20260826
Parent: docs/p7-final-handoff-20260825-01 @
        ca54d84e077d0a5584f79edec6ef54c4629ce61b

Artifact:
- research/external_validity/github_issue_action/WORLD_FREEZE.json

Allowed files:
- .claude/SESSION_CONTRACT.md
- research/external_validity/github_issue_action/WORLD_FREEZE.json

Frozen inputs:
- Preregistration commit 7ae6cceb40e30fe7b467a9f759e39bd589100968,
  independently verified from a fresh clone before live setup.
- P7 result commit 4194d3245fd72cee08089f339d21654aebb03bf7.
- Existing Gate 1/1B/1C and Gate 2 artifacts remain immutable.
- Production code, P7 harnesses, tests, and prior evidence remain immutable.

Non-goals:
- No runner, adapter, server, queue, schema, or production implementation.
- No source, relay, attack, remediation, or control issue comment.
- No issue close/reopen, webhook delivery, model call, Firestore call, or P7
  rerun.
- No receiver deployment, webhook endpoint activation, relay workflow, case
  manifest, incident interval, experimental secret, or experiment execution.
- No PAT or overprivileged identity may substitute for either preregistered
  GitHub App.
- No change to B7 semantics, no B8, and no reinterpretation of P7.
- No secret material in repository files, command output, or the freeze
  artifact.

Authorized external mutations:
- Create one dedicated private GitHub repository owned by Yatsuiii, with Issues
  enabled and unnecessary collaboration surfaces disabled.
- Create one inert, open target issue whose body identifies it as setup-only.
- Create two private, repository-scoped GitHub Apps if the available GitHub
  interface supports exact least-privilege registration: ingress has Issues
  read plus only `issue_comment`; action has Issues write and no webhook event.
- Install each App only on the dedicated sandbox repository. App installation
  tokens and webhook secrets must remain outside the repository and output.

Acceptance gates:
1. Verify the preregistration remote commit and content digest before the first
   live mutation.
2. Record the repository numeric ID, node ID, owner numeric/node IDs, privacy,
   Issues setting, URL, and creation timestamp from GitHub readback.
3. Record an open issue's numeric ID, node ID, number, URL, state, creator ID,
   and absence of a pull-request marker from GitHub readback.
4. Record separately verified ingress/action App IDs, installation IDs,
   repository selection, permissions, and event subscription only if GitHub
   actually exposes and confirms them. Otherwise record null identifiers and a
   concrete `SETUP-PARTIAL-BLOCKED` reason; do not approximate the boundary.
5. Pin REST API version 2026-03-10 and keep all execution-dependent fields
   explicitly null/pending. Validate JSON and scan it for secret-like material.
6. Commit and push only the two allowed paths, then independently verify the
   remote commit and WORLD_FREEZE digest.

Verification:
- GitHub API readback for every live resource and permission available here.
- `jq` schema/invariant checks plus secret-key/value scans.
- Staged-diff inspection limited to the two allowed paths; protected code diff
  remains content-empty.
- Fresh-clone remote commit and artifact-digest verification.

Status: complete_with_blockers
