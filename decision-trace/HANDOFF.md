# DecisionTrace — handoff for a new session

Written 2026-08-17. Read this before doing anything else here. This is a
resume point, not a status report to skim — the next session should be
able to act on it without re-deriving anything.

## Where things stand

**The MVP is built, tested, and demo-verified. Nothing is deployed and no
submission package exists yet.** Those are two different kinds of "done" —
don't conflate them.

- Branch `explore/decision-trace-v0`, commit `a62f20a`, pushed to
  `origin/explore/decision-trace-v0`. Not merged anywhere, no PR open.
- `decision-trace/BUILD_SCOPE.md` is the frozen spec. `decision-trace/
  RESULTS.md` is the frozen falsifier result (n=37: structured decision
  memory 100% combined-correct vs. embedding RAG 57%, gap concentrated in
  long template-structured documents — a real, explained mechanism, not an
  unexplained score gap). Neither should be edited; they're the evidence
  trail for why this product exists.
- `decision-trace/app/` is the product: `models.py`/`graph.py` (domain
  model + deterministic lifecycle resolver), `store.py`/`loader.py`
  (storage abstraction + benchmark loading), `retrieval.py` (card-level
  embedding search), `collaborate.py` (Gemini answers, four-way claim
  categorization), `memory.py` (conversational candidate-decision
  creation), `ui.py` (Streamlit), `ingest.py` (live GitHub/KEP discovery +
  extraction). All 8 BUILD_SCOPE stages complete.
- 30/30 tests passing (`decision-trace/app/tests/`), all real API calls,
  no mocks. The full 9-step demo acceptance test (ask why → recover
  history → surface the revert → state current status → record a
  reconsideration → **genuine process kill** → **genuine fresh process** →
  confirm the candidate persists and shapes the answer) passed live
  through the actual UI, not just in tests.
- One real bug was found and fixed along the way (Stage 6): a `PROPOSED`
  candidate briefly read as "currently active" before being accepted.
  Fixed in `retrieval.py`'s `is_current`, covered by a regression test.
  Worth knowing this class of bug exists (lifecycle status vs. graph
  topology can diverge for isolated nodes) if you touch `graph.py`/
  `retrieval.py` again.

## What's explicitly NOT done

1. ~~No Cloud Run deployment.~~ **Done (2026-08-17).** Live at
   https://decision-trace-742122658452.us-central1.run.app (service
   `decision-trace`, project-988bc9fe-092c-4b32-90c, us-central1),
   running against `FirestoreDecisionStore`. Verified live in a real
   browser, not just curl: the k8s delayed-preemption revert scenario
   works end-to-end on the deployed instance (Gemini answer, claim
   categorization, resolved current-decision card, evidence citations).
   Detail in `.claude/SESSION_CONTRACT.md`. It's public
   (`--allow-unauthenticated`), which is what judges need but worth
   knowing before writing anything sensitive into the shared
   `decisiontrace-decisions` Firestore collection.
2. ~~No Firestore.~~ **Done (2026-08-17).** `FirestoreDecisionStore` is
   implemented in `store.py` against the real `project-988bc9fe-092c-4b32-
   90c` Firestore Native DB, proven with a real (non-mocked) round-trip
   test in `test_store.py` and a manual fresh-process/fresh-client smoke
   test. `ui.py` uses it when `DECISIONTRACE_STORE=firestore` is set;
   `JSONFileDecisionStore` stays the local-dev default. `google-cloud-
   firestore` is now recorded in `app/requirements.txt`. Full suite:
   31/31. Detail in `.claude/SESSION_CONTRACT.md`.
3. ~~No ADK.~~ **Not needed (2026-08-17).** GenAI SDK (`google-genai`,
   already used throughout `vertex.py`) is one of the four frameworks the
   rubric names explicitly as satisfying its "Google Agent Framework"
   requirement — confirmed directly from the Devpost rules page, not
   assumed. ADK evaluation is no longer a gap.
