# Action-Compliance V6 Manifest Runtime-Boundary Amendment

## Status

The original V6 manifest is superseded before statistical output. Its file
SHA-256 was:

```text
0e8a02d2da4da13ea947d8681ae38e66b3fd4beddc4f0fde5b2f72309bcca84a
```

The exact superseded manifest is preserved as
`ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V6_PRE_RUNTIME_BOUNDARY_FIX_SHA256.txt`.
At supersession, `data/action_compliance/codex_runs_v6_host/` contained zero
files and no V6 statistical coding-model call had begun.

## Defect and correction

The original manifest included `host_launch_snapshot.json` from the model-free
dry-run directory. That file records a timestamped host environment observation
and is rewritten on every host launch. A completed dry-run therefore changed a
listed checksum before the execution gate, which correctly stopped V6 before
any statistical model call.

The manifest generator now classifies host launch snapshots as mutable runtime
evidence and excludes them from the immutable experiment-input manifest. The
snapshots remain preserved in their output directories for audit. Frozen
dry-run plans, rows, patches, setup logs, results, and resume state remain in
the manifest.

No task, prompt, context, summary, AuthorityProof, extractor, resolver, grader,
test contract, model, reasoning effort, approval policy, sandbox, timeout,
storage policy, run ID, repetition, statistic, or GO criterion changed. The
Codex backend hash therefore remains unchanged.
