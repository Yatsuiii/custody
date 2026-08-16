# DecisionTrace — MVP build scope

Written 2026-08-16, after the n=37 falsifier closed at GO
(`decision-trace/RESULTS.md`). This document scopes the hackathon MVP. It
does not contain implementation code.

## 1. Target user

A software engineer — mid-to-senior, not a newcomer needing onboarding docs
and not a PM needing a status report — who is about to touch a subsystem
they didn't design, in a codebase with real history (dozens to thousands of
PRs/issues/proposals), and needs to know *why* it's built the way it is
before changing it. The moment this product exists for: "I'm about to do
something and I don't know if it's already been tried and rejected."

## 2. One-sentence product definition

DecisionTrace is a conversational agent that mines a repository's PRs,
issues, and design proposals into structured, evidence-backed decision
records with explicit lifecycle status, so a developer asking "why is this
built this way" gets the currently-active rationale — not a pile of
retrieved documents they have to reconcile themselves.

## 3. Primary user workflow

1. Developer asks a why/whether question about a subsystem.
2. DecisionTrace returns the currently active decision: chosen approach,
   rejected alternatives, rationale, evidence.
3. Developer proposes something that resembles a past rejected/reverted
   approach. DecisionTrace recognizes the collision and shows the timeline.
4. Developer states that an assumption behind the old decision has changed.
   DecisionTrace reasons over that, doesn't just repeat the old rationale.
5. Developer asks to record the reconsideration. DecisionTrace creates a new
   `PROPOSED` decision that `reconsiders` the old one.
6. New session, same or different developer: the candidate decision is
   still there and shapes subsequent answers. This step is the actual proof
   of the Collaborative Partner thesis — everything before it could be
   faked by a good retrieval demo; this can't.

## 4. MVP feature list

Exactly four capabilities, nothing adjacent:

1. **Ingestion** — narrow, two channels only (see §8), one repo at a time.
2. **Extraction** — raw artifact → structured decision card, evidence-bound.
3. **Temporal graph** — status + relationships + "what's active now."
4. **Collaborative interface** — chat, grounded answers, memory that
   persists and can be written to through conversation.

## 5. Non-goals

Autonomous code generation or PR creation, generic chat-with-your-repo, bug
fixing, code review, CI repair, test generation, issue triage,
organization-wide knowledge management, every Git provider, every proposal
format, perfect automated architecture understanding, replacing ADRs, a
full graph database platform, enterprise governance. If a feature doesn't
sit directly on `history → extraction → temporal memory → collaborative
reasoning → memory evolution`, it's out.

## 6. Decision data model

```json
{
  "id": "string, stable, e.g. repo-slug + short hash",
  "subject": "string, one line",
  "current_status": "PROPOSED | ACCEPTED | IMPLEMENTED | REVERTED | SUPERSEDED | REAFFIRMED",
  "context": "string, the problem being solved",
  "chosen_approach": "string",
  "rejected_alternatives": ["string", "..."],
  "rationale": "string, must be evidence-grounded, never invented",
  "constraints": ["string", "..."],
  "introduced_at": "ISO timestamp",
  "superseded_at": "ISO timestamp | null",
  "evidence": [
    {"type": "pr | issue | proposal | revert_pr", "url": "string", "quote": "string, verbatim excerpt"}
  ],
  "related_components": ["string path/module identifiers"],
  "related_decisions": [{"decision_id": "string", "relationship": "see §7"}]
}
```

This is a direct typed version of the schema in the brief. The one addition
is `evidence[].quote` — every field that claims a rationale must carry a
verbatim excerpt, not just a URL. That discipline is inherited directly
from the falsifier's `pick_quote()` (`mine_decisions.py`): a rationale
string that isn't a real, checkable substring of a fetched source is the
single biggest quality risk in this whole product, and the benchmark's own
credibility rests on never doing that. Same rule applies in production.

## 7. Temporal graph model

Nodes = decisions. Edges, directed, typed:

