#!/usr/bin/env python3
"""Model-free V3 replay of all frozen sanity patches.

This replay is the first consumer-level verification of the setup-owned test
interpreter contract. It uses the same setup, capture, grader, and independent
test-verification functions as the production runner, but never calls Codex.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import run_action_compliance_codex as runner


ROOT = runner.ROOT
TASKS = runner.TASKS


def _check_contract(task: str, worktree: Path) -> dict[str, object]:
    metadata = runner._setup_metadata(worktree, expected_task=task)
    if metadata["task"] != task:
        raise RuntimeError(f"metadata task mismatch: {metadata}")
    pinned = runner._checked(["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60).stdout.strip()
    if pinned != metadata["pinned_sha"]:
        raise RuntimeError(f"metadata SHA mismatch for {task}: {pinned} != {metadata['pinned_sha']}")
    return {
        "contract_version": metadata["contract_version"],
        "grader_interpreter": metadata["grader_interpreter"],
        "interpreter": metadata["interpreter"],
        "test_command": metadata["test_command"],
        "test_cwd": metadata["test_cwd"],
        "interpreter_kind": metadata["interpreter_kind"],
        "pinned_sha": pinned,
        "full_worktree": metadata["full_worktree"],
        "sparse_checkout": metadata["sparse_checkout"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    contract_rows: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="action-compliance-sanity-v3-") as raw:
        root = Path(raw)
        for task in TASKS:
            setup, worktree = runner._setup_args(task, root)
            setup_process = runner._run(setup, cwd=ROOT, timeout=3600)
            (args.output / f"{task}.setup.log").write_text(
                setup_process.stdout + setup_process.stderr, encoding="utf-8"
            )
            if setup_process.returncode != 0:
                raise RuntimeError(f"setup failed for {task}: {setup_process.stdout}{setup_process.stderr}")
            runner._ignore_setup_untracked(worktree)
            contract_rows.append({"task": task, **_check_contract(task, worktree)})

            for label in ("compliant", "violating"):
                patch = ROOT / "pilot" / task / f"sanity_patch_{label}.diff"
                runner._restore_clean_worktree(task, worktree)
                applied = runner._run(
                    ["git", "apply", "--whitespace=nowarn", str(patch)],
                    cwd=worktree,
                    timeout=120,
                )
                if applied.returncode != 0:
                    raise RuntimeError(f"sanity patch failed for {task}/{label}: {applied.stdout}{applied.stderr}")
                status = runner._git_status(worktree)
                captured_path = args.output / "captured_patches" / f"{task}__{label}.diff"
                capture = runner.capture_patch(worktree, captured_path)
                runner._restore_clean_worktree(task, worktree)

                grader_path = args.output / "grader_outputs" / f"{task}__{label}.log"
                grader_path.parent.mkdir(parents=True, exist_ok=True)
                grader = runner._run_grader(task, worktree, patch, root, grader_path)
                tests = runner._run_test_verification(task, worktree, patch, root)
                runner._restore_clean_worktree(task, worktree)
                clean = not runner._git_status(worktree).strip()
                values = grader["grader_output"]
                rows.append(
                    {
                        "task": task,
                        "patch": label,
                        "status_after_apply": status,
                        "capture": capture,
                        "grader": grader,
                        "tests": tests,
                        "reset_clean": clean,
                    }
                )
                if grader["grader_returncode"] != 0 or not grader["grader_output_parseable"]:
                    raise RuntimeError(f"grader failed for {task}/{label}: {grader}")
                if values["TASK_COMPLETED"] is not True:
                    raise RuntimeError(f"sanity task did not complete for {task}/{label}: {values}")
                expected_authority = label == "compliant"
                if values["AUTHORITY_COMPLIANT"] is not expected_authority:
                    raise RuntimeError(f"authority sanity mismatch for {task}/{label}: {values}")
                if not tests["tests_executed"]:
                    raise RuntimeError(f"tests were not actually executed for {task}/{label}: {tests}")
                if not clean:
                    raise RuntimeError(f"reset did not restore clean worktree for {task}/{label}")

    result = {
        "model_calls": 0,
        "task_count": len(TASKS),
        "contract_rows": contract_rows,
        "row_count": len(rows),
        "all_grader_calls_passed": True,
        "all_tests_executed": all(row["tests"]["tests_executed"] for row in rows),
        "all_compliant_authority": all(
            row["patch"] != "compliant" or row["grader"]["grader_output"]["AUTHORITY_COMPLIANT"] is True
            for row in rows
        ),
        "all_violating_authority": all(
            row["patch"] != "violating" or row["grader"]["grader_output"]["AUTHORITY_COMPLIANT"] is False
            for row in rows
        ),
        "rows": rows,
    }
    (args.output / "results.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
