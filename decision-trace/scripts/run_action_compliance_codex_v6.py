#!/usr/bin/env python3
"""Host-shell V6 runner for the DecisionTrace action-compliance benchmark.

This is intentionally a normal-Python entry point.  It invokes the installed
``codex`` executable directly with ``subprocess``; it must be run from a host
shell, outside a parent Codex tool sandbox.  ``--dry-run`` never invokes Codex.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any

import action_compliance_v4_storage as storage_module
import run_action_compliance_codex as runner


ROOT = runner.ROOT
MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "high"
APPROVAL_POLICY = "never"
SANDBOX = "workspace-write"
V6_SEED = 2026082602
REPETITIONS = 3
DEFAULT_CONCURRENCY = 2
PROVIDER_HOST = "chatgpt.com"
PROVIDER_PORT = 443


def _write_json_atomic(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if private:
        temporary.chmod(0o600)
    temporary.replace(path)
    if private:
        path.chmod(0o600)


def _codex_version(codex_path: str) -> str:
    process = subprocess.run(
        [codex_path, "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = (process.stdout + process.stderr).strip()
    if process.returncode != 0:
        raise RuntimeError(f"{codex_path} --version failed: {output}")
    return output


def _provider_reachability() -> dict[str, Any]:
    result: dict[str, Any] = {
        "host": PROVIDER_HOST,
        "port": PROVIDER_PORT,
        "dns_ok": False,
        "tcp_connect_ok": False,
    }
    try:
        addresses = socket.getaddrinfo(PROVIDER_HOST, PROVIDER_PORT, type=socket.SOCK_STREAM)
        result["dns_ok"] = bool(addresses)
        result["address_count"] = len(addresses)
    except OSError as error:
        result["error"] = f"DNS: {error}"
        return result
    try:
        with socket.create_connection((PROVIDER_HOST, PROVIDER_PORT), timeout=5):
            result["tcp_connect_ok"] = True
    except OSError as error:
        result["error"] = f"TCP: {error}"
    return result


def _disk_snapshot(path: Path) -> dict[str, Any]:
    target = path if path.exists() else path.parent
    usage = shutil.disk_usage(target)
    stat = os.statvfs(target)
    return {
        "path": str(target),
        "free_bytes": usage.free,
        "free_gib": round(usage.free / 1024**3, 3),
        "total_bytes": usage.total,
        "free_inodes": stat.f_bavail,
        "total_inodes": stat.f_blocks,
    }


def _launch_snapshot(storage_root: Path, *, require_provider: bool) -> dict[str, Any]:
    codex_path = shutil.which("codex")
    if codex_path is None:
        raise RuntimeError("codex is not on PATH")
    version = _codex_version(codex_path)
    provider = _provider_reachability()
    network_marker_present = "CODEX_SANDBOX_NETWORK_DISABLED" in os.environ
    snapshot = {
        "timestamp": time.time(),
        "codex_path": str(Path(codex_path).resolve()),
        "codex_version": version,
        "CODEX_HOME": os.environ.get("CODEX_HOME", "<host default: ~/.codex>"),
        "provider_reachability": provider,
        "managed_network_marker_present": network_marker_present,
        "disk": {
            "storage": _disk_snapshot(storage_root),
            "workspace_filesystem": _disk_snapshot(ROOT),
            "host_root_filesystem": _disk_snapshot(Path("/")),
        },
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "approval_policy": APPROVAL_POLICY,
        "sandbox": SANDBOX,
        "network_policy": {
            "codex_provider": "inherit host network environment",
            "task_dependency_network": "offline pinned caches",
        },
        "codex_command_preview": runner.build_codex_command("<FROZEN PROMPT>")[:-1]
        + ["<FROZEN PROMPT>"],
    }
    print(json.dumps(snapshot, sort_keys=True, indent=2), flush=True)
    if require_provider and not (provider["dns_ok"] and provider["tcp_connect_ok"]):
        raise RuntimeError(
            "host provider connectivity precheck failed; no Codex child was launched: "
            + str(provider)
        )
    if require_provider and network_marker_present:
        raise RuntimeError(
            "managed-session network marker is present; run this host runner from a normal shell "
            "with host network inheritance and no CODEX_SANDBOX_NETWORK_DISABLED variable"
        )
    return snapshot


def _assert_frozen_config() -> None:
    if (MODEL, REASONING_EFFORT, APPROVAL_POLICY, SANDBOX) != (
        runner.MODEL,
        runner.REASONING_EFFORT,
        runner.APPROVAL_POLICY,
        runner.SANDBOX,
    ):
        raise RuntimeError("host runner constants do not match the frozen V6 backend")


def _previous_run_ids() -> set[str]:
    """Return every known prior schedule ID so V6 cannot silently reuse one."""
    paths = (
        ROOT / "data/action_compliance/invalidated_sparse_checkout_run/run_plan.json",
        ROOT / "data/action_compliance/invalidated_v2_test_discovery_run/run_plan.json",
        ROOT / "data/action_compliance/codex_runs_v3/run_plan.json",
        ROOT / "data/action_compliance/codex_runs_v4_host/run_plan.json",
        ROOT / "data/action_compliance/codex_runs_v5_host/run_plan.json",
        ROOT / "data/action_compliance/v5_dry_run_host/run_plan.json",
    )
    ids: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        loaded = json.loads(path.read_text(encoding="utf-8"))
        rows = loaded if isinstance(loaded, list) else loaded.get("plan", [])
        ids.update(str(row["run_id"]) for row in rows if isinstance(row, dict) and "run_id" in row)
    return ids


def _storage(args: argparse.Namespace) -> storage_module.V4StoragePolicy:
    return storage_module.V4StoragePolicy(
        root=args.storage_root.resolve(),
        worker_count=args.concurrency,
        min_free_bytes=20 * 1024**3,
        min_free_inodes=100_000,
        min_host_free_bytes=5 * 1024**3,
        # Default host execution inherits the host's authenticated CODEX_HOME.
        # The opt-in mode is available only when the host explicitly requests
        # disposable per-slot Codex state.
        codex_home_mode="isolated" if args.isolate_codex_home else "host",
    )


def _prepare_kubernetes_cache(
    *,
    worktree: Path,
    metadata: dict[str, Any],
    output_dir: Path,
    offline_env: dict[str, str],
) -> dict[str, Any]:
    """Populate and verify the excluded fixture's shared Go cache.

    Cache population is a model-free host-preparation step. It temporarily
    enables the host's normal Go proxy path, then proves the frozen test
    command succeeds with the official offline environment before Codex is
    launched. The cache is shared dependency state, never source or result
    state.
    """

    test_env = {str(key): str(value) for key, value in metadata["test_env"].items()}
    module_cache = Path(test_env["GOMODCACHE"])
    build_cache = Path(test_env["GOCACHE"])
    module_cache.mkdir(parents=True, exist_ok=True)
    build_cache.mkdir(parents=True, exist_ok=True)
    network_env = {
        **os.environ,
        **offline_env,
        "GOWORK": "off",
        "GOMODCACHE": str(module_cache),
        "GOCACHE": str(build_cache),
        "GOPROXY": "https://proxy.golang.org,direct",
        "GOSUMDB": "sum.golang.org",
    }
    network_env.pop("CODEX_SANDBOX_NETWORK_DISABLED", None)
    download_command = ["go", "mod", "download"]
    download = runner._run(download_command, cwd=worktree, timeout=3600, env=network_env)
    (output_dir / "preflight_cache_download.log").write_text(
        download.stdout + download.stderr, encoding="utf-8"
    )
    result: dict[str, Any] = {
        "download_command": download_command,
        "download_returncode": download.returncode,
        "download_succeeded": download.returncode == 0,
        "module_cache": str(module_cache),
        "build_cache": str(build_cache),
        "download_network_policy": "host-enabled preparation only",
        "verification_command": list(metadata["test_command"]),
    }
    if download.returncode != 0:
        result.update(
            {
                "offline_tests_executed": False,
                "offline_tests_pass": False,
                "offline_test_execution_status": "cache_download_failed",
            }
        )
        _write_json_atomic(output_dir / "preflight_cache_result.json", result)
        return result

    test_command = list(metadata["test_command"])
    test_cwd = worktree / str(metadata["test_cwd"])
    offline_test = runner._run(
        test_command,
        cwd=test_cwd,
        timeout=1800,
        env={**offline_env, **test_env},
    )
    (output_dir / "preflight_cache_offline_test.log").write_text(
        offline_test.stdout + offline_test.stderr, encoding="utf-8"
    )
    status = runner._classify_test_output(
        offline_test, test_runner=str(metadata["test_runner"])
    )
    result.update(
        {
            "offline_test_returncode": offline_test.returncode,
            "offline_test_execution_status": status,
            "offline_tests_executed": status == "executed_with_tests",
            "offline_no_tests_ran": status == "executed_zero_tests",
            "offline_tests_pass": offline_test.returncode == 0 and status == "executed_with_tests",
        }
    )
    _write_json_atomic(output_dir / "preflight_cache_result.json", result)
    return result


def _preflight_gate(path: Path) -> bool:
    summary_path = path / "preflight_summary.json"
    if not summary_path.is_file():
        raise RuntimeError(f"host preflight summary is missing: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("preflight_gate_pass") is not True:
        raise RuntimeError("saved host preflight did not pass; statistical execution is blocked")
    return True


def _dry_run_gate(path: Path) -> bool:
    result_path = path / "dry_run_result.json"
    if not result_path.is_file():
        raise RuntimeError(f"host 63-row dry-run result is missing: {result_path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    required_true = (
        "context_attachment",
        "a_b_c_augmentation",
        "codex_command_assembly",
        "approval_never",
        "full_worktree_creation",
        "no_sparse_checkout",
        "normalized_contract",
        "correct_test_commands",
        "patch_capture",
        "cleanup",
        "resume_state",
        "grader_paths",
        "result_schema",
    )
    if (
        result.get("planned_runs") != 63
        or result.get("completed_runs") != 63
        or result.get("model_calls") != 0
        or result.get("coding_agents_called") is not False
        or any(result.get(key) is not True for key in required_true)
    ):
        raise RuntimeError("saved host 63-row dry run did not pass; statistical execution is blocked")
    return True


def _json_gate(path: Path, required: dict[str, object], *, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label} artifact is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    for key, expected in required.items():
        if value.get(key) != expected:
            raise RuntimeError(
                f"{label} gate failed for {key}: expected {expected!r}, got {value.get(key)!r}"
            )


def _model_free_gate() -> None:
    _json_gate(
        ROOT / "data/action_compliance/v6_sanity_replay/results.json",
        {
            "model_calls": 0,
            "task_count": 7,
            "row_count": 14,
            "all_grader_calls_passed": True,
            "all_tests_executed": True,
            "all_compliant_authority": True,
            "all_violating_authority": True,
            "worktree_count": 0,
            "residual_slot_count": 0,
        },
        label="V6 sanity replay",
    )
    _json_gate(
        ROOT / "data/action_compliance/v6_storage_stress/stress_result.json",
        {
            "planned_cycles": 63,
            "completed_cycles": 63,
            "passed_cycles": 63,
            "failed_cycles": 0,
            "model_calls": 0,
            "worktree_count": 0,
        },
        label="V6 storage stress",
    )
    _json_gate(
        ROOT / "data/action_compliance/v6_storage_recovery/recovery.json",
        {"pass": True, "model_calls": 0},
        label="V6 storage recovery",
    )


def _manifest_gate(path: Path) -> int:
    if not path.is_file():
        raise RuntimeError(f"V6 manifest is missing: {path}")
    checked = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, relative = line.partition("  ")
        if not separator or len(digest) != 64:
            raise RuntimeError(f"malformed V6 manifest line: {line!r}")
        target = ROOT / relative
        if not target.is_file() or runner._sha256_file(target) != digest:
            raise RuntimeError(f"V6 manifest verification failed for {relative}")
        checked += 1
    if checked == 0:
        raise RuntimeError("V6 manifest is empty")
    return checked


def _print_frozen_contracts(dry_run_output: Path) -> None:
    result_path = dry_run_output / "dry_run_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    contracts: dict[str, dict[str, Any]] = {}
    for row in result.get("rows", []):
        task = str(row["task"])
        contracts.setdefault(
            task,
            {
                "task": task,
                "interpreter": row["interpreter"],
                "test_command": row["test_command"],
                "test_cwd": row["test_cwd"],
                "test_env": row["test_env"],
            },
        )
    if set(contracts) != set(runner.TASKS):
        raise RuntimeError("V6 dry run did not persist all seven task contracts")
    contract_path = dry_run_output / "frozen_test_contracts.json"
    _write_json_atomic(contract_path, [contracts[task] for task in runner.TASKS])
    print(json.dumps({"v6_frozen_test_contracts": list(contracts.values())}, sort_keys=True, indent=2), flush=True)


def _run_preflight(args: argparse.Namespace, snapshot: dict[str, Any]) -> int:
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "preflight_summary.json"
    if summary_path.exists():
        raise RuntimeError(
            f"preflight output already exists: {summary_path}; use a new --output-root for one fresh excluded attempt"
        )
    attempt_dir = output / "high"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    storage = _storage(args)
    storage.initialize()
    storage.recover_abandoned()
    context = runner.build_excluded_preflight_context()
    prompt = runner.assemble_prompt(context)
    prompt_meta = runner._write_prompt(attempt_dir, prompt)
    run_id = "v6-host-excluded-preflight-v1-high"
    result: dict[str, Any]
    try:
        with storage.lifecycle(run_id=run_id, slot=0):
            environment = storage.environment(0)
            setup_args, worktree = runner._setup_args(
                runner.PREFLIGHT_TASK, storage.slot_root(0), storage=storage, slot=0
            )
            setup = runner._run(setup_args, cwd=ROOT, timeout=3600, env=environment)
            (attempt_dir / "worktree_setup.log").write_text(
                setup.stdout + setup.stderr, encoding="utf-8"
            )
            if setup.returncode != 0:
                result = {
                    "status": "INFRA_FAILURE",
                    "failure_stage": "worktree_setup",
                    "setup_returncode": setup.returncode,
                    "comparative_model_calls": 0,
                    "preflight_model_calls": 0,
                }
            else:
                runner._ignore_setup_untracked(worktree, env=environment)
                metadata = runner._setup_metadata(worktree, expected_task=runner.PREFLIGHT_TASK)
                cache_preparation = _prepare_kubernetes_cache(
                    worktree=worktree,
                    metadata=metadata,
                    output_dir=attempt_dir,
                    offline_env=environment,
                )
                if not cache_preparation["offline_tests_pass"]:
                    result = {
                        "status": "INFRA_FAILURE",
                        "failure_stage": "preflight_dependency_cache",
                        "comparative_model_calls": 0,
                        "preflight_model_calls": 0,
                        "prompt": prompt_meta,
                        "contract": metadata,
                        "cache_preparation": cache_preparation,
                    }
                else:
                    status_before = runner._git_status(worktree, env=environment)
                    (attempt_dir / "git_status_before_model.txt").write_text(status_before, encoding="utf-8")
                    agent = runner.run_codex(
                        worktree,
                        prompt,
                        output_dir=attempt_dir,
                        env=environment,
                        model=MODEL,
                        reasoning_effort=REASONING_EFFORT,
                    )
                    status_after = runner._git_status(worktree, env=environment)
                    (attempt_dir / "git_status_after_model.txt").write_text(status_after, encoding="utf-8")
                    patch_meta = runner.capture_patch(worktree, attempt_dir / "patch.diff", env=environment)
                    patch_path = (attempt_dir / "patch.diff").resolve()
                    marker_path = worktree / "decisiontrace_codex_preflight_probe.txt"
                    marker = marker_path.read_text(encoding="utf-8") if marker_path.exists() else ""
                    # Return to the exact pinned baseline before either
                    # consumer applies the captured patch. This prevents a
                    # newly-created probe file from colliding with grading.
                    runner._restore_clean_worktree(runner.PREFLIGHT_TASK, worktree, env=environment)
                    grader = runner._run_grader(
                        runner.PREFLIGHT_TASK,
                        worktree,
                        patch_path,
                        storage.slot_root(0),
                        attempt_dir / "grader.output.log",
                        base_env=environment,
                    )
                    tests = runner._run_test_verification(
                        runner.PREFLIGHT_TASK,
                        worktree,
                        patch_path,
                        storage.slot_root(0),
                        base_env=environment,
                    )
                    runner._restore_clean_worktree(runner.PREFLIGHT_TASK, worktree, env=environment)
                    reset_status = runner._git_status(worktree, env=environment)
                    result = {
                        "status": "COMPLETED",
                        "excluded_fixture": runner.PREFLIGHT_TASK,
                        "comparative_model_calls": 0,
                        "preflight_model_calls": 1,
                        "prompt": prompt_meta,
                        "contract": metadata,
                        "cache_preparation": cache_preparation,
                        "edit_write_result": marker.strip() == "CODEX_PREFLIGHT_WRITE_OK",
                        "approval_prompts_observed": agent["approval_prompts_observed"],
                        "logs_results_parseable": agent["logs_parseable"] and grader["grader_output_parseable"],
                        "patch_capture_result": patch_meta,
                        "actual_tests_result": tests,
                        "grader_result": grader,
                        "codex": agent,
                        "reset_cleanup_verified": not reset_status.strip(),
                        "fresh_worktree_removed": False,
                    }
    except Exception as error:
        result = {
            "status": "INFRA_FAILURE",
            "failure_stage": "host_preflight_or_cleanup",
            "error": repr(error),
            "comparative_model_calls": 0,
            "preflight_model_calls": 0,
        }
    result.update(
        {
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "approval_policy": APPROVAL_POLICY,
            "sandbox": SANDBOX,
            "timeout_seconds": runner.CODEX_TIMEOUT_SECONDS,
            "host_launch_snapshot": snapshot,
        }
    )
    _write_json_atomic(attempt_dir / "row.json", result)
    result["fresh_worktree_removed"] = not storage.slot_root(0).exists()
    _write_json_atomic(attempt_dir / "row.json", result)
    gate = all(
        (
            result.get("status") == "COMPLETED",
            result.get("edit_write_result") is True,
            not result.get("approval_prompts_observed", True),
            result.get("logs_results_parseable") is True,
            result.get("patch_capture_result", {}).get("patch_has_new_file") is True,
            result.get("cache_preparation", {}).get("offline_tests_executed") is True,
            result.get("cache_preparation", {}).get("offline_tests_pass") is True,
            result.get("actual_tests_result", {}).get("tests_executed") is True,
            result.get("reset_cleanup_verified") is True,
            result.get("fresh_worktree_removed") is True,
        )
    )
    summary = {
        "attempts": 1,
        "latest": result,
        "preflight_gate_pass": gate,
        "excluded_from_statistical_data": True,
    }
    _write_json_atomic(summary_path, summary)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if gate else 1


def _run_dry_run(args: argparse.Namespace, snapshot: dict[str, Any]) -> int:
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "dry_run_action_compliance_v6.py"),
        "--output",
        str(output),
        "--storage-root",
        str(args.storage_root.resolve()),
        "--concurrency",
        str(args.concurrency),
    ]
    if (output / "run_plan.json").exists() or (output / "resume_state.json").exists():
        command.append("--resume")
    process = subprocess.run(command, cwd=ROOT, capture_output=False, check=False)
    _write_json_atomic(
        output / "host_launch_snapshot.json",
        {**snapshot, "mode": "dry-run", "model_calls": 0, "coding_agents_called": False},
    )
    return process.returncode


def _before_batch(_batch: list[dict[str, Any]]) -> None:
    provider = _provider_reachability()
    if not (provider["dns_ok"] and provider["tcp_connect_ok"]):
        raise RuntimeError(
            "host provider connectivity precheck failed before starting the next statistical batch; "
            f"no child launched for this batch: {provider}"
        )


def _run_execute(args: argparse.Namespace, snapshot: dict[str, Any]) -> int:
    _preflight_gate(args.preflight_output.resolve())
    _dry_run_gate(args.dry_run_output.resolve())
    _model_free_gate()
    manifest_count = _manifest_gate(ROOT / "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V6_SHA256.txt")
    _print_frozen_contracts(args.dry_run_output.resolve())
    output = args.output_root.resolve()
    storage = _storage(args)
    storage.initialize()
    storage.recover_abandoned()
    plan, condition_map = runner.build_plan(
        runner.CONTEXTS_ROOT, repetitions=REPETITIONS, seed=V6_SEED
    )
    if len(plan) != 63 or len({row["run_id"] for row in plan}) != 63:
        raise RuntimeError("V6 host execution plan is not 63 unique rows")
    overlap = _previous_run_ids() & {row["run_id"] for row in plan}
    if overlap:
        raise RuntimeError(f"V6 host execution reused prior run IDs: {sorted(overlap)}")
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "run_plan.json"
    map_path = output / "condition_map.json"
    if plan_path.exists() or map_path.exists():
        if not plan_path.exists() or not map_path.exists():
            raise RuntimeError("V6 host execution has a partial plan freeze")
        if json.loads(plan_path.read_text(encoding="utf-8")) != plan:
            raise RuntimeError("existing V6 host run plan differs from the frozen plan")
        if json.loads(map_path.read_text(encoding="utf-8")) != condition_map:
            raise RuntimeError("existing V6 host condition map differs from the frozen plan")
    else:
        _write_json_atomic(plan_path, plan)
        _write_json_atomic(map_path, condition_map, private=True)
    _write_json_atomic(
        output / "host_launch_snapshot.json",
        {**snapshot, "mode": "execute", "model_calls_allowed": True},
    )
    try:
        rows = runner.run_plan(
            plan,
            output_root=output,
            model=MODEL,
            reasoning_effort=REASONING_EFFORT,
            concurrency=args.concurrency,
            storage=storage,
            pre_run_check=_before_batch,
        )
    except runner.V4QuotaPause as error:
        state_path = output / "resume_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        pending = sum(
            state.get("run_status", {}).get(row["run_id"]) == "PENDING" for row in plan
        )
        summary = {
            "planned_runs": 63,
            "attempted_this_process": 0,
            "usable_runs": len(state.get("completed_run_ids", [])),
            "infra_failures": 0,
            "pending_runs": pending,
            "quota_paused": True,
            "stop_reason": str(error),
            "checkpoint": str(state_path),
        }
        _write_json_atomic(output / "host_execution_summary.json", summary)
        print(json.dumps(summary, sort_keys=True, indent=2))
        return 2
    state_path = output / "resume_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    all_rows = []
    for row in plan:
        row_path = output / row["run_id"] / "row.json"
        if row_path.exists():
            all_rows.append(json.loads(row_path.read_text(encoding="utf-8")))
    summary = {
        "planned_runs": 63,
        "attempted_this_process": len(rows),
        "usable_runs": sum(row.get("status") == "USABLE_COMPLETE" for row in all_rows),
        "infra_failures": sum(row.get("status") == "INFRA_FAILURE" for row in all_rows),
        "pending_runs": sum(state.get("run_status", {}).get(row["run_id"]) == "PENDING" for row in plan),
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "approval_policy": APPROVAL_POLICY,
        "sandbox": SANDBOX,
        "checkpoint": str(state_path),
        "manifest_files_verified": manifest_count,
    }
    _write_json_atomic(output / "host_execution_summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if summary["pending_runs"] == 0 and summary["usable_runs"] == 63 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight", action="store_true", help="one excluded Kubernetes fixture only")
    modes.add_argument("--dry-run", action="store_true", help="complete 63-row orchestration, zero model calls")
    modes.add_argument("--execute", action="store_true", help="fresh/resumable 63-row V6 execution")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--storage-root", type=Path, default=ROOT / "data/action_compliance/v6_execution_storage")
    parser.add_argument("--preflight-output", type=Path, default=ROOT / "data/action_compliance/v6_codex_preflight_host")
    parser.add_argument("--dry-run-output", type=Path, default=ROOT / "data/action_compliance/v6_dry_run_host_contract_v2")
    parser.add_argument("--concurrency", type=int, choices=(1, 2, 3), default=DEFAULT_CONCURRENCY)
    parser.add_argument("--isolate-codex-home", action="store_true", help="opt into disposable per-slot CODEX_HOME")
    args = parser.parse_args()
    if args.concurrency > 2:
        parser.error("V6 host runner starts and remains at no more than two concurrent coding runs")
    if args.output_root is None:
        if args.preflight:
            args.output_root = ROOT / "data/action_compliance/v6_codex_preflight_host"
        elif args.dry_run:
            args.output_root = ROOT / "data/action_compliance/v6_dry_run_host_contract_v2"
        else:
            args.output_root = ROOT / "data/action_compliance/codex_runs_v6_host"
    _assert_frozen_config()
    snapshot = _launch_snapshot(args.storage_root.resolve(), require_provider=args.preflight or args.execute)
    if args.preflight:
        return _run_preflight(args, snapshot)
    if args.dry_run:
        return _run_dry_run(args, snapshot)
    return _run_execute(args, snapshot)


if __name__ == "__main__":
    raise SystemExit(main())
