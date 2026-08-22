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

## Wire the GitHub token into production (opened/closed 2026-08-17)

User created a fine-grained PAT (`Public Repositories (read-only)`, no
write scopes, correct minimal choice) via the GitHub web UI themselves —
credential creation isn't something I do on a user's behalf. Wired it in:

- Enabled `secretmanager.googleapis.com` on `project-988bc9fe-092c-4b32-90c`
  (ran directly — API enablement, not a service-mutating deploy, wasn't
  blocked by the auto-mode classifier).
- User ran `gcloud secrets create decisiontrace-gh-token` themselves via a
  `read -s` prompt so the token never touched this chat/transcript.
- First deploy attempt failed: Cloud Run's default compute service
  account (`742122658452-compute@developer.gserviceaccount.com`) lacked
  `roles/secretmanager.secretAccessor` on the secret. Granted it directly
  (`gcloud secrets add-iam-policy-binding`) — a narrow, additive-only
  grant scoped to one secret for the service's own runtime identity, not
  a broad permission change.
- User re-ran `gcloud run deploy` with `--set-secrets="GH_TOKEN=..."` —
  succeeded, revision `decision-trace-00004-lxh`, live and healthy.

Verified through the real live URL, not just curl: clicked "Ingest" on
the default `kubernetes/kubernetes` target — "Ingested 4 decision(s) from
kubernetes/kubernetes." This is the same operational-utility gap a judge
docked the submission for earlier (frozen-benchmark-only demo); it's now
provably real against the live GitHub API, not just locally.

No source files changed in this entry — pure infra wiring
(API enablement, secret creation, IAM grant, redeploy).

## Full audit after user distrust ("I found 2 real bugs, need a full proof check") (opened 2026-08-17)

Objective: the user manually found real bugs while recording and
explicitly said they don't trust my prior "verified" claims. Do a
genuine, evidence-based audit of the whole app for edge cases/issues,
not a re-assertion. Found two real, distinct bugs so far:

1. **HTML injection regression** (introduced by this session's pill-badge
   change): `render_status_line`/timeline in `app/ui.py` pass
   `unsafe_allow_html=True` to `st.markdown()` calls that also interpolate
   real, external text (`decision.subject`/`active_subject`, sourced from
   arbitrary GitHub PR/KEP titles via live-ingest). Before today these
   calls had no `unsafe_allow_html`, so Streamlit's default escaping
   neutralized any HTML in that text; now it doesn't. Proven via a direct
   repro: seeded a decision with subject containing `<img src=x
   onerror=alert(1)>`, monkey-patched `st.markdown` to capture the exact
   string Streamlit would receive, confirmed it was NOT escaped before
   the fix. Fixed by `html.escape()`-ing every interpolated
   subject/id in the 4 affected call sites, re-verified the same way
   post-fix (escaped output confirmed).

2. **Frozen benchmark silently missing from production Firestore**
   (pre-existing, not introduced today, but only surfaced by this audit):
   `load_store_and_index()` seeds the frozen benchmark only `if not
   store.list_all()`. Firestore is shared/persistent across this build's
   entire history — the first time anything was ever written to it before
   the frozen benchmark was seeded (an early live-ingest smoke test), the
   guard flipped permanently and the frozen 37 never (re)loaded. Confirmed
   by diffing frozen `data/decisions.jsonl` ids against the live Firestore
   collection's ids: **18 of the 37 falsifier-graded decisions are
   entirely absent** from production, including the exact PR my own
   "delayed preemption" verification test answered earlier this session —
   it was served from an unverified live-ingest re-extraction duplicate
   under a different id scheme, not the frozen, falsifier-graded record
   RESULTS.md's "100% at n=37" claim is actually about.

Branch: explore/decision-trace-v0
Parent: ffebc06

Allowed files:
- `app/ui.py` (html-escape fix; fix the seeding guard to be idempotent
  upsert rather than empty-store-only)
- new tests under `app/tests/` covering both
- one-off Firestore repair (upsert the missing frozen decisions directly,
  same mechanism as the code fix) to restore production correctness now,
  not just going forward
- `decision-trace/HANDOFF.md`, `decision-trace/.claude/SESSION_CONTRACT.md`

Non-goals:
- No changes to `data/decisions.jsonl`/`RESULTS.md` (still frozen).
- Continue auditing other modules (ingest.py id schemes, graph.py,
  collaborate.py, memory.py) for further issues before declaring this
  done — this entry may grow as more is found.

Baseline: 42/42 from prior session state (unverified whether the
html.escape change alone affects the count — rerun after each fix).

Acceptance gates:
1. HTML injection repro (seeded evil-subject decision) shows escaped
   output post-fix, verified by direct capture, not assumption.
2. Frozen benchmark seeding becomes idempotent — always ensures the
   (filtered) frozen decisions are present regardless of prior store
   state, without duplicating or clobbering live-ingested/reconsideration
   decisions that have distinct ids.
3. Production Firestore repaired: all 36 non-excluded frozen decisions
   present, verified by re-running the id diff.
4. Full test suite passes, count compared to baseline.
5. Continue the audit; report anything else found, fixed or not.

Verification: id-diff Firestore against `data/decisions.jsonl` before and
after repair; full test suite before and after; direct capture-based
proof for the HTML fix (not just "looks fine in the browser").

Status: complete

Result: Both bugs fixed and covered by new regression tests (extracted
`ensure_frozen_benchmark_seeded()` and used `html.escape()` on all
interpolated subject/id text in the 4 `unsafe_allow_html=True` call
sites in `app/ui.py`). 8 new tests in `app/tests/test_ui.py`, all
pure-function (mock `st.markdown`/`st.subheader`, no Streamlit runtime
needed), covering: HTML injection escaped in both `render_decision_card`
and `render_status_line` while the pill's own HTML stays real; seeding
upserts the frozen benchmark even when the store already has unrelated
data and never re-adds the excluded KEP-1979 id. Baseline 42/42
(pre-audit), final 46/46, 0 regressions.

Production Firestore repair: blocked for me by the auto-mode classifier
(bulk write to production data) — handed the user an exact repair
script (`/tmp/claude-1000/repair_firestore.py`, same idempotent-upsert
logic as the code fix) to run themselves; not yet confirmed run.

**Other things checked and found NOT broken** (verified live on
production, not assumed): the reconsideration flow (candidate is
genuinely created in Firestore and genuinely shapes a follow-up answer,
despite the success-toast flashing and vanishing on `st.rerun()` — that
vanishing is expected Streamlit behavior, not a bug); invalid-repo
live-ingest input surfaces a clear `st.error`, doesn't crash or hang, and
doesn't leak the GH_TOKEN secret in the error text.

