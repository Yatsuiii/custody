# Fleet idea tournament

Date: 2026-08-12

Lane: agentic developer tooling.

Artifact: a falsification-first comparison of Fortified Enterprise Fleet ideas.
This note does not authorize a pivot or widen the session contract.

## Decision rule

A challenger replaces Custody only if it:

1. has a measurable triggering event and a current Google platform gap;
2. maps naturally to discovery, runtime and state, security, and observability;
3. produces a decisive live proof in four minutes;
4. can reach an offline acceptance proof within one day and a live Google proof
   by 2026-08-20; and
5. beats Custody by at least five points on a 100-point risk-adjusted score.

The risk adjustment includes existing evidence, code reuse, required new cloud
integrations, and unverified correctness claims. The raw score follows the
official 40/30/30 judging weights. Scores below are estimates, not judge
predictions.

## Tournament

| Candidate | One-line invariant | Raw ceiling | Proof debt | Risk-adjusted estimate | Decision |
| --- | --- | ---: | --- | ---: | --- |
| Custody | Untrusted-origin content never enters memory, and descendants of a later-compromised tool can be removed. | 93 | G1 and G5 live proof | 89 | Incumbent |
| Revision-aware Custody | Every memory is bound to the exact tool revision that produced it; unapproved changes are blocked and compromised revisions are surgically revoked. | 96 | Reproduce drift, prove live mismatch, extend lineage | 88 | One-day challenge |
| Chain of Authority | Every cross-agent action proves a non-escalating authority chain back to the initiating user. | 97 | New authorization core, A2A propagation, revocation, live enforcement | 81 | Hold |
| Effect Ledger | An ambiguous external action is reconciled before any retry can repeat it. | 96 | New execution core, target reconciliation, live failure injection | 80 | Kill as a pivot |
| Purpose-bound Context | Data keeps its allowed purpose, region, and retention constraints through every agent handoff. | 95 | Label source, propagation semantics, policy engine, compliance proof | 77 | Kill for this deadline |
| Agent canary rollout | A regressing agent revision is stopped before it reaches the fleet. | 91 | Traffic split, eval design, rollback, cloud deployment | 78 | Kill as mostly platform assembly |

## Evidence that changed the ranking

### Revision-aware Custody

Google Agent Registry does not automatically introspect MCP servers. A changed
tool specification must be uploaded manually, and the uploaded content replaces
the previous definition. This creates a current gap between a catalogued tool
surface and the surface an agent can meet at runtime.

