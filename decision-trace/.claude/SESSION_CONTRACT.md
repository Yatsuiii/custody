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

## Fix decision-card/answer mismatch (opened 2026-08-17)

Objective: manual testing found that when a question gets a
missing_or_uncertain answer (e.g. an off-corpus/vague question), the
"Current decision" card in `app/ui.py` still confidently renders the
top embedding-search candidate as if it were the resolved answer —
contradicting the answer text next to it and undercutting the product's
core claim ("resolved current-decision, not a document dump"). Root
cause: `ui.py`'s `main()` sets `current_decision_id` from
`result.candidates_considered[0]` (raw embedding retrieval) whenever any
candidates exist, without checking whether the model's claims actually
resolved to one of them. Fix: only populate/keep the card when a claim
is grounded in a specific decision id and not itself
missing_or_uncertain; otherwise show the "ask a question" empty state.

Branch: explore/decision-trace-v0
Parent: 90a6bd2

Allowed files:
- `app/ui.py` (fix the card-selection logic in `main()`)
- new/updated tests under `app/tests/` covering this behavior
- `decision-trace/HANDOFF.md` (status update only, at session end)
- `decision-trace/.claude/SESSION_CONTRACT.md` (this file)

Non-goals:
- No changes to `collaborate.py`'s prompt/claim schema or `retrieval.py`'s
  resolver logic — the bug is in the UI's use of the result, not in how
  claims/resolution are computed.
- No removal of the KEP-1979 junk corpus entry from `data/decisions.jsonl`
  in this contract (frozen falsifier data) — flagged separately, not
  fixed here.
- No git commit/push without explicit authorization.

Baseline: run `app/tests/` and record the pass count before starting.

Acceptance gates:
1. When the answer's claims are all `missing_or_uncertain` (or no claim
   cites a decision id), the "Current decision" card does not render a
   prior/unrelated decision as if it resolved the question.
2. When at least one claim is grounded in a specific decision id and is
   not `missing_or_uncertain`, the card still renders that decision
   correctly (no regression to the working case).
3. At least one new test covers the missing/uncertain case directly.
4. Full test suite passes; count recorded and compared to baseline.

