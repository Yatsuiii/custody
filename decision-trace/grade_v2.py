"""Grades the three conditions against the v2 benchmark and writes RESULTS_V2.md.

Judging is a separate Gemini call from the conditions, identical in shape
for all three, exactly as in v0.

`revert_pair` cases are judged by v0's `grade.judge_one` verbatim, so that
arm is unchanged between benchmarks in query, target and grading. Only the
KEP arm uses the v2 judge, which asks about one named alternative instead of
"the rationale" of a whole KEP.

`verdict_for` is imported from grade.py rather than reimplemented, so the
preregistered GO/KILL/CAUTION thresholds cannot drift.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

import vertex
from grade import judge_one as judge_v0, verdict_for
from run_conditions_v2 import RUNS_DIR, load_cases

CONDITIONS = ["code_only", "rag", "structured"]
# v2.1 is graded as a fourth column: identical questions, identical judge,
# identical rag/code_only responses, but the structured store was rebuilt
# by an unsupervised ingestion pass. See BENCHMARK_V2_SPEC.md Amendment 2.
V21 = "structured_ingested"
# v2.2 relabels the RAG target with its real identity; see Amendment 3.
V22 = "rag_labelled"
V2_DIR = Path(__file__).parent / "data" / "v2"
SCORES_PATH = V2_DIR / "scores.json"

JUDGE_PROMPT_V2 = """You are grading whether an AI assistant's answer \
correctly recalled a specific real engineering decision.

GROUND TRUTH
Project decision: {chosen}
The specific alternative in question: {alternative_name}
Correct citation: {citation_str}
What the project's source document actually says about this alternative \
(verbatim):
{evidence_quote}

ASSISTANT'S ANSWER
{response}