`implements`, `supersedes`, `reverts`, `reconsiders`, `reaffirms`,
`depends_on`, `related_to`.

**Active-decision resolution** (the one algorithm that has to be correct):
a decision is *active* iff no outgoing `supersedes`/`reverts`/`reaffirms`
edge from a later decision points at it, walking the chain to a fixed
point. A `REVERTED` or `SUPERSEDED` decision is never presented as current
guidance without an explicit "this was reverted, here's what's active now"
framing — this is the one behavior the demo script's step 2-3 depends on
being airtight, and it's a graph traversal, not an LLM judgment call. Keep
it as deterministic code, not a Gemini-decided answer, so it can't
hallucinate a wrong current-status.

## 8. Ingestion strategy

Reuse, don't rebuild: `mine_decisions.py` already implements exactly the
two channels that survived the substrate audit —

1. Revert-PR pairs (regex-detected `revert`+`#number` reference, real PR
   bodies fetched via `gh`).
2. Structural "Alternatives Considered" sections in template-enforced
   proposal repos (KEPs and equivalents).

Generalize this from "3 hardcoded repos" to "any repo the demo targets,"
but do **not** widen the channels themselves — the falsifier only validated
these two, and broadening ingestion to arbitrary issue-tracker mining is
exactly the noisy, low-yield path the original substrate audit already
rejected. Every ingested artifact keeps: source repo, artifact type/ID,
timestamps, author, linked-artifact IDs, evidence URL, raw text — this is
already the shape `mine_decisions.py` produces.

## 9. Extraction strategy

Gemini with structured output (JSON schema matching §6), given one raw
artifact (or a revert-pair/KEP-alternatives-section) at a time, instructed
to fill the decision card **only from what's in the text**, with every
`rationale` and `rejected_alternatives` entry required to trace to a quoted
`evidence[].quote`. If the artifact doesn't contain enough signal to fill a
field, the field is explicitly `null`/`"insufficient evidence"`, never
invented — same rule the falsifier already enforces via
`pick_quote()` returning `None` rather than fabricating a rationale. This
is a stricter extraction contract than typical "summarize this PR," and
it's the one place hallucination risk is highest, so it gets the most
explicit safeguard (see §16).

## 10. Retrieval/query strategy

