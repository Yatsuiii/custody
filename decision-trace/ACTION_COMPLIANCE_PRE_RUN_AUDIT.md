# DecisionTrace action-compliance pre-run audit

Date: 2026-08-23  
Lane: optimization / research engineering  
Status: **FIX AUDIT ISSUE BEFORE RUN**

This is an audit artifact only. It authorizes no model calls and no
comparative Arms A/B/C.

## 1. Freeze verification

- Branch: `research/decisiontrace-action-compliance`
- Starting HEAD: `0983bdcfe5db4e16df05b70691bc6530779efe61`
- Frozen production: `explore/decision-trace-v0`
- Production SHA: `9bdec25e9a9e3aee157e5f73b2c78e690fc343e6`
- `sha256sum -c ACTION_COMPLIANCE_INVENTORY_SHA256.txt`: **PASS (9/9)**
- `python scripts/verify_authority_freeze.py`: **PASS (9/9)**
- `git diff 9bdec25e... -- app/`: **empty**
- Existing seven task artifacts and V1 manifest: unchanged.
- Kubernetes pilot task and pilot outputs: excluded from the statistical set.

The original inventory is frozen and the production resolver has not drifted.

## 2. Independent source audit

The audit reviewed every `TASK.md`, every context-bundle file, every pinned
SHA, every sanity patch, every grader, and every recorded result. The V1
checksum covers the reviewed files. Each bundle contains canonical primary
source URLs and source excerpts that support its claimed transition; the
recorded prior replays also show the pinned setup and grader behavior.

Live remote re-fetch was attempted for all seven repositories but was
unavailable in this environment. Therefore the source result below is an
artifact-level pass, not a fresh network attestation. No task is being
silently upgraded from that limitation.

| Task | Repository / pin | Authority evidence and distinction | Patch/grader audit | Result |
|---|---|---|---|---|
| `task-02-django-index-together-superseded` | `django/django` / `879e5d587b84e6fc961829611999431778eb9f6a` | Ticket #27236, 4.2 deprecation commit, 5.1 removal commit; `Meta.indexes` vs. still-functional `index_together` | AST/schema completion; warning-enforced ordinary test; A separates from B | **PASS*** |
| `task-go-01-maps-sorted-keys` | `golang/go` / `56ebf80e57db9f61981fc0636fc6419dc6f68eda` | #61626 explicitly declined slice helpers; #61900 accepted iterator composition | Go AST/data-flow plus package test; both patches technically pass | **PASS*** |
| `task-03-pip-inline-script-metadata` | `pypa/pip` / `b35182d8f7245f046eed2975275c57b54ce3ba56` | PEP 722 rejected/superseded; PEP 723 final; pip issue/merged PR | Behavioral parser probe for both formats; both task-complete | **PASS*** |
| `task-04-cpython-locale-encoding-scope` | `python/cpython` / `261a452a1300eeeae1428ffd6e6623329c085e2c` | PEP 597 text scope; merged binary exception explicitly reverted | Runtime text/binary behavior probe; applied pure-Python state | **PASS*** |
| `task-05-packaging-manylinux-aliases` | `pypa/packaging` / `19fbc45b24ca0d577c9b256bb404b0dbaf4903da` | PEP 600 replacement while retaining legacy aliases; merged PR #293 | Behavioral tag sequence probe; mechanism-level separation | **PASS*** |
| `task-06-opentofu-static-source-scope` | `opentofu/opentofu` / `3fdc8090501234c55093078255969ecbc46f2fe2` | Issue #1042 and maintainer comments exclude label interpolation; merged RFC/implementation cover source attributes | Go AST/data-flow and focused/full package tests | **PASS*** |
| `task-07-axum-optional-typed-header` | `tokio-rs/axum` / `fd11d8efde4895a2159a29dcd586a7db99917057` | Issue #2298 direction and merged PR #2475 distinguish absent from malformed values | Compiled public-contract and HTTP behavior probe | **PASS*** |

`PASS*` means: primary excerpts, URLs, pins, and prior recorded replay are
internally coherent. A fresh remote re-fetch and fresh 14-patch replay remain
required before authorization. The bundles are curated excerpts; there is no
machine-readable manifest proving that every contrary artifact in each full
repository history was considered. That is a residual source-completeness
risk, not a reason to rewrite the tasks.

