# DecisionTrace: port authority-proof engine into the product

Opened 2026-08-22.

Objective: Product-integration session. Port the general authority-proof
architecture developed and validated on `research/decisiontrace-authority-
proof` (checkpoint `f417acf`, live-integration-verified at `96cc921`) into
the actual DecisionTrace product, without touching the frozen submission
branch. Minimum required product changes: scope-local authority semantics,
`partial_acceptance` support, deterministic `AuthorityProof` generation,
a Gemini explanation layer that narrates but never decides authority, and
Firestore persistence compatible with existing production records. Wire
this into the existing collaborative worker story (Evidence Scout ->
Lifecycle Resolver -> Provenance Challenger -> Gemini Reconciler) and the
smallest possible judge-facing UI addition. No new benchmark, no Custody
changes, no research dataset ported into the product, no application
rewrite beyond the authority path.

Branch: integration/decisiontrace-authority-proof
Parent: 1c33d3de169ebbdb874992e9383b632d163b2658
(`explore/decision-trace-v0`, the frozen hackathon submission — never
developed on directly, remains the rollback point)

Allowed files:
- `decision-trace/app/authority.py` (new — ported from research, port
  audit determines exact scope)
- `decision-trace/app/models.py` (edit — `partial_acceptance` field)
- `decision-trace/app/graph.py` (edit — structured `lifecycle_events`
  field, matching research)
- `decision-trace/app/store.py` (edit — round-trip fix for the new
  field, both JSON and Firestore paths)
- `decision-trace/app/collaborate.py` (edit — wire the authority
  resolver into the Lifecycle Resolver/Provenance Challenger/Gemini
  Reconciler worker story; add an authority-explanation path)
- `decision-trace/app/loader.py` (edit — assign `related_components` to
  loaded frozen-benchmark decisions; found during Phase 10 demo replay
  that the loader never set a scope at all, so `_resolve_authority_for_
  candidates` could never produce an `AuthorityProof` for any real demo
  decision. Minimal, deterministic scope derivation only — no new fields
  on the source JSONL, no re-mining)
- `decision-trace/app/memory.py` (edit — `propose_reconsideration`'s
  candidate must inherit the target decision's `related_components` so
  the reconsideration becomes a visible, correctly-excluded
  `PROPOSED_NOT_ACCEPTED` candidate in the target's own AuthorityProof,
  per Phase 7's reconsideration demo requirement; no change to
  `RECONSIDERS` not being a lifecycle edge, so governing truth is still
  unaffected)
- `decision-trace/app/ui.py` (edit — minimal "CURRENTLY GOVERNING / WHY
  THIS GOVERNS / View full authority proof" addition only, no redesign)
- `decision-trace/app/tests/**` (new/edit — port relevant adversarial +
  regression tests, add product-integration tests)
- `decision-trace/README.md` (edit — remove/replace any 76%-vs-57%-style
  superiority claim with the architectural positioning sentence)
- `decision-trace/.claude/SESSION_CONTRACT.md`, this file
- `decision-trace/PORT_PLAN.md` (new — Phase 2 audit/plan, written
  before any product code changes)
- `decision-trace/INTEGRATION_DECISION.md` or equivalent final-report doc
  (new, end of session)

Non-goals:
- No new benchmark, no new dataset, no rescoring, no prospective-
  superiority claim.
- Do not port benchmark data, prospective runs, research score files,
  failure-mining artifacts, research-only scripts, or old falsifier
  experiments from the research branch.
- Do not touch Custody.
- Do not develop directly on `explore/decision-trace-v0`.
- Do not merge this branch into the frozen product without explicit
  authorization (research/audit only this session; recommendation, not
  action).
- Do not replace the existing production Cloud Run deployment; a preview
  revision/service only, and only after local gates are green.
- Do not push unless explicitly authorized.
- Do not add product features unrelated to the authority-proof path.

Baseline: `git log -1 --format=%H` on this branch ==
`1c33d3de169ebbdb874992e9383b632d163b2658`; `app/authority.py` does not
exist on this branch pre-port (confirmed); `app/requirements.txt` here
matches the research branch's (google-genai, google-cloud-firestore,
numpy, streamlit, pytest) — confirmed byte-identical.

Acceptance gates:
1. `PORT_PLAN.md` written and the minimum-diff port scope decided before
   any product file is edited.
2. Ported authority engine passes an adversarial test suite (ported/
   adapted from research) covering scope-locality, proposal/supersession/
   revert/parallel-scope/partial-acceptance semantics.
3. `AuthorityProof` reaches the Gemini explanation layer without Gemini
   gaining any authority-deciding responsibility (tested).
4. Old 76%-vs-57% superiority claim removed from judge-facing product
   copy (README/UI), replaced with the architectural positioning
   sentence, not a new number.
5. Full product suite green under the correct `.venv` interpreter, real
   integrations exercised (Firestore, Gemini, GitHub), backward
   compatibility with pre-existing (no `partial_acceptance`) Firestore
   records proven without mutating production data.

Verification: `source .venv/bin/activate` (or `.venv/bin/python`
explicitly) for every test run; full suite count recorded; real
Firestore/Gemini/GitHub integration results recorded; local demo replay
of the delayed-preemption scenario; preview deployment (not production)
smoke-tested if reached.

Status: active

---

# Archived — closed, superseded by the entry above

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
