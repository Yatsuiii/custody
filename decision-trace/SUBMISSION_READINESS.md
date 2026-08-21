# DecisionTrace submission readiness

Date: 2026-08-21  
Lane: evidence-gated agentic developer tooling  
Status: **READY TO RECORD**

## Integrated and deployed build

- Base branch: `explore/decision-trace-v0`
- Final commit: `b376cf0` (`Keep reconsideration confirmation visible`)
- Hardening branch retained: `hardening/collaborative-pre-submission`
- Cloud Run revision: `decision-trace-00008-j9s` (100% traffic)
- Public URL: https://decision-trace-742122658452.us-central1.run.app
- Project/region: `project-988bc9fe-092c-4b32-90c` / `us-central1`

## Verification

- Full authenticated suite: **53 passed in 317.24s**
- Real Gemini generation and embeddings: passed
- Live GitHub ingestion: passed
- Real Firestore round trip: passed
- `ruff check --no-cache .`: passed
- `python3 -m compileall -q app *.py`: passed
- `git diff --check`: passed
- Public root: HTTP 200
- Streamlit health endpoint: HTTP 200
- Cloud Run traffic: 100% to `decision-trace-00008-j9s`

## Judge dry-run result

The delayed-preemption/revert path was run as a cold reviewer:

1. Ask: “Why was delayed preemption reverted in kubernetes?”
2. Show historical and current claims, evidence, and the `REVERTED` current card.
3. Open **Agent collaboration trace** and show Evidence Scout, Lifecycle
   Resolver, Provenance Challenger, and Gemini Reconciler.
4. Show the deterministic `REVERTS` explanation and clickable evidence.
5. Submit a changed-assumption reconsideration.
6. Show confirmation: `status: PROPOSED`.
7. Show governing truth remains `REVERTED`.
8. Optionally show Cloud Run and Firestore as the Google Cloud proof segment.

Observed result: all gates passed. The exact Firestore candidate persisted as
`PROPOSED`; the target decision remained `REVERTED`.

## Judge score

The repository contains the judging dimensions but no numeric weighting, so
this is an equal-weight, transparent composite rescaled to 100:

| Dimension | Score |
|---|---:|
| Problem/value clarity | 8/10 |
| Collaborative-track legitimacy | 9/10 |
| Technical depth | 9/10 |
| Google/Gemini integration | 10/10 |
| Differentiation from generic RAG | 9/10 |
| Correctness/provenance | 9/10 |
| Demo quality | 8/10 |
| Production readiness | 8/10 |
| Memorability | 9/10 |
| **Composite** | **88/100** |

The single highest-leverage remaining action is to record the short browser
walkthrough above. Adding another feature is not justified by the evidence.

## Frozen evidence and remaining risks

- Frozen benchmark remains **n=37, structured 76% vs RAG 57%, CAUTION**.
- The shipped branch contains the frozen 37-source-row / 55-domain-record
  corpus and 37 run files per condition.
- The separate local 42-source-row / 63-domain-record expansion remains
  uncommitted, ungraded, and excluded from every claim.
- Remaining P2 items: mutable source URLs without snapshots/hashes, no
  first-class edge evidence, shared Firestore demo state, and the collaboration
  trace requiring one explicit expand action.
- No P0/P1 blockers remain. Product development should now be frozen.
