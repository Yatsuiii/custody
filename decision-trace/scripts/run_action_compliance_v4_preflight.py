#!/usr/bin/env python3
"""Run the single excluded Kubernetes capability preflight on V4 storage."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import action_compliance_v4_storage as storage_module
import run_action_compliance_codex as runner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--attempt", default="high")
    args = parser.parse_args()
    if args.attempt != "high":
        raise SystemExit("V4 preflight is frozen to the Luna/high backend")

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    attempt_dir = output / args.attempt
    attempt_dir.mkdir(parents=True, exist_ok=True)
    storage = storage_module.V4StoragePolicy(args.storage_root)
    storage.initialize()
    storage.recover_abandoned()
    context = runner.build_excluded_preflight_context()
    prompt = runner.assemble_prompt(context)
    prompt_meta = runner._write_prompt(attempt_dir, prompt)
    run_id = f"v4-excluded-preflight-{args.attempt}"

    with storage.lifecycle(run_id=run_id, slot=0):
        environment = storage.environment(0)
        setup_args, worktree = runner._setup_args(
            runner.PREFLIGHT_TASK,
            storage.slot_root(0),
            storage=storage,
            slot=0,
        )
        setup = runner._run(setup_args, cwd=runner.ROOT, timeout=3600, env=environment)
        (attempt_dir / "worktree_setup.log").write_text(
            setup.stdout + setup.stderr, encoding="utf-8"
        )
        if setup.returncode != 0:
            result = {
                "status": "infrastructure_failure",
                "failure_stage": "worktree_setup",
                "setup_returncode": setup.returncode,
                "model": runner.MODEL,
                "reasoning_effort": runner.REASONING_EFFORT,
                "approval_policy": runner.APPROVAL_POLICY,
                "sandbox": runner.SANDBOX,
                "comparative_model_calls": 0,
            }
            (attempt_dir / "row.json").write_text(
                json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            return 1

        runner._ignore_setup_untracked(worktree, env=environment)
        metadata = runner._setup_metadata(worktree, expected_task=runner.PREFLIGHT_TASK)
        status_before = runner._git_status(worktree, env=environment)
        (attempt_dir / "git_status_before_model.txt").write_text(
            status_before, encoding="utf-8"
        )
        agent = runner.run_codex(
            worktree,
            prompt,
            output_dir=attempt_dir,
            env=environment,
            model=runner.MODEL,
            reasoning_effort=runner.REASONING_EFFORT,
        )
        status_after = runner._git_status(worktree, env=environment)
        (attempt_dir / "git_status_after_model.txt").write_text(
            status_after, encoding="utf-8"
        )
        patch_meta = runner.capture_patch(
            worktree, attempt_dir / "patch.diff", env=environment
        )
        marker_path = worktree / "decisiontrace_codex_preflight_probe.txt"
        marker = marker_path.read_text(encoding="utf-8") if marker_path.exists() else ""
        runner._restore_clean_worktree(
            runner.PREFLIGHT_TASK, worktree, env=environment
        )
        patch_path = (attempt_dir / "patch.diff").resolve()
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
        reset_status = runner._git_status(worktree, env=environment)
        result = {
            "status": "completed",
            "attempt": args.attempt,
            "excluded_fixture": runner.PREFLIGHT_TASK,
            "model": runner.MODEL,
            "reasoning_effort": runner.REASONING_EFFORT,
            "approval_policy": runner.APPROVAL_POLICY,
            "sandbox": runner.SANDBOX,
            "timeout_seconds": runner.CODEX_TIMEOUT_SECONDS,
            "network_marker": os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "absent"),
            "comparative_model_calls": 0,
            "preflight_model_calls": 1,
            "prompt": prompt_meta,
            "contract": metadata,
            "edit_write_result": marker.strip() == "CODEX_PREFLIGHT_WRITE_OK",
            "preflight_marker_found": marker.strip() == "CODEX_PREFLIGHT_WRITE_OK",
            "approval_prompts_observed": agent["approval_prompts_observed"],
            "logs_results_parseable": agent["logs_parseable"] and grader["grader_output_parseable"],
            "patch_capture_result": patch_meta,
            "actual_tests_result": tests,
            "grader_result": grader,
            "codex": agent,
            "reset_cleanup_verified": not reset_status.strip(),
            "fresh_worktree_removed": False,
        }
        (attempt_dir / "row.json").write_text(
            json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

    result["fresh_worktree_removed"] = not storage.slot_root(0).exists()
    (attempt_dir / "row.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "attempts": 1,
        "latest": result,
        "preflight_gate_pass": all(
            (
                result["edit_write_result"],
                result["preflight_marker_found"],
                not result["approval_prompts_observed"],
                result["logs_results_parseable"],
                result["patch_capture_result"]["patch_has_new_file"],
                result["actual_tests_result"]["tests_executed"],
                result["reset_cleanup_verified"],
                result["fresh_worktree_removed"],
            )
        ),
    }
    (output / "preflight_summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if summary["preflight_gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
