# Filming handoff: Custody demo video

Updated 2026-08-31 after the organizer's ten-hour warning. Read this whole
file before touching anything — it exists so a fresh session (or you,
recording directly) doesn't have to re-derive what's already verified.

**Your only job in this session: record a 3:50 demo video and get it
uploaded to Devpost's "Video demo link" field.** Nothing else on the
submission is blocking. The organizer explicitly said judges may watch only
the first four minutes, so the Cloud proof is inside the first minute and
every spoken beat ends by 3:50.

## What's already true, verified minutes ago

- `custody-control-plane` is live and current: revision
  `custody-control-plane-00006-z7s`, redeployed from clean source this
  session, zero code drift.
- G5 is no longer an aggregate blocker: `make scheduler-gates` is 10/10
  PASS, `elapsed_days_since_seed: 18`, and `make gates` is 5/5 PASS with
  0 blocked. The Scheduler command writes bounded evidence that the offline
  aggregate independently re-judges.
- `make check`: 409/409 tests.
- The proof rows used in the filmed slice are current: R1, S1, O1,
  Onboarding, Auditor, Escalation, Reviewer, Fleet N=25, and F1. The R2 and
  D1/D2 snapshots are honestly labeled stale on the architecture evidence
  page; neither is claimed as freshly re-run in this video.
- The architecture renderer now includes Onboarding and Escalation and
  keeps their draft-only/no-trust boundary visible. Both production aliases
  passed byte-for-byte `make verify-deploy` checks after the final deploy.
- The public source must be on GitHub `main` before recording; verify with
  `git ls-remote origin refs/heads/main` after the release push.
- The judge-facing pages are:
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

## Filming condition — do not "fix" this beforehand

The G5 seed record is still live and unrevoked. `scheduler-gates` directly
confirmed that state. Revoke it once, on camera, in Beat 5. This is the
demo's one-time state transition, not a project blocker.

The hosted architecture evidence page is current, but it is too dense for
the organizer's "one glance" architecture requirement. Use the six-agent
diagram already in the Devpost gallery for the ten-second architecture beat.
Use `/architecture.html` only as repository evidence, not as the diagram.

## Organizer submission checklist

- hosted project URL
- text description covering features, Google Cloud tech, and learning
- public repository link and setup README
- simple architecture diagram
- approximately four-minute demo showing the backend actually running on
  Google Cloud

The video URL is the remaining user-owned artifact. Start or save the Devpost
draft before recording; the deadline is hard.

## Environment you'll need

```
export CLOUDSDK_CONFIG="/run/media/Yatsuiii/Windows-SSD/custody/.gcloud"; export CUSTODY_PROJECT="project-988bc9fe-092c-4b32-90c"; export CUSTODY_AGENT_ENGINE_ID="6936011268348182528"; export CUSTODY_REGION="us-central1"; export PYTHON="/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python"; CONTROL_PLANE="https://custody-control-plane-742122658452.us-central1.run.app"; cd "/run/media/Yatsuiii/Windows-SSD/custody-codex-check"
```

Python: use `/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python`
(pass as `PYTHON=...` to every `make` target below, or `source` its
`activate` script first).

## Ten-minute preflight — do not consume G5 here

1. Set the environment above in one terminal, enlarge the terminal font,
   and run `clear`. Check that `echo "$CUSTODY_PROJECT"` and
   `test -x /run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python` look
   right. These checks make no live call.