4. **Submission package: 3 of 4 pieces done (2026-08-17).** `README.md`
   (judge-facing pitch, falsifier table, live URL, spin-up + deploy
   instructions), `docs/architecture.md` (Mermaid diagram matching real
   components), `docs/DEMO_SCRIPT.md` (timed ~4-minute script for the 9
   proven steps, including the "backend proof on Google Cloud" segment
   the rubric asks for). **Still missing: the actual video recording** —
   that needs a human doing screen capture + narration, which isn't
   something this session can produce; the script is ready to record
   from. Devpost submission text itself also still needs writing/pasting
   into their form.
5. **Live ingestion isn't wired into the UI.** `ingest.py` works and is
   tested (Stage 7), but `ui.py` still loads only from the frozen
   benchmark — deliberately, per BUILD_SCOPE §15's call to keep the judged
   demo off a live-extraction gamble. If judges want to point it at their
   own repo live, that's unbuilt UI wiring on top of an already-working
   backend function.

## Decided next step: deploy to Cloud Run — now confirmed a HARD requirement, not just polish

Pulled the actual rubric from allthingsagentichackathon.devpost.com
(2026-08-17). This changes the priority from "recommended" to "submission
may be ineligible without it":

- **Deadline: August 31, 2026, 5:00 PM PDT.**
- **Judging weights**: Innovation & Operational Utility 40%,
  Architectural Discipline & Tech Stack 30%, Demo & Production Readiness
  30%.
- **Hard tech requirements**: Gemini 3.5+ (via API or Vertex AI — met,
  `vertex.py` uses `gemini-3.7-flash`); at least one Google Agent
  Framework — ADK, **GenAI SDK**, Antigravity SDK, or GenKit (likely
  already met: `vertex.py` uses `google-genai`, the GenAI SDK, but this
  hasn't been explicitly cross-checked against the submission rules'
  exact definition — verify before assuming); **at least one Google
  Cloud infrastructure service — Cloud Run, Cloud SQL, Firestore, GKE, or
  Pub/Sub. Currently ZERO of these are used.** Vertex AI (the Gemini API
  transport) does not count toward this — it's a named, separate bucket.
- **Submission requirements**: a hosted project URL (not a repo link — an
  actual running deployment), a ~4-minute demo video that shows "backend
  proof on Google Cloud," an architecture diagram, and a README with
  spin-up instructions. None of these exist yet.

**Net: the technical build is done, but as of 2026-08-17 this submission
does not meet the tech-stack eligibility bar and has none of the required
submission artifacts.** Deploying to Cloud Run isn't just the
highest-leverage next step, it's likely required for the submission to be
judged at all, since it's the natural way to close both the missing-infra-
service gap and the missing-hosted-URL gap in one move.

**Concrete next actions, in order:**
1. ~~Containerize and deploy to Cloud Run~~ **Done (2026-08-17).** Live URL
   above. Local `docker build` doesn't work on this dev machine (host
   networking limitation — `docker run hello-world` fails identically),
   so deploys must go through `gcloud run deploy --source .` (remote
   Cloud Build), not local `docker build`/`push`.
2. ~~Do the Firestore swap now~~ **Done (2026-08-17).** `FirestoreDecisionStore`
   exists, is tested against real Firestore, and `ui.py` uses it when
   `DECISIONTRACE_STORE=firestore` is set. Remaining: Cloud Run's container
   entrypoint needs to actually set that env var (step 1) so the deployed
   app doesn't silently fall back to the ephemeral local JSONL store.
3. Verify the GenAI SDK usage in `vertex.py` actually counts as the
   required "Google Agent Framework" under the hackathon's specific
   definition — don't assume, check the rules page or ask organizers if
   ambiguous. If it doesn't count, evaluate ADK as a fallback.
