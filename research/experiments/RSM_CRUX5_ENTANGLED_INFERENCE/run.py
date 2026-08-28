"""RSM crux5: entangled inference -- does a repair correctly retract a
CONCLUSION that depended on a now-revoked value, rather than leaving a
literal token behind (crux4's easier case). Uses a third, independent
classifier call to score confident-assertion vs. withdrawn/hedged, since
the repaired wording varies and can't be substring-matched. That scoring
call is a real methodological limitation, named in PLAN.md, not hidden.

Run: python3 research/experiments/RSM_CRUX5_ENTANGLED_INFERENCE/run.py
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

GENERATE_PROMPT = """Rule: {rule}
Current information: {value_at_write_time}

Based on the rule and the current information above, write exactly one sentence stating the conclusion that follows -- state it as a settled fact, the way an AI agent would record it in memory. Output only that one sentence, nothing else."""

REPAIR_PROMPT = """The following is a memory record in an AI agent's memory system, stating a conclusion:

Memory record: {fused_memory}

{revocation_notice}

Rewrite the memory record to correctly reflect that this specific information is no longer trusted. If the conclusion can no longer be confidently asserted without that information, say so explicitly rather than repeating the original conclusion as settled fact. Output only the rewritten memory text, nothing else."""

CLASSIFY_PROMPT = """Text: {text}

Does this text assert, as an established and settled fact, that the following is true: "{conclusion}"?

Answer YES only if it is asserted confidently, without hedging, qualification, or expressed uncertainty. Answer NO if the claim is absent, explicitly hedged, marked as no longer confirmed/unknown/uncertain, or contradicted.

Format your answer as:
ANSWER: YES or NO
REASON: <one sentence>"""


def classify(client: genai.Client, text: str, conclusion: str) -> tuple[bool, str]:
    resp = client.models.generate_content(
        model=MODEL, contents=CLASSIFY_PROMPT.format(text=text, conclusion=conclusion)
    )
    raw = (resp.text or "").strip()
    match = re.search(r"ANSWER:\s*(YES|NO)", raw, re.IGNORECASE)
    asserted = match is not None and match.group(1).upper() == "YES"
    return asserted, raw


def run_case(client: genai.Client, case: dict) -> dict:
    gen_resp = client.models.generate_content(
        model=MODEL,
        contents=GENERATE_PROMPT.format(rule=case["rule"], value_at_write_time=case["value_at_write_time"]),
    )
    fused_memory = (gen_resp.text or "").strip()

    fused_asserts, fused_classification_raw = classify(client, fused_memory, case["conclusion_phrase"])

    result = {
        "id": case["id"],
        "rule": case["rule"],
        "value_at_write_time": case["value_at_write_time"],
        "revocation_notice": case["revocation_notice"],
        "conclusion_phrase": case["conclusion_phrase"],
        "fused_memory": fused_memory,
        "fused_asserts_conclusion": fused_asserts,
        "fused_classification_raw": fused_classification_raw,
    }

    if not fused_asserts:
        result.update(
            {
                "repaired_memory": None,
                "repaired_asserts_conclusion": None,
                "case_verdict": "SKIPPED_INVALID_GENERATION",
            }
        )
        return result

    repair_resp = client.models.generate_content(
        model=MODEL,
        contents=REPAIR_PROMPT.format(fused_memory=fused_memory, revocation_notice=case["revocation_notice"]),
    )
    repaired_memory = (repair_resp.text or "").strip()

    repaired_asserts, repaired_classification_raw = classify(client, repaired_memory, case["conclusion_phrase"])

    result.update(
        {
            "repaired_memory": repaired_memory,
            "repaired_asserts_conclusion": repaired_asserts,
            "repaired_classification_raw": repaired_classification_raw,
            "case_verdict": "LEAK" if repaired_asserts else "CLEAN",
        }
    )
    return result


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    assert len(fixture) == 6, f"expected 6 cases, got {len(fixture)}"

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    per_case = [run_case(client, case) for case in fixture]

    valid = [c for c in per_case if c["fused_asserts_conclusion"]]
    leaks = [c for c in valid if c["case_verdict"] == "LEAK"]
    clean = [c for c in valid if c["case_verdict"] == "CLEAN"]

    result = {
        "model": MODEL,
        "project": PROJECT,
        "metrics": {
            "total_cases": len(fixture),
            "generation_valid_cases": len(valid),
            "leak_rate": len(leaks) / len(valid) if valid else None,
            "leaks": len(leaks),
            "clean_repairs": len(clean),
            "leaked_case_ids": [c["id"] for c in leaks],
        },
        "per_case": per_case,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Generation valid: {m['generation_valid_cases']}/{m['total_cases']}")
    print(f"Leak rate: {m['leaks']}/{m['generation_valid_cases']} = {m['leak_rate']:.1%}" if m["leak_rate"] is not None else "Leak rate: N/A")
    print(f"Leaked case ids: {m['leaked_case_ids']}")
    for c in result["per_case"]:
        print(f"\n=== {c['id']} ({c['case_verdict']}) ===")
        print(f"Fused:    {c['fused_memory']}")
        if c.get("repaired_memory"):
            print(f"Repaired: {c['repaired_memory']}")
