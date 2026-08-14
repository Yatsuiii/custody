# Submission handoff, 2026-08-14

This file is for a **fresh session finishing the submission**. It assumes no
prior context.

- Judging the project instead? `JUDGE_HANDOFF.md`.
- Want the build history? `HANDOFF.md` and `.claude/SESSION_CONTRACT.md`.
- Want the R1 digest story? `R1_HANDOFF.md`, now closed.

It exists because a read-only judging pass found eight defects. Seven are
now closed. What follows is what is left, in cost order, with the state of
the world as of this writing so you can trust the starting point.

---

## Where things actually stand

Verified by running the commands, not by reading prose:

| | |
| --- | --- |
| `make check` | ruff clean, **345 tests, 0 skipped**, ~0.15s, no network |
| `make gates` | G1-G4 **PASS**, G5 **BLOCKED** at 2 of 4 groups |
| `make registry-gates` | 9/9 |
| `make revision-binding-gates` | 16/16 |
| Cloud Run control plane | live, `GET /health` -> `200 {"status":"ok"}` |
| Vercel pages | live, render clean, **2 lines behind the local build** (see item 3) |
| `proof-out/` | R1 and R2 recaptured 2026-08-14 ~16:30Z; S1, M1, O1, D1/D2 are **older than 24h** |

Closed since the judging pass: the R1 digest break (the substantive one),
the README's stale headline transcript, both stale test counts, F1's wrong
gate count, the Firestore-planned diagram contradiction, G5's hardcoded
telemetry group, and the README understating R1/R2 after the
runtime-binding and durable-ledger work landed.

---

## 1. The demo video — highest cost, entirely unverified

`Demo & Production Readiness` is 30% of the score and the rubric names
**video clarity first**. Nothing in this repo evidences that a video exists.
`.claude/SESSION_CONTRACT.md:23` lists "one four-minute video" as a
deliverable and `HANDOFF.md:35,224` treats video time as a future
constraint, which reads like it was still prospective.

**If it is already shot and on Devpost, this item is done — check before
building anything.** If not, it outranks every other item in this file
combined, because the other 70% is already strong and unwatchable work
scores nothing.

A four-minute cut that matches what the repo can actually prove:

1. **The problem, 30s.** `make demo`. Week one a page carries an
   instruction, week three it leaves the building. The two-column output
   is the whole pitch and it is already legible on a terminal.
2. **The mechanism, 45s.** The Dependency Cartography page. Click
   **Revoke exact descendants**. The lineage flips to REVOKED, the evidence
   ledger fills in, 32 removed and 575 preserved. This is the most
   screen-ready thing in the project — use it, do not narrate the README.
3. **That it is real, 90s.** The Architecture & Evidence page, scrolling
   the live proof rows. Land on R1 (a same-schema image swap blocked before
   dispatch), F1 (a real cross-department `derived_from` chain against live
   Memory Bank), and Fleet N=25. Each row shows its own captured data.
4. **The fleet claim, 45s.** One revocation, 2 departments pulled, 23
   untouched, verified by 25 independent Memory Bank rereads.
5. **Honesty, 30s.** Say out loud that G5 is BLOCKED and why. Judges
   reward a project that names its own gap far more than one that hides it,
   and this project's entire posture is built on that.

Do not add UI for the video. The scale-up decision earlier in this project
was explicitly "a reported number, not a UI feature competing for video
time" (`HANDOFF.md:35-37`). That still holds.

## 2. Refresh the live evidence on judging day

**This is the item most likely to silently cost points**, because it looks
fine until someone opens the page.

Every `proof-out/live-*.json` expires after 24 hours by this project's own
freshness gates. Right now S1, M1, O1 and D1/D2 are already past it. The
`make gates` G5 line currently reports `security/governance` and `telemetry`
as not demonstrable **purely because their artifacts aged out**, not because
anything is broken. A judge reading that line will not know the difference.

Within 24 hours of judging, run:

```bash
export CLOUDSDK_CONFIG="$PWD/.gcloud"
export CUSTODY_PROJECT=project-988bc9fe-092c-4b32-90c
export CUSTODY_AGENT_ENGINE_ID=6936011268348182528

make live-g1 && make live-gateway && make live-model-armor \
  && make live-observability && make live-memory-deletion \
  && make live-auditor && make live-review && make live-narration \
  && make live-fleet && make live-chain

make gates          # expect G5 at 4 of 4 groups, still BLOCKED on elapsed time
make gui            # then redeploy, item 3
```

