# Per-alternative retrieval handoff — the next real lever on the falsifier

For a fresh session picking this up. No prior context assumed. The
previous session ran the falsifier confound fix all the way through three
rounds and landed on a converged, honest number. This doc is about the
next concrete improvement, not a repeat of that work — read the "What's
already true" section below before touching anything.

## What's already true — verified, don't re-derive

As of 2026-08-18, `.claude/SESSION_CONTRACT.md` has four `Status: complete`
entries this session, in order:

1. **Apply the falsifier confound fix** — the original benchmark had a
   real confound (structured's card rendered `rationale_quote` itself,
   the same string the judge graded against). Fixed with a distilled
   `rationale_card` field, pooled 37-card retrieval, and a leakage test.
   Result: structured 46% combined-correct (a bug, see next entry).
2. **Multi-point rationale cards** — the 46% was itself a bug, not a
   capability limit: a one-sentence card can't represent a KEP's
   `## Alternatives Considered` section when it names multiple distinct
   alternatives. Added `distill_rationale_card_multi()` in
   `mine_decisions.py`. Result: 78% combined.
3. **Tighten pick_quote() for kep_alternatives ground truth** — 5 of 7
   remaining failures traced to the ground-truth extractor grabbing a
   sentence about the *chosen* design, not a rejected alternative (its
   cue regex matched generic "because"/"since"). Added a stricter
   `REJECTION_CUES` tier, `pick_quote(require_rejection=True)`. Result:
   76% combined — within judge-noise of 78%, a wash, not a regression.
4. **This doc.**

**Current, real, final numbers** (`RESULTS.md`, 2026-08-18):

| Condition | Combined (citation + rationale) |
|---|---|
| code_only | 0% |
| rag | 57% |
| structured | 76% |
| structured, `revert_pair` subset only (n=18) | 94% |
| structured, `kep_alternatives` subset only (n=19) | 58% |

**Verdict is CAUTION**, not GO — `verdict_for()` in `grade.py` requires
`structured >= 85%` for a clean GO; rag already clears its side
(`<=70%`). The threshold was never touched across three fix rounds. The
gap is entirely in the `kep_alternatives` subset — `revert_pair` is
already excellent.

**Do not re-run the confound fix, the multi-point cards work, or the
pick_quote() tightening again.** All three are done, verified, and their
full diagnosis is in the session contract entries above. If you find
yourself about to touch `pick_quote()`, `CARD_PROMPT`/`CARD_PROMPT_MULTI`,
or re-derive why KEPs score lower than revert-pairs — stop and read those
entries first, the answer is already there.

**Not yet done, separate from this doc's scope**: `README.md`'s
Architecture section still states an old "100% vs 57%, GO" claim from
before any of the above. It needs updating to 76%/57%/CAUTION before any
Devpost submission text cites this benchmark. That's a small, separate
task — do it if asked, but it's not what this doc is about.

## The next lever: retrieval granularity, not card content

Three rounds of fixing *what a card says* (confound → multi-point →
ground truth) converged on the same ~76-78% band. That convergence is
itself evidence: card *content* is no longer the bottleneck. The
remaining gap is structural, in how retrieval is *indexed*.

### The current mechanism (`run_conditions.py`)

```python
def get_card_index(all_decisions: list[dict]):
    """Embedding index over every decision's card, pooled across all repos
    (37 cards)..."""
    docs = [{"id": d["decision_id"], "text": card_text(d)} for d in all_decisions]
    return rag_index.load_or_build_index(CARDS_INDEX_CACHE, docs)


def run_structured(all_decisions: list[dict], d: dict, query: str) -> tuple[str, list[str]]:
    chunk_texts, chunk_doc_ids, chunk_vecs = get_card_index(all_decisions)
    retrieved = rag_index.top_k_chunks(
        query, chunk_texts, chunk_doc_ids, chunk_vecs, k=TOP_K
    )
    ...
```

`card_text(d)` renders **one whole card per decision** — for a
multi-point KEP card, that's all 3-6 alternatives concatenated into a
single embedded string:

```python
def card_text(d: dict) -> str:
    return (
        f"Decision [{d['decision_id']}]\n"
        f"Context: {d['context']}\n"
        f"Chosen: {d['chosen']}\n"
        f"Rejected/Reverted: {d['rejected']}\n"
        f"Rationale: {d['rationale_card']}\n"  # <- all points, joined
        f"Evidence: {cite_str(d)}"
    )
```

So retrieval picks **decisions**, never alternatives within a decision.
Citation-correct is already 100% — retrieval always finds the right
*decision*. But once retrieved, the model has to synthesize an answer
from a card that may describe 5-6 different rejected approaches, and pick
which one the judge's ground-truth quote happens to be about. That's the
mechanism gap: precision at the decision level, imprecision at the
alternative level.

### The proposed fix: index one embeddable unit per alternative-point

Instead of embedding the whole card, split `rationale_card` into its
individual points (already newline-`"- "`-delimited for multi-point
cards, or the single sentence for one-point cards) and index **each point
separately**, still tagged with its parent `decision_id` so citation and
grading still resolve correctly.

Concretely, add to `run_conditions.py` (or `mine_decisions.py`, either is
reasonable — keep it near `card_text`/`cite_str` since it reuses them):

