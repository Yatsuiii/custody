# Custody — judge handoff, 2026-08-14

This file is for a **fresh session judging this submission**, not for a
session continuing the build. If you are picking up build work instead,
read `HANDOFF.md`, not this file.

## What you're judging

**Custody**: a revision-aware provenance layer over agent long-term memory
across a fleet of departmental agents, built for the Google All Things
Agentic Hackathon, **Fortified Enterprise Fleet** track. One sentence, and
it is meant to stay one sentence:

> Custody blocks an observed unapproved tool revision before dispatch, and
> if an approved revision is later compromised, identifies every memory
> descended from it for selective revocation.

Also a candidate for the separate **Best Multimodal UX** award ($5,000, 2
winners) — no published rubric exists for that award beyond its name and
prize amount (checked live against the hackathon's main page and rules
page, not assumed).

## The real judging criteria, quoted from source, not assumed

Confirmed live against `https://allthingsagentichackathon.devpost.com/`
and its `/rules` page this session (2026-08-14) — do not substitute
generic hackathon-judging assumptions for these:

- **Innovation & Operational Utility — 40%**: how much real-world friction
  the agent removes autonomously.
- **Architectural Discipline & Tech Stack — 30%**: decoupling, state
  management, security, failure handling.
- **Demo & Production Readiness — 30%**: video clarity, repo quality,
  architecture docs, proof of GCP deployment.
- **Best Multimodal UX** (separate specialty award): no published rubric
  beyond "$5,000, 2 winners, top scoring projects in that judging
  criteria."

## Where the evidence actually is

Do not take any claim below at face value — every one of these has a
command or artifact behind it, per this project's own rule ("no row moves
to BUILT without one"). Verify, don't just read.

1. **`README.md`** — the authoritative, judge-facing account of what's
   built, what's live, and what each proof does and does not show. Start
   here.
2. **`.claude/SESSION_CONTRACT.md`** — the full build history, one scoped
   sub-build section per capability, each with acceptance gates stated
   *before* the work and a closing write-up stated *after*. This is where
   to check whether a claim was actually gated or just asserted.
3. **`HANDOFF.md`** — session-by-session build log for whoever continues
   the work. Useful for provenance/timeline, not the primary judging
   source.
4. **Live GUI, already deployed**:
   - https://custody-incident-cave2.vercel.app/ — "Dependency
     Cartography": the G3 blast-radius/revocation story as an interactive
     node graph.
   - https://custody-incident-cave2.vercel.app/architecture.html —
     "Architecture & Evidence": every other live-proven capability (R1,
     R2, S1, G1/G2/G4/G5, M1, O1, D1/D2, the Provenance Auditor, the
     Custody Reviewer, Reviewer Narration, the N=25 fleet, F1), each
     widget showing that proof's own real captured data, not prose
     describing it.
5. **`proof-out/*.json`** — every live proof's raw evidence artifact, one
   per capability (e.g. `live-fleet.json`, `live-narration.json`,
   `live-chain.json`, `g1.json`). These are what the GUI widgets and
   `README.md`'s claims are actually built from.

## How to independently verify, not just read

```sh
make check          # 319/319 offline tests + lint, no cloud needed
make gates           # G1-G4 PASS, G5 correctly BLOCKED (real elapsed time
                      # hasn't finished accumulating — this is a true
                      # gap, not a bug; see HANDOFF.md's G5 section)
make fleet-gates      # independently rereads live Memory Bank for the
                      # N=25 fleet claim (needs GCP credentials, see below)
make narration-gates  # independently re-calls Cloud Text-to-Speech
make review-gates     # independently re-calls Gemini
make chain-gates      # independently rereads live Memory Bank for F1
```

**Credential caveat, found live this session, worth knowing before you
try any `make live-*` or `make *-gates` target yourself**: the project's
Google Cloud resources live under `project-988bc9fe-092c-4b32-90c`, owned
by account `yoursturuly@gmail.com`. The environment's *default* `gcloud`
CLI config was authenticated as a different account against a different,
unrelated project. If you need to run a live command yourself, pass
`--account=yoursturuly@gmail.com --project=project-988bc9fe-092c-4b32-90c`
explicitly, or use the repo's own `.gcloud/application_default_credentials.json`
via `GOOGLE_APPLICATION_CREDENTIALS` for the Python client calls (`make
live-*`/`make *-gates` read `CUSTODY_PROJECT` and
`GOOGLE_APPLICATION_CREDENTIALS` from the environment, not from `gcloud
config`). The offline gates (`make check`, `make gates`) need neither.

All `proof-out/live-*.json` evidence expires after 24 hours by this
project's own stated discipline (freshness is one of the offline gate
checks) — if you find a gate reporting stale evidence, that is expected
between sessions, not a defect; note it rather than penalizing the
architecture for it.

## What to actually produce

A judge's assessment, not more build work. Do not edit code, do not
commit, do not push, do not redeploy — this is a read-only review. Report:

1. A score or strong/weak call against each of the three real criteria
   above (40/30/30), with specific evidence citations (file:line, proof
   id, or a claim you personally verified vs. one you're taking on
   trust).
2. Whether this reads as a credible Best Multimodal UX candidate, given
   no published rubric exists — your own honest read of whether the
   Reviewer Narration capability (`README.md`'s "Reviewer narration"
   section, live proof in `proof-out/live-narration.json`) is a genuine
   second modality or a stretch.
3. The single most damaging gap you can find, if any — the thing a real
   judge would flag first. This project's own `HANDOFF.md` and
   `SESSION_CONTRACT.md` already document several known limitations
   honestly (see `README.md`'s "Status, honestly" section) — check
   whether they're accurately stated or whether something is quietly
   overclaimed.
4. Anything you could not verify and had to take on the project's own
   word, named explicitly as such.
