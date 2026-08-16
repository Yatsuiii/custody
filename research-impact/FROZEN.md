# Frozen 2026-08-16

Not abandoned, not resumed. This directory is closed research and must stop
consuming hackathon execution time. It is not part of the Custody submission.

**What it is.** Keel, a persistent research change-impact engine: a typed graph
of hypotheses, assumptions, experiments and claims, with excerpt-anchored
provenance and deterministic state propagation over an event-sourced ledger.

**Why it stopped.** Three pre-registered falsifiers, in order:

- **F1 dev** (15 controlled variants): a tie. F1 0.909 for a monolithic Gemini
  given the whole graph, 0.907 for bounded judgment plus deterministic
  propagation. The headline claim did not survive its own first test.
- **F1 holdout** (18 unseen variants, locked before tuning, digest
  `80b07fc8...`): a loss, 0.993 to 0.939. The strength-rubric change made on
  the dev set made the holdout *worse*, which is the result the lock existed
  to make visible.
- **F3 longitudinal** (10 history-dependent documents, 80 adjudicated pairs,
  sequence digest `409edd00...`): **KILL by hard override.** A *persistent*
  monolithic baseline reached 0.956 per-step accuracy and 1.000 correction
  persistence. Persistent explicit state bought nothing measurable over
  persistent context.

**What is worth keeping.** The method, more than the artifact: freezing a dev
set and locking a holdout before tuning; benchmarking against the strongest
baseline rather than a memory-denied one; pre-registering what "substantial"
means before seeing numbers. Three ground-truth defects and two metric bugs
were caught by those disciplines and are disclosed in the results rather than
quietly fixed.

Artifacts: `results/f1-dev-summary.json`, `results/f1-holdout-summary.json`,
`results/f3-summary.json`, and the two lock files. 113 tests, `make judge`
22/22, judge rejects 4 forged artifacts. Reproducible; nothing here is
believed on the strength of prose.
