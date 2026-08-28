"""RSM crux6: cascading repair -- does correct retraction of M1 propagate
to a downstream M2 that only knows M1's (corrected) text, never the
original root cause? This is the multi-hop case none of crux1-5 tested,
and the one closest to Custody's actual derivation-graph architecture.

Run: python3 research/experiments/RSM_CRUX6_CASCADING_REPAIR/run.py
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

GENERATE_M1_PROMPT = """Rule: {rule}
Current information: {value_at_write_time}

Based on the rule and the current information above, write exactly one sentence stating the conclusion that follows -- state it as a settled fact, the way an AI agent would record it in memory. Output only that one sentence, nothing else."""

REPAIR_M1_PROMPT = """The following is a memory record in an AI agent's memory system, stating a conclusion:

Memory record: {m1}

{revocation_notice}

Rewrite the memory record to correctly reflect that this specific information is no longer trusted. If the conclusion can no longer be confidently asserted without that information, say so explicitly rather than repeating the original conclusion as settled fact. Output only the rewritten memory text, nothing else."""

REPAIR_M2_PROMPT = """The following is a memory record in an AI agent's memory system:

Memory record: {m2}

This memory was based on a fact recorded by another department, which has just been revised as follows: "{repaired_m1}"

Rewrite the memory record to correctly reflect that the upstream fact it depended on is no longer settled. If the memory's claim can no longer be confidently asserted given the revision above, say so explicitly rather than repeating the original claim as settled fact. Output only the rewritten memory text, nothing else."""

CLASSIFY_ASSERTION_PROMPT = """Text: {text}

Does this text assert, as an established and settled fact, that the following is true: "{conclusion}"?

Answer YES only if it is asserted confidently, without hedging, qualification, or expressed uncertainty. Answer NO if the claim is absent, explicitly hedged, marked as no longer confirmed/unknown/uncertain, or contradicted.

Format your answer as:
ANSWER: YES or NO
REASON: <one sentence>"""

CLASSIFY_ACTION_PROMPT = """Text: {text}

Does this text describe an action that was confidently taken by {role}, presented as settled without any hedging, qualification, or expressed uncertainty about whether it was justified?

Answer YES if the action is described as confidently taken/settled. Answer NO if the text instead says the action can no longer be confidently taken, is being reconsidered, is paused, or is explicitly uncertain because of a revised upstream fact.

Format your answer as:
ANSWER: YES or NO
REASON: <one sentence>"""


def classify(client: genai.Client, prompt: str) -> tuple[bool, str]:
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    raw = (resp.text or "").strip()
    match = re.search(r"ANSWER:\s*(YES|NO)", raw, re.IGNORECASE)
    asserted = match is not None and match.group(1).upper() == "YES"
    return asserted, raw


def run_case(client: genai.Client, case: dict) -> dict:
    m1_resp = client.models.generate_content(
        model=MODEL,
        contents=GENERATE_M1_PROMPT.format(rule=case["rule"], value_at_write_time=case["value_at_write_time"]),
    )
    m1 = (m1_resp.text or "").strip()
    m1_asserts, m1_raw = classify(
        client, CLASSIFY_ASSERTION_PROMPT.format(text=m1, conclusion=case["conclusion_phrase"])
    )

    m2_resp = client.models.generate_content(model=MODEL, contents=case["downstream_prompt"].format(m1=m1))
    m2 = (m2_resp.text or "").strip()
    m2_asserts, m2_raw = classify(
        client, CLASSIFY_ACTION_PROMPT.format(text=m2, role=case["downstream_role"])
    )

    result = {
        "id": case["id"],
        "m1": m1,
        "m1_asserts": m1_asserts,
        "m2": m2,
        "m2_asserts": m2_asserts,
    }

    if not (m1_asserts and m2_asserts):
        result["case_verdict"] = "SKIPPED_INVALID_GENERATION"
        return result

    m1_repair_resp = client.models.generate_content(
        model=MODEL,
        contents=REPAIR_M1_PROMPT.format(m1=m1, revocation_notice=case["revocation_notice"]),
    )
    repaired_m1 = (m1_repair_resp.text or "").strip()
    repaired_m1_asserts, repaired_m1_raw = classify(
        client, CLASSIFY_ASSERTION_PROMPT.format(text=repaired_m1, conclusion=case["conclusion_phrase"])
    )

    m2_repair_resp = client.models.generate_content(
        model=MODEL, contents=REPAIR_M2_PROMPT.format(m2=m2, repaired_m1=repaired_m1)
    )
    repaired_m2 = (m2_repair_resp.text or "").strip()
    repaired_m2_asserts, repaired_m2_raw = classify(
        client, CLASSIFY_ACTION_PROMPT.format(text=repaired_m2, role=case["downstream_role"])
    )

    hop1_verdict = "LEAK" if repaired_m1_asserts else "CLEAN"
    hop2_verdict = "LEAK" if repaired_m2_asserts else "CLEAN"

    result.update(
        {
            "repaired_m1": repaired_m1,
            "repaired_m1_asserts": repaired_m1_asserts,
            "repaired_m1_classification_raw": repaired_m1_raw,
            "repaired_m2": repaired_m2,
            "repaired_m2_asserts": repaired_m2_asserts,
            "repaired_m2_classification_raw": repaired_m2_raw,
            "hop1_verdict": hop1_verdict,
            "hop2_verdict": hop2_verdict,
            "cascade_failure": hop1_verdict == "CLEAN" and hop2_verdict == "LEAK",
            "case_verdict": f"hop1={hop1_verdict},hop2={hop2_verdict}",
        }
    )
    return result


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    assert len(fixture) == 5, f"expected 5 cases, got {len(fixture)}"

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    per_case = [run_case(client, case) for case in fixture]

    valid = [c for c in per_case if c["case_verdict"] != "SKIPPED_INVALID_GENERATION"]
    hop1_leaks = [c for c in valid if c["hop1_verdict"] == "LEAK"]
    hop2_leaks = [c for c in valid if c["hop2_verdict"] == "LEAK"]
    cascade_failures = [c for c in valid if c["cascade_failure"]]

    result = {
        "model": MODEL,
        "project": PROJECT,
        "metrics": {
            "total_cases": len(fixture),
            "valid_cases": len(valid),
            "hop1_leak_rate": len(hop1_leaks) / len(valid) if valid else None,
            "hop2_leak_rate": len(hop2_leaks) / len(valid) if valid else None,
            "hop1_leaks": len(hop1_leaks),
            "hop2_leaks": len(hop2_leaks),
            "cascade_failures": len(cascade_failures),
            "cascade_failure_ids": [c["id"] for c in cascade_failures],
        },
        "per_case": per_case,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Valid: {m['valid_cases']}/{m['total_cases']}")
    print(f"Hop-1 leak rate: {m['hop1_leaks']}/{m['valid_cases']}" if m["valid_cases"] else "N/A")
    print(f"Hop-2 leak rate: {m['hop2_leaks']}/{m['valid_cases']}" if m["valid_cases"] else "N/A")
    print(f"Cascade failures (hop1 clean, hop2 leaked): {m['cascade_failures']} {m['cascade_failure_ids']}")
    for c in result["per_case"]:
        print(f"\n=== {c['id']} ({c['case_verdict']}) ===")
        print(f"M1:            {c['m1']}")
        print(f"M2 ({c.get('id','')}): {c['m2']}")
        if c.get("repaired_m1"):
            print(f"Repaired M1:   {c['repaired_m1']}")
            print(f"Repaired M2:   {c['repaired_m2']}")
