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

---

# Amendment 1 — derivation rules revised at the dry-run gate

Recorded **before any v2 generation, grading or scoring call**. §9 of this
spec reserves the dry run as the point at which a bad rule gets fixed
rather than run. Three rules did not survive contact with the documents.
Each change is listed with what it was, what it is now, and the evidence
that forced it. No score existed when any of them were made.

## A1.1 — the unit is the *leaf-most* alternative heading, not the child

**Was** (V2): an immediate child heading of the canonical section, or a
top-level bullet where the section uses no headings.

**Now**: the leaf-most heading inside the canonical section whose own name
is not a part label (`Advantages`, `Disadvantages`, `Cons`, …). Prose-bullet
sections yield nothing at all.

**Why**: KEPs group at different depths. KEP-2876 lists `Rego`, `Expr`,
`WebAssembly` flat at level 3; KEP-3488 groups its options under
`Policy definition and configuration separation alternatives` and names the
real ones a level deeper. Taking immediate children gave KEP-3488 four
group labels — and "the group label instead of the option" is exactly the
representation error the audit found in v0's card for that KEP. Taking
leaves gives `Duck Typed CRDs`, `OpenAPIv3 $ref in CRDs`,
`` `/matchRules` subresource ``, which are the actual alternatives.

Prose-bullet sections are dropped because there the option name and its
rationale are one fused sentence, so no name can be put in the question
without also putting the reason there. This excludes 3 KEPs on document
shape: `auth-1205` (a v0 **failure**), `2332` and `storage-2451` (v0
**passes**). A fourth, `5501`, contributes nothing because its Alternatives
section is written as a design FAQ. Dropping one failure and three passes
is not a score-selective filter, and it was fixed before any score existed.

## A1.2 — name-shape filter replaces the length filter

**Was** (V3): reject if under 3 characters or if stripping links leaves
under 8 characters.

**Now**: reject if the name is a question, matches the meta-name prefix
list, or its head noun is a meta word (`alternatives`, `considerations`,
`criteria`, `analysis`, `justification`, …). Strip a leading
`Rejected alternative:` alongside enumeration and `Alternative:`.

**Why**: the 8-character rule deleted `Rego` and `Expr`, two genuine
alternatives, while admitting `How should outdated messages be handled?`
and `Primary evaluation criteria`, which are design questions no one can
substitute into "was X considered, and why wasn't it adopted?". Stripping
`Rejected alternative:` matters for fairness: leaving it in would put the
disposition into the question.

## A1.3 — the cue-word requirement is removed entirely

**Was** (V4): a labelled disposition part, **or** a body containing a
`REJECTION_CUES`/`RATIONALE_CUES` hit; otherwise excluded.

**Now**: the labelled disposition part when present, otherwise the whole
write-up. No lexical gate.

**Why**: this is the most important amendment. The cue gate excluded 28 of
71 alternatives, and reading them showed it was excluding the *good* ones:

- "…so there is not a clear way for this to be implemented" — dropped.
- "It's unclear how we would do this without conflicting with usage of
  groups and potentially compromising security" — dropped.
- "File-based config isn't easily kept in sync in HA apiserver setups" —
  dropped.

while v0's cue list happily admitted "requests would be **rejected** once
the initial token got expired", where the word means HTTP requests. Keyword
matching for rationale is precisely the defect that produced v0's invalid
ground truth, and rebuilding the benchmark on top of it would import the
disease into the cure. A heading under a section titled *Alternatives* is,
by the document's own structure, an option the project did not take, so its
write-up is evidence about why — whether or not it uses a magic word.

Consequence to keep in view: 46 of 65 KEP targets are whole-body evidence
and 19 are labelled disposition parts. `RESULTS_V2.md` reports the split.

## A1.4 — the decoy invariant is restated as anti-planting

**Was** (§6 rule 2, as tested): no decoy chunk may contain any case's
evidence span.

**Now**: no case's **own cited document** may appear in its repo's decoy
pool, and any incidental overlap must come from a different document and is
printed for disclosure.