## 3. Literal prompt audit

The agent-facing text is only the `requested_change` block, not the rest of
`TASK.md`. A deterministic scan found no task IDs, category labels, grader
field names, sanity-patch terms, or explicit superseded/rejected/reverted
markers in any of the seven blocks.

| Task | Leakage result | Realism / ambiguity result |
|---|---|---|
| Django | PASS — no metadata/status/grader marker | Ordinary composite-index plus schema-test request; allows old/new mechanisms |
| Go | PASS | Ordinary sorted-key test request; allows composition or a new helper |
| pip | PASS | Ordinary parser request; does not name PEP 722/723 or the governing format |
| CPython | PASS | Names `encoding="locale"` and pure-Python scope as task requirements, not authority; allows text-only or over-broad binary behavior |
| packaging | PASS | Names PEP 600 bounded slice, but does not state alias policy; allows alias omission or retention |
| OpenTofu | PASS | Names source-expression retention and excludes evaluator implementation as scope, but does not mention label authority |
| axum | PASS | Requests deliberate absent/malformed behavior without stating which outcome is correct |

No prompt rewrite is justified before comparative outputs. The context bundles
do contain headings such as “rejected predecessor” and “governing standard,”
but those same raw artifacts are intentionally supplied to all three arms;
that is context, not arm-specific leakage.

## 4. Context fairness

The intended raw block is:

1. the literal requested-change block;
2. the byte-preserved concatenation of all files under that task's
   `context_bundle/`, in deterministic filename order;
3. a neutral repository/task setup wrapper that contains no ground-truth
   fields.

The current repository has **no implemented assembler** that produces this
block, no frozen ordering/serialization file, and no run manifest. Therefore:

- Arm A exact raw context: **not yet materialized**;
- Arm B exact raw context plus summary: **not yet materialized**;
- Arm C exact raw context plus proof: **not yet materialized**;
- proof that B/C contain the byte-identical A block: **FAIL / unimplemented**.

This is a harness gap, not a task-inventory gap.

## 5. AuthorityProof oracle audit

### Current path

The frozen resolver accepts `list[Decision]` plus an `authority_scope`:
`resolve_authority_with_proof(decisions, authority_scope)` in
`app/authority.py`. The only existing ingestion path is `app/ingest.py`:

- it fetches live GitHub/KEP sources rather than consuming the task bundles;
- it uses Gemini to extract fields from source text;
- it constructs statuses, roles, scopes, and relationship edges from source
  shapes in Python code;
- it has no adapter for the seven task bundles;
- only the excluded Kubernetes pilot currently has a serialized
  `authority_proof.json`.

### Oracle finding

To create a proof for the seven tasks today, a researcher would have to hand
populate at least some of:

- `DecisionStatus` (`PROPOSED`, `ACCEPTED`, `REVERTED`, `SUPERSEDED`, etc.);
- policy versus implementation `role`;
- `authority_scope` / `related_components`;
- `SUPERSEDES`, `REVERTS`, `IMPLEMENTS`, or `RECONSIDERS` edges;
- `partial_acceptance` flags;
- candidate IDs and exclusions.

Those values are present in `TASK.md`, the ground-truth ledger, category
labels, prohibited interpretations, sanity patches, and grader metadata. If
any of those manually adjudicated values were used, Arm C would receive the
benchmark answer. **The current path is therefore an oracle leak and cannot
be used.**

Answer to the required question:

> Can Arm C produce its AuthorityProof without receiving any human benchmark
> answer that Arms A/B do not also have access to?

**No — not with the current implementation.**

### Fair extraction design required before a run

Build a separate, deterministic bundle adapter that reads only the exact raw
prompt and context block available to A/B/C:

1. extract source URLs and verbatim evidence spans from bundle text;
2. extract explicit lifecycle/status phrases only when literally stated in
   those artifacts (otherwise emit `UNRESOLVED`);
3. derive the requested scope from prompt/code-path text using a generic,
   documented rule, never from task ID/category/ledger/grader metadata;
4. infer relationship edges only from explicit textual relation statements;
5. emit no manually entered status, role, scope, edge, partial-acceptance
   flag, candidate, or expected-compliance field;
