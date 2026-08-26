#!/usr/bin/env python3
"""Replay the seven frozen human sanity patches, never model output."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY312 = "/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python"
TASKS = (
    "task-02-django-index-together-superseded",
    "task-go-01-maps-sorted-keys",
    "task-03-pip-inline-script-metadata",
    "task-04-cpython-locale-encoding-scope",
    "task-05-packaging-manylinux-aliases",
    "task-06-opentofu-static-source-scope",
    "task-07-axum-optional-typed-header",
)


def _run(args: list[str], *, cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _setup(task: str, task_dir: Path, root: Path) -> tuple[list[str], Path, list[str]]:
    worktree = root / task / "worktree"
    script = task_dir / "worktree_setup.sh"
    if task == "task-02-django-index-together-superseded":
        return ["bash", str(script), str(worktree), PY312], worktree, []
    if task == "task-go-01-maps-sorted-keys":
        return ["bash", str(script), str(worktree), str(root / task / "go-cache")], worktree, []
    if task == "task-04-cpython-locale-encoding-scope":
        return ["bash", str(script), str(worktree)], worktree, [PY312]
    if task == "task-06-opentofu-static-source-scope":
        return ["bash", str(script), str(worktree), str(root / task / "go-cache")], worktree, [
            "go-cache", "modules-cache"
        ]
    if task == "task-07-axum-optional-typed-header":
        return [
            "bash", str(script), str(worktree),
            str(root / task / "cargo-home"), str(root / task / "cargo-target"),
        ], worktree, ["cargo-home", "cargo-target"]
    return ["bash", str(script), str(worktree)], worktree, []


def _grader(task: str, task_dir: Path, worktree: Path, patch: Path, root: Path, extra: list[str]) -> list[str]:
    grader = task_dir / "grader.py"
    if task == "task-02-django-index-together-superseded":
        return [
            PY312, str(grader), str(worktree), str(patch),
            str(worktree / ".venv" / "bin" / "python"),
        ]
    if task == "task-04-cpython-locale-encoding-scope":
        return [PY312, str(grader), str(worktree), str(patch), PY312]
    if task == "task-06-opentofu-static-source-scope":
        return [
            "python", str(grader), str(worktree), str(patch),
            str(root / task / "go-cache" / "build"),
            str(root / task / "go-cache" / "modules"),
        ]
    if task == "task-07-axum-optional-typed-header":
        return [
            "python", str(grader), str(worktree), str(patch),
            str(root / task / "cargo-home"), str(root / task / "cargo-target"),
        ]
    if task == "task-go-01-maps-sorted-keys":
        return ["python", str(grader), str(worktree), str(patch), str(root / task / "go-cache")]
    return ["python", str(grader), str(worktree), str(patch)]


def _booleans(output: str) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    for name in ("TASK_COMPLETED", "TESTS_PASS", "AUTHORITY_COMPLIANT"):
        match = re.search(rf"^{name}=(True|False)", output, re.MULTILINE)
        result[name] = None if match is None else match.group(1) == "True"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix="action-compliance-sanity-") as raw:
        replay_root = Path(raw)
        for task in TASKS:
            task_dir = ROOT / "pilot" / task
            setup_args, worktree, _ = _setup(task, task_dir, replay_root)
            setup = _run(setup_args, timeout=1200)
            setup_output = setup.stdout + setup.stderr
            task_row = {"task": task, "setup_returncode": setup.returncode}
            if setup.returncode != 0:
                task_row["setup_output_tail"] = "\n".join(setup_output.splitlines()[-40:])
                rows.append(task_row)
                continue
            for label in ("compliant", "violating"):
                patch = task_dir / f"sanity_patch_{label}.diff"
                try:
                    graded = _run(_grader(task, task_dir, worktree, patch, replay_root, []), timeout=900)
                    output = graded.stdout + graded.stderr
                    rows.append({
                        "task": task,
                        "patch": label,
                        "grader_returncode": graded.returncode,
                        **_booleans(output),
                        "output_tail": "\n".join(output.splitlines()[-40:]),
                    })
                except subprocess.TimeoutExpired as error:
                    rows.append({
                        "task": task,
                        "patch": label,
                        "grader_returncode": None,
                        "TASK_COMPLETED": None,
                        "TESTS_PASS": None,
                        "AUTHORITY_COMPLIANT": None,
                        "output_tail": f"timeout: {error}",
                    })
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(rows, sort_keys=True, indent=2) + "\n")
    print(json.dumps(rows, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
