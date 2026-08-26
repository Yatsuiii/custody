#!/usr/bin/env python3
"""Cost/token/runtime pilot for the action-compliance coding backend.

NOT part of the frozen 63-run dataset. Writes to data/action_compliance/cost_pilot/,
which is excluded from ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_SHA256.txt and from
run_plan.json, so running this does not consume a real run_id or trigger the
"no changes after first comparative output" freeze on the actual experiment.

Runs the frozen Claude Code CLI backend (ACTION_COMPLIANCE_RUN_PROTOCOL.md #3)
against real task contexts to measure actual cost/tokens/tool-calls/runtime,
so the 63-run cost can be extrapolated from real numbers instead of guesses.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_PATH = ROOT / "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt"
MODEL = "claude-sonnet-4-5-20250929"


def _setup_worktree(task: str, target: Path) -> None:
    task_dir = ROOT / "pilot" / task
    script = task_dir / "worktree_setup.sh"
    result = subprocess.run(
        ["bash", str(script), str(target)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"worktree setup failed for {task}: {result.stderr}")


def _run_agent(worktree: Path, user_prompt: str, budget_usd: float) -> tuple[list[dict], float]:
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    args = [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--safe-mode",
        "--system-prompt", system_prompt,
        "--tools", "Read,Edit,Bash",
        "--permission-mode", "bypassPermissions",
        "--model", MODEL,
        "--max-budget-usd", str(budget_usd),
        user_prompt,
    ]
    start = time.monotonic()
    proc = subprocess.run(
        args,
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ},
    )
    elapsed = time.monotonic() - start
    events = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if proc.returncode != 0 and not events:
        events.append({"type": "error", "stderr": proc.stderr[-4000:], "returncode": proc.returncode})
    return events, elapsed


def _tool_call_count(events: list[dict]) -> int:
    count = 0
    for event in events:
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                count += 1
    return count


def _result_row(events: list[dict]) -> dict:
    for event in events:
        if event.get("type") == "result":
            return event
    return {}


def run_one(task: str, condition: str, repetition: int, output_root: Path, budget_usd: float) -> dict:
    context_path = ROOT / "data" / "action_compliance" / "contexts" / condition / task / "context.txt"
    user_prompt = context_path.read_text(encoding="utf-8")
    run_dir = output_root / f"{task}__{condition}__rep{repetition}"
    worktree = run_dir / "worktree"
    _setup_worktree(task, worktree)
    events, elapsed = _run_agent(worktree, user_prompt, budget_usd)
    subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True, text=True, timeout=60)
    patch = subprocess.run(
        ["git", "diff", "--cached", "--binary", "--no-ext-diff"],
        cwd=worktree, capture_output=True, text=True, timeout=60,
    ).stdout
    result = _result_row(events)
    row = {
        "task": task,
        "condition": condition,
        "repetition": repetition,
        "wall_seconds": round(elapsed, 1),
        "tool_calls": _tool_call_count(events),
        "num_turns": result.get("num_turns"),
        "total_cost_usd": result.get("total_cost_usd"),
        "input_tokens": (result.get("usage") or {}).get("input_tokens"),
        "output_tokens": (result.get("usage") or {}).get("output_tokens"),
        "cache_creation_input_tokens": (result.get("usage") or {}).get("cache_creation_input_tokens"),
        "cache_read_input_tokens": (result.get("usage") or {}).get("cache_read_input_tokens"),
        "is_error": result.get("is_error"),
        "patch_bytes": len(patch),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8"
    )
    (run_dir / "patch.diff").write_text(patch, encoding="utf-8")
    (run_dir / "row.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=ROOT / "data" / "action_compliance" / "cost_pilot")
    parser.add_argument("--budget-usd", type=float, default=1.0)
    parser.add_argument(
        "--plan",
        nargs="+",
        default=["task-03-pip-inline-script-metadata:A:1",
                  "task-03-pip-inline-script-metadata:B:1",
                  "task-03-pip-inline-script-metadata:C:1",
                  "task-03-pip-inline-script-metadata:C:2"],
        help="task:condition:repetition entries",
    )
    args = parser.parse_args()
    rows = []
    for entry in args.plan:
        task, condition, repetition = entry.split(":")
        print(f"running {entry} ...", flush=True)
        row = run_one(task, condition, int(repetition), args.output_root, args.budget_usd)
        print(json.dumps(row), flush=True)
        rows.append(row)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