6. pass the resulting records to the unchanged frozen resolver;
7. if extraction cannot prove a field, preserve the uncertainty in the
   proof rather than repairing it with ground truth.

The adapter must be tested with adversarial fixtures and frozen before any
agent output. Its imperfections are part of the DecisionTrace treatment.

## 6. Arm B design (prompt frozen conceptually, output not generated)

Arm B should receive the same raw block and one summary generated once per
task, then reused across all stochastic coding repetitions. This removes
summary-generation noise from the arm comparison while preserving the
strong-context baseline.

Proposed summary prompt, to freeze only after the fair adapter is built:

```text
You are a context summarizer for a coding agent. Using ONLY the raw task
prompt and source artifacts below, summarize the engineering history without
calling DecisionTrace and without using any hidden task metadata. Identify:
(1) the currently applicable design, (2) historical alternatives, including
superseded, reverted, proposed, or rejected material when explicitly stated,
(3) scope constraints and neighboring scopes, and (4) uncertainty or facts
the sources do not establish. Cite the source filename or URL for each claim.
Do not invent a status, relationship, or implementation rule. Return concise
plain text with sections Current, History, Scope, and Uncertainty.
``` 

The summary model should be the same model family and model ID as the coding
agent, but it must never call the DecisionTrace resolver or receive a proof.

## 7. Execution backend and freeze status

The pilot demonstrated a workable pattern: isolated sparse checkout, one
non-interactive coding-agent invocation, deterministic `git diff` capture,
and a central grader. The available automatable backend is Claude Code CLI
`2.1.232` with `claude --print`; the exact model ID, temperature, token
budget, and timeout are **not frozen** in the repository. The planned
configuration would be:

- one fresh isolated worktree per run;
- same model/config for A/B/C;
- no network, MCP, or cross-run state;
- only `Read`, `Edit`, and constrained `Bash` for repository/tests;
- fixed timeout and max tool calls/tokens;
- patch captured by `git diff --binary --no-ext-diff HEAD`;
- agent response and patch stored under an opaque random run ID.

Because the exact model identifier/configuration and the orchestration script
are absent, the execution backend is **selected in principle but not frozen**.

## 8. Context-size audit

Exact sizes below are the literal requested-change block and the concatenated
raw bundle only. `TASK.md` metadata is excluded from the agent context.

| Task | Prompt words / bytes | Bundle words / bytes | Raw total words / bytes |
|---|---:|---:|---:|
| Django | 81 / 568 | 612 / 5,973 | 693 / 6,541 |
| Go maps | 112 / 703 | 1,317 / 9,028 | 1,429 / 9,731 |
| pip | 87 / 606 | 230 / 1,745 | 317 / 2,351 |
| CPython | 60 / 425 | 215 / 1,783 | 275 / 2,208 |
| packaging | 70 / 483 | 195 / 1,570 | 265 / 2,053 |
| OpenTofu | 63 / 439 | 205 / 1,921 | 268 / 2,360 |
| axum | 45 / 345 | 311 / 2,581 | 356 / 2,926 |

Arm B summary and Arm C proof sizes are **N/A** because neither has been
generated through a fair frozen path. A common context ceiling (proposed
8,192 model tokens, with explicit rejection on overflow rather than silent
truncation) must be enforced only after the summary/proof serializers exist.
No arm may receive a larger raw-context allowance.

## 9. Repetition and statistics plan

Candidate plans are 42, 63, and 105 coding runs for 2, 3, and 5 repetitions
per arm/task respectively. The prior pilot averaged about 86,625 tokens and
301 seconds per arm run, giving rough serial lower-bound estimates:

| Repetitions | Runs | Approx. tokens | Approx. serial agent time |
|---:|---:|---:|---:|
| 2 | 42 | 3.64M | 3.5 h |
| 3 | 63 | 5.46M | 5.3 h |
| 5 | 105 | 9.10M | 8.8 h |

These are planning estimates, not a quote; the pilot had one task and no
metered dollar price. A dollar estimate is **unknown** until the exact model
and billing plan are frozen.

Recommended plan, after the oracle/harness fix: **3 repetitions per arm per
task (63 runs)**. Two is too noisy for per-task stability; five spends roughly
67% more runs than three without creating new independent engineering
histories. The independent unit remains the task cluster (n=7).

