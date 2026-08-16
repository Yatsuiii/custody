# Frozen 2026-08-16

Not abandoned, not resumed. Closed research, not part of the Custody
submission. See `FINDINGS.md` for the full write-up.

**The method change.** Stop inventing a thesis about what Gemini cannot do.
Run it on a benchmark whose final state is checked programmatically
(AutomationBench: 600 verifiable workflows, 47 simulated SaaS tools, no LLM
judge), read the failures, cluster them, then check competitors.

**It worked, and that is the point worth keeping.** One afternoon produced
three real, reproducible failure clusters, where three idea-first theses had
each evaporated on contact with a falsifier.

**Why it stopped: all three clusters are already claimed**, each by work from
the last six months. Entity binding, arXiv 2606.30531, June 2026, with the
read-after-write remedy published two weeks ago as arXiv 2608.02645.
Explanation-bound execution, arXiv 2607.25364. Durable execution, an entire
funded product category. The field is publishing these conclusions faster than
a fifteen-day build cycle can reach them.

**What survives, and it is real:** `adapter/vertex_client.py`, a working
AutomationBench transport for Gemini 3.x over Vertex, written because every
off-the-shelf path was closed (OpenAI-compat drops thought signatures, the
benchmark's own client speaks a replaced input shape, the free tier allows 20
requests a day). Validated at 8/8 on `simple` after three genuine bugs.
Plus a reproducible 50% Operations baseline for `gemini-3.7-flash`, and the
measurement that one prompt-level sentence naming the failure fixes 1 of 6.

**Handling notes for anyone reopening this.** `AutomationBench/` and the API
key in `AutomationBench/.env` are double-ignored, by `.gitignore` here and by
the clone's own. The benchmark's tasks and graders were never modified; the
only change inside it is a disclosed transport branch in `scripts/eval.py`.
The one-sentence experiment's task-file edit was reverted with `git checkout`
and verified clean.
