#!/usr/bin/env python3
"""Run the complete V5 orchestration with zero coding-model calls."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path

import run_action_compliance_codex as runner
from action_compliance_v4_storage import V4StoragePolicy
from setup_action_compliance_full_worktree import REPOSITORIES


ROOT = runner.ROOT
V5_SEED = 2026082601
TASKS = runner.TASKS
CONDITIONS = runner.CONDITIONS


def _unexpected_setup_status(status: str) -> str:
    allowed_prefixes = ("?? .venv/", "?? .decisiontrace_setup_metadata.json")
    return "\n".join(
        line for line in status.splitlines() if line and not line.startswith(allowed_prefixes)
    )


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _save_state(path: Path, state: dict[str, object]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _previous_ids() -> set[str]:
    ids: set[str] = set()
    for path in (
        ROOT / "data/action_compliance/invalidated_sparse_checkout_run/run_plan.json",
        ROOT / "data/action_compliance/invalidated_v2_test_discovery_run/run_plan.json",
        ROOT / "data/action_compliance/codex_runs_v3/run_plan.json",
        ROOT / "data/action_compliance/codex_runs_v4_host/run_plan.json",
    ):
        if path.exists():
            ids.update(row["run_id"] for row in json.loads(path.read_text(encoding="utf-8")))
    return ids


def _cycle(
    plan_row: dict[str, object],
    *,
    output: Path,
    storage: V4StoragePolicy,
    slot: int,
    condition: str,
) -> dict[str, object]:
    run_id = str(plan_row["run_id"])
    task = str(plan_row["task"])
    context_path = Path(str(plan_row["context_path"]))
    context = context_path.read_text(encoding="utf-8")
    prompt = runner.assemble_prompt(context)
    command = runner.build_codex_command(prompt, model=runner.MODEL, reasoning_effort=runner.REASONING_EFFORT)
    run_output = output / "rows" / run_id
    run_output.mkdir(parents=True, exist_ok=True)
    with storage.lifecycle(run_id=run_id, slot=slot):
        env = storage.environment(slot)
        setup_args, worktree = runner._setup_args(task, storage.slot_root(slot), storage=storage, slot=slot)
        setup = runner._run(setup_args, cwd=ROOT, timeout=3600, env=env)
        (run_output / "setup.log").write_text(setup.stdout + setup.stderr, encoding="utf-8")
        if setup.returncode != 0:
            raise RuntimeError(f"setup failed for {run_id}: {setup.stdout}{setup.stderr}")
        runner._ignore_setup_untracked(worktree, env=env)
        metadata = runner._setup_metadata(worktree, expected_task=task)
        actual_sha = runner._checked(["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60, env=env).stdout.strip()
        status_before = runner._git_status(worktree, env=env)
        if _unexpected_setup_status(status_before).strip():
            raise RuntimeError(f"unexpected setup status for {run_id}: {status_before}")

        tracked_candidates = runner._checked(["git", "ls-files"], cwd=worktree, timeout=60, env=env).stdout.splitlines()
        if not tracked_candidates:
            raise RuntimeError(f"no tracked file available for {run_id}")
        tracked = worktree / tracked_candidates[0]
        original = tracked.read_bytes()
        tracked.write_bytes(original + b"\n# V4 dry-run tracked modification.\n")
        new_file = worktree / f"decisiontrace_v4_dry_run_new_{run_id}.txt"
        new_file.write_text(run_id + "\n", encoding="utf-8")
        status_after = runner._git_status(worktree, env=env)
        runner._checked(["git", "add", "-A"], cwd=worktree, timeout=120, env=env)
        patch = runner._checked(
            ["git", "diff", "--cached", "--binary", "--no-ext-diff"], cwd=worktree, timeout=120, env=env
        ).stdout
        patch_path = run_output / "patch.diff"
        patch_path.write_text(patch, encoding="utf-8")
        has_new = "new file mode" in patch or "--- /dev/null" in patch
        runner._restore_clean_worktree(task, worktree, env=env)
        clean = not _unexpected_setup_status(runner._git_status(worktree, env=env)).strip()
        if not clean:
            raise RuntimeError(f"dry-run reset was not clean for {run_id}")

        row = {
            "run_id": run_id,
            "task": task,
            "repetition": plan_row["repetition"],
            "round": plan_row["round"],
            "condition_context_attached": prompt.endswith(context),
            "condition": condition,
            "context_sha256": _digest(context),
            "codex_command_assembled": command[:-1] + ["<PROMPT>"],
            "approval_never": command[1:3] == ["-a", "never"],
            "model": runner.MODEL,
            "reasoning_effort": runner.REASONING_EFFORT,
            "grader_path": str(ROOT / "pilot" / task / "grader.py"),
            "interpreter": metadata["interpreter"],
            "test_command": metadata["test_command"],
            "test_cwd": metadata["test_cwd"],
            "test_env": metadata["test_env"],
            "pinned_sha": actual_sha,
            "expected_pinned_sha": REPOSITORIES[task][1],
            "full_worktree": metadata["full_worktree"],
            "sparse_checkout": metadata["sparse_checkout"],
            "status_before_model": status_before,
            "status_after_dummy_edit": status_after,
            "patch_capture": "git add -A && git diff --cached --binary --no-ext-diff",
            "patch_has_new_file": has_new,
            "patch_sha256": _digest(patch),
            "reset_clean": clean,
            "cleanup": True,
            "coding_agent_called": False,
            "model_calls": 0,
        }
        (run_output / "row.json").write_text(json.dumps(row, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.concurrency != 2:
        raise SystemExit("V4 dry run requires exactly two worker slots")

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    storage = V4StoragePolicy(args.storage_root.resolve(), worker_count=2)
    storage.initialize()
    storage.recover_abandoned()
    state_path = output / "resume_state.json"
    if args.resume:
        plan = json.loads((output / "run_plan.json").read_text(encoding="utf-8"))
        condition_map = json.loads((output / "condition_map.json").read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for run_id, status in state["run_status"].items():
            if status == "RUNNING":
                state["run_status"][run_id] = "PENDING"
        state["model_calls"] = 0
        _save_state(state_path, state)
    else:
        plan, condition_map = runner.build_plan(runner.CONTEXTS_ROOT, repetitions=3, seed=V5_SEED)
        if len(plan) != 63 or len({row["run_id"] for row in plan}) != 63:
            raise RuntimeError("V4 dry-run plan is not 63 unique rows")
        if set(row["task"] for row in plan) != set(TASKS):
            raise RuntimeError("V4 dry-run task set mismatch")
        if _previous_ids() & {row["run_id"] for row in plan}:
            raise RuntimeError("V4 dry-run reused an invalidated run ID")
        (output / "run_plan.json").write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (output / "condition_map.json").write_text(json.dumps(condition_map, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        state = {
            "plan_run_ids": [row["run_id"] for row in plan],
            "run_status": {row["run_id"]: "PENDING" for row in plan},
            "completed_run_ids": [],
            "model_calls": 0,
        }
        _save_state(state_path, state)
    if len(plan) != 63 or len({row["run_id"] for row in plan}) != 63:
        raise RuntimeError("V4 dry-run plan is not 63 unique rows")
    if set(row["task"] for row in plan) != set(TASKS):
        raise RuntimeError("V4 dry-run task set mismatch")
    if _previous_ids() & {row["run_id"] for row in plan}:
        raise RuntimeError("V4 dry-run reused an invalidated run ID")
    rows: list[dict[str, object]] = []
    for run_id in state["completed_run_ids"]:
        row_path = output / "rows" / run_id / "row.json"
        if not row_path.is_file():
            raise RuntimeError(f"completed dry-run row is missing: {run_id}")
        rows.append(json.loads(row_path.read_text(encoding="utf-8")))
    pending_plan = [row for row in plan if state["run_status"].get(row["run_id"]) == "PENDING"]
    for start in range(0, len(pending_plan), 2):
        batch = pending_plan[start:start + 2]
        for row in batch:
            state["run_status"][row["run_id"]] = "RUNNING"
        _save_state(state_path, state)
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="v4-dry-run") as executor:
            futures = {
                executor.submit(
                    _cycle,
                    row,
                    output=output,
                    storage=storage,
                    slot=slot,
                    condition=condition_map[row["run_id"]]["condition"],
                ): row
                for slot, row in enumerate(batch)
            }
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                state["run_status"][row["run_id"]] = "USABLE_COMPLETE"
                state["completed_run_ids"].append(row["run_id"])
                _save_state(state_path, state)
    rows.sort(key=lambda row: next(index for index, plan_row in enumerate(plan) if plan_row["run_id"] == row["run_id"]))
    state["completed_run_ids"] = sorted(state["completed_run_ids"])
    _save_state(state_path, state)
    result = {
        "planned_runs": len(plan),
        "completed_runs": len(rows),
        "task_count": len(TASKS),
        "conditions": len(CONDITIONS),
        "repetitions": 3,
        "round_counts": {str(number): sum(row["round"] == number for row in plan) for number in (1, 2, 3)},
        "opaque_run_ids": len({row["run_id"] for row in plan}) == 63 and all(len(row["run_id"]) == 32 for row in plan),
        "fresh_run_ids": not (_previous_ids() & {row["run_id"] for row in plan}),
        "randomized_order": len({row["run_id"] for row in plan}) == 63,
        "condition_map_separate": True,
        "context_attachment": all(row["condition_context_attached"] for row in rows),
        "a_b_c_augmentation": {row["condition"] for row in rows} == set(CONDITIONS),
        "codex_command_assembly": all(row["codex_command_assembled"][0:3] == ["codex", "-a", "never"] for row in rows),
        "approval_never": all(row["approval_never"] for row in rows),
        "full_worktree_creation": all(row["pinned_sha"] == row["expected_pinned_sha"] and row["full_worktree"] for row in rows),
        "no_sparse_checkout": all(row["sparse_checkout"] is False for row in rows),
        "normalized_contract": all(row["interpreter"] == row["test_command"][0] for row in rows),
        "correct_test_commands": all(row["test_command"] and row["test_cwd"] is not None for row in rows),
        "patch_capture": all(row["patch_has_new_file"] for row in rows),
        "cleanup": all(row["cleanup"] and row["reset_clean"] for row in rows),
        "resume_state": len(state["completed_run_ids"]) == 63 and all(value == "USABLE_COMPLETE" for value in state["run_status"].values()),
        "grader_paths": all(Path(row["grader_path"]).is_file() for row in rows),
        "result_schema": all({"run_id", "task", "interpreter", "test_command", "patch_sha256"} <= row.keys() for row in rows),
        "model_calls": 0,
        "coding_agents_called": any(row["coding_agent_called"] for row in rows),
        "rows": rows,
    }
    (output / "dry_run_result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, sort_keys=True, indent=2))
    required = (
        "planned_runs", "completed_runs", "context_attachment", "a_b_c_augmentation",
        "codex_command_assembly", "approval_never", "full_worktree_creation",
        "no_sparse_checkout", "normalized_contract", "correct_test_commands",
        "patch_capture", "cleanup", "resume_state", "grader_paths", "result_schema",
    )
    return 0 if all(result[key] for key in required) and not result["coding_agents_called"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
