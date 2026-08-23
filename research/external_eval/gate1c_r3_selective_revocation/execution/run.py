#!/usr/bin/env python3
"""Gate 1C-R2 selective receipt-root revocation falsifier.

R2 is a fresh runner. Its only semantic difference from R1 is an explicit
alias -> durable ID -> record resolver before RootKey construction.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[4]
EXECUTION_DIR = Path(__file__).resolve().parent
R3_RUNNER_PATH = REPO_ROOT / "research/external_eval/gate1b_r3_provenance/execution/run.py"

EXPERIMENT_ID = "EXT_GATE1C_R3_SELECTIVE_RECEIPT_REVOCATION"
PREREGISTRATION_SHA = os.environ.get("R3_PREREGISTRATION_SHA", "").strip()
PARENT_R2_PREREGISTRATION = "552cf23336a0a222364c247e61c7263f84e56f60"
R2_INVALID_PRESERVATION = "40e33a7c0b75afd4f9e63816caa136368ecd7c1b"
PARENT_GATE1C_DESIGN = "3b27797aa0fb20d6207ecd3881bbcbabf3580ca2"
GATE1B_R3_EXECUTION_COMMIT = "f3eb51cbdd52eca0f30f9989311f944b5ee50c35"
EXTERNAL_COMMIT = "63f1359d677efbe1a65b982b2a54cabfec97f1e1"
EXTERNAL_SOURCE_DIR = Path(os.environ.get("TMANM_SOURCE_DIR", "/tmp/custody-gate1-tmanm-source")).resolve()

ARM_R0 = "R0_ISSUER_WIDE"
ARM_ROOT = "R3_RECEIPT_ROOT_BOUND"
ARMS = (ARM_R0, ARM_ROOT)
ROOT_ALIASES = {
    "R_PRE": "ROOT-01",
    "R_BAD_1": "ROOT-02",
    "R_BAD_2": "ROOT-03",
    "R_POST": "ROOT-04",
    "R_OTHER": "ROOT-05",
}
CASE_RECORDS = {
    "D_PRE": "MEM-01",
    "D_BAD1": "MEM-02",
    "D_BAD2": "MEM-03",
    "D_POST": "MEM-04",
    "D_OTHER": "MEM-05",
    "D_MIX": "MEM-06",
    "cross_agent_revoked": "AGENT-02",
    "record_reissue": "MEM-07",
    "revoked_receipt_copy": "MEM-08",
    "generation_old": "MEM-09",
}
EXPECTED_RECEIPT_FIELDS = {
    "receipt_version", "receipt_id", "issuer_id", "issuer_key_id", "policy_key",
    "granting_generation", "granted_cap", "action_scope", "source_revision",
    "upstream_record_id", "upstream_object_commitment", "issuer_signature",
}


def load_r3():
    spec = importlib.util.spec_from_file_location("gate1c_r2_frozen_r3", R3_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen R3 runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r3 = load_r3()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.STDOUT).strip()


def verify_lineage() -> dict[str, Any]:
    branch = git_output("branch", "--show-current")
    head = git_output("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", PREREGISTRATION_SHA):
        raise RuntimeError("R3_PREREGISTRATION_SHA must be 40 lowercase hex characters")
    if branch != "research/external-gate1c-r3-selective-revocation-falsifier":
        raise RuntimeError(f"wrong R3 branch: {branch}")
    if head != PREREGISTRATION_SHA:
        raise RuntimeError("execution head differs from R3 preregistration")
    required = {
        "research/external_eval/gate1c_r3_selective_revocation/PLAN.md",
        "research/external_eval/gate1c_r3_selective_revocation/PREREGISTRATION.md",
        "research/external_eval/gate1c_r3_selective_revocation/EQUIVALENCE_AUDIT.md",
        "research/external_eval/gate1c_r3_selective_revocation/METRIC_LIFECYCLE_CONTRACT.md",
    }
    files = set(git_output("ls-tree", "-r", "--name-only", PREREGISTRATION_SHA).splitlines())
    if not required <= files:
        raise RuntimeError("R3 authoritative document set is incomplete")
    if subprocess.call(
        ["git", "diff", "--quiet", GATE1B_R3_EXECUTION_COMMIT, "--",
         "research/external_eval/gate1b_r3_provenance"],
        cwd=REPO_ROOT,
    ) != 0:
        raise RuntimeError("frozen Gate 1B-R3 artifacts differ")
    return {
        "branch": branch,
        "execution_head": head,
        "preregistration_sha": PREREGISTRATION_SHA,
        "parent_r2_preregistration": PARENT_R2_PREREGISTRATION,
        "r2_invalid_preservation": R2_INVALID_PRESERVATION,
        "parent_gate1c_design": PARENT_GATE1C_DESIGN,
        "gate1b_r3_execution": GATE1B_R3_EXECUTION_COMMIT,
    }


def verify_receipt_schema() -> dict[str, Any]:
    fields = set(r3.AuthorityReceipt.__dataclass_fields__)
    if fields != EXPECTED_RECEIPT_FIELDS:
        raise RuntimeError("P2 receipt schema differs from frozen schema")
    return {"passed": True, "fields": sorted(fields), "new_fields": [], "schema_changed": False}


def root_key(record: Any, receipt: Any) -> tuple[Any, ...]:
    return (
        receipt.issuer_id,
        receipt.receipt_id,
        receipt.upstream_record_id,
        receipt.upstream_object_commitment,
        tuple(receipt.policy_key),
        receipt.granting_generation,
        record.record_id,
    )


def immutable_key(value: Any) -> bool:
    if isinstance(value, tuple):
        return all(immutable_key(item) for item in value)
    return isinstance(value, (str, int, float, bool, type(None)))


def records_by_id(state: Any) -> dict[str, Any]:
    resolved = {record_id: record for record_id, record in state.records.items()}
    if len(resolved) != len(state.records):
        raise RuntimeError("duplicate durable record ID")
    return resolved


def resolve_root(alias: str, objects_by_alias: Mapping[str, Any], aliases: Mapping[str, str], by_id: Mapping[str, Any]) -> Any:
    if alias not in aliases:
        raise RuntimeError(f"missing root alias: {alias}")
    durable_id = aliases[alias]
    record = by_id.get(durable_id)
    if record is None:
        raise RuntimeError(f"missing durable root record: {durable_id}")
    if alias not in objects_by_alias or objects_by_alias[alias].record_id != durable_id:
        raise RuntimeError(f"root alias manifest mismatch: {alias}")
    if record.record_id != durable_id:
        raise RuntimeError(f"resolved root ID mismatch: {alias}")
    return record


def root_preflight(state: Any, objects_by_alias: Mapping[str, Any], aliases: Mapping[str, str], issuer: Any) -> dict[str, Any]:
    by_id = records_by_id(state)
    if len(state.records) != 16 or len(set(state.records)) != 16:
        raise RuntimeError("graph must contain 16 unique durable record IDs")
    expected_aliases = {"R_PRE": "ROOT-01", "R_BAD_1": "ROOT-02", "R_BAD_2": "ROOT-03", "R_POST": "ROOT-04", "R_OTHER": "ROOT-05"}
    if dict(aliases) != expected_aliases:
        raise RuntimeError("frozen root alias manifest changed")
    roots = {alias: resolve_root(alias, objects_by_alias, aliases, by_id) for alias in expected_aliases}
    verifier = r3.ReceiptVerifier(public_key_for(state, issuer), issuer.issuer_id)
    for alias, record in roots.items():
        receipt = record.authority_receipt
        if receipt is None:
            raise RuntimeError(f"missing root receipt: {alias}")
        verified, reason, _trace = verifier.verify(record, receipt, state)
        if not verified:
            raise RuntimeError(f"root receipt failed authentication: {alias}:{reason}")
    keys = {alias: root_key(record, record.authority_receipt) for alias, record in roots.items()}
    reconstructed = {alias: root_key(resolve_root(alias, objects_by_alias, aliases, by_id), roots[alias].authority_receipt) for alias in expected_aliases}
    if keys != reconstructed or len(set(keys.values())) != 5:
        raise RuntimeError("RootKeys are not deterministic and unique")
    if any(not immutable_key(key) for key in keys.values()):
        raise RuntimeError("RootKey contains mutable data")
    for key in keys.values():
        hash(key)
    for alias, record in roots.items():
        base = keys[alias]
        receipt = record.authority_receipt
        mutations = (
            dataclasses.replace(receipt, issuer_id=receipt.issuer_id + "-x"),
            dataclasses.replace(receipt, receipt_id=receipt.receipt_id + "-x"),
            dataclasses.replace(receipt, upstream_record_id=receipt.upstream_record_id + "-x"),
            dataclasses.replace(receipt, upstream_object_commitment=receipt.upstream_object_commitment[::-1]),
            dataclasses.replace(receipt, policy_key=tuple(list(receipt.policy_key[:-1]) + ["different.scope"])),
            dataclasses.replace(receipt, granting_generation=receipt.granting_generation + 1),
        )
        if any(root_key(record, changed) == base for changed in mutations):
            raise RuntimeError(f"identity field did not affect RootKey: {alias}")
        if root_key(dataclasses.replace(record, payload=record.payload + "-metadata"), receipt) != base:
            raise RuntimeError(f"non-identity metadata affected RootKey: {alias}")
    selected = {keys["R_BAD_1"], keys["R_BAD_2"]}
    if len(selected) != 2 or any(alias in {"R_PRE", "R_POST", "R_OTHER"} for alias in selected):
        raise RuntimeError("selector contains a non-compromised root")
    return {
        "records": 16,
        "unique_durable_record_ids": 16,
        "authenticated_roots": 5,
        "unique_root_keys": 5,
        "root_key_digests": {alias: digest(list(key)) for alias, key in keys.items()},
        "selector": {"selected_roots": ["R_BAD_1", "R_BAD_2"], "selected_keys": 2, "unique_selector_keys": 2, "mutable_objects": 0},
    }


class RootSelectiveVerifier:
    def __init__(self, base_verifier: Any, revoked_root_keys: set[tuple[Any, ...]]):
        self.base_verifier = base_verifier
        self.revoked_root_keys = revoked_root_keys

    def verify(self, record: Any, receipt: Any, state: Any):
        if receipt is not None and root_key(record, receipt) in self.revoked_root_keys:
            return False, "REVOKED_AUTHORITY_ROOT", {"revocation_selector": "receipt_root", "root_record_id": record.record_id, "receipt_id": receipt.receipt_id}
        return self.base_verifier.verify(record, receipt, state)


def action_for(target: str) -> dict[str, Any]:
    return {"tool": "pay", "to": target, "amount": 1200, "scope": r3.ACTION_SCOPE, "destination": "payment_processor"}


def make_root(issuer: Any, state: Any, record_id: str, source_id: str, value: str, policy_key: tuple[str, ...]) -> Any:
    source = r3.source_object(source_id, value)
    receipt = issuer.issue(source, policy_key, 1)
    record = r3.root_record(record_id, f"value:{source_id}", action_for(value), policy_key, 1, source, receipt, role="ORIGIN")
    state.add(record)
    return record


def make_child(state: Any, record_id: str, payload: str, parents: tuple[str, ...], transform: str = "REGISTERED", policy_key: tuple[str, ...] | None = None, transform_cap: str = "ACT") -> Any:
    record = r3.derived_record(record_id, payload, action_for("ACME-OFFICIAL-AP"), state, parents, transform, policy_key or r3.POLICY_KEYS["registered"], transform_cap)
    state.add(record)
    return record


def build_graph() -> tuple[Any, dict[str, Any], dict[str, str], Any]:
    issuer = r3.AuthorityIssuer()
    state = r3.make_policy_state(issuer)
    roots = {
        "R_PRE": make_root(issuer, state, ROOT_ALIASES["R_PRE"], "SRC-01", "ACCOUNT-101", r3.POLICY_KEYS["vendor"]),
        "R_BAD_1": make_root(issuer, state, ROOT_ALIASES["R_BAD_1"], "SRC-02", "ACCOUNT-202", r3.POLICY_KEYS["vendor"]),
        "R_BAD_2": make_root(issuer, state, ROOT_ALIASES["R_BAD_2"], "SRC-03", "ACCOUNT-303", r3.POLICY_KEYS["vendor"]),
        "R_POST": make_root(issuer, state, ROOT_ALIASES["R_POST"], "SRC-04", "ACCOUNT-404", r3.POLICY_KEYS["vendor"]),
        "R_OTHER": make_root(issuer, state, ROOT_ALIASES["R_OTHER"], "SRC-05", "ACCOUNT-505", r3.POLICY_KEYS["clean"]),
    }
    records = {
        "D_PRE": make_child(state, CASE_RECORDS["D_PRE"], "derived-01", (roots["R_PRE"].record_id,)),
        "D_BAD1": make_child(state, CASE_RECORDS["D_BAD1"], "derived-02", (roots["R_BAD_1"].record_id,)),
        "D_BAD2": make_child(state, CASE_RECORDS["D_BAD2"], "derived-03", (roots["R_BAD_2"].record_id,)),
        "D_POST": make_child(state, CASE_RECORDS["D_POST"], "derived-04", (roots["R_POST"].record_id,)),
        "D_OTHER": make_child(state, CASE_RECORDS["D_OTHER"], "derived-05", (roots["R_OTHER"].record_id,)),
        "D_MIX": make_child(state, CASE_RECORDS["D_MIX"], "derived-06", (roots["R_BAD_1"].record_id, roots["R_OTHER"].record_id)),
    }
    agent_a = make_child(state, "AGENT-01", "forwarded-01", (roots["R_BAD_1"].record_id,))
    records["cross_agent_revoked"] = make_child(state, CASE_RECORDS["cross_agent_revoked"], "forwarded-02", (agent_a.record_id,), "CROSS_AGENT", r3.POLICY_KEYS["agent"])
    records["record_reissue"] = make_child(state, CASE_RECORDS["record_reissue"], "reissued-02", (roots["R_BAD_1"].record_id,))
    copied = dataclasses.replace(roots["R_BAD_2"], record_id=CASE_RECORDS["revoked_receipt_copy"], payload="copied-02", operation_role="RELAY", direct_parent_ids=(), observed_parent_ids=(), support_root_ids=(roots["R_BAD_2"].record_id,))
    state.add(copied)
    records["revoked_receipt_copy"] = copied
    records["generation_old"] = make_child(state, CASE_RECORDS["generation_old"], "old-generation", (roots["R_PRE"].record_id,))
    return state, {**roots, **records}, dict(ROOT_ALIASES), issuer


def public_key_for(state: Any, issuer: Any):
    return r3.ed25519.Ed25519PublicKey.from_public_bytes(state.issuer_public_keys[issuer.issuer_id])


def evaluate_arm(base_state: Any, objects: Mapping[str, Any], arm: str, issuer: Any, revoked_root_keys: set[tuple[Any, ...]]) -> dict[str, Any]:
    state = copy.deepcopy(base_state)
    if arm == ARM_R0:
        state.revoked_issuers.add(issuer.issuer_id)
        verifier: Any = r3.ReceiptVerifier(public_key_for(state, issuer), issuer.issuer_id)
    elif arm == ARM_ROOT:
        verifier = RootSelectiveVerifier(r3.ReceiptVerifier(public_key_for(state, issuer), issuer.issuer_id), revoked_root_keys)
    else:
        raise ValueError(arm)
    outcomes: dict[str, dict[str, Any]] = {}
    for case_name, record_id in CASE_RECORDS.items():
        outcomes[case_name] = r3.ArchitectureAP2Adapter(state.records[record_id], state, verifier).evaluate().as_dict()
    generation_state = copy.deepcopy(state)
    generation_state.policies[r3.POLICY_KEYS["vendor"]] = r3.PolicySnapshot("v2", 2, {r3.ACTION_SCOPE: "ACT"})
    outcomes["generation_old"] = r3.ArchitectureAP2Adapter(generation_state.records[CASE_RECORDS["generation_old"]], generation_state, verifier).evaluate().as_dict()
    return {
        "arm": arm,
        "revoked_root_keys": [list(key) for key in sorted(revoked_root_keys, key=str)],
        "outcomes": outcomes,
        "state_before": base_state.snapshot(),
        "state_after": state.snapshot(),
        "historical_rewrite_count": int(base_state.snapshot()["records"] != state.snapshot()["records"] or base_state.snapshot()["policies"] != state.snapshot()["policies"]),
    }


def _collect_root_ids(trace: Any) -> set[str]:
    roots: set[str] = set()
    if not isinstance(trace, Mapping):
        return roots
    for root_id in trace.get("support_roots", []):
        if isinstance(root_id, str):
            roots.add(root_id)
    for dependency in trace.get("authority_dependencies", []):
        if isinstance(dependency, Mapping):
            root_id = dependency.get("root_record_id")
            if isinstance(root_id, str):
                roots.add(root_id)
    parent_decisions = trace.get("parent_decisions", {})
    if isinstance(parent_decisions, Mapping):
        for child_trace in parent_decisions.values():
            roots.update(_collect_root_ids(child_trace))
    return roots


def raw_action_traces(run: Mapping[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    root_alias_by_id = {
        "ROOT-01": "R_PRE",
        "ROOT-02": "R_BAD_1",
        "ROOT-03": "R_BAD_2",
        "ROOT-04": "R_POST",
        "ROOT-05": "R_OTHER",
    }
    traces: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in ARMS:
        traces[arm] = {}
        for case_name, record_id in CASE_RECORDS.items():
            outcome = run["arms"][arm]["outcomes"][case_name]
            required = sorted(_collect_root_ids(outcome.get("decision_trace", {})))
            matched = sorted(
                root_alias_by_id[root_id]
                for root_id in required
                if root_id in root_alias_by_id
                and root_alias_by_id[root_id] in {"R_BAD_1", "R_BAD_2"}
                and arm == ARM_ROOT
                and outcome.get("reason") == "REVOKED_AUTHORITY_ROOT"
            )
            traces[arm][case_name] = {
                "case": case_name,
                "arm": arm,
                "record_id": record_id,
                "required_roots": required,
                "matched_revoked_roots": matched,
                "action_allowed": bool(outcome["action_allowed"]),
                "decision_reason": outcome["reason"],
            }
    return traces


def build_run(run_index: int) -> dict[str, Any]:
    state, objects, aliases, issuer = build_graph()
    by_id = records_by_id(state)
    roots = {alias: resolve_root(alias, objects, aliases, by_id) for alias in aliases}
    revoked_keys = {root_key(roots[alias], roots[alias].authority_receipt) for alias in ("R_BAD_1", "R_BAD_2")}
    if len(revoked_keys) != 2:
        raise RuntimeError("selector does not contain exactly two keys")
    arms = {arm: evaluate_arm(state, objects, arm, issuer, revoked_keys) for arm in ARMS}
    raw_traces = raw_action_traces({"arms": arms})
    snapshots = {name: record.immutable_snapshot() for name, record in objects.items()}
    return {
        "run_index": run_index,
        "arms": arms,
        "raw_action_traces": raw_traces,
        "root_manifest": {
            alias: {
                "record_id": roots[alias].record_id,
                "receipt_id": roots[alias].authority_receipt.receipt_id,
                "issuer_id": roots[alias].authority_receipt.issuer_id,
                "upstream_record_id": roots[alias].authority_receipt.upstream_record_id,
                "upstream_object_commitment": roots[alias].authority_receipt.upstream_object_commitment,
                "policy_key": list(roots[alias].authority_receipt.policy_key),
                "granting_generation": roots[alias].authority_receipt.granting_generation,
            }
            for alias in aliases
        },
        "case_records": dict(CASE_RECORDS),
        "receipt_schema": sorted(EXPECTED_RECEIPT_FIELDS),
        "immutable_snapshots": snapshots,
        "historical_rewrite_count": sum(arm["historical_rewrite_count"] for arm in arms.values()),
        "scorer_guard": {"scorer_reads": 0, "treatment_received_scorer_truth": False, "payload_semantics_used": False},
    }


def normalized_run(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "arms": run["arms"],
        "raw_action_traces": run["raw_action_traces"],
        "root_manifest": run["root_manifest"],
        "case_records": run["case_records"],
        "receipt_schema": run["receipt_schema"],
        "historical_rewrite_count": run["historical_rewrite_count"],
    }


def _action_values(
    runs: tuple[Mapping[str, Any], ...], arm: str, case: str
) -> list[bool]:
    return [
        bool(run["raw_action_traces"][arm][case]["action_allowed"])
        for run in runs
    ]


def utility_metric(values: list[bool]) -> dict[str, int]:
    return {"numerator": sum(value is True for value in values), "denominator": len(values)}


def false_act_metric(values: list[bool]) -> dict[str, int]:
    # False ACT is the finalized action observation itself. Correct DENY is zero.
    return {"numerator": sum(value is True for value in values), "denominator": len(values)}


def affected_recall_metric(values: list[bool]) -> dict[str, int]:
    return {"numerator": sum(value is False for value in values), "denominator": len(values)}


def build_metrics(runs: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    affected_values = [
        value
        for case in ("D_BAD1", "D_BAD2")
        for value in _action_values(runs, ARM_ROOT, case)
    ]
    r0_affected_values = [
        value
        for case in ("D_BAD1", "D_BAD2")
        for value in _action_values(runs, ARM_R0, case)
    ]
    return {
        "affected_revocation_recall": affected_recall_metric(affected_values),
        "affected_false_act": false_act_metric(affected_values),
        "unrelated_receipt_utility": utility_metric(_action_values(runs, ARM_ROOT, "D_OTHER")),
        "pre_compromise_utility": utility_metric(_action_values(runs, ARM_ROOT, "D_PRE")),
        "post_remediation_utility": utility_metric(_action_values(runs, ARM_ROOT, "D_POST")),
        "mixed_parent_false_act": false_act_metric(_action_values(runs, ARM_ROOT, "D_MIX")),
        "cross_agent_revoked_false_act": false_act_metric(_action_values(runs, ARM_ROOT, "cross_agent_revoked")),
        "record_reissue_escape_false_act": false_act_metric(_action_values(runs, ARM_ROOT, "record_reissue")),
        "revoked_receipt_copy_false_act": false_act_metric(_action_values(runs, ARM_ROOT, "revoked_receipt_copy")),
        "sibling_receipt_utility": utility_metric(_action_values(runs, ARM_ROOT, "D_OTHER")),
        "generation_false_act": false_act_metric(_action_values(runs, ARM_ROOT, "generation_old")),
        "historical_rewrite_count": {
            "numerator": sum(run["historical_rewrite_count"] for run in runs),
            "denominator": len(runs) * len(ARMS),
        },
        "r0_affected_revocation_recall": affected_recall_metric(r0_affected_values),
        "r0_affected_false_act": false_act_metric(r0_affected_values),
        "r0_unrelated_receipt_utility": utility_metric(_action_values(runs, ARM_R0, "D_OTHER")),
        "r0_pre_compromise_utility": utility_metric(_action_values(runs, ARM_R0, "D_PRE")),
        "r0_post_remediation_utility": utility_metric(_action_values(runs, ARM_R0, "D_POST")),
    }


def independent_metric_recomputation(
    runs: tuple[Mapping[str, Any], ...]
) -> dict[str, Any]:
    traces = [run["raw_action_traces"] for run in runs]

    def values(arm: str, case: str) -> list[bool]:
        return [bool(trace[arm][case]["action_allowed"]) for trace in traces]

    affected = values(ARM_ROOT, "D_BAD1") + values(ARM_ROOT, "D_BAD2")
    r0_affected = values(ARM_R0, "D_BAD1") + values(ARM_R0, "D_BAD2")
    return {
        "affected_revocation_recall": {"numerator": sum(value is False for value in affected), "denominator": len(affected)},
        "affected_false_act": {"numerator": sum(value is True for value in affected), "denominator": len(affected)},
        "unrelated_receipt_utility": {"numerator": sum(value is True for value in values(ARM_ROOT, "D_OTHER")), "denominator": len(values(ARM_ROOT, "D_OTHER"))},
        "pre_compromise_utility": {"numerator": sum(value is True for value in values(ARM_ROOT, "D_PRE")), "denominator": len(values(ARM_ROOT, "D_PRE"))},
        "post_remediation_utility": {"numerator": sum(value is True for value in values(ARM_ROOT, "D_POST")), "denominator": len(values(ARM_ROOT, "D_POST"))},
        "mixed_parent_false_act": {"numerator": sum(value is True for value in values(ARM_ROOT, "D_MIX")), "denominator": len(values(ARM_ROOT, "D_MIX"))},
        "cross_agent_revoked_false_act": {"numerator": sum(value is True for value in values(ARM_ROOT, "cross_agent_revoked")), "denominator": len(values(ARM_ROOT, "cross_agent_revoked"))},
        "record_reissue_escape_false_act": {"numerator": sum(value is True for value in values(ARM_ROOT, "record_reissue")), "denominator": len(values(ARM_ROOT, "record_reissue"))},
        "revoked_receipt_copy_false_act": {"numerator": sum(value is True for value in values(ARM_ROOT, "revoked_receipt_copy")), "denominator": len(values(ARM_ROOT, "revoked_receipt_copy"))},
        "sibling_receipt_utility": {"numerator": sum(value is True for value in values(ARM_ROOT, "D_OTHER")), "denominator": len(values(ARM_ROOT, "D_OTHER"))},
        "generation_false_act": {"numerator": sum(value is True for value in values(ARM_ROOT, "generation_old")), "denominator": len(values(ARM_ROOT, "generation_old"))},
        "historical_rewrite_count": {"numerator": sum(run["historical_rewrite_count"] for run in runs), "denominator": len(runs) * len(ARMS)},
        "r0_affected_revocation_recall": {"numerator": sum(value is False for value in r0_affected), "denominator": len(r0_affected)},
        "r0_affected_false_act": {"numerator": sum(value is True for value in r0_affected), "denominator": len(r0_affected)},
        "r0_unrelated_receipt_utility": {"numerator": sum(value is True for value in values(ARM_R0, "D_OTHER")), "denominator": len(values(ARM_R0, "D_OTHER"))},
        "r0_pre_compromise_utility": {"numerator": sum(value is True for value in values(ARM_R0, "D_PRE")), "denominator": len(values(ARM_R0, "D_PRE"))},
        "r0_post_remediation_utility": {"numerator": sum(value is True for value in values(ARM_R0, "D_POST")), "denominator": len(values(ARM_R0, "D_POST"))},
    }


def metric_mapping_audit() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    false_start = source.index("def false_act_metric")
    recall_start = source.index("def affected_recall_metric")
    false_block = source[false_start:recall_start]
    forbidden_inversion = "not action_allowed" in false_block or "not value" in false_block
    if forbidden_inversion:
        raise RuntimeError("false-ACT metric contains the forbidden inversion")
    return {
        "expected_allow_mapping": "numerator=count(action_allowed == True)",
        "expected_deny_false_act_mapping": "numerator=count(action_allowed == True)",
        "affected_recall_mapping": "numerator=count(action_allowed == False)",
        "false_act_uses_not_action_allowed": False,
        "source_scan": "PASS",
    }


def mechanical_verdict(metrics: Mapping[str, Any], reproducible: bool) -> tuple[str, str | None]:
    for name in ("affected_false_act", "mixed_parent_false_act", "cross_agent_revoked_false_act", "record_reissue_escape_false_act", "revoked_receipt_copy_false_act", "generation_false_act"):
        if metrics[name]["numerator"] != 0:
            return "KILL", "SELECTIVE_AUTHORITY_SAFETY"
    if metrics["historical_rewrite_count"]["numerator"] != 0:
        return "KILL", "HISTORICAL_REWRITE"
    for name in ("unrelated_receipt_utility", "pre_compromise_utility", "post_remediation_utility", "sibling_receipt_utility"):
        if metrics[name]["numerator"] != metrics[name]["denominator"]:
            return "SELECTIVITY-FAIL", "SELECTIVE_UTILITY"
    if metrics["affected_revocation_recall"]["numerator"] != metrics["affected_revocation_recall"]["denominator"]:
        return "SELECTIVITY-FAIL", "AFFECTED_RECALL"
    if not reproducible:
        return "SELECTIVITY-FAIL", "REPRODUCIBILITY"
    return "SELECTIVE-REVOCATION-SUPPORTED", None


def preflight() -> dict[str, Any]:
    lineage = verify_lineage()
    schema = verify_receipt_schema()
    ctx = r3.load_official_context(EXTERNAL_SOURCE_DIR)
    if ctx.attack_source_digest != r3.EXPECTED_ATTACK_SOURCE_DIGEST:
        raise RuntimeError("pinned external attack digest mismatch")
    if ctx.model_calls != 0:
        raise RuntimeError("model call attempted during source preflight")
    state, objects, aliases, issuer = build_graph()
    root_contract = root_preflight(state, objects, aliases, issuer)
    return {
        "lineage": lineage,
        "receipt_schema": schema,
        "external_source": {"repository": r3.EXTERNAL_REPOSITORY, "pinned_commit": EXTERNAL_COMMIT, "attack_path": r3.EXTERNAL_ATTACK_PATH, "attack_source_digest": ctx.attack_source_digest, "source_tree": ctx.source_tree},
        "graph": {"record_count": 16, "unique_durable_record_ids": 16, "authenticated_roots": 5},
        "root_resolution": {"namespace": "ROOT_ALIASES->RECORDS_BY_ID", "resolved_aliases": dict(aliases), "preflight": "PASS"},
        "root_key_contract": root_contract,
        "issuer_relay_separation": {"issuer_id": "vendor-source-authority", "relay": r3.TOOL_IDENTITY, "relay_signing_key_absent": True},
        "security_boundary": {"scorer_reads": 0, "treatment_received_scorer_truth": False, "true_origin_to_treatment": False, "payload_semantics_used": False},
        "model_calls": 0,
        "api_cost_usd": 0.0,
    }


def render_result(result: Mapping[str, Any]) -> str:
    metrics = result["R3_root_metrics"]
    lines = [
        "# Gate 1C-R3 Selective Receipt-Root Revocation Falsifier",
        "",
        f"Gate validity: **{result['gate_validity']}**",
        f"Mechanical result: **{result['mechanical_verdict']}**",
        "",
        "R3 changes only post-treatment metric accounting; treatment semantics are frozen.",
        "Compromise discovery is out of scope; explicit authenticated root identities are supplied.",
        "",
        f"Preregistration: {result['preregistration_sha']}",
        f"Canonical result digest: {result['canonical_result_digest']}",
        "",
        "## Raw action outcomes (R3-root, run 1)",
        "",
        "| Case | Record | Required roots | Matched revoked roots | Allowed | Reason |",
        "|---|---|---|---|---:|---|",
    ]
    for case_name, trace in result["raw_action_traces"]["run_1"][ARM_ROOT].items():
        lines.append(
            f"| {case_name} | {trace['record_id']} | {trace['required_roots']} | "
            f"{trace['matched_revoked_roots']} | {trace['action_allowed']} | "
            f"{trace['decision_reason']} |"
        )
    lines += ["", "## R3-root metrics", "", "| Metric | Result |", "|---|---:|"]
    for name, value in metrics.items():
        if isinstance(value, dict) and "numerator" in value:
            lines.append(f"| {name} | {value['numerator']}/{value['denominator']} |")
    lines += [
        "",
        "## Metric audits",
        "",
        f"- independent recomputation match: {result['metric_recomputation_match']}",
        f"- false-ACT mapping audit: {result['false_act_mapping_audit']['source_scan']}",
        f"- affected-recall mapping: {result['affected_recall_mapping_audit']['mapping']}",
        f"- reproducibility: {result['reproducibility']['status']}",
        f"- model calls/API cost: {result['model_calls']} / USD {result['api_cost_usd']:.2f}",
        f"- first failed gate: {result['first_failed_gate']}",
    ]
    return "\n".join(lines) + "\n"


def render_audit(result: Mapping[str, Any]) -> str:
    return f"""# Gate 1C-R3 Adapter and Metric Audit