Credential caveat, and it has bitten before: the environment's default
`gcloud` config is authenticated as a **different account against an
unrelated project**. The project's resources live under
`project-988bc9fe-092c-4b32-90c`, owned by `yoursturuly@gmail.com`. Pass
`CLOUDSDK_CONFIG="$PWD/.gcloud"` explicitly, or `--account`/`--project` on
raw `gcloud` calls. The offline gates need neither.

Budget real time for this. Ten live proofs, several of which deploy Cloud
Run revisions. Do not start it an hour before the deadline.

## 3. Redeploy the page (needs the user's go-ahead)

`web/architecture.html` is currently **2 lines ahead** of what is deployed
— the embedded `gate-data` JSON, from G5's telemetry group now being judged
rather than hardcoded. Everything else matches.

This is a public production deploy, so **ask before running it**. Two
things learned the hard way (`HANDOFF.md:48-70`):

```bash
vercel link --project custody-incident   # once
vercel deploy --prod                     # deploys web/ from disk
```

- Deploy **from disk with the `vercel` CLI**. Do not use the
  `deploy_to_vercel` MCP tool: passing these files' contents as a JSON tool
  parameter silently corrupted `architecture.html`'s inline `<script>` once,
  blanking every widget on the live page. It was not visible in a
  screenshot.
- Afterwards check the browser **console**, not just that the deploy call
  returned success.

## 4. Stale evidence still renders as fresh evidence

The one judging-pass finding deliberately left open, because it is real work
rather than a text fix.

`scripts/render_architecture.py:109-120` computes an age string but there is
no staleness threshold anywhere in the renderer. So an artifact 28 hours old
carries the same green `EVIDENCE` chip as one 14 minutes old, while the page
asserts, at `render_architecture.py:444`, that "a missing or stale file is
labeled as such, not hidden". Missing is handled. Stale is not.

**Fix.** The proof rows already know how to judge themselves — the mapping
from artifact to judge is in `tests/test_stored_artifacts.py`, verified and
working. Reuse it: compute each row's chip by calling its offline judge and
render `PASS` / `STALE` / `FAILING` instead of a fixed `EVIDENCE`. The CSS
already has a `BLOCKED` warning style to borrow.

Roughly 30 minutes, plus a redeploy. Worth doing **only after item 2**, when
everything is fresh and the honest answer is mostly `PASS`.

## 5. Two open decisions, not tasks

Neither should be settled silently. Both are judgment calls.

**Should `proof-out/` be committed?** Today it is gitignored, so a fresh
clone has no live evidence and every live gate reports BLOCKED. That is now
stated plainly in `README.md`'s "Status, honestly" and in
`JUDGE_HANDOFF.md`, so nobody is misled — but a judge who clones instead of
opening the deployed page still cannot verify a single live claim. Against
committing: every artifact expires in 24 hours, so the repo would carry
permanently-stale evidence, which is the exact drift this project exists to
prevent. A middle option nobody has costed yet: commit one dated,
clearly-labelled snapshot directory, separate from the live `proof-out/`.

**Should the README's headline transcript be generated?** The `make incident`
block at `README.md:9-48` is currently correct, but it is still a
hand-paste, and it was wrong for a day because someone changed
`VOUCHED_AT` (`scripts/incident.py:40`) without repasting. Directly below it
the README claims "the story and the numbers cannot drift apart", which is
true of the GUI (it embeds generated JSON) and not yet true of the README.
Generating that block at `make gui` time would make the sentence true.

## 6. G5's elapsed-time close, when the days are there

Unchanged and still genuinely open. G5 needs one custody record whose
timestamps span from first deploy to filming, not fast-forwarded. The daily
Cloud Scheduler heartbeat has been seeding since 2026-08-13.
`scripts/scheduler_gates.py` is still deliberately unwritten — building a
judge before there is a multi-day span to judge would have nothing real to
check.

When the span is long enough: revoke the seed record near filming, write
that gate script, and prove the whole span independently. Until then G5
reporting BLOCKED is the correct output, and item 2 is what gets it to
"4 of 4 groups, blocked only on elapsed time" — which is a much better line
for a judge to read than the current one.

---

## What was not verified while writing this

- **No live proof was re-run in this session.** Every live number quoted
  above comes from artifacts captured earlier the same day by the R1
  sub-build, plus the offline judges re-run over them.
- **The Devpost submission itself was never seen** — not the page, not the
  video, not the category selection. Item 1 could already be done.
- **Whether the ten `make live-*` commands in item 2 still pass** is
  unknown for the eight that were not re-run today. R1 and R2 did pass.
- The Cloud Run health check and both Vercel page loads were verified
  directly. Those are the only live facts here.
