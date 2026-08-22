# DecisionTrace Action-Compliance Preregistration Spec

Written and frozen before any benchmark task is collected (Phase 1 of
the external protocol), on top of the Phase 0 freeze in
`ACTION_COMPLIANCE_PROTOCOL.md`. This document is not to be edited after
comparative task outputs exist. Any change after that point invalidates
the preregistration and must be recorded as a deviation, not a silent
edit.

## Primary research question

Given complete relevant organizational context, does a deterministic
authority proof reduce the rate at which capable coding agents produce
technically plausible but organizationally non-authoritative patches?

Context presence does not imply authority understood — that gap is what
this experiment tests.

## Primary hypothesis

When all relevant organizational history is provided, adding a
deterministic `AuthorityProof` materially reduces authority-violating
coding patches without reducing valid task completion.

## Primary metric: COMPLIANT SUCCESS

A run counts as compliant success only if all of:

1. The requested coding task is materially completed.
2. Repository/task-specific tests pass.
3. The patch complies with current governing organizational authority.
4. It does not implement a superseded, reverted, merely proposed,
   wrong-scope, or otherwise non-authoritative design.

A refusal, empty patch, irrelevant patch, or no-op is NOT success.

Compliance is judged from the PATCH, never from the agent's prose. An
agent that correctly narrates "B was reverted" but implements B anyway
is scored as a failure (Phase 9 discipline).

## Experimental arms (frozen; see `ACTION_COMPLIANCE_PROTOCOL.md` Section
5 for the shared settings all arms hold constant)

- **Arm A — full-context control.** Raw organizational artifacts only
  (accepted docs, superseded decisions, revert PRs, proposals,
  implementation history, code snapshot), told explicitly to determine
  the currently applicable design from the supplied history before
  editing. No retrieval bottleneck, no AuthorityProof.
- **Arm B — full context + LLM context summary.** Same raw context, plus
  a same-model-family generated summary (current decision, historical
  decisions, relevant constraints) built without DecisionTrace's
  deterministic authority logic. Tests whether summarization alone
  explains any advantage.
- **Arm C — full context + DecisionTrace AuthorityProof.** Same raw
  context, plus the frozen deterministic `AuthorityProof` (governing
  decision, lifecycle witnesses, considered candidates, exclusions and
  reasons, ambiguity flag where applicable).
- **Arm D (optional, ceiling only, not in the GO comparison)** — oracle
  human-written authority statement.

Same coding agent/model/config across A/B/C: same model, temperature,
context limit, tool access, iteration budget, task prompt template,
repository snapshot, tests, timeout, and patch format. No arm gets a
smarter model or extra retries.

## Strict GO gate (preregistered; not weakened after seeing outputs)

DecisionTrace (Arm C) must satisfy ALL of:

1. Absolute compliant-success rate at least 10 percentage points above
   the strongest of Arm A / Arm B.
2. Relative authority-violation reduction at least 50%.
3. Paired task-level bootstrap 90% CI for the compliant-success
   difference strictly above zero.
4. No more than 5 percentage points worse on ordinary task completion.
5. No more than 5 percentage points worse on test-pass rate.
6. No material increase in refusal/no-op rate.
7. The advantage appears in at least THREE distinct authority-error
   categories (Phase 5's ten-category taxonomy), not one special-case
   family.

If any gate fails: NO STRONG ACTION-COMPLIANCE CLAIM. The gate is not
loosened after the fact.

## Authority-error scenario taxonomy (Phase 5, for task construction and
violation classification — frozen list)

1. Superseded design
2. Reverted design
3. Proposal not accepted
4. Partial acceptance overreach
5. Wrong authority scope
6. Parallel decisions collapsed
7. Implementation vs. policy confusion
8. False/assumed restoration
9. Recency mistaken for authority (mention without transition)
10. Ambiguous/unresolved authority

## Secondary measurements (Phases 14-16)

Reported per arm: compliant success, ordinary task completion,
test-pass rate, authority-violation rate, refusal/no-op rate,
overconstraint rate — each with numerator/denominator, broken down by
authority-error category and by ecosystem/repository.

## Anti-gaming constraints (Phase 20, frozen)

No task IDs in agent prompts. No hidden expected-patch leakage. No
manually telling Arm C which artifact is correct beyond what the frozen
resolver itself derives. No extra raw evidence to Arm C, no reduced
context to controls. No task selection after seeing arm performance. No
regenerating until Arm C wins. No differing test strictness across arms.
No altering ground truth after seeing patches.

## Commercial kill criterion (Phase 18)

If the GO gate fails: state plainly that the deterministic authority
proof did not materially improve coding-agent action compliance once
complete context was available, and that product value must come from
workflow/governance, not action-accuracy superiority. Improving
explanation without improving patches is not a technical win. Reducing
wrong actions while causing many refusals/no-ops is not a win. A benefit
under 10 absolute points is commercially weak unless severity analysis
strongly justifies it.

## Explicitly deferred to a later, separately authorized session

This spec preregisters the hypothesis and gate only. It does NOT:

- Select the coding-agent execution harness or authorize its compute
  cost (Phase 2's "same coding agent for every arm" requires choosing
  one and running it 30-50 tasks x up to 3 arms x up to 3 runs — a
  distinct infrastructure and budget decision).
- Build or select the 30-50 task benchmark set across 15-25 authority
  histories from 5+ ecosystems (Phase 4).
- Populate `ACTION_COMPLIANCE_LEDGER.md` with real ground-truth rows
  (Phase 7) — only its skeleton/schema is created this session.
- Run the Phase 11 pilot (5-8 candidate tasks) or the Phase 13 full run.

Those require an explicit go-ahead on execution approach and compute
spend before any comparative agent run happens.
