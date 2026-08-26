# Second-project search, resumed here — handoff for this worktree

Written 2026-08-16, mid-session. This is a **new working directory**, not a
copy of the old one. Read this before doing anything else here.

## Where this directory came from and why

This is a `git worktree` (`/run/media/Yatsuiii/Windows-SSD/custody-search-2`),
checked out on branch `explore/second-project-search-2`, off
`archive/second-project-search` at commit `853ad18`. It is physically
separate from `/run/media/Yatsuiii/Windows-SSD/custody`, which stays on
`feat/memory-provenance` (the Custody hackathon submission) and must not be
touched by this work. That separation is the whole point of doing it this
way — the original search handoff was explicit that nothing about the
second-project search may modify Custody source, gates, proofs, or docs, or
land on the submission branch.

**The original, longer handoff** (four dead candidates, the filter
methodology, credential details, discipline notes) still lives at
`/run/media/Yatsuiii/Windows-SSD/custody/second-project-search/HANDOFF.md`
in the *other* checkout — it was never committed to git (it's scratch), so
it doesn't exist inside this worktree by normal means. Read it there if you
need the full history; this file only covers what changed in this session
and how to keep going from here.

## What's different about this checkout

- `failure-mining/AutomationBench` here is a **symlink** to
  `/run/media/Yatsuiii/Windows-SSD/custody/failure-mining/AutomationBench`
  (the 645MB benchmark clone with its own `.venv`). It's gitignored on both
  sides, so it was symlinked in rather than recloned or copied.
- `.gcloud` here is a **symlink** to
  `/run/media/Yatsuiii/Windows-SSD/custody/.gcloud` (the ADC config dir), for
  the same reason. Credentials verified working this session:
  `yoursturuly@gmail.com` active, project `project-988bc9fe-092c-4b32-90c`.
- `.claude/SESSION_CONTRACT.md` in this worktree was overwritten with a
  contract scoped to this search work (branch `explore/second-project-search-2`,
  allowed files under `failure-mining/` only). The Custody contract that
  used to be there is gone from this worktree but is untouched in the
  original `custody/` directory.

If you `rm` or move those two symlinks, you break access to the venv and
credentials — don't, unless you mean to replace them with real copies.

## Session so far

Following the original handoff's section 6 ("if you resume"): credentials
verified, then moved to mining a domain other than Operations (the only one
run before). Picked **finance** (5 domains remained: finance, hr, marketing,
sales, support; sizes in `tasks.py` line count were all comparable to
operations' 30880 lines, finance was smallest at 19661).

Command, run from `failure-mining/AutomationBench/`:

```bash
export CLOUDSDK_CONFIG="/run/media/Yatsuiii/Windows-SSD/custody-search-2/.gcloud"
export AB_ADAPTER_PATH="/run/media/Yatsuiii/Windows-SSD/custody-search-2/failure-mining/adapter"
.venv/bin/python automationbench/scripts/eval.py --model gemini-3.7-flash \
  --api vertex_native --toolset api --domains finance \
  --reasoning-effort high --max-steps 50 --num-examples 30 --max-concurrent 5
```

Two things learned getting this to run, worth recording since they're not in
the original handoff:

1. **`AB_ADAPTER_PATH` is required** and undocumented in the prior findings —
   `eval.py` does `os.environ["AB_ADAPTER_PATH"]` with no default. It must
   point at the directory containing `vertex_client.py`
   (`failure-mining/adapter`), not the file itself.
2. **`--max-concurrent` defaults to 100**, and the finance domain's default
   dataset is 100 tasks (`eval_dataset is not set, falling back to train
   dataset` — finance apparently has no separate held-out eval split the way
   operations did, so `--num-examples 30` was added to keep it comparable
   and cheap). Running all 100 at full concurrency hit `429
   RESOURCE_EXHAUSTED` immediately. Dropped to `--max-concurrent 5`; still
   saw **one abort on the very first rollout** before settling in. That one
   abort needs to be checked against the "0 aborts" acceptance gate before
   trusting the pass rate — don't just read the summary number.

**Update: the eval finished during this session**, clean — 0 aborts (one
early abort self-resolved), 30/30 tasks, pass rate 50%, average partial
credit 81%. Result JSON:
`failure-mining/AutomationBench/visualizer/runs/local/gemini-3.7-flash-high-20260816-112049-271.json`.
Failures were read individually and clustered, and the write-up is already
in `failure-mining/FINDINGS.md` under "Second run, 2026-08-16: the `finance`
domain" — read that section before redoing this work.

**Two things came out of it, both in FINDINGS.md in full:**

1. A confirmed, disclosed benchmark bug: `automationbench/rubric/assertions/
   slack.py`'s `_normalize_text` is missing a trailing-zero-collapse step
   that the sibling `gmail.py` matcher already has (with a comment
   explaining exactly this problem). Any Slack `text_contains` assertion on
   a whole-number currency total false-negatives when the message renders
   cents (e.g. `"33,350"` never matches `"$33,350.00"`). Not a product —
   just filed, per "fix the fixture, not the system, and disclose it."
2. A candidate cluster, **gate 5 not yet checked**: agents correctly
   identify the entity/record but inconsistently apply a conditional or
   superseding business rule (wrong late-fee tier, a skipped Credit Hold
   eligibility check, a stale invoice amount that should have been
   overridden by a correction elsewhere in the inbox, wrong accrual splits)
   — distinct from Operations' entity-binding cluster because the entity is
   right and the *rule governing the action* is what's misapplied, and
   inconsistently (the same run gets an equivalent override right
   elsewhere). Four concrete examples are in FINDINGS.md.

## Gate 5: checked 2026-08-16, dead

The conditional-rule-misapplication cluster is killed, more decisively than
Operations' entity-binding cluster was. Full citations in FINDINGS.md; short
version: this is a named, actively benchmarked subfield ("policy-invisible
violations," arXiv 2604.12177), measured at scale on τ-bench/τ²-bench, with
its proposed fix already published and validated (deterministic eligibility
gates, arXiv 2607.07405), five more adjacent 2026 papers in the same space,
and an entire "AI agent guardrails" commercial product category (Galileo,
Atlan, AWS Bedrock Guardrails, Vertex AI Safety, Privacera, Immuta) already
selling exactly this mechanism. Do not re-propose it, and do not spend time
re-verifying this search — it was thorough (four separate query angles,
academic and commercial) and the result was not close.

## Next steps, in order

1. **This finding is closed as a product.** What survives: a reproduction
   data point (the same failure mode shows up on AutomationBench finance,
   not just τ-bench/τ²-bench) and the disclosed `slack.py` grader bug —
   neither is a submission, both are recorded in FINDINGS.md.
2. **Try a different domain.** finance and operations are both mined and
   both dead. Untried: **hr, marketing, sales, support** — same command
   shape documented in FINDINGS.md, swap `--domains`. Read failures
   individually before clustering; don't stop at the aggregate score.
3. **Budget check before continuing**, per the original handoff's standing
   note: this is now two domains mined, two clusters found, both already
   claimed — the same pattern as three of the four original dead
   candidates. If a third domain also lands on an already-occupied
   mechanism, that is itself a signal worth surfacing to the user rather
   than mining a fourth and fifth domain on inertia: it may mean Gemini
   3.7's failure modes on this benchmark are, as a set, already well-covered
   by 2026's agent-reliability literature, which would be a reason to
   revisit whether continuing the search is still the highest-leverage use
   of remaining time versus Custody.
4. Separately, low-priority: the slack.py grader bug could be reported/fixed
   upstream (it's a one-line port from gmail.py), but that's not this
   project's deliverable — don't let it become a distraction from the
   search itself.

## Standing reminder from the original handoff, worth repeating

Four candidates already died in two days, and the honest advice after that
was to stop and spend the remaining time on Custody. The user chose to keep
going and that's still their call to keep making, not something to
relitigate here. Budget accordingly: this is a search with a real chance of
coming up empty again, in a research area that publishes faster than a build
cycle.
