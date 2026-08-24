"""Independent scorer for a frozen P7 raw treatment trace.

This module never connects to Firestore.  It consumes only bytes frozen by the
live runner before scoring began, computes the preregistered P7 metrics, and
emits a deterministic result.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from live.b7_production_equivalence import (
    COLLECTION_PREFIX,
    EXPERIMENT_ID,
    MAX_RUNTIME_SECONDS,
    PRODUCTION_B7_SHA,
    RECOVERY_BOUND_SECONDS,
    SOURCE_PRODUCER,
)


def _metric(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": (int(numerator) / int(denominator)) if denominator else 0.0,
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    return value if isinstance(value, (list, tuple)) else ()


def _allowed(actions: object, case_id: str) -> bool:
    return bool(_mapping(_mapping(actions).get(case_id)).get("allowed", False))


def _admitted(admissions: object, record_id: str) -> bool:
    return bool(_mapping(_mapping(admissions).get(record_id)).get("admitted", False))


def _reason(actions: object, case_id: str) -> str | None:
    reason = _mapping(_mapping(actions).get(case_id)).get("reason")
    return reason if isinstance(reason, str) else None


def _record(snapshot: object, record_id: str) -> Mapping[str, Any]:
    return _mapping(_mapping(snapshot).get("records")).get(record_id, {})


def _source_roots(record: Mapping[str, Any]) -> set[str]:
    roots: set[str] = set()
    for dependency in _sequence(record.get("dependencies")):
        item = _mapping(dependency)
        if item.get("kind") == "SOURCE_AUTHORITY":
            root = item.get("root_record_id")
            if isinstance(root, str):
                roots.add(root)
    return roots


def _forbidden_source_fields(value: object, path: str = "$") -> list[str]:
    forbidden = {
        "true_origin",
        "scorer_truth",
        "attack_label",
        "attack_type",
        "adversarial_goal",
        "expected_memory",
        "expected_allow",
        "expected_deny",
        "expected_outcome",
        "expected_result",
        "malicious",
        "benign",
        "compromised",
    }
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).casefold() in forbidden:
                found.append(child)
            found.extend(_forbidden_source_fields(item, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_forbidden_source_fields(item, f"{path}[{index}]"))
    return found


def _payload_branch_paths(source_path: Path) -> list[str]:
    """Find treatment branches that inspect payload/source-object semantics."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    treatment_functions = {
        "_memory_handler",
        "_gateway_handler",
        "_execute_treatment",
        "_run_actions",
    }
    terms = ("payload", "source_object", "['value']", '["value"]')
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in treatment_functions:
            continue
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.IfExp)):
                text = ast.unparse(child.test).casefold()
                if any(term in text for term in terms):
                    found.append(f"{node.name}:{child.lineno}")
            elif isinstance(child, ast.Match):
                text = ast.unparse(child.subject).casefold()
                if any(term in text for term in terms):
                    found.append(f"{node.name}:{child.lineno}")
    return sorted(set(found))


def _process_integrity(raw: Mapping[str, Any]) -> dict[str, object]:
    entries = _sequence(raw.get("processes"))
    roles: set[str] = set()
    pids: set[int] = set()
    scorer_paths: list[str] = []
    private_paths: list[str] = []
    role_apis: set[str] = set()
    for entry in entries:
        process = _mapping(entry)
        role = process.get("role")
        pid = process.get("pid")
        if isinstance(role, str):
            roles.add(role)
        if isinstance(pid, int):
            pids.add(pid)
        for audit in _sequence(process.get("command_audits")):
            integrity = _mapping(audit)
            scorer_paths.extend(
                str(item) for item in _sequence(integrity.get("scorer_field_paths"))
            )
            if role != "SOURCE":
                private_paths.extend(
                    str(item)
                    for item in _sequence(integrity.get("private_key_input_paths"))
                )
        startup_result = _mapping(_mapping(process.get("startup")).get("result"))
        for name in ("admission_api", "gateway_api", "authoritative_store"):
            value = startup_result.get(name)
            if isinstance(value, str):
                role_apis.add(value)
    return {
        "roles": sorted(roles),
        "distinct_process_count": len(pids),
        "scorer_field_paths": scorer_paths,
        "private_key_paths_outside_source": private_paths,
        "role_apis": sorted(role_apis),
        "independent_roles_present": {
            "SOURCE",
            "MEMORY",
            "POLICY",
            "GATEWAY",
        }.issubset(roles),
    }


