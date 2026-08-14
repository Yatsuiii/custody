# Custody recovery handoff, 2026-08-14 (GUI shipped, live on Vercel, redeployed with F1's data, Reviewer narration, and the N=25 fleet; F1 live cross-department chain proof closed; Best Multimodal UX pass closed via a real Cloud Text-to-Speech modality; fleet scale-up closed at N=25)

## Start here if you are picking this up next

This session built a judge-facing GUI (two static pages: a "Dependency
Cartography" incident view and an "Architecture & Evidence" page) and
deployed it live on Vercel. It also worked through the right next move for
the live fleet proof, through three corrections in a row:

1. A first attempt at just scaling N=5 to N=12 was rejected by the user as
   padding ("dont wanna increase the fleet just for the sake of it"),
   reverted cleanly.
2. Replaced with a two-part plan: prove a genuine live cross-department
   derivation chain (a real proof gap, not a bigger number), *then* scale
   the existing parallel fleet proof as a paired stress-test. User
   confirmed this direction, then separately asked whether scale itself
   was still too low for a "Fleet" track and picked ~20-30 departments
   when asked directly.
3. **Then the actual hackathon page was read** (was not read before this
   point in the session) —
   https://allthingsagentichackathon.devpost.com/ and its `/resources`
   page. Real judging weights: **Innovation & Operational Utility 40%**
   ("how much real-world friction the agent removes autonomously"),
   **Architectural Discipline & Tech Stack 30%** (decoupling, state
   management, security, failure handling), **Demo & Production
   Readiness 30%** (video clarity, repo quality, architecture docs, proof
   of GCP deployment). The Fortified Enterprise Fleet track description
   says "multi-agent orchestration at scale" but states **no numeric
   agent count anywhere**, on either page. There is also a separate
   **Best Multimodal UX award ($5,000, 2 winners)** the GUI work already
   done this session is a real candidate for.
   **Conclusion, agreed with the user:** the live-chain proof is what
   actually moves the score (hits the 40% and 30% criteria directly); a
   bigger N moves nothing in the rubric and risks working *against* the
   30% demo-clarity criterion in a ~4-minute video. The scale-up is now
   explicitly demoted to secondary — cheap to do, but as a single
   reported number, not a UI feature competing for video time.

**Update, 2026-08-14: the chain proof (section 2 below) is now closed,
live-proven on the first run, and redeployed to Vercel.** `scripts/
live_chain.py` / `scripts/chain_gates.py`, proof
`a7bf097fcbce430c821ca655daa6cb07`, `make chain-gates` 20/20 PASS. Added as
a new `F1` entry in `scripts/render_architecture.py`'s `LIVE_PROOFS` and a
new README section. Full write-up in `.claude/SESSION_CONTRACT.md`'s
"Sub-build: F1, a genuine live cross-department derivation chain" section.

**Redeployed to Vercel and verified live, with one real snag found and
fixed along the way.** The `deploy_to_vercel` MCP tool (used for every
prior redeploy) silently corrupted `architecture.html`'s inline `<script>`
when the huge file content was passed as a JSON tool parameter — a manual
quote-escaping error broke `renderWidget`'s first line with a `SyntaxError:
Unexpected string`, which left every gate row and proof card blank on the
live page (caught via `read_console_messages`, not visually obvious at
first glance from a plain screenshot). Switched to deploying straight from
disk with the authenticated `vercel` CLI (`vercel link --project
custody-incident` then `vercel deploy --prod`) instead of retyping file
contents into a tool parameter — eliminates the transcription risk
entirely; **prefer this method for future redeploys of these two files**
over `deploy_to_vercel`. That CLI deploy also surfaced a separate,
unrelated finding: the project's `ssoProtection` was set to
`all_except_custom_domains` (Vercel Authentication gating every
`*.vercel.app` URL, including the production alias), which the earlier
`deploy_to_vercel`-based deploys had apparently never triggered — so the
site started returning a login redirect instead of the page. Disabled via
the Vercel API with explicit user authorization (`ssoProtection: null`);
confirmed public again (`200`, no console errors, F1 widget renders with
real data) at both `custody-incident-cave2.vercel.app/` and
`/architecture.html`. If a future redeploy is done via `deploy_to_vercel`
again, check console errors after, not just that the deploy call
succeeded.

The scale-up (section 3) remains optional/secondary, not started. The Best
Multimodal UX pass (section 4) remains open, not started — a distinct,
currently-unaddressed opportunity.

### 1. GUI: built, verified, deployed live — closed

- `scripts/incident.py` — `compute()` computes the vendor_portal incident
  narrative (blast radius, lineage, revocation) from real code, no
  hand-typed numbers. (An earlier `compute_standing()` for a "runs on every
  write" panel was added then explicitly removed on user request — don't
  re-add it without being asked again.)
- `scripts/render_gui.py` — renders `web/incident.html`, a "Dependency
  Cartography" node-graph page (5 real columns: sources, tool result,
  derived statement, memories, departments; SVG connectors computed from
  live DOM positions; click-to-inspect right panel; working
  "Revoke exact descendants" interaction).
- `scripts/render_architecture.py` — renders `web/architecture.html`, a
  secondary page reading real `proof-out/*.json` artifacts (G1-G5 from
  `scripts/gates.py`'s actual stdout, plus 9 live-proof widgets — R1, R2,
  S1, M1, O1, D1/D2, Auditor, Reviewer, Fleet — each showing the artifact's
  own real captured data, e.g. the actual jailbreak prompt text, the
  actual before/after fact list, not prose describing them). This went
  through two design iterations before landing here: an initial
  prose-heavy version was rejected ("show capability, don't tell"), a
  full 4-reference comparison was done against real security-startup
  homepages before the current direction was picked.
- `make gui` runs both renderers.
- **Deployed live to Vercel** (files-only deploy, no git integration, no
  `.vercel/project.json` in the repo): project `custody-incident`.
  - https://custody-incident-cave2.vercel.app/ (dependency map, served as
    `index.html`)
  - https://custody-incident-cave2.vercel.app/architecture.html
  - Footer links in both templates point at the real GitHub remote
    (`https://github.com/Yatsuiii/custody/blob/main/...`) instead of
    relative repo paths, because only `web/`'s two files are deployed
    standalone — relative `../README.md` links would 404 on Vercel.
  - **Redeploying is manual.** `make gui` regenerates the local HTML but
    does NOT redeploy. If you change the GUI or regenerate data (e.g.
    after the fleet scale-up below), redeploy by calling the `deploy_to_vercel`
    MCP tool again with target `production`, name `custody-incident`, and
    the two files' contents (read `web/incident.html` as `index.html` and
    `web/architecture.html` as `architecture.html` — keep the
    `architecture.html` back-link as `href="index.html"` for the deployed
    copy, matching what's live now).
  - Verified live in-browser (Chrome via `claude-in-chrome`): both pages
    render, nav between them works, revoke interaction works, no console
    errors.

### 2. Live cross-department derivation chain: closed 2026-08-14, live-proven as F1

**This replaces an earlier, abandoned plan.** This session first tried
"scale the fleet from N=5 to N=12" in response to the user worrying that
low idle GCP/Vercel cost reads as "the project is small." That reasoning
was corrected (cost and scale are not the same thing; low idle cost is
serverless architecture working correctly), but the user then separately
said, unprompted: **don't grow N just for the sake of a bigger number —
it has to be a meaningful update.** The N=12 edit to
`scripts/live_fleet.py` was reverted with `git checkout --`; that file is
back to its original N=5 state, unmodified from before this session.
Nothing live was ever run for the N=12 attempt.

**The actual gap, found by comparing what's proven where:**

- `scripts/incident.py` (offline, powers `make incident` and the deployed
  GUI) dramatizes the product's real headline claim: a tool-origin fact
  hops sales -> support -> finance, each hop a `derived_from` edge earned
  by a genuine content-hash match through a `load_memory` retrieval
  (`custody/graph.py`'s `resolve`). This is the whole "identified and
  pulled ... across every department, agent and session since" story. It
  is 100% synthetic/offline — `PlainMemory`, not live Memory Bank.
- `scripts/live_fleet.py` (live, N=5) proves something different and
  narrower: N departments each independently write once, two of them
  happen to trust a tool with the *same name*, and revoking that tool
  reaches both. No department in that script ever retrieves another
  department's memory. There is no live cross-department `derived_from`
  edge anywhere in this codebase's live proofs.
- **So the dramatic story the GUI tells is unproven live.** Nobody has
  shown, against real Vertex Memory Bank, that Custody's core mechanism —
  a derivation edge earned through a real cross-department retrieval,
  followed by a revocation that walks that live edge and removes every
  hop — actually holds outside the pure offline graph. That is a real,
  meaningful gap tied directly to the product's own one-sentence claim,
  not a vanity metric.

**Proposed next step, NOT yet built:** a new script,
`scripts/live_chain.py` (name not final), structured like
`scripts/live_fleet.py` (same `CustodyMemoryBank` / `AgentEngineMemoryBank`
/ `RevokingMemoryBankGraph` wiring, same env vars) but proving a genuine
live chain instead of parallel independent writes:

1. Sales agent: one real ADK Runner/Gemini turn, one tool-origin write
   (a live analog of `scripts/incident.py`'s `sales_session()`).
2. Support agent: a real Gemini turn whose session event is constructed
   as a `load_memory` function response carrying the *exact* text
   `custody.search_memory` just retrieved for Sales's fact — this is what
   earns a genuine `derived_from` edge live, the same content-hash match
   `custody/graph.py`'s `resolve` already does offline, exercised here
   against the real Agent Engine.
3. Finance agent: same pattern, citing Support's restatement.
4. One sibling department (e.g. `engineering`) writes something
   unrelated, as the live "does revocation touch things it shouldn't"
   negative control, same role `untouched_departments` plays in the
   existing fleet proof.
5. Revoke Sales's tool. Confirm live, via `search_memory`, that all three
   real Agent Engine memories (sales, support, finance) are gone and the
   sibling department's memory is untouched.

This is more work than the N=12 edit was (it needs the `load_memory`
event-construction pattern from `scripts/incident.py`'s
`support_session()`/`finance_session()` adapted to real ADK
`Runner`/Gemini turns, not just more dict entries), but it closes a real
proof gap instead of inflating a number that's already proven at N=5.

**User confirmed this direction ("thts a great direction"). Built and closed
2026-08-14.** `scripts/live_chain.py` (new) implements exactly this shape:
sales gets a real ADK Runner/Gemini turn plus a manually-constructed
tool-origin write and its own restatement in one invocation; support and
finance each get a real Gemini reply spliced with a manually-constructed
`load_memory` citation event carrying the exact text live `search_memory`
returned for the upstream department's restatement, earning a genuine
content-hash-matched `derived_from` edge each hop; engineering is the
independent negative control. `scripts/chain_gates.py` (new) mirrors
`fleet_gates.py`'s discipline exactly: offline structural checks
independently re-deriving the expected removed/untouched sets from the
producer's own JSON, plus 6 independent live Memory Bank rereads by a
`memory_id_for`-recomputed name. Proof `a7bf097fcbce430c821ca655daa6cb07`,
`proof-out/live-chain.json`, `make chain-gates` 20/20 PASS on the first
run. Landed as its own numbered proof, `F1`, in `scripts/
render_architecture.py`'s `LIVE_PROOFS` list (own widget, `widget_chain`)
and a new README section, rather than folding into the existing "Fleet
N=5" row, since it proves a different property than that row does. Full
write-up: `.claude/SESSION_CONTRACT.md`'s "Sub-build: F1, a genuine live
cross-department derivation chain" section.

### 3. Fleet scale-up: demoted to optional/secondary after reading the real rubric

The user raised the N=12 idea again after seeing the live-chain direction,
reasoning that "Fleet" track judging might score visible scale of the
governed population separately from mechanism correctness, and picked
~20-30 departments when asked directly what would read as credible. **That
reasoning was then checked against the actual hackathon page** (see the
top of this file) rather than assumed. Finding: the real judging weights
(Innovation & Operational Utility 40%, Architectural Discipline & Tech
Stack 30%, Demo & Production Readiness 30%) and the Fortified Enterprise
Fleet track description mention "at scale" but state **no numeric agent
count anywhere**. The user agreed with this reading. Consequence: this
scale-up is no longer treated as something the score depends on. It only
went from "reconsidered, paired with #2" to "optional, lightweight" — it
was not cancelled outright, since it's still cheap and the user hasn't
said to drop it.

**If this is picked up:** do it only after #2 (the live chain) exists, and
keep it minimal enough that it doesn't cost video time in the ~4-minute
demo — a single reported number ("proven at N=25, not just N=5"), not a
UI feature, not a wall of rendered department cards competing with the
30%-weighted demo-clarity criterion. Concretely, if built:
- Pick a real target in the 20-30 range and a plausible, non-repetitive
  set of department names — reuse the existing naming style
  (`legal_review_tool`, `hr_disclosure_tool`, etc.), not `dept_1`,
  `dept_2` placeholders.
- Update `scripts/fleet_gates.py`'s hardcoded `== 5`/`== 2`/`== 3` checks
  (lines ~46-48) to match whatever the final chosen N/shared/untouched
  split actually is — read this from the real run's JSON, don't hand-type.
- Update README's "### The fleet at N=5" section and
  `render_architecture.py`'s `LiveProof("Fleet N=5", ...)` entry only if
  built — surface the number in prose/stats, not as an expanded GUI
  section.
- Regenerate (`make gui`) and redeploy to the same Vercel project
  (`custody-incident`) per section 1's instructions above, only if the
  GUI actually changed.

**Non-goals:** do not also touch G1, the Auditor, or the Reviewer proofs.
Do not fabricate or hand-type any numbers before a real run produces them.
Do not scale N before the live-chain proof (#2) exists. Do not let this
scale-up grow into a GUI feature that takes attention away from the
demo-video clarity the rubric actually scores.

**Closed 2026-08-14, picked up after the multimodal pass, exactly as
scoped above.** `DEPARTMENT_TOOLS` in `scripts/live_fleet.py` extended
5 → 25 (sales/finance still share `cross_dept_export_tool`; 23 distinct
plausibly-named tools, no `dept_N` placeholders). `make live-fleet` ran
live end to end on the first attempt, proof
`5617b30b169840928abfff93f08a0145`: all 25 departments' real ADK/Gemini
turns and tool-origin writes succeeded, one revocation removed exactly
the 2 sharing departments' records, the other 23 stayed untouched.
`scripts/fleet_gates.py`'s three hardcoded checks were replaced with
checks that independently recompute the expected sets from
`live_fleet.py`'s own constants rather than a second hand-typed number.
`make fleet-gates` reported 35/35 PASS (10 offline + 25 independent live
Memory Bank rereads). `make check` 319/319, `make gates` unaffected.
README's fleet section and `render_architecture.py`'s `LiveProof` entry
(`Fleet N=5` → `Fleet N=25`) updated; the widget's shape is unchanged, it
now just lists 23 untouched names instead of 3 — confirmed in-browser
this reads as a longer list, not a new UI section. Regenerated and
redeployed to the same Vercel project via the `vercel` CLI (confirmed
with the user first). Verified live at
`custody-incident-cave2.vercel.app/architecture.html`, no console errors.
Full write-up in `.claude/SESSION_CONTRACT.md`'s "Sub-build: fleet
scale-up, N=5 to N=25" section.

### 4. Best Multimodal UX award ($5,000, 2 winners) — real opportunity, not yet acted on

Found while reading the hackathon page for section 3 above, not previously
tracked anywhere in this project's planning docs. This is a specialty
award separate from the Fortified Enterprise Fleet track prize, and the
GUI built and deployed this session (Dependency Cartography +
Architecture & Evidence, live at the Vercel URLs in section 1) is a real,
already-built candidate for it. Nothing has been done specifically to
target this award — no polish pass framed around it, and it isn't
mentioned in the README or any submission-prep material yet. Worth a
deliberate look before submission: is the GUI good enough as-is to enter
for this award, or does it need a targeted pass (this is a separate
question from whether it works for the main track's Demo & Production
Readiness criterion, which it already satisfies).

**Closed 2026-08-14.** Checked live first, rather than assumed: neither
the hackathon's main page nor its rules page define a rubric for this
award beyond its name and prize ($5,000, 2 winners). Given that, and given
that the GUI as built was single-modality (HTML/SVG, text and graph
visuals only), the user chose to scope a genuine second modality rather
than a cosmetic polish pass or skipping the award. Built: the Custody
Reviewer's real, already-live Gemini-drafted verdict is now narrated as
speech through a real Google Cloud Text-to-Speech call
(`scripts/live_narration.py`), a second, genuine audio modality tied to
content that already exists, not a forced use of an unrelated Google AI
product (the project's own contract already warns against inventing a Veo
use). Live proof `26f576c3ffe74958938b383b57755aee`, `make live-narration`
first-run success, `make narration-gates` 14/14 PASS (offline structural
checks plus one independent live Cloud Text-to-Speech re-call). Surfaced
in the GUI as a new "Narration" widget in `scripts/render_architecture.py`
(`web/architecture.html`, next to the existing Reviewer widget): the
verdict text plus a user-initiated `<audio controls>` player, the audio
embedded as a `data:audio/mpeg;base64,...` URI encoded at render time, no
autoplay. `make check` still 319/319 offline; `make gates` unaffected
(G1-G4 PASS, G5 correctly BLOCKED). Regenerated (`make gui`) and
redeployed to the same Vercel project (`custody-incident`) via the
`vercel` CLI, per this file's own documented preferred method; verified
live in-browser at both `custody-incident-cave2.vercel.app/architecture.
html` and the root page, no console errors, the audio widget renders and
plays real narrated speech matching the on-screen verdict text. Full
write-up in `.claude/SESSION_CONTRACT.md`'s "Sub-build: Reviewer
narration" section and `README.md`'s new "Reviewer narration" section.

---


This is a live handoff document for Claude or another coding agent. Continue
from the current repository state. Do not restart the project, redesign the
product, revert the dirty tree, or redo passing work. Read this file, then read
`.claude/SESSION_CONTRACT.md`, `README.md`, `DECISIONS.md`, and the current
diffs before editing.

## Start here if you are the next session

The user asked, on request, to review the "fleet" section of the hackathon
product-mapping table against actual code, then build the gaps found for
real, one at a time, each closed with its own live proof and its own
handoff so work can continue in a fresh Claude session. Three gaps were
found (`.claude/SESSION_CONTRACT.md`, "Fleet review, 2026-08-14" section);
user's stated order: **Auditor, then Reviewer, then N agents.** All three
are now closed; the user chose N=5 for the third.

1. **Provenance Auditor — closed 2026-08-14**, live-proven. See below.
2. **Custody Reviewer — closed 2026-08-14**, live-proven. See below.
3. **N department worker agents — closed 2026-08-14**, live-proven, N=5.
   See below. All three fleet-review findings are now closed.
4. **Legible daily heartbeat — closed 2026-08-14**, small addition on top
   of the Auditor. `/auditor`'s response and a new `custody-auditor`
   structured Cloud Logging entry now carry `elapsed_days_since_seed`, so
   G5's accumulating span is readable day-by-day without manual timestamp
   diffing. See below.

## Provenance Auditor: closed 2026-08-14, live-proven

`/vouch` grants trust; `/demote` (new) withdraws it, with the same
cross-department refusal rule (`custody/catalog.py`'s `TrustCatalog.demote`,
mirroring `request`). Demotions are durably logged
(`custody.firestore_store.FirestoreDemotionLog`, create-fails-if-exists,
replay-on-construction, same pattern as `FirestoreAuditorLog`). The
existing daily Cloud Scheduler `/auditor` tick (G5's heartbeat) now also
sweeps every outstanding demotion through `CustodyGraph.revoke`,
deterministically — no LLM anywhere in this path, consistent with the
project's own "no model decides a fact" rule. `CustodyGraph.revoke`'s
existing idempotency (keyed on the demotion's own deterministic id) meant
no second bookkeeping table was needed.

Redeployed `custody-control-plane` to Cloud Run revision
`custody-control-plane-00004-ttb` (same service, same env, same posture,
user-authorized live during the session — the original scoping did not
anticipate needing a redeploy). Live proof (`make live-auditor`, proof
`668ad6bb08384da889c76a008e6a218d`, `proof-out/live-auditor.json`): demote
a live tool, confirm via an immediate `GET /custody/{id}` reread that
*nothing* is revoked yet (the async gap is real, not simulated), trigger
`/auditor`, confirm via a second, independent live reread
(`scripts/auditor_gates.py`, its own `gcloud`-derived URL, not the
producer's) that the record now carries the swept revocation.
`make auditor-gates` reports 9/9 PASS. 310/310 offline tests pass
(`tests/test_catalog.py`, `tests/test_control_plane.py`,
`tests/test_firestore_store.py` all extended). Full write-up in
`.claude/SESSION_CONTRACT.md`'s "Sub-build: real Provenance Auditor"
section and `README.md`'s new "The Provenance Auditor" section.

**Side effect worth knowing:** the redeploy meant `proof-out/g1.json` was
regenerated too (`make live-g1`), since G1's own evidence had recorded the
now-superseded Cloud Run revision. `make gates` reports G1 PASS against
the fresh evidence, revision `custody-control-plane-00004-ttb`. No other
G1 behavior changed.

## Custody Reviewer: closed 2026-08-14, live-proven

`custody/review.py` (new module) closes the fleet-review finding that the
only live Gemini call in the repo was a connectivity echo
(`scripts/live_g1.py`'s `_gemini_proof`, asked to return a fixed string).
`draft_verdict` takes one `Quarantined` item (`custody/service.py`) and an
injected `explain` callable, returning a `Verdict` (`department`,
`source_tool`, `summary`, `drafted_at`) — no trust or origin field, and the
module imports neither `custody.catalog` nor `custody.graph`, checked by
both a unit test and an AST-parse test in `tests/test_review.py` (5 new
tests, 315/315 offline total) so a future edit that wires either import
back in fails the suite rather than silently opening a fact-deciding path.

No control-plane or Cloud Run change was needed: the quarantine item is
produced in-process by the same `ControlPlane.ingest` logic G2 already
proves offline, so the only new live surface is the Gemini call itself.
`make live-review` (proof `22d187b18ff54ccd809c7eeff52e6394`,
`proof-out/live-review.json`): an ungranted tool's response carrying a
per-run random marker is quarantined, then `gemini-3.5-flash` through
Vertex AI is given that exact text and asked to draft a verdict. The
response correctly explained the attempted export and reproduced the
marker, proving the call read the specific quarantined content rather than
echoing a fixed string. `make review-gates` reports 9/9 PASS: 8 offline
structural checks plus one independently issued, separate Gemini call
under the project's own credentials at judge time (there is no durable
Cloud resource to reread here, so the independent check re-makes the live
call instead of re-reading one, the same substitution O1 made for Cloud
Trace storage). Full write-up in `.claude/SESSION_CONTRACT.md`'s
"Sub-build: real Custody Reviewer" section and `README.md`'s new "The
Custody Reviewer" section.

**Non-goal, stated in the artifact and every write-up:** no console or
human-facing review queue exists yet. A verdict is read from
`proof-out/live-review.json`; any resulting demotion or revocation still
goes through the existing `/demote`/`/revoke` endpoints, driven by a
human.

## N department worker agents: closed 2026-08-14, live-proven, N=5

Only one live ADK agent had ever run before this, once per proof script,
one department per invocation — the fleet's own claim, that a compromised
tool is "identified and pulled ... across every department, agent and
session," had never been exercised at N>1. Checked in code before
scoping, not assumed: `CustodyGraph.revoke` (`custody/graph.py`) matches
descendants by tool name alone, and `CustodyRecord` carries no department
field at all — intended, matching the claim above, but untested at scale.

`scripts/live_fleet.py` (new) runs five live department worker agents
(`sales`, `legal`, `hr`, `finance`, `engineering`), each a real ADK
`Runner`/`gemini-3.5-flash` conversational turn plus one tool-origin
write, through the exact `CustodyMemoryBank` -> `AgentEngineMemoryBank`/
`write_record` wiring G1 already proved. All five share one
`CustodyMemoryBank` instance (one process-wide `CustodyGraph`, mirroring
production, not five isolated ones) against the one already-owned Agent
Engine `6936011268348182528` — no new Cloud Run services or Agent Engine
identities; Memory Bank's own `{app_name, user_id}` scoping is what
separates the five departments. `sales` and `finance` independently trust
and invoke a tool with the *same name*, `cross_dept_export_tool`; `legal`,
`hr`, and `engineering` each use a distinct tool name. No changes to
`custody/graph.py`, `custody/catalog.py`, `custody/origin.py`,
`custody/control_plane.py`, or any `custody/adapters/*` file — this is a
proof-at-scale build over already-correct, already-tested mechanisms, not
a new one.

Live proof (`make live-fleet`, proof
`2f5461ce99ba46aebe7f43ac72595612`, `proof-out/live-fleet.json`): all five
departments' tool-origin facts are written and independently retrievable;
one revocation of the shared tool (`RevokingMemoryBankGraph.revoke`)
removes exactly `sales` and `finance`'s tool-origin memories from both
departments, while `legal`, `hr`, and `engineering`'s own memories stay
retrievable, untouched. `make fleet-gates` (new,
`scripts/fleet_gates.py`) reports 15/15 PASS: 10 offline structural
checks plus 5 independent live Memory Bank rereads (`memories.get` by a
`memory_id_for`-recomputed name, not the producer's claim — 2 confirming
deletion, 3 confirming survival). `make check` 315/315 offline, unaffected.
`make gates` reports the same baseline as before this sub-build (G1/G2/G3/G4
PASS, G5 correctly BLOCKED). Full write-up in `.claude/SESSION_CONTRACT.md`'s
"Sub-build: N department worker agents" section and `README.md`'s new "The
fleet at N=5" section.

**Non-goal, stated in the artifact and every write-up:** this does not test
`TrustCatalog`'s per-department grant boundary (a department cannot
vouch/demote another's tool) — that is already proven offline and live,
unchanged, by the Provenance Auditor sub-build above. This build proves the
derivation graph's cross-department revocation *reach* instead, a
different, previously-unproven property.

## Legible daily heartbeat: closed 2026-08-14

Raised on request, after the Auditor landed: the daily Scheduler-driven
`/auditor` tick only ever produced generic Cloud Run access-log entries
(method, URL, status, timestamp) — a judge would have had to manually diff
timestamps across days to see G5's elapsed-time claim at all, and every
day's entry would look identical either way. Small, additive fix, not a
new gate: `ControlPlane.auditor` (`custody/control_plane.py`) now reads
the seed record back through the existing `graph.record` port, computes
`elapsed_days_since_seed` from its durably-stamped `admitted_at`, and
writes the full heartbeat payload to a new structured log,
`custody-auditor`, mirroring O1's `custody-observability` pattern. `None`
offline (the pure in-memory graph never stamps `admitted_at`); a real
integer once the durable, Firestore-backed seed exists. The structured
log write only happens when a `log_client` is configured, so no
offline/local run needs `google.cloud.logging` credentials — 319/319
offline tests pass, all three new behaviors (the `None` case, the
opt-in log write, that every tick logs, not just the first) covered in
`tests/test_control_plane.py`.

Redeployed `custody-control-plane` again, to revision
`custody-control-plane-00005-s2k` (third redeploy this session, same
service/env/posture each time, user-authorized live each time). Verified
live: one manual `/auditor` call returned `"elapsed_days_since_seed": 0`
and the identical payload landed in
`projects/project-988bc9fe-092c-4b32-90c/logs/custody-auditor`
(`insertId 1pm8pk5f30azdx`) within seconds. Today's own Scheduler-triggered
fire (`2026-08-14T06:00:03Z`) had already happened, against the prior
revision, a few minutes before this redeploy landed, so it does not carry
the new field — every fire from tomorrow's `06:00 UTC` onward will. No new
`make *-gates` script: this is not a new capability with its own
acceptance gate, it is legibility for G5's still-accumulating span, which
`scripts/scheduler_gates.py` will read once real days exist. `make gates`
unaffected (G1-G4 PASS, G5 correctly BLOCKED). Full write-up in
`.claude/SESSION_CONTRACT.md`'s "Sub-build: legible daily heartbeat"
section.

## Lane and artifact

Lane: agentic security infrastructure, built as an evidence-gated systems
project for the Google All Things Agentic Hackathon, Fortified Enterprise Fleet.

Six capabilities are complete and independently judged:

- G1 (Cloud Run/Vertex/ADK/Memory Bank) and R1 (stale Registry): complete
  before the S1/M1/O1 session began.
- S1 (Gateway): `proof-out/live-gateway.json`, `make gateway-gates` 20/20 PASS.
- M1 (Model Armor): `proof-out/live-model-armor.json`, `make model-armor-gates`
  9/9 PASS.
- O1 (Observability): `proof-out/live-observability.json`,
  `make observability-gates` 7/7 PASS.
- **R2 (dispatch-bound attestation, new this session):**
  `proof-out/live-revision-binding.json`, `make revision-binding-gates`
  13/13 PASS. Closes R1's own stated gap: an allowed `tools/call` is now
  cryptographically bound, server-side, to the `tools/list` read that
  authorized it.
- **D2 (selective live Memory Bank deletion):**
  `proof-out/live-memory-deletion.json`, `make memory-deletion-gates` 7/7
  PASS. A second, additive, opt-in write path
  (`custody/adapters/memory_bank.py`) makes revoked records genuinely
  deletable from live Memory Bank.
- **G1 migration onto D2's write path (new this session, 2026-08-14):** G1's
  live ADK Runner now writes through `AgentEngineMemoryBank`/`write_record`
  instead of `ingest_events`. Found and fixed a real integration gap first:
  `custody/adapters/adk.py`'s `_SessionRebuilding` never proxied
  `write_record`, so `CustodyMemoryBank` (what the real `Runner` sees) could
  not have reached D2's path regardless of downstream, until fixed. Live
  end to end against Agent Engine `6936011268348182528`:
  `proof-out/g1.json`, `make gates` reports G1 PASS reading the new shape.
  Also proves selective deletion through G1's own wiring (a tool-origin
  write, confirmed retrievable, then confirmed gone after its tool is
  revoked, sibling conversational memory untouched) and answers the
  retrieval-quality question live rather than assuming it: `write_record`
  returns two raw, unmerged per-event facts where `ingest_events` returned
  one Memory-Bank-synthesized fact. See `DECISIONS.md` #2 and
  `README.md`'s deletion section for the full write-up.

An eighth, G5's elapsed-time record, is **started and running, structurally
cannot be "complete" until real calendar time passes** — see below.

This list predates the Provenance Auditor, Custody Reviewer, N=5 fleet, and
F1 chain sub-builds recorded further down this file and in
`.claude/SESSION_CONTRACT.md` — treat those, not this stale list, as
authoritative for anything built after G1's migration.

README.md and `.claude/SESSION_CONTRACT.md` are authoritative for all claim
text; do not restate any of it from memory, read them.

## Git and working-tree state

- Branch: `feat/memory-provenance`
- Commits landed: `df334f1` (S1 fix + accumulated G1/R1 work), `94bcad4`
  (M1), `68f1b88` (G5 persistence/Scheduler start), `9c4174b` (O1),
  `7f7ea00` (R2 + D2), `0b4a816` (G1 migration onto D2's write path),
  `f9e19cd` (Provenance Auditor), `ce54bad` (Custody Reviewer), `5d377fe`
  (N=5 fleet).
- **Working tree carries an uncommitted `HANDOFF.md` update as of this
  handoff**: confirming G5's natural Scheduler fire and correcting this
  file's earlier wrong instruction about the `custody-cold-start-check`
  label (see "G5" section below). Not yet committed — commit only on
  explicit user authorization, same rule as every other checkpoint here.
  Confirm with `git status` before assuming otherwise; do not trust this
  line if time has passed.
- None of the landed commits are pushed. Do not push without explicit
  authorization.

```sh
git status --short --branch
git diff --check
git log -8 --oneline --decorate
```

## Previously proven state, do not redo

- G1, R1, S1, M1, O1, R2, D2, the Provenance Auditor, the Custody
  Reviewer, and the N=5 department fleet, as above.
- Structural TOOL roots and MODEL/DERIVED descendants are already enforced.
- Offline G2, G3, G4 pass; `make gates` reports 4 PASS, 0 FAIL, 1 BLOCKED (G5,
  correctly BLOCKED — its elapsed-time requirement is real, not a bug).

Known limitations that must remain explicit unless new direct evidence changes
them:

- **Closed 2026-08-14: G1's live ADK Runner now writes through D2's path
  and its memories are selectively deletable.** Any memory G1 wrote earlier
  through the old `ingest_events` path (before this session) remains
  outside what D2's mechanism can delete — that history does not
  retroactively become deletable, only writes from this migration onward.
- Behavior-only drift with identical `tools/list` is outside R2's claim by
  design — would need the server to attest its own running code identity, a
  materially different problem, deliberately not attempted.
- R2's replay ledger and D2's write path are correct per-process; nothing
  here claims multi-instance replay safety beyond the single-owned-instance
  scope R1/S1 already required.
- O1 does not independently verify Cloud Trace's own span storage — this
  project's Cloud Trace v1 API returns no default trace bucket for any trace
  exported to it, and v2 has no read endpoint. The independently-verified
  claim is the trace ID/span ID/digest binding recorded in Cloud Logging, not
  Cloud Trace storage. Do not claim more than that.
- The Gateway proof covers one owned Agent Runtime identity, one registered MCP
  projection, and four controlled calls. The Model Armor proof covers one
  owned Template and two controlled calls. Neither proves fleet-wide coverage.

## Owned Google Cloud scope

```text
project id:      project-988bc9fe-092c-4b32-90c
project number:  742122658452
region:          us-central1
organization:    521713171342

Agent Gateway:   custody-fleet-egress
AuthzExtension:  custody-fleet-iap-enforced
AuthzPolicy:     custody-fleet-request-authz
Registry service: custody-export-mcp
Registry MCP projection:
  agentregistry-00000000-0000-0000-8247-c8250af4b9b8
Agent Runtime (Gateway probe):
  projects/742122658452/locations/us-central1/reasoningEngines/5289382654590844928
Agent Runtime (G1/O1/D2):
  projects/742122658452/locations/us-central1/reasoningEngines/6936011268348182528
Registered Runtime Agent:
  agentregistry-00000000-0000-0000-5b70-78deb73916d5
Runtime principal:
  principal://agents.global.org-521713171342.system.id.goog/resources/aiplatform/projects/742122658452/locations/us-central1/reasoningEngines/5289382654590844928
MCP endpoint (custody-export-mcp, now serving R2's attestation middleware):
  https://custody-export-mcp-anexdhueiq-uc.a.run.app/mcp
  (last live revisions: custody-export-mcp-00011-rm5 / -00012-8kz; the
  service accepts CUSTODY_ATTESTATION_SECRET and
  CUSTODY_ATTESTATION_TTL_SECONDS env vars now, in addition to the existing
  CUSTODY_MCP_REVISION)
Model Armor Template:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/templates/custody-approved-tool-ingress
Control plane (Cloud Run, public):
  https://custody-control-plane-742122658452.us-central1.run.app
Firestore database:
  projects/project-988bc9fe-092c-4b32-90c/databases/(default), Native mode, us-central1
Cloud Scheduler job:
  projects/project-988bc9fe-092c-4b32-90c/locations/us-central1/jobs/custody-g5-auditor
Observability Cloud Logging log:
  projects/project-988bc9fe-092c-4b32-90c/logs/custody-observability
```

Repo-local Google credentials/configuration live under ignored `.gcloud/`.
Never print, copy, or commit credential contents.

**Live IAP resting state (S1's projection), last confirmed 2026-08-13:** exact
safe deny — `api.getAttribute('iap.googleapis.com/mcp.toolName', '') in
['custody_policy_canary', '']`. Re-read before any future mutation, never
assume it.

## R2: what was built (dispatch-bound attestation)

Scope: close R1's own stated gap — an allowed `tools/call` was not
cryptographically bound to the `tools/list` read that authorized it, and
IAP's static CEL conditions cannot carry a per-request digest across two
separate calls, so only the owned MCP server could close this, not the
Gateway.

`custody/revision.py` gained `mac`, `SurfaceAttestation`, and
`AttestationAuthority` (mint/verify, HMAC-signed, short-TTL, single-use
nonce, stdlib-only). `live/registry_attack/server/server.py` gained
`SurfaceAttestationMiddleware`: mints a token per tool on every
`tools/list`, and on `tools/call` recomputes the tool's live digest at the
instant of dispatch and refuses to run it on any digest mismatch, expiry, or
replay, before the tool body executes.

**A real implementation bug was found and fixed mid-build, not guessed at
against live infra:** the obvious channel, `MiddlewareContext.message.meta`,
does not carry the caller's token. FastMCP's own `tools/call` dispatcher
(`fastmcp/server/server.py`, `_call_tool_middleware`) rebuilds
`CallToolRequestParams(name=key, arguments=arguments)` from scratch before a
middleware ever sees it, discarding the request's real `_meta`. The token
only survives in the low-level MCP SDK's `request_ctx` contextvar, read via
`Context.request_context.meta`. Root-caused by reproducing in-process
(`fastmcp.Client(server.mcp)`, no live Cloud Run needed) before touching
live infra a second time.

`ToolSurface.from_tools_list` (`custody/revision.py`) now strips `_meta`
before computing a tool's revision digest — otherwise R2's own per-call
token would make every read's digest different, breaking R1's stability
guarantee. Regression test:
`test_per_response_meta_does_not_change_a_revision`.

Live proof: `scripts/live_revision_binding.py` deploys v1, mints a token,
positive-dispatches, replays the same token (refused, `REPLAYED`),
redeploys to v2, presents the stale v1 token (refused, `DIGEST_MISMATCH`,
dispatch count unmoved), then dispatches normally with a fresh v2 token.
`scripts/revision_binding_gates.py` independently rereads both denial log
entries and both Cloud Run revisions from Google Cloud by their own
server-issued identifiers.

**Non-goal, stated in every artifact:** closes the declared-surface TOCTOU
only. A behavior-only change under an identical `tools/list` remains
undetected — would need the server to attest its own running code identity.
Replay state is process-local, same single-instance scope R1/S1 already
require.

## D2: what was built (selective live Memory Bank deletion)

Scope: G3 proves revocation across `CustodyGraph`, but has never deleted the
underlying memory from live Memory Bank. Checked live twice against Agent
Engine `6936011268348182528` and closed as not viable through G1's
`ingest_events` write path: the API returns no created-memory name, and a
metadata-based consolidation guard (`REQUIRE_EXACT_MATCH`) also failed live
— two records with different `custody_record_id` metadata still collapsed
into one memory.

On request, a different write path was tested live instead of reasoned
about: `agent_engines.memories.create(config={"memory_id": <id>})` does not
share that consolidation behavior. Built as a **second, additive, opt-in**
write path:

- `custody/memory_bank.py`: `memory_id_for(record_id)`, a pure hash mapping
  a `CustodyRecord.id` to a valid Memory Bank `memory_id` — no stored state,
  always recomputable.
- `custody/service.py`: `RecordWriter` protocol.
  `CustodyMemoryService.add_session_to_memory` writes one record at a time
  through `downstream.write_record` when a downstream offers it; falls back
  to the existing whole-session `add_session_to_memory` otherwise. Every
  existing downstream (offline fakes, G1's `ingest_events` adapter) is
  **unchanged**.
- `custody/adapters/memory_bank.py`: `AgentEngineMemoryBank` (writes via
  `memories.create`) and `RevokingMemoryBankGraph` (wraps any graph's
  `revoke`, then deletes each removed record's memory by the same computed
  name).

Live proof (`scripts/live_memory_deletion.py`): one session writes two
trusted, different-tool records; both retrievable via `search_memory`;
revoking one tool deletes exactly its memory; a subsequent `search_memory`
no longer returns it while the sibling tool's memory is untouched.
`scripts/memory_deletion_gates.py` independently recomputes `memory_id_for`
for both records rather than trusting the producer's claim.

**Non-goal, as originally scoped:** at the time D2 was built, migrating G1
onto this path was explicitly deferred. **Done in the next session,
2026-08-14** — see "G1 migration" below. Content G1 wrote before that
migration, through the old `ingest_events` path, remains outside what this
mechanism can delete.

## G1 migration: G1's own writes are now selectively deletable

Scope: close the one gap D2 deliberately left open — G1's live ADK Runner
still wrote through `ingest_events`, so nothing it wrote could be
selectively deleted, even though D2's mechanism existed.

**A real integration bug was found and fixed first, not assumed away.**
`custody/adapters/adk.py`'s `_SessionRebuilding` — the wrapper
`CustodyMemoryBank` (the ADK-facing shell a real `Runner` requires) puts
between `CustodyMemoryService` and any downstream — proxied only
`add_session_to_memory` and `search_memory`. `CustodyMemoryService`'s own
capability detection (`getattr(self.downstream, "write_record", None)`)
runs against `self.downstream`, which for `CustodyMemoryBank` is always a
`_SessionRebuilding` instance, so a real ADK `Runner` could never have
reached `write_record` regardless of which downstream `CustodyMemoryBank`
was given. Fixed additively: `_SessionRebuilding.__post_init__` now sets
`self.write_record = inner.write_record` only when the wrapped downstream
offers it. Confirmed safe by usage: only `scripts/live_memory_bank.py` and
tests using `InMemoryMemoryService` (which never offers `write_record`)
construct `CustodyMemoryBank`.

`scripts/live_memory_bank.py`'s `prove_adk_memory_bank` now builds its
downstream from `AgentEngineMemoryBank` instead of the removed
`ingest_events`-based `BlockingAgentPlatformMemoryBank`. The real
Runner/Gemini/conversational leg is unchanged in shape and behavior. A
second, direct write — one real ADK event carrying a trusted tool's
`function_response`, admitted through the same `CustodyMemoryBank`
instance — proves selective deletion through G1's actual wiring: the
conversational turn's records carry no `source_tool` and so cannot be
targeted by `revoke(tool=...)`, so this tool-origin write is what makes the
claim demonstrable, the same shape D2 already proved standalone.

Live proof (`make live-g1`, evidence in `proof-out/g1.json`): the tool-origin
memory is retrievable via `search_memory` before its tool is revoked, and
gone afterward, while the untooled conversational memories stay untouched.
`make gates`'s G1 judge (`scripts/gates.py`) was updated to match the new
evidence shape and now also independently recomputes `memory_id_for` for
the revoked record rather than trusting the producer's claim, plus checks
the before/after `search_memory` results directly — the same discipline
`memory_deletion_gates.py` already used for D2. Reported PASS against this
session's live evidence.

**Retrieval quality, decided and documented live, not assumed:** the
pre-migration baseline (`ingest_events`) returned one Memory-Bank-synthesized
fact merging both admitted events' content ("Sales exports require a
signed approval, and the audit identifier is b888ba0c..."). The
post-migration path (`write_record`) returns two separate, unmerged, raw
per-event facts instead — no cross-event synthesis, by design, since
`write_record` trades Memory Bank's own server-side consolidation for a
deterministic per-record `memory_id`. This is the exact tradeoff
`DECISIONS.md` #2 named before it was made: real, and now measured.

**Non-goal, stated in every artifact:** memories G1 wrote before this
migration, through the old `ingest_events` path, are unchanged and remain
outside what this mechanism can delete.

## G5: what was built, and why it can't be "done" yet

Started 2026-08-13. Firestore (Native mode, `us-central1`) backs the
derivation graph (`custody/firestore_store.py`). Cloud Scheduler job
`custody-g5-auditor` (daily, `0 6 * * *` UTC, `POST /auditor`) is `ENABLED`.

**Confirmed 2026-08-14, natural first scheduled fire happened.** The job's
one manual "run now" trigger from the prior session succeeded — logged at
`2026-08-13T12:00:44Z`, HTTP 200, `insertId 6a7db1ed00084c8dae8758ee`. Its
natural first scheduled fire, `2026-08-14T06:00:02Z` UTC, has now also
happened: `gcloud scheduler jobs describe custody-g5-auditor` reports
`lastAttemptTime: 2026-08-14T06:00:03.016110Z` and `scheduleTime` has
already advanced to tomorrow (`2026-08-15T06:00:02Z`) — the authoritative,
Scheduler-reported confirmation, independent of log interpretation. The
matching Cloud Logging entry (`insertId 6a7eaee5000d85ead04c20df`, HTTP
200, revision `custody-control-plane-00004-ttb`) confirms the same instant
from the Cloud Run side.

**Correction to a prior instruction in this file:** the earlier version of
this section said to look for a log entry "without the
`custody-cold-start-check` label," reasoning that label marked only the
manual trigger. Checked live and found wrong: `gcloud run services
describe custody-control-plane` shows `custody-cold-start-check=1` is a
static label on the Cloud Run **service and revision themselves** (set
during an earlier session's redeploy), not a per-request marker — it
appears on every request log line, scheduled or manual, and cannot
distinguish them. Use timestamp and `gcloud scheduler jobs describe`'s own
`lastAttemptTime`/`scheduleTime` instead, as above; do not filter Cloud
Logging queries by this label.

Deliberately not built yet: revoking the seed record (must happen near
filming, not now) and `scripts/scheduler_gates.py` (a judge for a
multi-day span, before enough days have elapsed, would have nothing real to
check). Neither is fixable by code today; both need calendar time.

## Evidence and claim discipline

- Admin Activity authenticates policy transitions but omits historical CEL
  condition text; scope and post-expiry 403 controls are the falsifiable
  evidence for S1's semantics, not the log text itself.
- O1's independently-verified claim is a Cloud Logging entry, not Cloud
  Trace storage. Say so exactly; do not round up to "verified in Cloud Trace."
- R2's independently-verified claim is two Cloud Logging denial entries plus
  two Cloud Run revision descriptions, not a claim about IAP or the Gateway.
- D2's independently-verified claim covers only records written through the
  new `write_record` path. As of the 2026-08-14 G1 migration, G1's live
  Runner is one of those writers too — do not imply memories G1 wrote
  *before* that migration became retroactively deletable; they did not.
- Cloud Run and the control plane are public because they are synthetic proof
  services. Do not generalize that posture to production customer data.
- All synthetic IDs and `example.invalid` addresses are controls. Do not use
  external targets or real customer data.
- Keep TOOL call roots structural. Never let a model label provenance, trust,
  revision admission, or policy outcomes.

## Next capability

With R2, D2, the G1 migration, the Provenance Auditor, the Custody
Reviewer, the N=5 fleet, F1 (the live cross-department derivation chain),
and G5's clock all landed, all three fleet-review findings plus the
GUI-vs-live proof gap are closed, and G5's natural first scheduled fire is
confirmed (above). Remaining scoped work, in the order the top of this file
names:

1. **Done, 2026-08-14: GUI redeployed to Vercel with F1's data**, via the
   `vercel` CLI (see the redeploy write-up above — prefer this method over
   `deploy_to_vercel` for these two files going forward). Verified live,
   both pages, no console errors, `ssoProtection` confirmed disabled so the
   site stays public.
2. **Done, 2026-08-14: Best Multimodal UX award pass (section 4)** —
   Reviewer narration (real Cloud Text-to-Speech, GUI widget, redeployed).
3. **Done, 2026-08-14: fleet scale-up (section 3)** — N=5 → N=25,
   live-proven, gates and GUI updated, redeployed.
4. `scripts/scheduler_gates.py`, once there is a real multi-day span to
   judge — not yet, would have nothing to check.
5. Revoke the G5 seed record near filming, via the existing `/revoke`
   endpoint, once enough real elapsed time has passed.
6. Regenerate `proof-out/g1.json` before filming — G1 evidence expires
   after 24 hours, same discipline as every other live gate here.
7. `proof-out/live-review.json`, `proof-out/live-fleet.json`, and
   `proof-out/live-chain.json` also expire after 24 hours, same
   discipline — regenerate with `make live-review`, `make live-fleet`, and
   `make live-chain` before filming.
8. `proof-out/live-narration.json` and `proof-out/live-narration.mp3`
   also expire after 24 hours (evidence freshness), same discipline —
   regenerate with `make live-narration` before filming.
