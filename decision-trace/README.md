# DecisionTrace

**Live demo:** https://decision-trace-742122658452.us-central1.run.app

**Demo script:** [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)

DecisionTrace is a conversational agent that turns a repository's PRs,
issues, and design proposals into structured, evidence-backed decision
records with explicit lifecycle status — so asking "why is this built this
way" gets you the *currently active* rationale, not a pile of retrieved
documents you have to reconcile yourself.

DecisionTrace separates evidence interpretation from organizational
authority. Agents discover and interpret decision history, while
deterministic lifecycle logic decides what governs and emits an auditable
proof explaining why competing decisions do not. See
[Why deterministic authority, not an LLM verdict?](#why-deterministic-authority-not-an-llm-verdict)
below.

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

## Why deterministic authority, not an LLM verdict?

A generic RAG assistant retrieves documents and asks the language model to
reconcile which one is still true. That question — *which decision
currently governs, and why don't the alternatives* — is exactly the kind
of question we don't think a model should answer by guessing. So it
doesn't: DecisionTrace resolves it with a deterministic lifecycle
resolver, and the model's job is narrowed to explaining an
already-computed result, never producing one.

That resolver returns more than an id. Every authority conclusion carries
a machine-readable **proof**: the requested scope, the governing decision,
every competing candidate that was considered, and — for each one that
didn't govern — a specific, checkable reason (`PROPOSED_NOT_ACCEPTED`,
`SUPERSEDED`, `IMPLEMENTATION_NOT_POLICY_AUTHORITY`, and others) plus the
lifecycle edges that establish the winner. A skeptical reader can verify
"decision A governs" against the proof directly, without trusting a
model's prose.

This product doesn't lead with a benchmark score, and earlier ones we ran
don't back a superiority claim strong enough to lead with — the full
research history, run honestly and reported however it came out, is
preserved in [`RESULTS.md`](./RESULTS.md) for anyone who wants it. What
we're claiming here is architectural: an auditable proof of *why*
something governs is a more serious answer than a plausible-sounding
retrieval, whether or not either approach finds the right document more
often on a given sample.

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
candidate decision cards, a **Lifecycle Resolver** replays typed edges and
computes a deterministic **AuthorityProof** — the governing decision, every
candidate considered, and a specific, checkable reason for each one that
didn't govern — a **Provenance Challenger** rejects evidence-less or
ambiguous authority and flags an unresolved or absent proof, and a
**Gemini Reconciler** explains only the candidates and proof that survived
those checks. Gemini never decides authority; if its prose disagrees with
the proof, the proof wins, enforced by the citation gate that rejects any
claim naming a decision the proof didn't already name as governing. The UI
shows "CURRENTLY GOVERNING" with a "why this governs" breakdown alongside
the "Agent collaboration trace." Canonical organizational state remains the
structured decision store and the deterministic resolver.

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
  for generation, `text-embedding-005` for retrieval) — every product model
  call goes through this SDK. Credentialed integration tests exercise the
  real endpoints; deterministic failure-path tests inject only the failure
  they are designed to verify.

## Spin up locally

```bash
git clone <this-repo-url>
cd decision-trace
uv sync --frozen
gcloud auth application-default login   # or point CLOUDSDK_CONFIG at existing ADC

# Local dev default: JSONFileDecisionStore, no GCP credentials required to just look around
uv run streamlit run app/ui.py --server.headless true --server.port 8765

# To run against the same Firestore-backed store the deployed service uses:
DECISIONTRACE_STORE=firestore VERTEX_PROJECT=<your-project> \
  uv run streamlit run app/ui.py --server.headless true --server.port 8765
```

First load embeds the current decision store once (~30s), then caches to
`app/data/card_embeddings.json` (gitignored, regenerates when the card set
changes). The checked-in `data/decisions.jsonl` remains the frozen
37-source-row benchmark corpus, which loads as 55 domain records. A separate
local, user-owned expansion to 42 source rows / 63 domain records remains
uncommitted and ungraded; it must not be used to claim new benchmark numbers.

Run the deterministic release gate without network access or cloud credentials:

```bash
make check
```

Credentialed Gemini/embedding, GitHub ingestion, and Firestore checks are
explicitly separated so a clean clone never silently depends on local cloud
state:

```bash
make test-live
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
