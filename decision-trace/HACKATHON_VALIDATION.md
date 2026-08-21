# DecisionTrace Hackathon Validation

Date: 2026-08-21
Branch: `hardening/collaborative-pre-submission`
Track: All Things Agentic — Collaborative

## Current architecture

DecisionTrace keeps a structured decision store as the accumulated
organizational state. The read path is:

```text
Evidence Scout
  -> card retrieval from DecisionIndex
  -> Lifecycle Resolver
  -> Provenance Challenger
  -> Gemini Reconciler
  -> Answer claims + worker trace + current-decision card
```

The first three workers are deterministic or evidence-gated code. Gemini is
used to interpret and explain approved evidence; it does not decide which
decision is currently governing. `DecisionStore` remains the persistence
owner, with local JSON and Firestore implementations behind the same
protocol. Reconsiderations remain durable `PROPOSED` decisions and do not
silently change active truth.

Relevant implementation evidence:

- Worker handoffs and claim validation: `app/collaborate.py`
- Stable lifecycle replay, cycle detection, and explanations: `app/graph.py`
- Evidence-bearing retrieval candidates: `app/retrieval.py`
- Persistent state and Firestore boundary: `app/store.py`
- UI worker trace and lifecycle explanation: `app/ui.py`
- Architecture diagram and read/write paths: `docs/architecture.md`

## Collaboration test

**Pass for the local hardening branch.** A judge can see four distinct
contributions to one answer:

1. Evidence Scout reports which structured decision cards were discovered.
2. Lifecycle Resolver reports the typed-edge result, including ambiguity.
3. Provenance Challenger removes evidence-less candidates and rejects model
   claim IDs outside the retrieved set.
4. Gemini Reconciler explains only challenger-approved candidates and returns
   the four existing claim categories.

The UI renders these answer-scoped handoffs in the **Agent collaboration
trace** expander. The workers do not create a second source of truth; the
canonical state remains the structured decision graph and evidence records.

Proof tests:

```bash
.venv/bin/python -m pytest -q \
  app/tests/test_collaborate.py \
  -k 'claim_gate or provenance or emits'
```

Expected result on this branch: 5 passed, 4 deselected.

## Necessity test

Multiple specialized workers are necessary here because the failure is not
just finding a semantically similar paragraph:

- Retrieval can find both the historical implementation and the later revert.
- Only lifecycle replay can deterministically say which node governs now.
- Only provenance checking can prevent a model from promoting a candidate
  without source evidence or citing a decision it never received.
- Gemini remains useful for interpreting messy rationale and producing a
  human-readable answer after those constraints are established.

A single generic agent could imitate this sequence in one prompt, but it
would not provide a separately checkable lifecycle verdict, an evidence gate,
or a durable state boundary. DecisionTrace makes those contracts executable
and visible rather than trusting the strongest model output.

## Generic-RAG test

Ordinary vector retrieval plus LLM synthesis can retrieve a relevant original
PR and a relevant revert PR, but it cannot reliably determine from similarity
alone that:

- the original is historically real but no longer governing;
- the revert is the current operative state under this product's semantics;
- `A -> B -> C` resolves to `C` while preserving `A` and `B` as history;
- a mention without a typed supersession edge must not change current truth;
- two competing successors or a lifecycle cycle require uncertainty;
- an evidence-less or unknown-ID model claim cannot become authoritative.

Those are structured lifecycle/provenance decisions, not retrieval ranking
decisions. The existing falsifier remains the empirical differentiation
artifact: `RESULTS.md` reports frozen n=37 results of RAG 57% combined versus
structured 76% combined, with a CAUTION verdict.

## Active-truth test

**Pass.** The system distinguishes historically true from currently governing:

- original PR: `IMPLEMENTED`, historical evidence;
- revert PR: `REVERTED`, current operative node for the tested pair;
- candidate reconsideration: `PROPOSED`, persistent but not current;
- resolver explanation: names the actual `SUPERSEDES`, `REVERTS`, or
  `REAFFIRMS` events that led to the result;
- ambiguous cycle/fork: no active ID is returned.

Proof tests include the real delayed-preemption pair plus pure graph tests for
reordering, multi-hop supersession, revert semantics, reaffirmation,
parallel decisions, mention-without-edge, forks, and cycles.

## Evidence test

**Pass for authoritative claims from accepted candidates.** Evidence is
retained as URL + verbatim quote through JSON/Firestore round trips. Live
ingestion verifies quotes against fetched source text before accepting them.
The challenger rejects candidates without evidence, and the claim gate
rejects unknown IDs or current-truth IDs that are not approved active
candidates.

