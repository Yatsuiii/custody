"""RSM crux3: redundant support, isolated and properly controlled. Every
case is genuinely redundant by construction (depends_on_b = false in
all 16); this measures the false-positive rate specifically, with the
confound crux2 found (sufficiency rule bundled inside the removable
source) fixed for every case, and n=8 per arm instead of n=1.

Run: python3 research/experiments/RSM_CRUX3_REDUNDANT_ISOLATED/run.py
Requires: CLOUDSDK_CONFIG pointed at a credentialed gcloud config for
project-988bc9fe-092c-4b32-90c.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from google import genai

OUT_DIR = Path(__file__).parent
PROJECT = "project-988bc9fe-092c-4b32-90c"
MODEL = "gemini-3.5-flash"

PROMPT_TEMPLATE = """You are analyzing a memory record in an AI agent's long-term memory system.

A derived memory was created from two independent source facts, A and B.{policy_line} Later, source B is discovered to be false or is removed.

Source A: {source_a}
Source B: {source_b}
Derived memory: {derived_memory}

If source B were removed or discovered false, would the derived memory's claim need to change or be withdrawn? Answer with exactly one word first -- YES or NO -- then a single sentence of reasoning.

Format your answer as:
ANSWER: YES or NO
REASON: <one sentence>"""


def build_prompt(case: dict) -> str:
    policy_line = f"\n\nRelevant policy: {case['policy_context']}" if case.get("policy_context") else ""
    return PROMPT_TEMPLATE.format(
        policy_line=policy_line,
        source_a=case["source_a"],
        source_b=case["source_b"],
        derived_memory=case["derived_memory"],
    )


def judge_case(client: genai.Client, case: dict) -> dict:
    prompt = build_prompt(case)
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    text = resp.text or ""
    match = re.search(r"ANSWER:\s*(YES|NO)", text, re.IGNORECASE)
    judged_yes = match is not None and match.group(1).upper() == "YES"
    return {
        "id": case["id"],
        "domain": case["domain"],
        "variant": case["variant"],
        "ground_truth_depends_on_b": case["depends_on_b"],
        "judged_depends_on_b": judged_yes,
        "correct": judged_yes == case["depends_on_b"],
        "raw_response": text.strip(),
    }


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    assert len(fixture) == 16, f"expected 16 cases, got {len(fixture)}"

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    per_case = [judge_case(client, case) for case in fixture]

    explicit = [r for r in per_case if r["variant"] == "explicit"]
    ambiguous = [r for r in per_case if r["variant"] == "ambiguous"]

    explicit_fp = sum(1 for r in explicit if r["judged_depends_on_b"])
    ambiguous_fp = sum(1 for r in ambiguous if r["judged_depends_on_b"])

    by_domain = {}
    for domain in sorted({c["domain"] for c in fixture}):
        exp = next(r for r in per_case if r["domain"] == domain and r["variant"] == "explicit")
        amb = next(r for r in per_case if r["domain"] == domain and r["variant"] == "ambiguous")
        by_domain[domain] = {
            "explicit_correct": exp["correct"],
            "ambiguous_correct": amb["correct"],
            "agree_with_hypothesis": exp["correct"] and not amb["correct"],
        }

    hypothesis_confirming_domains = sum(1 for v in by_domain.values() if v["agree_with_hypothesis"])

    result = {
        "model": MODEL,
        "project": PROJECT,
        "metrics": {
            "explicit_false_positive_rate": explicit_fp / len(explicit),
            "explicit_false_positives": explicit_fp,
            "explicit_n": len(explicit),
            "ambiguous_false_positive_rate": ambiguous_fp / len(ambiguous),
            "ambiguous_false_positives": ambiguous_fp,
            "ambiguous_n": len(ambiguous),
            "overall_accuracy": sum(1 for r in per_case if r["correct"]) / len(per_case),
            "domains_matching_hypothesis": hypothesis_confirming_domains,
            "domains_total": len(by_domain),
        },
        "by_domain": by_domain,
        "per_case": per_case,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Explicit false-positive rate: {m['explicit_false_positives']}/{m['explicit_n']} = {m['explicit_false_positive_rate']:.1%}")
    print(f"Ambiguous false-positive rate: {m['ambiguous_false_positives']}/{m['ambiguous_n']} = {m['ambiguous_false_positive_rate']:.1%}")
    print(f"Overall accuracy: {m['overall_accuracy']:.1%}")
    print(f"Domains matching hypothesis (explicit correct, ambiguous wrong): {m['domains_matching_hypothesis']}/{m['domains_total']}")
    print(json.dumps(result["by_domain"], indent=2))
