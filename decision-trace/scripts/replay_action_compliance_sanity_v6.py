#!/usr/bin/env python3
"""Replay all frozen sanity patches through the V6 storage lifecycle.

This is a model-free consumer-level gate.  It exercises the exact V6 full
worktree setup, normalized test contract, staged binary patch capture, blind
grader, independent test verification, and crash-safe cleanup used by the
statistical runner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import action_compliance_v4_storage as storage_module
import run_action_compliance_codex as runner


ROOT = runner.ROOT
TASKS = runner.TASKS


def _contract(
    task: str, worktree: Path, *, env: dict[str, str]
) -> dict[str, object]:
    metadata = runner._setup_metadata(worktree, expected_task=task)
    pinned = runner._checked(
        ["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60, env=env
    ).stdout.strip()
    if pinned != metadata["pinned_sha"]:
        raise RuntimeError(f"pinned SHA mismatch for {task}: {pinned} != {metadata['pinned_sha']}")
    return {
        "task": task,
        "contract_version": metadata["contract_version"],
        "grader_interpreter": metadata["grader_interpreter"],
        "interpreter": metadata["interpreter"],
        "test_command": metadata["test_command"],
        "test_cwd": metadata["test_cwd"],
        "test_env": metadata["test_env"],
        "interpreter_kind": metadata["interpreter_kind"],
        "pinned_sha": pinned,
        "full_worktree": metadata["full_worktree"],
        "sparse_checkout": metadata["sparse_checkout"],
    }


def _run_case(
    *,
    task: str,
    label: str,
    output: Path,
    storage: storage_module.V4StoragePolicy,
    slot: int,
) -> dict[str, object]:
    case_id = f"sanity-{task}-{label}"
    patch = ROOT / "pilot" / task / f"sanity_patch_{label}.diff"
    case_dir = output / "cases" / task / label
    case_dir.mkdir(parents=True, exist_ok=True)
    with storage.lifecycle(run_id=case_id, slot=slot):
        environment = storage.environment(slot)
        setup_args, worktree = runner._setup_args(
            task, storage.slot_root(slot), storage=storage, slot=slot
        )
        setup = runner._run(setup_args, cwd=ROOT, timeout=3600, env=environment)
        (case_dir / "setup.log").write_text(
            setup.stdout + setup.stderr, encoding="utf-8"
        )
        if setup.returncode != 0:
            raise RuntimeError(f"setup failed for {case_id}: {setup.stdout}{setup.stderr}")
        runner._ignore_setup_untracked(worktree, env=environment)
        metadata = _contract(task, worktree, env=environment)

        runner._restore_clean_worktree(task, worktree, env=environment)
        applied = runner._run(
            ["git", "apply", "--whitespace=nowarn", str(patch)],
            cwd=worktree,
            timeout=120,
            env=environment,
        )
        if applied.returncode != 0:
            raise RuntimeError(
                f"sanity patch failed for {case_id}: {applied.stdout}{applied.stderr}"
            )
        status_after_apply = runner._git_status(worktree, env=environment)
        capture = runner.capture_patch(
            worktree, case_dir / "captured_patch.diff", env=environment
        )
        runner._restore_clean_worktree(task, worktree, env=environment)

        grader = runner._run_grader(
            task,
            worktree,
            patch,
            storage.slot_root(slot),
            case_dir / "grader.output.log",
            base_env=environment,
        )
        tests = runner._run_test_verification(
            task,
            worktree,
            patch,
            storage.slot_root(slot),
            base_env=environment,
        )
        runner._restore_clean_worktree(task, worktree, env=environment)
        reset_status = runner._git_status(worktree, env=environment)
        values = grader["grader_output"]
        expected_authority = label == "compliant"
        if grader["grader_returncode"] != 0 or not grader["grader_output_parseable"]:
            raise RuntimeError(f"grader failed for {case_id}: {grader}")
        if values["TASK_COMPLETED"] is not True:
            raise RuntimeError(f"TASK_COMPLETED mismatch for {case_id}: {values}")
        if values["AUTHORITY_COMPLIANT"] is not expected_authority:
            raise RuntimeError(f"authority mismatch for {case_id}: {values}")
        if not tests["tests_executed"]:
            raise RuntimeError(f"tests did not execute for {case_id}: {tests}")
        if reset_status.strip():
            raise RuntimeError(f"reset was not clean for {case_id}: {reset_status}")
        return {
            "task": task,
            "patch": label,
            "contract": metadata,
            "status_after_apply": status_after_apply,
            "capture": capture,
            "grader": grader,
            "tests": tests,
            "reset_clean": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    storage = storage_module.V4StoragePolicy(args.storage_root)
    storage.initialize()
    storage.recover_abandoned()

    contracts: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for task in TASKS:
        # The contract is collected during the first case and repeated cases
        # consume the same setup-owned metadata for that task.
        for label in ("compliant", "violating"):
            row = _run_case(
                task=task,
                label=label,
                output=args.output,
                storage=storage,
                slot=0,
            )
            rows.append(row)
            if label == "compliant":
                contracts.append(row["contract"])

    result = {
        "model_calls": 0,
        "task_count": len(TASKS),
        "row_count": len(rows),
        "contract_rows": contracts,
        "all_grader_calls_passed": all(
            row["grader"]["grader_returncode"] == 0
            and row["grader"]["grader_output_parseable"]
            for row in rows
        ),
        "all_tests_executed": all(row["tests"]["tests_executed"] for row in rows),
        "all_compliant_authority": all(
            row["patch"] != "compliant"
            or row["grader"]["grader_output"]["AUTHORITY_COMPLIANT"] is True
            for row in rows
        ),
        "all_violating_authority": all(
            row["patch"] != "violating"
            or row["grader"]["grader_output"]["AUTHORITY_COMPLIANT"] is False
            for row in rows
        ),
        "rows": rows,
        "worktree_count": len(list(storage.slots.glob("slot-*/worktree"))),
        "residual_slot_count": len(list(storage.slots.glob("slot-*"))),
    }
    (args.output / "results.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if all(
        (
            result["model_calls"] == 0,
            result["task_count"] == 7,
            result["row_count"] == 14,
            result["all_grader_calls_passed"],
            result["all_tests_executed"],
            result["all_compliant_authority"],
            result["all_violating_authority"],
            result["worktree_count"] == 0,
            result["residual_slot_count"] == 0,
        )
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
