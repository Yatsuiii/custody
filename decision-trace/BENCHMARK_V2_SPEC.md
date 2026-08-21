# DecisionTrace falsifier v2 — preregistered specification

Written **before** any v2 generation or grading call. Branch
`research/decisiontrace-plateau`, parent `1c33d3d`. Nothing in v0 is
modified; v2 lives entirely in new paths.

Read `BENCHMARK_FAILURE_AUDIT.md` first — this document only states what
changes and why, and fixes every rule before results exist.

## 1. Is the v0 KEP task scientifically compatible with its grading?

**No.** Three independent reasons, each measured in the audit:

1. **Set question, element answer.** `build_query()` asks *"What does this
   project's history say about alternatives that were already considered
   here, and why weren't they used?"* — a question about a set.
   `grade.py` scores `rationale_match` against **one** `rationale_quote`.
   Nothing in the query identifies which element is the target. Across the
   8 KEP failures the system named a mean of 4.4 real rejected
   alternatives with correct source reasons and scored zero on all of
   them. That is not a measurement of recall; it is a measurement of
   whether an unseeded choice happened to land on the graded element.

2. **The budget cannot even hold the set.** `TOP_K = 5` and KEPs carry up
   to 9 named alternatives (`CARD_PROMPT_MULTI` itself caps at 6). Three
   failures lost the target alternative's card point to the top-5 budget
   *inside the correct decision*. For a multi-alternative KEP the maximum
   attainable score is bounded by cardinality, not by system quality.

3. **The targets are not reliably rejection rationales.** 9 of 19 KEP
   ground truths are still selected by the loose `RATIONALE_CUES` because
   `reextract_kep_quotes.py` silently keeps the old quote on `no_pick`.
   4 of the 9 failures have targets that are not a rejected-alternative
   rationale at all: reasoning for the chosen design, a rollout caveat,
   a meta-narrative about editing the proposal, and a truncated lead-in
   clause. One target lies outside any Alternatives section, selected on
   the word "rejected" meaning *HTTP requests were rejected*.

A benchmark can be hard, arbitrary, or noisy and still be valid. This one
is **ill-posed**: for a large fraction of its KEP rows there is no
behaviour the system could exhibit that would reliably score correct.

The `revert_pair` half is *not* ill-posed — one decision, one supersession,
one stated reason — and is therefore left untouched.

## 2. What v2 changes

One change: the KEP arm goes from

> one KEP → broad question about all alternatives → one arbitrary sentence

to

> one **named alternative** → targeted question about **that** alternative
> → the contiguous source span stating **that** alternative's disposition

The `revert_pair` arm is carried over **byte-identical**: same 18
decisions, same queries, same `rationale_quote` targets, including
`elastic-…-147071`, whose target the audit judges to be a symptom rather
than a cause. Repairing exactly the one revert row that failed would be
rewriting a failed ground truth. It stays as it is, and it will most
likely still fail. That is deliberate.

This keeps v2 a single-variable change at the benchmark level.

## 3. Case derivation — uniform structural rule, fixed now

Derivation is rule A from the brief: **every explicitly named alternative
in every valid Alternatives section**, with a validity filter that is
purely structural and fixed before any score exists.

A KEP alternative becomes a v2 case iff all of:

- **V1** The KEP has a canonical Alternatives section: the *shallowest*
  heading whose title matches `^alternatives?( considered)?$`
  (case-insensitive), found with a **fence-aware** parser so `#` comments
  inside code blocks are never treated as headings. Section extent runs to
  the next heading of the same or shallower level — not to the next `##`,
  which is the v0 bug.
- **V2** The alternative is a named item of that section: an immediate
  child heading, or — only when the section has no child headings — a
  top-level bullet.
- **V3** The name survives a meta-label denylist fixed in advance:
  rejected if it matches
  `^(detailed comparison|comparison|summary|table|notes?|references?|see also|open questions?|background|goals?|non-goals?)\b`,
  if it is under 3 characters, or if stripping markdown links leaves under
  8 characters (this drops navigational bullets like
  *"in [GDoc which preceded this KEP](…)"*). Leading enumeration
  (`1.`, `2)`) and an `Alternative:` prefix are stripped from the name.
- **V4** The alternative's body contains an explicit **disposition span**:
  a labelled sub-part matching
  `Why (Rejected|not)|Disadvantages?|Cons\b|Drawbacks|Reasons? for reject`,
  taken from the label to the end of that sub-part; or, if no label is
  present, the whole body, which must then contain at least one
  `REJECTION_CUES` or `RATIONALE_CUES` hit.
- **V5** The disposition span is at least 40 characters after stripping
  markdown and URLs. This is what makes v0's
  *"* **Why Rejected**: This approach was discussed as a potential
  implementation detail…"* truncation impossible: the span is the whole
  labelled part, not the first sentence of it.
- **V6** No leakage: the alternative name shares no contiguous 6-word span
  with its own evidence quote.

Every alternative failing any of V1–V6 is **excluded and counted by
reason** in the dry-run report, before any generation runs. Exclusions are
never decided per-case after seeing a score.

The evidence span is capped at 1200 characters, cut at a sentence
boundary, purely to bound judge-prompt size.

## 4. Ground truth

Per v2 case:

- `alternative_name` — verbatim from the source heading/bullet, normalised
  only by stripping enumeration and the `Alternative:` prefix.
- `evidence_quote` — the contiguous disposition span, verbatim from the
  live source. No LLM in the loop, same discipline as v0's `pick_quote()`.
- `citation` — the KEP file path (revert cases keep both PR numbers).

## 5. Structured representation — first-class alternative objects

