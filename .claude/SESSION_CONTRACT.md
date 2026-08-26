Objective: Write one standalone, docs-only external-validity preregistration
that tests frozen B7 against a real independently operated source producer and
a real reversible consequential endpoint before any runner is built.

Lane: evidence-gated agent action systems.

Branch: research/external-validity-github-issue-prereg-20260826
Parent: docs/p7-final-handoff-20260825-01 @
        ca54d84e077d0a5584f79edec6ef54c4629ce61b

Artifact:
- research/external_validity/github_issue_action/PREREGISTRATION.md

Allowed files:
- .claude/SESSION_CONTRACT.md
- research/external_validity/github_issue_action/PREREGISTRATION.md

Frozen inputs:
- P7 result commit 4194d3245fd72cee08089f339d21654aebb03bf7.
- Existing Gate 1/1B/1C and Gate 2 artifacts remain immutable.
- Production code, P7 harnesses, tests, and prior evidence remain immutable.

Non-goals:
- No runner, adapter, server, queue, schema, or production implementation.
- No GitHub repository, GitHub App, webhook, issue, token, or secret creation.
- No external write, API mutation, model call, Firestore call, or P7 rerun.
- No change to B7 semantics, no B8, and no reinterpretation of P7.
- No claim that a preregistration itself establishes external validity.

Acceptance gates:
1. Freeze GitHub.com signed issue-comment webhooks as the real producer and an
   open-to-closed issue transition in a dedicated sandbox repository as the
   sole consequential endpoint, with reopening as mandatory compensation.
2. Compare only the security layer while holding the exact webhook deliveries,
   action request, endpoint, issue pre-state, order, and timing schedule fixed.
3. Include the strongest simple baseline: signature verification plus an exact
   repository/sender/action allowlist and delivery-id replay ledger.
4. Precommit safety, benign utility, replay/idempotency, recovery, and privacy
   gates plus explicit KILL/CAUTION/INVALID/BLOCKED rules.
5. Define artifact lineage, scorer separation, external identifiers that must
   be pinned before execution, and the exact additional authorization required
   to build or run anything.
6. Verify the new document contains no placeholder success claim and that the
   only content diffs are the two allowed documentation files.

Verification:
- Read-through against current official GitHub webhook and REST API docs.
- `rg` checks for required sections, metrics, baselines, and authorization.
- `git diff --numstat` limited to the two allowed paths; protected code diff
  remains content-empty.

Status: complete