Score the assistant's answer on exactly these four fields, as strict JSON \
with no other text:
{{
  "citation_correct": true/false,   // cites the correct PR/issue number(s) or file path from the ground truth citation, not just any number
  "rationale_match": true/false,    // says why this specific alternative was not adopted, consistently with the source text above (paraphrase is fine; it need not repeat every point the source makes; a different or invented reason is not)
  "hallucinated_citation": true/false, // cites a DIFFERENT specific PR/issue number as if it were the relevant one, when it is not the correct citation
  "supersession_aware": null // not applicable for this case type
}}"""


def citation_str(c: dict) -> str:
    cit = c["citation"]
    if "original_pr" in cit:
        return (f"PR #{cit['original_pr']['number']} "
                f"(reverted by PR #{cit['revert_pr']['number']})")
    return cit["file"]["path"]


def judge_one(c: dict, response: str) -> dict:
    if c["source"] == "revert_pair":
        return judge_v0({"chosen": c["chosen"], "citation": c["citation"],
                         "rationale_quote": c["evidence_quote"],
                         "superseded_by": c["superseded_by"]}, response)
    prompt = JUDGE_PROMPT_V2.format(
        chosen=c["chosen"], alternative_name=c["alternative_name"],
        citation_str=citation_str(c), evidence_quote=c["evidence_quote"],
        response=response,
    )
    raw = vertex.generate(prompt)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    blank = {"citation_correct": False, "rationale_match": False,
             "hallucinated_citation": False, "supersession_aware": None}
    if not m:
        return {**blank, "judge_error": raw[:200]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {**blank, "judge_error": raw[:200]}


def graded_conditions() -> list[str]:
    extra = [c for c in (V21, V22) if (RUNS_DIR / c).exists()]
    return CONDITIONS + extra


def grade_all(cases: list[dict]) -> dict:
    scores = json.loads(SCORES_PATH.read_text()) if SCORES_PATH.exists() else {}
    for i, c in enumerate(cases):
        cid = c["case_id"]
        for cond in graded_conditions():
            key = f"{cond}::{cid}"
            if key in scores:
                continue
            run_path = RUNS_DIR / cond / f"{cid}.json"
            if not run_path.exists():
                continue
            print(f"[{i + 1}/{len(cases)}] {cond} {cid[:60]}")
            scores[key] = judge_one(c, json.loads(run_path.read_text())["response"])
            SCORES_PATH.write_text(json.dumps(scores, indent=1))
    return scores


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z, p = 1.96, k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z / denom * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def combined(rows: list[dict]) -> int:
    return sum(1 for s in rows
               if s.get("citation_correct") and s.get("rationale_match"))


def clustered(cases: list[dict], scores: dict, cond: str) -> tuple[float, int]:
    """Each decision contributes once, as the mean of its own cases. v2's KEP
    cases share a document and a card-building pass, so the per-case number
    overstates independent evidence."""
    by_dec = defaultdict(list)
    for c in cases:
        s = scores.get(f"{cond}::{c['case_id']}")
        if s is not None:
            by_dec[c["decision_id"]].append(
                bool(s.get("citation_correct") and s.get("rationale_match")))
    if not by_dec:
        return (0.0, 0)
    means = [sum(v) / len(v) for v in by_dec.values()]
    return (sum(means) / len(means), len(means))


def rows_for(cases, scores, cond, source=None):
    return [scores[f"{cond}::{c['case_id']}"] for c in cases
            if (source is None or c["source"] == source)
            and f"{cond}::{c['case_id']}" in scores]


def headline_table(cases, scores) -> tuple[list[str], dict]:
    lines = ["| Condition | Citation-correct | Rationale-match | "
             "Combined (both) | 95% CI | Hallucination | Per-decision mean |",
             "|---|---|---|---|---|---|---|"]
    rates = {}
    for cond in graded_conditions():
        rows = rows_for(cases, scores, cond)
        n = len(rows)
        cc = sum(1 for s in rows if s.get("citation_correct"))
        rm = sum(1 for s in rows if s.get("rationale_match"))
        cb = combined(rows)
        hl = sum(1 for s in rows if s.get("hallucinated_citation"))
        lo, hi = wilson(cb, n)
        cl, k = clustered(cases, scores, cond)
        rates[cond] = cb / n if n else 0.0
        lines.append(
            f"| {cond} | {cc / n:.0%} ({cc}/{n}) | {rm / n:.0%} ({rm}/{n}) | "
            f"**{cb / n:.0%}** ({cb}/{n}) | {lo:.0%}–{hi:.0%} | "
            f"{hl / n:.0%} | {cl:.0%} (k={k}) |")
    return lines, rates


def source_table(cases, scores) -> list[str]:
    lines = ["| Condition | Source | Citation | Rationale | Combined |",
             "|---|---|---|---|---|"]
    for cond in graded_conditions():
        for src in ("revert_pair", "kep_alternative"):
            rows = rows_for(cases, scores, cond, src)
            if not rows:
                continue
            n = len(rows)
            cc = sum(1 for s in rows if s.get("citation_correct"))
            rm = sum(1 for s in rows if s.get("rationale_match"))
            lines.append(f"| {cond} | {src} | {cc / n:.0%} | {rm / n:.0%} | "
                         f"{combined(rows) / n:.0%} (n={n}) |")
    return lines


def case_table(cases, scores) -> list[str]:
    cols = graded_conditions()
    lines = ["| case_id | source | " + " | ".join(cols) + " |",
             "|---|---|" + "---|" * len(cols)]
    for c in cases:
        cells = []
        for cond in cols:
            s = scores.get(f"{cond}::{c['case_id']}")
            cells.append("-" if s is None else
                         ("C" if s.get("citation_correct") else "c")
                         + ("R" if s.get("rationale_match") else "r")
                         + ("H" if s.get("hallucinated_citation") else ""))
        lines.append(f"| `{c['case_id'][:78]}` | {c['source']} | "
                     + " | ".join(cells) + " |")
    return lines


METHODOLOGY = """
## What changed from v0, and why

| | v0 | v2 |
|---|---|---|
| KEP unit | one KEP | one **named alternative** |
| KEP question | "what alternatives were considered here, and why weren't they used?" | "was *X* considered, and if so why wasn't it adopted?" |
| KEP target | one sentence picked by a cue regex | the alternative's own contiguous disposition span |
| Section boundary | next `##`, from an unanchored match | next heading of the same or shallower level, fence-aware |
| Structured record | one free-form card, "up to 6" points | one first-class object per alternative, uncapped |
| `revert_pair` arm | 18 cases | **identical** 18 cases, same query, same target, judged by v0's `judge_one` |
| Retrieval | `TOP_K=5` over 91 points | `TOP_K=5` over the alternative-card pool |
| Thresholds | structured >= 85%, RAG <= 70% | **unchanged**, imported from `grade.py` |

