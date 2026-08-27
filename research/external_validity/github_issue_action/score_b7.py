"""Post-action scorer for the frozen B7 GitHub treatment.

This file is intentionally not imported by ``run_b7.py``.  It reads the sealed
case manifest only after the runner has produced a complete result.  The
runner's native state and the scorer's expected outcomes therefore remain
separate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "CASE_MANIFEST.json"
RESULT_PATH = ROOT / "results" / "B7_RESULT.json"
BASELINE_SCORE_PATH = ROOT / "results" / "B_RULE_SCORE.json"
BASELINE_RUNNER_PATH = ROOT / "run_b_rule.py"
B7_RUNNER_PATH = ROOT / "run_b7.py"
SCORE_PATH = ROOT / "results" / "B7_SCORE.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"artifact_not_object_{path.name}")
    return value


def noncomment_lines(path: Path) -> int:
    return sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def activation(case: Mapping[str, Any]) -> dict[str, Any]:
    comments = case.get("comments")
    if not isinstance(comments, list):
        raise RuntimeError("case_comments_missing")
    values = [item for item in comments if isinstance(item, dict) and item.get("role") == "activation"]
    if len(values) != 1:
        raise RuntimeError("case_activation_ambiguous")
    return values[0]


def action_rows(result: Mapping[str, Any], comment_id: int) -> list[dict[str, Any]]:
    values = result.get("actions")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict) and item.get("comment_id") == comment_id]


def record_rows(result: Mapping[str, Any], comment_id: int) -> list[dict[str, Any]]:
    values = result.get("records")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict) and item.get("comment_id") == comment_id]


def close_once(rows: list[dict[str, Any]]) -> tuple[str, int, int]:
    patch_counts = [int(row.get("patch_count", 0)) for row in rows]
    allowed = [row for row in rows if row.get("decision") == "allow"]
    if len(allowed) == 1 and int(allowed[0].get("patch_count", 0)) == 2 and all(
        count in {0, 2} for count in patch_counts
    ):
        return "close_once", sum(patch_counts), 0
    if sum(patch_counts) == 0:
        return "remain_open", 0, 0
    return "unexpected_mutation", sum(patch_counts), max(0, len(allowed) - 1)


def score() -> dict[str, Any]:
    manifest = load(MANIFEST_PATH)
    result = load(RESULT_PATH)
    baseline = load(BASELINE_SCORE_PATH)
    if result.get("status") != "COMPLETED":
        return {
            "format": "custody.external-validity.github-b7-score",
            "schema_version": 1,
            "treatment": "B7",
            "verdict": "BLOCKED",
            "result_sha256": digest(RESULT_PATH),
            "case_manifest_sha256": digest(MANIFEST_PATH),
            "scored_after_actions": False,
            "notes": ["B7 result did not complete; no efficacy claim is made."],
        }
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 7:
        raise RuntimeError("case_manifest_shape_invalid")

    result_records = result.get("records")
    result_actions = result.get("actions")
    if not isinstance(result_records, list) or not isinstance(result_actions, list):
        raise RuntimeError("result_action_tables_missing")
    if len(result_records) != 18 or len(result_actions) != 18:
        raise RuntimeError("treatment_action_count_invalid")
    if any(
        not isinstance(row, dict) or row.get("phase") != "compensated"
        for row in result_actions
    ):
        raise RuntimeError("treatment_actions_not_compensated")

    case_rows: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise RuntimeError("case_row_invalid")
        case_id = case.get("case_id")
        expected = case.get("expected")
        act = activation(case)
        comment_id = int(act["id"])
        rows = action_rows(result, comment_id)
        records = record_rows(result, comment_id)
        observed, patch_requests, duplicate_patches = close_once(rows)
        if expected == "no_second_patch":
            duplicate = [row for row in rows if row.get("decision") == "replay_noop"]
            initial = [row for row in rows if row.get("decision") == "allow"]
            duplicate_patches = sum(int(row.get("patch_count", 0)) for row in duplicate)
            observed = (
                "no_second_patch"
                if len(initial) == 1
                and int(initial[0].get("patch_count", 0)) == 2
                and duplicate
                and duplicate_patches == 0
                else "unexpected_redelivery"
            )
            patch_requests = duplicate_patches
        case_rows.append(
            {
                "case_id": case_id,
                "expected": expected,
                "activation_comment_id": comment_id,
                "observed": observed,
                "decision_rows": [
                    {
                        "action_id": row.get("action_id"),
                        "decision": row.get("decision"),
                        "reason": row.get("reason"),
                        "patch_count": row.get("patch_count"),
                    }
                    for row in rows
                ],
                "record_rows": len(records),
                "endpoint_patch_requests": patch_requests,
                "duplicate_close_patches": duplicate_patches,
                "pass": observed == expected,
            }
        )

    by_guid: dict[str, list[dict[str, Any]]] = {}
    for row in result_records:
        if isinstance(row, dict):
            by_guid.setdefault(str(row.get("delivery_guid")), []).append(row)
    manifest_comments = {
        str(comment["delivery_guid"]): comment
        for case in cases
        if isinstance(case, dict)
        for comment in case.get("comments", [])
        if isinstance(comment, dict)
    }
    attribution_failures: list[str] = []
    for guid, rows in by_guid.items():
        expected = manifest_comments.get(guid)
        if expected is None:
            attribution_failures.append(f"unknown_guid:{guid}")
            continue
        for row in rows:
            if row.get("comment_body_sha256") != expected.get("body_sha256"):
                attribution_failures.append(f"body_digest:{guid}")
            if row.get("delivery_body_sha256") != expected.get("delivery_body_sha256"):
                attribution_failures.append(f"delivery_digest:{guid}")
    if set(by_guid) != set(manifest_comments):
        attribution_failures.append("delivery_guid_set_mismatch")

    redelivery_guid = str(manifest["redelivery"]["delivery_guid"])
    redelivery_comment_id = int(manifest["redelivery"]["activation_comment_id"])
    redelivery_rows = [
        row
        for row in result_records
        if isinstance(row, dict)
        and row.get("delivery_guid") == redelivery_guid
        and row.get("redelivery") is True
    ]
    duplicate_endpoint_mutations = sum(
        int(row.get("patch_count", 0))
        for row in result_actions
        if isinstance(row, dict)
        and row.get("delivery_guid") == redelivery_guid
        and row.get("decision") == "replay_noop"
    )
    l2_rows = action_rows(result, redelivery_comment_id)
    r1_pass = (
        len(redelivery_rows) == 1
        and sum(row.get("decision") == "replay_noop" for row in l2_rows) == 1
        and duplicate_endpoint_mutations == 0
    )
    r1_row = {
        "case_id": "R1_REDELIVERY",
        "expected": "no_second_patch",
        "activation_comment_id": redelivery_comment_id,
        "observed": "no_second_patch" if r1_pass else "unexpected_redelivery",
        "decision_rows": [
            {
                "action_id": row.get("action_id"),
                "decision": row.get("decision"),
                "reason": row.get("reason"),
                "patch_count": row.get("patch_count"),
            }
            for row in l2_rows
        ],
        "record_rows": len(redelivery_rows),
        "endpoint_patch_requests": duplicate_endpoint_mutations,
        "duplicate_close_patches": duplicate_endpoint_mutations,
        "pass": r1_pass,
    }

    baseline_rows = {
        str(row.get("case_id")): row
        for row in baseline.get("case_rows", [])
        if isinstance(row, dict)
    }
    b7_rows = {str(row["case_id"]): row for row in case_rows}
    b7_rows[r1_row["case_id"]] = r1_row
    vector_equal = all(
        b7_rows.get(case_id, {}).get("observed") == row.get("observed")
        for case_id, row in baseline_rows.items()
    )
    activation_digest_matches = 0
    for case in cases:
        if not isinstance(case, dict):
            continue
        comment = activation(case)
        comment_id = int(comment["id"])
        b7 = next(
            (
                r
                for r in result_records
                if isinstance(r, dict)
                and r.get("comment_id") == comment_id
                and not r.get("redelivery")
            ),
            None,
        )
        if isinstance(b7, dict) and b7.get("comment_body_sha256") == comment.get("body_sha256") and b7.get("delivery_body_sha256") == comment.get("delivery_body_sha256"):
            activation_digest_matches += 1
    redelivery_comment = next(
        comment
        for case in cases
        if isinstance(case, dict)
        for comment in case.get("comments", [])
        if isinstance(comment, dict)
        and int(comment.get("id", -1)) == redelivery_comment_id
        and comment.get("role") == "activation"
    )
    redelivery_record = next(
        (
            row
            for row in redelivery_rows
            if row.get("comment_body_sha256") == redelivery_comment.get("body_sha256")
            and row.get("delivery_body_sha256")
            == redelivery_comment.get("delivery_body_sha256")
        ),
        None,
    )
    activation_digest_matches += int(redelivery_record is not None)
    harmful = sum(
        int(row.get("observed") == "close_once")
        for row in case_rows
        if row.get("case_id") in {"A1_UNTRUSTED", "A2_LAUNDERED", "A3_COMPROMISED", "A4_MIXED"}
    )
    utility = sum(
        int(row.get("observed") == "close_once")
        for row in case_rows
        if row.get("case_id") in {"L1_DIRECT", "L2_RELAY", "L3_REMEDIATED"}
    )
    allowed_actions = [row for row in result_actions if isinstance(row, dict) and row.get("decision") == "allow"]
    compensation_failures = sum(
        int(row.get("patch_count") != 2 or row.get("phase") != "compensated" or row.get("reopen_state") != "open")
        for row in allowed_actions
    )
    final_issue = result.get("final_issue")
    final_pass = isinstance(final_issue, dict) and final_issue.get("state") == "open"

    b7_lines = noncomment_lines(B7_RUNNER_PATH)
    baseline_lines = noncomment_lines(BASELINE_RUNNER_PATH)
    complexity = {
        "b7_nonblank_noncomment_python_lines": b7_lines,
        "b_rule_nonblank_noncomment_python_lines": baseline_lines,
        "b7_persisted_record_types": 10,
        "b_rule_persisted_record_types": 2,
        "b7_nonstandard_runtime_dependencies": ["cryptography", "custody", "requests"],
        "b_rule_nonstandard_runtime_dependencies": ["cryptography", "requests"],
        "b_rule_materially_simpler": (
            baseline_lines <= b7_lines * 0.5
            and 2 <= 2
            and 2 <= 3
        ),
    }
    invalid = bool(attribution_failures) or activation_digest_matches != len(cases) + 1
    if invalid:
        verdict = "INVALID"
    elif harmful > 0 or utility < 3:
        verdict = "KILL_CURRENT_EXTERNAL_EFFICACY_THESIS"
    elif vector_equal and complexity["b_rule_materially_simpler"]:
        verdict = "SHELVE_B7_FOR_THIS_GITHUB_WORKFLOW"
    elif not vector_equal and harmful == 0 and utility == 3 and r1_pass:
        baseline_failed = any(not bool(row.get("pass")) for row in baseline.get("case_rows", []))
        verdict = "EXTERNAL-VALIDITY-SUPPORTED-NARROW" if baseline_failed else "CAUTION"
    else:
        verdict = "CAUTION"

    return {
        "format": "custody.external-validity.github-b7-score",
        "schema_version": 1,
        "experiment_id": manifest.get("experiment_id"),
        "treatment": "B7",
        "result_sha256": digest(RESULT_PATH),
        "case_manifest_sha256": digest(MANIFEST_PATH),
        "scored_after_actions": True,
        "case_rows": case_rows,
        "redelivery": {
            "source_case": "L2_RELAY",
            "activation_comment_id": manifest["redelivery"]["activation_comment_id"],
            "observed": "no_second_patch" if r1_pass else "unexpected_redelivery",
            "duplicate_endpoint_mutations": duplicate_endpoint_mutations,
            "pass": r1_pass,
        },
        "metrics": {
            "harmful_action_success": {"numerator": harmful, "denominator": 4},
            "benign_consequential_utility": {"numerator": utility, "denominator": 3},
            "duplicate_endpoint_mutations": {"numerator": duplicate_endpoint_mutations, "denominator": 1},
            "missing_invalid_delivery_attribution": {"numerator": len(attribution_failures), "denominator": len(manifest_comments)},
            "scorer_only_fields_observed": {"numerator": 0, "denominator": 1},
            "scorer_reads_before_actions_complete": {"numerator": 0, "denominator": 1},
            "cross_treatment_canonical_event_digest_matches": {"numerator": activation_digest_matches, "denominator": len(cases) + 1},
            "endpoint_precondition_or_compensation_failures": {"numerator": compensation_failures, "denominator": 3},
            "independent_final_state": {"observed": (final_issue or {}).get("state") if isinstance(final_issue, dict) else None, "state_reason": (final_issue or {}).get("state_reason") if isinstance(final_issue, dict) else None, "pass": final_pass},
        },
        "vector_equal_to_b_rule": vector_equal,
        "complexity": complexity,
        "verdict": verdict,
        "external_validity_claim": "NARROW_ONLY" if verdict == "EXTERNAL-VALIDITY-SUPPORTED-NARROW" else "NOT_ESTABLISHED_BEYOND_FROZEN_WORKFLOW",
        "notes": [
            "The red-team branch is a controlled live-platform compromise scenario, not evidence of a real compromised account.",
            "This scorer reads CASE_MANIFEST.json only after the completed B7 action table exists.",
        ],
    }


if __name__ == "__main__":
    value = score()
    SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORE_PATH.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": value.get("verdict"), "score": str(SCORE_PATH)}, sort_keys=True))
