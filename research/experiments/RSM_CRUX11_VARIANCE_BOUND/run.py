"""RSM crux11: repeat clean crux5 and crux9 probes to measure variance.

The fixture fixes both source rounds, their ground truth, and five
repetitions before any model call. Prompt text and parsing intentionally
match the source harnesses. Every raw response or call error is retained
in result.json; no post-hoc relabeling or retry is performed.

Run: python3 research/experiments/RSM_CRUX11_VARIANCE_BOUND/run.py
Requires: CLOUDSDK_CONFIG pointed at a credentialed gcloud config for
project-988bc9fe-092c-4b32-90c.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from statistics import pvariance, pstdev

from google import genai

OUT_DIR = Path(__file__).parent
FIXTURE_PATH = OUT_DIR / "fixture.json"
PROJECT = "project-988bc9fe-092c-4b32-90c"
MODEL = "gemini-3.5-flash"

ROUND5_GENERATE_PROMPT = """Rule: {rule}
Current information: {value_at_write_time}

Based on the rule and the current information above, write exactly one sentence stating the conclusion that follows -- state it as a settled fact, the way an AI agent would record it in memory. Output only that one sentence, nothing else."""

ROUND5_REPAIR_PROMPT = """The following is a memory record in an AI agent's memory system, stating a conclusion:

Memory record: {fused_memory}

{revocation_notice}

Rewrite the memory record to correctly reflect that this specific information is no longer trusted. If the conclusion can no longer be confidently asserted without that information, say so explicitly rather than repeating the original conclusion as settled fact. Output only the rewritten memory text, nothing else."""

ROUND5_CLASSIFY_PROMPT = """Text: {text}

Does this text assert, as an established and settled fact, that the following is true: "{conclusion}"?

Answer YES only if it is asserted confidently, without hedging, qualification, or expressed uncertainty. Answer NO if the claim is absent, explicitly hedged, marked as no longer confirmed/unknown/uncertain, or contradicted.

Format your answer as:
ANSWER: YES or NO
REASON: <one sentence>"""

ROUND9_REPAIR_PROMPT = """A source has just been revoked:

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


def call_model(client: genai.Client, prompt: str, ledger: dict[str, int]) -> tuple[str, str | None]:
    ledger["model_calls"] += 1
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
    except Exception as exc:  # noqa: BLE001 - preserve an honest per-call failure artifact.
        return "", f"{type(exc).__name__}: {exc}"
    return (response.text or "").strip(), None


def classify(
    client: genai.Client, text: str, conclusion: str, ledger: dict[str, int]
) -> tuple[bool | None, str, str | None]:
    raw, error = call_model(
        client,
        ROUND5_CLASSIFY_PROMPT.format(text=text, conclusion=conclusion),
        ledger,
    )
    if error:
        return None, raw, error
    match = re.search(r"ANSWER:\s*(YES|NO)", raw, re.IGNORECASE)
    if match is None:
        return None, raw, "MISSING_OR_MALFORMED_ANSWER"
    return match.group(1).upper() == "YES", raw, None


