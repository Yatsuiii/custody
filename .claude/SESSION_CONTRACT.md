Objective: configure a least-privilege signed GitHub ingress receiver, freeze
the live execution substrate, and run the preregistered B_RULE baseline on the
public external-validity sandbox without claiming external validity.

Lane: evidence-gated agentic developer tooling.

Branch: research/external-validity-github-issue-execution-20260826
Parent: ea684b1 (setup-only world freeze with distinct actor and App readbacks)

Artifact:
- research/external_validity/github_issue_action/WORLD_FREEZE.json
- research/external_validity/github_issue_action/RAW_DELIVERIES.manifest.json
- research/external_validity/github_issue_action/RESULT.json
- research/external_validity/github_issue_action/COMPENSATION.json
- research/external_validity/github_issue_action/RESULT.md
- a reviewable receiver/runner implementation under
  research/external_validity/github_issue_action/

Allowed files:
- .claude/SESSION_CONTRACT.md
- research/external_validity/github_issue_action/**

Frozen inputs:
- Preregistration and public-amendment commits/digests recorded in the parent
  WORLD_FREEZE.json.
- P7 evidence commit 4194d3245fd72cee08089f339d21654aebb03bf7.
- Repository ID 1347005783 and target issue ID 5254158748.
- World owner ID 155452778; red-team actor ID 191570034.
- Ingress App ID 4725929 / installation 156728027; action App ID 4723384 /
  installation 156746789; selected repository is exactly 1347005783.
- The preregistration, case set, endpoint, metrics, thresholds, and kill rules
  are immutable. No P7 or production module edits are permitted.

Non-goals:
- No private key, webhook secret, installation token, OAuth token, raw
  signature, or other credential in Git, output, screenshots, or artifacts.
- No use of a PAT, connected GitHub app, or owner account as a substitute for
  the action App or ingress App.
- No runner-generated source/attack comments; source production remains with
  the owner and red-team accounts only.
- No treatment before all execution fields and the case manifest are pushed,
  fresh-clone verified, and the target has an open precondition.

Acceptance gates:
1. Receiver verifies HMAC over exact raw bytes before JSON parsing, enforces
   immutable event/install/repository/issue/actor allowlists, durably records a
   delivery GUID exactly once, and has a replay/uncertain-write test.
2. Ingress App webhook is active at the isolated receiver and the freeze records
   only its immutable hook ID; secrets and keys remain outside Git and output.
3. Relay commit, runner commit, case-manifest SHA-256, incident interval,
   receiver URL, and raw-delivery store are nonblank in WORLD_FREEZE.json and
   verified from a clean remote clone before first treatment.
4. B_RULE is run with the frozen eight-case set, no scorer labels in treatment,
   <=28 PATCH and <=100 read ceilings, mandatory compensation/readback, and a
   generated result table.
5. Any missing delivery, uncertain endpoint precondition, failed compensation,
   ceiling exhaustion, or unauthorized close stops the run and preserves a
   BLOCKED/KILL artifact; external validity remains unclaimed.

Credential boundary:
The operator may place App private keys in local paths and provision the
receiver secret through a secret manager or process environment. The runner
must consume only scoped installation tokens created in memory and must redact
all credential-bearing errors. If keys, a durable inbox, or a reachable HTTPS
receiver are unavailable, execution is BLOCKED rather than approximated.

Current status: preflight in progress; no live treatment has run.
