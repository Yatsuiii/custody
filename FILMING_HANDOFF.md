# Filming handoff: Custody demo video

Written 2026-08-31, ~17 hours before the Devpost deadline. Read this whole
file before touching anything — it exists so a fresh session (or you,
recording directly) doesn't have to re-derive what's already verified.

**Your only job in this session: record a 4-5 minute demo video and get it
uploaded to Devpost's "Video demo link" field.** Nothing else on the
submission is blocking. Do not refactor, redeploy, or "improve" anything
not listed under "Known gaps" below — that is scope creep on filming day.

## What's already true, verified minutes ago

- `custody-control-plane` is live and current: revision
  `custody-control-plane-00006-z7s`, redeployed from clean source this
  session, zero code drift.
- G5's elapsed-time claim is real: `elapsed_days_since_seed: 17`,
  independently judged, `make scheduler-gates` 7/7 PASS.
- `make check`: 400/400 tests, 1 expected skip.
- Every 24-hour-expiring live proof was regenerated in the last hour:
  `review-gates` 9/9, `fleet-gates` 35/35, `chain-gates` 15/15,
  `narration-gates` 14/14. **These expire again ~24h from
  2026-08-31T06:41 UTC** — if you are not filming within that window,
  rerun the `make live-*` / `make *-gates` pairs listed below before you
  start, in the same worktree (`custody-codex-check`, branch
  `hackathon/g5-scheduler-gate`).
- All four live judge-facing GUI pages return 200 and are current:
  - `https://custody-incident-cave2.vercel.app/` (landing)
  - `https://custody-incident-cave2.vercel.app/incident.html` — "Custody —
    dependency cartography" (the blast-radius/trust-graph view)
  - `https://custody-incident-cave2.vercel.app/timeline.html` — "Custody —
    trust lifecycle" (vouched → compromised → revoked timeline + the
    purge-vs-Custody cost comparison table)
  - `https://custody-incident-cave2.vercel.app/fleet.html` — "Custody —
    fleet at N=25" (the 25-department scale test — remember this ran
    **sequentially**, not concurrently; don't say "mirrors production
    concurrency" on camera, say "sequential trust re-examination across 25
    departments")

## Known gaps — route around these, don't try to fix them today

1. **`web/architecture.html` (the live `/architecture.html` page) is
   stale** — it predates the Onboarding/Escalation agents, confirmed via
   `curl .../architecture.html | grep -ic "onboarding\|escalation"` → 0.
   **Do not film this page as "the current architecture."** Instead, show
   the six-agent Mermaid diagram already rendered this week
   (`/tmp/custody_arch.png`, also uploaded to the Devpost image gallery)
   as a static image, or screen-record `docs/architecture.md` rendered on
   GitHub, which is current.
2. **This session's two commits are on an unpushed local branch**
   (`hackathon/g5-scheduler-gate`, commits `37bc1ba` and `5441904`), not
   on GitHub `main`. If you want the public repo to match what the video
   claims about G5 (the scheduler gate script, the live_fleet.py fix),
   merge and push before or right after filming. Not required for the
   recording itself — everything you'll show runs live against Cloud Run,
   not against GitHub.
3. **The G5 seed record has not been revoked yet.** This is intentional —
   do it live, on camera, as part of the recording (Beat 4 below), not
   before.

## Environment you'll need

```
export CLOUDSDK_CONFIG="/run/media/Yatsuiii/Windows-SSD/custody/.gcloud"
export CUSTODY_PROJECT=project-988bc9fe-092c-4b32-90c
export CUSTODY_AGENT_ENGINE_ID=6936011268348182528
export CUSTODY_REGION=us-central1
CONTROL_PLANE=https://custody-control-plane-742122658452.us-central1.run.app
cd /run/media/Yatsuiii/Windows-SSD/custody-codex-check
```

Python: use `/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python`
(pass as `PYTHON=...` to every `make` target below, or `source` its
`activate` script first).

## Shot list (target 4:30, budget below sums to ~4:50 with breathing room — cut the weakest beat first if you're over)

### Beat 0 — cold open (0:00–0:20)

No terminal yet. State the problem in one breath: agent memory (ADK /
Vertex AI Memory Bank) tracks *who* wrote something, never *where it came
from* or whether it's still trustworthy. OWASP ASI06 is the named threat
class. One sentence, then cut to the architecture.