def run_round5_case(
    client: genai.Client, case: dict, repetition: int, ledger: dict[str, int]
) -> dict:
    fused_memory, generation_error = call_model(
        client,
        ROUND5_GENERATE_PROMPT.format(
            rule=case["rule"], value_at_write_time=case["value_at_write_time"]
        ),
        ledger,
    )
    result = {
        "repetition": repetition,
        "id": case["id"],
        "rule": case["rule"],
        "value_at_write_time": case["value_at_write_time"],
        "revocation_notice": case["revocation_notice"],
        "conclusion_phrase": case["conclusion_phrase"],
        "expected_fused_asserts_conclusion": case["expected_fused_asserts_conclusion"],
        "expected_repaired_asserts_conclusion": case["expected_repaired_asserts_conclusion"],
        "expected_case_verdict": case["expected_case_verdict"],
        "fused_memory": fused_memory,
        "generation_error": generation_error,
    }
    if generation_error:
        result.update(
            {
                "fused_asserts_conclusion": None,
                "fused_classification_raw": "",
                "fused_classification_error": generation_error,
                "repaired_memory": None,
                "repaired_asserts_conclusion": None,
                "repaired_classification_raw": "",
                "repaired_classification_error": None,
                "case_verdict": "ERROR_GENERATION",
            }
        )
        return result

    fused_asserts, fused_raw, fused_error = classify(
        client, fused_memory, case["conclusion_phrase"], ledger
    )
    result.update(
        {
            "fused_asserts_conclusion": fused_asserts,
            "fused_classification_raw": fused_raw,
            "fused_classification_error": fused_error,
        }
    )
    if fused_asserts is not True:
        result.update(
            {
                "repaired_memory": None,
                "repaired_asserts_conclusion": None,
                "repaired_classification_raw": "",
                "repaired_classification_error": None,
                "case_verdict": "SKIPPED_INVALID_GENERATION"
                if fused_error is None
                else "ERROR_GENERATION_CLASSIFICATION",
            }
        )
        return result

    repaired_memory, repair_error = call_model(
        client,
        ROUND5_REPAIR_PROMPT.format(
            fused_memory=fused_memory, revocation_notice=case["revocation_notice"]
        ),
        ledger,
    )
    if repair_error:
        result.update(
            {
                "repaired_memory": repaired_memory,
                "repaired_asserts_conclusion": None,
                "repaired_classification_raw": "",
                "repaired_classification_error": repair_error,
                "case_verdict": "ERROR_REPAIR",
            }
        )
        return result

    repaired_asserts, repaired_raw, repaired_error = classify(
        client, repaired_memory, case["conclusion_phrase"], ledger
    )
    result.update(
        {
            "repaired_memory": repaired_memory,
            "repaired_asserts_conclusion": repaired_asserts,
            "repaired_classification_raw": repaired_raw,
            "repaired_classification_error": repaired_error,
            "case_verdict": "CLEAN"
            if repaired_asserts is False
            else "LEAK"
            if repaired_asserts is True
            else "ERROR_REPAIR_CLASSIFICATION",
        }
    )
    return result


def parse_verdicts(raw: str) -> dict[str, str]:
    verdicts = {}
    for line in raw.splitlines():
        match = re.match(r"\s*([123])\s*:\s*(RETRACT|SURVIVE)", line, re.IGNORECASE)
        if match:
            verdicts[match.group(1)] = match.group(2).upper()
    return verdicts


def run_round9_domain(
    client: genai.Client, domain: dict, repetition: int, ledger: dict[str, int]
) -> dict:
    memories = domain["memories"]
    prompt = ROUND9_REPAIR_PROMPT.format(
        revoked_source=domain["revoked_source"],
        independent_fact_c=domain["independent_fact_c"],
        m1_text=memories["m1"]["text"],
        m1_support=memories["m1"]["support"],
        m2a_text=memories["m2a"]["text"],
        m2a_support=memories["m2a"]["support"],
        m2b_text=memories["m2b"]["text"],
        m2b_support=memories["m2b"]["support"],
    )
    raw, error = call_model(client, prompt, ledger)
    verdicts = parse_verdicts(raw)
    expected = {
        "1": memories["m1"]["expected"].upper(),
        "2": memories["m2a"]["expected"].upper(),
        "3": memories["m2b"]["expected"].upper(),
    }
    correct = {key: verdicts.get(key) == expected[key] for key in expected}
    return {
        "repetition": repetition,
        "domain": domain["name"],
        "raw_response": raw,
        "call_error": error,
        "verdicts": verdicts,
        "expected": expected,
        "correct": correct,
        "missing_verdict_positions": [key for key in expected if key not in verdicts],
        "all_correct": error is None and all(correct.values()),
    }


def write_result(result: dict) -> None:
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))


def variance(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "population_variance": None, "population_stddev": None}
    return {
        "mean": sum(values) / len(values),
        "population_variance": pvariance(values),
        "population_stddev": pstdev(values),
    }


