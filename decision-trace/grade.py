"""Grades the three conditions' responses against ground truth.

An LLM-judge pass (Gemini, separate call from the conditions themselves)
scores each response on:
  - citation_correct: does it cite the right PR/issue number(s) or file path?
  - rationale_match: does the stated reason semantically match rationale_quote?
  - hallucinated_citation: does it cite a plausible-sounding but WRONG number?
  - supersession_aware: for revert-pair decisions only, does it correctly
    note the decision was later reverted?

Writes decision-trace/RESULTS.md with a scored table and the GO/KILL/CAUTION
verdict from SESSION_CONTRACT.md's thresholds.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import vertex

DATA_DIR = Path(__file__).parent / "data"
RUNS_DIR = DATA_DIR / "runs"
CONDITIONS = ["code_only", "rag", "structured"]

JUDGE_PROMPT = """You are grading whether an AI assistant's answer correctly \
recalled a specific real engineering decision.

GROUND TRUTH
Decision: {chosen}
Correct citation: {citation_str}
Correct rationale (verbatim from the source): {rationale_quote}
Was this decision later superseded/reverted? {superseded_str}

ASSISTANT'S ANSWER
{response}

Score the assistant's answer on exactly these four fields, as strict JSON \
with no other text:
{{
  "citation_correct": true/false,   // cites the correct PR/issue number(s) or file path from the ground truth citation, not just any number
  "rationale_match": true/false,    // states a reason that semantically matches the correct rationale above (paraphrase is fine, wrong reason is not)
  "hallucinated_citation": true/false, // cites a DIFFERENT specific PR/issue number as if it were the relevant one, when it is not the correct citation
  "supersession_aware": true/false/null // null if not applicable (ground truth not superseded); true only if ground truth WAS superseded AND the answer correctly says so
}}"""


def citation_str(d: dict) -> str:
    c = d["citation"]
    if "original_pr" in c:
        return f"PR #{c['original_pr']['number']} (reverted by PR #{c['revert_pr']['number']})"
    return c["file"]["path"]


def judge_one(d: dict, response: str) -> dict:
    superseded = d.get("superseded_by") is not None
    prompt = JUDGE_PROMPT.format(
        chosen=d["chosen"],
        citation_str=citation_str(d),
        rationale_quote=d["rationale_quote"],
        superseded_str="Yes" if superseded else "No",
        response=response,
    )
    raw = vertex.generate(prompt)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"citation_correct": False, "rationale_match": False,
                 "hallucinated_citation": False, "supersession_aware": None,
                 "judge_error": raw[:200]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"citation_correct": False, "rationale_match": False,
                 "hallucinated_citation": False, "supersession_aware": None,
                 "judge_error": raw[:200]}


def grade_all(decisions: dict[str, dict]) -> tuple[dict, list]:
    all_scores: dict[str, list[dict]] = {c: [] for c in CONDITIONS}
    per_decision_rows = []
    for did, d in decisions.items():
        row = {"decision_id": did, "repo": d["repo"]}
        for cond in CONDITIONS:
            print(f"grading {did} / {cond}...", end=" ", flush=True)
            run_path = RUNS_DIR / cond / f"{did}.json"
            if not run_path.exists():
                print("skip (no run)")
                continue
            run = json.loads(run_path.read_text())
            score = judge_one(d, run["response"])
            score["decision_id"] = did
            all_scores[cond].append(score)
            row[cond] = score
            print("ok")
        per_decision_rows.append(row)
    return all_scores, per_decision_rows


def verdict_for(rag_combined: float, struct_combined: float, n: int) -> tuple[str, str]:
    if rag_combined >= 0.90:
        return "KILL", (
            f"Embedding RAG reached {rag_combined:.0%} on the combined "
            f"citation+rationale metric (>= 90% threshold). Structured "
            f"memory isn't earning its complexity at this scale. Fall "
            f"back to Accommodation Compiler.")
    if rag_combined <= 0.70 and struct_combined >= 0.85:
        return "GO", (
            f"RAG reached only {rag_combined:.0%} (<=70%) while "
            f"structured memory reached {struct_combined:.0%} (>=85%). "
            f"Structured decision memory materially beats naive RAG. "
            f"Build DecisionTrace.")
    return "CAUTION", (
        f"RAG={rag_combined:.0%}, structured={struct_combined:.0%} — "
        f"doesn't cleanly clear either threshold at n={n}. "
        f"Inconclusive; widen the sample or inspect per-decision "
        f"detail above before deciding.")


def main() -> None:
    decisions = {d["decision_id"]: d for d in
                 (json.loads(line) for line in (DATA_DIR / "decisions.jsonl").open())}

    all_scores, per_decision_rows = grade_all(decisions)

    def rate(cond: str, field: str) -> tuple[float, int, int]:
        vals = [s[field] for s in all_scores[cond] if s.get(field) is not None]
        n = len(vals)
        return (sum(vals) / n if n else 0.0, sum(vals), n)

    lines = ["# DecisionTrace v0 falsifier results\n"]
    lines.append(f"n = {len(decisions)} decisions across "
                  f"{len({d['repo'] for d in decisions.values()})} repos.\n")
    lines.append("| Condition | Citation-correct | Rationale-match | "
                  "Combined (both) | Hallucination rate | Supersession-aware |")
    lines.append("|---|---|---|---|---|---|")

    combined_rates = {}
    for cond in CONDITIONS:
        cc_rate, cc_n, cc_d = rate(cond, "citation_correct")
        rm_rate, rm_n, rm_d = rate(cond, "rationale_match")
        combined = sum(
            1 for s in all_scores[cond]
            if s.get("citation_correct") and s.get("rationale_match")
        ) / max(len(all_scores[cond]), 1)
        combined_rates[cond] = combined
        hall_rate, _, _ = rate(cond, "hallucinated_citation")
        sup_rate, sup_n, sup_d = rate(cond, "supersession_aware")
        lines.append(
            f"| {cond} | {cc_rate:.0%} ({cc_n}/{cc_d}) | {rm_rate:.0%} ({rm_n}/{rm_d}) "
            f"| {combined:.0%} | {hall_rate:.0%} | "
            f"{sup_rate:.0%} ({sup_n}/{sup_d})" + " |"
        )

    lines.append("\n## Threats to validity\n")
    lines.append(
        "- **Citation-correctness is satisfied by construction for the "
        "structured arm.** Every retrieved card carries its own citation "
        "field (`Evidence: PR #N` / file path) inline, so a model that "
        "answers from a retrieved card at all is very likely to cite "
        "correctly — this measures whether retrieval found the right "
        "card, not independent recall of the citation.\n"
    )
    n_kep = sum(1 for d in decisions.values() if d["source"] == "kep_alternatives")
    n_revert = sum(1 for d in decisions.values() if d["source"] == "revert_pair")
    lines.append(
        f"- **{n_kep} of {len(decisions)} decisions ({n_kep / len(decisions):.0%}) "
        f"come from kubernetes/enhancements KEPs** (source `kep_alternatives`); "
        f"the remaining {n_revert} are revert-PR pairs across three repos. "
        f"The headline numbers are weighted toward KEP-shaped sources — see "
        f"the per-source breakdown below.\n"
    )

    lines.append("\n## Per-source breakdown\n")
    lines.append("| Condition | Source | Citation-correct | Rationale-match | Combined |")
    lines.append("|---|---|---|---|---|")
    for cond in CONDITIONS:
        for source in ("revert_pair", "kep_alternatives"):
            source_ids = {did for did, d in decisions.items() if d["source"] == source}
            scores = [s for s in all_scores[cond] if s["decision_id"] in source_ids]
            if not scores:
                continue
            cc = sum(1 for s in scores if s.get("citation_correct")) / len(scores)
            rm = sum(1 for s in scores if s.get("rationale_match")) / len(scores)
            comb = sum(
                1 for s in scores
                if s.get("citation_correct") and s.get("rationale_match")
            ) / len(scores)
            lines.append(
                f"| {cond} | {source} | {cc:.0%} | {rm:.0%} | {comb:.0%} "
                f"(n={len(scores)}) |"
            )

    lines.append("\n## Per-decision detail\n")
    lines.append("| decision_id | repo | code_only | rag | structured |")
    lines.append("|---|---|---|---|---|")
    for row in per_decision_rows:
        def fmt(cond):
            s = row.get(cond)
            if not s:
                return "-"
            return ("C" if s.get("citation_correct") else "c") + \
                   ("R" if s.get("rationale_match") else "r") + \
                   ("H" if s.get("hallucinated_citation") else "")
        lines.append(f"| {row['decision_id']} | {row['repo']} | "
                      f"{fmt('code_only')} | {fmt('rag')} | {fmt('structured')} |")
    lines.append("\n(Capital = correct/true, lowercase = incorrect/false, "
                  "H = hallucinated a wrong citation.)\n")

    verdict, reason = verdict_for(
        combined_rates.get("rag", 0.0), combined_rates.get("structured", 0.0),
        len(decisions),
    )
    lines.append(f"\n## Verdict: {verdict}\n\n{reason}\n")

    out = Path(__file__).parent / "RESULTS.md"
    out.write_text("\n".join(lines))
    print(f"\nwrote {out}")
    print(f"VERDICT: {verdict}")
    print(reason)


if __name__ == "__main__":
    main()