The audit's class-B failures (`3488` dropped three of four alternative
groups; `2523` compressed away one of two disadvantages; the "up to 6"
cap binding on 4 of 19 KEPs) say the free-form multi-point
`rationale_card: str` is the wrong abstraction. v2 replaces it, for the
benchmark path, with one object per alternative:

```json
{
  "decision_id": "...",
  "alternative_name": "...",
  "reason": "abstractive, generated from THIS alternative's body only",
  "evidence_quote": "verbatim source span — provenance only",
  "source_path": "keps/..."
}
```

Rules that make this safe:

- The rendered card shows `alternative_name`, `reason`, `source_path`.
  It **never renders `evidence_quote`**. Rendering it would reintroduce
  the original confound exactly (`docs/FALSIFIER_CONFOUND_HANDOFF.md` §4.1).
- `reason` is generated per alternative, from that alternative's body
  alone — so there is no cap, no "up to 6", and no competition between
  alternatives for room in one card.
- Assert at build time: `reason` is not a substring of `evidence_quote`
  and vice versa; no contiguous 6-word overlap.
- No alternative is invented. If a named alternative has no explicit
  disposition in the source, V4 excludes it from the benchmark rather than
  a reason being fabricated for it.
- Revert cases reuse their existing distilled `rationale_card` as `reason`
  unchanged — no new distillation, no content change.

Retrieval indexes **one card per alternative object** plus one per revert
decision, pooled across all repos, `TOP_K = 5` — the same budget and the
same embedder as RAG.

This is a benchmark-path change only. `app/**` is untouched. Whether the
product should adopt the same abstraction is a separate, separately
authorised decision.

## 6. Fairness rules (binding)

1. RAG, structured and code-only receive the **identical** developer query
   for a given case.
2. No condition's prompt may contain that case's `evidence_quote`, except
   where RAG legitimately retrieves the target document — which is the
   RAG condition's whole test, exactly as in v0.
3. The query is built only from `repo`, `context`/`chosen` and
   `alternative_name`. It never contains the reason, the disposition, or
   `decision_id`.
4. RAG's corpus is unchanged: the same decoy pools plus the decision's own
   source document. RAG is not degraded, and naming the alternative in the
   query is a **stronger** retrieval signal for RAG than v0's broad query.
5. Same model, same version, same temperature, same `TOP_K` for all
   conditions. `vertex.py` is untouched.
6. Judging stays a separate Gemini call, identical prompt shape for all
   three conditions.
7. All v0 data and results stay byte-identical. v2 writes only to
   `data/v2/`, `data/runs_v2/`, `RESULTS_V2.md`.
8. `test_no_leakage_v2.py` must prove rule 2 for every case in every
   deterministic condition before generation runs.
9. `verdict_for()` is **imported from `grade.py`**, not reimplemented, so
   the GO/KILL/CAUTION thresholds cannot drift: structured ≥ 85%,
   RAG ≤ 70%, KILL at RAG ≥ 90%.
10. Every inclusion/exclusion rule above is fixed by this document, before
    results exist.

## 7. Metrics and reporting

Same four judge fields as v0. Combined = `citation_correct AND
rationale_match`. `rationale_match` for a v2 KEP case asks whether the
answer gives a reason for **that named alternative** not being chosen that
is consistent with the source evidence span.

Reported: overall combined, citation correctness, rationale correctness,
hallucination rate, per-source breakdown, per-case detail, numerator and
denominator everywhere, and Wilson 95% intervals.

**Clustering disclosure.** v2 KEP cases are not independent: several cases
share one document and one card-building pass. So `RESULTS_V2.md` also
reports a **per-decision-averaged** score (each decision contributes once,
as the mean of its cases) as a conservative secondary statistic, and the
number of clusters alongside the number of cases. The headline number is
the per-case one; the clustered one is published next to it so a reader
can discount it themselves.

Model/API failures are recorded separately from wrong answers and never
counted as correct.

## 8. Preregistered predictions

Recorded now so they cannot be fitted afterwards.

1. **Structured KEP-arm combined rises well above 58%**, because 7 of 9
   failures were target-selection artefacts rather than system behaviour.
   Predicted band: 80–95%.
2. **RAG also rises, and this is the main risk to a GO verdict.** Naming
   the alternative in the query is a much stronger embedding signal for
   RAG than v0's broad question. RAG's KEP arm was 21%; it should improve
   materially, and pooled RAG could cross the 70% ceiling that
   `verdict_for()` requires for GO. If that happens the verdict is
   CAUTION — or KILL at ≥90% — **and that is a real result about
   structured memory not earning its complexity, not a bug to fix.**
   v2 is not built to produce GO; it is built to produce a well-posed
   question.
3. **code_only stays near zero combined**, since it still cannot cite.
4. `elastic-…-147071` most likely still fails, by design (§2).

## 9. Cost and stop conditions

Dry run (§10) spends zero generation calls. If it reports malformed
targets that V1–V6 did not catch, **stop and fix the rule**, do not
generate.

Budget: one distillation call per KEP alternative, then
`3 × n_cases` generations and `3 × n_cases` judgements.

## 10. Gates before any Vertex generation spend

1. Case count, source distribution, alternatives per KEP, and exclusion
   counts by reason, all reported.
2. Every case's `evidence_quote` verified present verbatim in the live
   source.
3. `test_no_leakage_v2.py` passes for every case and every deterministic
   condition.
4. Structured cards verified to carry the expected alternative and reason,
   and verified never to carry `evidence_quote`.
5. A hand-read sample of cases confirms the targets are real dispositions.

Only after all five: generate, grade, publish `RESULTS_V2.md`, and record
whatever `verdict_for()` returns.