**Why**: the original assertion failed, and the cause was not a leak.
KEP-5593 inherits its Alternatives section from its predecessor KEP-4603,
and 4603 is a legitimate member of the 150-document decoy pool. 5593's own
document is not in the pool. Public corpora genuinely repeat themselves,
and this particular repetition can only ever help the **RAG** arm — it
cannot reach structured or code-only. Forbidding it would mean deleting a
real decoy to make RAG's job harder, which §6 rule 4 prohibits. It is
disclosed instead: **6 of 65 KEP cases**, all from KEP-5593, have evidence
text that also appears in KEP-4603.

## A1.5 — resulting case set

| | count |
|---|---|
| cases | **83** |
| clusters (decisions) | 33 |
| `revert_pair` (carried over unchanged) | 18 |
| `kep_alternative` | 65, across 15 KEPs |
| evidence tier: labelled / whole-body / v0 carryover | 19 / 46 / 18 |
| alternatives per contributing KEP (min/median/max) | 1 / 4 / 9 |
| exclusions after the rules above | 0 |
| evidence verified verbatim in live source | 83/83 |

Residual imperfections, disclosed rather than tuned away: `Scopes`
(KEP-3488) and `On Success and the 10 minute recovery threshold`
(KEP-5593) are topic headings rather than option names — 2 of 65. Three
structural passes were made over the derivation rules; all were completed
before any generation ran, and rule-tuning stopped there.

The predictions in §8 stand as written and were not revised.

---

# Amendment 2 — v2.1, removing the supervision leak

Recorded **after** v2's numbers were seen and **before** any v2.1
generation or grading call. The v2 result is not being discarded or
rewritten; it stands in `RESULTS_V2.md` exactly as it came out, including
its GO verdict. What follows is a further experiment, because that GO is
not defensible and saying so is more useful than banking it.

## A2.1 — What v2 actually measured

v2 returned structured 99% (82/83), RAG 55%, code_only 10%, verdict GO.
Two measured properties of the construction explain most of that gap.

1. **The card index is bijective with the test set.** 83 cards for 83
   cases, each card's `reason` distilled from precisely the span the judge
   grades against, and the question containing that card's
   `alternative_name` verbatim. Measured: the case's own card is in the
   top 5 for 83/83 cases and at rank 1 for 82/83. Structured was performing
   an exact-key lookup against a store built one record per question.
2. **Half the KEP questions need no memory at all.** `code_only` has no
   retrieval and no cards and still scores `rationale_match` on 32 of 65
   KEP cases, because naming an alternative usually implies its weakness.

Neither is a coding error; both follow from deriving the cases and the
cards from the same structural pass. But the combination means v2 tested
retrieval and generation over a pre-solved memory, and did not test the
step where a decision-memory product can actually fail: **extraction**.

## A2.2 — The one change

Exactly one thing changes. The structured store is rebuilt by an
**unsupervised ingestion pass**:

- One call per KEP over its whole canonical Alternatives section.
- The model decides how many alternatives exist, names them itself, and
  writes each one's reason. Uncapped.
- It is **not** given the case list, the case names, or any per-case
  evidence span.
- All **19** KEPs are ingested, including the 4 that contribute no cases,
  so their alternatives enter the index as genuine distractors.
- Revert cards are unchanged: a revert decision has exactly one
  alternative and its card was already distilled from the whole PR body,
  so there was never per-case supervision there.

Everything else is held fixed: the same 83 questions, the same targets,
the same judge prompts, the same `TOP_K=5`, the same embedder, the same
model, the same thresholds imported from `grade.py`.

`rag` and `code_only` responses are **reused unchanged**, because their
prompts are byte-identical between v2 and v2.1. That is a uniform rule
applied to every case of those conditions, not a per-case choice, and it
is the same rule `docs/FALSIFIER_CONFOUND_HANDOFF.md` §5 used in v0.

## A2.3 — Hypothesis and predictions

