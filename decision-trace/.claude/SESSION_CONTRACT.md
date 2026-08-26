Objective: the prior extraction-capability session closed with a substantive
7/7 GOVERNING one-shot holdout for extractor v2 (verified this session: root
cause documented, disjoint dev corpus, pre-registered dev gate passed,
frozen-before-read holdout, quote-verified). This session finishes the
remaining Phase 0-8 harness plumbing for the preregistered 63-run
action-compliance falsifier (Arm C context freeze, Arm B summary freeze,
coding backend freeze, blind run plan, dry run, sanity replay, final
manifest) and STOPS before Phase 9. Phase 9 (executing the 63 real
coding-agent runs) requires a SEPARATE explicit user go-ahead in this same
session before it starts, regardless of gate outcomes — it is real API
spend/compute against external services and this contract does not
preauthorize it.

Lane: optimization / research engineering.

Branch: research/decisiontrace-action-compliance
Parent: 0983bdcfe5db4e16df05b70691bc6530779efe61 (HEAD at session start)

v1/v2 extraction closure record (frozen, read-only for this session):
- Frozen v1 extractor: `app/ingest.py::extract_bundle_decisions`, produced
  0/7 `NO_GOVERNING_DECISION` (documented failure, not repaired in place).
- Frozen v2 extractor: `app/action_compliance_extraction_v2.py`, hash-frozen
  in `ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt` BEFORE the seven-task
  holdout was read. One-shot holdout (`ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt`,
  `data/action_compliance/holdout_v2_runs/`): 7/7 `GOVERNING`, 0 wrong,
  0 unresolved, matching human ground truth.
- Both extractors and their outputs are CLOSED for this session: not edited,
  not re-run, not repaired.

Allowed files (this session may only touch these; anything else is scope
drift):
- `.claude/SESSION_CONTRACT.md` (this file)
- `ACTION_COMPLIANCE_RUN_PROTOCOL.md` (existing — correcting the Arm C
  context-size table and documenting the Arm-C-proof-source fix only; no
  design changes to arms, backend, run count, or GO gate)
- `ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL.md` (new — Phase 8 consolidation doc)
- `ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_SHA256.txt` (new — consolidated
  checksum manifest)
- `scripts/create_action_compliance_final_manifest.py` (new)
- `data/action_compliance/contexts/C/**` (rebuild only — swapping the proof
  source from the failed v1 `bundle_runs/` output to the frozen v2
  `holdout_v2_runs/` output via the existing, unmodified
  `scripts/assemble_action_compliance_context.py`; Arm A and Arm B contexts
  are not touched)

Explicitly NOT touched, this session: `app/authority.py` (frozen resolver),
`app/ingest.py`, `app/action_compliance_extraction_v2.py` (frozen
extractors), `app/bundle_source.py`, `app/action_compliance_context.py`
(frozen context-assembly logic — only its CLI invocation is re-run, not its
code), any `TASK.md`, sanity patch, grader, `ACTION_COMPLIANCE_LEDGER.md`,
`ACTION_COMPLIANCE_GRADING.md`, or human ground truth for the seven tasks,
`data/action_compliance/contexts/A/**` and `.../B/**`, and
`explore/decision-trace-v0` / production.

Non-goals:
- No Phase 9 execution (the 63 real coding-agent runs) without a separate,
  explicit user go-ahead given after this contract's gates are reported —
  not implied by this contract, not implied by gate-pass alone, and not
  triggered by the task brief's own "don't ask again" instruction.
- No reading of the seven tasks' human ground truth (`governing_authority`,
  violation category, sanity-patch content) beyond what Phase 7's sanity
  replay already validates mechanically.
- No modification of the resolver, either extractor, or their frozen
  outputs.
- No git commit/push unless the user explicitly asks.

Baseline (run before any Phase 1-8 work; all passed this session):
- `sha256sum -c ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt` — PASS.
- `sha256sum -c ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt` — PASS.
- `sha256sum -c ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt` — PASS.
- `sha256sum -c ACTION_COMPLIANCE_INVENTORY_SHA256.txt` — PASS.
- `python3 scripts/verify_authority_freeze.py` — PASS (9/9 frozen files).
- `git diff 9bdec25..HEAD -- app/authority.py` — empty (resolver unchanged
  since frozen production merge).
- `git diff explore/decision-trace-v0 origin/explore/decision-trace-v0` —
  empty (production branch unchanged).

Acceptance gates:
1. Arm C's materialized context uses the v2 holdout `GOVERNING` proofs, not
   the v1 `NO_GOVERNING_DECISION` proofs — verified per-task after rebuild.
2. `scripts/verify_action_compliance_contexts.py` reports
   `A/B/C_RAW_PREFIX_EQUAL=true` for all seven tasks after the Arm C rebuild.
3. `ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_SHA256.txt` covers the full package
   (bundles, contexts, summaries, both extractors, dev corpus, holdout
   outputs, run protocol docs, run plan, sanity replay) and verifies clean.
4. Sanity replay evidence (existing or freshly run) shows all 7 compliant
   patches `TASK_COMPLETED=true, TESTS_PASS=true, AUTHORITY_COMPLIANT=true`
   and all 7 violating patches `TASK_COMPLETED=true, AUTHORITY_COMPLIANT=false`.
5. This contract, `ACTION_COMPLIANCE_RUN_PROTOCOL.md`, and
   `ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL.md` together are internally
   consistent about what is frozen and what still requires Phase 9
   authorization — no gate silently implies Phase 9 is authorized.

Verification: final status report to the user enumerating Phase 0-8 results,
the Arm C defect found and fixed, checksum verification results, and an
explicit request for go/no-go on Phase 9 before any coding-agent run
executes.

Completion record (Phase 0-8):
- Arm C was rebuilt from `data/action_compliance/holdout_v2_runs`; the
  context verifier reports `all_equal=true` for all 7 tasks.
- The consolidated 191-file manifest verifies clean, and the 9-file
  authority freeze remains clean.
- The condition-blind dry run planned all 63 rows, called no coding agent,
  and verified opaque IDs, separated condition mapping, cleanup, and cached
  patch capture.
- Sanity replay evidence contains 7/7 compliant rows with
  `TASK_COMPLETED=true`, `TESTS_PASS=true`, `AUTHORITY_COMPLIANT=true`, and
  7/7 violating rows with `TASK_COMPLETED=true`, `AUTHORITY_COMPLIANT=false`.
- Targeted Phase 0-8 tests pass. The full app test command is not a valid
  offline gate here because live Vertex/Firestore tests require external
  services; the first such Vertex query remains bounded but unavailable in
  this sandbox.
- Phase 9 was not executed. It remains separately gated because it spends
  real external API/compute budget.

Status: complete through Phase 8; Phase 9 pending separate authorization
