# Handoff: the falsifier's structured condition is graded against its own input

Written 2026-08-17, out of a portfolio audit. Nothing in this document has been
applied. It specifies one fix and the gates that decide whether it worked.

Read `RESULTS.md` first for the numbers this concerns.

## 1. What is wrong

`RESULTS.md` reports structured memory at 100% citation-correct, 100%
rationale-match, 100% supersession-aware, n=37, and records a **GO** verdict on
that basis.

The rationale-match number is not a measurement. The grading key is inside the
prompt being graded.

Trace it:

| Step | Location | What happens |
| --- | --- | --- |
| Ground truth is mined | `mine_decisions.py:64` `pick_quote()` | `rationale_quote` is set to a contiguous substring of the live-fetched PR body or KEP file |
| Card is built | `run_conditions.py:137` | The card literally contains `f"Rationale: {d['rationale_quote']}\n"` |
| Card is handed to the model | `run_conditions.py:143` `run_structured()` | Every card for the repo is inlined, no retrieval step |
| Judge scores the answer | `grade.py:43` | `rationale_match` asks whether the answer "semantically matches the correct rationale above", where "above" is the same `rationale_quote` |

So the structured condition is asked to restate a string it was just given, and
is scored on whether it restated that string. 100% is close to the arithmetic
result of the setup, not evidence about structured memory.

The same applies to `citation_correct`: the card carries `Evidence: PR #N`, and
the judge checks for PR #N.

**The comparison is also unequal in a second way.** RAG retrieves `TOP_K = 5`
chunks (`run_conditions.py:106`). Structured receives *all* cards for the repo
with no retrieval at all (`run_conditions.py:144`). Two conditions doing
different tasks cannot be differenced.

## 2. Why this matters more than the number

The 57% for RAG and 14% for code-only are real. They measure retrieval plus
extraction against distractors, which is a fair task. Only the structured arm is
broken, which is unfortunately the arm the GO verdict rests on.

A reviewer who reads `run_conditions.py` for two minutes finds this. When the
headline is 100/100/100, they will read it. The current state converts good
underlying work into a credibility problem.

## 3. What is already sound. Do not "fix" these

- `pick_quote()` produces ground truth with **no LLM in the loop**. It is a
  verbatim span of a live document. Keep it exactly as it is.
- `build_query()` (`run_conditions.py:44`) builds the query from `chosen` and
  `context` only, never from `rationale_quote`. The query does not leak the
  answer. Keep this property and keep the comment that explains it.
- The RAG corpus deliberately contains the target document alongside real
  decoys, so RAG is not rigged to fail. Keep it.
- Judging is a separate Gemini call from the conditions. Keep it separate.
- The GO/KILL/CAUTION thresholds in `verdict_for()` were preregistered.
  **Do not touch them after seeing new numbers.** If the verdict flips, the
  flip is the result.

## 4. The fix

Three changes, in dependency order.

### 4.1 Store a distilled rationale in the card, grade against the verbatim span

This is the important one, and it makes the experiment *more* faithful to the
product rather than less. A real DecisionTrace record is a distillation of a
discussion, not a verbatim copy of one sentence out of it. Nobody ships a
decision store that pastes a raw quote.

At mining time, generate an abstractive one-line rationale per decision and
persist it as a new field, `rationale_card`, next to the existing
`rationale_quote`. The card renders `rationale_card`. The judge keeps grading
against `rationale_quote`.

Then a correct answer requires the model to carry the *meaning* through a
distillation, which is the actual claim DecisionTrace makes. Copying no longer
scores.

Constraint: `rationale_card` must be generated from the source document, and
must not be a substring of `rationale_quote`. Assert that at write time.

### 4.2 Give both conditions the same retrieval budget

Build an embedding index over the cards using the same embedder as
`rag_index.py`, and retrieve `TOP_K` cards for the query. Structured then
becomes "distilled records plus retrieval" against RAG's "raw chunks plus
retrieval", which isolates the representation. That is the thesis.

While doing this, **pool the card index across all four repos** (37 cards) rather
than per-repo. Per-repo pools are 5 to 19 cards, so a top-5 retrieval over 6
cards barely filters anything and the budget parity would be cosmetic. A single
37-card pool makes retrieval do real work.

### 4.3 Make the bug unreintroducible

Add a test that fails if any grading key appears in any condition's prompt:

```
for every decision d, for every condition c:
    prompt = build_prompt(c, d)
    assert d["rationale_quote"] not in prompt
```

This is the part that matters long term. The confound was not a typo, it was an
invariant nobody had written down. Write it down as an assertion and it cannot
come back. Same spirit as the rest of this repo: turn the failure mode into
state the code checks, rather than a caveat in a document.

## 5. What to re-run, and what it costs

Cached runs on disk: 37 each for `code_only`, `rag`, `structured`.

| Action | Count | Why |
| --- | --- | --- |
| Regenerate `structured` responses | 37 generations | its prompt changes |
| Keep `code_only` and `rag` responses | 0 | queries unchanged, so cached answers stay valid |
| Re-judge all three conditions | 111 judgements | the grading key changes, so old scores are not comparable |

About 148 Vertex calls total. Delete `data/runs/structured/` to force
regeneration; the existing `if not out.exists()` guard in `main()` handles the
rest.

## 6. Acceptance gates

1. The assertion in 4.3 exists and passes for all 37 decisions across all three
   conditions.
2. `structured` and `rag` each receive exactly `TOP_K` retrieved items, from the
   same embedder, over a pooled 37-card index.
3. `rationale_card` is present for all 37 decisions and is not a substring of the
   corresponding `rationale_quote`.
4. `RESULTS.md` carries a **Threats to validity** section that states plainly:
   citation-correctness is satisfied by construction for the structured arm,
   because the card carries the citation; and 19 of 37 decisions come from
   `kubernetes/enhancements`, so the headline is weighted toward KEP-shaped
   sources.
5. `RESULTS.md` adds a per-source breakdown (revert-pair vs KEP) alongside the
   pooled numbers.
6. The verdict is recomputed against the **unchanged** thresholds and recorded
   as whatever it comes out to be, including CAUTION or KILL.

## 7. If you would rather not re-run

The defensible fallback costs nothing and requires no Vertex calls: stop
reporting the structured arm as a measurement.

Retitle the result to what was actually established, which is real and worth
having on its own:

> Naive embedding RAG recovers the correct rationale for 57% of 37 real
> engineering decisions across four large repositories, and cites a wrong
> PR number 3% of the time. Code-only context recovers 14%.

Then state that the structured arm was an upper-bound sanity check with the
answer key in context, not a comparison, and that the real comparison is
pending. That is an honest, publishable framing of work already done.

What is not acceptable is leaving 100/100/100 in `RESULTS.md` with a GO verdict
attached and no note.

## 8. Priority

Do this before showing DecisionTrace to anyone technical. It is not urgent
against the deployed demo, which is unaffected. It is urgent against an
interview, a judge, or a reviewer, because it is the first thing any of them
would find.
