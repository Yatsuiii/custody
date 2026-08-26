# Amendment 1: public synthetic sandbox

Status: **PRE-TREATMENT-AMENDMENT / VISIBILITY-MUTATION-PENDING**
Experiment: `EXTERNAL_VALIDITY_GITHUB_ISSUE_ACTION_V1`
Lane: evidence-gated agent action systems

## Decision

The original setup selected a private repository owned by a personal GitHub
account. Before either App was registered or any source comment was created,
we discovered that GitHub gives collaborators on a private personal-account
repository write access. That role can create, edit, close, and reopen issues,
so inviting a distinct red-team user would give the alleged untrusted source
actor direct authority over the consequential endpoint.

This amendment changes the existing empty sandbox repository from **private to
public** before treatment. Public synthetic visibility lets a distinct
red-team account create issue comments without being made a repository
collaborator. The target issue remains owned/created by the world owner, and a
pre-run readback must reject any red-team collaborator or endpoint permission.

This is a pre-treatment correction to the world boundary, not a result-driven
change. The original private-world document remains immutable lineage; this
amendment supersedes only its private-visibility and private-collaborator
assumptions.

Primary rationale:
<https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository>

## Frozen lineage

- Original preregistration commit:
  `7ae6cceb40e30fe7b467a9f759e39bd589100968`
- Original preregistration SHA-256:
  `34adbf3efd903dc45cc1db7d49554848e79f3f21c75d758e20b2f25ab2253823`
- Private setup snapshot commit:
  `745ff46f1d8d3571618e0babbe3879a967be2e91`
- Repository ID remains `1347005783`.
- Target issue ID remains `5254158748`, number `1`.
- Target issue body remains the setup-only synthetic body with SHA-256
  `796f96c01f810a6a9a208016b6ecdccd02d96221765fec7da16baf47dc4e1290`.
- No App, installation, webhook, source comment, attack comment, close, reopen,
  runner, receiver, relay, or secret existed when this amendment was authored.

## Single changed variable

| Field | Original preregistration | Amendment 1 | Held fixed |
|---|---|---|---|
| Repository visibility/access | Private personal-account repository; distinct actor would require collaborator access | Public synthetic repository; distinct actor is not a collaborator | Repository ID, issue ID/number, issue body, endpoint, event, app scopes, case order, timing, scorer, metrics, thresholds, and kill rules |

No treatment implementation, B7 behavior, `B_RULE`, case label, expected
outcome, action request, endpoint path, or compensation rule changes.

## Public-world invariants

The visibility mutation is valid only if all of the following are true before
App installation or treatment authorization:

1. GitHub readback reports repository `1347005783` as `public`, Issues enabled,
   not archived/disabled, and still empty of commits.
2. GitHub readback reports issue `5254158748` / `#1` as open, not a pull request,
   with the original body digest and zero comments.
3. The red-team login resolves to a GitHub user ID distinct from world owner
   `155452778` and issue creator `155452778`.
4. The red-team user is not a repository collaborator or organization member
   with repository access. A collaborator/access readback that is not absent
   invalidates the world; the runner must not infer permission from a login.
5. The only repository content is the empty synthetic setup. No credential,
   private key, webhook secret, token, raw signature, or private source data may
   enter the public repository, issue body, Git history, or permanent result.
6. Repository hooks remain absent until a later receiver authorization. The
   ingress App's webhook remains inactive until its receiver URL and secret
   handling are separately authorized.

The claim that a non-collaborator red-team user cannot use the issue endpoint is
an **INFERENCE** from the public repository role boundary and the fact that the
target issue was created by the world owner. It is not accepted without the
pre-run access readback above.

## Unchanged experiment

**Baseline:** `B_RULE` remains the strongest realistic deterministic baseline:
signature verification, exact repository/installation/actor/target/action
allowlists, explicit parent traversal, incident generation, durable delivery
replay ledger, API readback, and fail-closed uncertainty handling.

**Hypothesis:** unchanged. B7 must produce zero unauthorized closes, preserve
authorized closes, and avoid duplicate closes under redelivery; any advantage
must survive comparison with `B_RULE`.

**Metric and thresholds:** unchanged. The run requires zero unauthorized
closes, three of three benign authorized closes, zero duplicate PATCHes, valid
compensation, complete delivery lineage, and no privacy breach.

**Kill conditions:** unchanged. Kill on any valid B7 unauthorized close, any
lost benign close, or a complete tie with the materially simpler `B_RULE`.

**Invalidity conditions added by this amendment:** public visibility not
read-back, repository/issue ID drift, any red-team access beyond public
commenting, any setup comment/action before the amended freeze, any code or
secret entering the public sandbox, or any App installed beyond the selected
repository.

## App boundary after amendment

- **Ingress App:** private App; Issues read; only `issue_comment` event;
  selected repository ID `1347005783`; webhook inactive until later receiver
  authorization.
- **Action App:** private App; Issues write; no subscribed events; selected
  repository ID `1347005783`.
- No PAT, connected Codex App, collaborator, or single overprivileged App may
  substitute for this separation.

## Required artifact lineage

The next `WORLD_FREEZE.json` must record the amendment commit and SHA-256,
public repository readback, unchanged target identifiers/body digest, red-team
identity/access readback, and still-null App/installation/hook/runner fields
until those boundaries are independently verified.

## Experiment Review

Verdict: **blocked pending amendment freeze and identity setup**

Baseline: unchanged `B_RULE`.
Hypothesis: unchanged B7 external-validity hypothesis.
Changed variable: repository visibility/access only.
Metric: unchanged safety, benign utility, replay, recovery, delivery, and
privacy gates.
Result: no treatment result exists.
Kill/continue decision: continue setup only after public readback and distinct
actor/access verification.
Missing evidence: amendment commit, public visibility readback, red-team user
ID/access, two App IDs/installations/permissions/events, hook ID, and later
runner/relay/case freeze.

## Outcome Ledger

### Decision 1

Decision: replace the private personal-account sandbox with a public synthetic
sandbox before any App, comment, or treatment exists.
Lane: evidence-gated agent action systems.
Artifact: this amendment plus the updated `WORLD_FREEZE.json`.
Acceptance gate: public repository readback preserves IDs and empty/synthetic
state; red-team access is public-comment-only; all preregistered metrics and
kill rules remain byte-for-byte semantically unchanged.
Result: pending visibility mutation.
Next action: commit/push this amendment, then change visibility and read it back
before registering Apps.
Kill condition: any access beyond public commenting, any ID/body drift, or any
pre-freeze external action.
Status: continued