**Hypothesis.** The remaining difficulty in structured decision memory
lives in extraction, not in retrieval or generation. Removing the
supervision leak should therefore move the number materially, and whatever
it moves to is the first honest estimate of the product's real capability.

Predictions, fixed now:

1. Structured combined **falls from 99%**. Predicted band **70–90%**.
2. The drop is driven by **extraction recall**, not by retrieval rank: the
   ingester will fail to emit a matching record for some case
   alternatives, and those cases will fail.
3. RAG stays at 55% and code_only at 10% by construction, since their
   responses are reused.

**New metric, defined before results.** *Extraction recall*: of the 65 KEP
case alternatives, the fraction for which the unsupervised ingester
produced a record whose own card is retrieved into that case's top-5
prompt. This is the number the experiment exists to produce.

## A2.4 — Kill criterion

If structured under v2.1 is **below 85%**, the verdict is CAUTION and that
is the reported result. No third benchmark, no further rule changes, no
re-judging. If it is at or above 85% with the leak removed, the GO is
reported together with both the v2 and v2.1 numbers and with this
amendment attached, so a reader can see exactly what was and was not
tested.

Either way `RESULTS_V2.md` keeps the v2 numbers alongside the v2.1 ones.

---

# Amendment 3 — v2.2, removing a handicap on the RAG arm

Recorded **before** any v2.2 generation or grading call. This one corrects
an unfairness that runs *against* the result I already have, so it can only
make the GO harder to keep.

## A3.1 — The defect

In `run_rag` (v0's, inherited unchanged by v2) the decision's own source
document is indexed as:

```python
[{"id": "TARGET", "text": doc}]
```

while every decoy keeps its real identifier — `keps/sig-api-machinery/
1027-api-unions/README.md`, `elastic/elasticsearch#111968`. The prompt then
renders each chunk as `[<doc_id>]`. So the **only** document that can
answer the question is the only one whose identity is hidden, and the
distractors all announce theirs.

Measured consequence on the v2 KEP arm: the target document is retrieved
in **65 of 65** cases and RAG states a correct reason in **88%** of them,
but cites correctly in only **49%**. Retrieval is not RAG's problem and
reasoning is not RAG's problem. Its combined score is being held down
almost entirely by a labelling artifact, and citation is precisely the
metric on which the structured arm wins.

This also explains RAG's 7% hallucinated-citation rate: asked to cite, with
the right document anonymised and several decoys clearly named, the
plausible move is to cite a decoy.

Meanwhile the structured card has always rendered `Evidence: <path>`
inline. So the two conditions were not being asked the same thing.

## A3.2 — The change

One change, RAG-only, applied uniformly to all 83 cases: the target
document's chunks are labelled with the case's real citation identifier,
using the same convention the decoys already use — the file path for KEPs,
`{repo}#{revert_pr}` for revert pairs. Nothing else moves: same retrieval,
same `TOP_K`, same embedder, same chunking, same corpus, same questions,
same judge, same thresholds. The cached embeddings are reused; only the
identifier attached to them changes, so this costs no re-embedding.

`code_only`, `structured` and `structured_ingested` are **not**
regenerated: their prompts do not contain a target label and are byte-
identical. Only the condition whose prompt changed is re-run, which is the
same uniform rule used in Amendment 2.

## A3.3 — Predictions and kill criterion

Fixed now:

1. RAG citation-correct rises materially from 59% pooled / 49% on the KEP
   arm. RAG's rationale-match should be roughly unchanged near 88%.
2. RAG combined therefore rises from 55% and **may cross the 70% ceiling**
   that `verdict_for()` requires for GO.
3. If it does, the verdict becomes CAUTION — or KILL at 90% or above — and
   **that is the reported result.** The v2.1 GO does not survive on the
   strength of a labelling artifact, and I would rather lose it honestly
   than keep it this way.
4. Structured's numbers do not move, because nothing in its path changed.

The comparison this produces is the one the project actually wants: both
arms see what they retrieved and both are told where it came from, so the
question becomes whether a distilled per-alternative record beats raw
chunks of the same document. That is the thesis, tested without a thumb on
either scale.
