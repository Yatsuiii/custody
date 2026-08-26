# Action-compliance extraction failure audit (v2 pre-work)

Date: 2026-08-23
Status: research-only. No holdout bundle content, per-task ground truth,
`governing_authority`, sanity patch, or grader was read to produce this
document. The only permitted fact carried over from the prior session is the
aggregate observation: 7/7 frozen bundles produced `NO_GOVERNING_DECISION`
(`ACTION_COMPLIANCE_BUNDLE_DIAGNOSTIC_COMPARISON.md`, read only for that
aggregate line and for the generic architectural facts below — its per-task
narrative column was not used to shape any extraction rule).

## 1. What the resolver actually requires (frozen, cannot change)

`app/authority.py::resolve_authority_with_proof` starts with exactly one
line that decides everything downstream:

```python
scoped = sorted(
    (d for d in decisions if authority_scope in d.related_components),
    key=lambda d: d.id,
)
if not scoped:
    return _build_no_governing(...)
```

This is **exact Python string membership** in a `list[str]`. There is no
normalization, no substring match, no fuzzy match, no case-folding. A
`Decision` only participates in resolution at all if one of its
`related_components` entries is byte-identical to the `authority_scope`
string the caller passes in.

`scripts/run_action_compliance_bundle_ingestion.py` passes
`extraction.requested_scope` as that `authority_scope` — a single free-text
string produced by the extractor's own read of the prompt. Nothing
downstream reconciles it against the decisions' `scopes`; that reconciliation
has to already exist by the time extraction returns.

## 2. What the v1 prompt actually asks for (root cause)

`app/ingest.py::_BUNDLE_EXTRACTION_INSTRUCTIONS` asks the model for two
independently-phrased free-text fields with no instruction that they must
agree:

- `requested_scope`: "the exact code/subsystem scope requested" — extracted
  from the prompt's prose, with no length or form constraint. In practice
  this invites either a full paraphrase of the requested-change block or an
  idiosyncratic phrase.
- per-decision `scopes`: "literal scope strings explicitly supported by the
  **source**" — extracted independently per artifact, worded however that
  artifact's own text happens to name the subsystem.

Nothing in the prompt tells the model these two fields feed one exact-string
join. Nothing asks it to pick a single canonical scope identifier and reuse
that identical string in both places. Two independent free-text
paraphrases of the same underlying subsystem, produced by an LLM with no
shared-vocabulary constraint, are extremely unlikely to be byte-identical —
different tense, different noun phrasing, different granularity, prompt
paraphrase vs. source paraphrase.

**This is the generic root cause.** It is architectural, not a per-task
extraction quality problem: even a perfect, fully-correct read of every
artifact's lifecycle state fails downstream if the one required string
match — `requested_scope == <one of a decision's scopes>` — never fires. A
`NO_GOVERNING_DECISION` result is the resolver's correct, honest answer to
"none of these records carry the exact scope string I was asked about," and
that condition is structurally near-guaranteed by a two-independent-free-text
schema, regardless of how good the underlying lifecycle read is.

This also explains why `NO_GOVERNING_DECISION` (scope-empty) rather than
`UNRESOLVED` (scope non-empty but ambiguous) was the dominant v1 failure
mode: `UNRESOLVED` requires records to already be in the requested scope and
conflict; most v1 runs never got that far because `scoped` was already
empty.

## 3. Secondary generic risks (checked from the code/schema, not from
   holdout text)

Reviewed against the questions in the task brief:

- **Lifecycle status vs. discussion**: the schema forces a `current_status`
  choice from a closed enum for every emitted decision, with a documented
  escape hatch (drop the whole record instead of guessing) — i.e. the model
  is not required to fabricate a status. That escape hatch is a `failures[]`
  entry per record, not a partial/uncertain status value. There is no
  `UNCERTAIN` status in `DecisionStatus`; the only way to express "read this
  but can't tell its lifecycle state" is to omit it from `decisions[]`
  entirely, which loses the record instead of keeping it as an explicitly
  uncertain candidate. This is a real gap but secondary to §2.
- **SUPERSEDES/REVERTS relationship detection**: the schema supports it
  (`related_decisions` with `target_index` + `relationship`), and IDs are
  assigned deterministically from artifact identity/position rather than
  trusted from the model, which is sound. But relationship edges are scoped
  to `target_index` within the *same* extraction call's `decisions[]` list
  only — an edge can never point at a decision the model chose not to emit
  (e.g. because its status was ambiguous and it got dropped per the
  paragraph above). A dropped low-confidence record silently deletes any
  edge that would have explained why a later record governs.
  A generic deprecation-then-removal pattern spans exactly this dropped-node
  failure mode.
- **Multiple artifacts reconciled**: yes structurally — `extract_bundle_decisions`
  makes one Gemini call over the concatenation of all artifacts in one
  prompt (`_bundle_prompt`), so the model can in principle see the full
  chronology and cross-reference artifacts in one pass. Reconciliation is
  not prevented by transport; it depends entirely on whether the single
  response's fields agree with each other, which is exactly the §2 gap.
- **Timestamps/order**: `artifact.timestamp` (first `YYYY-MM-DD` regex match
  in the artifact) is attached to `introduced_at` but is not given to the
  model as an ordering signal in the prompt — the model sees the artifacts
  in filename order with a timestamp header, but nothing asks it to reason
  about chronology explicitly.
- **Metadata discarded by the bundle adapter**: no — `BundleArtifact` keeps
  `source_url`, `title`, `timestamp`, and full `content`; all four are
  rendered into the prompt (`_bundle_prompt`). Nothing is silently dropped
  before the model sees it.
- **Fragmented/normalized IDs preventing linking**: decision IDs
  (`bundle-{artifact_id}-decision-{ordinal}`) are assigned after extraction
  and are stable within one run, so they do not themselves fragment
  authority. The fragmentation is in `related_components` (scope strings),
  covered in §2, not in decision identity.
- **Resolver receiving empty/ineligible records**: yes, this is the
  observed symptom, and it is downstream of §2 — the resolver is not
  receiving zero decisions, it is receiving decisions whose `related_components`
  never intersects the one `authority_scope` string it was asked to
  resolve.

## 4. What must change, and what must not

The fix belongs entirely in extraction (Phase 6 constraint: resolver frozen,
untouched). The generic, benchmark-agnostic requirement is: **the extractor
must emit one canonical scope identifier per subsystem and reuse that exact
string as both the requested scope and the scope tag on every decision that
subsystem's evidence supports** — a single-pass internal consistency
constraint, not a benchmark-specific mapping. Extractor v2
(`app/action_compliance_extraction_v2.py`) implements this by asking the
model to first name a short canonical scope slug set, then use only slugs
from that set everywhere else in the same response, and by keeping a
non-emitting `UNCERTAIN`-style path (recorded as `uncertainty[]`, not a
silently dropped node) for decisions whose lifecycle status can't be
determined, so an edge naming that node is not silently orphaned.

No holdout bundle, `TASK.md`, grader, sanity patch, or `ACTION_COMPLIANCE_LEDGER.md`
row was read to write this document.
