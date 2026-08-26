#!/usr/bin/env python3
"""Run the 63-cycle model-free V5 storage lifecycle stress test."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time
import traceback

from action_compliance_v4_storage import V4StoragePolicy
from run_action_compliance_codex import (
    TASKS,
    _checked,
    _classify_test_output,
    _git_status,
    _ignore_setup_untracked,
    _prepare_test_probe,
    _restore_clean_worktree,
    _run,
    _setup_args,
    _setup_metadata,
    _test_spec,
    build_plan,
    capture_patch,
)


ROOT = Path(__file__).resolve().parents[1]
V5_STRESS_SEED = 2026082601


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _unexpected_setup_status(status: str) -> str:
    allowed_prefixes = ("?? .venv/", "?? .decisiontrace_setup_metadata.json")
    return "\n".join(
        line for line in status.splitlines() if line and not line.startswith(allowed_prefixes)
    )


def _dummy_tracked_edit(worktree: Path, index: int, *, env: dict[str, str]) -> Path:
    candidates = _checked(["git", "ls-files", "-z"], cwd=worktree, timeout=60, env=env).stdout.encode().split(b"\0")
    text_suffixes = {".c", ".cc", ".cpp", ".go", ".h", ".java", ".js", ".md", ".py", ".rs", ".txt"}
    for raw in candidates:
        if not raw:
            continue
        candidate = worktree / os.fsdecode(raw)
        if candidate.suffix not in text_suffixes or not candidate.is_file() or candidate.stat().st_size > 1_000_000:
            continue
        original = candidate.read_bytes()
        candidate.write_bytes(original + f"\n# V4_STORAGE_STRESS_TRACKED_{index}\n".encode())
        return candidate
    raise RuntimeError(f"no bounded text file available for dummy tracked edit in {worktree}")


def _run_cycle(task: str, index: int, slot: int, storage: V4StoragePolicy, records: Path) -> dict[str, object]:
    run_id = f"stress-{index:03d}-{task}"
    started = time.monotonic()
    record: dict[str, object] = {
        "run_id": run_id,
        "index": index,
        "slot": slot,
        "task": task,
        "model_calls": 0,
        "status": "RUNNING",
    }
    try:
        with storage.lifecycle(run_id=run_id, slot=slot):
            environment = storage.environment(slot)
            setup_args, worktree = _setup_args(task, storage.slot_root(slot), storage=storage, slot=slot)
            setup = _run(setup_args, cwd=ROOT, timeout=1800, env=environment)
            setup_log = setup.stdout + setup.stderr
            record["setup_returncode"] = setup.returncode
            record["setup_output_tail"] = setup_log[-2000:]
            if setup.returncode != 0:
                raise RuntimeError(f"setup failed for {task}: {setup_log[-2000:]}")
            metadata = _setup_metadata(worktree, expected_task=task)
            record["pinned_sha"] = metadata["pinned_sha"]
            record["full_worktree"] = metadata["full_worktree"]
            record["sparse_checkout"] = metadata["sparse_checkout"]
            _ignore_setup_untracked(worktree, env=environment)
            record["status_before"] = _git_status(worktree, env=environment)
            unexpected_before = _unexpected_setup_status(str(record["status_before"]))
            if unexpected_before:
                raise RuntimeError(f"setup left worktree dirty: {record['status_before']}")
            record["disk_after_setup"] = storage.measure(slot)

            command, cwd, env, probe_targets = _test_spec(task, worktree, storage.slot_root(slot))
            _prepare_test_probe(task, worktree, probe_targets)
            record["test_command"] = command
            record["test_cwd"] = str(cwd)
            record["test_env"] = env

            tracked = _dummy_tracked_edit(worktree, index, env=environment)
            new_file = worktree / f"decisiontrace_v4_storage_new_{index:03d}.txt"
            new_file.write_text(f"V4_STORAGE_STRESS_NEW_FILE_{index}\n", encoding="utf-8")
            record["tracked_edit"] = str(tracked.relative_to(worktree))
            record["new_file"] = str(new_file.relative_to(worktree))
            patch_path = records / "patches" / f"{index:03d}.diff"
            patch_meta = capture_patch(worktree, patch_path, env=environment)
            record["patch_capture"] = patch_meta
            if not patch_meta["patch_has_new_file"]:
                raise RuntimeError("new file was not captured by staged binary diff")
            record["disk_after_capture"] = storage.measure(slot)
            _restore_clean_worktree(task, worktree, env=environment)

            sanity_patch = ROOT / "pilot" / task / "sanity_patch_compliant.diff"
            apply = _run(
                ["git", "apply", "--whitespace=nowarn", str(sanity_patch)],
                cwd=worktree,
                timeout=120,
                env=environment,
            )
            if apply.returncode != 0:
                raise RuntimeError(f"sanity patch failed to apply: {(apply.stdout + apply.stderr)[-2000:]}")
            _prepare_test_probe(task, worktree, probe_targets)

            process = _run(command, cwd=cwd, timeout=900, env={**environment, **env})
            test_status = _classify_test_output(
                process, test_runner=str(metadata["test_runner"])
            )
            record["test_returncode"] = process.returncode
            record["test_execution_status"] = test_status
            record["tests_executed"] = test_status == "executed_with_tests"
            record["test_output_tail"] = ((process.stdout or "") + (process.stderr or ""))[-3000:]
            if not record["tests_executed"]:
                raise RuntimeError(f"test contract did not execute tests: {test_status}")
            record["disk_after_test"] = storage.measure(slot)
            _restore_clean_worktree(task, worktree, env=environment)
            record["status_after"] = _git_status(worktree, env=environment)
            unexpected_after = _unexpected_setup_status(str(record["status_after"]))
            if unexpected_after:
                raise RuntimeError(f"reset left worktree dirty: {record['status_after']}")
        record["status"] = "PASS"
    except Exception as error:
        record["status"] = "FAIL"
        record["error"] = repr(error)
        record["traceback"] = traceback.format_exc()
    record["wall_seconds"] = round(time.monotonic() - started, 3)
    _write_json(records / f"{index:03d}.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--records-root", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()
    if args.concurrency != 2:
        raise SystemExit("V5 stress test requires exactly two worker slots")
    storage = V4StoragePolicy(args.storage_root.resolve(), worker_count=2)
    storage.initialize()
    recovered = storage.recover_abandoned()
    initial_filesystem = storage.measure()
    initial_residual_bytes = storage.residual_bytes()
    plan, _ = build_plan(seed=V5_STRESS_SEED)
    if len(plan) != 63 or {row["task"] for row in plan} != set(TASKS):
        raise SystemExit("V5 stress schedule is not the frozen 63-row task design")
    records = args.records_root.resolve()
    records.mkdir(parents=True, exist_ok=True)
    _write_json(records / "stress_plan.json", {"seed": V5_STRESS_SEED, "rows": plan, "recovered": recovered})
    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="v4-storage-stress") as executor:
        for batch_start in range(0, len(plan), 2):
            batch = list(enumerate(plan[batch_start:batch_start + 2], start=batch_start))
            futures = {
                executor.submit(_run_cycle, row["task"], index, slot, storage, records): row
                for slot, (index, row) in enumerate(batch)
            }
            for future in as_completed(futures):
                results.append(future.result())
    results.sort(key=lambda row: int(row["index"]))
    failures = [row for row in results if row["status"] != "PASS"]
    final = {
        "planned_cycles": len(plan),
        "completed_cycles": len(results),
        "passed_cycles": len(results) - len(failures),
        "failed_cycles": len(failures),
        "model_calls": 0,
        "concurrency": 2,
        "initial_filesystem": initial_filesystem,
        "initial_residual_bytes": initial_residual_bytes,
        "failures": failures,
        "final_filesystem": storage.measure(),
        "residual_bytes": storage.residual_bytes(),
        "worktree_count": len(list(storage.slots.glob("slot-*/worktree"))),
        "recovery": recovered,
    }
    _write_json(records / "stress_result.json", final)
    print(json.dumps(final, sort_keys=True, indent=2))
    return 0 if not failures and final["worktree_count"] == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"V4_STORAGE_STRESS_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
