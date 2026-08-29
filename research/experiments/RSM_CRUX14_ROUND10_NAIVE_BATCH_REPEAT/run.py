"""Repeat Round 10's exact naive four-domain batch.

The fixture contains the four Round 10 domains in their original order.
Five sequential batches use the unchanged naive prompt and parser. Every
raw response or transport error is retained in result.json; there is no
retry or post-hoc relabeling.

Run: python3 research/experiments/RSM_CRUX14_ROUND10_NAIVE_BATCH_REPEAT/run.py
Requires: CLOUDSDK_CONFIG pointed at a credentialed gcloud config for
project-988bc9fe-092c-4b32-90c.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from statistics import pvariance, pstdev

from google import genai

OUT_DIR = Path(__file__).parent
FIXTURE_PATH = OUT_DIR / "fixture.json"
SOURCE_FIXTURE_PATH = OUT_DIR.parent / "RSM_CRUX10_SPOOFED_INDEPENDENCE" / "fixture.json"
SOURCE_RUN_PATH = OUT_DIR.parent / "RSM_CRUX10_SPOOFED_INDEPENDENCE" / "run.py"
PROJECT = "project-988bc9fe-092c-4b32-90c"
MODEL = "gemini-3.5-flash"

NAIVE_PROMPT = """A source has just been revoked:

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
        match = re.match(r"\s*([123])\s*:\s*(RETRACT|SURVIVE)", line, re.IGNORECASE)
        if match:
            verdicts[match.group(1)] = match.group(2).upper()
    return verdicts


