Objective: Apply and freeze a pre-treatment public-sandbox amendment that fixes
the actor-authority confound discovered in the original private personal-account
setup, while preserving every experimental treatment and scoring rule.

Lane: evidence-gated agent action systems.

Branch: research/external-validity-github-issue-prereg-20260826
Parent: docs/p7-final-handoff-20260825-01 @
        ca54d84e077d0a5584f79edec6ef54c4629ce61b

Artifact:
- research/external_validity/github_issue_action/AMENDMENT_1_PUBLIC_SANDBOX.md
- research/external_validity/github_issue_action/WORLD_FREEZE.json

Allowed files:
- .claude/SESSION_CONTRACT.md
- research/external_validity/github_issue_action/AMENDMENT_1_PUBLIC_SANDBOX.md
- research/external_validity/github_issue_action/WORLD_FREEZE.json

Frozen inputs:
- Preregistration commit 7ae6cceb40e30fe7b467a9f759e39bd589100968,
  independently verified from a fresh clone before live setup.
- Existing setup snapshot commit 745ff46f1d8d3571618e0babbe3879a967be2e91.
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
- Change only the existing empty sandbox repository 1347005783 from private to
  public after the amendment is committed and independently verified.
- Preserve the existing inert, open target issue and its immutable ID/number.
- Create two private, repository-scoped GitHub Apps if the available GitHub
  interface supports exact least-privilege registration: ingress has Issues
  read plus only `issue_comment`; action has Issues write and no webhook event.
- Install each App only on the dedicated sandbox repository. App installation
  tokens and webhook secrets must remain outside the repository and output.

Acceptance gates:
1. Freeze the amendment before changing GitHub visibility; preserve the
   original preregistration commit and digest as immutable lineage.
2. Change no variable except repository visibility/access: public synthetic
   issue comments replace private-collaborator source comments.
3. Record the repository numeric ID, node ID, owner numeric/node IDs, public
   visibility, Issues setting, URL, and creation timestamp from GitHub
   readback; verify the empty repository contains no code or secrets.
4. Record an open issue's numeric ID, node ID, number, URL, state, creator ID,
   and absence of a pull-request marker from GitHub readback.
5. Verify the distinct red-team account is not a collaborator and is not the
   issue creator; it must have no endpoint mutation authority.
6. Record separately verified ingress/action App IDs, installation IDs,
   repository selection, permissions, and event subscription only if GitHub
   actually exposes and confirms them. Otherwise record null identifiers and a
   concrete `SETUP-PARTIAL-BLOCKED` reason; do not approximate the boundary.
7. Pin REST API version 2026-03-10 and keep all execution-dependent fields
   explicitly null/pending. Validate JSON and scan it for secret-like material.
8. Commit and push only the three allowed paths, then independently verify the
   remote commit and WORLD_FREEZE digest.

Verification:
- GitHub API readback for every live resource and permission available here.
- `jq` schema/invariant checks plus secret-key/value scans.
- Staged-diff inspection limited to the two allowed paths; protected code diff
  remains content-empty.
- Fresh-clone remote commit and artifact-digest verification.

Status: in_progress_public_sandbox_amendment
