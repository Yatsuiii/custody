# DecisionTrace: MVP implementation (staged, stop-and-verify)

Written 2026-08-16. This supersedes the build-scope-planning contract.
`decision-trace/BUILD_SCOPE.md` is approved and frozen — this contract
covers implementing it, staged exactly as the user specified, with an
explicit stop-and-verify checkpoint after each stage. Do not redesign the
product or reopen scope; if implementation and BUILD_SCOPE.md conflict,
stop and flag it rather than silently deciding.

This worktree is still `custody-search-2`, still physically separate from
`/run/media/Yatsuiii/Windows-SSD/custody` (`feat/memory-provenance`, the
Custody submission).

Objective: implement DecisionTrace per BUILD_SCOPE.md, in 8 stages (domain
model + resolver; benchmark → decision store; retrieval; Gemini
collaboration layer; persistent memory; minimal UI; real ingestion; demo
acceptance test). Stage 1 and Stage 2 are complete and verified (11/11
tests passing, falsifier artifacts confirmed untouched). Stages 1-3 are
complete and verified (15/15 tests passing). Stage 4 is now authorized: the
Gemini collaboration layer, supporting exactly the five MVP question
classes (why designed this way / was X tried before / what constraints
apply / is this still current / what changed), fed the resolved decision +
evidence from Stage 3's retrieval. Gemini does not decide lifecycle state —
that stays `resolve_active`'s job — and every answer must distinguish
verified historical fact, current active decision, inferred advice, and
missing/uncertain information. Stages 1-4 are complete and verified (20/20
tests passing). Stage 5 is now authorized: persistent memory — let a user
create a candidate decision conversationally, link it to an existing
decision via `RECONSIDERS` (or another appropriate relation), persist it,
and prove a *fresh session* (a new store/index instance reading the same
persisted file, not just a new chat turn in the same process) remembers it
and can surface it in retrieval/answers. Stages 1-5 are complete and
verified (23/23 tests passing). Stage 6 is now authorized: a minimal
Streamlit UI (user's explicit choice after a framework comparison) —
conversation, current-decision card, timeline, evidence links, candidate
creation/update. No dashboards, no generic repository browser, no graph
visualization (a status badge + timeline list, not a rendered graph).
Stage 6 is complete and verified (24/24 tests passing; a real correctness
bug found via manual UI testing — a PROPOSED candidate briefly presented as
currently active — was flagged, fixed in `retrieval.py`'s `is_current`, and
covered by a new regression test). Stage 7 is now authorized: real
GitHub/KEP ingestion — generalize discovery beyond the frozen 37-decision
benchmark to any repo, using the same two validated channels (revert-PR
pairs, KEP alternatives-considered sections), with Gemini structured-output
extraction per BUILD_SCOPE.md §9 kept strictly separate from the
deterministic lifecycle resolver (extraction never sets/implies
active/inactive status — only `resolve_active` does that, unchanged since
Stage 1). Stage 7 is complete and verified (30/30 tests passing, including
cross-validation of live extraction against the falsifier's hand-verified
k8s-136254/137662 rationale). Stage 8 is now authorized: the full demo
acceptance test — the delayed-preemption scenario end-to-end through the
actual running UI, including a genuine process restart to prove
cross-session persistence, per BUILD_SCOPE.md's "MVP complete" definition
(§20). This is verification only; no new product code is expected unless
the walkthrough surfaces a real bug (as Stage 6's did), in which case stop
and flag before fixing, same as before.

Branch: explore/decision-trace-v0
Parent: HEAD (falsifier + BUILD_SCOPE.md + Stages 1-7 already on this branch, uncommitted)

Allowed files: none new — Stage 8 is a live walkthrough of the existing
app (`decision-trace/app/*.py`) via `decision-trace/.venv`'s Streamlit
server. Any fix required by a bug found during the walkthrough is scoped
exactly like Stage 6's fix was: minimal, flagged before applying, and
re-verified with the full test suite plus a live re-check.

Non-goals:

- No changes to the frozen falsifier artifacts: `decision-trace/RESULTS.md`,
  `decision-trace/data/` (including `decisions.jsonl`), or the pipeline
  scripts (`mine_decisions.py`, `build_corpus.py`, `rag_index.py`,
  `run_conditions.py`, `grade.py`, `vertex.py`, `gh_util.py`). Stage 2 reads
  `decisions.jsonl`, never writes to it or its directory.
- No changes to `decision-trace/BUILD_SCOPE.md` — implementation follows
  it, doesn't rewrite it. If something in it turns out to be wrong, stop
  and flag rather than editing it unilaterally.
- No work beyond Stage 8 (this is the final stage per BUILD_SCOPE.md's
  8-stage build sequence).
- The restart proving cross-session persistence must be a real process
  kill + relaunch of the Streamlit server, not a page reload alone (a page
  reload only clears `st.session_state`; the process-level `st.cache_resource`
  index/store would still be warm from before — the real proof needs a
  cold process reading only the persisted file, same standard as Stage 5's
  and Stage 6's tests).
- UI is read-mostly: the only write path is candidate creation via
  `memory.propose_reconsideration`, called exactly as Stage 5 defined it —
  no new write logic invented in the UI layer.
- No login/auth, no multi-repo switcher, no rendered graph visualization,
  no dashboards, no code generation/PR/review/CI surfaces in the UI.
- Ingestion stays on the two validated channels only (revert-PR pairs,
  KEP-style alternatives-considered sections) — no generic issue-tracker
  mining; that's the exact channel restriction that survived the original
  substrate audit, don't re-widen it now.
- Extraction must never invent a rationale/evidence quote: every extracted
  `rationale`/`rejected_alternatives` claim must trace to a verbatim
  substring of the fetched source, checked programmatically after the
  Gemini call (not just instructed via prompt) — same discipline as
  `mine_decisions.pick_quote()`, degrade to null/insufficient-evidence
  rather than trust an unverified "verbatim" claim from the model.
- Extraction is separate from lifecycle resolution: `ingest.py` never sets
  `current_status` to anything implying settled activity beyond what the
  source directly states (e.g. IMPLEMENTED for a merged original,
  REVERTED for a revert record) — whether something is *currently* active
  stays `resolve_active`'s job, not the extractor's.
- Stage 7 builds the ingestion capability and proves it works; it does not
  change `ui.py`'s default demo-repo loading behavior (BUILD_SCOPE.md §15's
  explicit call to keep the judged demo on pre-verified data, live
  ingestion as a stretch capability only).
- A candidate decision created via `memory.py` gets `PROPOSED` status and a
  `RECONSIDERS` edge to its target — it must NOT automatically become the
  resolver's active decision (that would mean any proposal silently
  overrides settled history; `RECONSIDERS` is deliberately outside
  `DEACTIVATING_RELATIONSHIPS`/`REACTIVATING_RELATIONSHIPS` in `graph.py`,
  unchanged from Stage 1).
- The cross-session proof must use a genuinely fresh store/index instance
  reading the same persisted file — not the same Python objects reused
  within one test/process pretending to be two sessions.
- No user auth/session-management infrastructure — "session" here means
  "new process reading the same persisted store," per BUILD_SCOPE.md's
  actual requirement, not a login system.
- No changes to `failure-mining/`, `research-impact/`, `contribution-gate/`,
  `research-access/`, or Custody's `feat/memory-provenance`.
- No commit or push from this worktree without explicit user authorization.

Baseline: BUILD_SCOPE.md approved with recommendation "BUILD AS SCOPED."
Stage 1 domain model (`Decision`, `Evidence`, `DecisionStatus`,
`RelationshipType`) and resolver (`resolve_active`) complete and tested.
Falsifier data at `decision-trace/data/decisions.jsonl` (37 verified
records, e.g. `kubernetes-kubernetes-revert-136254`).

Acceptance gates:

1. `decision-trace/app/models.py` implements `DecisionStatus`,
   `RelationshipType`, `Evidence`, `Decision` matching BUILD_SCOPE.md §6.
   (Stage 1, done.)
2. `decision-trace/app/graph.py` implements a deterministic (non-LLM)
   `resolve_active` per BUILD_SCOPE.md §7. (Stage 1, done.)
3. `decision-trace/app/store.py` defines a storage abstraction (an
   interface/protocol, not just one hardcoded backend) with at least
   save/get/list-all operations, plus a concrete local implementation.
4. `decision-trace/app/loader.py` converts every record in
   `decisions.jsonl` into `Decision` objects via the Stage 1 domain model,
   preserving citation URLs and rationale quotes exactly as `Evidence`
   entries — no paraphrasing, no dropped evidence.
5. `decision-trace/app/tests/test_store.py` confirms: all benchmark records
   load without error; the k8s delayed-preemption pair loads through the
   loader (not hardcoded like Stage 1's test) and resolves to the same
   active/inactive result Stage 1 proved; evidence round-trips exactly
   (loaded `Evidence.url`/`.quote` match the source `decisions.jsonl`
   record byte-for-byte). (Stage 2, done.)
6. `decision-trace/app/retrieval.py` embeds decision *cards* (rendered from
   the Stage 1 `Decision` model), not raw source documents, and exposes a
   `search(query, k)` returning candidates each carrying similarity, the
   `Decision`, and its `ActiveResolution`.
7. `decision-trace/app/tests/test_retrieval.py` proves, using real
   benchmark decisions (e.g. a query about delayed preemption/victim pods
   retrieving the k8s-136254/137662 pair): retrieval returns evidence-
   bearing candidates, and a retrieved-but-inactive decision (the original,
   reverted PR) is never presented without its resolution showing it's
   inactive and naming what is active instead. (Stage 3, done.)
9. `decision-trace/app/collaborate.py` answers the five MVP question
   classes by calling Stage 3's `search()` for grounding, passing each
   candidate's `Decision` + `ActiveResolution` into the Gemini prompt as
   given fact (not something Gemini re-derives), and returns a structured
   answer whose claims are each tagged one of: verified_historical_fact,
   current_active_decision, inferred_advice, missing_or_uncertain.
10. `decision-trace/app/tests/test_collaborate.py` proves, on the real
    k8s-136254/137662 case: the answer never tags decision 136254 (the
    reverted original) as `current_active_decision` (that would contradict
    `resolve_active`'s ground truth), a `current_active_decision`-tagged
    claim correctly points at 137662, and a query with no relevant match in
    the store produces a `missing_or_uncertain` claim rather than a
    fabricated one. (Stage 4, done.)
12. `decision-trace/app/memory.py` creates a `PROPOSED` candidate `Decision`
    linked via `RECONSIDERS` to a target, persists it through Stage 2's
    store, and does not alter `resolve_active`'s result for the existing
    chain.
13. `decision-trace/app/tests/test_memory.py` proves: the candidate
    persists and links correctly; a *fresh* store/index instance built from
    the same file (not the same in-process objects) recalls the candidate
    via retrieval; and `collaborate.answer()` run against the fresh session
    includes the candidate decision among the grounding candidates it
    considered for a relevant follow-up question. (Stage 5, done.)
15. `decision-trace/app/ui.py` renders, on top of the existing backend
    (no new business logic): a chat interface calling `collaborate.answer`,
    a current-decision card with a status badge and clickable evidence
    links, a timeline from `graph.lineage`, and a candidate-creation form
    calling `memory.propose_reconsideration`.
16. Manual walkthrough (Streamlit apps aren't unit-tested the way Stages
    1-5 were): delayed-preemption question shows the revert as active with
    both PRs in the timeline; recording a reconsideration adds a visible
    `PROPOSED` node to the timeline. (Stage 6, done.)
18. `decision-trace/app/ingest.py` discovers revert-PR pairs and KEP
    alternatives-considered sections for an arbitrary repo (not hardcoded
    to the falsifier's 3-4 repos), extracts each into a `Decision` via
    Gemini structured output, and programmatically verifies every
    `rationale`/evidence quote is a real substring of the fetched source
    before accepting it — null/insufficient-evidence otherwise.
19. `decision-trace/app/tests/test_ingest.py` proves: at least one
    freshly-ingested decision from a repo/PR pair NOT already in
    `decisions.jsonl`; every accepted decision's evidence quote passes the
    verbatim-substring check; and re-ingesting the known
    kubernetes-kubernetes-136254/137662 pair produces a rationale
    consistent with the falsifier's hand-verified `rationale_quote` (cross-
    validation against already-trusted data). (Stage 7, done.)
21. The full delayed-preemption demo scenario runs live through the actual
    UI: ask why → recover the historical decision + evidence → the later
    revert/supersession is surfaced → correct current active status stated
    → developer states a changed assumption → candidate reconsideration is
    recorded → the Streamlit process is genuinely killed and relaunched →
    a fresh-session question shows the candidate decision persisted and
    shaped the answer. Every answer in the walkthrough carries a real,
    checkable evidence citation.
22. `git status`/checksums confirm no falsifier file was touched.

Verification: run `pytest decision-trace/app/tests/ -v`, report full
pass/fail. Report format at every stage checkpoint: files changed, tests
run, pass/fail, deviations from BUILD_SCOPE.md, next stage — per the user's
explicit instruction.

Status: active
