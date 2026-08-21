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


def grade_all(cases: list[dict]) -> dict:
    scores = json.loads(SCORES_PATH.read_text()) if SCORES_PATH.exists() else {}
    for i, c in enumerate(cases):
        cid = c["case_id"]
        for cond in CONDITIONS:
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
    for cond in CONDITIONS:
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
    for cond in CONDITIONS:
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
    lines = ["| case_id | source | code_only | rag | structured |",
             "|---|---|---|---|---|"]
    for c in cases:
        cells = []
        for cond in CONDITIONS:
            s = scores.get(f"{cond}::{c['case_id']}")
            cells.append("-" if s is None else
                         ("C" if s.get("citation_correct") else "c")
                         + ("R" if s.get("rationale_match") else "r")
                         + ("H" if s.get("hallucinated_citation") else ""))
        lines.append(f"| `{c['case_id'][:78]}` | {c['source']} | "
                     f"{cells[0]} | {cells[1]} | {cells[2]} |")
    return lines


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
    lines.append(f"\nAPI failures recorded separately (never scored as "
                 f"correct): {len(errors)}\n")
    lines.append("\n## Per-case detail\n")
    lines += case_table(cases, scores)
    lines.append("\n(Capital = correct, lowercase = incorrect, "
                 "H = hallucinated a wrong citation.)\n")

    verdict, reason = verdict_for(rates["rag"], rates["structured"], len(cases))
    lines.append(f"\n## Verdict: {verdict}\n\n{reason}\n")

    out = Path(__file__).parent / "RESULTS_V2.md"
    out.write_text("\n".join(lines))
    print(f"\nwrote {out}\nVERDICT: {verdict}\n{reason}")


if __name__ == "__main__":
    main()