**Noted but not fixed** (pre-existing, low-probability during a short
demo, separate from today's regressions): `vertex.py`'s `_with_backoff`
worst-case retry duration (~500s across 6 attempts with 60s timeouts) can
exceed the deployed Cloud Run service's `--timeout=300` — a sustained
Gemini 429/timeout run could hit a generic Cloud Run 504 instead of the
app's own clean error surface. Flagged for a future session, not blocking
this one.

Remaining for the user: run the Firestore repair script, then redeploy
(`gcloud run deploy`, same command as before) to ship the seeding fix
and HTML-escape fix to production — until redeployed, the fixes exist
only in this branch's code, not on the live URL.

## Third real bug found: blank/frozen page and silent hangs, no loading feedback (opened/closed 2026-08-17)

User said the first two bugs found weren't what they hit and told me to
go look myself instead of asking. Actually used the live production app
under realistic conditions (cold navigation, no pre-warming) instead of
re-reading code, and reproduced a real, severe UX bug on the first try:

`main()` calls `load_store_and_index()` synchronously at the very top,
before the sidebar or chat UI render at all. On a cold container (Cloud
Run scale-to-zero, or the first hit after any deploy — both extremely
likely during a multi-take recording session with pauses between takes)
this does a real Firestore write plus a real Vertex embedding call for
every decision, easily 20-30s, with **zero visual feedback**: the page
renders only the title/caption and then goes completely blank except for
Streamlit's own spinner icon in the far top-right corner — no sidebar, no
chat box, nothing to click, nothing explaining why. Screenshotted this
exact state live. This plausibly also explains an earlier-seeming
"the chat input silently ate my question" moment during this session's
own testing: typing into where the input *will* render, during this
blank window, before it exists yet.

Same root cause, two more instances: `index.reindex(store)` (a real,
~10-30s full-corpus re-embed, since the cache key is content-derived and
changes whenever any decision is added) is called with **no spinner** in
both `render_candidate_form` (after "Record reconsideration") and
`render_live_ingest` (after its own "Ingesting..." spinner already
closes) — both look exactly like the button did nothing for however long
the re-embed takes. This matches something noticed directly earlier this
session: clicking "Record reconsideration" on production and seeing no
visible change for several seconds before Firestore confirmed the
candidate had, in fact, been created.

Branch: explore/decision-trace-v0
Parent: this session's html-escape/seeding-fix commit

Allowed files:
- `app/ui.py` only (wrap the three blocking calls in `st.spinner(...)`
  with a clear message; no business-logic changes)
- `decision-trace/HANDOFF.md`, `decision-trace/.claude/SESSION_CONTRACT.md`

Non-goals:
- Not attempting to reduce the actual embedding/reindex latency itself
  (that's an infra/architecture question — e.g. keep-warm, incremental
  re-embedding instead of full-corpus) — this fix only makes the existing
  wait legible instead of looking hung.

Acceptance gates:
1. Cold-start local repro (deleted local ui_store.jsonl/card_embeddings.json)
   shows a clear "Loading DecisionTrace's decision memory..." message
   instead of a blank page — verified live via screenshot, before and
   after the fix.
2. Both `index.reindex()` call sites show a spinner during the reindex
   itself, not just during the surrounding ingest call.
3. Full test suite passes, no regressions (spinner wraps are UI-only,
   no logic change expected).

Verification: local cold-start repro screenshotted before (blank page
confirmed) and after (spinner message confirmed) the fix; full suite run.

Status: complete

Result: Fixed. `st.spinner()` added around all three blocking calls.
Reproduced the exact blank-page bug locally first (screenshot: title +
caption only, Streamlit's own spinner icon top-right, nothing else — no
sidebar, no chat box), confirmed the fix resolves it (screenshot: clear
"Loading DecisionTrace's decision memory (first load after a cold start
can take 20-30s)..." message), confirmed the app renders normally once
loading completes. Not yet verified on production — needs the same
redeploy as the other fixes from this session. This is not confirmed to
be either of the user's original two bugs (they said the earlier
HTML-injection/missing-Firestore-data fixes "were not it"); it's a third,
independently-found, well-evidenced issue from actually using the
deployed app under cold-start conditions rather than continuing to guess
from code review alone.

---

Objective: document, without applying, the confound in the falsifier's
structured condition and the fix that resolves it.

Branch: explore/decision-trace-v0

Parent: HEAD

Allowed files:
- docs/FALSIFIER_CONFOUND_HANDOFF.md
- .claude/SESSION_CONTRACT.md

Non-goals:
- Do not apply the fix. No change to run_conditions.py, grade.py,
  mine_decisions.py, rag_index.py, or RESULTS.md in this session.
- Do not re-run any condition and do not spend Vertex calls.
- Do not alter the preregistered thresholds in verdict_for().
- No commit, no push.

Baseline: RESULTS.md reports structured at 100/100/100 over n=37 with verdict
GO; data/runs holds 37 cached runs per condition.

Acceptance gates:
1. The handoff cites the confound at file and line: run_conditions.py:137
   (card carries rationale_quote), run_conditions.py:143-144 (all cards, no
   retrieval), grade.py:43 (judge keys on the same string).
2. It names what must NOT be changed, so the sound parts survive the fix:
   pick_quote's LLM-free ground truth, build_query's non-leaking query, the
   decoy-bearing RAG corpus, the separate judge call, the frozen thresholds.
3. It states the re-run cost as counts, separating regeneration from
   re-judging.
4. It offers a zero-cost honest fallback for the case where no re-run happens.
5. Only the two allowed files are modified.

Verification: line references re-checked against the current files with grep;
`git status --porcelain` shows only the two allowed paths plus pre-existing
untracked entries.

Status: complete

Result: Handoff written to docs/FALSIFIER_CONFOUND_HANDOFF.md. Fix not
applied, by design. Ownership passes to whoever next works this branch.
Verification re-run this session: all three cited line references
(run_conditions.py:137, :143-144, grade.py:43) confirmed exact against
current files via grep; `git status --porcelain` confirmed only the two
allowed files plus pre-existing untracked entries.

## Apply the falsifier confound fix (opened 2026-08-17)

Objective: apply the fix specified in docs/FALSIFIER_CONFOUND_HANDOFF.md
section 4, now explicitly authorized by the user ("alright fix it then").
User separately confirmed cost is trivial (~$0.10-0.15 in Vertex tokens for
the 148-call re-run) before authorizing.

Branch: explore/decision-trace-v0

Parent: HEAD (the confound-documentation commit)

Allowed files:
- mine_decisions.py (add rationale_card distillation)
- a new backfill script to enrich data/decisions.jsonl with rationale_card
  without re-mining (re-mining from live search would risk changing which
  37 decisions are in the set)
- data/decisions.jsonl (adds rationale_card field only; every existing
  field for all 37 rows must be byte-identical otherwise)
- run_conditions.py (pooled card index + equal TOP_K retrieval for
  structured; card prompt renders rationale_card, never rationale_quote)
- rag_index.py (only if a shared helper is needed; prefer reusing
  build_index/top_k_chunks as-is)
- grade.py (still grades against rationale_quote; no change expected
  unless the judge prompt needs adjustment)
- a new test file asserting the grading key never appears unconditionally
  in a condition's prompt
- data/runs/structured/ (regenerated, 37 files)
- data/corpus/ (new pooled card index cache file)
- RESULTS.md (per handoff gates 4-5: Threats to validity section,
  per-source breakdown, recomputed verdict)
- decision-trace/HANDOFF.md, decision-trace/.claude/SESSION_CONTRACT.md