This is where the benchmark result directly determines the architecture,
not just informs it. The falsifier tested two extremes: raw-document
embedding RAG (57% combined, collapsing to ~21% on long template-structured
KEPs) and "hand every card for the repo into the prompt" (100%, but
doesn't scale past a few dozen decisions).

Production retrieval should be the natural middle the benchmark didn't
directly test but clearly implies: **embed the structured decision cards
themselves, not the raw source documents, and retrieve top-k cards.**
Cards are short, uniform, and already stripped of the boilerplate/
repetition that caused KEP retrieval to fail — retrieving over them is
retrieving over exactly the artifact type the "structured" condition proved
works, just without inlining all of them unconditionally. This is a direct,
low-risk extrapolation from tested results, not a new unverified claim —
flag it as such in the demo/pitch rather than presenting it as
independently benchmarked.

## 11. Persistent-memory design

Firestore holds three collections: `decisions` (the cards), `edges` (the
graph), `conversations` (session-scoped turn history plus any candidate
decisions created in that session, cross-linked by `decision_id` so a new
session's retrieval includes conversation-originated decisions, not just
ingested ones). Writing a candidate decision from conversation (demo step
5) is a normal write to `decisions` with `current_status: PROPOSED` and a
`reconsiders` edge — not a special code path, which keeps "memory
evolution" honest rather than a scripted-looking demo trick.

## 12. Google/Gemini architecture

| Service | Why needed | State it owns | If removed | Cost/complexity |
|---|---|---|---|---|
| Gemini via Vertex (reuse `vertex.py`'s validated transport) | Extraction (structured output) + conversational reasoning + citation synthesis | None (stateless calls) | No product | Already proven working this session; near-zero marginal setup |
| Gemini embeddings (`text-embedding-005`, already validated) | Card retrieval (§10) | None | Falls back to "inline all cards," breaks at scale but not for a demo-sized repo | Same transport, already working |
| Google ADK | Stateful multi-turn agent, tool calls (query decisions, create/supersede a decision) | Session/turn state during a live conversation | Falls back to hand-rolled turn loop — doable but reinvents session mgmt and tool-call plumbing for no benefit | Moderate: one new framework, but purpose-built for exactly this shape of app |
| Firestore | Decision cards, graph edges, cross-session conversation memory | All persistent product state | No cross-session memory — kills the one demo step (6) that actually proves the thesis | Free tier covers a hackathon demo trivially; low complexity, no schema migrations needed for a document store |
| Cloud Run | Hosts the demo backend/UI | None (stateless) | Run locally for the demo — acceptable fallback, not for judged deployment | Free tier, minutes to deploy |

Explicitly **not** in scope: BigQuery, Pub/Sub, Cloud Functions, Vertex AI
Search/Agent Builder, GKE. None of them own state this product needs or do
anything Firestore/Cloud Run/Gemini don't already cover — including them
would be logo-count padding, which the brief explicitly rules out.

## 13. Minimum UI surfaces

One chat pane (the conversation) plus one decision-card display (chosen
approach, rejected alternatives, rationale, evidence links, a status badge:
ACTIVE / REVERTED / SUPERSEDED / PROPOSED). A secondary list view for demo
step 1 ("here's what's already ingested"). No graph visualization in the
MVP — a status badge plus a link to the decision that superseded/reverted
this one covers the lifecycle-legibility requirement without building a
graph UI. If a graph view happens, it's a stretch goal (§19).

## 14. Benchmark integration

Keep `decision-trace/{mine_decisions,build_corpus,rag_index,run_conditions,
grade}.py` exactly as they are — frozen, reusable comparison harness. The
product's real ingestion/extraction pipeline should be a generalized
version of `mine_decisions.py`'s channel logic (§8), not a parallel
reimplementation, so the harness keeps measuring what the product actually
does. Future strengthening (hybrid BM25+embedding, heading-aware retrieval,
reranking, more RFC ecosystems, larger KEP sample) stays a v1+ benchmark
task, explicitly not a blocker for this MVP.

## 15. Demo script

Anchor step 1 on a repo and decision **already inside the verified
falsifier dataset** rather than ingesting something new live —
`kubernetes/kubernetes`'s delayed-preemption revert
(`kubernetes-kubernetes-revert-136254` in `decisions.jsonl`, evidence
already fetched and hand-verified) is the same example already used in the
original pitch's sample dialogue. Zero new verification risk on demo day;
the "why" answer, the revert citation, and the rationale quote are all
already fact-checked. Then follow the brief's 6 steps exactly: ask why →
get current decision + rationale + evidence → propose the reverted approach
→ system recognizes the collision and shows the timeline → developer says
the old blocking condition no longer applies → system reasons over the
changed assumption rather than repeating stale rationale → developer asks
to record it → new `PROPOSED` decision created → restart the session/process
→ ask a related question → the candidate decision is still there and shapes
the answer.

## 16. Failure cases and safeguards

- **Extraction hallucinates a rationale.** Safeguard: every claim must
  trace to an `evidence[].quote` that's a real substring of fetched source
  text (§6, §9) — reject/null the field otherwise, mirroring
  `pick_quote()`'s existing discipline.
- **Ambiguous or conflicting supersession chain** (two decisions each claim
  to supersede the other, or a cycle). Safeguard: active-decision
  resolution (§7) is deterministic graph code; if it can't resolve to a
  single fixed point, surface both candidates explicitly flagged
  "ambiguous," never silently pick one.
- **Gemini answers from parametric/background knowledge instead of
  retrieved cards.** Safeguard: system prompt requires every claim to cite
  a retrieved card's evidence, same "answer using only what's provided"
  discipline already used in `run_conditions.py`'s prompts, which the
  benchmark shows produces a low (3%) hallucination rate even under
  adversarial-ish conditions.
- **Ingestion noise from over-broad channels.** Safeguard: stay on the two
  validated channels (§8); don't add generic issue-tracker mining without
  its own substrate check.

## 17. Build sequence with verification checkpoints

- **Phase 0 — generalize ingestion+extraction.** Refactor
  `mine_decisions.py`'s channel logic to target an arbitrary repo, add
  Gemini structured-output extraction on top (§9). *Checkpoint:* run
  against a fresh repo, hand-spot-check N extracted cards the same way
  `decisions.jsonl` was spot-checked (gate 2 discipline from the falsifier
  contract).
- **Phase 1 — Firestore schema + graph.** Persist cards + edges; implement
  active-decision resolution (§7). *Checkpoint:* resolution correctly
  returns `REVERTED/INACTIVE` for a known chain already in the benchmark
  data (e.g. the k8s delayed-preemption pair) before trusting it on
  anything new.
- **Phase 2 — card-embedding retrieval + grounded QA.** Implement §10.
  *Checkpoint:* re-run a held-out slice of the benchmark's own 37 decisions
  through the product's real retrieval path and confirm accuracy tracks the
  "structured" condition, not the "RAG" condition — this reuses the
  falsifier as a regression test for the product itself, not just a
  one-time research result.
- **Phase 3 — ADK agent + conversational writes.** Tool for creating/
  updating a candidate decision from conversation; session persistence
  across restarts. *Checkpoint:* demo steps 5-6 work end to end, including
  an actual process restart, not just a new chat turn in the same process.
- **Phase 4 — minimal UI on Cloud Run.** *Checkpoint:* the full 6-step demo
  script runs live through the UI, not via direct API calls.

## 18. Verification checkpoints

Listed inline per phase in §17 — each phase has one concrete, checkable
gate before moving to the next, matching the evidence-gated discipline used
throughout this search (baseline before editing, verification gate before
declaring a phase done).

## 19. Cut list if time-constrained, in cut order

1. UI polish — fall back to a bare chat interface with printed decision
   cards if Cloud Run deployment or frontend work eats the clock.
2. Multi-repo ingestion — hardcode to the one demo repo (§15).
3. Graph visualization — status badge + one link is enough; never scoped
   for MVP anyway (§13).
4. Hybrid/reranked retrieval — plain card-embedding retrieval (§10) is
   already a direct extrapolation of a tested-working mechanism; don't
   add complexity chasing marginal accuracy under time pressure.
5. Firestore, as an absolute last resort only — an in-memory or flat-file
   store gets the demo running, but cutting this specifically weakens the
   one thing (cross-session memory) that proves the Collaborative Partner
   thesis rather than a generic RAG demo. Cut everything else first.

## 20. Definition of "MVP complete"

The 6-step demo script (§15) runs live, end to end, against real ingested
data — not scripted or mocked responses — including: at least one
supersession/revert chain correctly resolved to `REVERTED`/inactive by the
graph, at least one conversational reconsideration recorded as a new
`PROPOSED` decision, and that decision correctly recalled after an actual
process/session restart. Every answer given during the demo carries a
citation traceable to a real PR/issue/KEP URL. If all of that is true, the
MVP is complete regardless of what's on the cut list.

## Recommendation

**BUILD AS SCOPED**, with one modification already folded into this
document rather than left open: commit to a single pre-selected, already-
verified demo repo/decision (§15) instead of live-ingesting a
judge-provided repo. Live arbitrary-repo ingestion is real and the pipeline
supports it, but it turns a rehearsed, fact-checked demo into a live
extraction gamble on stage — treat it as a stretch capability to show if
time allows, never as the thing the judged demo depends on.

No fundamental blocker found. The mechanism is falsified-and-passed at
n=37 with an explained, replicated failure mode (not a black-box aggregate
gap), the two ingestion channels are validated, the Google/Gemini stack is
minimal and every service earns its place, and the hardest behavior in the
whole product (correct active-decision resolution) is deterministic graph
code rather than something that depends on an LLM getting it right every
time.
