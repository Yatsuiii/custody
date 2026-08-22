Objective: E0/E1/E2/E2A/E2B/E2C complete and frozen (commit 040c28c on
research/e2c-exact-vs-transformed-retrieval). This phase is mechanism
DESIGN ONLY: derive the minimum architecture that could satisfy the nine
security invariants forced by the measured failures (I1-I9), compare at
least three candidate architectures, define an authority algebra, a
transformation model, a tool-relay model, a dynamic-trust/interval-
revocation model, repair semantics, an explicit trusted-computing-base
boundary, and a preregistered falsifier — as design documents only. No
production code. No implementation. Render exactly one MECHANISM DECISION
(DESIGN-READY / DESIGN-CAUTION / DESIGN-PIVOT / DESIGN-KILL).

Branch: research/design-mechanism-v0
Parent: research/e2c-exact-vs-transformed-retrieval @ 040c28c36d10a6c89144a19e01b0eae77a88ec64
        (frozen E0-E2C commit chain), which sits on
        research/memory-poisoning-thesis, which sits on
        hardening/fleet-track-pre-submission
        (the hackathon/shipping branch — MUST NOT be modified by this work).

Allowed files:
- research/design/REQUIREMENTS_FROM_FAILURES.md
- research/design/MECHANISM_CANDIDATES.md
- research/design/TMA_NM_RELATIONSHIP.md
- research/design/AUTHORITY_MODEL.md
- research/design/TRANSFORMATION_MODEL.md
- research/design/TOOL_RELAY_MODEL.md
- research/design/DYNAMIC_TRUST_MODEL.md
- research/design/REPAIR_SEMANTICS.md
- research/design/TRUSTED_COMPUTING_BASE.md
- research/design/DESIGN_FALSIFIER.md
- research/design/MECHANISM_DECISION.md
- research/RESEARCH_QUESTION.md (append/refine only)
- research/THREAT_MODEL.md (append/refine only)
- research/HYPOTHESES.md (append/refine only)
- research/EXPERIMENT_REGISTRY.md (add next-falsifier row only)
- research/RESEARCH_VERDICT.md (append design-phase outcome only)
- .claude/SESSION_CONTRACT.md

Non-goals:
- No edit to any file under custody/, tests/, live/, scripts/, web/ — this
  phase produces no code, only design documents.
- No claim of novelty and no claim of "solves memory poisoning" anywhere
  in these documents — every claim must be phrased as a hypothesis to
  test, not a conclusion, per the user's explicit instruction.
- Do not adopt TMA-NM's mechanism, or any other candidate, without first
  showing the measured failures force it and a simpler alternative was
  considered and rejected with reasons.
- Do not implement the chosen falsifier — design and preregister its
  gates only.
- No commit/push unless explicitly authorized.

Baseline: E0-E2C frozen through commit 040c28c. `python -m unittest
discover tests` = 381/381, must remain unchanged since no code is touched
in this phase — verified once at the end as a no-drift check.

Acceptance gates:
1. Every proposed primitive in REQUIREMENTS_FROM_FAILURES.md is traced to
   a specific measured result (E0/E1/E2A/E2B/E2C) and a specific invariant
   (I1-I9), with a "could a simpler mechanism satisfy this" check answered
   explicitly, not skipped.
2. MECHANISM_CANDIDATES.md compares at least three genuinely different
   architectures against the full evaluation list (11 attack/property
   rows + assumptions/TCB), with stated reasons, not scores alone.
3. AUTHORITY_MODEL.md gives a deterministic (not hand-waved) rule for
   Authority(M) given parents P1..Pn, covering every case the user listed
   (untrusted parent, trusted parent, independent corroboration,
   correlated corroboration, action-type-dependent authority).
4. TRANSFORMATION_MODEL.md addresses every hostile question the user
   posed (undeclared context, huge retrieval, hallucination, incomplete
   attribution, weak contribution, memory+fresh-tool mixing) with an
   explicit fallback, not silence.
5. TOOL_RELAY_MODEL.md states the trusted-computing-base assumption
   honestly if arbitrary tools cannot supply trustworthy upstream
   provenance, rather than inventing provenance that cannot exist.
6. DESIGN_FALSIFIER.md's PASS/CAUTION/KILL gates are fixed in that
   document before any implementation is authorized, and cover all six
   required scenario elements (tool echo, benign paraphrase, malicious
   paraphrase, multi-parent synthesis, later compromise, unaffected
   sibling).
7. MECHANISM_DECISION.md renders exactly one of the four allowed verdicts
   with reasoning tied to the acceptance gates above, and does not use
   the words "novel" or "solves memory poisoning" as conclusions.

Verification: manual read-through for internal consistency (no claim in
MECHANISM_DECISION.md exceeds what AUTHORITY_MODEL.md/TRANSFORMATION_
MODEL.md/TOOL_RELAY_MODEL.md actually specify); `git diff --stat custody/
tests/` empty; `python -m unittest discover tests` still 381/381 at the
end, confirming no code drift occurred during a docs-only phase.

Status: complete. Mechanism verdict: DESIGN-CAUTION. Eleven design documents
completed under research/design/, with all seven document acceptance gates
checked. Architecture A is specified for an isolated E2D falsifier only;
production remains architecturally unshippable until context-id capture,
authoritative timestamps, atomic publication, current-generation action checks,
and crash/retry recovery are proved. No production code or falsifier
implementation was written. `git diff --stat custody/ tests/` is empty and
`.venv/bin/python -m unittest discover tests` reports 381/381. Uncommitted
pending user review.
