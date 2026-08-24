#!/usr/bin/env python3
"""Supervise the non-security Firestore contract probe.

The child owns the storage operations. This parent owns process supervision and
the terminal evidence contract, so an import failure, timeout, signal, or
silent exit cannot be mistaken for a passing integration probe.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_TERMINAL_STATUSES = frozenset({"PASS", "FAIL", "BLOCKED"})
DEFAULT_OUTPUT = ROOT / "proof-out" / "firestore-contract-probe.json"
DEFAULT_TIMEOUT_SECONDS = 180


def _write_json_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
            json.dump(value, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _git(*arguments: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={ROOT}",
            *arguments,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _repository_metadata() -> dict[str, object]:
    branch_code, branch, branch_error = _git("branch", "--show-current")
    sha_code, sha, sha_error = _git("rev-parse", "HEAD")
    remote_sha = ""
    remote_error = ""
    if branch:
        remote_code, remote_output, remote_error = _git(
            "ls-remote", "origin", f"refs/heads/{branch}"
        )
        if remote_code == 0 and remote_output:
            remote_sha = remote_output.split()[0]
    return {
        "repository_root": str(ROOT),
        "branch": branch,
        "branch_command_ok": branch_code == 0,
        "branch_error": branch_error,
        "sha": sha,
        "sha_command_ok": sha_code == 0,
        "sha_error": sha_error,
        "remote_sha": remote_sha,
        "remote_error": remote_error,
        "local_remote_equal": bool(sha and remote_sha and sha == remote_sha),
    }


def _sdk_versions() -> dict[str, str | None]:
    names = ("google-cloud-firestore", "google-api-core", "grpcio")
    return {name: _version(name) for name in names}


def _version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _start_record(*, output: Path, timeout_seconds: int) -> dict[str, object]:
    return {
        "status": "START",
        "started_at": datetime.now(UTC).isoformat(),
        "output": str(output),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "sys_path": list(sys.path),
        "custody_package_path": str(ROOT / "custody"),
        "repository": _repository_metadata(),
        "sdk_versions": _sdk_versions(),
        "timeout_seconds": timeout_seconds,
        "network_started_after_artifact": True,
    }


def _terminal_failure(
    *,
    start: dict[str, object],
    output: Path,
    child_output: Path,
    reason: str,
    process: dict[str, object],
    child_result: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": "FAIL",
        "classification": "PROBE-HARNESS-FAIL",
        "terminal_reason": reason,
        "started": start,
        "finished_at": datetime.now(UTC).isoformat(),
        "output": str(output),
        "child_output": str(child_output),
        "process": process,
        "child_result": child_result,
        "security_metrics": False,
        "scorer_reads": 0,
        "model_calls": 0,
    }


def _load_child_result(path: Path) -> tuple[dict[str, object] | None, str | None]:
    if not path.exists():
        return None, "child result artifact is missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except BaseException as error:
        return None, f"child result artifact is unreadable: {error!r}"
    if not isinstance(value, dict):
        return None, "child result artifact is not a JSON object"
    status = value.get("status")
    if status not in ALLOWED_TERMINAL_STATUSES:
        return None, f"child result has no terminal status: {status!r}"
    return value, None


def supervise(
    *,
    project: str,
    prefix: str,
    output: Path,
    timeout_seconds: int,
) -> dict[str, object]:
    output = output.resolve()
    child_output = output.with_name(f".{output.stem}.child.json")
    start_path = output.with_name(f"{output.stem}.start.json")
    start = _start_record(output=output, timeout_seconds=timeout_seconds)
    _write_json_atomic(start_path, start)

    command = [
        sys.executable,
        str(ROOT / "scripts" / "firestore_contract_probe.py"),
        "--project",
        project,
        "--prefix",
        prefix,
        "--output",
        str(child_output),
    ]
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        process.kill()
        stdout, stderr = process.communicate()
        result = _terminal_failure(
            start=start,
            output=output,
            child_output=child_output,
            reason="child process exceeded the maximum runtime",
            process={
                "pid": process.pid,
                "returncode": process.returncode,
                "timed_out": True,
                "stdout": stdout,
                "stderr": stderr,
                "exception": repr(error),
            },
        )
        _write_json_atomic(output, result)
        return result

    child_result, child_error = _load_child_result(child_output)
    process_record = {
        "pid": process.pid,
        "returncode": process.returncode,
        "timed_out": False,
        "stdout": stdout,
        "stderr": stderr,
    }
    if child_error is not None:
        result = _terminal_failure(
            start=start,
            output=output,
            child_output=child_output,
            reason=child_error,
            process=process_record,
        )
        _write_json_atomic(output, result)
        return result
    if process.returncode == 0 and child_result["status"] != "PASS":
        result = _terminal_failure(
            start=start,
            output=output,
            child_output=child_output,
            reason="child exited zero without a PASS terminal status",
            process=process_record,
            child_result=child_result,
        )
        _write_json_atomic(output, result)
        return result

    result = {
        "status": child_result["status"],
        "classification": child_result.get("classification"),
        "terminal_reason": "child produced a terminal result",
        "started": start,
        "finished_at": datetime.now(UTC).isoformat(),
        "output": str(output),
        "child_output": str(child_output),
        "process": process_record,
        "child_result": child_result,
        "security_metrics": False,
        "scorer_reads": child_result.get("scorer_reads", 0),
        "model_calls": child_result.get("model_calls", 0),
    }
    _write_json_atomic(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="project-988bc9fe-092c-4b32-90c")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    arguments = parser.parse_args()
    if arguments.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    result = supervise(
        project=arguments.project,
        prefix=arguments.prefix,
        output=arguments.output,
        timeout_seconds=arguments.timeout_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