Source: [Google Cloud, Manage MCP servers and tools](https://docs.cloud.google.com/agent-registry/manage-mcp-tools?hl=en)

Drift detection alone is not novel. Existing packages already pin tool-schema
fingerprints, and recent systems attest tool-server admission. The narrower
Custody opportunity is the connection drift tools do not prove: exact tool
revision to downstream agent memory and action blast radius.

Prior art checked:

- [ai-tool-guard MCP drift detection](https://ai-tool-guard.readthedocs.io/en/latest/guides/mcp-drift-detection/)
- [Attested Tool-Server Admission](https://arxiv.org/abs/2605.24248)
- [OWASP MCP03 Tool Poisoning](https://owasp.org/www-project-mcp-top-10/2025/MCP03-2025%E2%80%93Tool-Poisoning)

The repository's current 97 percent tool-surface-change claim is not admissible
for this decision until its dataset and computation are reproduced from a saved
artifact. The current external measurement is directionally supportive, not a
replacement for that missing lineage.

### Chain of Authority

Google Agent Identity authenticates an agent and supports acting on behalf of an
end user. The A2A specification supports delegation, but states that granular
authorization is specific to the implementation. That leaves a real boundary
between proving who called and proving that every delegation hop retained the
root principal's allowed scope.

Sources:

- [Google Cloud, Agent Identity overview](https://docs.cloud.google.com/iam/docs/agent-identity-overview?hl=en)
- [A2A enterprise authorization guidance](https://github.com/a2aproject/A2A/blob/main/docs/topics/enterprise-ready.md)

This is the strongest clean-sheet concept on track fit. It does not currently
beat Custody because it needs a new correctness-critical authorization kernel and
has no measured enterprise incident frequency in this record.

### Effect Ledger

The failure is real. ADK resumability is best-effort and at-least-once around an
interrupted unit, so side-effecting tools still need an idempotency contract.
However, effect-ledger packages and current research already target this exact
idea. Its demo ceiling is high, but novelty and reuse are too low to justify a
pivot now.

Sources:

- [ADK workflow resumability](https://github.com/google/adk-python/blob/7c715423927a454f12b5a995b0843d8f68b06ef1/.agents/skills/adk-architecture/references/architecture/workflow-resumability.md)
- [agent-ledger package](https://pypi.org/project/agent-ledger/)

### Agent canary rollout

Google's current tools already compare agent evaluations, expose runtime
revisions, and support deployment canaries. Combining them may be useful, but it
looks more like platform assembly than a new systems invariant.

Sources:

- [Google agents-cli evaluation guide](https://google.github.io/agents-cli/guide/evaluation/)
- [Google Cloud Deploy canary rollouts](https://docs.cloud.google.com/deploy/docs/deployment-strategies/manage-rollout)

## Surviving experiment

The only challenger authorized for a one-day falsification spike is
revision-aware Custody. No production code or contract wording changes until the
spike passes.

### Hypothesis

Binding Custody provenance to an approved Agent Registry tool revision produces
a clearer Fleet demo and stronger current problem evidence without replacing the
existing graph, write gate, revocation path, or department isolation.

### One changed variable

Replace source tool identity with source tool plus an immutable tool-spec digest.
Do not add content classification, autonomous trust decisions, a dashboard, or a
new memory store.

### Acceptance gates

1. A saved fixture contains an approved tool specification and a changed live
   `tools/list` response with a different canonical digest.
2. The negative control admits the changed surface because its registry entry is
   stale.
3. The governed path refuses the changed surface before tool output reaches an
   agent or memory.
4. Revoking one approved revision removes all and only records descended from
   that revision across at least three derivation hops.
5. The full breach, detection, containment, and preserved-good-state story fits
   in 150 seconds, leaving 90 seconds for architecture and live Google proof.

### Kill conditions

Kill the challenger and return to current Custody if any of these occurs:

- Agent Gateway or Registry already provides live specification attestation and
  revision-specific downstream lineage.
- Canonicalizing the live tool surface cannot be deterministic.
- Revision identity requires replacing the existing graph or memory adapter.
- The negative control cannot reproduce a stale-registry mismatch.
- The spike does not pass all five gates in one working day.

## Spike result, 2026-08-12

Verdict: valid, all five offline gates passed.

Baseline: a Registry snapshot identifies `fetch_page` as an approved tool and
does not inspect its later live surface.

Changed variable: each server-qualified tool is bound to a canonical digest of
its `tools/list` definition.

Result: `make revision-spike` generated
`proof-out/revision-spike.json` with five PASS results. The changed definition
was different from the approved digest; the stale baseline still bound the
runtime name; the governed path raised before dispatch; revision-specific
revocation removed `old-root`, `sales`, `support`, and `finance`, while
preserving `new-root` and `unrelated`; and the decisive demo sequence totals 150
seconds.

Decision: Custody pivots to revision-aware Custody. The session contract was
rewritten accordingly.

## Live result, 2026-08-13

Verdict: the stale-Registry attack and application-side mismatch block are live.

`make live-registry-attack` deployed v1 and v2 FastMCP surfaces to two Cloud Run
revisions at one URL, registered the exact live v1 schema in Agent Registry,
left it unchanged during the v2 deploy, and showed the negative control invoke
v2 while Custody refused before its dispatch counter moved. `make
registry-gates` independently recomputed both revision digests and passed eight
checks. The graph roots are bound to hashes of the real v1 and v2 call results,
and revision-specific traversal removes only the v1 descendants.

Remaining evidence: `RevisionCatalog` and `CustodyGraph` are still in-memory,
the revocation did not delete live Memory Bank resources, and Agent Gateway is
not yet in the call path. A surface read and later allowed dispatch are not
cryptographically atomic, so a revision-attested server or Gateway must close
that time-of-check/time-of-use gap before the absolute enforcement contract is
shippable. Behavior-only drift with an identical `tools/list` is outside this
mechanism's claim.