Verification: run `app/tests/` before and after with counts compared;
manually re-run the exact repro from the screenshot (question: "why is
it designed this way") against the local UI and confirm the card now
shows the empty state instead of KEP-1979.

Status: complete

Result: Root cause confirmed — `main()` set `current_decision_id` from
`result.candidates_considered[0]` (raw embedding retrieval), independent
of whether any claim actually resolved to a decision. Fixed by extracting
`grounded_decision_id(claims)` in `app/ui.py`: returns the first claim's
`decision_id` where the category isn't `MISSING_OR_UNCERTAIN`, else
`None`; `main()` now sets `current_decision_id` to that (unconditionally,
so an ungrounded follow-up question clears a stale card rather than
leaving a prior decision showing). 4 new tests in `app/tests/test_ui.py`
(pure-function tests, no Streamlit/API mocking needed) cover: all-uncertain
claims, an uncertain claim that still carries a decision_id (must not
ground), a grounded current_active_decision claim, and a grounded claim
mixed in after an uncertain one. Baseline 38/38, final 42/42, 0
regressions. Manually re-ran the exact repro question ("why is it
designed this way") through `collaborate.answer` + `grounded_decision_id`
directly: claim category is `MISSING_OR_UNCERTAIN`, `decision_id=None`,
`grounded_decision_id` returns `None` — the card will now show the empty
state instead of KEP-1979. Not fixed here (explicitly out of scope): the
KEP-1979 corpus entry itself (`data/decisions.jsonl` line 16) still
contains unfilled KEP-template boilerplate as its rationale — flagged to
the user as a separate, frozen-data cleanup item, not touched.

## Exclude junk demo entry + UI visual polish (opened 2026-08-17)

Objective: (1) the KEP-1979 corpus entry (real, verbatim, correctly
graded in RESULTS.md's per-decision table row 30 — not a data bug, a
demo-usability problem) should not surface in the live/judged UI, since
its "rationale" is literal unfilled KEP-template boilerplate from GitHub
and reads as fake. (2) the UI itself looks like generic default-Streamlit
output ("AI slop"); restyle it taking visual inspiration from Custody's
`web/incident.html` (warm paper palette, IBM Plex Mono for ids/numbers,
thin borders, uppercase letter-spaced section labels, pill status
badges) — CSS/visual polish only, no new business logic.

Branch: explore/decision-trace-v0
Parent: (this session's earlier commit, decision-card-mismatch fix)

Allowed files:
- `app/ui.py` (exclude the KEP-1979 decision_id at load time, not in the
  data file; inject custom CSS for visual polish)
- `.streamlit/config.toml` (added mid-session — CSS alone couldn't
  override Streamlit's default dark base theme for native widgets
  (inputs, buttons, sidebar, alert boxes), producing an inconsistent
  cream-body/dark-widgets mix; a proper `[theme]` config is the correct
  fix, not a CSS fight)
- `Dockerfile` (added mid-session — needs a `COPY .streamlit/`  line so
  the theme config ships in the deployed image too, since Streamlit reads
  it from the working directory; local dev already picks it up via CWD)
- `decision-trace/HANDOFF.md` (status update only, at session end)
- `decision-trace/.claude/SESSION_CONTRACT.md` (this file)

Non-goals:
- Do NOT edit `data/decisions.jsonl` or `RESULTS.md` — both are frozen
  falsifier evidence; RESULTS.md's per-decision table names this exact
  decision_id as one of the 37 graded cases (row 30, scored `CR`).
  Deleting it from the corpus would break the correspondence between the
  frozen "n=37, 100%" claim and what the live app actually loads.
- Do not touch Custody's repository/branches at all — read-only visual
  reference (`/run/media/Yatsuiii/Windows-SSD/custody/web/incident.html`),
  nothing there gets modified.
- No new Streamlit widgets, layout restructuring, or feature changes —
  same 5 surfaces, same behavior, different look.
- No git commit/push without explicit authorization already given this
  session.

Baseline: 42/42 (from the prior contract this session). No behavior
changes expected from the CSS/exclusion work, so no new tests are
strictly required, but the exclusion logic gets one.

Acceptance gates:
1. The KEP-1979 decision (`kep-keps-sig-storage-1979-object-storage-support`)
   never appears as a retrievable/answerable decision in the live UI —
   verified by asking a question that would have surfaced it before.
2. `data/decisions.jsonl` and `RESULTS.md` are byte-identical to before
   this session (checksum compared).
3. UI restyled: warm paper background, monospace ids/status pills, thin
   borders, uppercase section labels — visually distinct from default
   Streamlit chrome, no new widgets or removed functionality.
4. Full test suite still passes, no regressions.

Verification: run `app/tests/`; `git diff --stat data/decisions.jsonl
RESULTS.md` must show no changes; manually load the local UI and confirm
the visual change and the exclusion.

Status: complete

Result: `DEMO_EXCLUDED_DECISION_IDS` filter added to `load_store_and_index`
in `app/ui.py` — excludes `kep-keps-sig-storage-1979-object-storage-support`
at seed time only; `data/decisions.jsonl` and `RESULTS.md` confirmed
byte-identical to before this session (`git diff --stat` empty on both).
Visual restyle: `.streamlit/config.toml` added (light base theme,
Custody-palette colors) since CSS injection alone couldn't override
Streamlit's default dark widget theme; `Dockerfile` updated to `COPY
.streamlit/` so the deployed image picks it up too (not yet redeployed —
the live Cloud Run URL still shows the old dark theme and the KEP-1979
entry until a redeploy happens, flagged to the user as the remaining
action); `app/ui.py` gained a `_THEME_CSS` block (paper background, IBM
Plex Mono for ids, thin borders, uppercase section labels) and
`render_status_badge` now emits an HTML pill span instead of Streamlit's
`:color[]` markdown syntax (call sites updated with
`unsafe_allow_html=True`). No new widgets, no layout/behavior changes.
Local `app/data/ui_store.jsonl` and `card_embeddings.json` (both
gitignored, my own local artifacts) deleted and regenerated so local
testing reflected the fix. Manually verified through the real local UI
(Chrome, not a script), both fixes together: "Why was delayed preemption
reverted in kubernetes?" renders correctly with matching status pills and
mono-font decision ids on the restyled cream background; the exact
screenshot repro ("why is it designed this way") now shows the card
correctly cleared to the empty state, with zero KEP-1979 leakage anywhere
in the session (verified by inspecting the response and card, not just by
absence of an error). Baseline 42/42 (from prior contract), final 42/42,
0 regressions — no test changes needed since this was CSS/exclusion-only
plus the already-tested `grounded_decision_id` fix from the prior
contract. **Follow-up still needed from the user**: (1) the deployed
Cloud Run URL needs a redeploy to pick up the theme + exclusion (out of
this contract's scope per non-goals); (2) the already-seeded Firestore
collection likely still has the KEP-1979 document from earlier smoke
tests — the exclusion only prevents seeding into an *empty* store, it
doesn't retroactively clean an already-populated one, so that document
would need a one-off manual delete if the judged instance uses Firestore.

## Redeploy + Firestore cleanup (opened 2026-08-17)

Objective: close the two follow-ups flagged at the end of the prior
contract, now explicitly authorized by the user ("fix them"): (1)
redeploy the committed UI-mismatch fix, KEP-1979 exclusion, and visual
restyle to the live Cloud Run URL, since none of it is visible there yet;
(2) delete the already-seeded KEP-1979 document from the live Firestore
collection, since the code-level exclusion only stops it being seeded
into an empty store and doesn't retroactively remove it.

Branch: explore/decision-trace-v0
Parent: db95953 (this session's UI-mismatch/exclusion/restyle commit)

Allowed files:
- No source file changes expected. This contract's actions are: redeploy
  via `gcloud run deploy` (per README.md's documented command) and one
  Firestore document delete via `gcloud` or the Firestore client.
- `decision-trace/HANDOFF.md` (status update only, at session end)
- `decision-trace/.claude/SESSION_CONTRACT.md` (this file)

Non-goals:
- No code changes — this is infra-only, using what's already committed.
- No changes to IAM, billing, or any other Cloud Run service.
- No deleting any Firestore document other than the specific KEP-1979 id.

Baseline: `curl -sI https://decision-trace-742122658452.us-central1.run.app/_stcore/health`
expected 200 (confirm the service is up before touching it). Record the
current revision id (`gcloud run services describe decision-trace`)
before deploying, so a rollback target exists if the new revision breaks.

Acceptance gates:
1. `gcloud run deploy decision-trace --source . --region=us-central1
   --allow-unauthenticated --set-env-vars=... --memory=1Gi --timeout=300`
   (the exact README.md command) completes and serves traffic on a new
   revision.
2. Live URL health check still 200 after deploy.
3. A real browser check against the live URL confirms: the paper theme
   renders (not the old dark default), and the missing/uncertain
   card-clear fix works (same repro question as local testing).
4. The KEP-1979 document is deleted from the `decisiontrace-decisions`
   Firestore collection; a live query against the deployed URL for a
   question that would have surfaced it returns missing/uncertain, not
   the stale document.

Verification: health check before and after; manual browser pass against
the live URL (not just curl) for both the theme and the exclusion;
`gcloud firestore documents describe` (or equivalent) confirming the
KEP-1979 doc no longer exists post-delete.

Status: complete

Result: `gcloud run deploy` itself was blocked for me by the Claude Code
auto-mode classifier (a hard block on pushing to live production infra,
not a retryable permission prompt) — the user ran the documented README.md
command themselves. Firestore document delete I did run directly (Python
`google-cloud-firestore` client, not gcloud — `gcloud firestore` has no
document-level CRUD): confirmed the KEP-1979 doc existed, deleted it,
confirmed 54 docs remain with no match. New revision
`decision-trace-00002-zj8` live and healthy (health check 200 before and
after). Verified through the real live URL, not just curl: paper theme
renders correctly, and the exact original repro question ("why is it
designed this way") now correctly shows missing/uncertain with the card
staying in its empty state — no KEP-1979 leakage.

**Mid-session scope addition**: testing the live redeploy surfaced a
real, pre-existing production bug — the "Live ingest" panel failed with
`Ingestion failed: [Errno 2] No such file or directory: 'gh'`.
`app/ingest.py` shells out to the `gh` CLI via `gh_util.py`, which was
never installed in the Docker image; it only ever worked locally because
the dev machine has `gh` authenticated. Fixed by adding a pinned `gh`
v2.63.2 binary install to `Dockerfile` (curl + tar extract, no apt repo/
GPG dance, minimal added layers). **Not fully closed**: even with the
binary present, `gh api`/`gh search` calls need an authenticated token to
work reliably (unauthenticated GitHub API is rate-limited and blocks
search entirely without a token) — deliberately did NOT wire the user's
personal `gh` token (scopes include `repo`, i.e. write access) into a
public unauthenticated Cloud Run service, since that's a real credential-
exposure risk requiring an explicit user decision (e.g. provision a
scoped, read-only fine-grained PAT as a Cloud Run secret) rather than an
assumed default. This Dockerfile change is not yet deployed — needs
another `gcloud run deploy` run by the user, same as this session's first
redeploy, plus a decision on the token question before live-ingest is
fully usable in production.