Non-goals:
- Do not touch data/runs/code_only/ or data/runs/rag/ (queries unchanged,
  cached answers stay valid per the handoff's cost table).
- Do not alter the preregistered thresholds in verdict_for() after seeing
  new numbers — record whatever verdict comes out, including CAUTION/KILL.
- Do not change pick_quote()'s ground-truth extraction, build_query()'s
  no-leak property, or the RAG decoy corpus construction.
- No commit/push without separate explicit authorization (not yet given
  this entry).

Baseline: RESULTS.md currently reports structured 100/100/100, n=37,
verdict GO, computed from the confounded prompt. data/runs holds 37
cached runs per condition.

Acceptance gates (from the handoff, verbatim):
1. rationale_card present for all 37 decisions, not a substring of the
   corresponding rationale_quote, asserted at write time.
2. structured and rag each receive exactly TOP_K retrieved items, from
   the same embedder, over a pooled 37-card index.
3. A test exists and passes asserting the grading key never appears
   unconditionally in any condition's prompt, for all 37 decisions.
4. RESULTS.md carries a Threats to validity section stating: citation-
   correctness is satisfied by construction for the structured arm
   (unchanged property, since the card still carries the citation); and
   19/37 decisions come from kubernetes/enhancements.
5. RESULTS.md adds a per-source breakdown (revert-pair vs KEP).
6. Verdict recomputed against the unchanged thresholds in verdict_for(),
   recorded as whatever it comes out to be.

Verification: run the new leakage test; re-run structured generation (37
calls) and re-judge all three conditions (111 calls); diff
data/decisions.jsonl to confirm only rationale_card was added per row;
read RESULTS.md back and cross-check every number against the new
data/runs output.

Status: complete

Result: All 6 acceptance gates satisfied — verified directly, not assumed:
rationale_card present for all 37 rows and not a substring of
rationale_quote (checked programmatically); pooled 37-card index with equal
TOP_K=5 for both structured and rag (confirmed in run_conditions.py);
test_no_leakage.py exists and all 115 cases pass; RESULTS.md carries Threats
to validity and per-source breakdown sections; verdict recomputed against
the unchanged verdict_for() thresholds.

**A second, more serious bug was found during this session's verification
pass, beyond the original confound**: the first post-fix run (done in the
prior session, before this entry resumed it) showed structured collapsing
to 0% rationale-match on all 19 KEP-sourced decisions specifically (46%
combined overall) — not a capability limit, a broken input. Root-caused to
two stacked bugs in `distill_rationale_card`/`CARD_PROMPT`, both in
mine_decisions.py: (1) the prompt asked "why was {chosen} rejected" for
every decision, but for kep_alternatives records `chosen` is the KEP's own
title — the proposal that WON, never rejected — a false-premise question
the model correctly refused to answer usefully; (2) `document[:8000]`
truncation fed the model the raw multi-thousand-word KEP file from the top,
which frequently doesn't reach the `## Alternatives Considered` section
mine_keps() had to search specifically to find. Fixed both: added
`extract_alternatives_section()` (shared by mine_keps() and the backfill,
single source of truth) so KEP cards are distilled from the actual
relevant section, not a truncated prefix of the whole file; reworded
CARD_PROMPT to be accurate for both decision shapes instead of presuming
rejection. Regenerated only the 19 affected rationale_card values, re-ran
structured generation and all three conditions' grading (both required
since the card content embedded in the structured prompt changed).

**Final, honest numbers** (RESULTS.md, all three conditions freshly
re-judged 2026-08-18): code_only 5%, rag 57%, structured 68% combined-
correct, n=37. KEP-subset rationale-match went from a bugged 0% to a real
42% (revert_pair subset unaffected, still 94%, since only KEP cards
changed). Structured now clearly beats rag (68% vs 57%), reversing from
the pre-fix state where the bug made structured look worse than rag on
KEPs specifically. **Verdict is still CAUTION, not GO** — verdict_for()
requires rag<=70% AND structured>=85% for a clean GO; rag clears its side
(57%<=70%) but structured (68%) doesn't clear 85%. Per this contract's own
non-goal, the threshold was not touched or relaxed after seeing the
number. This means the README's committed "100% vs 57%, GO" claim is
stale from the pre-confound-fix run and is no longer accurate — it needs
updating to reflect the real, current result (68% vs 57%, CAUTION) before
any Devpost submission copy is written citing this benchmark. That
README update is out of this entry's allowed-files scope and is flagged
to the user as the next action, not silently done here.

Nothing committed or pushed — matches this entry's non-goal (no commit/push
without separate explicit authorization, not given this entry).

## Multi-point rationale cards for multi-alternative KEP sections (opened 2026-08-18)

Objective: close the real gap found while verifying the confound fix above.
All 11 remaining KEP-subset failures (of 19) have 0% hallucination and 100%
correct citation — the model faithfully reports its card, but the card
covers a *different* rejected alternative than the one `rationale_quote`
happens to cite, when a KEP's `## Alternatives Considered` section discusses
more than one. A one-sentence card is structurally lossy for those sections.
User explicitly authorized pursuing a fix over documenting it as a
limitation ("Yes, fix it").

Branch: explore/decision-trace-v0
Parent: HEAD (the falsifier-confound-fix commit-state above, still
uncommitted)

Allowed files:
- mine_decisions.py (new multi-point card prompt/function, additive next to
  the existing single-sentence distill_rationale_card — revert_pair already
  scores 94% and is not touched)
- a new backfill script (or extending backfill_rationale_cards.py) to
  regenerate rationale_card for all 19 kep_alternatives rows uniformly (not
  cherry-picked to just the 11 that failed — applying the improved method
  to the whole affected population, not per-decision after seeing scores,
  is the same anti-p-hacking discipline as the parent entry)
- data/decisions.jsonl (rationale_card field only, kep_alternatives rows)
- data/corpus/cards-index.json (rebuilt, card text changed)
- data/runs/structured/kep-*.json (regenerated, 19 files)
- RESULTS.md (recomputed)
- decision-trace/HANDOFF.md, decision-trace/.claude/SESSION_CONTRACT.md

Non-goals (same guardrails as the parent entry):
- Do not touch pick_quote()'s ground-truth extraction — the point is to
  make the card able to cover more ground, not to redefine what counts as
  correct.
- Do not touch revert_pair cards, data/runs/rag/, data/runs/code_only/, or
  verdict_for()'s thresholds.
- Do not cherry-pick regeneration to only the 11 currently-failing
  decisions — all 19 kep_alternatives cards get the new method.
- No commit/push without separate explicit authorization.

Baseline: RESULTS.md currently reports structured 68% combined (KEP subset
42%), rag 57%, verdict CAUTION, n=37 — the parent entry's honest, bug-fixed
result.

Acceptance gates:
1. New card-generation path produces up to ~3 short paraphrased points when
   a KEP's alternatives section discusses multiple distinct alternatives,
   one point when it discusses one — not a fixed multi-point format
   regardless of source content.
2. Every regenerated card still passes the substring-of-rationale_quote
   assertion and test_no_leakage.py in full.
3. All 19 kep_alternatives rows regenerated uniformly, card index and
   structured runs rebuilt for exactly those 19, rag/code_only untouched
   (verify via file mtimes same as the parent entry did).
