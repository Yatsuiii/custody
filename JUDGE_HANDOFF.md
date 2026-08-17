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

Not entered as a **Best Multimodal UX** candidate — a Reviewer-narration
audio widget was built and briefly deployed for that award, then removed
on 2026-08-17 (see `README.md`'s "Reviewer narration" section): its
playback couldn't be verified reliable in every browser, and the verdict
text it narrated already conveyed everything the audio did. The
underlying live Text-to-Speech capability is still real and gated
(`make live-narration` / `make narration-gates`), just not surfaced or
claimed for this award.

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
     Custody Reviewer, the N=25 fleet, F1), each
     widget showing that proof's own real captured data, not prose
     describing it.
5. **`proof-out/*.json`** — every live proof's raw evidence artifact, one
   per capability (e.g. `live-fleet.json`, `live-narration.json`,
   `live-chain.json`, `g1.json`). These are what the GUI widgets and
   `README.md`'s claims are actually built from.
   **`proof-out/` is generated and deliberately not committed**, because
   each artifact expires after 24 hours by this project's own freshness
   gates and a committed copy would be stale on arrival. So if you cloned
   this repo, you have none of them: the offline gates still run, the live
   rows report BLOCKED until you run their `make live-*` command yourself,
   and the deployed Architecture & Evidence page (item 4 above) is where
   the captured evidence can be read without credentials. The reasoning is
   restated in `README.md`'s "Status, honestly" section.

## How to independently verify, not just read

```sh
make check          # 376/376 offline tests + lint, no cloud needed
make gates           # G1-G4 PASS, G5 correctly BLOCKED. Read its detail
                      # line: it names which of the four capability groups
                      # are demonstrable right now and which are not, and
                      # every group is judged from that group's own
                      # artifact. G5 also requires real elapsed time, which
                      # is a true gap and cannot be produced in one
                      # sitting; see HANDOFF.md's G5 section.
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
`make live-revision-binding` additionally needs `CUSTODY_FIRESTORE_PROJECT`
set to the same project id — without it, R2's fresh-process nonce-replay
control falls back to an in-process ledger that cannot detect a replay
across the redeploy the proof itself performs, and the command hangs
waiting for a denial log that will never be written rather than failing
fast.

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
2. The single most damaging gap you can find, if any — the thing a real
   judge would flag first. This project's own `HANDOFF.md` and
   `SESSION_CONTRACT.md` already document several known limitations
   honestly (see `README.md`'s "Status, honestly" section) — check
   whether they're accurately stated or whether something is quietly
   overclaimed.
3. Anything you could not verify and had to take on the project's own
   word, named explicitly as such.
