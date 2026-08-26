#!/usr/bin/env python3
"""Shared execution contract for action-compliance test commands.

The setup script owns the command, cwd, environment, and observation mode.
This module owns only validation and language-neutral outcome normalization so
the runner and all graders observe the same process result.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "test-command-v2"
KNOWN_STATUSES = frozenset(
    {
        "executed_with_tests",
        "executed_zero_tests",
        "test_build_failed",
        "test_collection_failed",
        "test_command_error",
        "test_timeout",
        "unknown",
    }
)


def load_contract(worktree: Path, *, expected_task: str | None = None) -> dict[str, Any]:
    path = worktree / ".decisiontrace_setup_metadata.json"
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read test contract {path}: {error}") from error
    if not isinstance(contract, dict):
        raise RuntimeError(f"test contract is not an object: {path}")
    if contract.get("contract_version") != CONTRACT_VERSION:
        raise RuntimeError(
            f"unsupported test contract {contract.get('contract_version')!r}; "
            f"expected {CONTRACT_VERSION!r}"
        )
    if expected_task is not None and contract.get("task") != expected_task:
        raise RuntimeError(
            f"test contract task mismatch: expected {expected_task}, got {contract.get('task')}"
        )
    required = {
        "task",
        "interpreter",
        "test_command",
        "test_cwd",
        "test_env",
        "test_runner",
        "full_worktree",
        "sparse_checkout",
    }
    missing = sorted(required - contract.keys())
    if missing:
        raise RuntimeError(f"test contract missing fields: {missing}")
    if contract["full_worktree"] is not True or contract["sparse_checkout"] is not False:
        raise RuntimeError("test contract is not attached to a complete non-sparse worktree")
    interpreter = contract["interpreter"]
    command = contract["test_command"]
    if not isinstance(interpreter, str) or not isinstance(command, list):
        raise RuntimeError("test contract interpreter/command have invalid types")
    if not command or not all(isinstance(part, str) for part in command):
        raise RuntimeError("test contract command must be a non-empty string list")
    if command[0] != interpreter:
        raise RuntimeError("test contract command must begin with its interpreter")
    if not isinstance(contract["test_cwd"], str) or not isinstance(contract["test_env"], dict):
        raise RuntimeError("test contract cwd/environment have invalid types")
    if contract["test_runner"] not in {
        "go-test",
        "django-runtests",
        "pytest",
        "cpython-unittest",
        "cargo-test",
    }:
        raise RuntimeError(f"unknown test runner mode: {contract['test_runner']!r}")
    executable = interpreter
    if os.sep in executable:
        valid = Path(executable).is_file() and os.access(executable, os.X_OK)
    else:
        valid = shutil.which(executable) is not None
    if not valid:
        raise RuntimeError(f"test interpreter is unavailable: {executable}")
    return contract


def execute_contract(
    worktree: Path,
    *,
    expected_task: str,
    timeout: int = 1200,
    base_env: dict[str, str] | None = None,
) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    contract = load_contract(worktree, expected_task=expected_task)
    cwd = worktree / str(contract["test_cwd"])
    if not cwd.is_dir():
        raise RuntimeError(f"test contract cwd does not exist: {cwd}")
    environment = {
        **os.environ,
        **(base_env or {}),
        **{str(key): str(value) for key, value in contract["test_env"].items()},
    }
    try:
        process = subprocess.run(
            list(contract["test_command"]),
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise RuntimeError(f"test interpreter disappeared: {error}") from error
    return contract, process


def classify_process(
    process: subprocess.CompletedProcess[str], *, test_runner: str
) -> str:
    """Normalize process output without treating ambiguous output as a pass.

    A nonzero build failure is a known coding/test outcome, not a zero-test
    result.  Conversely, explicit zero-test output remains separate from both
    pass and fail.  Unknown is reserved for output that the frozen runner mode
    genuinely cannot interpret.
    """

    output = (process.stdout or "") + "\n" + (process.stderr or "")
    lowered = output.lower()

    if test_runner in {"pytest", "django-runtests", "cpython-unittest"}:
        zero_patterns = (
            r"\bno tests? ran\b",
            r"\bran 0 tests?\b",
            r"\brun 0 tests?\b",
            r"\b0 tests? collected\b",
            r"\bcollected 0 items?\b",
        )
        if any(re.search(pattern, lowered) for pattern in zero_patterns):
            return "executed_zero_tests"

    build_patterns = (
        "build failed",
        "could not compile",
        "cannot convert",
        "undefined:",
        "no required module provides package",
        "compilation failed",
    )
    if process.returncode != 0 and any(pattern in lowered for pattern in build_patterns):
        return "test_build_failed"

    if test_runner == "pytest":
        if re.search(r"\bcollected [1-9][0-9]* items?\b", lowered):
            return "executed_with_tests"
        if re.search(r"\b[1-9][0-9]* passed\b|\b[1-9][0-9]* failed\b", lowered):
            return "executed_with_tests"
        if "collection error" in lowered or "error collecting" in lowered:
            return "test_collection_failed"
    elif test_runner == "django-runtests":
        if re.search(r"\bran [1-9][0-9]* tests?\b|\btests? run\b", lowered):
            return "executed_with_tests"
        if "test database" in lowered or "testing against django" in lowered:
            return "executed_with_tests"
    elif test_runner == "cpython-unittest":
        if re.search(r"\bran [1-9][0-9]* tests?\b|\btests? run\b", lowered):
            return "executed_with_tests"
        if re.search(r"\bok\b|\bfailed \([^)]+\)", lowered):
            return "executed_with_tests"
    elif test_runner in {"go-test", "cargo-test"}:
        if test_runner == "go-test" and re.search(r"\[no test files\]|\[no tests? to run\]", lowered):
            return "executed_zero_tests"
        if test_runner == "cargo-test" and re.search(r"running 0 tests?", lowered):
            return "executed_zero_tests"
        if test_runner == "go-test" and re.search(r"\bok\s+\S+|\bfail\s+\S+|\b--- fail:", lowered):
            return "executed_with_tests"
        if test_runner == "cargo-test" and re.search(
            r"test result:\s+(?:ok|failed)|\b[1-9][0-9]* passed;|\btest .* \.{3} (?:ok|FAILED)",
            lowered,
        ):
            return "executed_with_tests"

    command_error_patterns = (
        "no such file or directory",
        "can't open file",
        "could not open",
        "cannot open",
        "file or directory not found",
        "unknown package",
        "no test target named",
    )
    if process.returncode != 0 and any(pattern in lowered for pattern in command_error_patterns):
        return "test_command_error"

    if process.returncode != 0 and test_runner in {"pytest", "django-runtests", "cpython-unittest"}:
        # The command reached the declared interpreter and produced a runner
        # failure, even when the framework omitted a summary line.
        return "test_collection_failed"

    return "unknown"


def result_fields(
    process: subprocess.CompletedProcess[str], *, test_runner: str
) -> dict[str, Any]:
    status = classify_process(process, test_runner=test_runner)
    return {
        "test_execution_status": status,
        "tests_executed": status == "executed_with_tests",
        "no_tests_ran": status == "executed_zero_tests",
        "tests_pass": process.returncode == 0 and status == "executed_with_tests",
        "test_returncode": process.returncode,
        "test_output": ((process.stdout or "") + (process.stderr or "")).strip(),
    }