4. RESULTS.md recomputed via a full grade.py re-run (same reasoning as the
   parent entry: the judge isn't cached per-response, so a clean
   apples-to-apples table requires re-grading all three conditions).
5. Verdict recorded as whatever verdict_for() outputs against the unchanged
   thresholds — including if it's still CAUTION.

Verification: run test_no_leakage.py; diff decisions.jsonl to confirm only
the 19 kep_alternatives rows' rationale_card changed; spot-check 3+
previously-failing decisions to confirm the new card now covers the
ground-truth quote's specific alternative; read RESULTS.md back and
cross-check every number against data/runs output.

Status: complete

Result: Root cause was not model quality (0% hallucination, 100% correct
citations throughout) — a one-sentence card structurally cannot represent a
KEP section that discusses multiple distinct rejected alternatives, so it
was a coin-flip whether the card's single point matched the specific
alternative pick_quote() happened to extract as ground truth. Added
distill_rationale_card_multi() (mine_decisions.py, additive, revert_pair
untouched) allowing up to N short paraphrased points, one per genuinely
distinct alternative named in the source. Regenerated all 19
kep_alternatives cards uniformly (not cherry-picked), rebuilt the card
index, re-ran structured generation for those 19, re-graded all three
conditions fresh (111 judge calls). Ran twice: first with a 3-point cap
(structured 68% -> 78% combined, KEP subset 42% -> 63%), then uncapped to
6 points after the user asked to push further (auth-5681's ground truth
turned out to reference a 4th alternative the 3-point cap had cut) — the
uncapped run produced byte-identical aggregate numbers (78%/63%), a real
plateau, not a bug: the remaining failures were spot-checked and include
at least one (api-machinery-2876) where the ground-truth quote isn't about
a rejected alternative at all but a scoping/sequencing rationale, which no
amount of card content can match without touching pick_quote() — an
explicit non-goal, correctly left alone. Kept the uncapped version as
final since it's more methodologically complete even though it didn't
move this benchmark's score. rag/code_only confirmed untouched via file
mtimes both rounds. 115/115 leakage tests pass. Final: code_only 3%, rag
57%, structured 78% combined, n=37, verdict CAUTION (unchanged threshold:
needs >=85%). This is now genuinely the ceiling of the card-content lever;
further improvement would need a larger n or a different mechanism, not
another prompt iteration. HANDOFF.md and README.md still need updating to
this final number (README specifically, out of every entry's file scope
so far — flagged repeatedly, not yet done).

Nothing committed or pushed.

## Write the Devpost architecture-diagram handoff doc (opened 2026-08-18)

Objective: write `decision-trace/docs/ARCHITECTURE_DIAGRAM_HANDOFF.md` — a
resume-point handoff for a fresh session to build a beautifully-designed,
standalone visual architecture diagram for the Devpost "Architecture
Diagram" upload field, mirroring the approach used for the sibling Custody
project this session (`custody/docs/ARCHITECTURE_DIAGRAM_HANDOFF.md`, and
the iterative design work that produced `custody/web/system-diagram.html`).
This entry covers writing the handoff doc only — not building the diagram
itself, not touching app code, not deploying anything.

Branch: explore/decision-trace-v0
Parent: HEAD (same branch/commit state as the active falsifier-confound
entry above; this is an independent, unrelated docs-only addition and
does not depend on that work landing first)

Allowed files:
- decision-trace/docs/ARCHITECTURE_DIAGRAM_HANDOFF.md (new)
- decision-trace/.claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not touch `docs/architecture.md` (the existing Mermaid diagram) —
  it stays as the GitHub-native technical reference, same rule as Custody.
- Do not touch `app/*.py`, `.streamlit/config.toml`, README.md, or any
  other file — this session only writes the handoff markdown.
- Do not build the diagram HTML/SVG itself in this entry — that's the
  fresh session's job, per the handoff doc's own instructions.
