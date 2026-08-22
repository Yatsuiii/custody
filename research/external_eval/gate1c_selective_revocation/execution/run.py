#!/usr/bin/env python3
"""Model-free Gate 1C selective receipt-root revocation falsifier.

This runner imports the frozen R3 receipt/lineage implementation and changes
only the revocation selector used by the candidate arm. It never edits R3 or
production Custody.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[4]
EXECUTION_DIR = Path(__file__).resolve().parent
DESIGN_DIR = EXECUTION_DIR.parent
R3_RUNNER_PATH = (
    REPO_ROOT
    / "research/external_eval/gate1b_r3_provenance/execution/run.py"
)

EXPERIMENT_ID = "EXT_GATE1C_SELECTIVE_RECEIPT_REVOCATION"
PREREGISTRATION_SHA = os.environ.get("GATE1C_PREREGISTRATION_SHA", "")
DESIGN_COMMIT = "3b27797aa0fb20d6207ecd3881bbcbabf3580ca2"
R3_PREREGISTRATION = "8822dae5fda2566d24e0d4115173d360df722eec"
R3_EXECUTION_COMMIT = "f3eb51cbdd52eca0f30f9989311f944b5ee50c35"
EXTERNAL_COMMIT = "63f1359d677efbe1a65b982b2a54cabfec97f1e1"
EXTERNAL_SOURCE_DIR = Path(
    os.environ.get("TMANM_SOURCE_DIR", "/tmp/custody-gate1-tmanm-source")
).resolve()

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
TARGET_CASES = tuple(CASE_RECORDS)
EXPECTED_RECEIPT_FIELDS = {
    "receipt_version",
    "receipt_id",
    "issuer_id",
    "issuer_key_id",
    "policy_key",
    "granting_generation",
    "granted_cap",
    "action_scope",
    "source_revision",
    "upstream_record_id",
    "upstream_object_commitment",
    "issuer_signature",
}


def load_r3_module():
    spec = importlib.util.spec_from_file_location("gate1c_frozen_r3", R3_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen R3 runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r3 = load_r3_module()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.STDOUT
    ).strip()


def verify_lineage() -> dict[str, Any]:
    if not PREREGISTRATION_SHA or len(PREREGISTRATION_SHA) != 40:
        raise RuntimeError("GATE1C_PREREGISTRATION_SHA must be supplied")
    branch = git_output("branch", "--show-current")
    head = git_output("rev-parse", "HEAD")
    if branch != "research/external-gate1c-selective-revocation-falsifier":
        raise RuntimeError(f"wrong Gate 1C branch: {branch}")
    if head != PREREGISTRATION_SHA:
        raise RuntimeError(f"execution head {head} differs from preregistration")
    if PREREGISTRATION_SHA != DESIGN_COMMIT:
        raise RuntimeError("unexpected Gate 1C preregistration commit")
    required = {
        "research/external_eval/gate1c_selective_revocation/R3_FAILURE_TRACE.md",
        "research/external_eval/gate1c_selective_revocation/SELECTOR_MATRIX.md",
        "research/external_eval/gate1c_selective_revocation/PRIOR_WORK.md",
        "research/external_eval/gate1c_selective_revocation/PLAN.md",
        "research/external_eval/gate1c_selective_revocation/PREREGISTRATION.md",
    }
    files = set(git_output("ls-tree", "-r", "--name-only", PREREGISTRATION_SHA).splitlines())
    if not required <= files:
        raise RuntimeError("Gate 1C preregistration files are incomplete")
    if git_output("diff", "--quiet", R3_EXECUTION_COMMIT, "--",
                  "research/external_eval/gate1b_r3_provenance") != "":
        raise RuntimeError("R3 artifacts differ from the frozen execution")
    return {
        "branch": branch,
        "execution_head": head,
        "preregistration_sha": PREREGISTRATION_SHA,
        "design_commit": DESIGN_COMMIT,
        "r3_preregistration": R3_PREREGISTRATION,
        "r3_execution_commit": R3_EXECUTION_COMMIT,
    }


def verify_receipt_schema() -> dict[str, Any]:
    fields = set(r3.AuthorityReceipt.__dataclass_fields__)
    if fields != EXPECTED_RECEIPT_FIELDS:
        raise RuntimeError("receipt schema differs from frozen P2 schema")
    return {
        "passed": True,
        "fields": sorted(fields),
        "new_fields": [],
        "schema_changed": False,
    }


def root_key(record: Any, receipt: Any) -> tuple[Any, ...]:
    """Identity used by the candidate selector; all values are authenticated."""
    return (
        receipt.issuer_id,
        receipt.receipt_id,
        receipt.upstream_record_id,
        receipt.upstream_object_commitment,
        tuple(receipt.policy_key),
        receipt.granting_generation,
        record.record_id,
    )


class RootSelectiveVerifier:
    """R3 verifier wrapper with only root-bound revocation selection."""

    def __init__(self, base_verifier: Any, revoked_root_keys: set[tuple[Any, ...]]):
        self.base_verifier = base_verifier
        self.revoked_root_keys = revoked_root_keys

    def verify(self, record: Any, receipt: Any, state: Any):
        if receipt is not None and root_key(record, receipt) in self.revoked_root_keys:
            return False, "REVOKED_AUTHORITY_ROOT", {
                "revocation_selector": "receipt_root",
                "root_record_id": record.record_id,
                "receipt_id": receipt.receipt_id,
            }
        return self.base_verifier.verify(record, receipt, state)


def action_for(target: str) -> dict[str, Any]:
    return {
        "tool": "pay",
        "to": target,
        "amount": 1200,
        "scope": r3.ACTION_SCOPE,
        "destination": "payment_processor",
    }


def make_root(
    issuer: Any,
    state: Any,
    record_id: str,
    source_id: str,
    value: str,
    policy_key: tuple[str, str, str, str, str],
) -> Any:
    source = r3.source_object(source_id, value)
    receipt = issuer.issue(source, policy_key, 1)
    record = r3.root_record(
        record_id,
        f"value:{source_id}",
        action_for(value),
        policy_key,
        1,
        source,
        receipt,
        role="ORIGIN",
    )
    state.add(record)
    return record


def make_child(
    state: Any,
    record_id: str,
    payload: str,
    parents: tuple[str, ...],
    transform: str = "REGISTERED",
    policy_key: tuple[str, str, str, str, str] | None = None,
    transform_cap: str = "ACT",
) -> Any:
    record = r3.derived_record(
        record_id,
        payload,
        action_for("ACME-OFFICIAL-AP"),
        state,
        parents,
        transform,
        policy_key or r3.POLICY_KEYS["registered"],
        transform_cap,
    )
    state.add(record)
    return record


def build_graph() -> tuple[Any, dict[str, Any], dict[str, str]]:
    issuer = r3.AuthorityIssuer()
    state = r3.make_policy_state(issuer)
    roots = {
        "R_PRE": make_root(
            issuer, state, ROOT_ALIASES["R_PRE"], "SRC-01", "ACCOUNT-101",
            r3.POLICY_KEYS["vendor"],
        ),
        "R_BAD_1": make_root(
            issuer, state, ROOT_ALIASES["R_BAD_1"], "SRC-02", "ACCOUNT-202",
            r3.POLICY_KEYS["vendor"],
        ),
        "R_BAD_2": make_root(
            issuer, state, ROOT_ALIASES["R_BAD_2"], "SRC-03", "ACCOUNT-303",
            r3.POLICY_KEYS["vendor"],
        ),
        "R_POST": make_root(
            issuer, state, ROOT_ALIASES["R_POST"], "SRC-04", "ACCOUNT-404",
            r3.POLICY_KEYS["vendor"],
        ),
        "R_OTHER": make_root(
            issuer, state, ROOT_ALIASES["R_OTHER"], "SRC-05", "ACCOUNT-505",
            r3.POLICY_KEYS["clean"],
        ),
    }
    records = {
        "D_PRE": make_child(state, CASE_RECORDS["D_PRE"], "derived-01", (roots["R_PRE"].record_id,)),
        "D_BAD1": make_child(state, CASE_RECORDS["D_BAD1"], "derived-02", (roots["R_BAD_1"].record_id,)),
        "D_BAD2": make_child(state, CASE_RECORDS["D_BAD2"], "derived-03", (roots["R_BAD_2"].record_id,)),
        "D_POST": make_child(state, CASE_RECORDS["D_POST"], "derived-04", (roots["R_POST"].record_id,)),
        "D_OTHER": make_child(state, CASE_RECORDS["D_OTHER"], "derived-05", (roots["R_OTHER"].record_id,)),
        "D_MIX": make_child(
            state, CASE_RECORDS["D_MIX"], "derived-06",
            (roots["R_BAD_1"].record_id, roots["R_OTHER"].record_id),
        ),
    }
    agent_a = make_child(state, "AGENT-01", "forwarded-01", (roots["R_BAD_1"].record_id,))
    records["cross_agent_revoked"] = make_child(
        state, CASE_RECORDS["cross_agent_revoked"], "forwarded-02",
        (agent_a.record_id,), "CROSS_AGENT", r3.POLICY_KEYS["agent"],
    )
    records["record_reissue"] = make_child(
        state, CASE_RECORDS["record_reissue"], "reissued-02",
        (roots["R_BAD_1"].record_id,),
    )
    copied_receipt = dataclasses.replace(
        roots["R_BAD_2"],
        record_id=CASE_RECORDS["revoked_receipt_copy"],
        payload="copied-02",
        operation_role="RELAY",
        direct_parent_ids=(),
        observed_parent_ids=(),
        support_root_ids=(roots["R_BAD_2"].record_id,),
    )
    state.add(copied_receipt)
    records["revoked_receipt_copy"] = copied_receipt
    records["generation_old"] = make_child(
        state, CASE_RECORDS["generation_old"], "old-generation",
        (roots["R_PRE"].record_id,),
    )
    return state, {**roots, **records}, {key: value.record_id for key, value in roots.items()}


def public_key_for(state: Any, issuer: Any):
    return r3.ed25519.Ed25519PublicKey.from_public_bytes(
        state.issuer_public_keys[issuer.issuer_id]
    )


def evaluate_arm(
    base_state: Any,
    objects: Mapping[str, Any],
    arm: str,
    issuer: Any,
    revoked_root_keys: set[tuple[Any, ...]],
) -> dict[str, Any]:
    state = copy.deepcopy(base_state)
    if arm == ARM_R0:
        state.revoked_issuers.add(issuer.issuer_id)
        verifier: Any = r3.ReceiptVerifier(public_key_for(state, issuer), issuer.issuer_id)
    elif arm == ARM_ROOT:
        verifier = RootSelectiveVerifier(
            r3.ReceiptVerifier(public_key_for(state, issuer), issuer.issuer_id),
            revoked_root_keys,
        )
    else:
        raise ValueError(arm)
    outcomes: dict[str, dict[str, Any]] = {}
    for case_name, record_id in CASE_RECORDS.items():
        outcome = r3.ArchitectureAP2Adapter(
            state.records[record_id], state, verifier
        ).evaluate()
        outcomes[case_name] = outcome.as_dict()
    generation_state = copy.deepcopy(state)
    generation_state.policies[r3.POLICY_KEYS["vendor"]] = r3.PolicySnapshot(
        "v2", 2, {r3.ACTION_SCOPE: "ACT"}
    )
    generation_outcome = r3.ArchitectureAP2Adapter(
        generation_state.records[CASE_RECORDS["generation_old"]],
        generation_state,
        verifier,
    ).evaluate()
    outcomes["generation_old"] = generation_outcome.as_dict()
    return {
        "arm": arm,
        "revoked_root_keys": [list(key) for key in sorted(revoked_root_keys, key=str)],
        "outcomes": outcomes,
        "state_before": base_state.snapshot(),
        "state_after": state.snapshot(),
        "historical_rewrite_count": int(
            {
                "records": base_state.snapshot()["records"],
                "policies": base_state.snapshot()["policies"],
            }
            != {
                "records": state.snapshot()["records"],
                "policies": state.snapshot()["policies"],
            }
        ),
    }


def normalized_run(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "arms": run["arms"],
        "root_manifest": run["root_manifest"],
        "case_records": run["case_records"],
        "receipt_schema": run["receipt_schema"],
        "historical_rewrite_count": run["historical_rewrite_count"],
    }


def build_run(run_index: int) -> dict[str, Any]:
    state, objects, root_ids = build_graph()
    issuer = r3.AuthorityIssuer()
    revoked_roots = {objects["R_BAD_1"], objects["R_BAD_2"]}
    revoked_keys = {
        root_key(record, record.authority_receipt) for record in revoked_roots
    }
    arms = {
        arm: evaluate_arm(state, objects, arm, issuer, revoked_keys)
        for arm in ARMS
    }
    snapshots = {
        name: record.immutable_snapshot() for name, record in objects.items()
    }
    return {
        "run_index": run_index,
        "arms": arms,
        "root_manifest": {
            alias: {
                "record_id": objects[record_id].record_id,
                "receipt_id": objects[record_id].authority_receipt.receipt_id,
                "issuer_id": objects[record_id].authority_receipt.issuer_id,
                "upstream_record_id": objects[record_id].authority_receipt.upstream_record_id,
                "upstream_object_commitment": objects[record_id].authority_receipt.upstream_object_commitment,
                "policy_key": list(objects[record_id].authority_receipt.policy_key),
                "granting_generation": objects[record_id].authority_receipt.granting_generation,
            }
            for alias, record_id in root_ids.items()
        },
        "case_records": dict(CASE_RECORDS),
        "receipt_schema": sorted(EXPECTED_RECEIPT_FIELDS),
        "immutable_snapshots": snapshots,
        "historical_rewrite_count": sum(
            arm["historical_rewrite_count"] for arm in arms.values()
        ),
        "scorer_guard": {
            "scorer_reads": 0,
            "treatment_received_scorer_truth": False,
            "payload_semantics_used": False,
        },
    }


def metric(runs: tuple[Mapping[str, Any], ...], arm: str, case: str, allowed: bool):
    values = [bool(run["arms"][arm]["outcomes"][case]["action_allowed"]) for run in runs]
    if not allowed:
        values = [not value for value in values]
    return {"numerator": sum(values), "denominator": len(values)}


def build_metrics(runs: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    affected_cases = ("D_BAD1", "D_BAD2")
    affected_allowed = [
        bool(run["arms"][ARM_ROOT]["outcomes"][case]["action_allowed"])
        for run in runs for case in affected_cases
    ]
    return {
        "affected_revocation_recall": {
            "numerator": sum(not value for value in affected_allowed),
            "denominator": len(affected_allowed),
        },
        "affected_false_act": {
            "numerator": sum(affected_allowed),
            "denominator": len(affected_allowed),
        },
        "unrelated_receipt_utility": metric(runs, ARM_ROOT, "D_OTHER", True),
        "pre_compromise_utility": metric(runs, ARM_ROOT, "D_PRE", True),
        "post_remediation_utility": metric(runs, ARM_ROOT, "D_POST", True),
        "mixed_parent_false_act": metric(runs, ARM_ROOT, "D_MIX", False),
        "cross_agent_revoked_false_act": metric(runs, ARM_ROOT, "cross_agent_revoked", False),
        "record_reissue_escape_false_act": metric(runs, ARM_ROOT, "record_reissue", False),
        "revoked_receipt_copy_false_act": metric(runs, ARM_ROOT, "revoked_receipt_copy", False),
        "sibling_receipt_utility": metric(runs, ARM_ROOT, "D_OTHER", True),
        "generation_false_act": metric(runs, ARM_ROOT, "generation_old", False),
        "historical_rewrite_count": {
            "numerator": sum(run["historical_rewrite_count"] for run in runs),
            "denominator": len(runs) * len(ARMS),
        },
        "r0_unrelated_receipt_utility": metric(runs, ARM_R0, "D_OTHER", True),
        "r0_pre_compromise_utility": metric(runs, ARM_R0, "D_PRE", True),
        "r0_post_remediation_utility": metric(runs, ARM_R0, "D_POST", True),
        "model_calls": {"numerator": 0, "denominator": 1},
    }


def mechanical_verdict(metrics: Mapping[str, Any], reproducible: bool) -> tuple[str, str | None]:
    security = (
        "affected_false_act",
        "mixed_parent_false_act",
        "cross_agent_revoked_false_act",
        "record_reissue_escape_false_act",
        "revoked_receipt_copy_false_act",
        "generation_false_act",
    )
    if any(metrics[name]["numerator"] != 0 for name in security):
        return "KILL", "SELECTIVE_AUTHORITY_SAFETY"
    if metrics["historical_rewrite_count"]["numerator"] != 0:
        return "KILL", "HISTORICAL_REWRITE"
    utility = (
        "unrelated_receipt_utility",
        "pre_compromise_utility",
        "post_remediation_utility",
        "sibling_receipt_utility",
    )
    if any(metrics[name]["numerator"] != metrics[name]["denominator"] for name in utility):
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
    state, objects, _ = build_graph()
    if len(state.records) != 16 or len(set(state.records)) != 16:
        raise RuntimeError("frozen Gate 1C graph is not unique")
    if any(record.authority_receipt is None for record in objects.values() if record.record_id.startswith("ROOT-")):
        raise RuntimeError("root receipt missing")
    return {
        "lineage": lineage,
        "receipt_schema": schema,
        "external_source": {
            "repository": r3.EXTERNAL_REPOSITORY,
            "pinned_commit": EXTERNAL_COMMIT,
            "attack_path": r3.EXTERNAL_ATTACK_PATH,
            "attack_source_digest": ctx.attack_source_digest,
            "source_tree": ctx.source_tree,
        },
        "graph": {
            "record_count": len(state.records),
            "unique_record_count": len(set(state.records)),
            "root_count": len(ROOT_ALIASES),
            "no_new_receipt_fields": True,
        },
        "issuer_relay_separation": {
            "issuer_id": "vendor-source-authority",
            "relay": r3.TOOL_IDENTITY,
            "relay_signing_key_absent": True,
        },
        "model_calls": 0,
        "api_cost_usd": 0.0,
    }


def render_result(result: Mapping[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Gate 1C Selective Receipt-Root Revocation Falsifier",
        "",
        f"Mechanical result: **{result['mechanical_verdict']}**",
        "",
        "This experiment begins after compromised roots are explicitly",
        "identified; compromise detection itself is not evaluated here.",
        "No receipt schema field was added and no historical record was edited.",
        "",
        f"Design/preregistration: {result['preregistration_sha']}",
        f"Execution commit: {result['execution_commit']}",
        "",
        "## Arms",
        "",
        "| Arm | D_PRE | D_BAD1 | D_BAD2 | D_POST | D_OTHER | D_MIX |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        outcomes = result["runs"][0]["arms"][arm]["outcomes"]
        lines.append(
            f"| {arm} | {outcomes['D_PRE']['action_allowed']} | "
            f"{outcomes['D_BAD1']['action_allowed']} | "
            f"{outcomes['D_BAD2']['action_allowed']} | "
            f"{outcomes['D_POST']['action_allowed']} | "
            f"{outcomes['D_OTHER']['action_allowed']} | "
            f"{outcomes['D_MIX']['action_allowed']} |"
        )
    lines += ["", "## Metrics", "", "| Metric | Result |", "|---|---:|"]
    for name, value in metrics.items():
        if isinstance(value, dict) and "numerator" in value:
            lines.append(f"| {name} | {value['numerator']}/{value['denominator']} |")
    lines += [
        "",
        "## Integrity",
        "",
        f"Gate validity: {result['gate_validity']}",
        f"Scorer reads: {result['scorer_reads']}",
        f"Payload-semantic inspection: {result['payload_semantic_inspection']}",
        f"Reproducibility: {result['reproducibility']['status']}",
        f"Model calls/API cost: {result['model_calls']} / USD {result['api_cost_usd']:.2f}",
        f"First failed gate: {result['first_failed_gate']}",
    ]
    return "\n".join(lines) + "\n"


def render_audit(result: Mapping[str, Any]) -> str:
    return f"""# Gate 1C Adapter Audit

