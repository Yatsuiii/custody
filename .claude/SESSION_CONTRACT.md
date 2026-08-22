Objective: E0/E1 (complete) plus E2 evidence-collection only. E2: determine
whether TMA-NM (arXiv:2606.24322) has a real, verifiable, reproducible
released implementation/benchmark, whether it runs, what laundering
attacks it actually implements in code (not just paper prose), and whether
it could feasibly be adapted to test current Custody — without building
that adapter, without spending money on LLM API calls, and without
starting any Custody 2.0 architecture, trust epochs, or new benchmark.

Branch: research/e0-e1-multiparent-lineage
Parent: research/memory-poisoning-thesis (docs-only research audit branch),
        which itself sits on hardening/fleet-track-pre-submission
        (the hackathon/shipping branch — MUST NOT be modified by this work).

Allowed files:
- research/experiments/E0_CURRENT_LINEAGE_REPRO/ (done, do not modify)
- research/experiments/E1_MULTIPARENT_LINEAGE/ (done, do not modify)
- research/experiments/E2_TMANM_REPRO/PLAN.md
- research/experiments/E2_TMANM_REPRO/SOURCE_AUDIT.md
- research/experiments/E2_TMANM_REPRO/REPRODUCTION.md
- research/experiments/E2_TMANM_REPRO/ATTACK_MATRIX.md
- research/experiments/E2_TMANM_REPRO/CUSTODY_ADAPTER_MAP.md
- research/experiments/E2_TMANM_REPRO/RESULT.md
- research/RELATED_WORK_AUDIT.md (append/correct TMA-NM section only)
- research/NOVELTY_MATRIX.md (append E2 findings only)
- research/EXPERIMENT_REGISTRY.md (update E2 row only)
- research/RESEARCH_VERDICT.md (append E2 outcome, do not rewrite prior sections)
- .claude/SESSION_CONTRACT.md
- External clone at $SCRATCHPAD/mem-inv-bench (outside the Custody tree,
  read-only reproduction target, not part of this repo)

Non-goals:
- No Custody 2.0 architecture, trust epochs, interval revocation, or any
  edit to custody/*.py, tests/*.py, live/, scripts/, web/.
- No new benchmark (that is a possible E4, gated on this experiment's own
  verdict, not started here).
- No spending money on LLM API calls (no OPENROUTER_API_KEY is configured;
  do not obtain or use one without explicit authorization). The offline,
  no-cost parts of the external repo may be run; anything requiring
  OpenRouter credentials is a documented BLOCKED item, not worked around.
- Do not modify the cloned external repository's code to make results look
  better; environment-only fixes must be logged with before/after, per the
  user's instruction, and none were needed here.
- No commit/push unless explicitly authorized.

Baseline: E0/E1 already complete (FOUNDATION-SURVIVES), 381/381 tests
passing, untouched by this phase.

Acceptance gates:
1. TMA-NM's exact primary-source metadata (title, author, date, version)
   independently confirmed via direct arXiv fetch, not inferred.
2. Official repository confirmed to exist via ground-truth GitHub API
   (`gh api`), not just an AI-summarized page fetch, and pinned to an
   exact commit SHA.
3. The smallest official, no-cost reproduction command actually executed
   and its real output recorded (PASS/PARTIAL/BLOCKED/FAIL).
4. All 10 attack classes (A-J) classified against the actual source code
   read, not paper prose, with file citations.
5. Adapter feasibility map answers all 8 questions per implemented attack,
   without building the adapter.
6. Final verdict is exactly one of EXTERNAL-HARNESS-READY/-PARTIAL/
   -BLOCKED/-ABSENT.

Verification: `gh api repos/yedidel/mem-inv-bench` output and `git log -1`
inside the clone confirm the pinned commit; reproduction commands' exact
stdout is quoted in REPRODUCTION.md; `git status` in the Custody repo
shows no changes outside the allowed list.

Status: complete. E2 verdict: EXTERNAL-HARNESS-PARTIAL. TMA-NM repo
verified real (ground-truth gh api), pinned at 63f1359d677e, offline
formal reproduction PASSED with no fix needed. LLM-backed empirical runs
BLOCKED (no OpenRouter key, no spend). 6/10 attack classes adaptable to
Custody as pure harness plumbing; D and J not present in TMA-NM. No
production code changed beyond E1's existing origin.py/test_origin.py
diff. Hackathon branch untouched.