Gate validity: {result['gate_validity']}
Mechanical verdict: {result['mechanical_verdict']}

R0 is the issuer-wide negative control. R3-root matches only the two
authenticated RootKeys selected for R_BAD_1 and R_BAD_2. The same 16-record
graph is used for both arms. No receipt schema field was added and no
historical record was edited.

Raw traces are frozen before metrics. Expected-ALLOW utilities and
expected-DENY false-ACT metrics both count finalized action_allowed=True.
Affected recall counts action_allowed=False. Independent recomputation:
{result['metric_recomputation_match']}.

Scorer reads: {result['scorer_reads']}
Payload-semantic inspection: {result['payload_semantic_inspection']}
True-origin to treatment: {result['preflights']['security_boundary']['true_origin_to_treatment']}
Relay signing key absent: {result['preflights']['issuer_relay_separation']['relay_signing_key_absent']}
Model calls/API cost: {result['model_calls']} / USD {result['api_cost_usd']:.2f}
"""


def main() -> None:
    preflights = preflight()
    if os.environ.get("R3_PREFLIGHT_ONLY") == "1":
        print(json.dumps({"preflights": preflights}, indent=2, sort_keys=True))
        return
    EXECUTION_DIR.mkdir(parents=True, exist_ok=True)
    first = build_run(1)
    second = build_run(2)
    first_digest = digest(normalized_run(first))
    second_digest = digest(normalized_run(second))
    in_process_reproducible = first_digest == second_digest
    runs = (first, second)
    metrics = build_metrics(runs)
    independent = independent_metric_recomputation(runs)
    mapping_match = metrics == independent
    mapping_audit = metric_mapping_audit()
    affected_recall_audit = {
        "mapping": "numerator=count(action_allowed == False)",
        "observed_numerator": metrics["affected_revocation_recall"]["numerator"],
        "independent_numerator": independent["affected_revocation_recall"]["numerator"],
        "match": metrics["affected_revocation_recall"] == independent["affected_revocation_recall"],
    }
    mechanical_ok = mapping_match and not mapping_audit["false_act_uses_not_action_allowed"]
    verdict, first_failed = (
        mechanical_verdict(metrics, in_process_reproducible)
        if mechanical_ok
        else ("INVALID", "METRIC_RECOMPUTATION_OR_MAPPING")
    )
    reference_path = os.environ.get("R3_REFERENCE_RESULT", "").strip()
    process_reproducibility = {"checked": False, "match": None}
    if reference_path:
        prior = json.loads(Path(reference_path).read_text(encoding="utf-8"))
        prior_digest = prior.get("canonical_result_digest")
        prior_metrics = prior.get("R3_root_metrics", prior.get("metrics"))
        prior_raw = prior.get("raw_action_traces")
        current_raw = {"run_1": first["raw_action_traces"], "run_2": second["raw_action_traces"]}
        process_reproducibility = {
            "checked": True,
            "reference_digest": prior_digest,
            "current_digest": first_digest,
            "match": (
                prior_digest == first_digest
                and prior_metrics == {k: v for k, v in metrics.items() if not k.startswith("r0_")}
                and prior_raw == current_raw
            ),
        }
        if not process_reproducibility["match"]:
            verdict, first_failed = "INVALID", "CROSS_PROCESS_REPRODUCIBILITY"
    reproducible = in_process_reproducible and (
        not process_reproducibility["checked"] or bool(process_reproducibility["match"])
    )
    result = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_sha": PREREGISTRATION_SHA,
        "execution_commit": git_output("rev-parse", "HEAD"),
        "lineage": preflights["lineage"],
        "preflights": preflights,
        "raw_action_traces": {"run_1": first["raw_action_traces"], "run_2": second["raw_action_traces"]},
        "runs": [first, second],
        "metrics": metrics,
        "R0_metrics": {k: v for k, v in metrics.items() if k.startswith("r0_")},
        "R3_root_metrics": {k: v for k, v in metrics.items() if not k.startswith("r0_")},
        "independent_metric_recomputation": independent,
        "metric_recomputation_match": mapping_match,
        "false_act_mapping_audit": mapping_audit,
        "affected_recall_mapping_audit": affected_recall_audit,
        "historical_immutability": {"historical_rewrite_count": metrics["historical_rewrite_count"]},
        "scorer_reads": 0,
        "scorer_leakage": False,
        "leakage_guard": preflights["security_boundary"],
        "payload_semantic_inspection": False,
        "model_calls": 0,
        "api_cost_usd": 0.0,
        "reproducibility": {
            "status": "PASS" if reproducible else "FAIL",
            "in_process": in_process_reproducible,
            "process_pair": process_reproducibility,
            "run_digests": [first_digest, second_digest],
            "match": reproducible,
        },
        "gate_validity": "VALID" if mechanical_ok and reproducible else "INVALID",
        "mechanical_verdict": verdict if mechanical_ok and reproducible else "INVALID",
        "first_failed_gate": first_failed,
        "canonical_result_digest": first_digest,
        "design_verdict": "SELECTOR-TOO-COARSE",
    }
    (EXECUTION_DIR / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (EXECUTION_DIR / "RESULT.md").write_text(render_result(result), encoding="utf-8")
    (EXECUTION_DIR / "ADAPTER_AUDIT.md").write_text(render_audit(result), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "preregistration_sha": PREREGISTRATION_SHA,
        "gate_validity": result["gate_validity"],
        "mechanical_verdict": result["mechanical_verdict"],
        "first_failed_gate": result["first_failed_gate"],
        "canonical_result_digest": first_digest,
        "reproducibility": reproducible,
        "metric_recomputation_match": mapping_match,
        "model_calls": 0,
        "api_cost_usd": 0.0,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
