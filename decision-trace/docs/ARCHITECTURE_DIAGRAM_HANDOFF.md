# Architecture diagram handoff — build the Devpost-facing diagram

For a fresh session picking this up. No prior context assumed. This is
**not** a request to touch `docs/architecture.md`'s existing Mermaid
diagram (leave it alone, see "What already exists" below) — it's a new,
standalone visual asset for the Devpost submission's required
"Architecture Diagram" field.

## Why this exists

Devpost's submission requirements (`allthingsagentichackathon.devpost.com`,
same hackathon DecisionTrace and the sibling Custody project are both
submitting to) state:

> Architecture Diagram with a clear visual representation of your system
> (e.g., how Gemini connects to your backend, database, and frontend).

The Devpost upload field accepts `pdf, ppt, pptx, png, jpg, jpeg`, max
35MB per file — re-verify this against the live rules page before
finalizing, since it was confirmed for Custody's submission on 2026-08-18
but not re-checked here. It wants a **static image**, not a link and not
live Mermaid source.

"Beautifully designed" was the explicit ask, modeled on the diagram
already built for the sibling Custody project this session
(`custody/web/system-diagram.html`, exported to
`custody/web/exports/system-diagram.png`). That diagram went through five
rounds of user feedback before landing — the lessons from that process are
below, and skipping them will very likely reproduce the same mistakes.

## What already exists — don't redo this part

`docs/architecture.md` has one Mermaid diagram, committed as source (not
an image) so it renders natively on GitHub and stays correct without a
toolchain. It's accurate — matches `app/*.py`'s real module/class names,
not an idealized architecture. It covers: `Streamlit UI (app/ui.py)`,
`collaborate.answer()`, `retrieval.DecisionIndex`, `graph.resolve_active()`,
`memory.propose_reconsideration()`, `store.FirestoreDecisionStore`,
Firestore, Vertex AI via the Google GenAI SDK, `gemini-3.7-flash`,
`text-embedding-005`, all inside a `Cloud Run — decision-trace service`
subgraph.

This diagram stays as-is. It's the GitHub-native technical reference; the
new diagram is a separate, more polished asset for the Devpost image
upload, not a replacement.

## The real, verified surface the new diagram must show

Cross-checked against `README.md`'s Architecture section and
`docs/architecture.md` as of 2026-08-18. Don't add anything not on this
list without re-verifying against those files first.

**The product (Cloud Run — decision-trace service):**
- `app/ui.py` — Streamlit UI, the judge-facing frontend
- `app/ingest.py` — live GitHub/KEP discovery + extraction, wired into the
  UI's sidebar ("Live ingest" panel), shells out to the `gh` CLI
- `app/retrieval.py` — `DecisionIndex`, card-level embedding search (not
  raw-document search — this is a deliberate, falsifier-driven design
  choice worth calling out visually if there's room)
- `app/graph.py` — `resolve_active()`, the deterministic lifecycle
  resolver. This is the one component that must read as "plain code, not
  an LLM call" — it's the product's core differentiation claim (never
  presents a reverted/superseded decision as current guidance, by graph
  traversal, not model judgment)
- `app/collaborate.py` — `answer()`, four-way claim categorization
  (verified historical fact / current active decision / inferred advice /
  missing-uncertain), the only component that calls Gemini for generation
- `app/memory.py` — `propose_reconsideration()`, the write path: creates a
  new `PROPOSED` decision with a `reconsiders` edge
- `app/store.py` — `DecisionStore` Protocol, with two implementations:
  `JSONFileDecisionStore` (local dev, no GCP dependency) and
  `FirestoreDecisionStore` (production). Every caller depends on the
  Protocol, never the concrete class — this is why the diagram should
  probably show the Protocol boundary, not just "Firestore" as one box

**Google Cloud (managed infrastructure the product runs on/against):**
- **Cloud Run** — hosts the Streamlit app as a container, built via Cloud
  Build from the repo's `Dockerfile`
- **Firestore** (Native mode, collection `decisiontrace-decisions`) —
  persists every decision record and conversational candidate; survives
  Cloud Run's ephemeral filesystem and scale-to-zero, proven with a real
  kill-and-restart test, not just a code review
- **Vertex AI via the Google GenAI SDK** (`google-genai` package) — every
  model call in the product goes through this SDK, nothing mocked
  including in the test suite
- **`gemini-3.7-flash`** — generation, called from `collaborate.answer()`
- **`text-embedding-005`** — retrieval embeddings, called from
  `retrieval.DecisionIndex`