Frozen aggregation proposal:

- report run-level rates with denominators 21 per arm (7 tasks × 3 runs);
- report each task's mean compliant-success, completion, test-pass, violation,
  and refusal/no-op rates across its three runs;
- choose the strongest A/B baseline by overall compliant-success rate, with a
  pre-registered tie break to Arm A;
- compute seven paired task differences `d_i = C_i - baseline_i`;
- use a fixed-seed (documented seed) percentile bootstrap over the seven task
  clusters, 10,000 resamples, for the 90% CI;
- never treat the 63 runs as 63 independent tasks.

The relative violation reduction is `(v_baseline - v_C) / v_baseline`. If the
baseline violation rate is zero, the ratio is undefined; the 50% reduction
gate cannot pass and no denominator workaround may be chosen after results.
Category advantage is reported as a strict positive category-level mean
difference in at least three distinct categories. The existing seven tasks
cover five categories, with singleton categories explicitly retained in the
table.

With n=7, every gate is mathematically calculable under these rules, but the
bootstrap has low power and coarse resolution. It remains a meaningful
falsifier: a strictly-positive 90% paired interval requires consistent
task-level improvement, not a pile of pseudo-independent repetitions.

## 10. Blind grading and sanity replay status

The intended blind layout is:

- opaque random run ID directory;
- separate protected run-ID → condition mapping;
- grader receives only pinned task, applied patch, and worktree;
- grader emits `TASK_COMPLETED`, `TESTS_PASS`, `AUTHORITY_COMPLIANT`, and a
  violation reason/category;
- condition is joined only after grading.

No such orchestration package currently exists. The 14 sanity patches were
**not freshly replayed in this session** because all seven external clone
fetches failed due unavailable network access. The frozen recorded outcomes
remain:

- all seven compliant patches: `true / true / true`;
- all seven violating patches: `TASK_COMPLETED=true`,
  `AUTHORITY_COMPLIANT=false`;
- six violating patches pass ordinary tests;
- Django's violating patch fails the warning-as-error test, as disclosed in
  the inventory.

Fresh replay is a hard pre-run gate and must be run after the fair adapter and
orchestration package exist. It must not be replaced by these historical
results.

The pilot fixture `task-01-k8s-postfilter-victims`, its proof, and all prior
pilot A/B/C outputs are excluded from task lists, power calculations, and any
future statistical result.

## 11. Dry-run status

There is no current run harness to dry-run. Worktree setup scripts and graders
exist per task, but condition randomization, prompt assembly, context-size
enforcement, opaque IDs, cleanup, and result-schema orchestration are absent.
Therefore the no-model dry-run is **BLOCKED / not executed**, rather than
being simulated by hand.

## 12. Audit verdict

### Experiment review

**Baseline:** Arm A receives all raw history; Arm B adds a strong same-model
summary; Arm C adds the frozen deterministic proof.  
**Hypothesis:** the proof increases compliant coding success without reducing
ordinary completion or tests.  
**Single changed variable:** the arm-specific derived context (summary versus
AuthorityProof); task, raw history, model, tools, and budgets must be held
constant.  
**Metric:** compliant success, with task-clustered paired differences and the
frozen seven-part GO gate.  
**Acceptance threshold:** the existing preregistered gate, unchanged.  
**Kill condition:** any oracle/manual ground truth in Arm C, checksum/freeze
drift, failed sanity replay, missing raw-context parity, or failed harness
dry-run blocks all comparative runs.  
**Result:** audit blocked by oracle path, absent context assembler, unfrozen
backend configuration, unavailable fresh replay, and absent dry-run harness.

### Recommendation

**FIX AUDIT ISSUE BEFORE RUN**

The next highest-leverage action is to implement and adversarially test the
oracle-free bundle adapter and scripted harness, then rerun the freeze,
freshly replay all 14 sanity patches, and perform a no-model dry-run. Do not
generate Arm A/B/C coding outputs until those artifacts pass.

Estimated audit-session usage: read-only inspection and local checks only;
zero model-under-test calls, zero agents, zero comparative outputs. Wall-clock
time: under one hour. No production files changed.
