Objective: Produce the hackathon submission package for DecisionTrace per
`decision-trace/HANDOFF.md` step 3: a judge-facing README with spin-up
instructions, an architecture diagram, and a written demo script covering
the same 9-step scenario already proven live (Stage 8 local + this week's
Cloud Run smoke test). Scope excludes actually recording/narrating the
~4-minute video — that requires a human voice/screen capture I cannot
produce; I will hand off a tight, timed script instead, and flag the actual
recording as the user's remaining action.

Branch: explore/decision-trace-v0
Parent: a62f20a (app/store.py, app/ui.py, app/tests/test_store.py,
app/requirements.txt, Dockerfile, .dockerignore remain uncommitted from
prior sessions this week; this session adds submission docs on top,
still uncommitted unless the user asks to commit)

Allowed files:
- decision-trace/README.md (new — judge-facing, not the internal
  BUILD_SCOPE.md/RESULTS.md docs, which stay frozen and untouched)
- decision-trace/docs/architecture.md or decision-trace/docs/ARCHITECTURE.md
  (new — diagram, as Mermaid embedded in Markdown, since there's no image
  tooling here; GitHub/most viewers render Mermaid natively)
- decision-trace/docs/DEMO_SCRIPT.md (new — timed walkthrough script for
  the ~4-minute video, referencing the real deployed URL)
- decision-trace/HANDOFF.md (status update only, at session end)
- decision-trace/.claude/SESSION_CONTRACT.md (this file)

Non-goals:
- No video recording/editing — out of my capability, explicitly handed
  back to the user as the one remaining manual step.
- No edits to BUILD_SCOPE.md, RESULTS.md, or any frozen falsifier
  artifact/script.
- No app code changes this session (store.py, ui.py, etc. stay as they
  are from the last two sessions).
- No further Cloud Run/infra changes — the deployed service from the
  prior session is treated as done; this session only documents it.
- No touching Custody's services/branches or failure-mining/AutomationBench.
- No git commit/push without explicit authorization.

Baseline: N/A (docs-only session, no code under test). Confirm the live
URL still responds before citing it: `curl -sI
https://decision-trace-742122658452.us-central1.run.app/_stcore/health`
expected 200.

Acceptance gates:
1. README.md covers: one-paragraph pitch, the falsifier result as the
   differentiation claim (100% vs 57%, n=37, cited from RESULTS.md's real
   numbers — no invented stats), the live Cloud Run URL, local spin-up
   instructions that actually match HANDOFF.md's real commands, and the
   Google Cloud stack used (Cloud Run + Firestore + Vertex AI/GenAI SDK).