**What's explicitly NOT Google ADK** — the rubric's "Google Agent
Framework" requirement is satisfied by direct use of the Google GenAI SDK,
one of four frameworks the rubric names explicitly. If the diagram implies
an agent framework, that's wrong; don't add ADK-shaped boxes.

**Data (the evidence trail, worth a small mention, not a full node):**
- `data/decisions.jsonl` — the 55-decision benchmark corpus (`BUILD_SCOPE.md`
  and `RESULTS.md` are frozen evidence artifacts, referenced not drawn)

## Design tokens — already established, don't invent new ones

Unlike a from-scratch project, DecisionTrace already has a real visual
identity, live in production right now (`.streamlit/config.toml` +
`_THEME_CSS` in `app/ui.py`). Copy these values exactly:

```css
:root {
  --dt-bg: #f4f3ee; --dt-panel: #fdfcf9; --dt-panel-2: #f8f6f0;
  --dt-line: #e0ddd2; --dt-ink: #1e1c17; --dt-ink-dim: #6b6858;
  --dt-ink-faint: #9b9786; --dt-accent: #3f6e52; --dt-accent-dim: rgba(63,110,82,0.1);
  --dt-danger: #b5432e; --dt-danger-dim: rgba(181,67,46,0.09);
  --dt-amber: #a6741c; --dt-amber-dim: rgba(166,116,28,0.1);
  --dt-mono: "IBM Plex Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace;
}
```

Status pills already exist in the product (`.dt-pill-accent`,
`.dt-pill-danger`, `.dt-pill-amber`, `.dt-pill-gray`) for
`PROPOSED`/`ACCEPTED`/`IMPLEMENTED`/`REVERTED`/`SUPERSEDED`/`REAFFIRMED`.
If the diagram shows a `Decision` object or its lifecycle anywhere, reuse
these exact pill colors rather than inventing a new status-color mapping.

This happens to be the same "paper" palette family as the sibling Custody
project (`--accent: #3f6e52` in both) — coincidence of two sessions
converging on the same aesthetic, not a shared design system. Don't try to
literally match Custody's diagram; match *this* product's own established
theme, which these tokens already are.

## Design lessons from Custody's diagram — read before starting

Custody's `web/system-diagram.html` went through five iterations this
session. In order, what happened and why, so this session doesn't repeat
the cycle:

1. **First attempt: a stack of labeled section cards with no arrows.**
   Rejected immediately — "looks like a page with many headings... where's
   the connection, flow & all." Lesson: a diagram is arrows carrying
   labels between boxes, not boxes with captions. If you can't draw the
   edge and name what flows on it, you don't understand the mechanism
   well enough yet to draw it.

2. **Second attempt: real topology, organic layout, labeled edges, color
   by edge meaning (trusted-write path, quarantine path, deny/revoke
   path, read/feedback path).** This landed well and became the
   foundation for everything after. This is the shape to aim for
   directly, skipping step 1.

3. **Third attempt: wrapped the core modules in one giant thick-bordered
   box, added ①–⑧ numbered step badges, a full prose 8-item legend below.**
   Feedback: "too many simultaneous things competing for attention" —
   the box, the numbers, the color legend, and the infra nodes were all
   fighting for the same visual weight. Also: numbered badges "made it
   feel more like a presentation slide than engineering documentation."
   Lesson: resist the urge to add a legend/index/numbering system on top
   of a diagram that's already legible from its topology and edge labels
   alone. If you need a numbered walkthrough, that's a separate list in
   the surrounding page text, not baked into the figure.

4. **Fourth attempt: three collapsed zones (input/core/output), heavy
   simplification, moved most infrastructure to a caption line.**
   Feedback (from an external second opinion the user brought back):
   this "felt like a simplified infographic trying too hard to explain
   itself" and lost the real spatial relationships between components —
   "organized complexity... is appropriate here because [it]'s a
   multi-component system." The user's verdict: go back to version 2
   almost unchanged.

5. **Final: version 2, plus three small edits** — a stronger one-line
   subtitle, a faint (not boxed) label/bracket marking which nodes are
   the product's own code vs. managed infrastructure, and slightly
   lighter/greyer styling on the least-important infra nodes (kept
   present, not removed). That's what shipped.

