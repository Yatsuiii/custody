Objective: E0/E1/E2/E2A/E2B complete and frozen (E0-E2 at 31bd1b0, E2A at
c4d519b, E2B at cf2ac74). This phase, E2C: a mechanistic falsifier, not an
attack benchmark. Determine whether current Custody's cross-invocation
ancestry reconstruction is genuinely content-identity fragile — exact
retrieval preserves authority, any change (trivial or semantic) loses
it — by running one trusted root fact through four retrieval forms
(exact, trivial-format-change, semantic-paraphrase, unrelated) and tracing
the first code-path divergence. Reuse/confirm existing test coverage
before writing anything new. No defense design, no production edits.

Branch: research/e2c-exact-vs-transformed-retrieval
Parent: research/e2b-tmanm-summarize @ cf2ac74dbe3a0963d28dc6550787905e19e84494
        (frozen E0-E2B commit chain), which sits on
        research/memory-poisoning-thesis, which sits on
        hardening/fleet-track-pre-submission
        (the hackathon/shipping branch — MUST NOT be modified by this work).

Allowed files:
- research/experiments/E2C_EXACT_VS_TRANSFORMED/PLAN.md
- research/experiments/E2C_EXACT_VS_TRANSFORMED/RESULT.md
- research/experiments/E2C_EXACT_VS_TRANSFORMED/WHY_TRACE.md
- research/experiments/E2C_EXACT_VS_TRANSFORMED/attack.py
- research/EXPERIMENT_REGISTRY.md (add E2C row only)
- research/CURRENT_CUSTODY_REDTEAM.md (update case D/E only, with measured boundary)
- research/RESEARCH_VERDICT.md (append E2C outcome only)
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/ — production code stays byte-identical
  to the frozen E2B commit throughout.
- No embeddings, fuzzy matching, token overlap, LLM judgement, string
  normalization beyond what production Custody already does, or manual
  derived_from edges not produced by real runtime behavior.
- No defense implementation, no mechanism design, no Custody 2.0, no trust
  epochs, no TMA-NM-style authority — characterization only.
- Do not duplicate tests/test_graph.py::RetrievalIsAttributedAsACitation's
  exact-match coverage without first confirming what it already proves.
- No commit/push unless explicitly authorized.

Baseline: E0-E2B frozen through commit cf2ac74. `python -m unittest
discover tests` = 381/381 before this phase and must remain 381/381 after.

Acceptance gates:
1. tests/test_graph.py::RetrievalIsAttributedAsACitation inspected first
   and its actual coverage (scenario, invocation-boundary-crossing,
   byte-identity, trust/derived_from assertions, whether it reaches
   instruction_eligible()/ExportGateway) documented before any new code
   is written.
2. Cases A-D all run through real, unmodified take_custody/CustodyGraph/
   ExportGateway, one shared trusted root fact, one shared graph.
3. Every case reports resolve-hit, origin, trust, derived_from,
   instruction_eligible(), and ExportGateway decision separately.
4. WHY_TRACE.md identifies the first code-path line where Case A diverges
   from B/C.
5. Final verdict is exactly one of EXACT-MATCH-DEPENDENCY-CONFIRMED /
   -PARTIAL / HYPOTHESIS-REJECTED / EXISTING-TEST-SUFFICIENT.

Verification: `attack.py`'s actual stdout captured verbatim into
RESULT.md/WHY_TRACE.md; `git diff --stat custody/` empty; `python -m
unittest discover tests` reports 381/381 after this phase.

Status: complete. E2C verdict: EXACT-MATCH-DEPENDENCY-CONFIRMED. Existing
test RetrievalIsAttributedAsACitation reused as the Case A positive
control (proved, not re-derived). New harness confirmed Cases B (one
trailing period removed), C (paraphrase), D (unrelated) are byte-for-byte
identical in outcome - total ancestry loss via CustodyGraph.resolve's
SHA-256 exact-match miss, no partial-credit boundary. Zero production
code touched; 381/381 suite unchanged. No defense implemented, no
readiness judgment made. Uncommitted pending user review.