2. Architecture doc has one diagram covering the real components (ui.py,
   collaborate.py, retrieval.py, graph.py, FirestoreDecisionStore, Vertex
   AI/Gemini, Cloud Run) and data flow, matching what's actually in
   app/*.py — not an idealized/aspirational architecture.
3. Demo script is timed to fit ~4 minutes, walks the same 9 steps already
   proven (ask why -> recover history -> surface the revert -> state
   current status -> record reconsideration -> kill process -> fresh
   process -> confirm persistence), and explicitly calls out the moment
   that proves "backend proof on Google Cloud" (Firestore persistence
   surviving a fresh session) since the rubric asks for that specifically.
4. Every factual claim in these docs traces to something verified earlier
   this week (test counts, falsifier numbers, the live URL, the IAM/
   deploy details) — no new unverified claims about behavior.
5. Live URL re-confirmed responding (curl health check) before the README
   is written, so the submission doesn't cite a dead link.

Verification: read the three new docs back and cross-check every number
against RESULTS.md/HANDOFF.md/SESSION_CONTRACT.md history; curl the live
health endpoint once at the end to reconfirm it's still up.

Status: complete

Result: README.md, docs/architecture.md (Mermaid diagram), docs/DEMO_SCRIPT.md
written. Every stat cross-checked against RESULTS.md's real table (100%
vs 57% combined-correct, n=37) and HANDOFF.md's real commands before
being written down. Live URL re-confirmed responding (HTTP/2 200 on
/_stcore/health) both before writing and after, at session end. Video
recording itself is explicitly out of scope (no screen/voice capture
capability here) and handed back to the user as the one remaining manual
step — DEMO_SCRIPT.md is a ready-to-follow, timed script referencing only
things already proven live this week.

## Live-ingest UI wiring + failure-path tests (opened 2026-08-17)

Objective: a judge re-review scored Innovation & Utility 80/100 and
Architectural Discipline 78/100, docked for two named reasons: (1) the
judged demo only ever shows the frozen 55-decision benchmark, so
"operational utility" is asserted, not demoed — `ingest_repo()` in
`app/ingest.py` already works and is tested but isn't reachable from the
UI; (2) the test suite is happy-path only (911 lines across 5 files, zero
tests named `timeout`/`error`/`malformed`) — no proof of behavior when
Gemini times out, a PR body is malformed, or Firestore is unavailable.
Close both gaps.

Branch: explore/decision-trace-v0
Parent: 162234a

Allowed files:
- `app/ui.py` (add a live-ingest entry point calling the existing
  `ingest_repo()` — UI wiring only, not new extraction logic)
- new tests under `app/tests/` for ingest failure paths and existing
  component failure paths (Gemini timeout, malformed PR/KEP input,
  Firestore unavailable)
- `app/ingest.py` (added mid-session, 2026-08-17): the failure-path tests
  found a real bug in `extract_decision_fields` — a malformed Gemini
  response where `rejected_alternatives`/`constraints` come back as a
  string instead of a list passes straight through into a `Decision`,
  where downstream `'; '.join(...)` would silently iterate over
  characters instead of failing or defaulting cleanly. Scope: minimal
  type-validation fix only, not a rewrite of the extraction pipeline.
- `README.md`'s "What's deliberately not in the demo" section (update to
  reflect live ingest now being wired, if it lands) and status notes
- `decision-trace/HANDOFF.md` (status update only, at session end)
- `decision-trace/.claude/SESSION_CONTRACT.md` (this file)

Non-goals:
- `BUILD_SCOPE.md`, `RESULTS.md`, `data/decisions.jsonl`, and the frozen
  falsifier pipeline scripts (`mine_decisions.py`, `build_corpus.py`,
  `rag_index.py`, `run_conditions.py`, `grade.py`, `vertex.py`,
  `gh_util.py`) stay frozen and untouched — this is product work, not a
  re-run of the falsifier.
- No new Cloud Run deploy required by this contract alone; if live-ingest
  wiring needs redeploying to reach the judged URL, that's a follow-up
  the user will trigger explicitly, not assumed here.
- No touching Custody's `feat/memory-provenance` branch/services or the
  archived `failure-mining/`/`research-access/`/`research-impact/`/
  `contribution-gate/` directories (already removed from this branch at
  162234a — stay removed).
- No git commit/push without explicit authorization already given this
  session (user said "you can do everything else," 2026-08-17) — commit
  and push are in scope for this contract.

Baseline: run `app/tests/` and record the pass count before starting
(real API calls, needs `CLOUDSDK_CONFIG` pointed at `.gcloud`, ~5 min).

Acceptance gates:
1. The UI exposes a way to point ingestion at a live repo (at minimum, one
   judge-choosable target) and it produces at least one real decision
   record end-to-end through `ingest_repo()` — not a mock, not a canned
   fixture.
2. At least one test proves a Gemini API timeout/error during collaboration
   or ingestion is surfaced as a clear failure, not a silent wrong answer.
3. At least one test proves a malformed/incomplete PR or KEP input to
   `ingest.py` fails predictably (raises or returns a clear error) rather
   than producing a garbage decision record.
4. At least one test proves Firestore unavailability is handled — either a
   clear error or a documented fallback, not a silent data loss.
5. Full test suite passes afterward; count recorded and compared to
   baseline. `README.md`'s "not in the demo" section updated to match
   reality (remove the ingest caveat if it now holds, or narrow it
   precisely to what's still true).

Verification: run `app/tests/` before and after with counts compared;
manually exercise the new UI ingest path once against a real small repo to
confirm the end-to-end record actually appears and shapes a subsequent
answer, mirroring the existing Stage 8 discipline.

Status: complete

Result: Baseline 31/31, final 38/38 (7 new tests in
`app/tests/test_failure_paths.py`, 0 regressions). `app/ui.py` gained a
"Live ingest" sidebar panel (repo text input, max-candidates control,
Ingest button) that calls the existing `ingest_repo()` and adds results to
the session store via `store.save_many()` + `index.reindex()`. Manually
exercised through the real browser UI (Chrome, not a script): ingesting
`kubernetes/kubernetes` produced "Ingested 4 decision(s)", and a follow-up
question ("Why configure the max CrashLoopBackOff delay?") correctly
surfaced the freshly ingested `kep-keps-sig-node-5593-configure-the-max-
crashloopbackoff-delay` decision as the current active decision on the
card, with a real cited evidence URL — gate 1 satisfied against a real
repo, no mock. Gates 2-4 each covered by mocked failure-injection tests
(the failure condition itself is mocked; nothing else in the call path
is): Gemini timeout/error during `collaborate.answer` and
`ingest.extract_decision_fields` both propagate as a clear exception
rather than a fabricated answer; malformed/unparseable Gemini extraction
output defaults to a predictable "(untitled)"/empty-fields shape; an
incomplete revert-PR candidate raises `KeyError` rather than constructing
a Decision with silently missing data; Firestore unavailability (mocked
collection raising on `.stream()`/`.get()`/`.set()`) raises clearly on
both read and write, never a silent empty result or a silently-lost
write. **Real bug found and fixed**: `extract_decision_fields` never
validated that `rejected_alternatives`/`constraints` came back from
Gemini as JSON arrays — a malformed response returning a bare string for
either field passed straight through into `Decision`, where
`retrieval.render_card`'s `'; '.join(...)` would have silently iterated
over the string's characters instead of failing or defaulting cleanly.
Fixed with a new `ingest._as_str_list` helper that coerces to `list[str]`
or defaults to `[]`; the fix required adding `app/ingest.py` to this
contract's Allowed files mid-session (documented above), since the bug
was discovered only after the contract was opened. Covered by a
regression test (`test_wrongly_typed_model_fields_do_not_produce_a_garbage_
decision_record`). `README.md`'s "not in the demo" section rewritten to
describe the live-ingest panel instead of listing it as a gap.
