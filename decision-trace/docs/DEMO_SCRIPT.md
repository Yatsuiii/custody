# DecisionTrace demo script (~4 minutes)

Recording is the one remaining manual step — everything below is verified
to actually work on the live deployment as of 2026-08-17. This is a script
to read/follow while screen-recording
https://decision-trace-742122658452.us-central1.run.app, not a
hypothetical walkthrough.

Every step here was proven live (Stage 8's local acceptance test, then
re-verified against the deployed Cloud Run URL this week) before being
written down — nothing in this script is aspirational.

## Timing plan

| Time | Segment |
|---|---|
| 0:00–0:30 | Hook + one-sentence pitch |
| 0:30–1:00 | The falsifier result (why this exists) |
| 1:00–3:00 | Live walkthrough (the 6 steps below) |
| 3:00–3:40 | Backend proof on Google Cloud (Firestore persistence) |
| 3:40–4:00 | Close |

## 0:00–0:30 — Hook + pitch

> "You're about to touch a subsystem you didn't design. Was this already
> tried and rejected? Chat-with-your-repo tools retrieve documents and
> make you reconcile the mess yourself. DecisionTrace resolves it for
> you — it tells you the currently active decision, not a pile of
> maybe-current maybe-not documents."

Show the live URL loading: https://decision-trace-742122658452.us-central1.run.app

## 0:30–1:00 — Why this exists, not just a claim

On screen: the results table from `RESULTS.md`.

> "We didn't assume structured memory beats RAG — we measured it, and
> re-measured after finding real bugs in our own first attempt. 37 real
> decisions across 4 open-source repos. Naive embedding RAG: 57% combined
> correct. DecisionTrace's structured approach: 76% — clearly ahead, and
> on revert-PR decisions specifically it's already at 94%. The remaining
> gap is one document type: long, template-structured design docs that
> name several rejected alternatives in one section, where citing the
> right decision is easy but stating the specific right reason is
> genuinely harder. That's the mechanism this product is built around —
> and the mechanism we're still actively closing."

## 1:00–3:00 — Live walkthrough (6 steps, ~20s each)

Use the real question from this week's verification pass:

1. **Ask why.** Type: *"Why was delayed preemption reverted in
   kubernetes?"* Show the resolved answer: rationale, PR citations, the
   current-decision card on the right (status: `REVERTED`, active
   decision: the revert PR).
2. **Recover history.** Point at the Timeline panel — the original PR
   (`IMPLEMENTED`) and the revert (`REVERTED`, marked current) both shown,
   not just the latest state.
3. **Surface the revert explicitly.** Call out the status badge and the
   framing text — a reverted decision is never presented as settled
   guidance without saying so.
4. **State current status.** Point at the claim-category tags next to each
   line of the answer (verified historical fact / current active decision
   / inferred advice / missing-uncertain) — every claim is labeled with
   why it should be trusted. Open **Agent collaboration trace** and show the
   four handoffs: Evidence Scout → Lifecycle Resolver → Provenance Challenger
   → Gemini Reconciler. This is the visible collaboration moment.
5. **Record a reconsideration.** This is the step that separates
   DecisionTrace from a chat-with-your-repo tool with a nicer UI — say so
   out loud: *"This isn't just answering questions, it's a place where
   the project's memory actually changes."* Use the "Record a
   reconsideration of this decision" form: type an assumption change,
   submit. Show the new `PROPOSED` candidate decision appear.
6. **Ask a related question again** in the same session — show the
   candidate now shapes the answer (it's live in the index immediately,
   not just saved).

When the decision card is visible, point to its deterministic lifecycle line:
it names the typed `SUPERSEDES`/`REVERTS`/`REAFFIRMS` events that made the
current result. If a candidate is challenged for missing evidence or an
ambiguous lifecycle, leave it as `missing/uncertain`; that fail-closed moment
is part of the product proof, not a demo error.

## 3:00–3:40 — Backend proof on Google Cloud

This is the segment the rubric explicitly asks for ("backend proof on
Google Cloud") — don't skip it.

> "Everything you just saw is running on Cloud Run, backed by Firestore —
> not a local file that disappears when the container restarts."

Show, in order:
1. The Cloud Run console (or `gcloud run services describe decision-trace`)
   — the live revision, the `DECISIONTRACE_STORE=firestore` env var.
2. The Firestore console — the `decisiontrace-decisions` collection, with
   the candidate decision just created in step 5 visible as a real
   document.
3. **Do not cut this step for time.** Restart/redeploy the Cloud Run
   revision on screen, reload the app, ask about the same candidate
   again — show it survived the restart. Every other beat in this script
   (the answer, the timeline, the claim tags) could in principle be faked
   by a good retrieval demo with a nice UI; this step is the one that
   can't be — it requires a real write surviving a real process boundary.
   If the timing is tight, cut length elsewhere (step 2 or 3 of the
   walkthrough) before cutting this.

## 3:40–4:00 — Close

> "Gemini 3.7 via the Google GenAI SDK, Cloud Run, Firestore — all real,
> all measured against a falsifier before we built anything. DecisionTrace:
> collaborating agents reconstruct not just what engineers once decided, but
> which decision actually governs the codebase now."

Show the URL one more time on screen.

## Notes for whoever records this

- The claim-category emoji/labels (📜 / ✅ / 💭 / ❓) read well on camera —
  zoom in on them during step 4.
- If the demo Firestore collection has accumulated extra candidate
  decisions from prior smoke tests, either use a fresh browser session (a
  new `st.session_state` doesn't reset Firestore data, so old candidates
  will still show — that's realistic, not a bug) or note on screen that
  prior test data is visible by design.
- Keep questions close to the benchmark corpus (Kubernetes/Rust/
  Elasticsearch decisions) since that's what's actually seeded — an
  arbitrary out-of-corpus question will correctly return "missing/
  uncertain," which is honest behavior but not what you want mid-demo.
