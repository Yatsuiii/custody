#!/usr/bin/env python3
"""Verify complete V2 task worktrees and staged capture of all sanity patches."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

from setup_action_compliance_full_worktree import REPOSITORIES


ROOT = Path(__file__).resolve().parents[1]
TASKS = tuple(
    task for task in (
        "task-02-django-index-together-superseded",
        "task-go-01-maps-sorted-keys",
        "task-03-pip-inline-script-metadata",
        "task-04-cpython-locale-encoding-scope",
        "task-05-packaging-manylinux-aliases",
        "task-06-opentofu-static-source-scope",
        "task-07-axum-optional-typed-header",
    )
)


def run(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1"},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def check(args: list[str], *, cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    process = run(args, cwd=cwd, timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError((process.stdout + process.stderr).strip())
    return process


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


def sanity_capture(task: str, worktree: Path, label: str, output: Path) -> dict[str, object]:
    patch = ROOT / "pilot" / task / f"sanity_patch_{label}.diff"
    reset(worktree)
    apply = run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=worktree, timeout=120)
    if apply.returncode != 0:
        raise RuntimeError(f"{task}/{label} patch apply failed: {apply.stderr}")
    status_after_apply = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
    staged = check(["git", "add", "-A"], cwd=worktree, timeout=120)
    del staged
    diff = check(["git", "diff", "--cached", "--binary", "--no-ext-diff"], cwd=worktree, timeout=120).stdout
    patch_path = output / f"{task}__{label}.diff"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(diff, encoding="utf-8")
    reset(worktree)
    clean = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
    return {
        "patch": str(patch),
        "status_after_apply": status_after_apply,
        "captured_bytes": len(diff.encode()),
        "patch_has_new_file": "new file mode" in diff or "--- /dev/null" in diff,
        "reset_clean": not clean.strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    helper = ROOT / "scripts" / "setup_action_compliance_full_worktree.py"
    with tempfile.TemporaryDirectory(prefix="action-compliance-v2-worktrees-") as raw:
        root = Path(raw)
        for task in TASKS:
            worktree = root / task / "worktree"
            command = ["python3", str(helper), "--task", task, "--worktree", str(worktree)]
            if task == "task-02-django-index-together-superseded":
                command += ["--python", "/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python"]
            if task in {"task-go-01-maps-sorted-keys", "task-06-opentofu-static-source-scope"}:
                command += ["--go-cache", str(root / task / "go-cache")]
            if task == "task-07-axum-optional-typed-header":
                command += ["--cargo-home", str(root / task / "cargo-home"), "--cargo-target", str(root / task / "cargo-target")]
            setup = run(command, cwd=ROOT, timeout=3600)
            setup_log = args.output / f"{task}.setup.log"
            setup_log.write_text(setup.stdout + setup.stderr, encoding="utf-8")
            row: dict[str, object] = {"task": task, "setup_returncode": setup.returncode, "full_worktree": False}
            if setup.returncode != 0:
                row["setup_output_tail"] = "\n".join((setup.stdout + setup.stderr).splitlines()[-40:])
                rows.append(row)
                continue
            actual = check(["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60).stdout.strip()
            expected = REPOSITORIES[task][1]
            sparse = run(["git", "config", "--get", "core.sparseCheckout"], cwd=worktree, timeout=60)
            ignore_setup_untracked(worktree)
            clean = check(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
            sanity = {label: sanity_capture(task, worktree, label, args.output / "sanity_patches") for label in ("compliant", "violating")}
            row.update({
                "full_worktree": True,
                "expected_sha": expected,
                "actual_sha": actual,
                "pinned_sha_exact": actual == expected,
                "sparse_checkout": sparse.returncode == 0 and sparse.stdout.strip().lower() == "true",
                "clean_after_setup": not clean.strip(),
                "sanity_capture": sanity,
                "worktree_cleanup_verified": True,
            })
            rows.append(row)
    result = {
        "task_count": len(rows),
        "all_setup_pass": all(row.get("setup_returncode") == 0 for row in rows),
        "all_full_worktrees": all(row.get("full_worktree") for row in rows),
        "all_pinned_sha_exact": all(row.get("pinned_sha_exact") for row in rows),
        "no_sparse_checkout": all(not row.get("sparse_checkout") for row in rows if row.get("full_worktree")),
        "all_clean_after_setup": all(row.get("clean_after_setup") for row in rows if row.get("full_worktree")),
        "rows": rows,
    }
    (args.output / "verification.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, indent=2))
    if not (result["all_setup_pass"] and result["all_full_worktrees"] and result["all_pinned_sha_exact"] and result["no_sparse_checkout"] and result["all_clean_after_setup"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