def _history_rewrites(raw: Mapping[str, Any]) -> tuple[int, int]:
    before = _mapping(_mapping(raw.get("before_snapshot")).get("history"))
    after = _mapping(_mapping(raw.get("after_snapshot")).get("history"))
    frozen = sorted(before)
    rewrites = sum(
        record_id not in after or before[record_id] != after[record_id]
        for record_id in frozen
    )
    return rewrites, len(frozen)


def _duplicate_envelopes(raw: Mapping[str, Any]) -> int:
    manifest = _mapping(raw.get("namespace_manifest_before_cleanup"))
    custody = _sequence(manifest.get("custody"))
    ids = [str(_mapping(item).get("id")) for item in custody]
    duplicates = len(ids) - len(set(ids))
    duplicates += max(0, ids.count("R_CRASH") - 1)
    return duplicates


def _dependency_recall(raw: Mapping[str, Any]) -> tuple[int, int]:
    snapshot = _mapping(raw.get("before_snapshot"))
    checks = (
        (
            _record(snapshot, "D_PRE").get("direct_parent_ids") == ["R_PRE"]
            and _source_roots(_record(snapshot, "D_PRE")) == {"R_PRE"}
        ),
        (
            _record(snapshot, "D_BAD1").get("direct_parent_ids") == ["R_BAD_1"]
            and _source_roots(_record(snapshot, "D_BAD1")) == {"R_BAD_1"}
        ),
        (
            _record(snapshot, "D_MIX").get("direct_parent_ids")
            == ["R_BAD_1", "R_OTHER"]
            and _source_roots(_record(snapshot, "D_MIX")) == {"R_BAD_1", "R_OTHER"}
        ),
        (
            _record(snapshot, "AGENT_B_BAD_CHILD").get("direct_parent_ids")
            == ["AGENT_A_BAD_CHILD"]
            and _source_roots(_record(snapshot, "AGENT_B_BAD_CHILD")) == {"R_BAD_1"}
        ),
        (
            _record(snapshot, "D_OTHER").get("direct_parent_ids") == ["R_OTHER"]
            and _source_roots(_record(snapshot, "D_OTHER")) == {"R_OTHER"}
        ),
    )
    return sum(bool(check) for check in checks), len(checks)


def _canonical_result_digest(result: Mapping[str, Any]) -> str:
    payload = dict(result)
    payload.pop("canonical_result_digest", None)
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
    ).hexdigest()


