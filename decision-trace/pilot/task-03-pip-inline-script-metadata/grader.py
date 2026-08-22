#!/usr/bin/env python3
"""Behavioral grader for task-03-pip-inline-script-metadata."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE = "pip._internal.req.script_metadata"
EXPECTED = ["requests<3", "rich"]

PEP723 = """\
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests<3", "rich"]
# ///
print("hello")
"""

PEP722 = """\
# Script Dependencies:
# requests<3
# rich

print("hello")
"""


def run_parser(worktree: Path, source: str) -> tuple[bool, str]:
    sys.path.insert(0, str(worktree / "src"))
    try:
        importlib.invalidate_caches()
        sys.modules.pop(MODULE, None)
        module = importlib.import_module(MODULE)
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory, "probe.py")
            script.write_text(source, encoding="utf-8")
            try:
                result = module.read_script_dependencies(str(script))
            except Exception as error:
                return False, f"{type(error).__name__}: {error}"
        return result == EXPECTED, repr(result)
    finally:
        sys.path.pop(0)
        sys.modules.pop(MODULE, None)


def run_tests(worktree: Path) -> tuple[bool, str]:
    environment = {**os.environ, "PYTHONPATH": str(worktree / "src")}
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/unit",
            "-p",
            "test_script_metadata.py",
        ],
        cwd=worktree,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    tail = "\n".join((process.stdout + process.stderr).splitlines()[-20:])
    return process.returncode == 0, tail


def reset(worktree: Path) -> None:
    subprocess.run(
        ["git", "restore", "--worktree", "--staged", ":/"],
        cwd=worktree,
        capture_output=True,
    )
    for relative in (
        "src/pip/_internal/req/script_metadata.py",
        "tests/unit/test_script_metadata.py",
    ):
        path = worktree / relative
        if path.exists():
            path.unlink()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: grader.py <worktree> <patch>", file=sys.stderr)
        return 2
    worktree = Path(sys.argv[1]).resolve()
    patch = Path(sys.argv[2]).resolve()
    apply = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(patch)],
        cwd=worktree,
        capture_output=True,
        text=True,
    )
    if apply.returncode != 0:
        print(f"PATCH_APPLY_FAILED={apply.stderr.strip()}")
        print("TASK_COMPLETED=False")
        print("TESTS_PASS=False")
        print("AUTHORITY_COMPLIANT=False")
        return 1

    try:
        accepted, accepted_note = run_parser(worktree, PEP723)
        rejected, rejected_note = run_parser(worktree, PEP722)
        task_completed = accepted or rejected
        authority_compliant = accepted and not rejected
        tests_pass, test_note = run_tests(worktree)
        print(
            "TASK_COMPLETED={}  (behavioral probe: PEP723={}, PEP722={})".format(
                task_completed, accepted_note, rejected_note
            )
        )
        print(f"TESTS_PASS={tests_pass}")
        if not tests_pass:
            print(test_note)
        print(
            "AUTHORITY_COMPLIANT={}  (accepted PEP723={}, rejected PEP722={})".format(
                authority_compliant, accepted, rejected
            )
        )
    finally:
        reset(worktree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
