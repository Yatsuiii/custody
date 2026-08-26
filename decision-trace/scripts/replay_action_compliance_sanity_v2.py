#!/usr/bin/env python3
"""Replay all frozen sanity patches against V2 complete worktrees."""

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


def run(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"}, capture_output=True, text=True, timeout=timeout)


def check(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    process = run(args, cwd=cwd, timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError((process.stdout + process.stderr).strip())
    return process


def setup_command(task: str, root: Path) -> tuple[list[str], Path]:
    worktree = root / task / "worktree"
    command = ["python3", str(ROOT / "scripts" / "setup_action_compliance_full_worktree.py"), "--task", task, "--worktree", str(worktree)]
    if task == "task-02-django-index-together-superseded":
        command += ["--python", PY312]
    if task in {"task-go-01-maps-sorted-keys", "task-06-opentofu-static-source-scope"}:
        command += ["--go-cache", str(root / task / "go-cache")]
    if task == "task-07-axum-optional-typed-header":
        command += ["--cargo-home", str(root / task / "cargo-home"), "--cargo-target", str(root / task / "cargo-target")]
    return command, worktree


def ignore_setup_untracked(worktree: Path) -> None:
    status = check(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=worktree, timeout=60).stdout
    paths = [line[3:] for line in status.splitlines() if line.startswith("?? ")]
    if paths:
        exclude = worktree / ".git" / "info" / "exclude"
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write("\n# V2 setup artifacts; never part of an agent patch.\n")
            for path in paths:
                stream.write(f"/{path}\n")


def reset(worktree: Path) -> None:
    check(["git", "reset", "--hard", "HEAD"], cwd=worktree, timeout=120)
    check(["git", "clean", "-fd"], cwd=worktree, timeout=120)


def grader_command(task: str, worktree: Path, patch: Path, root: Path) -> list[str]:
    grader = ROOT / "pilot" / task / "grader.py"
    if task == "task-02-django-index-together-superseded":
        return [PY312, str(grader), str(worktree), str(patch), str(worktree / ".venv" / "bin" / "python")]
    if task == "task-04-cpython-locale-encoding-scope":
        return [PY312, str(grader), str(worktree), str(patch), PY312]
    if task == "task-06-opentofu-static-source-scope":
        return ["python", str(grader), str(worktree), str(patch), str(root / task / "go-cache" / "build"), str(root / task / "go-cache" / "modules")]
    if task == "task-07-axum-optional-typed-header":
        return ["python", str(grader), str(worktree), str(patch), str(root / task / "cargo-home"), str(root / task / "cargo-target")]
    if task == "task-go-01-maps-sorted-keys":
        return ["python", str(grader), str(worktree), str(patch), str(root / task / "go-cache")]
    return ["python", str(grader), str(worktree), str(patch)]


def booleans(output: str) -> dict[str, bool | None]:
    result = {}
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
    with tempfile.TemporaryDirectory(prefix="action-compliance-sanity-v2-") as raw:
        root = Path(raw)
        for task in TASKS:
            setup, worktree = setup_command(task, root)
            setup_process = run(setup, cwd=ROOT, timeout=3600)
            (args.output / f"{task}.setup.log").write_text(setup_process.stdout + setup_process.stderr, encoding="utf-8")
            if setup_process.returncode != 0:
                rows.append({"task": task, "setup_returncode": setup_process.returncode})
                continue
            ignore_setup_untracked(worktree)
            for label in ("compliant", "violating"):
                patch = ROOT / "pilot" / task / f"sanity_patch_{label}.diff"
                reset(worktree)
                applied = run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=worktree, timeout=120)
                if applied.returncode != 0:
                    rows.append({"task": task, "patch": label, "patch_apply": False})
                    continue
                status = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
                check(["git", "add", "-A"], cwd=worktree, timeout=120)
                staged = check(["git", "diff", "--cached", "--binary", "--no-ext-diff"], cwd=worktree, timeout=120).stdout
                capture_path = args.output / "captured_patches" / f"{task}__{label}.diff"
                capture_path.parent.mkdir(parents=True, exist_ok=True)
                capture_path.write_text(staged, encoding="utf-8")
                reset(worktree)
                graded = run(grader_command(task, worktree, patch, root), cwd=ROOT, timeout=1800)
                output = graded.stdout + graded.stderr
                rows.append({
                    "task": task,
                    "patch": label,
                    "grader_returncode": graded.returncode,
                    "status_after_apply": status,
                    "captured_bytes": len(staged.encode()),
                    "patch_has_new_file": "new file mode" in staged or "--- /dev/null" in staged,
                    "reset_clean": not check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout.strip(),
                    **booleans(output),
                    "output_tail": "\n".join(output.splitlines()[-40:]),
                })
    result = {
        "row_count": len(rows),
        "all_grader_calls_passed": all(row.get("grader_returncode") == 0 for row in rows),
        "all_task_completed": all(row.get("TASK_COMPLETED") is True for row in rows),
        "compliant_authority": all(row.get("patch") != "compliant" or row.get("AUTHORITY_COMPLIANT") is True for row in rows),
        "violating_authority": all(row.get("patch") != "violating" or row.get("AUTHORITY_COMPLIANT") is False for row in rows),
        "rows": rows,
    }
    (args.output / "results.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    if not (result["row_count"] == 14 and result["all_grader_calls_passed"] and result["all_task_completed"] and result["compliant_authority"] and result["violating_authority"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
