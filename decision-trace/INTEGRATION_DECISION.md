# Product Integration Decision

Branch: `integration/decisiontrace-authority-proof`, cut from the frozen
product commit `1c33d3de169ebbdb874992e9383b632d163b2658`
(`explore/decision-trace-v0`). Never developed on the frozen branch
directly. See `PORT_PLAN.md` for the port scope and
`AUTHORITY_PROOF_ARCHITECTURE_REVIEW.md` (research branch) for the
underlying engine's own design review.

## Cold judge review

Reviewed the live preview
(`https://decisiontrace-preview-authority-proof-742122658452.us-central1.run.app`)
from zero prior context, first-question walkthrough
("Why was delayed preemption reverted in kubernetes?").

**What the first 60 seconds actually communicate:**

1. The problem (orgs accumulate contradictory historical decisions) is
   not stated on the landing screen itself — the app opens straight to
   an empty chat box and a caption. A judge who skips the README and
   goes straight to the live URL has to infer the problem from the
   answer shape, not from framing text on load. This is the one gap
   worth naming.
2. Retrieval-vs-authority is visible immediately once a question is
   asked: the "Current decision" panel doesn't just answer, it shows a
   ranked, excluded candidate (`kubernetes/kubernetes-pr-136254`,
   reason `SUPERSEDED`... in this case `REVERTED`) right next to the
   winner, in one click.
3. The collaborative track is visible but collapsed by default — the
   "Agent collaboration trace" expander requires a click to reveal
   Evidence Scout / Lifecycle Resolver / Provenance Challenger / Gemini
   Reconciler. It's there and it's real (each stage's summary reflects
   actual computation, not placeholder text), but it's not the first
   thing a skimming judge sees.
4. Deterministic authority is the standout: "CURRENTLY GOVERNING:
   `kubernetes/kubernetes-pr-137662`" renders directly under the answer,
   unmissable, within the same ~10-second response.
5. The proof, not an assertion: "View full authority proof" expands to
   name every considered candidate, its exclusion reason, and the exact
   lifecycle edge (`kubernetes/kubernetes-pr-137662 REVERTS kubernetes/
   kubernetes-pr-136254`) that establishes the winner. This is the one
   element competitors' retrieval demos structurally cannot produce —
   it's not prose, it's a structured, checkable record.

**Reconsideration replay** (the strongest single demo moment, verified
live on the preview and separately on a local run): asking the same
question after recording a reconsideration shows the exact same
governing decision, now with a fourth candidate row — the reconsideration
itself — marked `PROPOSED_NOT_ACCEPTED`. Nothing about "what currently
governs" changed; what changed is that the system now explains why the
new candidate doesn't count yet. That is a materially stronger moment
than the pre-session UI had (which would have shown the same governing
truth but with no visible acknowledgment of the reconsideration at all in
this view).

### Scores

| Dimension | /10 | Note |
|---|---:|---|
| Problem clarity | 8 | Clear once a question is asked; not stated on the landing screen itself |
| Collaborative-track legitimacy | 8 | Four real stages, but collapsed by default |
| Technical depth | 9 | Deterministic graph resolution + structured proof schema, not a bolt-on |
| Google/Gemini integration | 8 | Real generation/embeddings/ingestion; live-ingest secret deliberately not wired on this preview |
| Authority-proof differentiation | 10 | The session's core deliverable, visibly working |
| Provenance/auditability | 9 | Exclusion reasons + lifecycle witnesses are independently checkable |
| Demo clarity | 7 | Two clicks (worker trace, full proof) to reach the strongest evidence |
| Production readiness | 7 | Real tests green; live-ingest secret and Firestore mode not exercised on this specific preview |
| Memorability | 8 | "CURRENTLY GOVERNING … WHY" is a distinct, repeatable framing |

**Overall: 82/100.** No benchmark-superiority number is included in this
score or anywhere in this document, per the session's explicit
instruction — this is a qualitative product/demo assessment only.

### Smallest presentation fix, if pursued later (not done this session)

Default-expand "View full authority proof" the first time a
`GOVERNING`/`UNRESOLVED` result renders in a session, rather than
requiring a click — the proof is the product's strongest evidence and
currently one interaction away from a skimming judge. This is a UI-only
change (`app/ui.py`'s `st.expander(..., expanded=False)` call site) and
was deliberately not made this session per the "no large UI rewrite"
constraint; flagged as the highest-leverage next UI change, not applied.

## Integration decision

**READY TO MERGE PRODUCT INTEGRATION** (recommendation only — not
executed; awaiting explicit approval per instruction).

Basis:

- Full offline test suite green (89 tests) plus every real-integration
  suite green (34 tests: memory, retrieval, ingest, collaborate, store
  including the two real Firestore round-trip tests) — 123 tests total
  on this branch, 0 failures, 0 skips attributable to environment.
- `ruff check`, `compileall`, `git diff --check` all clean.
- The existing demo (delayed-preemption walkthrough) still works,
  strengthened by the new proof panel, verified both locally and on a
  live Cloud Run preview.
- Reconsideration flow verified end-to-end, live: governing truth
  unchanged, new candidate visibly excluded with the correct reason.
- Backward compatibility proven directly: a Firestore document shaped
  exactly like a pre-`partial_acceptance` production record
  deserializes with the field defaulting to `False`, no KeyError, no
  migration required.
- Old 76%-vs-57% claim removed from `README.md` and
  `docs/DEMO_SCRIPT.md`; replaced with the architectural positioning
  sentence, not a new number.
- Preview deployment (`decisiontrace-preview-authority-proof`, revision
  `-00001-prq`) live, public, unauthenticated, smoke-tested with no
  console errors and no server-side tracebacks; production
  (`decision-trace`, revision `decision-trace-00008-j9s`) confirmed
  unchanged throughout.

No P0 found. Two P2s, neither blocking:

- **P2**: Proof panel requires one click to expand (see presentation fix
  above) — a polish item, not a defect.
- **P2**: The preview deployment doesn't have the GitHub PAT secret or
  Firestore mode wired (deliberate, to avoid touching production
  credentials/data from a throwaway preview) — live-ingest and
  Firestore-backed persistence were verified in the test suite and, for
  Firestore, against a disposable collection, but not on this specific
  preview URL. A production port would need the same secret-wiring step
  the frozen product's own history already documents
  (`decision-trace/.claude/SESSION_CONTRACT.md`, "Wire the GitHub token
  into production").

No P1 or P0 found.