def summarize_round5(repetitions: list[dict]) -> dict:
    all_cases = [case for repetition in repetitions for case in repetition["cases"]]
    valid = [case for case in all_cases if case["fused_asserts_conclusion"] is True]
    clean = [case for case in valid if case["case_verdict"] == "CLEAN"]
    leaks = [case for case in valid if case["case_verdict"] == "LEAK"]
    invalid = [
        case
        for case in all_cases
        if case["case_verdict"].startswith("SKIPPED")
    ]
    errors = [case for case in all_cases if case["case_verdict"].startswith("ERROR")]
    per_case = {}
    for case in all_cases:
        entry = per_case.setdefault(
            case["id"],
            {"total": 0, "valid": 0, "clean": 0, "leak": 0, "invalid": 0, "errors": 0},
        )
        entry["total"] += 1
        if case["fused_asserts_conclusion"] is True:
            entry["valid"] += 1
        if case["case_verdict"] == "CLEAN":
            entry["clean"] += 1
        elif case["case_verdict"] == "LEAK":
            entry["leak"] += 1
        elif case["case_verdict"].startswith("SKIPPED"):
            entry["invalid"] += 1
        else:
            entry["errors"] += 1

    repeat_metrics = []
    for repetition in repetitions:
        cases = repetition["cases"]
        repeat_valid = [case for case in cases if case["fused_asserts_conclusion"] is True]
        repeat_clean = [case for case in repeat_valid if case["case_verdict"] == "CLEAN"]
        repeat_leaks = [case for case in repeat_valid if case["case_verdict"] == "LEAK"]
        repeat_errors = [case for case in cases if case["case_verdict"].startswith("ERROR")]
        repeat_metrics.append(
            {
                "repetition": repetition["repetition"],
                "total_cases": len(cases),
                "generation_valid": len(repeat_valid),
                "clean_repairs": len(repeat_clean),
                "leaks": len(repeat_leaks),
                "invalid_generations": sum(
                    case["case_verdict"].startswith("SKIPPED") for case in cases
                ),
                "errors": len(repeat_errors),
                "leak_rate_over_valid": len(repeat_leaks) / len(repeat_valid)
                if repeat_valid
                else None,
                "clean_rate_over_total": len(repeat_clean) / len(cases) if cases else None,
            }
        )
    leak_rates = [
        metric["leak_rate_over_valid"]
        for metric in repeat_metrics
        if metric["leak_rate_over_valid"] is not None
    ]
    return {
        "repetitions_completed": len(repetitions),
        "total_cases": len(all_cases),
        "generation_valid_cases": len(valid),
        "clean_repairs": len(clean),
        "leaks": len(leaks),
        "invalid_generations": len(invalid),
        "errors": len(errors),
        "pooled_leak_rate_over_valid": len(leaks) / len(valid) if valid else None,
        "repeat_metrics": repeat_metrics,
        "repeat_leak_rate_variance": variance(leak_rates),
        "per_case": per_case,
    }


def summarize_round9(repetitions: list[dict]) -> dict:
    all_domains = [domain for repetition in repetitions for domain in repetition["domains"]]
    total_judgments = sum(len(domain["correct"]) for domain in all_domains)
    total_correct = sum(sum(domain["correct"].values()) for domain in all_domains)
    missing_verdicts = sum(len(domain["missing_verdict_positions"]) for domain in all_domains)
    errors = sum(domain["call_error"] is not None for domain in all_domains)
    per_domain = {}
    per_position = {key: {"correct": 0, "total": 0} for key in ("1", "2", "3")}
    for domain in all_domains:
        entry = per_domain.setdefault(
            domain["domain"], {"correct": 0, "total": 0, "missing": 0, "errors": 0}
        )
        entry["correct"] += sum(domain["correct"].values())
        entry["total"] += len(domain["correct"])
        entry["missing"] += len(domain["missing_verdict_positions"])
        entry["errors"] += domain["call_error"] is not None
        for key, value in domain["correct"].items():
            per_position[key]["total"] += 1
            per_position[key]["correct"] += value

    repeat_metrics = []
    for repetition in repetitions:
        domains = repetition["domains"]
        repeat_total = sum(len(domain["correct"]) for domain in domains)
        repeat_correct = sum(sum(domain["correct"].values()) for domain in domains)
        repeat_metrics.append(
            {
                "repetition": repetition["repetition"],
                "total_judgments": repeat_total,
                "correct": repeat_correct,
                "accuracy": repeat_correct / repeat_total if repeat_total else None,
                "domains_fully_correct": sum(
                    domain["all_correct"] for domain in domains
                ),
                "domains_total": len(domains),
                "missing_verdicts": sum(
                    len(domain["missing_verdict_positions"]) for domain in domains
                ),
                "errors": sum(domain["call_error"] is not None for domain in domains),
            }
        )
    accuracies = [
        metric["accuracy"] for metric in repeat_metrics if metric["accuracy"] is not None
    ]
    return {
        "repetitions_completed": len(repetitions),
        "total_judgments": total_judgments,
        "total_correct": total_correct,
        "accuracy": total_correct / total_judgments if total_judgments else None,
        "domains_fully_correct": sum(domain["all_correct"] for domain in all_domains),
        "domains_total": len(all_domains),
        "missing_verdicts": missing_verdicts,
        "errors": errors,
        "repeat_metrics": repeat_metrics,
        "repeat_accuracy_variance": variance(accuracies),
        "per_domain": per_domain,
        "per_position": per_position,
    }