Known boundary: source snapshots, content hashes, and first-class edge
evidence are not yet stored. URLs can point at mutable source branches, and
the KEP loader still represents some multi-alternative rationale as a quote
plus card rather than one structured record per alternative. This is a
remaining provenance P1, not silently treated as solved.

## Better-model test

**Pass.** A 10× better Gemini would improve extraction, rationale
interpretation, and reconciliation quality, but DecisionTrace would still
retain:

- accumulated decision history;
- typed lifecycle edges and deterministic active-state resolution;
- provenance quotes and source links;
- organization-specific reconsiderations and proposed memory;
- explicit ambiguity when evidence cannot resolve current truth.

The product is therefore a stateful organizational memory system with agents,
not a prompt wrapper whose value disappears when the model improves.

## Collaboration spectacle test

**Pass locally; deployment proof remains.** The smallest safe visible sequence
is now:

```text
discover -> resolve -> challenge -> reconcile -> update memory
```

The delayed-preemption demo makes the result concrete: the trace shows the
two PR records being considered, the resolver names the revert edge, the
challenger confirms evidence, Gemini explains the approved history, and the
UI can then persist a new `PROPOSED` reconsideration. The proposal changes
organizational memory without falsely changing governing truth.

The checked-in branch has not been redeployed to Cloud Run during this
hardening pass. The existing live URL remains a separate prior revision until
an authorized deployment and browser recording exercise is performed.

## Judge-memory test

> “DecisionTrace uses collaborating agents to reconstruct not just what
> engineers once decided, but which decision actually governs the codebase
> now.”

## Verification evidence

Passed:

- `CLOUDSDK_CONFIG=... .venv/bin/python -m pytest app/tests/ -v` — **53
  passed in 538.96s**, including real Gemini generation/embedding, live
  GitHub ingestion, and a real Firestore round trip.
- `ruff check --no-cache .` — passed.
- `python3 -m compileall -q app *.py` — passed.
- `git diff --check` — passed.
- `pytest --collect-only -q app/tests` — 53 tests collected.

Benchmark state deliberately not rerun:

- Frozen evaluation remains `RESULTS.md`, n=37, RAG 57%, structured 76%,
  CAUTION.
- The integrated branch contains the checked-in frozen corpus: 37 source
  rows and 55 loaded domain decisions.
- A separate local, user-owned additive expansion to 42 source rows and 63
  loaded domain decisions remains uncommitted and ungraded.
- Only 37 run files per condition exist, so the 5 new source rows have not
  been graded. No new benchmark number is claimed.

## Demo Gate

Verdict: **needs final deployment/recording work**

Proof artifact: local Streamlit UI with the Agent collaboration trace,
deterministic lifecycle explanation, evidence links, and existing Firestore
persistence path.
Setup path: README local-start commands.
Verification: full 53-test suite above.
Failure mode: missing evidence or ambiguous lifecycle produces an explicit
challenge/uncertain result; Vertex/Firestore failures propagate visibly.
Remaining gate: deploy this branch and record a fresh browser walkthrough;
the existing architecture PNG is present, but no new UI screenshot/video was
created in this pass.

## Outcome ledger

### Decision 1

Decision: Preserve structured history and deterministic lifecycle state.
Lane: evidence-gated agentic developer tooling.
Artifact: `app/graph.py`, `HACKATHON_HARDENING_AUDIT.md`.
Acceptance gate: adversarial resolver tests pass; full suite passes.
Result: shipped on this branch.
Next action: deploy and capture the worker trace.
Kill condition: any real corpus case resolves differently solely because
store iteration order changes.
Status: continued

### Decision 2

Decision: Make collaboration explicit with evidence/challenge/reconciliation
handoffs.
Lane: evidence-gated agentic developer tooling.
Artifact: `app/collaborate.py`, `app/ui.py`, `docs/architecture.md`.
Acceptance gate: worker handoff test passes and trace is visible in the UI.
Result: shipped locally; not yet redeployed.
Next action: record the four-stage trace in the submission demo.
Kill condition: judges cannot distinguish the worker contributions from a
single unstructured LLM call after the trace is shown.
Status: continued

### Decision 3

Decision: Keep the additive corpus expansion ungraded until its complete
run/grade/update gates are finished.
Lane: optimization/research engineering supporting the agentic product.
Artifact: `data/decisions.jsonl` plus the existing 37-run evidence set.
Acceptance gate: all new source IDs have all three runs, full grade reruns,
and docs cross-check every number.
Result: intentionally not claimed in this pass.
Next action: run the expansion gates only as a separate authorized benchmark
session.
Kill condition: the additive sample cannot be completed reproducibly or
changes the frozen 37 rows.
Status: continued
