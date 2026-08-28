"""RSM crux7: pool identification -- given a revoked source and a pool of
memories (real content reused verbatim from crux5/6, plus deliberately
adversarial hand-written distractors), can the model find only the ones
that actually depend on the revoked source? Untested by every prior round,
which always gave the model exactly the relevant memory/memories.

Run: python3 research/experiments/RSM_CRUX7_POOL_IDENTIFICATION/run.py
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

IDENTIFY_PROMPT = """The following source has just been revoked: "{revoked_source}"

Below is a numbered pool of memory records from an AI agent's memory system. For each one, decide whether it actually depends on the revoked source above -- meaning its truth was established by that source, directly or through another memory that depended on it. Do not flag a memory just because it mentions the same person, place, or topic; only flag it if the revoked source is actually part of why it was believed true.

Memories:
{numbered_pool}

List the numbers of every memory that depends on the revoked source. Output only a comma-separated list of numbers (e.g. "1, 4, 7"), or "none" if none depend on it. No other text."""


def parse_flagged(raw: str, pool_size: int) -> set[int]:
    if re.search(r"\bnone\b", raw, re.IGNORECASE) and not re.search(r"\d", raw):
        return set()
    nums = {int(n) for n in re.findall(r"\d+", raw)}
    return {n for n in nums if 1 <= n <= pool_size}


def main() -> dict:
    fixture = json.loads((OUT_DIR / "fixture.json").read_text())
    pool = fixture["pool"]
    assert len(pool) == 12, f"expected 12 pool items, got {len(pool)}"

    numbered_pool = "\n".join(f"{item['num']}. {item['text']}" for item in pool)
    prompt = IDENTIFY_PROMPT.format(
        revoked_source=fixture["revoked_source_description"], numbered_pool=numbered_pool
    )

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    raw = (resp.text or "").strip()
    flagged = parse_flagged(raw, len(pool))

    true_positive_nums = {item["num"] for item in pool if item["label"] == "true_positive"}
    adversarial_nums = {item["num"] for item in pool if item["label"] == "adversarial_true_negative"}
    ordinary_negative_nums = {item["num"] for item in pool if item["label"] == "true_negative"}
    all_negative_nums = adversarial_nums | ordinary_negative_nums

    true_positives_found = flagged & true_positive_nums
    false_positives = flagged & all_negative_nums
    false_negatives = true_positive_nums - flagged
    adversarial_false_positives = flagged & adversarial_nums

    recall = len(true_positives_found) / len(true_positive_nums) if true_positive_nums else None
    precision = len(true_positives_found) / len(flagged) if flagged else None

    result = {
        "model": MODEL,
        "project": PROJECT,
        "raw_response": raw,
        "flagged": sorted(flagged),
        "true_positive_nums": sorted(true_positive_nums),
        "metrics": {
            "recall": recall,
            "precision": precision,
            "true_positives_found": sorted(true_positives_found),
            "false_negatives": sorted(false_negatives),
            "false_positives": sorted(false_positives),
            "adversarial_false_positives": sorted(adversarial_false_positives),
            "adversarial_false_positive_rate": len(adversarial_false_positives) / len(adversarial_nums)
            if adversarial_nums
            else None,
        },
        "pool": pool,
    }
    return result


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))
    m = result["metrics"]
    print(f"Raw response: {result['raw_response']}")
    print(f"Flagged: {result['flagged']}")
    print(f"True positives found: {m['true_positives_found']} (recall={m['recall']})")
    print(f"False negatives (missed): {m['false_negatives']}")
    print(f"False positives: {m['false_positives']} (precision={m['precision']})")
    print(f"Adversarial false positives: {m['adversarial_false_positives']} (rate={m['adversarial_false_positive_rate']})")