- Do not invent components, model names, or Google Cloud services not
  already verified in README.md / docs/architecture.md / app/*.py.

Baseline: N/A (docs-only, no code under test).

Acceptance gates:
1. The handoff states the real, already-established design tokens
   (`.streamlit/config.toml` + `_THEME_CSS` in `app/ui.py`) verbatim, so
   the fresh session copies real hex values instead of inventing a new
   palette — same "paper" family already used in Custody, confirmed by
   direct file read this session.
2. The handoff lists every real component from `docs/architecture.md`'s
   Mermaid diagram (UI, collaborate.answer, retrieval.DecisionIndex,
   graph.resolve_active, memory.propose_reconsideration,
   FirestoreDecisionStore, Firestore, Vertex AI/Google GenAI SDK,
   gemini-3.7-flash, text-embedding-005, Cloud Run, ingest.py) as the
   required diagram content — nothing invented, nothing dropped.
3. The handoff encodes the concrete design lessons learned building
   Custody's diagram this session (see "Design lessons" section below,
   written into the doc): build the real topology first with labeled
   arrows, not a stacked list of section headings; do not wrap the whole
   thing in one giant box or add numbered 1-N step badges — those made
   Custody's diagram feel like a slide deck, not an engineering map, and
   were reverted after user feedback; keep generous whitespace; if a
   scope indicator (bracket/tick) is added, verify by the actual x/y
   coordinates that it never geometrically encloses a node it shouldn't
   (this exact bug happened in Custody's diagram and had to be fixed
   twice).
4. The handoff specifies the build method: static HTML + hand-authored
   inline SVG, headless-Chrome screenshot at 3-4x device scale factor,
   exported as PNG under Devpost's 35MB cap — the same reproducible
   pipeline used for Custody, commands included.

Verification: read the finished handoff doc back and confirm every
component name and hex value it cites matches what's actually in
`docs/architecture.md`, `.streamlit/config.toml`, and `app/ui.py` today.

Status: complete

Result: `docs/ARCHITECTURE_DIAGRAM_HANDOFF.md` written this session, all
four gates satisfied (design tokens, component list, design lessons,
build method) — confirmed by the fresh-session read of the doc that
opens the next entry below.

## Build the Devpost architecture diagram (opened 2026-08-18)

Objective: execute `docs/ARCHITECTURE_DIAGRAM_HANDOFF.md` as written — build
the standalone, beautifully-designed static architecture diagram for the
Devpost "Architecture Diagram" upload field. Hand-authored inline SVG in a
static HTML page, screenshotted at high DPI, exported as PNG. This is the
"fresh session" the handoff doc was written for.

Branch: explore/decision-trace-v0
Parent: HEAD

Allowed files:
- decision-trace/docs/system-diagram.html (new)
- decision-trace/docs/exports/system-diagram.png (new, or similar path)
- decision-trace/.claude/SESSION_CONTRACT.md (this entry)

Non-goals (per the handoff doc verbatim):
- Do not touch `docs/architecture.md`'s existing Mermaid diagram.
- Do not touch `app/*.py`, `.streamlit/config.toml`, or any product code.
- Do not invent capabilities/components not verified in README.md /
  docs/architecture.md / app/*.py — no ADK-shaped boxes.
- Do not deploy this page anywhere public; build, screenshot, leave local.
- Do not touch the unrelated in-progress falsifier-confound work (the
  modified `data/decisions.jsonl`, `RESULTS.md`, `data/runs/structured/*`
  from the active entry above) — untouched, unrelated, uncommitted work
  in progress from a separate contract entry.
- No git commit/push without explicit authorization.
- No uploading to Devpost from this session (no browser session/credentials
  established for that yet) — flag the exported PNG as ready for the user
  to upload themselves, unless the user explicitly asks me to drive that
  via browser automation this session.

Baseline: N/A (new standalone asset, no code under test).

Acceptance gates (per the handoff doc's own 6 gates):
1. Every real component listed in the handoff (product code + Google Cloud
   services + the two named models) appears — nothing invented, nothing
   dropped, no ADK-shaped boxes.
2. Visual language matches DecisionTrace's own established tokens
   (`--dt-*` CSS variables, IBM Plex Mono, existing pill colors) — not
   Custody's diagram, not a generic new palette.
3. Reads as real system topology with labeled arrows — not stacked
   section cards, not boxed-and-numbered, not over-collapsed into zones
   that lose spatial relationships (the three Custody mistakes to avoid).
4. Any scope bracket/tick's bounding box is checked against every node's
   bounding box and confirmed not to falsely enclose anything.
5. Exported as static PNG, under 35MB, legible at Devpost's display
   resolution — verified by reading the exported file back.
6. Ready for upload to Devpost's Architecture Diagram field (actual
   upload only if the user explicitly authorizes driving that this
   session).

Verification: read the exported PNG back via the Read tool to visually
confirm no overlapping labels, no text clipped at the image edge, and
correct bracket/box geometry, before calling this done.

Status: complete

Result: `docs/system-diagram.html` (hand-authored inline SVG, no library,
2000x900 viewBox) built and exported to `docs/exports/system-diagram.png`
at 8000x3600px (~913KB, well under the 35MB cap) via headless Chrome at
`--force-device-scale-factor=4`. All 12 real components from the handoff
present (app/ui.py, app/ingest.py, retrieval.DecisionIndex,
graph.resolve_active(), collaborate.answer(),
memory.propose_reconsideration(), the DecisionStore Protocol boundary +
FirestoreDecisionStore, Firestore, Vertex AI, gemini-3.7-flash,
text-embedding-005), plus Browser and GitHub as external nodes — no ADK
boxes. Visual language pulled verbatim from `_THEME_CSS`/`.streamlit/
config.toml` (`--dt-*` hex values, IBM Plex Mono for identifiers). Real
topology with 3 color-coded, labeled edge families (green=read path,
amber=write path, grey=ingest/external), two dashed zone boundaries
(Cloud Run vs Google Cloud) instead of one dominant box, no numbered
badges, no prose legend block (one small two-line caption only). One
scope annotation (`graph.resolve_active()`'s "plain code — no LLM call"
tick) — built as a short line strictly within that node's own x-range
(830-980, inside the node's 810-1000 span) so it cannot geometrically
enclose any other node by construction; confirmed by reading the
rendered PNG back at both preview and full 8000x3600 resolution — no
overlapping labels, no clipped text, tick reads as attached only to
graph.resolve_active(). Two rounds of self-review before finalizing:
first render surfaced a label collision (the amber "write PROPOSED
decision" text overlapped the rotated "DecisionStore Protocol
(interface)" label) and unused canvas whitespace below the content;
fixed by rerouting the Memory→Store arrow around the protocol strip and
trimming the canvas height, then re-rendered clean. Not done this
session: uploading to Devpost (no browser session authorized for that;
the PNG is ready at `docs/exports/system-diagram.png` for the user to
upload themselves).

Status: active

## Tighten pick_quote() for kep_alternatives ground truth (opened 2026-08-18)

Objective: the 78% plateau's remaining failures were inspected in full (all
7, not a sample) — 5 of 7 trace to `RATIONALE_CUES` (generic "because"/
"since"/"instead of") matching a sentence that explains why the CHOSEN KEP
design works, not why an alternative was REJECTED. Concrete evidence: e.g.
`api-machinery-2523`'s "ground truth" is "Disadvantages [of the field] -
...3 options instead of 2" (a disadvantage of the chosen field, not a
rejected alternative); `scheduling-5229`'s is "This prevents race
conditions [in the chosen design] because..." User explicitly authorized
touching `pick_quote()` after seeing this evidence — the one thing every
prior entry in this project refused to touch without it, specifically to
avoid re-defining ground truth after seeing unflattering numbers. This is
the third and intended-to-be-final such authorization.

Branch: explore/decision-trace-v0
Parent: HEAD (the multi-point rationale cards commit-state, still
uncommitted)

Allowed files:
- mine_decisions.py (new REJECTION_CUES tier + pick_quote(require_rejection)
  parameter, additive — RATIONALE_CUES and the no-arg default behavior are
  unchanged, so revert_pair mining via mine_reverts() is untouched)
- reextract_kep_quotes.py (new, one-off — re-extracts rationale_quote for
  the existing 19 kep_alternatives rows from their already-cited source
  file, NOT a re-mine: same 19 decision_ids, no new GitHub search)
- data/decisions.jsonl (rationale_quote + quote_has_rationale_cue fields
  only, kep_alternatives rows; rationale_card, citation, chosen, etc.
  unchanged)
- RESULTS.md (recomputed)
- decision-trace/HANDOFF.md, decision-trace/.claude/SESSION_CONTRACT.md

Non-goals:
- Do not re-mine (no live GitHub search for new decisions) — the 37
  decision_ids stay exactly as they are.
- Do not touch revert_pair's ground truth or mine_reverts() — that arm
  scores 94% and RATIONALE_CUES was never the problem there.
- Do not regenerate rationale_card or re-run structured/rag/code_only
  generation — model responses don't depend on rationale_quote at all
  (only build_query()'s chosen/context fields do, and those are
  untouched), so only re-grading is needed, not re-running conditions.
- Apply re-extraction uniformly to all 19 kep_alternatives rows, not
  cherry-picked to the 5 diagnosed failures.
- No commit/push without separate explicit authorization.

Baseline: RESULTS.md currently reports structured 78% combined (KEP
subset 63%), rag 57%, verdict CAUTION, n=37 — the multi-point-cards
entry's result, confirmed a real plateau under the old ground truth.

Acceptance gates:
1. REJECTION_CUES requires explicit rejection/negative framing
   (rejected/ruled out/dismissed/chose not to/decided against/etc.), not
   generic "because"/"since" — verified by re-reading the regex against
   the 5 concrete examples above.
2. All 19 kep_alternatives rows re-extracted uniformly; rows where no
   rejection-cue sentence exists keep their original quote (documented,
   not silently dropped) rather than forcing a worse pick.
3. Every kep_alternatives rationale_card still not a substring of its
   (possibly new) rationale_quote, asserted at write time.
4. test_no_leakage.py passes in full against the updated decisions.jsonl.
5. RESULTS.md recomputed via a full grade.py re-run (judge isn't cached).
6. Verdict recorded as whatever verdict_for() outputs, unchanged
   thresholds — including if still CAUTION.

Verification: run test_no_leakage.py; read the re-extraction script's own
changed/unchanged/no-pick log; read RESULTS.md back and cross-check every
number; confirm via file mtimes that data/runs/ (all three conditions) was
NOT touched this entry, since responses don't depend on rationale_quote.

Status: complete

Result: First pass of the REJECTION_CUES tier had a real bug of its own —
included a bare "alternative" cue, which matched markdown ATX subsection
headers like "### Alternative: Introduce ExactResourceVersion..." (no
sentence-ending punctuation, so sentences()'s whitespace-collapse glues
the header label onto whatever prose follows it into one contaminated
candidate). Caught by manually reading all 11 changed quotes before
spending the grading budget — several were header fragments, not real
prose. Fixed by adding MARKDOWN_HEADER_LINE stripping (require_rejection
path only) and removing the "alternative"/"in favor of"/"instead of" cues
that were too easily satisfied by labels rather than reasoning. Re-ran:
6 of 19 kep_alternatives quotes changed (9 found no rejection-cue sentence
and safely kept their prior quote per the fallback design, 4 were already
unchanged), all 6 changes hand-verified as genuine on-topic rejection
prose, not header fragments. 115/115 leakage tests pass. data/runs/
confirmed untouched by this entry (responses don't depend on
rationale_quote, only grading does).

Full re-grade (111 calls): structured 76% combined (KEP subset 58%), rag
57%, code_only 0%, verdict CAUTION (unchanged thresholds, needs >=85%).
This is within judge-noise of the prior 78%/63% — a wash, not a
regression: only 6 quotes changed, and LLM-judge grading has inherent
run-to-run variance at this n. The meaningful finding is that three
independent, real bug fixes (confound fix: 46%->68%; multi-point cards:
68%->78%; stricter ground truth: 78%->76%) now all converge on the same
~76-78% band. That convergence is itself evidence this is a genuine,
stable measurement of the approach at n=37, not an artifact of any one
remaining bug. Further movement would need a larger sample or a different
mechanism (e.g. per-alternative retrieval instead of one card per
decision) — flagged to the user as a research question, not something to
keep chasing via more prompt/regex iteration on the same n=37 set.

Nothing committed or pushed.

## Write the per-alternative retrieval handoff doc (opened 2026-08-18)

Objective: this session is getting long (multiple rounds of falsifier
work already this session — confound fix, multi-point cards, stricter
ground truth, all `Status: complete` above). User asked to pursue
per-alternative retrieval as the next lever but explicitly asked for it
to be handed off to a fresh session rather than implemented here. Write
`decision-trace/docs/PER_ALTERNATIVE_RETRIEVAL_HANDOFF.md` — a
resume-point doc, same pattern as
`decision-trace/docs/ARCHITECTURE_DIAGRAM_HANDOFF.md` and
`custody/docs/ARCHITECTURE_DIAGRAM_HANDOFF.md` (sibling project, same
session). This entry covers writing the handoff doc only, not the
retrieval-index change itself.

Branch: explore/decision-trace-v0
Parent: HEAD (the pick_quote()-tightening commit-state above, still
uncommitted)

Allowed files:
- decision-trace/docs/PER_ALTERNATIVE_RETRIEVAL_HANDOFF.md (new)
- decision-trace/.claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not implement the per-alternative retrieval change itself — that's
  the fresh session's job, per the handoff doc's own instructions.
- Do not touch mine_decisions.py, run_conditions.py, rag_index.py,
  data/decisions.jsonl, or RESULTS.md in this entry.

Baseline: RESULTS.md currently reports structured 76% combined (KEP
subset 58%), rag 57%, verdict CAUTION, n=37 — the final, converged result
from this session's three falsifier-fix entries.

Acceptance gates:
1. The handoff states the exact current mechanism (get_card_index() in
   run_conditions.py embeds one whole rationale_card per decision, so
   retrieval picks decisions, not alternatives) and precisely what
   changes (index one embeddable unit per alternative-point, still
   tagged with its parent decision_id, so retrieval can surface the
   specific point a query is about).
2. The handoff gives concrete function signatures/names to add
   (point-splitting helper, per-point card-text renderer, a new point-
   level index, and the one-line swap in run_structured()) so the fresh
   session isn't re-deriving the design from scratch.
3. The handoff is explicit that this is an experiment, not a guaranteed
   win — a larger, more granular pooled index could make retrieval
   *harder* (more distractors) even though each candidate is more
   topically precise — and specifies exactly what evidence would confirm
   or reject the hypothesis (same grade.py re-run, compare structured's
   KEP-subset combined score against the current 58% baseline).
4. The handoff carries forward every open, unresolved item from this
   session: README.md still needs updating to the real 76%/57%/CAUTION
   numbers (out of every prior entry's scope), and the Devpost
   architecture-diagram entry status if still open.

Verification: read the finished handoff doc back and confirm the function
names/signatures it proposes actually match what's in the current
run_conditions.py/rag_index.py/mine_decisions.py (not stale/invented).

Status: complete

Result: docs/PER_ALTERNATIVE_RETRIEVAL_HANDOFF.md written. Every function
name/signature it proposes reusing (card_text, cite_str, CARDS_INDEX_CACHE,
DATA_DIR, get_card_index, run_structured, build_structured_prompt, TOP_K)
verified against run_conditions.py's actual current line-for-line content
via grep before being cited — not invented or stale. Carries forward the
open README.md item and states plainly which three fix rounds are already
done so a fresh session doesn't re-derive or redo them.

Nothing committed or pushed.

## Implement per-alternative retrieval (opened 2026-08-18)

Objective: execute docs/PER_ALTERNATIVE_RETRIEVAL_HANDOFF.md as written —
the fresh session it was written for. Split each decision's rationale_card
into individual alternative-points and index each point separately (still
tagged with its parent decision_id), instead of indexing one whole card per
decision. Swap run_structured() to retrieve from the point-level index.
Re-run structured generation for all 37 decisions and re-grade all three
conditions. User explicitly authorized running this now, including the
real Vertex API cost (37 generation calls + 111 judge calls, same order as
prior rounds).

Branch: explore/decision-trace-v0
Parent: HEAD (the per-alternative-retrieval-handoff-doc commit-state above,
still uncommitted; the falsifier confound fix / multi-point cards /
pick_quote-tightening changes to data/decisions.jsonl and RESULTS.md from
earlier this session are also still uncommitted and are carried forward,
not reverted)

Allowed files:
- run_conditions.py (add split_rationale_points, point_card_text,
  POINTS_INDEX_CACHE, get_point_index; swap run_structured() to use
  get_point_index() instead of get_card_index())
- data/corpus/points-index.json (new cache file — cards-index.json stays
  untouched, kept for rollback/comparison per the handoff's non-goals)
- data/runs/structured/*.json (all 37 regenerated — the handoff is explicit
  every decision needs regenerating this time, not just KEP rows, since the
  retrieval mechanism changed for everyone)
- RESULTS.md (recomputed)
- decision-trace/HANDOFF.md, decision-trace/.claude/SESSION_CONTRACT.md

Non-goals (per the handoff doc verbatim):
- Do not touch pick_quote(), CARD_PROMPT/CARD_PROMPT_MULTI, or
  verdict_for()'s thresholds.
- Do not change TOP_K from 5.
- Do not delete or overwrite data/corpus/cards-index.json.
- Do not touch data/runs/rag/ or data/runs/code_only/ (queries/retrieval
  for those conditions are unaffected by this change).
- No commit/push without separate explicit authorization.

Baseline: RESULTS.md currently reports structured 76% combined (KEP subset
58%, revert_pair subset 94%), rag 57%, code_only 0%, verdict CAUTION, n=37.

Acceptance gates (per the handoff doc's own 6 gates):
1. split_rationale_points() yields one element for single-sentence cards
   and N elements for multi-point cards — spot-checked against 3+ real
   rationale_card values before trusting it on the full set.
2. get_point_index() builds without error; data/corpus/points-index.json is
   new, cards-index.json is untouched (byte-identical).
3. run_structured() swapped to the point index; all 37 decisions'
   structured runs regenerated (old files deleted first, every one
   regenerates, not just KEP rows).
4. Full grade.py re-run (111 calls, judge isn't cached).
5. test_no_leakage.py still passes in full.
6. RESULTS.md's kep_alternatives-subset combined score recorded and
   compared against the 58% baseline — whatever it is, including if worse.

Verification: spot-check split_rationale_points() against 3+ real cards;
confirm cards-index.json unchanged (checksum) after the run; run
test_no_leakage.py; read RESULTS.md back and cross-check every number
against the new data/runs output; confirm data/runs/rag and
data/runs/code_only untouched via file mtimes.

Status: complete

Result: All 6 acceptance gates satisfied. `split_rationale_points()`
verified against 3 real cards (a 6-point KEP card, a 3-point KEP card, and
a single-sentence revert_pair card) before trusting it on the full set —
multi-point cards split correctly on "- " lines, single-sentence cards
yield exactly one unchanged element. `get_point_index()` built
`data/corpus/points-index.json` (new, 1.59MB) without error;
`data/corpus/cards-index.json` confirmed byte-identical before/after
(md5 839cbe1376d8e9c137798ff3562c7f01, unchanged). `run_structured()`
swapped to `get_point_index()`; all 37 structured runs regenerated (old
files deleted first, confirmed 37/37 present after). `data/runs/rag` and
`data/runs/code_only` confirmed untouched two ways: aggregate md5 of all
their files unchanged, and per-file mtimes ~45 hours old, predating this
entry entirely (run_conditions.py's `if not out.exists()` guard correctly
skipped them). test_no_leakage.py: 115/115 pass, both before and after.
Full grade.py re-run (111 judge calls) completed cleanly.

**Result: a clean null.** structured combined 76%, revert_pair subset 94%,
kep_alternatives subset 58% — byte-identical to the pre-experiment
baseline in every aggregate number. Retrieval granularity was not the
bottleneck: splitting multi-point cards into separately-indexed points and
doubling the pooled index size (60-90 points vs 37 cards, same TOP_K=5)
did not change which content reached the model's prompt for these
queries. Documented as a dedicated section in RESULTS.md ("Per-alternative
retrieval experiment (2026-08-18) — null result") rather than silently
folded into the unchanged headline table, so the experiment and its
negative result are traceable. This closes the retrieval-granularity
lever: per the handoff doc's own acceptance framing, a real result
including "if it's worse" was to be recorded, not chased further — "no
change" is exactly as informative here, and further movement on the
kep_alternatives 58% ceiling needs a larger n or a genuinely different
mechanism, not another indexing-granularity iteration on this n=37 set.

Encountered and fixed along the way (infra, not code): `CLOUDSDK_CONFIG`
needed to point at `$PWD/../.gcloud` (one level above the repo root, a
symlink to `custody/.gcloud`), not `$PWD/.gcloud` inside decision-trace/
— the first generation attempt failed with `DefaultCredentialsError`
before any Vertex calls succeeded; corrected and reran cleanly, matching
the path documented in HANDOFF.md's own app/ test commands.

`run_conditions.py` now calls `get_point_index()` as the live default
(the code change from this entry, not reverted) — RESULTS.md documents
that reverting to `get_card_index()` is a one-line change if a future
session prefers the simpler whole-card mechanism, now that per-point
retrieval is confirmed not to help either way.

Nothing committed or pushed (no authorization given this entry).

## Update README.md's stale benchmark claim (opened 2026-08-18)

Objective: README.md's "Why not just RAG?" section still states the
original, debunked "100% vs 57%, GO" claim from before this session's
three falsifier fix rounds. Every one of those entries flagged this as
out-of-scope and outstanding. External review (via the user) independently
flagged the same stale claim as DecisionTrace's single biggest Devpost
liability. Update it to the real, converged, honest numbers.

Note: a separate, concurrently-active session
("Implement per-alternative retrieval") may change RESULTS.md's numbers
again later. This entry uses the latest numbers on disk as of now (RESULTS.md
mtime 2026-08-18 14:41, nothing from that other entry has run yet — no
data/corpus/points-index.json, no process running). If those numbers change
later, README needs one more quick follow-up edit; not blocking on
speculative future work from a parallel session.

Branch: explore/decision-trace-v0
Parent: HEAD

Allowed files:
- decision-trace/README.md ("Why not just RAG?" section only — one
  paragraph, one table, one sentence in the opening description)
- decision-trace/.claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not touch any other README section (spin-up, deploy, project layout,
  etc.) — those weren't flagged as stale.
- Do not touch RESULTS.md, data/decisions.jsonl, or any code — this is a
  docs-only claim correction using numbers that already exist.
- No commit/push without separate explicit authorization.

Baseline: README currently states structured 100%, rag 57%, "GO" framing.
RESULTS.md currently states structured 76%, rag 57%, code_only 0%,
verdict CAUTION, n=37 (per-source: revert_pair 94%, kep_alternatives 58%).

Acceptance gates:
1. The claims table matches RESULTS.md's top-level numbers exactly (76% /
   57% / 0%), not rounded up or softened past what the data says.
2. The surrounding prose states the CAUTION verdict honestly (doesn't clear
   the preregistered 85% GO bar) rather than implying a clean win.
3. The "measured, rather than assumed" framing stays truthful — it should,
   since this session did run three real, verified re-measurements.
4. No invented statistics — every number traces directly to RESULTS.md.

Verification: read the updated README section back and diff every number
against the current RESULTS.md by hand.

Status: complete

Result: "Why not just RAG?" section rewritten. Every number
(14/14/0/8 code_only, 76/59/57/3 rag, 100/76/76/0 structured, 94%
revert_pair subset, 58% kep_alternatives subset n=19) verified against
RESULTS.md's current table by direct side-by-side comparison, byte-for-
byte match. States the CAUTION verdict and the 85% bar it didn't clear
honestly, explains the KEP-subset drag mechanism, and names the
per-alternative-retrieval hypothesis as the open next step rather than
hiding it. Opening description's "measured, rather than assumed" line
updated to mention the three-round fix history instead of implying a
single clean measurement.

Nothing committed or pushed.

## Strengthen the demo script (opened 2026-08-18)

Objective: per external review (via user), sharpen docs/DEMO_SCRIPT.md so
the state-change/persistence moment is unmissable, since that's what
separates DecisionTrace from "sophisticated RAG chatbot" — the
organizers' own stated failure mode to avoid. Review also suggested
adding an agent-led clarifying-question interaction; checked
app/collaborate.py first — it's explicitly scoped to answer, never ask
(BUILD_SCOPE §12/§16, "five question classes... not a general chat"), so
that suggestion is not implemented: scripting a capability the product
doesn't have would be the exact kind of overclaim this project's own
discipline exists to prevent. Also found and fixed the same stale
100%/57% claim in the script's 0:30-1:00 segment that README had.

Branch: explore/decision-trace-v0
Parent: HEAD

Allowed files:
- decision-trace/docs/DEMO_SCRIPT.md
- decision-trace/.claude/SESSION_CONTRACT.md (this entry)

Non-goals:
- Do not add a clarifying-question feature to app/collaborate.py or
  app/memory.py — out of scope, and see above for why it wasn't scripted.
- Do not touch the timing plan's overall 4-minute structure or the
  Google Cloud proof segment's content, only make its already-strongest
  moment mandatory instead of hedged.
- No commit/push without separate explicit authorization.

Baseline: docs/DEMO_SCRIPT.md's 0:30-1:00 segment stated "100%" and "57%"
(the pre-fix numbers); step 3 of the backend-proof segment was marked
"(Strongest cut, if time allows)" despite the script's own text calling
it "the actual proof."

Acceptance gates:
1. The falsifier numbers in the script match RESULTS.md exactly, same as
   the README fix (76%/57%, CAUTION).
2. The Cloud Run restart / fresh-session persistence step is no longer
   hedged as optional — it's the step that proves durable state, and per
   the review this session incorporated, it's the single most important
   beat against a judge reading this as "just RAG with extra UI."
3. No new capability is scripted that isn't real and evidenced in the
   current app code.

Verification: read the updated script back; diff its numbers against
RESULTS.md; confirm nothing added references a code path that doesn't
exist in app/collaborate.py or app/memory.py.

Status: complete

Result: falsifier numbers corrected to 76%/57%/94% (revert-pair subset),
verified against RESULTS.md. Step 5 (record reconsideration) now
explicitly narrated as the "memory actually changes" differentiator. Step
3 of the Cloud Run proof segment changed from "(Strongest cut, if time
allows)" to "Do not cut this step for time," with an explicit note that
every other beat could in principle be faked by a good retrieval demo but
this one requires a real write surviving a real process boundary.
Clarifying-question suggestion from the review explicitly not
implemented — checked app/collaborate.py first, confirmed it's scoped to
answer-only (BUILD_SCOPE §12/§16), so scripting it would overclaim a
capability that doesn't exist.

Nothing committed or pushed.

## Find the mechanism behind the falsifier's 76% plateau (opened 2026-08-21)

Objective: determine the actual root-cause mechanism of the 9 remaining
structured failures, by tracing each one from live source section ->
ground-truth quote -> rationale_card -> retrieved points -> realized
prompt -> generated answer -> judge verdict. Then decide on that evidence
alone whether the `kep_alternatives` half of the benchmark measures the
system or mismeasures it, and only if it mismeasures, preregister and run
a corrected v2. The score is not allowed to select the conclusion.

Branch: research/decisiontrace-plateau
Parent: 1c33d3d (cut from the frozen submission commit; never merged back,
never deployed)

Allowed files: BENCHMARK_FAILURE_AUDIT.md, BENCHMARK_V2_SPEC.md,
RESULTS_V2.md, data/v2/**, data/runs_v2/**, and the new v2-only scripts
build_v2_cases.py, run_conditions_v2.py, grade_v2.py,
test_no_leakage_v2.py, audit_v0_failures.py. Plus this file and the
repo-root contract.

Non-goals: no deploy, no merge, no push. No mutation of any v0 artifact
(RESULTS.md, decisions.jsonl, data/runs/**, mine_decisions.py,
run_conditions.py, grade.py, test_no_leakage.py, rag_index.py, vertex.py).
No change to verdict_for()'s thresholds. No app/** changes. No repeat of a
closed lever (chunk size, embedding model, TOP_K, retrieval granularity).

Baseline: HEAD == 1c33d3d, decisions.jsonl == 37 rows,
`pytest test_no_leakage.py -q` == 115 passed, RESULTS.md == structured 76%
(28/37), rag 57%, code_only 0%, verdict CAUTION.

Acceptance gates:
1. All 9 structured failures and all 19 KEP rows classified against the
   live source, one named primary cause each, with totals.
2. Every claim about a KEP's Alternatives section checked against the live
   document, not inferred from the card or the quote.
3. If v2 is built, its spec is committed before the first v2 generation
   call, its cases derive from one uniform structural rule, and a
   structural dry run reports counts and exclusions before any spend.
4. test_no_leakage_v2.py proves no condition's prompt carries its own
   grading rationale, for every case.
5. `git diff 1c33d3d --stat` shows only new files plus the contracts.

Verification: `git diff 1c33d3d --name-status` read by hand for v0
mutations; `pytest test_no_leakage.py test_no_leakage_v2.py -q`;
`git stash list` still shows the parked hardening-branch work; final report
gives numerator/denominator for every score and the verdict from the
unchanged verdict_for().

Status: complete

Result: the 76% plateau was benchmark semantics, not capability. Of the 9
structured failures, 7 are benchmark-label or task mismatch (4 targets that
are not a rejected-alternative rationale at all, 3 that are one arbitrary
target among several the broad query equally invites), 2 are card coverage,
and 0 are retrieval, generation or judge noise as a primary cause. In all 9
the model used every card point it was given, naming a mean of 4.4 real
rejected alternatives per failing KEP answer and scoring zero for all of
them.

Two mining defects found and reproduced by audit_v0_failures.py:
ALTERNATIVES_SECTION_RE is unanchored, so on KEP-1205 it matched the last
two hashes of a level-5 heading and ran 6914 characters into Design
Details, where the target was then picked on the word "rejected" meaning
HTTP requests were rejected; and reextract_kep_quotes.py keeps the old
loose-regex quote whenever no rejection-cue sentence is found, so the
round-3 fix reached 10 of 19 rows, not 19.

v2 rebuilt the KEP arm as one targeted question per named alternative, 83
cases over 33 decisions, preregistered before any generation. It returned
structured 99% and a GO that turned out to be a near-tautology: 83 cards
for 83 cases, own card at rank 1 in 82 of 83. v2.1 rebuilt the store by
unsupervised ingestion (108 records, no sight of the question list) and
structured fell to 87%. v2.2 then removed a handicap on the other arm:
run_rag had indexed the answer-bearing document as {"id": "TARGET"} while
every decoy kept its real identifier, so RAG could not cite the one
document that mattered. Relabelling it moved RAG's KEP citation from 49%
to 95%.

Final, both arms fair: rag_labelled 89% (74/83), structured_ingested 87%
(72/83), code_only 10% (8/83). verdict_for() returns CAUTION, one point
below KILL. The structured-versus-RAG advantage this falsifier exists to
demonstrate is not demonstrated; v0's apparent gap was two artifacts
pointing in opposite directions.

v0 is byte-identical to 1c33d3d. Leakage gates 456 passed. Committed on
research/decisiontrace-plateau through ddada00. Nothing merged, pushed or
deployed.