def source_naive_prompt() -> str:
    tree = ast.parse(SOURCE_RUN_PATH.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "NAIVE_PROMPT"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("Round 10 NAIVE_PROMPT assignment not found")


def build_prompt(domain: dict) -> str:
    memories = domain["memories"]
    return NAIVE_PROMPT.format(
        revoked_source=domain["revoked_source"],
        independent_fact_c=domain["independent_fact_c"],
        m1_text=memories["m1"]["text"],
        m1_support=memories["m1"]["support"],
        m2a_text=memories["m2a"]["text"],
        m2a_support=memories["m2a"]["support"],
        m2b_text=memories["m2b"]["text"],
        m2b_support=memories["m2b"]["support"],
    )


def call_model(
    client: genai.Client, prompt: str, ledger: dict[str, int]
) -> tuple[str, str | None]:
    ledger["model_calls"] += 1
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        return (response.text or "").strip(), None
    except Exception as exc:  # noqa: BLE001 - preserve an honest per-call failure artifact.
        return "", f"{type(exc).__name__}: {exc}"


def run_call(
    client: genai.Client,
    domain: dict,
    repetition: int,
    batch_position: int,
    call_index: int,
    ledger: dict[str, int],
) -> dict:
    raw, error = call_model(client, build_prompt(domain), ledger)
    verdicts = parse_verdicts(raw)
    memories = domain["memories"]
    expected = {
        "1": memories["m1"]["expected"].upper(),
        "2": memories["m2a"]["expected"].upper(),
        "3": memories["m2b"]["expected"].upper(),
    }
    correct = {key: verdicts.get(key) == expected[key] for key in expected}
    missing = [key for key in expected if key not in verdicts]
    complete = error is None and not missing
    return {
        "call_index": call_index,
        "repetition": repetition,
        "batch_position": batch_position,
        "domain": domain["name"],
        "spoofed": domain["spoofed"],
        "raw_response": raw,
        "call_error": error,
        "verdicts": verdicts,
        "expected": expected,
        "correct": correct,
        "missing_verdict_positions": missing,
        "m2b_false_negative": (
            domain["name"] == "server_access"
            and verdicts.get("3") == "SURVIVE"
            and expected["3"] == "RETRACT"
        ),
        "m2b_false_positive": (
            domain["name"] == "vendor_onboarding"
            and verdicts.get("3") == "RETRACT"
            and expected["3"] == "SURVIVE"
        ),
        "complete": complete,
        "all_correct": complete and all(correct.values()),
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


def summarize(calls: list[dict], domain_names: list[str], repetitions: int) -> dict:
    total_judgments = sum(len(call["correct"]) for call in calls)
    total_correct = sum(sum(call["correct"].values()) for call in calls)
    missing = sum(len(call["missing_verdict_positions"]) for call in calls)
    errors = sum(call["call_error"] is not None for call in calls)
    batch_metrics = []
    for repetition in range(1, repetitions + 1):
        batch = [call for call in calls if call["repetition"] == repetition]
        batch_judgments = sum(len(call["correct"]) for call in batch)
        batch_correct = sum(sum(call["correct"].values()) for call in batch)
        server = next(
            (call for call in batch if call["domain"] == "server_access"), None
        )
        vendor = next(
            (call for call in batch if call["domain"] == "vendor_onboarding"), None
        )
        batch_metrics.append(
            {
                "repetition": repetition,
                "calls_recorded": len(batch),
                "correct": batch_correct,
                "total_judgments": batch_judgments,
                "accuracy": batch_correct / batch_judgments
                if batch_judgments
                else None,
                "complete": len(batch) == len(domain_names)
                and all(call["complete"] for call in batch),
                "all_correct": len(batch) == len(domain_names)
                and all(call["all_correct"] for call in batch),
                "server_access_m2b_false_negative": bool(
                    server and server["m2b_false_negative"]
                ),
                "vendor_onboarding_m2b_false_positive": bool(
                    vendor and vendor["m2b_false_positive"]
                ),
            }
        )

    call_metrics = []
    for call in calls:
        correct = sum(call["correct"].values())
        call_metrics.append(
            {
                "call_index": call["call_index"],
                "repetition": call["repetition"],
                "batch_position": call["batch_position"],
                "domain": call["domain"],
                "correct": correct,
                "total_judgments": len(call["correct"]),
                "accuracy": correct / len(call["correct"])
                if call["correct"]
                else None,
                "complete": call["complete"],
                "all_correct": call["all_correct"],
                "missing_verdicts": len(call["missing_verdict_positions"]),
                "errors": call["call_error"] is not None,
                "m2b_false_negative": call["m2b_false_negative"],
                "m2b_false_positive": call["m2b_false_positive"],
            }
        )

    complete_batch_accuracies = [
        batch["accuracy"]
        for batch in batch_metrics
        if batch["complete"] and batch["accuracy"] is not None
    ]
    complete_call_accuracies = [
        call["accuracy"]
        for call in call_metrics
        if call["complete"] and call["accuracy"] is not None
    ]
    server_flags = [
        1.0 if batch["server_access_m2b_false_negative"] else 0.0
        for batch in batch_metrics
    ]
    vendor_flags = [
        1.0 if batch["vendor_onboarding_m2b_false_positive"] else 0.0
        for batch in batch_metrics
    ]

    per_domain = {}
    for domain_name in domain_names:
        domain_calls = [call for call in calls if call["domain"] == domain_name]
        domain_total = sum(len(call["correct"]) for call in domain_calls)
        domain_correct = sum(sum(call["correct"].values()) for call in domain_calls)
        per_domain[domain_name] = {
            "calls": len(domain_calls),
            "complete_calls": sum(call["complete"] for call in domain_calls),
            "correct": domain_correct,
            "total_judgments": domain_total,
            "accuracy": domain_correct / domain_total if domain_total else None,
            "per_position": {
                key: {
                    "correct": sum(call["correct"][key] for call in domain_calls),
                    "total": len(domain_calls),
                    "got": [call["verdicts"].get(key) for call in domain_calls],
                }
                for key in ("1", "2", "3")
            },
        }

    return {
        "repetitions_completed": len(batch_metrics),
        "complete_batches": sum(batch["complete"] for batch in batch_metrics),
        "all_correct_batches": sum(batch["all_correct"] for batch in batch_metrics),
        "complete_calls": sum(call["complete"] for call in calls),
        "total_judgments": total_judgments,
        "total_correct": total_correct,
        "accuracy": total_correct / total_judgments if total_judgments else None,
        "server_access_m2b_false_negatives": sum(
            call["m2b_false_negative"] for call in calls
        ),
        "vendor_onboarding_m2b_false_positives": sum(
            call["m2b_false_positive"] for call in calls
        ),
        "missing_verdicts": missing,
        "errors": errors,
        "batch_metrics": batch_metrics,
        "call_metrics": call_metrics,
        "per_domain": per_domain,
        "complete_batch_accuracy_values": complete_batch_accuracies,
        "complete_call_accuracy_values": complete_call_accuracies,
        "batch_accuracy_variance": variance(complete_batch_accuracies),
        "call_accuracy_variance": variance(complete_call_accuracies),
        "server_access_m2b_false_negative_values": server_flags,
        "server_access_m2b_false_negative_variance": variance(server_flags),
        "vendor_onboarding_m2b_false_positive_values": vendor_flags,
        "vendor_onboarding_m2b_false_positive_variance": variance(vendor_flags),
        "per_position": {
            key: {
                "correct": sum(call["correct"][key] for call in calls),
                "total": len(calls),
                "got": [call["verdicts"].get(key) for call in calls],
            }
            for key in ("1", "2", "3")
        },
    }


def main() -> dict:
    fixture = json.loads(FIXTURE_PATH.read_text())
    source_fixture = json.loads(SOURCE_FIXTURE_PATH.read_text())
    domain_names = fixture["source_domain_order"]
    assert fixture["repetitions"] == 5
    assert fixture["condition"] == "naive"
    assert fixture["source_condition"] == "naive"
    assert fixture["ground_truth_frozen_before_model_calls"] is True
    assert fixture["domains"] == source_fixture["domains"]
    assert [domain["name"] for domain in fixture["domains"]] == domain_names
    assert NAIVE_PROMPT == source_naive_prompt()
    ledger = {"model_calls": 0}
    result = {
        "round": fixture["round"],
        "model": MODEL,
        "project": PROJECT,
        "location": fixture["location"],
        "condition": fixture["condition"],
        "fixture_sha256": hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
        "prompt_sha256": hashlib.sha256(NAIVE_PROMPT.encode()).hexdigest(),
        "source_round": fixture["source_round"],
        "source_domain_order": domain_names,
        "artifact_lineage": {
            "source_fixture": "RSM_CRUX10_SPOOFED_INDEPENDENCE/fixture.json",
            "source_harness": "RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py",
            "condition": "NAIVE_PROMPT only; skeptical condition not run",
            "execution": "four domains in source order, repeated five times",
        },
        "model_calls": ledger,
        "client_error": None,
        "repetitions": [],
    }
    write_result(result)

    try:
        client = genai.Client(vertexai=True, project=PROJECT, location="global")
    except Exception as exc:  # noqa: BLE001 - retain initialization failure in artifact.
        result["client_error"] = f"{type(exc).__name__}: {exc}"
        result["summary"] = summarize(result["repetitions"], domain_names, fixture["repetitions"])
        result["status"] = {
            "complete": False,
            "model_calls_total": ledger["model_calls"],
        }
        write_result(result)
        return result

    call_index = 0
    for repetition in range(1, fixture["repetitions"] + 1):
        for batch_position, domain in enumerate(fixture["domains"], start=1):
            call_index += 1
            result["repetitions"].append(
                run_call(
                    client,
                    domain,
                    repetition,
                    batch_position,
                    call_index,
                    ledger,
                )
            )
            write_result(result)

    result["summary"] = summarize(result["repetitions"], domain_names, fixture["repetitions"])
    result["status"] = {
        "complete": (
            len(result["repetitions"]) == fixture["repetitions"] * len(domain_names)
            and result["summary"]["complete_batches"] == fixture["repetitions"]
        ),
        "model_calls_total": ledger["model_calls"],
    }
    write_result(result)
    return result


if __name__ == "__main__":
    experiment = main()
    print("===== ROUND 10 NAIVE FULL-BATCH REPEATS =====")
    for call in experiment["repetitions"]:
        print(
            f"call={call['call_index']} batch={call['repetition']} "
            f"position={call['batch_position']} domain={call['domain']} "
            f"expected={call['expected']} got={call['verdicts']} "
            f"correct={call['correct']}"
        )
        print(f"raw={call['raw_response']}")
    summary = experiment["summary"]
    if summary["accuracy"] is None:
        print("Accuracy: n/a")
    else:
        print(
            f"Accuracy: {summary['total_correct']}/{summary['total_judgments']} "
            f"({summary['accuracy']:.2%})"
        )
    print(f"Complete batches: {summary['complete_batches']}/{summary['repetitions_completed']}")
    print(
        f"server_access M2b false negatives: "
        f"{summary['server_access_m2b_false_negatives']}"
    )
    print(
        f"vendor_onboarding M2b false positives: "
        f"{summary['vendor_onboarding_m2b_false_positives']}"
    )
    print(f"Model calls: {experiment['status']['model_calls_total']}")