v2 is a different task from v0. It is not a corrected score for the same
question, and the two headline numbers should not be differenced. What is
comparable is the mechanism: v0 asked a set question and graded one
element, v2 asks about the element it grades.

## The three confounds, and what actually survives them

Read this before quoting any number in the table. Two of the three inflate
the structured arm and one deflates the RAG arm, and once all three are
removed the headline claim does not survive.

**Confound 3 — RAG was never told which document it had retrieved.**
`run_rag` indexed the answer-bearing document as `{"id": "TARGET"}` while
every decoy kept its real identifier (`keps/sig-.../README.md`,
`elastic/elasticsearch#111968`). The prompt renders each chunk as
`[<doc_id>]`, so the one document that could answer the question was the
one document whose identity was hidden, and every distractor announced
its own. The structured card, meanwhile, has always rendered
`Evidence: <path>` inline. The two arms were not being asked the same
thing.

Measured: on the KEP arm RAG retrieved the target in **65/65** cases and
stated a correct reason in **88%** of them, but cited correctly in **49%**.
Relabelling the target with its real identity — nothing else changed, same
chunks, same vectors, same questions — moves RAG's KEP citation from 49%
to **95%** and its combined score from 55% to **89%**.

**What survives.** With the structured store built without ever seeing the
question list (`structured_ingested`) and RAG told what it retrieved
(`rag_labelled`), the comparison is **RAG 89% (74/83) versus structured
87% (72/83)**. The difference is two cases, far inside both Wilson
intervals. On rationale alone the two are 89% and 87%. The verdict under
the unchanged thresholds is CAUTION, one point below the KILL line.

**So the structured-versus-RAG advantage this benchmark was built to
demonstrate is not demonstrated.** v0's apparent gap (76% vs 57%) was two
artifacts pointing in opposite directions: structured was held down by
ground truth it could not have matched, and RAG was held down by a
labelling bug on the only document that mattered. Correct both and the two
arms are tied.

One asymmetry now runs the *other* way and is worth stating: RAG sees the
verbatim graded span whenever it retrieves the right chunk, while the
structured arm only ever sees a paraphrase and never the graded text. That
structured reaches parity from a distillation is a real qualitative point
in its favour. It is not what the preregistered threshold asks, and the
threshold governs.

## The two confounds that make 99% indefensible

Read this before quoting the headline number. The structured arm's 99% is
close to a tautology of how v2 was constructed, and it is reported here
only because the result is the result.

**Confound 1 — the card index is bijective with the test set.** v2 built
exactly one card per case, 83 for 83, and each card's `reason` was
distilled from precisely the span the judge grades against. The developer
question contains that card's `alternative_name` verbatim, so retrieval is
an exact-key lookup: measured, the case's own card is in the top 5 for
**83 of 83** cases and at **rank 1 for 82 of 83**. The only step between
the graded span and the answer is one paraphrase whose explicit purpose is
to preserve meaning. This is structurally the same family of defect as the
confound `docs/FALSIFIER_CONFOUND_HANDOFF.md` fixed in v0 — not identical,
since a paraphrase and a retrieval barrier sit in between, but it is
supervision leaking from the test-set decomposition into the memory being
tested. A real ingestion pipeline is not handed the list of questions.

**Confound 2 — half the KEP questions are answerable without any memory.**
`code_only` has no retrieval, no history and no cards, and still gets
`rationale_match` on **32 of 65** KEP cases. Naming an alternative often
implies its own weakness to any competent model ("why not Rego?" invites
"no static typing"). So in v2 `rationale_match` is a weak discriminator
and `citation_correct` carries most of the signal, which is the metric the
threats section below already flags as satisfied by construction for the
structured arm.

