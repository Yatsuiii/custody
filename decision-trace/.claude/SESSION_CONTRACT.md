Objective: Produce the hackathon submission package for DecisionTrace per
`decision-trace/HANDOFF.md` step 3: a judge-facing README with spin-up
instructions, an architecture diagram, and a written demo script covering
the same 9-step scenario already proven live (Stage 8 local + this week's
Cloud Run smoke test). Scope excludes actually recording/narrating the
~4-minute video — that requires a human voice/screen capture I cannot
produce; I will hand off a tight, timed script instead, and flag the actual
recording as the user's remaining action.

Branch: explore/decision-trace-v0
Parent: a62f20a (app/store.py, app/ui.py, app/tests/test_store.py,
app/requirements.txt, Dockerfile, .dockerignore remain uncommitted from
prior sessions this week; this session adds submission docs on top,
still uncommitted unless the user asks to commit)

Allowed files:
- decision-trace/README.md (new — judge-facing, not the internal
  BUILD_SCOPE.md/RESULTS.md docs, which stay frozen and untouched)
- decision-trace/docs/architecture.md or decision-trace/docs/ARCHITECTURE.md
  (new — diagram, as Mermaid embedded in Markdown, since there's no image
  tooling here; GitHub/most viewers render Mermaid natively)
- decision-trace/docs/DEMO_SCRIPT.md (new — timed walkthrough script for
  the ~4-minute video, referencing the real deployed URL)
- decision-trace/HANDOFF.md (status update only, at session end)
- decision-trace/.claude/SESSION_CONTRACT.md (this file)

Non-goals:
- No video recording/editing — out of my capability, explicitly handed
  back to the user as the one remaining manual step.
- No edits to BUILD_SCOPE.md, RESULTS.md, or any frozen falsifier
  artifact/script.
- No app code changes this session (store.py, ui.py, etc. stay as they
  are from the last two sessions).
- No further Cloud Run/infra changes — the deployed service from the
  prior session is treated as done; this session only documents it.
- No touching Custody's services/branches or failure-mining/AutomationBench.
- No git commit/push without explicit authorization.

Baseline: N/A (docs-only session, no code under test). Confirm the live
URL still responds before citing it: `curl -sI
https://decision-trace-742122658452.us-central1.run.app/_stcore/health`
expected 200.

Acceptance gates:
1. README.md covers: one-paragraph pitch, the falsifier result as the
   differentiation claim (100% vs 57%, n=37, cited from RESULTS.md's real
   numbers — no invented stats), the live Cloud Run URL, local spin-up
   instructions that actually match HANDOFF.md's real commands, and the
   Google Cloud stack used (Cloud Run + Firestore + Vertex AI/GenAI SDK).
2. Architecture doc has one diagram covering the real components (ui.py,
   collaborate.py, retrieval.py, graph.py, FirestoreDecisionStore, Vertex
   AI/Gemini, Cloud Run) and data flow, matching what's actually in
   app/*.py — not an idealized/aspirational architecture.
3. Demo script is timed to fit ~4 minutes, walks the same 9 steps already
   proven (ask why -> recover history -> surface the revert -> state
   current status -> record reconsideration -> kill process -> fresh
   process -> confirm persistence), and explicitly calls out the moment
   that proves "backend proof on Google Cloud" (Firestore persistence
   surviving a fresh session) since the rubric asks for that specifically.
4. Every factual claim in these docs traces to something verified earlier
   this week (test counts, falsifier numbers, the live URL, the IAM/
   deploy details) — no new unverified claims about behavior.
5. Live URL re-confirmed responding (curl health check) before the README
   is written, so the submission doesn't cite a dead link.

Verification: read the three new docs back and cross-check every number
against RESULTS.md/HANDOFF.md/SESSION_CONTRACT.md history; curl the live
health endpoint once at the end to reconfirm it's still up.

Status: complete

Result: README.md, docs/architecture.md (Mermaid diagram), docs/DEMO_SCRIPT.md
written. Every stat cross-checked against RESULTS.md's real table (100%
vs 57% combined-correct, n=37) and HANDOFF.md's real commands before
being written down. Live URL re-confirmed responding (HTTP/2 200 on
/_stcore/health) both before writing and after, at session end. Video
recording itself is explicitly out of scope (no screen/voice capture
capability here) and handed back to the user as the one remaining manual
step — DEMO_SCRIPT.md is a ready-to-follow, timed script referencing only
things already proven live this week.
