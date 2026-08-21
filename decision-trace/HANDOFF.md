# DecisionTrace — handoff for a new session

Written 2026-08-17. Read this before doing anything else here. This is a
resume point, not a status report to skim — the next session should be
able to act on it without re-deriving anything.

## Update (2026-08-18): the falsifier confound fix is done, numbers changed, README is now stale

**The "100% vs 57%, GO" claim everywhere below and in README.md is
outdated. Do not cite it.** `docs/FALSIFIER_CONFOUND_HANDOFF.md` documented
a real confound in the original benchmark; that fix is now fully applied
and verified (all 6 acceptance gates checked directly, 115/115 leakage
tests pass, full detail in `.claude/SESSION_CONTRACT.md`'s "Apply the
falsifier confound fix" entry, now `Status: complete`).

While verifying the fix, a second, separate bug was found and fixed: the
first post-fix run had structured collapsing to 0% rationale-match on all
19 KEP-sourced decisions specifically, dragging the overall combined score
to 46%. Root cause was in `mine_decisions.py`'s card-distillation prompt,
not a capability limit — it asked "why was `{chosen}` rejected" for every
decision, a false premise for KEP records where `chosen` is the proposal
that *won*, and separately truncated long KEP files before reaching the
`## Alternatives Considered` section it needed to read. Fixed both; see
the session contract entry for the full diagnosis.

**Update again, same day**: that 68% was itself improved further. All 11
of the then-remaining KEP failures had 0% hallucination and 100% correct
citations — the model wasn't wrong, a one-sentence card just structurally
can't represent a KEP section that names multiple distinct rejected
alternatives. Added `distill_rationale_card_multi()` (mine_decisions.py)
to let a card carry one point per real alternative instead of collapsing
them into one lossy sentence. Applied uniformly to all 19 KEP rows (not
cherry-picked), re-ran and re-graded fresh. Tried a 3-point cap first
(68% -> 78%), then uncapped it to 6 after finding one case referenced a
4th alternative the cap had cut — the uncapped run landed on the exact
same aggregate number, a genuine plateau: remaining failures were
spot-checked and at least one is a case where the ground-truth quote
isn't about a rejected alternative at all (a scoping rationale for the
chosen approach), which is a `pick_quote()` ground-truth issue, not
something more card content can fix — and touching `pick_quote()` is an
explicit non-goal. Full diagnosis in `.claude/SESSION_CONTRACT.md`'s
"Multi-point rationale cards" entry.

**Update a third time, same day**: user pushed back on 78% and asked to
"think harder." Reading all 7 remaining failures (not a sample) in full
found that 5 of 7 traced to `pick_quote()`'s `RATIONALE_CUES` regex — it
matches generic words ("because"/"since"/"instead of") that fire just as
often on prose justifying the CHOSEN KEP design as on prose rejecting an
alternative. Concrete example: `api-machinery-2523`'s "ground truth" quote
was "Disadvantages [of the chosen field]... 3 options instead of 2" — not
a rejected alternative at all. This is a real extraction-precision bug,
not p-hacking bait, but fixing it means touching `pick_quote()`, which
every entry before this one explicitly refused to do without new,
explicit authorization (to prevent redefining ground truth after seeing
unflattering numbers). User authorized it after seeing the evidence.
Added a stricter `REJECTION_CUES` tier (`require_rejection=True`,
additive — default behavior for `revert_pair` mining is byte-identical).
First attempt had its own bug (a bare "alternative" cue matched markdown
subsection headers like "### Alternative: X", which have no
sentence-ending punctuation and got glued onto following prose) — caught
by manually reading all 11 changed quotes before spending any grading
budget, then fixed by stripping header lines and dropping the too-broad
cues. Re-extracted ground truth for the existing 19 `kep_alternatives`
rows only (no re-mining, no new decisions) — 6 of 19 quotes actually
changed, 9 found no qualifying sentence and safely kept their prior quote.

**Current, final, freshly re-judged numbers** (RESULTS.md, 2026-08-18):

| Condition | Combined (citation + rationale) |
|---|---|
| code_only | 0% |
| rag | 57% |
| structured | 76% |