Together these mean the 99/55 gap overstates what structured memory
contributes. The honest reading of v2 is narrower: **given a correctly
extracted per-alternative record, answering "why wasn't X used?" is close
to solved, and the difficulty lives in the extraction, which v2 did not
test.** `BENCHMARK_V2_SPEC.md` Amendment 2 specifies the corrected run
that does test it.

## Threats to validity

- **Citation-correctness is satisfied by construction for the structured
  arm**, exactly as in v0: each retrieved card carries its own
  `Evidence:` line, so answering from a card at all tends to cite
  correctly. This measures whether retrieval found the right card, not
  independent recall of the citation.
- **Cases are clustered, not independent.** 65 of 83 cases come from 15
  KEPs, so several cases share one document and one card-building pass.
  The per-decision mean in the headline table is the conservative
  statistic; the per-case number and its Wilson interval assume more
  independence than the design has.
- **The benchmark is more KEP-weighted than v0** (78% vs 51%). Since the
  KEP arm is the harder one, this makes the pooled number harder to clear,
  not easier.
- **6 of 65 KEP cases have evidence text that also appears in a decoy**
  (KEP-5593 inherits its Alternatives section from KEP-4603, a legitimate
  member of the decoy pool). This can only help the RAG arm.
- **2 of 65 alternative names are topic headings rather than option names**
  (`Scopes`, `On Success and the 10 minute recovery threshold`). Disclosed
  rather than removed, since removing them after the fact would be
  case-level selection.
- **46 of 65 KEP targets are whole-body evidence**, not a labelled
  Why-Rejected part, so for those the judge is matching against everything
  the document says about the alternative, including description.
- **One revert case is knowingly mis-targeted.** `elastic-…-147071`'s
  target sentence is a symptom rather than the cause. It was left exactly
  as v0 had it, because repairing the single revert row that failed would
  be rewriting a failed ground truth.
- **The judge is an LLM.** A v0 variance probe over 9 failures flipped 1,
  so expect roughly ten percent of borderline rows to be unstable.
