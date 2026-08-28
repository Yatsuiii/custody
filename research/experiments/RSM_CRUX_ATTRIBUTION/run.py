"""RSM crux falsifier: can an LLM judge counterfactual claim dependence?

Sends each of the 20 fixed fixture cases to live Gemini (Vertex AI) once,
with one fixed prompt, and scores the YES/NO judgment against
precommitted ground truth. Ground truth and prompt are both fixed before
this file makes any model call.

Run: python3 research/experiments/RSM_CRUX_ATTRIBUTION/run.py
Requires: CLOUDSDK_CONFIG pointed at a credentialed gcloud config for
project-988bc9fe-092c-4b32-90c (see README.md's live-evidence section).
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

A derived memory was created from two source facts, A and B. Later, source B is discovered to be false or is removed. Your task: would the derived memory's claim need to change as a result?

Source A: {source_a}
Source B: {source_b}
Derived memory: {derived_memory}

If source B were removed or discovered false, would the derived memory's specific claim need to change or be withdrawn? Answer with exactly one word first -- YES or NO -- then a single sentence of reasoning.

Format your answer as:
ANSWER: YES or NO
REASON: <one sentence>"""


def judge_case(client: genai.Client, case: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        source_a=case["source_a"],
        source_b=case["source_b"],
        derived_memory=case["derived_memory"],
    )
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    text = resp.text or ""
    match = re.search(r"ANSWER:\s*(YES|NO)", text, re.IGNORECASE)
    judged_yes = match is not None and match.group(1).upper() == "YES"
    return {
        "id": case["id"],
        "category": case["category"],
        "ground_truth_depends_on_b": case["depends_on_b"],
        "judged_depends_on_b": judged_yes,
        "correct": judged_yes == case["depends_on_b"],
        "raw_response": text.strip(),
    }


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    assert len(fixture) == 20, f"expected 20 cases, got {len(fixture)}"

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    per_case = [judge_case(client, case) for case in fixture]

    total = len(per_case)
    correct = sum(1 for r in per_case if r["correct"])
    true_positives = sum(1 for r in per_case if r["ground_truth_depends_on_b"] and r["judged_depends_on_b"])
    false_positives = sum(1 for r in per_case if not r["ground_truth_depends_on_b"] and r["judged_depends_on_b"])
    false_negatives = sum(1 for r in per_case if r["ground_truth_depends_on_b"] and not r["judged_depends_on_b"])
    ground_truth_positive = sum(1 for r in per_case if r["ground_truth_depends_on_b"])

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else None
    recall = true_positives / ground_truth_positive if ground_truth_positive else None

    by_category: dict[str, list[dict]] = {}
    for r in per_case:
        by_category.setdefault(r["category"], []).append(r)
    category_accuracy = {
        cat: sum(1 for r in rows if r["correct"]) / len(rows) for cat, rows in by_category.items()
    }

    adversarial_misses = [
        r["id"] for r in per_case
        if r["category"] in ("redundant", "distractor") and not r["correct"]
    ]

    result = {
        "model": MODEL,
        "project": PROJECT,
        "metrics": {
            "accuracy": correct / total,
            "correct": correct,
            "total": total,
            "precision_on_depends_true": precision,
            "recall_on_depends_true": recall,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "category_accuracy": category_accuracy,
            "adversarial_category_misses": adversarial_misses,
        },
        "per_case": per_case,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Accuracy: {m['correct']}/{m['total']} = {m['accuracy']:.2%}")
    print(f"Precision (depends=true): {m['precision_on_depends_true']}")
    print(f"Recall (depends=true): {m['recall_on_depends_true']}")
    print(f"False positives: {m['false_positives']}, False negatives: {m['false_negatives']}")
    print(f"Category accuracy: {json.dumps(m['category_accuracy'], indent=2)}")
    print(f"Adversarial (redundant/distractor) misses: {m['adversarial_category_misses']}")
