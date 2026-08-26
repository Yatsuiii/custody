Objective: P7 concluded with a valid PASS on p7/b7-live-20260825-run06
(LOCAL-EQUIVALENCE-SUPPORTED, real Firestore, real processes). Write one
comprehensive handoff document for a fresh Codex session (or any fresh
session/tool) to pick up from here with zero prior context: the full
evidence trail from the reconciliation audit through the final PASS, every
branch/SHA needed to verify any claim independently, what is authorized
and what is not, and the concrete next research phase (external validity),
per the standing rule that a valid PASS means stop modifying the internal
architecture. Documentation only.

Branch: docs/p7-final-handoff-20260825-01
Parent: p7/b7-live-20260825-run06 @ 4194d3245fd72cee08089f339d21654aebb03bf7
        (final P7 evidence; frozen harness and all probe/evidence branches
        MUST NOT be modified or moved by this work)

Allowed files:
- research/production_b7/P7_CODEX_HANDOFF.md
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to scripts/p7_run.py, any probe script, custody/*, or
  tests/test_b7_production_equivalence.py.
- No further real-Firestore execution of any kind in this session.
- No new branch other than this docs branch.
- Every SHA, branch name, and metric quoted in the handoff must be copied
  from this session's actual verified output (git log, the frozen result
  JSON files), not retyped from memory.

Baseline: N/A -- documentation only; `git diff --stat custody/ tests/
scripts/` empty is the only relevant no-drift check.

Acceptance gates:
1. The handoff lets a reader with zero prior context reconstruct, without
   re-deriving: the reconciliation-audit finding, the frozen P7 harness
   lineage (run01 through run06), every barrier-probe result (01 through
   04) and what each found, the casep-lifecycle-validation branches from
   the other session, and the final run06 PASS with its exact metrics and
   two honest caveats (recovery-bound miss, resource-ceiling miss).
2. States explicitly what remains not authorized (rerunning P7 under any
   spent identity, reopening the barrier work, modifying the B7 security
   model) and what the standing rule requires next (external validity
   phase, not another internal gate, not a B8).
3. Includes a complete branch/SHA reference table sufficient to run every
   verification command (git log, git diff --stat, digest checks) without
   needing to re-discover branch names via git archaeology.
4. Carries forward the evidence-gate discipline (session contract required
   before edits, freeze-by-commit-and-push before execution, no unlimited
   retry loops) since Codex operates under the same global operating policy.

Verification: read-through against this session's actual git log/JSON
output for exact-copy accuracy; `git diff --stat custody/ tests/ scripts/`
empty.

Status: active