**The actionable takeaway for this diagram:** start at step 2's shape —
real component positions reflecting actual data flow, arrows labeled with
what moves on them, color coding edges by meaning (e.g., read path vs.
write path vs. the resolver's deterministic-code boundary), generous
whitespace, no enclosing box around "the important part," no numbered
badges, no long prose legend. If you want to mark "this is
`graph.resolve_active()` — deterministic code, not an LLM call" as a
scope note, use a small faint bracket/tick the way Custody's final version
does, and **verify by actual coordinates that the bracket doesn't
geometrically enclose a node it shouldn't** — this happened twice in
Custody's session (a bracket meant to span two code modules ended up
visually swallowing Memory Bank and Firestore, which sat between them on
the canvas, because nobody checked the x-ranges). Compute or check every
bracket's bounding box against every node's bounding box before shipping it.

## Suggested shape for this specific diagram

Not prescriptive, but a starting point given the real components above:

- **Left:** Browser / judge, arrow into the Streamlit UI.
- **Center-left, the product's own code (Cloud Run container):** `ui.py`
  branching to two paths — the **read path** (`retrieval.DecisionIndex`
  → embeds via Vertex AI → ranks against the store → **`graph.resolve_active()`**
  as a visually distinct deterministic-code node, maybe the one place
  worth a small "no LLM" scope tick → `collaborate.answer()` → Gemini) and
  the **write path** (`memory.propose_reconsideration()` → `store.save()`).
  `ingest.py` as a smaller side branch feeding new decisions in from
  GitHub.
- **Center-right, the storage boundary:** `DecisionStore` Protocol as a
  thin interface line between the app code and `FirestoreDecisionStore` —
  worth showing as an actual boundary/interface, not just an arrow to a
  database icon, since that abstraction is explicitly why the Firestore
  swap didn't touch any caller.
- **Right, Google Cloud:** Firestore, Vertex AI (branching to
  `gemini-3.7-flash` and `text-embedding-005`), Cloud Run as the
  deployment context wrapping the whole center section.
- Two colored edge families are probably enough: one color for the read
  path, one for the write path, plus maybe a third muted color for
  `ingest.py`'s external GitHub call. Don't invent a fourth or fifth
  meaning unless the diagram genuinely needs it.

## Build method

Same reproducible pipeline used for Custody:

1. Build a real static HTML page with hand-authored inline SVG (no
   diagramming library, no external assets) — e.g.
   `decision-trace/docs/system-diagram.html` or similar, doesn't need to
   be linked from the app or deployed, Devpost only needs the exported
   image.
2. Serve it locally (`python3 -m http.server` from the file's directory)
   and screenshot with headless Chrome at high DPI:
   ```bash
   google-chrome-stable --headless --disable-gpu --no-sandbox \
     --window-size=<W>,<H> \
     --screenshot=<output>.png \
     --hide-scrollbars \
     --force-device-scale-factor=3 \
     http://localhost:<port>/system-diagram.html
   ```
   Use `--force-device-scale-factor=3` or `4` for a crisp, large export —
   Custody's final export was 7040×3760px at ~970KB, comfortably under
   Devpost's 35MB cap.
3. Read the exported PNG back (e.g. via the Read tool) to visually verify
   before calling it done — check for overlapping labels, text clipped at
   the image edge, and bracket/box geometry actually matching the nodes
   it's supposed to scope, per the lesson above.

## Acceptance gates

1. Every real component listed above (product code + Google Cloud
   services + the two named models) appears in the diagram — nothing
   invented, nothing silently dropped, no ADK-shaped boxes.
2. Visual language matches this product's own established tokens
   (`--dt-*` CSS variables above, IBM Plex Mono, the existing pill
   colors) — not Custody's diagram, not a generic new palette.
3. The diagram reads as real system topology with labeled arrows — not a
   stack of section cards (mistake #1 above), not boxed-and-numbered
   (mistake #3), not over-collapsed into three zones losing spatial
   relationships (mistake #4).
4. Any scope bracket/tick's bounding box is checked against every node's
   bounding box and confirmed not to falsely enclose anything.
5. Exported as a static PNG, under 35MB, legible at the resolution
   Devpost displays it — verify by reading the exported file back, not
   just trusting the export command succeeded.
6. Uploaded to the Devpost submission's Architecture Diagram field.

## Non-goals

- Don't touch `docs/architecture.md`'s existing Mermaid diagram.
- Don't touch `app/*.py`, `.streamlit/config.toml`, or any product code —
  this is a documentation/submission asset only.
- Don't add capabilities to the diagram that aren't real and running
  today — if `ingest.py`'s live GitHub ingestion or the Firestore
  kill-and-restart proof aren't obviously "live," check
  `README.md`'s "What's deliberately not in the demo" section before
  claiming something works.
- Don't deploy this page anywhere public unless asked — build it,
  screenshot it, leave it local/undeployed.
