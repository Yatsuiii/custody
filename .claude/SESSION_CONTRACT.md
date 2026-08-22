# DecisionTrace: find the mechanism behind the falsifier's 76% plateau

Opened 2026-08-21.

Objective: Determine the actual root-cause mechanism of the 9 remaining
structured-condition failures in the DecisionTrace v0 falsifier (76% =
28/37 combined), by tracing each failure from live source section ->
ground-truth quote -> rationale_card -> retrieved points -> realized
prompt -> generated answer -> judge verdict. Then decide, on that
evidence alone, whether the `kep_alternatives` half of the benchmark is
measuring the system or mismeasuring it. If and only if the forensics
show the task itself is ill-posed (a broad "what alternatives were
considered" query graded against one arbitrarily-selected alternative
sentence), preregister a corrected V2 benchmark in writing BEFORE
generating any V2 answers, derive its cases by a uniform deterministic
rule, and run it end to end. The score is not allowed to select the
conclusion: if 76% is the real ceiling, that is the deliverable.

Branch: research/decisiontrace-plateau
Parent: 1c33d3d (`explore/decision-trace-v0`, the frozen submission
commit). The research branch is cut from exactly that commit and is
never merged back or deployed.

Allowed files:
- `decision-trace/BENCHMARK_FAILURE_AUDIT.md` (new — Phase 1 forensics)
- `decision-trace/BENCHMARK_V2_SPEC.md` (new — Phase 2 preregistration)
- `decision-trace/RESULTS_V2.md` (new — Phase 6 results)
- `decision-trace/data/v2/**` (new — V2 cases, separate from v0 data)
- `decision-trace/data/runs_v2/**` (new — V2 generations)
- new V2-only scripts under `decision-trace/`: `build_v2_cases.py`,
  `run_conditions_v2.py`, `grade_v2.py`, `test_no_leakage_v2.py`,
  `audit_v0_failures.py`
- `decision-trace/.claude/SESSION_CONTRACT.md` (project-local log entry)
- this file

Non-goals:
- No deploy, no Cloud Run revision change, no merge into
  `explore/decision-trace-v0` or any other branch, no push.
- No mutation of any v0 artifact: `RESULTS.md`, `data/decisions.jsonl`,
  `data/runs/**`, `mine_decisions.py`, `run_conditions.py`, `grade.py`,
  `test_no_leakage.py`, `rag_index.py`, `vertex.py` all stay byte-
  identical to 1c33d3d. V2 lives in new files only.
- No change to `verdict_for()`'s thresholds (structured >= 85%,
  rag <= 70%). They were preregistered and stay untouched whatever the
  V2 numbers turn out to be.
- No product/app code changes (`app/**`), even if the research finds an
  abstraction the product is missing — that would be a separate,
  separately-authorized session.
- No repeat of a closed lever: chunk size, embedding model, TOP_K, or
  retrieval granularity. The point-index experiment was a clean null;
  re-running it is scope drift, not evidence.
- Commit on `research/decisiontrace-plateau` IS authorized (the user
  asked for the resulting SHA). Push, merge, and deploy are NOT.

Baseline (run and record before editing anything):
- `git log -1 --format=%H` == `1c33d3de169ebbdb874992e9383b632d163b2658`
- `wc -l decision-trace/data/decisions.jsonl` == 37
- `python -m pytest test_no_leakage.py -q` — expected: all pass, offline
- `RESULTS.md` reports structured combined 76% (28/37), rag 57%,
  code_only 0%, structured revert_pair 94% (17/18), structured
  kep_alternatives 58% (11/19), verdict CAUTION.
- The 9 structured failures read off RESULTS.md's per-decision table are
  the rows scored `Cr`: elastic-elasticsearch-revert-147071, and 8 KEPs
  (storage-1979, auth-1205, auth-5681, api-machinery-3488,
  api-machinery-2523, node-5593, api-machinery-2876, node-6122).

Acceptance gates:
1. `BENCHMARK_FAILURE_AUDIT.md` exists and classifies all 9 structured
   failures and all 19 KEP rows with the required per-row columns, one
   named primary cause per failure from the fixed taxonomy
   (A INVALID_OR_MISALIGNED_GROUND_TRUTH / B CARD_COVERAGE_MISS /
   C RETRIEVAL_COVERAGE_MISS / D GENERATION_MISS / E JUDGE_MISS /
   F GENUINE_UNKNOWN), plus totals.
2. Every claim about what a KEP's `## Alternatives Considered` section
   contains is checked against the live source document, not inferred
   from the card or the quote. Where the live fetch is unavailable, the
   row says so rather than guessing.