"""


def failure_diagnostics(cases: list[dict], scores: dict) -> list[str]:
    """Where the surviving structured failures actually break.

    For a v2 case the card that answers it is identifiable by case_id, so
    'was the right card even in the prompt?' is a fact rather than an
    inference. That splits the remaining gap into retrieval (the card was
    not retrieved), representation (it was retrieved but says the wrong
    thing), and citation-only misses, which is what Phase 7 needs to pick
    one intervention instead of guessing."""
    retrieved_miss, in_prompt_miss, citation_only = [], [], []
    for c in cases:
        s = scores.get(f"structured::{c['case_id']}")
        if s is None or (s.get("citation_correct") and s.get("rationale_match")):
            continue
        run_path = RUNS_DIR / "structured" / f"{c['case_id']}.json"
        got = json.loads(run_path.read_text()).get("retrieved", []) \
            if run_path.exists() else []
        if not s.get("rationale_match"):
            (in_prompt_miss if c["case_id"] in got else retrieved_miss).append(c)
        else:
            citation_only.append(c)
    lines = ["\n## Structured failure diagnostics\n",
             f"- own card **not** retrieved into the prompt: "
             f"**{len(retrieved_miss)}** (retrieval)",
             f"- own card retrieved but the answer still missed the reason: "
             f"**{len(in_prompt_miss)}** (representation or generation)",
             f"- rationale right, citation wrong: **{len(citation_only)}**\n"]
    for label, rows in (("not retrieved", retrieved_miss),
                        ("retrieved but missed", in_prompt_miss),
                        ("citation-only miss", citation_only)):
        for c in rows:
            lines.append(f"  - _{label}_: `{c['case_id'][:76]}`")
    return lines



def extraction_recall(cases, scores) -> list[str]:
    """The number v2.1 exists to produce.

    v2's store had one record per question, so retrieval was a key lookup.
    v2.1's store was built without ever seeing the question list, so a case
    can fail simply because the ingester never wrote a record for that
    alternative. This separates that failure from retrieval and generation."""
    cards = [json.loads(line) for line in (V2_DIR / "cards_ingested.jsonl").open()]
    by_id = {c["card_id"]: c for c in cards}
    same_dec = named = 0
    kep = [c for c in cases if c["source"] == "kep_alternative"]
    for c in kep:
        run = RUNS_DIR / V21 / f"{c['case_id']}.json"
        got = json.loads(run.read_text())["retrieved"] if run.exists() else []
        recs = [by_id[g] for g in got if g in by_id]
        if any(r["decision_id"] == c["decision_id"] for r in recs):
            same_dec += 1
        want = set(re.findall(r"[a-z0-9]+", c["alternative_name"].lower()))
        for r in recs:
            if r["decision_id"] != c["decision_id"]:
                continue
            have = set(re.findall(r"[a-z0-9]+", r["alternative_name"].lower()))
            if want & have and len(want & have) / max(len(want), 1) >= 0.4:
                named += 1
                break
    n = len(kep)
    return [
        "\n## v2.1 extraction recall (preregistered metric)\n",
        f"- ingested records: **{len(cards)}** for {len(cases)} cases "
        f"({len(cards) / len(cases):.2f} per case), vs v2's exact 1.00",
        f"- a record from the right decision reached the prompt: "
        f"**{same_dec}/{n}** ({same_dec / n:.0%})",
        f"- a record actually *naming* the asked-about alternative reached "
        f"the prompt: **{named}/{n}** ({named / n:.0%})\n",
    ]


def main() -> None:
    cases = load_cases()
    scores = grade_all(cases)

    head, rates = headline_table(cases, scores)
    errors = json.loads((V2_DIR / "api_errors.json").read_text()) \
        if (V2_DIR / "api_errors.json").exists() else []
    tiers = {}
    for c in cases:
        tiers[c["evidence_tier"]] = tiers.get(c["evidence_tier"], 0) + 1

    lines = ["# DecisionTrace falsifier v2 results\n",
             f"n = {len(cases)} cases across "
             f"{len({c['decision_id'] for c in cases})} decisions and "
             f"{len({c['repo'] for c in cases})} repos. "
             f"Evidence tiers: {tiers}.\n",
             "v2 asks one targeted question per named alternative instead of "
             "one broad question per KEP. It is **not** the same benchmark as "
             "v0 and its numbers are not directly comparable — see "
             "`BENCHMARK_V2_SPEC.md` and the methodology section below.\n"]
    lines += head
    lines.append("\n## Per-source breakdown\n")
    lines += source_table(cases, scores)
    lines.append(METHODOLOGY)
    lines.append(f"\nAPI failures recorded separately (never scored as "
                 f"correct): {len(errors)}\n")
    lines.append("\n## Per-case detail\n")
    lines += case_table(cases, scores)
    lines.append("\n(Capital = correct, lowercase = incorrect, "
                 "H = hallucinated a wrong citation.)\n")
    lines += failure_diagnostics(cases, scores)

    if V21 in rates:
        lines += extraction_recall(cases, scores)
    verdict, reason = verdict_for(rates["rag"], rates["structured"], len(cases))
    lines.append(f"\n## Verdict (v2, leaked store): {verdict}\n\n{reason}\n")
    if V21 in rates:
        v21, why = verdict_for(rates["rag"], rates[V21], len(cases))
        lines.append(f"\n## Verdict (v2.1, unsupervised store, unlabelled "
                     f"RAG): {v21}\n\n{why}\n")
        verdict = v21
    if V21 in rates and V22 in rates:
        v22, why = verdict_for(rates[V22], rates[V21], len(cases))
        lines.append(
            f"\n## Verdict (v2.2 — the headline: unsupervised store, "
            f"labelled RAG): **{v22}**\n\n{why}\n\n"
            f"This is the comparison with no thumb on either scale: the "
            f"structured store was built without ever seeing the question "
            f"list, and RAG is told the identity of every chunk it "
            f"retrieved, including the one that answers the question.\n")
        verdict = v22

    out = Path(__file__).parent / "RESULTS_V2.md"
    out.write_text("\n".join(lines))
    print(f"\nwrote {out}\nFINAL VERDICT: {verdict}")


if __name__ == "__main__":
    main()