2. Open these tabs in order: `incident.html`, the Devpost gallery's
   six-agent diagram, `timeline.html`, `fleet.html`, the public GitHub repo,
   the Devpost draft, the [Cloud Scheduler jobs page](https://console.cloud.google.com/cloudscheduler?project=project-988bc9fe-092c-4b32-90c),
   and the [Cloud Run service dashboard](https://console.cloud.google.com/run/detail/us-central1/custody-control-plane/metrics?project=project-988bc9fe-092c-4b32-90c).
   Put `incident.html` on screen before recording.
3. Put `make scheduler-gates` and the one-time revoke command in the first
   terminal's history. Put the Reviewer command in a second terminal tab.
4. Start a disposable ten-second screen-and-microphone recording. Say one
   sentence, switch browser tabs, stop, and play it back. Verify readable
   text and audible speech. This is the only dry run needed.
5. **Do not preflight `POST /revoke`.** It is the one-time payoff. Also do
   not click the hosted incident page's button as if it were the G5 action;
   that button animates the embedded incident fixture, not the seed record.

Use `curl -fsS ... | jq` below so HTTP failures stay visible and the JSON is
legible. If `jq` is unavailable, remove only the final `| jq`.

## Read-aloud shot list (target 3:50)

The quoted paragraphs are narration. Bracketed lines are operator cues, not
spoken words. Do not add an intro card: the organizer said judges may watch
only four minutes, so the live Google Cloud proof starts at 0:18.

### Beat 0 — problem and payoff (0:00–0:18)

`[Start on incident.html, with the 32 affected / 575 preserved counters visible.]`

> Agent memory records who wrote an event, but not which external source its
> content came from or whether that source is still trustworthy. Custody adds
> deterministic provenance, then revokes only the memories descended from a
> compromised source.

### Beat 1 — prove Google Cloud immediately (0:18–0:55)

`[Switch to the G5 terminal and run this one command.]`

```
make PYTHON=/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python scheduler-gates
```

> This is the real backend, not the fixture. The gate asks Cloud Scheduler for
> the enabled daily job and its latest natural fire, calls the deployed Cloud
> Run Auditor, and directly reads the still-unrevoked seed. Ten of ten pass.
> The durable admission timestamp now spans 18 real days—no test clock and no
> fast-forward.

`[Hold on the 10/10 PASS output for two seconds.]`

`[Switch to the Cloud Scheduler jobs page or Cloud Run service dashboard for five
seconds so the Google Cloud resource is visible, then return to the script.]`

### Beat 2 — architecture in one glance (0:55–1:05)

`[Show only the six-agent diagram from the Devpost gallery.]`

> Department agents write through Custody. Gemini drafts review, onboarding,
> and escalation language; deterministic code alone assigns trust and revokes.

### Beat 3 — exact blast radius, not a purge (1:05–1:55)

`[Return to incident.html. Point to vendor_portal, lineage, 32 affected, and
575 preserved. At about 1:35 switch to timeline.html and hold the vouched →
compromised → revoked strip plus the purge comparison table for ten seconds.]`

> Here, `vendor_portal` propagated from sales to support to finance. The lifecycle
> is explicit: vouched on day one, compromised on day sixteen, then revoked.
> The graph finds 32 descendants across three departments and preserves 575
> unrelated records. The unit of revocation is one descendant, not an app or
> department. Against the strongest practical baseline—a coarse purge—the
> fixture preserves between 19 and 93 additional percentage points of memory,
> depending on tool reach.

### Beat 4 — real Gemini, structurally unable to decide (1:55–2:35)

`[Switch to the Reviewer terminal and run both targets together.]`

```
make PYTHON=/run/media/Yatsuiii/Windows-SSD/custody/.venv/bin/python live-review review-gates
```

> This is Gemini 3.5 Flash through Vertex AI reading a fresh quarantined item.
> A random marker must survive into the draft, proving it read this run rather
> than returning a canned echo. The verdict schema has no trust, origin,
> label, or decision field, so those facts are structurally outside the
> model's authority. The independent judge finishes nine of nine passing.

### Beat 5 — execute the one-time live revocation (2:35–3:10)

`[Run this once. Preserve the footage if the removed list contains the seed.]`

```
curl -fsS -X POST "$CONTROL_PLANE/revoke" -H "Content-Type: application/json" -d '{"tool": "custody_g5_seed"}' | jq
```

> The response removes `g5-elapsed-time-seed`. That is the same descendant
> revocation mechanism from the incident view, now executed against the
> deployed Firestore-backed control plane. The end state is explicit: the
> seed is revoked while unrelated memory remains outside its lineage.

`[Hold on the removed record for three seconds.]`

### Beat 6 — scale and close (3:10–3:50)

`[Show fleet.html, then end on the public GitHub repo and Devpost project.]`

> The same mechanism was tested sequentially across 25 departments. One
> shared-tool revocation removed sales and finance memories while 23 other
> departments stayed untouched—35 gates, including 25 independent Memory
> Bank rereads. This is sequential scale, not a concurrency claim. Building
> Custody also exposed an upstream ADK bug where search dropped custom
> metadata; issue 6946 and PR 6947 are open and tested against ADK's own
> 13,000-plus test suite.

## Failure routes during the take

- If `live-review` or `review-gates` fails, stop before Beat 5. Those calls
  are repeatable; diagnose them off-camera, then start a new take.
- If `scheduler-gates` is not 10/10, stop before continuing. Re-check the environment;
  do not spend the one-time action on a take that already failed.
- If the revoke response includes `g5-elapsed-time-seed`, preserve that take
  even if a later beat is imperfect. The action is idempotent and a second
  take will show an empty `removed` list. Trim or splice only after retaining
  the first successful revoke footage.
- If the first revoke returns an empty list, do not claim it happened in that
  take. Search existing recording/terminal history for the successful first
  response; otherwise state honestly that the seed had already been revoked.
- If the complete cut exceeds four minutes, shorten the incident narration
  and fleet close. Never cut Scheduler 10/10, Reviewer 9/9, or the one-time
  revoke response.

## After recording

1. Upload to YouTube (unlisted is fine, Devpost just needs a working URL)
   or wherever you're hosting it.
2. Paste the URL into Devpost → Project details → "Video demo link".
3. Save & continue through to Submit. This is the last blocking step —
   once the video URL is in, the submission goes from 3/5 to 5/5 steps
   done.
4. Open the submitted hosted URL and repository link in a private window;
   confirm neither requires authentication.
