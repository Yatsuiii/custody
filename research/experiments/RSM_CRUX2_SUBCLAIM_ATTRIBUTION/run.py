"""RSM crux2: sub-claim-level attribution -- can an LLM judge, within a
composite derived memory, which specific sub-claims survive removal of
one contributing source? Harder than RSM_CRUX_ATTRIBUTION's whole-claim
binary judgment; also re-tests the redundant-support weak spot found
there with matched explicit-vs-ambiguous phrasing pairs.

Run: python3 research/experiments/RSM_CRUX2_SUBCLAIM_ATTRIBUTION/run.py
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

PROMPT_TEMPLATE = """You are analyzing a composite derived memory in an AI agent's long-term memory system. It was built from two source facts, A and B{policy_clause}. Later, source B is discovered to be false or is removed.

Source A: {source_a}
Source B: {source_b}{policy_line}

Derived memory: {derived_memory}

This derived memory contains multiple sub-claims, listed below. For EACH numbered sub-claim, decide: if source B were removed or discovered false, would THIS SPECIFIC sub-claim need to change or be withdrawn? Some sub-claims may survive even if others don't -- judge each independently.

Sub-claims:
{numbered_claims}

Answer in exactly this format, one line per sub-claim, nothing else:
1: YES or NO
2: YES or NO
(etc, matching every numbered sub-claim above)"""


def build_prompt(case: dict) -> str:
    numbered = "\n".join(f"{i + 1}. {sc['text']}" for i, sc in enumerate(case["sub_claims"]))
    policy_clause = " and a policy context" if case.get("policy_context") else ""
    policy_line = f"\nPolicy context: {case['policy_context']}" if case.get("policy_context") else ""
    return PROMPT_TEMPLATE.format(
        policy_clause=policy_clause,
        source_a=case["source_a"],
        source_b=case["source_b"],
        policy_line=policy_line,
        derived_memory=case["derived_memory"],
        numbered_claims=numbered,
    )


def parse_answers(text: str, n: int) -> list[bool | None]:
    answers: list[bool | None] = [None] * n
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\s*[:.]\s*(YES|NO)", line.strip(), re.IGNORECASE)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < n:
                answers[idx] = m.group(2).upper() == "YES"
    return answers


def judge_case(client: genai.Client, case: dict) -> dict:
    prompt = build_prompt(case)
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    text = resp.text or ""
    judged = parse_answers(text, len(case["sub_claims"]))

    sub_results = []
    for sc, j in zip(case["sub_claims"], judged):
        sub_results.append(
            {
                "text": sc["text"],
                "ground_truth_depends_on_b": sc["depends_on_b"],
                "judged_depends_on_b": j,
                "correct": (j is not None and j == sc["depends_on_b"]),
                "unparsed": j is None,
            }
        )

    return {
        "id": case["id"],
        "category": case["category"],
        "sub_claims": sub_results,
        "raw_response": text.strip(),
    }


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    assert len(fixture) == 10, f"expected 10 cases, got {len(fixture)}"

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    per_case = [judge_case(client, case) for case in fixture]

    all_subs = [sc for c in per_case for sc in c["sub_claims"]]
    total = len(all_subs)
    correct = sum(1 for sc in all_subs if sc["correct"])
    unparsed = sum(1 for sc in all_subs if sc["unparsed"])
    true_positives = sum(1 for sc in all_subs if sc["ground_truth_depends_on_b"] and sc["judged_depends_on_b"])
    false_positives = sum(
        1 for sc in all_subs if not sc["ground_truth_depends_on_b"] and sc["judged_depends_on_b"] is True
    )
    false_negatives = sum(
        1 for sc in all_subs if sc["ground_truth_depends_on_b"] and sc["judged_depends_on_b"] is False
    )
    ground_truth_positive = sum(1 for sc in all_subs if sc["ground_truth_depends_on_b"])

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else None
    recall = true_positives / ground_truth_positive if ground_truth_positive else None

    def case_by_id(cid: str) -> dict:
        return next(c for c in per_case if c["id"] == cid)

    explicit_vs_ambiguous = {
        "vendor_cert_pair": {
            "explicit_C6": case_by_id("C6")["sub_claims"][0],
            "ambiguous_C7": case_by_id("C7")["sub_claims"][0],
        },
        "expense_approval_pair": {
            "explicit_C8": case_by_id("C8")["sub_claims"][0],
            "ambiguous_C9": case_by_id("C9")["sub_claims"][0],
        },
    }

    result = {
        "model": MODEL,
        "project": PROJECT,
        "metrics": {
            "subclaim_accuracy": correct / total,
            "correct": correct,
            "total": total,
            "unparsed": unparsed,
            "precision_on_depends_true": precision,
            "recall_on_depends_true": recall,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        },
        "explicit_vs_ambiguous_pairs": explicit_vs_ambiguous,
        "per_case": per_case,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Sub-claim accuracy: {m['correct']}/{m['total']} = {m['subclaim_accuracy']:.2%} (unparsed: {m['unparsed']})")
    print(f"Precision (depends=true): {m['precision_on_depends_true']}")
    print(f"Recall (depends=true): {m['recall_on_depends_true']}")
    print(f"False positives: {m['false_positives']}, False negatives: {m['false_negatives']}")
    print("Explicit vs ambiguous pairs:")
    print(json.dumps(result["explicit_vs_ambiguous_pairs"], indent=2))
