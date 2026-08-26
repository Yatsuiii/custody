#!/usr/bin/env python3
"""Model-free V2 orchestration dry run using complete pinned worktrees."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
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
)
from setup_action_compliance_full_worktree import REPOSITORIES


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}, capture_output=True, text=True, timeout=timeout)


def check(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    process = run(args, cwd=cwd, timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError((process.stdout + process.stderr).strip())
    return process


def setup_command(task: str, root: Path) -> tuple[list[str], Path]:
    worktree = root / "bases" / task / "worktree"
    command = ["python3", str(ROOT / "scripts" / "setup_action_compliance_full_worktree.py"), "--task", task, "--worktree", str(worktree)]
    if task == "task-02-django-index-together-superseded":
        command += ["--python", "/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python"]
    if task in {"task-go-01-maps-sorted-keys", "task-06-opentofu-static-source-scope"}:
        command += ["--go-cache", str(root / "caches" / task / "go-cache")]
    if task == "task-07-axum-optional-typed-header":
        command += ["--cargo-home", str(root / "caches" / task / "cargo-home"), "--cargo-target", str(root / "caches" / task / "cargo-target")]
    return command, worktree


def ignore_untracked(worktree: Path) -> None:
    status = check(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=worktree, timeout=60).stdout
    paths = [line[3:] for line in status.splitlines() if line.startswith("?? ")]
    if paths:
        exclude = worktree / ".git" / "info" / "exclude"
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write("\n# V2 dry-run setup artifacts.\n")
            for path in paths:
                stream.write(f"/{path}\n")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=PLAN_SEED)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plan, condition_map = build_plan(CONTEXTS_ROOT, repetitions=3, seed=args.seed)
    (args.output / "run_plan.json").write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (args.output / "condition_map.json").write_text(json.dumps(condition_map, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    state = {"completed_run_ids": [], "plan_run_ids": [row["run_id"] for row in plan]}
    (args.output / "resume_state.json").write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    task_contexts = {}
    manifests = {}
    for task in TASKS:
        texts = [(CONTEXTS_ROOT / condition / task / "context.txt").read_text(encoding="utf-8") for condition in CONDITIONS]
        task_contexts[task] = texts
        manifests[task] = [json.loads((CONTEXTS_ROOT / condition / "manifest.json").read_text(encoding="utf-8")) for condition in CONDITIONS]
    raw_prefixes = {
        task: {
            next(item["raw_prefix_sha256"] for item in manifest if Path(item["bundle"]).name == task)
            for manifest in manifests[task]
        }
        for task in TASKS
    }
    context_equal = all(len(prefixes) == 1 for prefixes in raw_prefixes.values())
    context_ceiling = all(len(text.encode()) <= 8192 * 4 for texts in task_contexts.values() for text in texts)
    rows = []
    with tempfile.TemporaryDirectory(prefix="action-compliance-v2-dry-run-") as raw:
        root = Path(raw)
        bases = {}
        for task in TASKS:
            setup, base = setup_command(task, root)
            process = run(setup, cwd=ROOT, timeout=3600)
            (args.output / f"{task}.base_setup.log").write_text(process.stdout + process.stderr, encoding="utf-8")
            if process.returncode != 0:
                raise RuntimeError(f"base setup failed for {task}: {process.stdout}{process.stderr}")
            ignore_untracked(base)
            actual = check(["git", "rev-parse", "HEAD"], cwd=base, timeout=60).stdout.strip()
            if actual != REPOSITORIES[task][1]:
                raise RuntimeError(f"base SHA mismatch for {task}")
            bases[task] = base
        for row in plan:
            run_id = row["run_id"]
            task = row["task"]
            worktree = root / "runs" / run_id / "worktree"
            worktree.parent.mkdir(parents=True, exist_ok=True)
            added = run(["git", "worktree", "add", "--detach", str(worktree), "HEAD"], cwd=bases[task], timeout=600)
            if added.returncode != 0:
                raise RuntimeError(f"full worktree creation failed for {run_id}: {added.stdout}{added.stderr}")
            actual = check(["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60).stdout.strip()
            if actual != REPOSITORIES[task][1]:
                raise RuntimeError(f"run worktree SHA mismatch for {run_id}")
            status_before = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            marker = worktree / "decisiontrace_v2_dry_run_new_file.txt"
            marker.write_text(run_id + "\n", encoding="utf-8")
            status_after = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            check(["git", "add", "-A"], cwd=worktree, timeout=120)
            patch = check(["git", "diff", "--cached", "--binary", "--no-ext-diff"], cwd=worktree, timeout=120).stdout
            patch_path = args.output / "patches" / f"{run_id}.diff"
            patch_path.parent.mkdir(parents=True, exist_ok=True)
            patch_path.write_text(patch, encoding="utf-8")
            check(["git", "reset", "--hard", "HEAD"], cwd=worktree, timeout=120)
            check(["git", "clean", "-fd"], cwd=worktree, timeout=120)
            clean = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            removed = run(["git", "worktree", "remove", "--force", str(worktree)], cwd=bases[task], timeout=120)
            if removed.returncode != 0:
                raise RuntimeError(f"worktree cleanup failed for {run_id}: {removed.stdout}{removed.stderr}")
            prompt = assemble_prompt((CONTEXTS_ROOT / condition_map[run_id]["condition"] / task / "context.txt").read_text(encoding="utf-8"))
            rows.append({
                "run_id": run_id,
                "task": task,
                "round": row["round"],
                "context_attached": task in task_contexts,
                "context_sha256": sha256((CONTEXTS_ROOT / condition_map[run_id]["condition"] / task / "context.txt").read_text(encoding="utf-8")),
                "codex_command_assembled": build_codex_command(prompt)[:-1] + ["<PROMPT>"],
                "grader_path": str(ROOT / "pilot" / task / "grader.py"),
                "status_before_model": status_before,
                "status_after_new_file": status_after,
                "full_worktree_created": actual == REPOSITORIES[task][1],
                "patch_has_new_file": "new file mode" in patch or "--- /dev/null" in patch,
                "patch_sha256": sha256(patch),
                "cleanup": not clean.strip(),
                "coding_agent_called": False,
            })
            state["completed_run_ids"] = sorted(set(state["completed_run_ids"]) | {run_id})
            temporary = args.output / "resume_state.json.tmp"
            temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            temporary.replace(args.output / "resume_state.json")
        for base in bases.values():
            check(["git", "worktree", "prune"], cwd=base, timeout=60)
    result = {
        "planned_runs": len(plan),
        "task_count": len(TASKS),
        "conditions": len(CONDITIONS),
        "repetitions": 3,
        "round_counts": {str(number): sum(row["round"] == number for row in plan) for number in (1, 2, 3)},
        "opaque_run_ids": len({row["run_id"] for row in plan}) == 63 and all(len(row["run_id"]) == 32 for row in plan),
        "randomized_condition_order": len({tuple(condition_map[row["run_id"]]["condition"] for row in plan if row["task"] == task and row["round"] == 1) for task in TASKS}) > 0,
        "condition_map_separate": True,
        "raw_context_equal": context_equal,
        "context_ceiling": context_ceiling,
        "full_worktree_creation": len(rows) == 63 and all(row["full_worktree_created"] for row in rows),
        "patch_capture": len(rows) == 63 and all(row["patch_has_new_file"] for row in rows),
        "cleanup": len(rows) == 63 and all(row["cleanup"] for row in rows),
        "resume_state": len(state["completed_run_ids"]) == 63,
        "result_schema": all("run_id" in row and "grader_path" in row and "codex_command_assembled" in row for row in rows),
        "coding_agents_called": any(row["coding_agent_called"] for row in rows),
        "rows": rows,
    }
    (args.output / "dry_run_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    if not (result["planned_runs"] == 63 and result["task_count"] == 7 and result["full_worktree_creation"] and result["patch_capture"] and result["cleanup"] and result["resume_state"] and result["result_schema"] and not result["coding_agents_called"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
