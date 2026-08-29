# RSM crux research — handoff for Codex

Written 2026-08-29. This is for a **fresh session with no prior context**
continuing the "Repairable Semantic Memory" (RSM) crux research. Read this
before touching anything. If you are working on the hackathon submission
itself (video, Devpost, deploy), that is a different, unrelated thread —
see `SUBMISSION_HANDOFF.md` / `JUDGE_HANDOFF.md` instead.

## What this is, in one sentence

Ten falsification rounds, live-tested against `gemini-3.5-flash`, probing
whether an LLM can identify and surgically strip poisoned influence from
already-fused text — a harder, unbuilt extension beyond Custody's shipped,
deterministic, LLM-free whole-tool revocation mechanism (`custody/graph.py`,
E2D falsifier, PASS, 11/11 live judges).

**Read `research/experiments/RSM_CRUX_SERIES_SUMMARY.md` in full before
doing anything else.** It has the results table, what's supported, what's
open, and the honest bottom line across all 10 rounds. This handoff does
not repeat that content — it only covers process, constraints, and where
to pick up.

## Non-negotiable constraints

1. **`custody/*.py` is never touched by this work.** Verify with
   `git diff --stat main -- custody/` after every single commit — it must
   show zero content changes (a filemode-only diff, 0 insertions/0
   deletions per file, is a known artifact of this filesystem/mount and is
   fine; any real diff is not).
2. **No merge of the research branch into `main`.** This is unvalidated,
   exploratory, small-n, single-model work. A merge-to-main or
   citation-rewrite decision is separate and requires the user's explicit
   sign-off — do not do it unprompted, even if a round produces a clean
   result.
3. **No claim-carrying memory system, support-formula engine, or repair
   operator gets built.** Every round is a narrow probe against a
   precommitted synthetic fixture, not a step toward shipping RSM as a
   product feature. If you find yourself writing production-shaped code
   (a class hierarchy, a persistence layer, an API), stop — that is scope
   creep past what any round in this series has done.
4. **Fixture, then model call, never the reverse.** Ground truth is
   written into `fixture.json` before any Gemini call is made for that
   round. Never edit a fixture after seeing results to make a number look
   better — if a result is bad or ambiguous, report it as found (see
   rounds 1, 2, 7 for the house style of reporting an honest miss).
5. **Report honestly, including your own mistakes.** Multiple rounds in
   this series (2, 5, 9→10) found and reported invalid fixtures, confounds,
   or variance discovered mid-round rather than hiding them behind a clean
   headline number. That discipline is the actual point of the series —
   preserve it.

## Session/repo mechanics you need to know

- **Branch**: `research/rsm-crux-falsifier`, currently at commit `8ca503f`
  on `origin`. Check out or continue on this branch; do not create a new
  one unless a specific reason requires it (if so, branch off this one,
  not off `main`).
- **`.claude/SESSION_CONTRACT.md`** has a section near the top (`Branch:
  research/rsm-crux-falsifier`) with an `Allowed files:` list. A repo hook
  (`~/.claude/hooks/evidence_gate.py`, Claude-side, may not apply to a
  Codex session — check if an equivalent gate exists in your environment)
  blocks edits to files not on that list. Before adding a new round's
  files, append them to that list first, following the existing pattern
  (5 files per round: `PLAN.md`, `fixture.json`, `run.py`, `RESULT.md`,
  `result.json`).
- **`core.fileMode=false`**: pass `-c core.fileMode=false` on every `git`
  command that touches status/diff/add/commit in this checkout — the
  filesystem here cannot preserve file permissions, which otherwise
  generates hundreds of spurious mode-only diffs. Never persist this as a
  config change, only as a per-command flag.
- **Live model access**: `from google import genai; client =
  genai.Client(vertexai=True, project="project-988bc9fe-092c-4b32-90c",
  location="global"); client.models.generate_content(model="gemini-3.5-flash",
  contents=prompt)`. Requires `export CLOUDSDK_CONFIG="$PWD/.gcloud"`
  before running — the default gcloud config points at an unrelated
  project.
- **APOSD pre-commit hook**: a `claude -p` (or equivalent) review runs on
  commit and can block on a clear design red flag. Fix the issue and
  recommit; don't bypass with `--no-verify` unless truly stuck and you've
  said so to the user first.
- **Test suite**: `make check` must stay at 381/381 (this work doesn't
  touch code under test, so it should never move, but confirm every
  round — a change would itself be a signal something went wrong).
- **Naming convention**: `research/experiments/RSM_CRUXn_SHORT_NAME/`,
  five files per round as above. Next round is `RSM_CRUX11_...`.

## Where the series actually left off, and the strongest next moves

Read `RSM_CRUX_SERIES_SUMMARY.md`'s "What remains open" section for the
full list. In priority order, the three most load-bearing untested gaps:

1. **Bound the variance round 10 surfaced.** Round 10's naive condition
   produced a false positive on `vendor_onboarding` that round 9's
   identical prompt/domain got right — a single-call result flipped on
   rerun. No round in this series has repeated a call to separate a real
   mechanism limit from noise. The highest-information next move is
   probably **not** a new scenario — it's rerunning 2-3 existing rounds
   (pick ones with a clean claimed result, e.g. round 5 or round 9)
   5-10 times each and reporting the actual variance, before adding more
   novel scenarios on top of an unmeasured noise floor.
2. **Combine the skeptical mitigation with a multi-hop cascade.** Round 6
   showed cascading repair works at 2 hops with honest state. Round
   8/10 showed skeptical framing catches spoofed independence/provenance
   at a single hop. Nobody has tested whether a skeptical prompt still
   correctly cascades a legitimate retraction through 2 hops while also
   catching a spoof planted at hop 2 specifically — that's a real
   interaction, not just two separate wins stapled together.
3. **A harder, more plausible spoof.** Round 8 and round 10's spoofs were
   each a single, fairly simple "sounds independent but shares an
   unstated upstream" construction. Neither round's `RESULT.md` claims
   this generalizes to a more carefully constructed spoof — that's named
   explicitly as untested in both.

Lower priority, but still open and named in the summary: a literature
search on prior claim-decomposition/ATMS-style repair work (none has been
done in this entire series — every novelty framing has been explicitly
avoided, not because prior work was checked and ruled out, but because it
was never checked at all), and testing with a second model to see if any
finding is Gemini-specific.

## What "done" looks like for a new round

Matching every prior round's shape:

1. Write `PLAN.md` first: the question, the fixture design, and a bar
   stated *before* running (what result would be interesting either way —
   see round 8's or round 10's `PLAN.md` for the pattern of not
   precommitting to "should pass").
2. Write `fixture.json` with fixed ground truth.
3. Write `run.py`, run it live, do not touch the fixture afterward.
4. Write `RESULT.md` reporting the actual numbers, including any miss,
   confound, or caveat found on inspection — not just the headline
   accuracy fraction. Compare explicitly to what prior rounds already
   found where relevant (this series builds each round on the last, not
   in isolation).
5. Update `RSM_CRUX_SERIES_SUMMARY.md`'s table and open-questions section
   to fold in the new round, same as round 10 did for round 9.
6. `git diff --stat main -- custody/` clean, `make check` 381/381, commit
   with an honest message (state the actual result, not just "added round
   N"), push to `origin/research/rsm-crux-falsifier`. Do not push to
   `main`.

## Who to ask if blocked

If a round's result is genuinely ambiguous, or you're unsure whether a
proposed next round is worth the model-call budget, that's a real
decision point for the user (Raghav) — surface it rather than guessing,
consistent with the "ask before expanding scope" default this whole
project runs under.