def main() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert fixture["repetitions"] == 5
    assert fixture["ground_truth_frozen_before_model_calls"] is True
    fixture_digest = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    ledger = {"model_calls": 0}
    result = {
        "round": fixture["round"],
        "model": MODEL,
        "project": PROJECT,
        "location": fixture["location"],
        "fixture_sha256": fixture_digest,
        "repetitions_requested": fixture["repetitions"],
        "artifact_lineage": {
            "round5_fixture": "RSM_CRUX5_ENTANGLED_INFERENCE/fixture.json",
            "round5_harness": "RSM_CRUX5_ENTANGLED_INFERENCE/run.py",
            "round9_fixture": "RSM_CRUX9_REDUNDANT_CASCADE/fixture.json",
            "round9_harness": "RSM_CRUX9_REDUNDANT_CASCADE/run.py",
            "round5_prompt_sha256": {
                "generate": hashlib.sha256(ROUND5_GENERATE_PROMPT.encode()).hexdigest(),
                "repair": hashlib.sha256(ROUND5_REPAIR_PROMPT.encode()).hexdigest(),
                "classify": hashlib.sha256(ROUND5_CLASSIFY_PROMPT.encode()).hexdigest(),
            },
            "round9_prompt_sha256": hashlib.sha256(ROUND9_REPAIR_PROMPT.encode()).hexdigest(),
        },
        "model_calls": ledger,
        "round5": {"repetitions": []},
        "round9": {"repetitions": []},
    }
    write_result(result)

    client = genai.Client(vertexai=True, project=PROJECT, location="global")
    for repetition in range(1, fixture["repetitions"] + 1):
        round5_cases = [
            run_round5_case(client, case, repetition, ledger)
            for case in fixture["source_rounds"]["round5"]["cases"]
        ]
        result["round5"]["repetitions"].append(
            {"repetition": repetition, "cases": round5_cases}
        )
        write_result(result)

        round9_domains = [
            run_round9_domain(client, domain, repetition, ledger)
            for domain in fixture["source_rounds"]["round9"]["domains"]
        ]
        result["round9"]["repetitions"].append(
            {"repetition": repetition, "domains": round9_domains}
        )
        write_result(result)

    result["round5"]["summary"] = summarize_round5(result["round5"]["repetitions"])
    result["round9"]["summary"] = summarize_round9(result["round9"]["repetitions"])
    result["status"] = {
        "round5_complete": len(result["round5"]["repetitions"]) == fixture["repetitions"],
        "round9_complete": len(result["round9"]["repetitions"]) == fixture["repetitions"],
        "model_calls_total": ledger["model_calls"],
    }
    write_result(result)
    return result


if __name__ == "__main__":
    experiment = main()
    round5 = experiment["round5"]["summary"]
    round9 = experiment["round9"]["summary"]
    print(
        "Round 5: "
        f"clean {round5['clean_repairs']}/{round5['generation_valid_cases']} valid, "
        f"leaks {round5['leaks']}, invalid {round5['invalid_generations']}, "
        f"errors {round5['errors']}"
    )
    print(
        "Round 9: "
        f"correct {round9['total_correct']}/{round9['total_judgments']}, "
        f"complete domains {round9['domains_fully_correct']}/{round9['domains_total']}, "
        f"missing {round9['missing_verdicts']}, errors {round9['errors']}"
    )
    print(f"Model calls: {experiment['status']['model_calls_total']}")