### Beat 1 — architecture, 15 seconds (0:20–0:35)

Show the six-agent Mermaid render (`/tmp/custody_arch.png`, or
`docs/architecture.md` on GitHub — NOT `/architecture.html`, see Known
Gap 1). Say the shape once: 3 governed department agents, Onboarding and
Escalation (Gemini drafts, never decides), Provenance Auditor (fully
deterministic), Reviewer (Gemini explains a quarantine, never labels it).
Don't linger — this is context, not the proof.

### Beat 2 — the live incident, on the real GUI (0:35–1:45)

Browser, `https://custody-incident-cave2.vercel.app/incident.html`.
Walk the dependency cartography: `vendor_portal` compromised, blast radius
32 affected descendants, 3/5 departments touched, 575 unrelated records
preserved untouched. This is the differentiator — say it plainly: revoke
by exact descendant, not by department purge.

Then `timeline.html`: the vouched→compromised→revoked timeline (15 days
of accumulated exposure before detection, matching G5's real elapsed-day
mechanism you'll prove live in Beat 4), and the cost table — purge the
whole app / purge every department that used the tool / Custody revokes
exact descendants, with the 1%–93% savings-by-reach numbers.

### Beat 3 — real Gemini, structurally barred from deciding (1:45–2:35)

Terminal. Run the Reviewer live, on camera, not a replay:

```
make PYTHON=/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python live-review
make PYTHON=/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python review-gates
```

Narrate while it runs: real Vertex AI call, a per-run random marker
embedded in quarantined content, the marker has to survive into the
drafted verdict — proves the call actually read this content, not a fixed
echo. Point at the verdict JSON: no `trust`/`origin`/`label` field exists
on the schema at all, not filtered out — structurally cannot decide.
`review-gates` 9/9 PASS on screen is the payoff shot.

### Beat 4 — G5: real elapsed time, then revoke live (2:35–3:40)

This is the newest, least-seen proof — give it real time. Terminal:

```
curl -s -X POST $CONTROL_PLANE/auditor -H "Content-Type: application/json" -d '{}'
```

Point at `"elapsed_days_since_seed": 17` in the response. Say what it
means in one sentence: a synthetic record was seeded on 2026-08-14 through
a real, still-running daily Cloud Scheduler job; this number could not be
faked or fast-forwarded, it only exists because 17 real days actually
passed.

```
make PYTHON=/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python scheduler-gates
```

7/7 PASS on screen — say that this script re-derives both claims itself
(`gcloud scheduler jobs describe` for the job's own fire history, a fresh
`/auditor` call for the elapsed count), it doesn't trust a saved file.

Then revoke the seed record live, on camera, right now:

```
curl -s -X POST $CONTROL_PLANE/revoke -H "Content-Type: application/json" -d '{"tool": "custody_g5_seed"}'
```

Show the response: `"removed": ["g5-elapsed-time-seed"]`. This is the
mechanism from Beat 2's incident page, happening for real, not staged.

### Beat 5 — scale, honestly stated (3:40–4:10)

`fleet.html` (already open from Beat 2, or re-open). One sentence: the
same revoke mechanism tested across 25 departments, one shared tool,
revoked once, pulled from every department that had it, everything else
untouched. Say "sequential" if asked or if you show the runtime — do not
imply concurrency you didn't test.

Optional if time allows: `make PYTHON=... fleet-gates` — 35/35 PASS,
already fresh from this session, no need to rerun live on camera unless
you want the terminal beat.

### Beat 6 — close (4:10–4:30)

One sentence on what's real vs. what's ahead (Onboarding/Escalation are
draft-only by design, not a gap), then GitHub + Devpost links on screen.
Do not end on a feature list — end on the one differentiated claim: exact
descendant revocation with a provenance graph, not tool-level or
department-level purge.

## After recording

1. Upload to YouTube (unlisted is fine, Devpost just needs a working URL)
   or wherever you're hosting it.
2. Paste the URL into Devpost → Project details → "Video demo link".
3. Save & continue through to Submit. This is the last blocking step —
   once the video URL is in, the submission goes from 3/5 to 5/5 steps
   done.
4. If you want the public GitHub repo to match what the video claims
   about G5, merge `hackathon/g5-scheduler-gate` into `main` and push
   (Known Gap 2) — not required for Devpost's own checks, just for
   consistency if a judge reads the source.