4. Write the required submission artifacts: architecture diagram, README
   with spin-up instructions, ~4-minute demo video showing the same
   9-step scenario already proven in Stage 8 plus visible backend proof
   on Google Cloud (the deployed Cloud Run URL + Firestore console),
   submission text description.
5. ~~Gemma bonus integration~~ **Tried and killed (2026-08-17), don't
   retry without checking budget first.** Gemma isn't a serverless Vertex
   endpoint (404 across every region/model-name tried — self-host-only,
   real GPU cost) and isn't on the Gemini API's free tier (only Gemini
   2.5 Flash/Flash-Lite are free as of this check; confirmed real
   `gemma-4-26b-a4b-it`/`gemma-4-31b-it` model names exist and a scoped
   API key authenticated correctly, but every call failed with `429:
   prepayment credits depleted` — Gemma needs its own paid AI Studio
   credits, separate from Vertex billing). User has no budget. The API
   key created during the attempt was deleted
   (`gcloud services api-keys delete`, confirmed via the response's
   `deleteTime`); no cost was incurred; no code was written. Skip this
   line item — every mandatory rubric requirement is already met without
   it, it was bonus-only.
6. **ADK not needed** — GenAI SDK (`google-genai`, already used
   throughout) is one of the four frameworks the rubric names explicitly,
   confirmed directly from the Devpost rules page. No fallback required.
7. Deadline: August 31, 2026, 5:00 PM PDT. Budget accordingly — steps 1-2
   are infra work with real failure modes (IAM, quotas, cold starts),
   don't leave them for the last few days.

## How to resume work

**Credentials/environment**, same as throughout this whole search:
```bash
cd /run/media/Yatsuiii/Windows-SSD/custody-search-2/decision-trace
export CLOUDSDK_CONFIG="$PWD/../.gcloud"   # symlinked ADC config
```
`.gcloud` and `decision-trace/.venv` are both gitignored — neither is in
the pushed branch. `.venv` needs recreating (`uv venv .venv --python 3.13
&& uv pip install --python .venv/bin/python google-genai numpy streamlit
pytest`) if this is a fresh checkout. `.gcloud` is a symlink to
`/run/media/Yatsuiii/Windows-SSD/custody/.gcloud` — if that original
checkout isn't present, credentials need to be re-established some other
way (gcloud auth, or wherever this account's ADC lives).

**Run the tests** (confirms nothing broke, ~5 min, real API calls):
```bash
CLOUDSDK_CONFIG="$PWD/../.gcloud" .venv/bin/python -m pytest app/tests/ -v
```

**Run the UI locally**:
```bash
CLOUDSDK_CONFIG="$PWD/../.gcloud" .venv/bin/streamlit run app/ui.py \
  --server.headless true --server.port 8765
```
First load takes ~30s (embeds all 55 benchmark decisions once, then
caches to `app/data/card_embeddings.json`, gitignored — regenerates on a
fresh checkout).

**Falsifier artifacts are frozen** — `RESULTS.md`, `data/decisions.jsonl`,
`data/runs/`, and the pipeline scripts (`mine_decisions.py`,
`build_corpus.py`, `rag_index.py`, `run_conditions.py`, `grade.py`,
`vertex.py`, `gh_util.py`) should not be edited. `data/corpus/` (93MB RAG
decoy pool) was deliberately excluded from git — regenerate via
`build_corpus.py` only if you need to re-run the falsifier itself, not for
normal product work.

## Session-contract discipline, if you're an agent picking this up

This whole build followed strict evidence-gated staging: one capability
per session-contract update, stop-and-verify after each, real tests
before claiming done, checksums confirming frozen files stay frozen. Keep
doing that for Cloud Run deployment too — it's a new capability (infra),
deserves its own contract scoped to `decision-trace/` deployment config
only, with the same non-goals (don't touch falsifier artifacts, don't
touch Custody's `feat/memory-provenance`, don't touch
`failure-mining/AutomationBench`).
