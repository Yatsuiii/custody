"""RSM crux4: repairing text the model actually fused itself -- the real
hard problem crux1-3 never tested. Generates the derived memory live
(not hand-templated), then asks a second independent call to repair it
given one source is revoked, and scores by literal-token presence
(precommitted, not another LLM judgment) rather than semantic equivalence.

Run: python3 research/experiments/RSM_CRUX4_FUSED_GENERATION/run.py
Requires: CLOUDSDK_CONFIG pointed at a credentialed gcloud config for
project-988bc9fe-092c-4b32-90c.
"""

from __future__ import annotations

import json
from pathlib import Path

from google import genai

OUT_DIR = Path(__file__).parent
PROJECT = "project-988bc9fe-092c-4b32-90c"
MODEL = "gemini-3.5-flash"

GENERATE_PROMPT = """Write exactly one natural sentence, as it would appear in an AI agent's long-term memory, that combines both of these facts:

Fact 1: {source_a}
Fact 2: {source_b}

Output only the single memory sentence, nothing else -- no preamble, no explanation."""

REPAIR_PROMPT = """The following is a memory record in an AI agent's long-term memory system. It was built by combining multiple source facts. One of those sources has just been discovered to be compromised/false:

Compromised source: {source_b}

Memory record: {fused_memory}

Rewrite this memory record to remove any information that came from the compromised source above, while preserving all information that did NOT come from it. If removing the compromised information leaves a gap, you may note that the information is no longer available rather than inventing a replacement. Output only the rewritten memory text, nothing else."""


def contains(text: str, marker: str) -> bool:
    return marker.lower() in text.lower()


def run_case(client: genai.Client, case: dict) -> dict:
    gen_resp = client.models.generate_content(
        model=MODEL,
        contents=GENERATE_PROMPT.format(source_a=case["source_a"], source_b=case["source_b"]),
    )
    fused_memory = (gen_resp.text or "").strip()

    a_in_fused = contains(fused_memory, case["a_marker"])
    b_in_fused = contains(fused_memory, case["b_marker"])
    fusion_valid = a_in_fused and b_in_fused

    result = {
        "id": case["id"],
        "source_a": case["source_a"],
        "source_b": case["source_b"],
        "a_marker": case["a_marker"],
        "b_marker": case["b_marker"],
        "fused_memory": fused_memory,
        "a_marker_in_fused": a_in_fused,
        "b_marker_in_fused": b_in_fused,
        "fusion_valid": fusion_valid,
    }

    if not fusion_valid:
        result.update(
            {
                "repaired_memory": None,
                "a_marker_retained": None,
                "b_marker_leaked": None,
                "case_verdict": "SKIPPED_INVALID_FUSION",
            }
        )
        return result

    repair_resp = client.models.generate_content(
        model=MODEL,
        contents=REPAIR_PROMPT.format(source_b=case["source_b"], fused_memory=fused_memory),
    )
    repaired_memory = (repair_resp.text or "").strip()

    a_retained = contains(repaired_memory, case["a_marker"])
    b_leaked = contains(repaired_memory, case["b_marker"])

    result.update(
        {
            "repaired_memory": repaired_memory,
            "a_marker_retained": a_retained,
            "b_marker_leaked": b_leaked,
            "case_verdict": "LEAK" if b_leaked else ("CLEAN" if a_retained else "OVER_DELETED"),
        }
    )
    return result


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    assert len(fixture) == 8, f"expected 8 cases, got {len(fixture)}"

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    per_case = [run_case(client, case) for case in fixture]

    valid = [c for c in per_case if c["fusion_valid"]]
    leaks = [c for c in valid if c["case_verdict"] == "LEAK"]
    clean = [c for c in valid if c["case_verdict"] == "CLEAN"]
    over_deleted = [c for c in valid if c["case_verdict"] == "OVER_DELETED"]

    result = {
        "model": MODEL,
        "project": PROJECT,
        "metrics": {
            "total_cases": len(fixture),
            "fusion_valid_cases": len(valid),
            "fusion_validity_rate": len(valid) / len(fixture),
            "leak_rate": len(leaks) / len(valid) if valid else None,
            "leaks": len(leaks),
            "clean_repairs": len(clean),
            "over_deleted": len(over_deleted),
            "leaked_case_ids": [c["id"] for c in leaks],
        },
        "per_case": per_case,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Fusion valid: {m['fusion_valid_cases']}/{m['total_cases']} = {m['fusion_validity_rate']:.1%}")
    print(f"Leak rate (of valid cases): {m['leaks']}/{m['fusion_valid_cases']} = {m['leak_rate']:.1%}" if m['leak_rate'] is not None else "Leak rate: N/A")
    print(f"Clean repairs: {m['clean_repairs']}, Over-deleted: {m['over_deleted']}")
    print(f"Leaked case ids: {m['leaked_case_ids']}")
    for c in result["per_case"]:
        print(f"\n=== {c['id']} ({c['case_verdict']}) ===")
        print(f"Fused:    {c['fused_memory']}")
        if c.get("repaired_memory"):
            print(f"Repaired: {c['repaired_memory']}")