3. If V2 is built at all: `BENCHMARK_V2_SPEC.md` is written and
   committed BEFORE the first V2 generation call; V2 cases are derived
   by one uniform structural rule fixed before any grading; and a
   structural dry run reports case count, source distribution,
   alternatives-per-KEP, and leakage results before any Vertex spend.
4. `test_no_leakage_v2.py` proves no V2 condition's prompt carries its
   own grading rationale, for every V2 case, and passes.
5. `git diff 1c33d3d --stat` at the end shows only new files plus the
   two contract files — zero modifications to v0 artifacts.

Verification:
- `git diff 1c33d3d --name-status` reviewed by hand for v0 mutations.
- `python -m pytest test_no_leakage.py test_no_leakage_v2.py -q`.
- `git stash list` still shows the parked
  `hardening/collaborative-pre-submission` work (42-row decisions.jsonl
  + its contract), unrestored and intact.
- Final report states numerator/denominator for every score and the
  verdict computed by the unchanged `verdict_for()`.

Status: complete

Result: the plateau was benchmark semantics. 7 of the 9 structured
failures are benchmark-label or task mismatch, 2 are card coverage, 0 are
retrieval, generation or judge noise as a primary cause. Two mining
defects proved and made reproducible. v2 re-posed the KEP arm as one
targeted question per named alternative (83 cases, 33 decisions,
preregistered). Its 99% turned out to be a bijective key lookup; v2.1
rebuilt the store by unsupervised ingestion and got 87%; v2.2 removed a
labelling handicap on RAG and RAG went to 89%. Final: rag_labelled 89%
(74/83), structured_ingested 87% (72/83), code_only 10% (8/83), verdict
CAUTION one point below KILL. The structured-versus-RAG advantage is not
demonstrated. v0 byte-identical, 456 leakage assertions passing, work
committed on `research/decisiontrace-plateau` through ddada00, nothing
merged, pushed or deployed.

---

# Archived — closed, superseded by the entry above

The entry below is the previous session's contract, kept verbatim for the
record. Its `Status: active` line is historical; the active contract for
this session is the one above.

# DecisionTrace: Gemma bonus integration — killed, documenting the decision

Updated 2026-08-17.

Objective: Gemma integration was attempted and killed (no budget, no free
path exists). Update `decision-trace/HANDOFF.md` and project memory to
record the finding accurately so a future session doesn't re-attempt it
without checking budget first, and confirm cleanup (deleted API key, no
leftover cost-bearing artifacts) is complete.

Branch: explore/decision-trace-v0
Parent: unchanged — Firestore/Cloud Run/submission-docs work from earlier
sessions this week, all still uncommitted.

Allowed files: `decision-trace/HANDOFF.md` (status update only), project
memory files under
`/home/Yatsuiii/.claude/projects/-run-media-Yatsuiii-Windows-SSD-custody-search-2/memory/`.
No app code — `vertex.py`, `ingest.py`, `test_ingest.py` are untouched by
the Gemma attempt and stay that way.

Non-goals: no edits to `BUILD_SCOPE.md`, `RESULTS.md`, `decisions.jsonl`,
or the frozen pipeline scripts; no touching `failure-mining/`,
`research-impact/`, `contribution-gate/`, `research-access/`, or
Custody's `feat/memory-provenance`; no new GCP credentials/spend; no
commit/push without explicit authorization.

Baseline: what was tried and found this session — Vertex AI: 404 on
every Gemma publisher-model path across 4 regions (self-host-only, real
GPU cost, not attempted). Gemini Developer API: enabled
`generativelanguage.googleapis.com`, created a scoped API key
(`decisiontrace-gemma-extraction`), confirmed real model names
(`gemma-4-26b-a4b-it`, `gemma-4-31b-it`) and that the key authenticated,
but every generation call failed `429: prepayment credits depleted`
(Gemma's own paid billing bucket, separate from Vertex). Web search
confirmed Gemma isn't on the Gemini API free tier (only Gemini 2.5
Flash/Flash-Lite are free). User has no budget. API key deleted
(`gcloud services api-keys delete`, confirmed via `deleteTime` in the
response); local `.env.gemma` removed; no code written; no cost
incurred.

Acceptance gates:
1. `decision-trace/HANDOFF.md` documents the Gemma kill decision (what
   was tried, why it failed, that cleanup is complete) so a future
   session has the finding, not just a stale "do this" line item.
2. Project memory (`decisiontrace_hackathon_rubric.md`) reflects the same
   finding, so it isn't re-suggested without checking budget/free-path
   status fresh.
3. `git status`/checksums confirm no falsifier file, and no app code
   file, was touched by this session.

Verification: read `HANDOFF.md` back to confirm the Gemma section is
accurate and doesn't overstate/understate what was actually tried.
Confirm via `gcloud services api-keys list` that no `decisiontrace-*` key
remains active in the project.

Status: active