76% is within judge-noise of the prior 78% (only 6 quotes changed; an
LLM judge has real run-to-run variance at this n) — a wash, not a
regression. **The meaningful finding is convergence**: three independent,
real bug fixes — confound fix (46%), multi-point cards (68% -> 78%),
stricter ground truth (78% -> 76%) — all land in the same ~76-78% band.
That stability across three different fixes is itself evidence this is a
genuine measurement of the approach at n=37, not an artifact of any one
remaining bug. **Verdict is CAUTION, not GO** — `verdict_for()`'s bar
needs structured>=85%. The threshold was never touched. Further movement
now needs a larger sample or a different mechanism (e.g. per-alternative
retrieval instead of one card per decision), not another round of prompt
or regex tuning against this same n=37 set — flagged to the user as a
research question, not pursued further here.

**Action needed, not yet done**: README.md's Architecture section still
states the old "100% vs 57%, GO" framing (that file was out of every
entry's allowed-files scope so far). It needs to be updated to the real
76%/57%/CAUTION numbers before any Devpost submission text is written
that cites this benchmark — writing marketing copy off the stale number
would be a false claim to judges.

## Update (later 2026-08-17): decision-card bug fixed, UI restyled, live-ingest actually works in prod

Everything below this note was true earlier in the day; several things it
lists as "done" had real gaps that got fixed in a later session the same
day. Full detail in `.claude/SESSION_CONTRACT.md`'s later entries;
summary:

- **Real bug found and fixed**: the "Current decision" card was driven by
  raw embedding retrieval, not by what the model actually answered — a
  missing/uncertain answer could still show a confident-looking card next
  to it, contradicting the product's own "resolved current-decision, not
  a document dump" pitch. Fixed via `grounded_decision_id()` in `app/ui.py`.
- The `kep-keps-sig-storage-1979-object-storage-support` benchmark entry
  (real, verbatim, correctly graded in RESULTS.md, but its "rationale" is
  literal unfilled KEP-template boilerplate) is excluded from the live
  demo at seed time only — `data/decisions.jsonl` and `RESULTS.md` are
  untouched and byte-identical.
- UI restyled (`.streamlit/config.toml` + CSS in `app/ui.py`) — paper
  palette, mono decision ids, status pills — replacing default Streamlit
  chrome, which read as generic/unpolished.
- **Live ingest was silently broken in production this whole time**:
  `app/ingest.py` shells out to the `gh` CLI, which was never installed
  in the Docker image — it only ever worked in local testing. Fixed:
  pinned `gh` binary added to `Dockerfile`, plus a fine-grained
  read-only GitHub PAT (public repos only, no write scopes) provisioned
  as a Cloud Run secret and granted to the service's runtime account.
- All of the above is deployed and verified live, not just locally:
  current production revision `decision-trace-00004-lxh`. Manually
  clicked "Ingest" against `kubernetes/kubernetes` on the actual
  production URL and got "Ingested 4 decision(s)" — the operational-
  utility gap a judge previously docked this submission for is now
  provably real in production, not just in local dev.
- Stale Firestore document for the excluded KEP-1979 entry (left over
  from earlier smoke-test sessions) was deleted directly from the
  `decisiontrace-decisions` collection.

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
5. ~~Live ingestion isn't wired into the UI.~~ **Done (2026-08-17).**
   `ui.py` now has a "Live ingest" sidebar panel (repo text input + max-
   candidates control + Ingest button) that calls `ingest_repo()` for
   real and adds the resulting decisions to the session's store.
   Confirmed manually end-to-end through the actual browser UI (not just
   a script): ingesting `kubernetes/kubernetes` added 4 real KEP-sourced
   decisions, and asking "Why configure the max CrashLoopBackOff delay?"
   afterward correctly surfaced the freshly ingested `KEP-5593` decision
   as the current active decision, citing its real evidence URL. The
   judged demo's core 9-step script still runs off the frozen benchmark
   (that's the scenario with a known, repeatable answer); live ingest is
   additive, for judges who want to try their own repo, capped at a
   small default candidate count to keep runtime bounded.

## Failure-path test coverage added (2026-08-17)

A judge re-review docked Architectural Discipline for a happy-path-only
suite. Added `app/tests/test_failure_paths.py` (7 tests, the project's
first deliberate use of mocks — for the specific failure conditions that
can't be forced on a real API on demand; everything else in the call path
stays real, per house convention):

- Gemini timeout/error during collaboration (`collaborate.answer`) and
  during ingestion extraction (`ingest.extract_decision_fields`) both
  propagate as a clear exception rather than being swallowed into a
  fabricated answer.
- Malformed/unparseable Gemini extraction output defaults to a predictable
  "(untitled)"/empty-fields shape rather than crashing or fabricating.
- **Real bug found and fixed**: `extract_decision_fields` didn't validate
  that `rejected_alternatives`/`constraints` came back as JSON arrays — a
  malformed response returning a bare string for either field passed
  straight through into `Decision`, where `retrieval.render_card`'s
  `'; '.join(...)` would silently iterate over the string's characters
  instead of failing or defaulting cleanly. Fixed with `ingest._as_str_list`,
  which coerces to `list[str]` or defaults to `[]`. Covered by a
  regression test.
- An incomplete revert-PR candidate (missing required upstream fields)
  raises `KeyError` predictably rather than constructing a Decision with
  silently missing data.
- Firestore unavailability (mocked collection raising on `.stream()`,
  `.get()`, `.set()`) surfaces as a clear raised exception on read and
  write, not a silent empty result or a silently-lost write.

Full suite: 38/38 (was 31/31 before this session — 7 new failure-path
tests, 0 regressions). Detail in `.claude/SESSION_CONTRACT.md`.

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
First load takes ~30s (embeds the current decision store once, then caches to
`app/data/card_embeddings.json`, gitignored — regenerates on a fresh checkout
or changed card set). The current working tree has 63 loaded domain decisions
from the additive corpus expansion; the frozen graded run artifacts remain
n=37 until the expansion's run/grade/update gates complete.

**Falsifier artifacts are frozen** — `RESULTS.md`, `data/decisions.jsonl`,
`data/runs/`, and the pipeline scripts (`mine_decisions.py`,
`build_corpus.py`, `rag_index.py`, `run_conditions.py`, `grade.py`,
`vertex.py`, `gh_util.py`) should not be edited. `data/corpus/` (93MB RAG
decoy pool) was deliberately excluded from git — regenerate via
`build_corpus.py` only if you need to re-run the falsifier itself, not for
normal product work.

## Falsifier status (2026-08-18, updated)

Note above ("falsifier artifacts are frozen") predates this session's
falsifier-fix work — `mine_decisions.py`, `run_conditions.py`, `grade.py`,
`data/decisions.jsonl`, and `RESULTS.md` were all deliberately touched
this session, each behind an explicit session-contract entry with user
authorization (see `.claude/SESSION_CONTRACT.md`). Current, real,
converged numbers: code_only 0%, rag 57%, structured 76% combined, n=37,
verdict CAUTION. Four independent fix rounds this session (confound fix,
multi-point cards, stricter ground-truth extraction, per-alternative
retrieval indexing) all converged on the same ~76% band — the last one
(retrieval granularity) was a clean null result, documented in RESULTS.md.
This is the real ceiling of prompt/retrieval-mechanism iteration on this
n=37 set; further movement needs a larger sample or a different lever.
**Done, 2026-08-18**: README.md's "Why not just RAG?" section was updated
to the real 76%/57%/CAUTION numbers (see the "Update README.md's stale
benchmark claim" session-contract entry) — the claim is no longer stale.
`docs/DEMO_SCRIPT.md` was updated to match and its persistence-proof step
made mandatory rather than hedged (see the "Strengthen the demo script"
entry). Both verified against RESULTS.md by hand, number for number.

## Session-contract discipline, if you're an agent picking this up

This whole build followed strict evidence-gated staging: one capability
per session-contract update, stop-and-verify after each, real tests
before claiming done, checksums confirming frozen files stay frozen. Keep
doing that for Cloud Run deployment too — it's a new capability (infra),
deserves its own contract scoped to `decision-trace/` deployment config
only, with the same non-goals (don't touch falsifier artifacts, don't
touch Custody's `feat/memory-provenance`, don't touch
`failure-mining/AutomationBench`).