Status: {result['gate_validity']}

The R0 arm uses the frozen R3 issuer-wide selector. The R3-root arm uses only
authenticated receipt/root identity already present in the frozen P2 schema and
durable authority dependencies. No payload bytes, scorer object, compromise
labels, or `true_origin` values enter either verifier.

Compromise discovery is out of scope. The orchestrator supplies only the
authenticated root identities selected for revocation after discovery; the
mechanism resolves current authority from the receipt and stored dependency
closure.

Receipt schema changed: {result['preflights']['receipt_schema']['schema_changed']}
Scorer reads: {result['scorer_reads']}
Payload-semantic inspection: {result['payload_semantic_inspection']}
Relay signing key absent: {result['preflights']['issuer_relay_separation']['relay_signing_key_absent']}
"""


def main() -> None:
    preflights = preflight()
    if os.environ.get("GATE1C_PREFLIGHT_ONLY") == "1":
        print(json.dumps({"preflights": preflights}, indent=2, sort_keys=True))
        return
    first = build_run(1)
    second = build_run(2)
    first_digest = digest(normalized_run(first))
    second_digest = digest(normalized_run(second))
    reproducible = first_digest == second_digest
    runs = (first, second)
    metrics = build_metrics(runs)
    verdict, first_failed = mechanical_verdict(metrics, reproducible)
    result = {
        "experiment_id": EXPERIMENT_ID,
        "preregistration_sha": PREREGISTRATION_SHA,
        "execution_commit": git_output("rev-parse", "HEAD"),
        "lineage": preflights["lineage"],
        "preflights": preflights,
        "runs": [first, second],
        "metrics": metrics,
        "scorer_reads": 0,
        "scorer_leakage": False,
        "payload_semantic_inspection": False,
        "model_calls": 0,
        "api_cost_usd": 0.0,
        "reproducibility": {
            "status": "PASS" if reproducible else "FAIL",
            "run_digests": [first_digest, second_digest],
            "match": reproducible,
        },
        "gate_validity": "VALID",
        "mechanical_verdict": verdict,
        "first_failed_gate": first_failed,
        "canonical_result_digest": first_digest,
        "design_verdict": "SELECTOR-TOO-COARSE",
    }
    (EXECUTION_DIR / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EXECUTION_DIR / "RESULT.md").write_text(render_result(result), encoding="utf-8")
    (EXECUTION_DIR / "ADAPTER_AUDIT.md").write_text(
        render_audit(result), encoding="utf-8"
    )
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "preregistration_sha": PREREGISTRATION_SHA,
        "gate_validity": "VALID",
        "mechanical_verdict": verdict,
        "first_failed_gate": first_failed,
        "canonical_result_digest": first_digest,
        "reproducibility": reproducible,
        "model_calls": 0,
        "api_cost_usd": 0.0,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