```python
def split_rationale_points(rationale_card: str) -> list[str]:
    """rationale_card is either one sentence (single-alternative cards)
    or several "- "-prefixed lines (distill_rationale_card_multi output).
    Splits into individual points; a single-sentence card yields a
    one-element list, unchanged in meaning."""
    lines = [
        ln.strip().lstrip("- ").strip()
        for ln in rationale_card.splitlines()
        if ln.strip()
    ]
    bulleted = [ln for ln in lines if rationale_card.strip().startswith("-")]
    return bulleted if bulleted else [rationale_card.strip()]


def point_card_text(d: dict, point: str) -> str:
    """Same shape as card_text(), but Rationale: is a single alternative
    point instead of the whole (possibly multi-point) card — so a
    retrieved unit is self-contained enough to answer from and cite
    correctly even when only one point of a multi-point decision is
    retrieved."""
    return (
        f"Decision [{d['decision_id']}]\n"
        f"Context: {d['context']}\n"
        f"Chosen: {d['chosen']}\n"
        f"Rejected/Reverted: {d['rejected']}\n"
        f"Rationale: {point}\n"
        f"Evidence: {cite_str(d)}"
    )


POINTS_INDEX_CACHE = DATA_DIR / "corpus" / "points-index.json"  # new cache
                                                                  # file, don't
                                                                  # overwrite
                                                                  # cards-index.json


def get_point_index(all_decisions: list[dict]):
    """Like get_card_index(), but pooled across every alternative-point
    (roughly 60-90 points across 37 decisions, not 37 whole cards) —
    retrieval can now surface the specific point a query is about,
    instead of the whole decision it belongs to."""
    docs = []
    for d in all_decisions:
        for point in split_rationale_points(d["rationale_card"]):
            docs.append({"id": d["decision_id"], "text": point_card_text(d, point)})
    return rag_index.load_or_build_index(POINTS_INDEX_CACHE, docs)
```

Then `run_structured()` needs exactly one line changed:

```python
def run_structured(all_decisions: list[dict], d: dict, query: str) -> tuple[str, list[str]]:
    chunk_texts, chunk_doc_ids, chunk_vecs = get_point_index(all_decisions)  # was get_card_index
    retrieved = rag_index.top_k_chunks(
        query, chunk_texts, chunk_doc_ids, chunk_vecs, k=TOP_K
    )
    retrieved_cards = [text for _, text in retrieved]
    retrieved_ids = [doc_id for doc_id, _ in retrieved]
    prompt = build_structured_prompt(query, retrieved_cards)
    return vertex.generate(prompt), retrieved_ids
```

`top_k_chunks()` and `build_structured_prompt()` need no changes — the
existing infra already supports multiple chunks sharing a `doc_id`
(that's exactly how `rag_index.chunk_by_section` already works for the
`rag` condition), and `build_structured_prompt` just joins whatever
`retrieved_cards` it's given.

### What could go either way — this is a real experiment

- **TOP_K stays 5**, same as now, to preserve the "equal retrieval budget"
  fairness property the confound-fix entry established. That means the
  pooled index roughly doubles in size (60-90 points vs 37 cards) while
  K stays fixed — retrieval now picks from more, narrower candidates.
  That could help (each candidate is topically precise, one alternative
  instead of a whole multi-topic card) or hurt (more near-duplicate
  distractors, e.g. several "Rejected because too complex" points from
  different KEPs competing on generic phrasing). Don't assume which way
  it goes — that's what running it tells you.
- Some of the top-5 retrieved points may end up from the **same**
  decision (e.g. 2 of 5 slots both from one KEP that's very relevant to
  the query) — that's expected and fine, same as how RAG's own chunking
  already allows multiple chunks per doc.
- Consider whether to dedupe identical `Evidence:`/citation lines when
  multiple retrieved points share a decision — not required for
  correctness (the model can handle repeated context), but worth a look
  if prompts get noisy.

## Acceptance gates

1. `split_rationale_points()` correctly yields one element for
   single-sentence cards (all `revert_pair` cards, plus any
   single-alternative KEP cards) and N elements for multi-point cards —
   spot-check against 3+ real `rationale_card` values in
   `data/decisions.jsonl` before trusting it on the full set.
2. `get_point_index()` builds without error and its cache file
   (`data/corpus/points-index.json`) is new, not overwriting
   `cards-index.json` — so the old whole-card index stays available for
   comparison/rollback.
3. `run_structured()` swapped to use the point index; `run_conditions.py`
   re-run for **all 37 decisions'** structured condition (delete the old
   `data/runs/structured/*.json` files first — every one needs
   regenerating this time, unlike the prior entries where only KEP rows
   changed, since the retrieval mechanism itself changed for everyone,
   including `revert_pair`).
4. Full `grade.py` re-run (111 calls, judge isn't cached).
5. `test_no_leakage.py` still passes in full — `build_structured_prompt`
   still only ever renders `rationale_card`/point text, never
   `rationale_quote`, so this should hold automatically, but verify.
6. RESULTS.md's `kep_alternatives`-subset combined score is the number
   that actually answers the hypothesis — compare it against the current
   58% baseline. Record whatever it is, including if it's worse; that's
   a real result, not a bug to explain away.

## Non-goals

- Do not touch `pick_quote()`, `CARD_PROMPT`/`CARD_PROMPT_MULTI`,
  `verdict_for()`'s thresholds, or `mine_reverts()`/`mine_keps()`'s live
  mining — none of that is in scope here, and all three prior entries
  already covered that ground.
- Do not change `TOP_K` from 5 without flagging it explicitly — that's
  the fairness-parity constant shared with the `rag` condition.
- Do not delete or overwrite `cards-index.json` — keep it so the
  whole-card approach can be compared against or rolled back to.
- No commit/push without separate explicit authorization.
