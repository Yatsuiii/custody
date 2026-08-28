"""RSM crux9: does cascading repair correctly stop at redundant support?
Combines crux3's finding (redundant support survives) with crux6's finding
(cascading repair can propagate two hops) into one prompt that has to get
both right in the same pass: M1 retracts, M2a (pure cascade) retracts,
M2b (redundant support from an independent fact) survives.

Run: python3 research/experiments/RSM_CRUX9_REDUNDANT_CASCADE/run.py
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

REPAIR_PROMPT = """A source has just been revoked:

{revoked_source}

Here is an independent fact that was NOT affected by this revocation, and was never derived from the revoked source:

{independent_fact_c}

Below are three memory records from an AI agent's memory system, each with a note on what it was derived from. For each one, decide whether it should be RETRACTED (its conclusion no longer holds without the revoked source) or SURVIVE (its conclusion still holds, because it has independent support that does not depend on the revoked source).

1. {m1_text}
   [derived from: {m1_support}]

2. {m2a_text}
   [derived from: {m2a_support}]

3. {m2b_text}
   [derived from: {m2b_support}]

For each of the three memories, answer RETRACT or SURVIVE, with a one-sentence reason. Format exactly as:
1: RETRACT|SURVIVE - reason
2: RETRACT|SURVIVE - reason
3: RETRACT|SURVIVE - reason"""


def parse_verdicts(raw: str) -> dict[str, str]:
    verdicts = {}
    for line in raw.splitlines():
        m = re.match(r"\s*([123])\s*:\s*(RETRACT|SURVIVE)", line, re.IGNORECASE)
        if m:
            verdicts[m.group(1)] = m.group(2).upper()
    return verdicts


def run_domain(client: genai.Client, domain: dict) -> dict:
    mem = domain["memories"]
    prompt = REPAIR_PROMPT.format(
        revoked_source=domain["revoked_source"],
        independent_fact_c=domain["independent_fact_c"],
        m1_text=mem["m1"]["text"],
        m1_support=mem["m1"]["support"],
        m2a_text=mem["m2a"]["text"],
        m2a_support=mem["m2a"]["support"],
        m2b_text=mem["m2b"]["text"],
        m2b_support=mem["m2b"]["support"],
    )
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    raw = (resp.text or "").strip()
    verdicts = parse_verdicts(raw)

    expected = {"1": mem["m1"]["expected"].upper(), "2": mem["m2a"]["expected"].upper(), "3": mem["m2b"]["expected"].upper()}
    correct = {k: verdicts.get(k) == expected[k] for k in expected}

    return {
        "domain": domain["name"],
        "raw_response": raw,
        "verdicts": verdicts,
        "expected": expected,
        "correct": correct,
        "all_correct": all(correct.values()),
    }


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    client = genai.Client(vertexai=True, project=PROJECT, location="global")

    results = [run_domain(client, domain) for domain in fixture["domains"]]

    total_judgments = sum(len(r["correct"]) for r in results)
    total_correct = sum(sum(r["correct"].values()) for r in results)
    domains_fully_correct = sum(1 for r in results if r["all_correct"])

    return {
        "model": MODEL,
        "project": PROJECT,
        "domains": results,
        "summary": {
            "total_judgments": total_judgments,
            "total_correct": total_correct,
            "accuracy": total_correct / total_judgments,
            "domains_fully_correct": domains_fully_correct,
            "domains_total": len(results),
        },
    }


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))

    for r in result["domains"]:
        print(f"\n=== {r['domain']} ===")
        print(f"Raw: {r['raw_response']}")
        print(f"Expected: {r['expected']}  Got: {r['verdicts']}  Correct: {r['correct']}")

    s = result["summary"]
    print("\n=== SUMMARY ===")
    print(f"Accuracy: {s['total_correct']}/{s['total_judgments']} ({s['accuracy']:.2%})")
    print(f"Domains fully correct: {s['domains_fully_correct']}/{s['domains_total']}")
