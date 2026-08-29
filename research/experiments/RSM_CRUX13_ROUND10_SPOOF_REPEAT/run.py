"""Repeat Round 10's naive spoofed server_access condition.

The fixture contains the exact Round 10 spoofed server_access domain and
ground truth. Five sequential calls use the unchanged naive prompt and
parser. Every raw response or transport error is retained in result.json;
there is no retry or post-hoc relabeling.

Run: python3 research/experiments/RSM_CRUX13_ROUND10_SPOOF_REPEAT/run.py
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
    client: genai.Client, fixture: dict, repetition: int, ledger: dict[str, int]
) -> dict:
    domain = fixture["domain"]
    memories = domain["memories"]
    prompt = NAIVE_PROMPT.format(
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
    expected = {key: value.upper() for key, value in fixture["expected"].items()}
    correct = {key: verdicts.get(key) == expected[key] for key in expected}
    missing = [key for key in expected if key not in verdicts]
    m2b_false_negative = (
        verdicts.get("3") == "SURVIVE" and expected["3"] == "RETRACT"
    )
    complete = error is None and not missing
    return {
        "repetition": repetition,
        "domain": domain["name"],
        "condition": fixture["condition"],
        "spoofed": domain["spoofed"],
        "raw_response": raw,
        "call_error": error,
        "verdicts": verdicts,
        "expected": expected,
        "correct": correct,
        "missing_verdict_positions": missing,
        "m2b_false_negative": m2b_false_negative,
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


def summarize(calls: list[dict]) -> dict:
    total_judgments = sum(len(call["correct"]) for call in calls)
    total_correct = sum(sum(call["correct"].values()) for call in calls)
    false_negatives = sum(call["m2b_false_negative"] for call in calls)
    missing = sum(len(call["missing_verdict_positions"]) for call in calls)
    errors = sum(call["call_error"] is not None for call in calls)
    repeat_metrics = []
    for call in calls:
        correct = sum(call["correct"].values())
        repeat_metrics.append(
            {
                "repetition": call["repetition"],
                "correct": correct,
                "total_judgments": len(call["correct"]),
                "accuracy": correct / len(call["correct"])
                if call["correct"]
                else None,
                "m2b_verdict": call["verdicts"].get("3"),
                "m2b_false_negative": call["m2b_false_negative"],
                "complete": call["complete"],
                "all_correct": call["all_correct"],
                "missing_verdicts": len(call["missing_verdict_positions"]),
                "errors": call["call_error"] is not None,
            }
        )
    complete_accuracies = [
        metric["accuracy"]
        for metric in repeat_metrics
        if metric["complete"] and metric["accuracy"] is not None
    ]
    false_negative_values = [
        1.0 if metric["m2b_false_negative"] else 0.0 for metric in repeat_metrics
    ]
    return {
        "repetitions_completed": len(calls),
        "complete_calls": sum(call["complete"] for call in calls),
        "all_correct_calls": sum(call["all_correct"] for call in calls),
        "total_judgments": total_judgments,
        "total_correct": total_correct,
        "accuracy": total_correct / total_judgments if total_judgments else None,
        "m2b_false_negatives": false_negatives,
        "m2b_false_negative_rate": false_negatives / len(calls) if calls else None,
        "missing_verdicts": missing,
        "errors": errors,
        "repeat_metrics": repeat_metrics,
        "complete_call_accuracy_values": complete_accuracies,
        "repeat_accuracy_variance": variance(complete_accuracies),
        "m2b_false_negative_values": false_negative_values,
        "m2b_false_negative_variance": variance(false_negative_values),
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
    assert fixture["repetitions"] == 5
    assert fixture["condition"] == "naive"
    assert fixture["ground_truth_frozen_before_model_calls"] is True
    assert fixture["domain"] == source_fixture["domains"][fixture["source_domain_index"]]
    assert NAIVE_PROMPT == source_naive_prompt()
    derived_expected = {
        "1": fixture["domain"]["memories"]["m1"]["expected"].upper(),
        "2": fixture["domain"]["memories"]["m2a"]["expected"].upper(),
        "3": fixture["domain"]["memories"]["m2b"]["expected"].upper(),
    }
    assert derived_expected == fixture["expected"]
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
        "artifact_lineage": {
            "source_fixture": "RSM_CRUX10_SPOOFED_INDEPENDENCE/fixture.json",
            "source_harness": "RSM_CRUX10_SPOOFED_INDEPENDENCE/run.py",
            "condition": "NAIVE_PROMPT only; skeptical condition not run",
            "execution": "isolated server_access call; full four-domain batch not repeated",
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
        result["summary"] = summarize(result["repetitions"])
        result["status"] = {
            "complete": False,
            "model_calls_total": ledger["model_calls"],
        }
        write_result(result)
        return result

    for repetition in range(1, fixture["repetitions"] + 1):
        result["repetitions"].append(run_call(client, fixture, repetition, ledger))
        write_result(result)

    result["summary"] = summarize(result["repetitions"])
    result["status"] = {
        "complete": (
            len(result["repetitions"]) == fixture["repetitions"]
            and result["summary"]["complete_calls"] == fixture["repetitions"]
        ),
        "model_calls_total": ledger["model_calls"],
    }
    write_result(result)
    return result


if __name__ == "__main__":
    experiment = main()
    print("===== ROUND 10 NAIVE SPOOFED SERVER_ACCESS REPEATS =====")
    for call in experiment["repetitions"]:
        print(
            f"r{call['repetition']}: expected={call['expected']} "
            f"got={call['verdicts']} correct={call['correct']}"
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
    print(
        f"M2b false negatives: {summary['m2b_false_negatives']}/"
        f"{summary['repetitions_completed']} "
        f"({summary['m2b_false_negative_rate']:.2%})"
        if summary["m2b_false_negative_rate"] is not None
        else "M2b false negatives: n/a"
    )
    print(f"Model calls: {experiment['status']['model_calls_total']}")
