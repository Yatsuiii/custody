Objective: E0/E1/E2 complete and frozen (commit 31bd1b0 on
research/e0-e1-multiparent-lineage). This phase, E2A: run ONE external
attack (TMA-NM's tool_echo construction) against UNCHANGED current
Custody, through a translation-layer adapter outside production code.
Measure PASS/FAIL. Do not fix, defend against, or otherwise modify
Custody's security semantics after seeing the result. No trust epochs, no
Custody 2.0, no OpenRouter/LLM calls.

Branch: research/e2a-tmanm-tool-echo
Parent: research/e0-e1-multiparent-lineage @ 31bd1b03c544a3fd2626491c5596694586cf3416
        (frozen E0/E1/E2 commit), which sits on
        research/memory-poisoning-thesis, which sits on
        hardening/fleet-track-pre-submission
        (the hackathon/shipping branch — MUST NOT be modified by this work).

Allowed files:
- research/experiments/E2A_TMANM_TOOL_ECHO/PLAN.md
- research/experiments/E2A_TMANM_TOOL_ECHO/ADAPTER_SPEC.md
- research/experiments/E2A_TMANM_TOOL_ECHO/RESULT.md
- research/experiments/E2A_TMANM_TOOL_ECHO/WHY_TRACE.md
- research/experiments/E2A_TMANM_TOOL_ECHO/attack.py (the adapter script;
  imports custody.* read-only, never edits it)
- research/CURRENT_CUSTODY_REDTEAM.md (update case F only, with measured result)
- research/EXPERIMENT_REGISTRY.md (update/add E2A row only)
- research/RESEARCH_VERDICT.md (append E2A outcome only)
- research/NOVELTY_MATRIX.md (only if the empirical result changes a claim)
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/ (production code stays byte-identical
  to the frozen E0/E1 commit for the entire duration of this experiment).
- No defense implementation, no semantic Custody change, regardless of
  what the attack shows — characterize the failure, do not fix it.
- No trust epochs, no Custody 2.0, no new benchmark beyond this one
  adapted scenario.
- No OpenRouter/LLM calls — this experiment is explicitly scoped to not
  need one (Custody's own decision path is deterministic).
- Do not hard-code the adapter/test to force a predetermined outcome; the
  attack construction must be built first, then run once, unmodified.
- No commit/push unless explicitly authorized.

Baseline: E0/E1/E2 frozen at commit 31bd1b0. `python -m unittest discover
tests` = 381/381 before this phase and must remain 381/381 after it (no
production code touched).

Acceptance gates:
1. TMA-NM's tool_echo semantics documented from the pinned repo's actual
   source (`code/laundering.py`), quoted, not paraphrased from memory of
   the earlier E2 pass.
2. The adapter translates TMA-NM's tool_echo item into a real ADK-shaped
   event sequence and runs it through real, unmodified
   `custody.origin.take_custody` / `custody.graph.CustodyGraph` /
   `custody.action.ExportGateway` — not a parallel toy reimplementation.
3. All three required states (Control 1 benign-trusted, Control 2
   untrusted-malicious, Attack trusted-tool-echo) actually executed, with
   real captured output, before any interpretation is written.
4. Success criterion (authority laundered = admitted AND action-authorized
   with the same standing a genuine trusted value would have) defined in
   PLAN.md before attack.py is run, not adjusted after seeing output.
5. WHY_TRACE.md shows the full decision chain (event -> origin
   classification -> trust lookup -> record -> admission -> action
   decision) for the attack case, distinguishing correct defense from
   accidental blocking from laundering.
6. Final verdict is exactly one of EXTERNAL-FAIL / EXTERNAL-PASS-CORRECT /
   EXTERNAL-PASS-ACCIDENTAL / ADAPTER-INVALID.

Verification: `attack.py`'s actual stdout is captured verbatim into
RESULT.md/WHY_TRACE.md; `git diff` against the frozen E0/E1 commit shows
zero changes under custody/; `python -m unittest discover tests` reports
381/381 after this phase, confirming no production drift.

Status: complete. E2A verdict: EXTERNAL-FAIL. TMA-NM's real tool_echo
attack, transcribed from the pinned repo, laundered authority through
current Custody's ExportGateway with no denial. Why-trace attributes it
to origin.py:325 (trust.of(runtime_name), payload never inspected). Zero
production code touched (git diff --stat custody/ empty); 381/381 suite
unchanged before and after. No defense implemented. Uncommitted pending
user review.
