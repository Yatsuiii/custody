#!/usr/bin/env python3
"""Complete V3 orchestration dry run with zero coding-model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from run_action_compliance_codex import (
    CONDITIONS,
    CONTEXTS_ROOT,
    PLAN_SEED,
    TASKS,
    assemble_prompt,
    build_codex_command,
    build_plan,
    _setup_metadata,
)
from setup_action_compliance_full_worktree import REPOSITORIES


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}, capture_output=True, text=True, timeout=timeout)


def checked(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    process = run(args, cwd=cwd, timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError((process.stdout + process.stderr).strip())
    return process


def setup_command(task: str, root: Path) -> tuple[list[str], Path]:
    worktree = root / "bases" / task / "worktree"
    command = ["python3", str(ROOT / "scripts" / "setup_action_compliance_full_worktree.py"), "--task", task, "--worktree", str(worktree)]
    if task in {"task-go-01-maps-sorted-keys", "task-06-opentofu-static-source-scope"}:
        command += ["--go-cache", str(root / "caches" / task / "go-cache")]
    if task == "task-07-axum-optional-typed-header":
        command += ["--cargo-home", str(root / "caches" / task / "cargo-home"), "--cargo-target", str(root / "caches" / task / "cargo-target")]
    return command, worktree


def ignore_untracked(worktree: Path) -> None:
    status = checked(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=worktree, timeout=60).stdout
    paths = [line[3:] for line in status.splitlines() if line.startswith("?? ")]
    if paths:
        exclude = worktree / ".git" / "info" / "exclude"
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write("\n# V3 dry-run setup artifacts.\n")
            for path in paths:
                stream.write(f"/{path}\n")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def previous_run_ids() -> set[str]:
    ids: set[str] = set()
    for path in (
        ROOT / "data/action_compliance/invalidated_sparse_checkout_run/run_plan.json",
        ROOT / "data/action_compliance/invalidated_v2_test_discovery_run/run_plan.json",
    ):
        if path.exists():
            ids.update(row["run_id"] for row in json.loads(path.read_text(encoding="utf-8")))
    return ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=PLAN_SEED)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plan, condition_map = build_plan(CONTEXTS_ROOT, repetitions=3, seed=args.seed)
    if len(plan) != 63 or len({row["run_id"] for row in plan}) != 63:
        raise RuntimeError("V3 plan does not contain 63 unique rows")
    if {row["run_id"] for row in plan} & previous_run_ids():
        raise RuntimeError("V3 plan reused an invalidated run ID")
    (args.output / "run_plan.json").write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (args.output / "condition_map.json").write_text(json.dumps(condition_map, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    state = {
        "plan_run_ids": [row["run_id"] for row in plan],
        "run_status": {row["run_id"]: "PENDING" for row in plan},
        "completed_run_ids": [],
        "model_calls": 0,
    }
    (args.output / "resume_state.json").write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    task_contexts = {task: [(CONTEXTS_ROOT / condition / task / "context.txt").read_text(encoding="utf-8") for condition in CONDITIONS] for task in TASKS}
    raw_prefixes = {}
    for task in TASKS:
        prefixes = set()
        for condition in CONDITIONS:
            manifest = json.loads((CONTEXTS_ROOT / condition / "manifest.json").read_text(encoding="utf-8"))
            prefixes.add(next(item["raw_prefix_sha256"] for item in manifest if Path(item["bundle"]).name == task))
        raw_prefixes[task] = sorted(prefixes)
    context_equal = all(len(prefixes) == 1 for prefixes in raw_prefixes.values())
    contracts: dict[str, dict[str, object]] = {}
    rows: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="action-compliance-v3-dry-run-") as raw:
        root = Path(raw)
        bases: dict[str, Path] = {}
        for task in TASKS:
            setup, base = setup_command(task, root)
            process = run(setup, cwd=ROOT, timeout=3600)
            (args.output / f"{task}.base_setup.log").write_text(process.stdout + process.stderr, encoding="utf-8")
            if process.returncode != 0:
                raise RuntimeError(f"base setup failed for {task}: {process.stdout}{process.stderr}")
            ignore_untracked(base)
            actual = checked(["git", "rev-parse", "HEAD"], cwd=base, timeout=60).stdout.strip()
            if actual != REPOSITORIES[task][1]:
                raise RuntimeError(f"base SHA mismatch for {task}")
            metadata = _setup_metadata(base, expected_task=task)
            contracts[task] = {
                "task": task,
                "pinned_sha": actual,
                "interpreter": metadata["interpreter"],
                "test_command": metadata["test_command"],
                "test_cwd": metadata["test_cwd"],
                "test_env": metadata["test_env"],
                "contract_version": metadata["contract_version"],
            }
            bases[task] = base
        (args.output / "task_test_contract.json").write_text(json.dumps(contracts, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        for row in plan:
            run_id = row["run_id"]
            task = row["task"]
            state["run_status"][run_id] = "RUNNING"
            temporary = args.output / "resume_state.json.tmp"
            temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            temporary.replace(args.output / "resume_state.json")
            worktree = root / "runs" / run_id / "worktree"
            worktree.parent.mkdir(parents=True, exist_ok=True)
            added = run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"], cwd=bases[task], timeout=600)
            if added.returncode != 0:
                raise RuntimeError(f"worktree creation failed for {run_id}: {added.stdout}{added.stderr}")
            actual = checked(["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60).stdout.strip()
            status_before = checked(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            marker = worktree / f"decisiontrace_v3_dry_run_{run_id}.txt"
            marker.write_text(run_id + "\n", encoding="utf-8")
            status_after = checked(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            checked(["git", "add", "-A"], cwd=worktree, timeout=120)
            patch = checked(["git", "diff", "--cached", "--binary", "--no-ext-diff"], cwd=worktree, timeout=120).stdout
            patch_path = args.output / "patches" / f"{run_id}.diff"
            patch_path.parent.mkdir(parents=True, exist_ok=True)
            patch_path.write_text(patch, encoding="utf-8")
            checked(["git", "reset", "--hard", "HEAD"], cwd=worktree, timeout=120)
            checked(["git", "clean", "-fd"], cwd=worktree, timeout=120)
            clean = checked(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            removed = run(["git", "worktree", "remove", "--force", str(worktree)], cwd=bases[task], timeout=120)
            if removed.returncode != 0:
                raise RuntimeError(f"worktree cleanup failed for {run_id}: {removed.stdout}{removed.stderr}")
            condition = condition_map[run_id]["condition"]
            context = (CONTEXTS_ROOT / condition / task / "context.txt").read_text(encoding="utf-8")
            prompt = assemble_prompt(context)
            command = build_codex_command(prompt)
            metadata = contracts[task]
            rows.append({
                "run_id": run_id,
                "task": task,
                "round": row["round"],
                "condition_context_attached": prompt.endswith(context),
                "context_sha256": digest(context),
                "codex_command_assembled": command[:-1] + ["<PROMPT>"],
                "approval_never": "-a" in command and "never" in command,
                "grader_path": str(ROOT / "pilot" / task / "grader.py"),
                "interpreter": metadata["interpreter"],
                "test_command": metadata["test_command"],
                "test_cwd": metadata["test_cwd"],
                "test_env": metadata["test_env"],
                "status_before_model": status_before,
                "status_after_new_file": status_after,
                "full_worktree_created": actual == REPOSITORIES[task][1],
                "patch_has_new_file": "new file mode" in patch or "--- /dev/null" in patch,
                "patch_sha256": digest(patch),
                "cleanup": not clean.strip(),
                "coding_agent_called": False,
            })
            state["run_status"][run_id] = "USABLE_COMPLETE"
            state["completed_run_ids"].append(run_id)
            temporary = args.output / "resume_state.json.tmp"
            temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            temporary.replace(args.output / "resume_state.json")
        for base in bases.values():
            checked(["git", "worktree", "prune"], cwd=base, timeout=60)

    result = {
        "planned_runs": len(plan),
        "task_count": len(TASKS),
        "conditions": len(CONDITIONS),
        "repetitions": 3,
        "round_counts": {str(number): sum(row["round"] == number for row in plan) for number in (1, 2, 3)},
        "opaque_run_ids": len({row["run_id"] for row in plan}) == 63 and all(len(row["run_id"]) == 32 for row in plan),
        "fresh_run_ids": not ({row["run_id"] for row in plan} & previous_run_ids()),
        "randomized_order": len({tuple(condition_map[row["run_id"]]["condition"] for row in plan if row["task"] == task and row["repetition"] == 1) for task in TASKS}) > 1,
        "condition_map_separate": True,
        "raw_context_equal": context_equal,
        "full_worktree_creation": len(rows) == 63 and all(row["full_worktree_created"] for row in rows),
        "normalized_contract": len(contracts) == 7 and all(row["interpreter"] == row["test_command"][0] for row in contracts.values()),
        "correct_test_commands": len(rows) == 63 and all(row["test_command"] for row in rows),
        "context_attachment": all(row["condition_context_attached"] for row in rows),
        "codex_command_assembly": all(row["codex_command_assembled"][1:3] == ["-a", "never"] and row["codex_command_assembled"][3] == "-c" for row in rows),
        "approval_never": all(row["approval_never"] for row in rows),
        "patch_capture": len(rows) == 63 and all(row["patch_has_new_file"] for row in rows),
        "cleanup": len(rows) == 63 and all(row["cleanup"] for row in rows),
        "resume_state": len(state["completed_run_ids"]) == 63 and all(value == "USABLE_COMPLETE" for value in state["run_status"].values()),
        "result_schema": all({"run_id", "task", "interpreter", "test_command", "grader_path", "patch_sha256"} <= row.keys() for row in rows),
        "coding_agents_called": any(row["coding_agent_called"] for row in rows),
        "model_calls": 0,
        "contracts": contracts,
        "rows": rows,
    }
    (args.output / "dry_run_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    required = ("planned_runs", "full_worktree_creation", "normalized_contract", "correct_test_commands", "context_attachment", "codex_command_assembly", "approval_never", "patch_capture", "cleanup", "resume_state", "result_schema")
    if not all(result[key] for key in required) or result["coding_agents_called"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