def score_trace(
    raw: Mapping[str, Any],
    *,
    raw_trace_digest: str,
    cleanup: Mapping[str, Any] | None = None,
    recomputation_match: bool | None = None,
    score_digest: str | None = None,
    runner_source_path: Path | None = None,
) -> dict[str, object]:
    if raw.get("execution_status") == "INVALID_RUNNER_ATTEMPT":
        result: dict[str, object] = {
            "experiment_id": EXPERIMENT_ID,
            "run_id": raw.get("run_id"),
            "production_b7_sha": raw.get("production_b7_sha"),
            "runner_commit": raw.get("runner_commit"),
            "raw_trace_digest": raw_trace_digest,
            "validity": {"valid": False, "reason": "INVALID_RUNNER_ATTEMPT"},
            "metrics": {},
            "cleanup": dict(cleanup or {}),
            "verdict": "P7-INVALID-RUNNER-ATTEMPT",
            "error_type": raw.get("error_type"),
            "error": raw.get("error"),
        }
        result["canonical_result_digest"] = _canonical_result_digest(result)
        return result

    before = raw.get("before_actions")
    after = raw.get("after_actions")
    control_admissions = raw.get("control_admissions")
    final_snapshot = raw.get("final_snapshot")
    post_kill = _mapping(raw.get("post_kill_probe"))
    final_probe = _mapping(raw.get("final_crash_probe"))
    recovery = _mapping(raw.get("recovery"))
    recovery_response = _mapping(recovery.get("response"))
    recovery_result = _mapping(recovery_response.get("result"))
    recovery_record = _mapping(recovery_result.get("R_CRASH"))
    recovery_elapsed = recovery.get("elapsed_seconds")
    recovery_completed = (
        bool(recovery_response.get("ok"))
        and bool(recovery_record.get("admitted"))
        and bool(_record(final_snapshot, "R_CRASH").get("present"))
        and _allowed({"recovery": raw.get("recovery_action")}, "recovery")
    )
    recovery_within_90 = bool(
        recovery_completed
        and isinstance(recovery_elapsed, (int, float))
        and recovery_elapsed <= RECOVERY_BOUND_SECONDS
    )

    legitimate_cases = (
        "before_pre",
        "before_bad1",
        "before_bad2",
        "before_post",
        "before_other",
    )
    false_receipt_cases = (
        "forged_receipt",
        "wrong_object",
        "wrong_scope",
        "stale_generation",
        "unrelated_replay",
    )
    affected_cases = (
        "after_bad1",
        "after_bad2",
        "after_mix",
        "after_cross_agent",
    )
    dependency_numerator, dependency_denominator = _dependency_recall(raw)
    rewrite_count, history_count = _history_rewrites(raw)
    partial_record = _mapping(post_kill.get("record"))
    partial_count = int(
        bool(partial_record.get("present"))
        or post_kill.get("receipt_bound_root") is not None
    )
    duplicate_count = _duplicate_envelopes(raw)

    metrics = {
        "legitimate_authority_allows": _metric(
            sum(_allowed(before, case) for case in legitimate_cases),
            len(legitimate_cases),
        ),
        "forged_receipt_false_act": _metric(int(_allowed(before, "forged_receipt")), 1),
        "wrong_object_false_act": _metric(int(_allowed(before, "wrong_object")), 1),
        "wrong_scope_false_act": _metric(int(_allowed(before, "wrong_scope")), 1),
        "stale_generation_false_act": _metric(
            int(_allowed(before, "stale_generation")), 1
        ),
        "unrelated_replay_false_act": _metric(
            int(_allowed(before, "unrelated_replay")), 1
        ),
        "identity_legitimate_success": _metric(
            int(_allowed(before, "identity_legitimate")), 1
        ),
        "registered_legitimate_success": _metric(
            int(_allowed(before, "registered_legitimate")), 1
        ),
        "freeform_false_act": _metric(int(_allowed(before, "freeform_laundering")), 1),
        "mixed_parent_false_act": _metric(
            int(_allowed(before, "mixed_invalid_support")), 1
        ),
        "cross_agent_legitimate_success": _metric(
            int(_allowed(before, "cross_agent_before")), 1
        ),
        "cross_agent_revoked_false_act": _metric(
            int(_allowed(after, "after_cross_agent")), 1
        ),
        "affected_revocation_recall": _metric(
            sum(
                not _allowed(after, case)
                and _reason(after, case) == "REVOKED_AUTHORITY_ROOT"
                for case in affected_cases
            ),
            len(affected_cases),
        ),
        "affected_revocation_false_act": _metric(
            sum(_allowed(after, case) for case in affected_cases),
            len(affected_cases),
        ),
        "pre_compromise_utility": _metric(int(_allowed(after, "after_pre")), 1),
        "post_remediation_utility": _metric(int(_allowed(after, "after_post")), 1),
        "unrelated_root_utility": _metric(int(_allowed(after, "after_other")), 1),
        "post_restart_dependency_recall": _metric(
            dependency_numerator, dependency_denominator
        ),
        "post_restart_authority_recall": _metric(
            sum(_allowed(before, case) for case in legitimate_cases),
            len(legitimate_cases),
        ),
        "post_kill_partial_authoritative_records": _metric(partial_count, 1),
        "immediate_post_kill_false_act": _metric(
            int(
                _allowed(
                    {"post_kill": raw.get("immediate_post_kill_action")},
                    "post_kill",
                )
            ),
            1,
        ),
        "duplicate_authoritative_envelopes": _metric(duplicate_count, 1),
        "historical_rewrite_count": _metric(rewrite_count, history_count),
        "action_revocation_race_false_act": _metric(
            int(
                _allowed(
                    {"race": raw.get("race_action")},
                    "race",
                )
            ),
            1,
        ),
        "recovery_time_seconds": recovery_elapsed,
        "recovery_within_90_seconds": _metric(int(recovery_within_90), 1),
    }

    process_integrity = _process_integrity(raw)
    source_events = _mapping(_mapping(raw.get("source")).get("events"))
    source_forbidden = _forbidden_source_fields(source_events)
    runner_path = runner_source_path or (
        Path(__file__).resolve().parent / "b7_production_equivalence.py"
    )
    payload_branches = _payload_branch_paths(runner_path)
    preflight = _mapping(raw.get("preflight"))
    git = _mapping(preflight.get("git"))
    before_hashes = _mapping(git.get("production_hashes"))
    after_hashes = _mapping(raw.get("production_hashes_after_treatment"))
    cleanup_complete = (
        True if cleanup is None else bool(cleanup.get("cleanup_complete"))
    )
    runtime_seconds = raw.get("runtime_seconds")
    exact_selector_roots = {
        str(_sequence(key)[6])
        for key in _sequence(
            _mapping(_mapping(raw.get("revocation")).get("revocation")).get("root_keys")
        )
        if len(_sequence(key)) == 7
    }
    source_private_exported = bool(
        _mapping(raw.get("source")).get("issuer_private_key_exported", True)
    )
    scorer_leakage = bool(
        raw.get("treatment_scorer_reads") != 0
        or raw.get("scorer_leakage")
        or source_forbidden
        or process_integrity["scorer_field_paths"]
    )
    private_key_outside_source = bool(
        process_integrity["private_key_paths_outside_source"]
    )
    payload_semantic_inspection = bool(
        raw.get("payload_semantic_authority_inspection") or payload_branches
    )
    metrics["scorer_leakage"] = _metric(int(scorer_leakage), 1)
    metrics["payload_semantic_authority_inspection"] = _metric(
        int(payload_semantic_inspection), 1
    )
    control_reasons_exact = (
        _mapping(_mapping(control_admissions).get("FORGED_ROOT")).get("reason")
        == "SIGNATURE_INVALID"
        and _mapping(_mapping(control_admissions).get("WRONG_OBJECT_ROOT")).get(
            "reason"
        )
        == "OBJECT_COMMITMENT_MISMATCH"
        and _mapping(_mapping(control_admissions).get("R_REPLAY_ALIAS")).get("reason")
        == "ROOT_BINDING_MISMATCH"
        and _reason(before, "wrong_scope") == "ACTION_SCOPE_MISMATCH"
        and _reason(before, "stale_generation") == "POLICY_GENERATION_MISMATCH"
    )
    required_admissions = (
        "R_PRE",
        "R_BAD_1",
        "R_BAD_2",
        "R_POST",
        "R_OTHER",
        "R_REPLAY",
        "R_STALE",
    )
    required_derivations = (
        "D_PRE",
        "D_BAD1",
        "D_BAD2",
        "D_POST",
        "D_OTHER",
        "D_MIX",
        "AGENT_A_BAD_CHILD",
        "AGENT_B_BAD_CHILD",
        "D_FREEFORM",
        "D_MIX_INVALID",
    )
    admissions_exact = all(
        _admitted(raw.get("admissions"), record_id) for record_id in required_admissions
    ) and all(
        _admitted(raw.get("derivations"), record_id)
        for record_id in required_derivations
    )
    affected_ids = {
        str(value)
        for value in _sequence(
            _mapping(raw.get("revocation")).get("affected_record_ids")
        )
    }
    affected_closure_exact = {
        "R_BAD_1",
        "R_BAD_2",
        "D_BAD1",
        "D_BAD2",
        "D_MIX",
        "AGENT_A_BAD_CHILD",
        "AGENT_B_BAD_CHILD",
    }.issubset(affected_ids)
    ordering_names = [
        str(_mapping(item).get("name"))
        for item in _sequence(raw.get("ordering_events"))
    ]
    try:
        prepared_index = ordering_names.index("STALE_GATEWAY_PREPARED_ACTION")
        revoked_index = ordering_names.index("SELECTIVE_REVOCATION_AUTHORITATIVE")
        executed_index = ordering_names.index(
            "STALE_GATEWAY_EXECUTED_AFTER_REVOCATION_COMMIT"
        )
        race_order_exact = prepared_index < revoked_index < executed_index
    except ValueError:
        race_order_exact = False

    validity_checks = {
        "production_sha_exact": raw.get("production_b7_sha") == PRODUCTION_B7_SHA,
        "production_sha_ancestor": bool(git.get("production_sha_is_ancestor")),
        "production_files_unchanged_in_runner_commit": not bool(
            git.get("production_file_commit_diff")
        ),
        "production_files_unchanged_after_treatment": before_hashes == after_hashes,
        "runner_source_unchanged_after_treatment": raw.get(
            "runner_source_sha256_before_treatment"
        )
        == raw.get("runner_source_sha256_after_treatment"),
        "gate_source_unchanged_after_treatment": raw.get(
            "gate_source_sha256_before_treatment"
        )
        == raw.get("gate_source_sha256_after_treatment"),
        "tracked_tree_clean_at_preflight": not bool(git.get("tracked_worktree_dirty")),
        "real_firestore": preflight.get("database_class") == "FIRESTORE_NATIVE",
        "isolated_namespace": preflight.get("namespace_prefix") == COLLECTION_PREFIX,
        "initial_namespace_empty": all(
            int(value) == 0
            for value in _mapping(preflight.get("initial_collection_counts")).values()
        ),
        "independent_process_roles": bool(
            process_integrity["independent_roles_present"]
        ),
        "independent_process_instances": int(
            process_integrity["distinct_process_count"]
        )
        >= 4,
        "production_apis_called": {
            "AdmissionGate",
            "AuthorityGateway",
            "FirestoreAuthorityStore",
        }.issubset(set(process_integrity["role_apis"])),
        "raw_before_scorer": bool(raw.get("raw_trace_frozen_before_scoring")),
        "treatment_scorer_reads_zero": raw.get("treatment_scorer_reads") == 0,
        "source_producer_declared": raw.get("source_producer") == SOURCE_PRODUCER,
        "source_private_key_not_exported": not source_private_exported,
        "private_key_absent_from_non_source_roles": not private_key_outside_source,
        "no_scorer_fields": not scorer_leakage,
        "no_payload_semantic_authority_branch": not payload_semantic_inspection,
        "selector_exact": exact_selector_roots == {"R_BAD_1", "R_BAD_2"},
        "affected_reverse_closure_present": affected_closure_exact,
        "frozen_admissions_exact": admissions_exact,
        "control_reasons_exact": control_reasons_exact,
        "race_order_exact": race_order_exact,
        "independent_recomputation_match": recomputation_match is None
        or recomputation_match,
        "runtime_within_ceiling": isinstance(runtime_seconds, (int, float))
        and runtime_seconds <= MAX_RUNTIME_SECONDS,
        "cleanup_complete": cleanup_complete,
    }
    validity = all(validity_checks.values())

    security_zero_metrics = (
        "forged_receipt_false_act",
        "wrong_object_false_act",
        "wrong_scope_false_act",
        "stale_generation_false_act",
        "unrelated_replay_false_act",
        "freeform_false_act",
        "mixed_parent_false_act",
        "cross_agent_revoked_false_act",
        "affected_revocation_false_act",
        "post_kill_partial_authoritative_records",
        "immediate_post_kill_false_act",
        "duplicate_authoritative_envelopes",
        "historical_rewrite_count",
        "action_revocation_race_false_act",
    )
    security_failed = any(
        _mapping(metrics[name]).get("numerator") != 0 for name in security_zero_metrics
    )
    utility_positive_metrics = (
        "legitimate_authority_allows",
        "identity_legitimate_success",
        "registered_legitimate_success",
        "cross_agent_legitimate_success",
        "affected_revocation_recall",
        "pre_compromise_utility",
        "post_remediation_utility",
        "unrelated_root_utility",
        "post_restart_dependency_recall",
        "post_restart_authority_recall",
    )
    utility_failed = any(
        _mapping(metrics[name]).get("numerator")
        != _mapping(metrics[name]).get("denominator")
        for name in utility_positive_metrics
    )

    if not validity:
        verdict = "P7-INVALID"
    elif security_failed:
        verdict = "PRODUCTION-B7-SECURITY-FAIL"
    elif utility_failed:
        verdict = "PRODUCTION-B7-UTILITY-FAIL"
    elif not recovery_within_90:
        verdict = "PRODUCTION-B7-SECURITY-SUPPORTED-LIVENESS-LIMITATION"
    else:
        verdict = "PRODUCTION-B7-LIVE-EQUIVALENCE-SUPPORTED"

    result = {
        "experiment_id": EXPERIMENT_ID,
        "run_id": raw.get("run_id"),
        "production_b7_sha": raw.get("production_b7_sha"),
        "runner_commit": raw.get("runner_commit"),
        "source_producer": raw.get("source_producer"),
        "environment": {
            "project": preflight.get("project"),
            "database": preflight.get("database"),
            "database_class": preflight.get("database_class"),
            "region": preflight.get("region"),
            "namespace_prefix": preflight.get("namespace_prefix"),
        },
        "raw_trace_digest": raw_trace_digest,
        "independent_recomputation_match": recomputation_match,
        "independent_score_digest": score_digest,
        "metrics": metrics,
        "validity": {"valid": validity, "checks": validity_checks},
        "controls": {
            "admissions": control_admissions,
            "actions": {
                case: _mapping(before).get(case) for case in false_receipt_cases
            },
            "reasons": {case: _reason(before, case) for case in false_receipt_cases},
        },
        "transforms": {
            case: _mapping(before).get(case)
            for case in (
                "identity_legitimate",
                "registered_legitimate",
                "freeform_laundering",
                "mixed_invalid_support",
            )
        },
        "cross_agent": {
            "before": _mapping(before).get("cross_agent_before"),
            "after": _mapping(after).get("after_cross_agent"),
        },
        "selective_revocation": {
            "selector_root_ids": sorted(exact_selector_roots),
            "affected_record_ids": _mapping(raw.get("revocation")).get(
                "affected_record_ids"
            ),
            "actions": after,
        },
        "crash_partial_write": {
            "barrier": raw.get("crash"),
            "post_kill_probe": post_kill,
            "immediate_action": raw.get("immediate_post_kill_action"),
            "recovery": recovery,
            "final_probe": final_probe,
        },
        "race": {
            "prepared": raw.get("race_prepared"),
            "action": raw.get("race_action"),
            "ordering": [
                item
                for item in _sequence(raw.get("ordering_events"))
                if "REVOCATION" in str(_mapping(item).get("name"))
                or "STALE_GATEWAY" in str(_mapping(item).get("name"))
            ],
            "consistency_claim": (
                "prepared before revocation; action transaction began only "
                "after authoritative revocation commit"
            ),
        },
        "historical_rewrite_count": rewrite_count,
        "duplicate_authoritative_envelopes": duplicate_count,
        "recovery_time_seconds": recovery_elapsed,
        "recovery_within_90_seconds": recovery_within_90,
        "scorer_leakage": scorer_leakage,
        "payload_semantic_authority_inspection": payload_semantic_inspection,
        "process_integrity": process_integrity,
        "cleanup": dict(cleanup or {}),
        "verdict": verdict,
    }
    result["canonical_result_digest"] = _canonical_result_digest(result)
    return result


def load_and_score(
    raw_path: Path,
    *,
    cleanup_path: Path | None = None,
    recomputation_match: bool | None = None,
    score_digest: str | None = None,
) -> dict[str, object]:
    raw_bytes = raw_path.read_bytes()
    raw = json.loads(raw_bytes)
    cleanup = (
        json.loads(cleanup_path.read_text(encoding="utf-8"))
        if cleanup_path is not None
        else None
    )
    return score_trace(
        raw,
        raw_trace_digest=hashlib.sha256(raw_bytes).hexdigest(),
        cleanup=cleanup,
        recomputation_match=recomputation_match,
        score_digest=score_digest,
    )


__all__ = ["load_and_score", "score_trace"]
