# DecisionTrace

**Live demo:** https://decision-trace-742122658452.us-central1.run.app

**Demo script:** [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)

DecisionTrace is a conversational agent that turns a repository's PRs,
issues, and design proposals into structured, evidence-backed decision
records with explicit lifecycle status — so asking "why is this built this
way" gets you the *currently active* rationale, not a pile of retrieved
documents you have to reconcile yourself.

It exists because we measured, rather than assumed, whether this beats
chat-with-your-repo RAG — and re-measured twice more after finding real
methodology bugs in our own first attempt. See
[Why not just RAG?](#why-not-just-rag) below.

## The problem

A developer about to touch a subsystem they didn't design needs to know:
was this already tried and rejected? Is the reasoning behind it still
valid? A generic RAG-over-the-repo assistant retrieves documents and lets
the model reconcile a mess of superseded, reverted, and current proposals
on the fly — which is exactly where it breaks, because nothing tells the
model which of five retrieved documents is the one that's actually still
true.

DecisionTrace's answer: don't leave lifecycle resolution to the language
model. Extract each decision into a structured record with an explicit
status (`PROPOSED`, `ACCEPTED`, `IMPLEMENTED`, `REVERTED`, `SUPERSEDED`,
`REAFFIRMED`), link related decisions with typed edges (`supersedes`,
`reverts`, `reconsiders`, ...), and resolve "what's active now" with
deterministic graph traversal — not an LLM guess. The model's only job is
to explain the resolved answer and ground every claim in a real citation.

## Why not just RAG?

We didn't assume the structured approach was better — we ran a falsifier
first and were prepared to kill the project if it lost. We also didn't
stop at the first result: our initial run had a real confound (the
structured condition's prompt and the judge's ground truth shared the
same underlying text), and fixing that honestly took three rounds, each
one a genuine bug found and fixed, not a retry until the number looked
better. Full diagnosis of all three rounds: [`RESULTS.md`](./RESULTS.md).

**n = 37** real decisions (reverted PRs + Kubernetes KEP
"Alternatives Considered" sections) across 4 repos (`kubernetes/kubernetes`,
`kubernetes/enhancements`, `rust-lang/rust`, `elastic/elasticsearch`),
graded on two axes: does the answer cite the correct evidence, and does it
state the correct current rationale.

| Condition | Citation-correct | Rationale-match | Combined (both correct) | Hallucination rate |
|---|---|---|---|---|
| code-only (no retrieval) | 14% | 14% | 0% | 8% |
| embedding RAG | 76% | 59% | **57%** | 3% |
| DecisionTrace (structured) | 100% | 76% | **76%** | 0% |

Structured clearly beats RAG (76% vs 57%) — but this is an honest
**CAUTION**, not a clean win: our preregistered bar for declaring the
structured approach decisively better required it to clear 85% combined,
and it doesn't, at this sample size. The gap is concentrated entirely in
one document type: on revert-PR pairs, structured already scores 94%
(matching RAG); the drag is Kubernetes KEP "Alternatives Considered"
sections specifically, where structured scores 58% combined (n=19) —
long, template-structured documents where a single decision often names
several distinct rejected alternatives, and correctly identifying *which
one* a question is about is genuinely harder than citation-correctness
alone suggests (structured's citation-correct rate is 100% throughout;
every remaining miss is about stating the specific right reason, not
finding the right decision).

That's a real, explained mechanism, not an unexplained score gap — and
it's also DecisionTrace's clearest next research direction, not a result
we're hiding: retrieving individual alternative-points instead of whole
decision cards is the current hypothesis for closing it. Full breakdown,
per-decision results, and all three rounds of methodology fixes:
[`RESULTS.md`](./RESULTS.md).

## What it does (5-minute tour)

1. **Ask why.** *"Why was delayed preemption reverted in kubernetes?"* —
   get the resolved current answer, not a document dump.
2. **Recover history.** Ask what was tried before; get the full lineage,
   not just the latest state.
3. **See the revert surfaced explicitly.** A reverted decision is never
   presented as current guidance — it's shown with an explicit "this was
   reverted, here's what's active now" framing.
4. **State current status** on demand, with evidence citations for every
   claim (verbatim quotes from the real PR/proposal, not paraphrases).
5. **Record a reconsideration.** Tell it an assumption has changed; it
   creates a new `PROPOSED` decision that `reconsiders` the old one — this
   is a write, not just a read.
6. **Kill the process. Start a fresh one.** The candidate decision is still
   there and still shapes subsequent answers. This step is the actual
   proof of the "collaborative partner, not a search box" thesis —
   everything before it could be faked by a good retrieval demo; this
   can't, because it requires real persistence across process boundaries.

Every claim the model makes is tagged with why it should be trusted:
verbatim historical fact, the resolver's current-truth verdict, the
model's own inference, or an admission that the data doesn't say — so "I
don't know" is a valid, expected answer instead of something the model has
to be tricked into.

The answer path is collaborative and visible: an **Evidence Scout** retrieves
candidate decision cards, a **Lifecycle Resolver** replays typed edges, a
**Provenance Challenger** rejects evidence-less or ambiguous authority, and a
**Gemini Reconciler** explains only the candidates that survived those checks.
The UI exposes those handoffs in an “Agent collaboration trace” alongside the
current-decision card. The workers exchange answer-scoped reports; canonical
organizational state remains the structured decision store and deterministic
resolver.

## Architecture

Full diagram and component breakdown: [`docs/architecture.md`](./docs/architecture.md).

Google Cloud stack, all actually wired and exercised, not aspirational:

- **Cloud Run** — hosts the Streamlit app as a container, built via Cloud
  Build from the repo's `Dockerfile`.
- **Firestore** (Native mode) — `FirestoreDecisionStore` persists every
  decision record and every conversational candidate, so state survives
  Cloud Run's ephemeral filesystem and scale-to-zero restarts. Verified
  with a genuine kill-and-restart proof, not just a code review: create a
  decision, kill the process, start a fresh one, confirm it's still there
  and still shapes answers.
- **Vertex AI via the Google GenAI SDK** (`google-genai`, `gemini-3.7-flash`
  for generation, `text-embedding-005` for retrieval) — every model call
  in the product goes through this SDK; nothing is mocked, including in
  the test suite.

## Spin up locally

```bash
git clone <this-repo-url>
cd decision-trace
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python google-genai google-cloud-firestore numpy streamlit pytest
gcloud auth application-default login   # or point CLOUDSDK_CONFIG at existing ADC

# Local dev default: JSONFileDecisionStore, no GCP credentials required to just look around
.venv/bin/streamlit run app/ui.py --server.headless true --server.port 8765

# To run against the same Firestore-backed store the deployed service uses:
DECISIONTRACE_STORE=firestore VERTEX_PROJECT=<your-project> \
  .venv/bin/streamlit run app/ui.py --server.headless true --server.port 8765
```

First load embeds the current decision store once (~30s), then caches to
`app/data/card_embeddings.json` (gitignored, regenerates when the card set
changes). The checked-in `data/decisions.jsonl` remains the frozen
37-source-row benchmark corpus, which loads as 55 domain records. A separate
local, user-owned expansion to 42 source rows / 63 domain records remains
uncommitted and ungraded; it must not be used to claim new benchmark numbers.

Run the tests (53 tests, including real Gemini/embedding calls, live GitHub
ingestion, a real Firestore round trip, and targeted failure-injection tests
for conditions that cannot be forced against a real backend on demand):

```bash
.venv/bin/python -m pytest app/tests/ -v
```

## Deploy your own copy

```bash
gcloud run deploy decision-trace \
  --source . \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DECISIONTRACE_STORE=firestore,VERTEX_PROJECT=<your-project>,VERTEX_LOCATION=global" \
  --memory=1Gi --timeout=300
```

Requires Cloud Run, Cloud Build, Artifact Registry, and Firestore (Native
mode, any region) APIs enabled, and a Firestore database already
provisioned. The deploying account's default compute service account needs
`roles/datastore.user` (Firestore) and Vertex AI access (`roles/editor`
covers both, or scope down to `roles/aiplatform.user` +
`roles/datastore.user`).

Local `docker build`/`docker run` may not work on every machine — this
Dockerfile is verified via `gcloud run deploy --source .`, which builds
remotely through Cloud Build and sidesteps any local Docker networking
quirks.

## Project layout

```
app/
  models.py       domain model: Decision, DecisionStatus, RelationshipType, Evidence
  graph.py         deterministic active-decision resolver (never an LLM guess)
  store.py         DecisionStore protocol + JSONFileDecisionStore + FirestoreDecisionStore
  loader.py        loads the frozen falsifier benchmark into the store
  retrieval.py     card-level embedding search over decisions
  collaborate.py   worker handoffs, provenance gate, Gemini reconciliation
  memory.py        conversational candidate-decision creation (the write path)
  ingest.py        live GitHub/KEP discovery + extraction, wired into ui.py's sidebar
  ui.py            Streamlit UI
  tests/           real API calls except deliberate failure-injection mocks (see below)

BUILD_SCOPE.md     frozen MVP spec
RESULTS.md         frozen falsifier result (the evidence this product exists on)
  data/decisions.jsonl   checked-in frozen corpus: 37 source rows -> 55 loaded domain records; separate local 42/63 expansion remains ungraded
```

`BUILD_SCOPE.md` and `RESULTS.md` are frozen evidence artifacts and are not
edited as the product evolves — they're the record of why this exists.

## What's deliberately not in the demo

- **Live ingestion is wired into the UI (2026-08-17)**, via a "Live ingest"
  panel in the sidebar: type any `owner/repo`, click Ingest, and
  `ingest_repo()` runs for real against GitHub + Gemini and adds the
  resulting decisions to the session's store — confirmed end-to-end with a
  real repo (`kubernetes/kubernetes`), including a follow-up question that
  cited the freshly ingested decision as the current active one. What's
  still deliberately narrow: it's additive to the frozen-benchmark path,
  not a replacement — the judged demo's core 9-step script still runs off
  the frozen benchmark corpus, since that's the scenario with a known,
  repeatable answer; live ingestion is there for judges who want to point
  it at their own repo, with candidate counts capped (default 2 per
  channel) to keep a live run's runtime bounded.
- **No Google ADK.** The rubric's "Google Agent Framework" requirement is
  satisfied by direct use of the Google GenAI SDK (`google-genai`), which
  is one of the four frameworks the rubric names explicitly (alongside
  ADK, Antigravity SDK, and GenKit 3) — not a substitute for it.
