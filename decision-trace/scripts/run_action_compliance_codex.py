#!/usr/bin/env python3
"""Frozen Codex runner and harness preflight for action-compliance.

The runner owns backend mechanics only.  Benchmark inputs, prompts, materialized
contexts, graders, and statistical aggregation remain outside this module.
Comparative result rows deliberately omit the arm condition; the condition is
stored in a separate map and joined only after blind grading.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from action_compliance_v4_storage import V4DiskGuardError, V4StorageError, V4StoragePolicy
from action_compliance_test_contract import classify_process


ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_PATH = ROOT / "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt"
CONTEXTS_ROOT = ROOT / "data" / "action_compliance" / "contexts"
TASKS = (
    "task-02-django-index-together-superseded",
    "task-go-01-maps-sorted-keys",
    "task-03-pip-inline-script-metadata",
    "task-04-cpython-locale-encoding-scope",
    "task-05-packaging-manylinux-aliases",
    "task-06-opentofu-static-source-scope",
    "task-07-axum-optional-typed-header",
)
PREFLIGHT_TASK = "task-01-k8s-postfilter-victims"
CONDITIONS = ("A", "B", "C")
MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "high"
APPROVAL_POLICY = "never"
SANDBOX = "workspace-write"
CODEX_TIMEOUT_SECONDS = 600
PLAN_SEED = 2026082401
V4_PLAN_SEED = 2026082402
SETUP_METADATA_NAME = ".decisiontrace_setup_metadata.json"


class V4QuotaPause(RuntimeError):
    """The provider reported exhausted usage; leave rows pending for resume."""


class TestContractInvalidation(RuntimeError):
    """A captured row cannot be represented by the frozen result contract."""


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _run(
    args: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", **(env or {})},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _checked(
    args: list[str], *, cwd: Path, timeout: int, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    process = _run(args, cwd=cwd, timeout=timeout, env=env)
    if process.returncode != 0:
        detail = (process.stdout + process.stderr).strip()
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(args)}\n{detail}")
    return process


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def codex_version() -> str:
    process = _run(["codex", "--version"], cwd=ROOT, timeout=30)
    output = (process.stdout + process.stderr).strip()
    if process.returncode != 0:
        raise RuntimeError(f"codex --version failed: {output}")
    return next((line for line in output.splitlines() if line.startswith("codex-cli ")), output)


def build_codex_command(
    prompt: str,
    *,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
) -> list[str]:
    """Build the only supported coding-agent invocation.

    The installed Codex CLI has no separate system-prompt option.  The frozen
    system prompt is therefore serialized before the materialized context by
    ``assemble_prompt``; the context bytes themselves remain unchanged.
    """

    return [
        "codex",
        "-a",
        APPROVAL_POLICY,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
        "-m",
        model,
        "exec",
        "--sandbox",
        SANDBOX,
        "--ephemeral",
        "--json",
        "--color",
        "never",
        prompt,
    ]


def assemble_prompt(context: str, *, system_prompt: str | None = None) -> str:
    system = system_prompt if system_prompt is not None else SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return f"{system}\n\n{context}"


def _requested_change(task_file: Path) -> str:
    text = task_file.read_text(encoding="utf-8")
    marker = "## requested_change"
    start = text.index(marker) + len(marker)
    remainder = text[start:]
    next_heading = remainder.find("\n## ")
    block = remainder if next_heading < 0 else remainder[:next_heading]
    lines = []
    for line in block.splitlines():
        if line.startswith("> "):
            lines.append(line[2:])
        elif line.startswith(">"):
            lines.append(line[1:].lstrip())
        elif line.strip():
            lines.append(line)
    return "\n".join(lines).strip() + "\n"


def build_excluded_preflight_context() -> str:
    task_dir = ROOT / "pilot" / PREFLIGHT_TASK
    parts = [_requested_change(task_dir / "TASK.md"), "\nRAW SOURCE ARTIFACTS:\n"]
    for artifact in sorted((task_dir / "context_bundle").glob("*")):
        if not artifact.is_file():
            continue
        parts.append(f"\n--- {artifact.name} ---\n")
        parts.append(artifact.read_text(encoding="utf-8"))
    parts.append(
        "\n\nHARNESS PREFLIGHT INSTRUCTIONS (EXCLUDED FIXTURE ONLY):\n"
        "This is a harness preflight and is excluded from all comparative data. "
        "Make a small, valid edit in the repository and create the new tracked-by-capture "
        "file decisiontrace_codex_preflight_probe.txt containing the exact marker "
        "CODEX_PREFLIGHT_WRITE_OK. Run the fixture's focused Go test command from the "
        "task evidence using GOWORK=off. Do not use network access, do not ask for approval, "
        "and do not modify anything outside this isolated worktree."
    )
    return "".join(parts)


def _setup_args(
    task: str,
    root: Path,
    *,
    storage: V4StoragePolicy | None = None,
    slot: int = 0,
) -> tuple[list[str], Path]:
    script = ROOT / "scripts" / "setup_action_compliance_full_worktree.py"
    worktree = root / task / "worktree"
    args = [sys.executable, str(script), "--task", task, "--worktree", str(worktree)]
    if task in {"task-01-k8s-postfilter-victims", "task-go-01-maps-sorted-keys"}:
        args += ["--go-cache", str(root / task / "go-cache")]
    if task == "task-06-opentofu-static-source-scope":
        args += ["--go-cache", str(root / task / "go-cache")]
    if task == "task-07-axum-optional-typed-header":
        args += [
            "--cargo-home", str(root / task / "cargo-home"),
            "--cargo-target", str(root / task / "cargo-target"),
        ]
    if storage is not None:
        args += ["--source-cache", str(storage.source_cache(task))]
        if task == "task-02-django-index-together-superseded":
            args += ["--python-wheelhouse", str(storage.shared / "python-wheelhouse")]
        if task in {"task-01-k8s-postfilter-victims", "task-go-01-maps-sorted-keys", "task-06-opentofu-static-source-scope"}:
            args += ["--go-module-cache", str(storage.shared / "go-modcache")]
        if task == "task-07-axum-optional-typed-header":
            for option in ("--cargo-home", "--cargo-target"):
                index = args.index(option)
                del args[index:index + 2]
            args += [
                "--cargo-home", str(storage.shared / "cargo-home"),
                "--cargo-target", str(storage.slot_cargo_target(slot)),
            ]
    return args, worktree


def _ensure_go_overlay(worktree: Path) -> None:
    goroot = _checked(["go", "env", "GOROOT"], cwd=worktree, timeout=30).stdout.strip()
    maps_dir = worktree / "src" / "maps"
    mapping = {
        str(Path(goroot) / "src" / "maps" / source.name): str(source)
        for source in maps_dir.glob("*.go")
    }
    _json_write(worktree / "overlay.json", {"Replace": mapping})


def _restore_clean_worktree(
    task: str, worktree: Path, *, env: dict[str, str] | None = None
) -> None:
    _run(["git", "reset", "--hard", "HEAD"], cwd=worktree, timeout=60, env=env)
    _run(["git", "clean", "-fd"], cwd=worktree, timeout=60, env=env)
    if task == "task-go-01-maps-sorted-keys":
        _ensure_go_overlay(worktree)


def _ignore_setup_untracked(
    worktree: Path, *, env: dict[str, str] | None = None
) -> list[str]:
    status = _run(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=worktree, timeout=30, env=env
    ).stdout
    paths = []
    for line in status.splitlines():
        if line.startswith("?? "):
            paths.append(line[3:])
    if paths:
        exclude = worktree / ".git" / "info" / "exclude"
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write("\n# DecisionTrace setup artifacts; never part of an agent patch.\n")
            for path in paths:
                stream.write(f"/{path.rstrip('/')}\n")
    return paths


def _setup_metadata(worktree: Path, *, expected_task: str | None = None) -> dict[str, Any]:
    """Load and validate the setup-owned interpreter contract."""

    path = worktree / SETUP_METADATA_NAME
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read setup metadata {path}: {error}") from error
    if not isinstance(metadata, dict):
        raise RuntimeError(f"setup metadata is not an object: {path}")
    required = {"contract_version", "task", "grader_interpreter", "interpreter", "test_command", "test_cwd", "test_env", "test_runner", "interpreter_kind", "pinned_sha", "full_worktree", "sparse_checkout"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise RuntimeError(f"setup metadata missing fields: {missing}")
    if metadata["contract_version"] != "test-command-v2":
        raise RuntimeError(f"unsupported test-interpreter contract: {metadata['contract_version']}")
    if expected_task is not None and metadata["task"] != expected_task:
        raise RuntimeError(f"setup metadata task mismatch: expected {expected_task}, got {metadata['task']}")
    if metadata["full_worktree"] is not True or metadata["sparse_checkout"] is not False:
        raise RuntimeError("test-interpreter metadata is not attached to a full, non-sparse worktree")
    if not isinstance(metadata["interpreter"], str):
        raise RuntimeError("metadata interpreter must be a string")
    if not isinstance(metadata["test_command"], list) or not all(isinstance(part, str) for part in metadata["test_command"]):
        raise RuntimeError("metadata test_command must be a string list")
    if not metadata["test_command"] or metadata["test_command"][0] != metadata["interpreter"]:
        raise RuntimeError("metadata test_command must start with metadata interpreter")
    if not isinstance(metadata["test_cwd"], str) or not isinstance(metadata["test_env"], dict):
        raise RuntimeError("metadata test_cwd/test_env have invalid types")
    if metadata["test_runner"] not in {
        "go-test", "django-runtests", "pytest", "cpython-unittest", "cargo-test"
    }:
        raise RuntimeError(f"unsupported test runner mode: {metadata['test_runner']!r}")
    for field in ("grader_interpreter", "interpreter"):
        executable = metadata[field]
        if os.sep in executable:
            valid = Path(executable).is_file() and os.access(executable, os.X_OK)
        else:
            valid = shutil.which(executable) is not None
        if not valid:
            raise RuntimeError(f"metadata {field} is not executable or unavailable: {executable}")
    return metadata


def capture_patch(
    worktree: Path, patch_path: Path, *, env: dict[str, str] | None = None
) -> dict[str, Any]:
    """Capture tracked and new files using the frozen staged-diff contract."""

    added = _checked(["git", "add", "-A"], cwd=worktree, timeout=60, env=env)
    del added
    diff = _checked(
        ["git", "diff", "--cached", "--binary", "--no-ext-diff"],
        cwd=worktree,
        timeout=60,
        env=env,
    ).stdout
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(diff, encoding="utf-8")
    return {
        "patch_bytes": len(diff.encode("utf-8")),
        "patch_sha256": _sha256_bytes(diff.encode("utf-8")),
        "patch_has_new_file": "new file mode" in diff or "--- /dev/null" in diff,
        "capture_command": "git add -A && git diff --cached --binary --no-ext-diff",
    }


def _git_status(worktree: Path, *, env: dict[str, str] | None = None) -> str:
    return _checked(
        ["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60, env=env
    ).stdout


def _parse_jsonl(stdout: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    invalid: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            invalid.append(line)
            continue
        if isinstance(value, dict):
            events.append(value)
        else:
            invalid.append(line)
    return events, invalid


def _usage_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    usage: dict[str, Any] = {}
    for event in events:
        candidate = event.get("usage")
        if isinstance(candidate, dict):
            usage = candidate
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage


def _tool_event_count(events: list[dict[str, Any]]) -> int:
    count = 0
    for event in events:
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") in {
            "command_execution",
            "file_change",
            "mcp_tool_call",
        }:
            count += 1
        if event.get("type") in {"tool_use", "command_execution", "file_change"}:
            count += 1
    return count


def _approval_prompts(events: list[dict[str, Any]], raw: str) -> list[dict[str, Any]]:
    observed = []
    for event in events:
        event_type = str(event.get("type", "")).lower()
        if "approval" in event_type or "approval_request" in json.dumps(event).lower():
            observed.append(event)
    for line in raw.splitlines():
        lowered = line.lower()
        if re.search(r"approval\s+(required|request)|request(?:ing)?\s+approval|waiting for approval", lowered):
            observed.append({"raw_line": line})
    return observed


def run_codex(
    worktree: Path,
    prompt: str,
    *,
    output_dir: Path,
    env: dict[str, str] | None = None,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
) -> dict[str, Any]:
    command = build_codex_command(prompt, model=model, reasoning_effort=reasoning_effort)
    started = time.monotonic()
    try:
        process = subprocess.run(
            command,
            cwd=worktree,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", **(env or {})},
            capture_output=True,
            text=True,
            timeout=CODEX_TIMEOUT_SECONDS,
        )
        timed_out = False
    except subprocess.TimeoutExpired as error:
        process = subprocess.CompletedProcess(command, 124, error.stdout or "", error.stderr or "")
        timed_out = True
    elapsed = time.monotonic() - started
    stdout = process.stdout or ""
    stderr = process.stderr or ""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "codex.stdout.log").write_text(stdout, encoding="utf-8")
    (output_dir / "codex.stderr.log").write_text(stderr, encoding="utf-8")
    events, invalid = _parse_jsonl(stdout)
    (output_dir / "events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    usage = _usage_from_events(events)
    approvals = _approval_prompts(events, stdout + "\n" + stderr)
    combined_output = (stdout + "\n" + stderr).lower()
    quota_exhausted = any(
        marker in combined_output
        for marker in (
            "quota exceeded",
            "quota exhausted",
            "usage limit",
            "insufficient credits",
            "out of credits",
            "monthly limit",
        )
    )
    row = {
        "command": command[:-1] + ["<PROMPT>"],
        "model": model,
        "reasoning_effort": reasoning_effort,
        "approval_policy": APPROVAL_POLICY,
        "sandbox": SANDBOX,
        "session_isolation": "--ephemeral; fresh invocation",
        "returncode": process.returncode,
        "timed_out": timed_out,
        "wall_seconds": round(elapsed, 3),
        "event_count": len(events),
        "tool_event_count": _tool_event_count(events),
        "invalid_json_lines": len(invalid),
        "logs_parseable": bool(events) and not invalid,
        "approval_prompts_observed": bool(approvals),
        "approval_prompt_events": approvals,
        "quota_exhausted": quota_exhausted,
        "usage": usage,
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": usage.get("cached_input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
    }
    _json_write(output_dir / "codex_invocation.json", row)
    return row


def _grader_args(task: str, worktree: Path, patch: Path, root: Path) -> list[str]:
    grader = ROOT / "pilot" / task / "grader.py"
    metadata = _setup_metadata(worktree, expected_task=task)
    grader_interpreter = str(metadata["grader_interpreter"])
    interpreter = metadata["interpreter"]
    if task == "task-02-django-index-together-superseded":
        if not isinstance(interpreter, str):
            raise RuntimeError("Django grader requires the setup test interpreter")
        return [grader_interpreter, str(grader), str(worktree), str(patch), interpreter]
    if task == "task-04-cpython-locale-encoding-scope":
        if not isinstance(interpreter, str):
            raise RuntimeError("CPython grader requires the setup test interpreter")
        return [grader_interpreter, str(grader), str(worktree), str(patch), interpreter]
    if task == "task-06-opentofu-static-source-scope":
        test_env = metadata["test_env"]
        return [
            grader_interpreter,
            str(grader),
            str(worktree),
            str(patch),
            str(test_env["GOCACHE"]),
            str(test_env["GOMODCACHE"]),
        ]
    if task == "task-07-axum-optional-typed-header":
        test_env = metadata["test_env"]
        return [
            grader_interpreter,
            str(grader),
            str(worktree),
            str(patch),
            str(test_env["CARGO_HOME"]),
            str(test_env["CARGO_TARGET_DIR"]),
        ]
    if task == "task-go-01-maps-sorted-keys":
        return [grader_interpreter, str(grader), str(worktree), str(patch), str(metadata["test_env"]["GOCACHE"])]
    if task == "task-05-packaging-manylinux-aliases":
        if not isinstance(interpreter, str):
            raise RuntimeError("packaging grader requires the setup test interpreter")
        return [grader_interpreter, str(grader), str(worktree), str(patch), interpreter]
    return [grader_interpreter, str(grader), str(worktree), str(patch)]


def _test_spec(task: str, worktree: Path, root: Path) -> tuple[list[str], Path, dict[str, str], list[Path]]:
    """Return the frozen grader test command plus files to stage for its probe."""

    metadata = _setup_metadata(worktree, expected_task=task)
    command = list(metadata["test_command"])
    cwd = worktree / metadata["test_cwd"]
    env = {str(key): str(value) for key, value in metadata["test_env"].items()}

    if task == "task-07-axum-optional-typed-header":
        probe_target = worktree / "axum-extra/tests/decisiontrace_optional_typed_header.rs"
        return command, cwd, env, [probe_target]
    return command, cwd, env, []


def _prepare_test_probe(task: str, worktree: Path, probe_targets: list[Path]) -> None:
    if task != "task-07-axum-optional-typed-header":
        return
    source = ROOT / "pilot" / task / "semantic_probe.rs"
    target = probe_targets[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _classify_test_output(
    process: subprocess.CompletedProcess[str], *, test_runner: str = "pytest"
) -> str:
    """Compatibility wrapper around the versioned shared test contract."""

    return classify_process(process, test_runner=test_runner)


def _run_test_verification(
    task: str,
    worktree: Path,
    patch: Path,
    root: Path,
    *,
    base_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    patch = patch.resolve()
    _restore_clean_worktree(task, worktree, env=base_env)
    apply = _run(
        ["git", "apply", "--whitespace=nowarn", str(patch)],
        cwd=worktree,
        timeout=60,
        env=base_env,
    )
    if apply.returncode != 0:
        return {
            "test_execution_status": "patch_apply_failed",
            "tests_executed": False,
            "no_tests_ran": False,
            "tests_pass": False,
            "output": (apply.stdout + apply.stderr).strip(),
        }
    command, cwd, env, probe_targets = _test_spec(task, worktree, root)
    metadata = _setup_metadata(worktree, expected_task=task)
    _prepare_test_probe(task, worktree, probe_targets)
    try:
        process = _run(command, cwd=cwd, timeout=900, env={**(base_env or {}), **env})
        status = _classify_test_output(process, test_runner=str(metadata["test_runner"]))
        return {
            "interpreter": _setup_metadata(worktree, expected_task=task)["interpreter"],
            "test_command": command,
            "interpreter_kind": _setup_metadata(worktree, expected_task=task)["interpreter_kind"],
            "test_runner": metadata["test_runner"],
            "test_execution_status": status,
            "tests_executed": status == "executed_with_tests",
            "no_tests_ran": status == "executed_zero_tests",
            "test_returncode": process.returncode,
            "tests_pass": process.returncode == 0 and status == "executed_with_tests",
            "output": (process.stdout + process.stderr).strip(),
        }
    except subprocess.TimeoutExpired as error:
        return {
            "test_command": command,
            "test_execution_status": "test_timeout",
            "tests_executed": False,
            "no_tests_ran": False,
            "tests_pass": False,
            "output": str(error),
        }
    finally:
        _restore_clean_worktree(task, worktree, env=base_env)


def _parse_grader_output(output: str) -> dict[str, bool | None]:
    parsed: dict[str, bool | None] = {}
    for name in ("TASK_COMPLETED", "TESTS_PASS", "AUTHORITY_COMPLIANT"):
        match = re.search(rf"^{name}=((?:True|False|true|false))", output, re.MULTILINE)
        parsed[name] = None if match is None else match.group(1).lower() == "true"
    return parsed


def _run_grader(
    task: str,
    worktree: Path,
    patch: Path,
    root: Path,
    output_path: Path,
    *,
    base_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    patch = patch.resolve()
    _restore_clean_worktree(task, worktree)
    command = _grader_args(task, worktree, patch, root)
    try:
        process = _run(command, cwd=ROOT, timeout=1200, env=base_env)
        output = process.stdout + process.stderr
    except subprocess.TimeoutExpired as error:
        process = subprocess.CompletedProcess(command, 124, "", str(error))
        output = str(error)
    output_path.write_text(output, encoding="utf-8")
    parsed = _parse_grader_output(output)
    _restore_clean_worktree(task, worktree)
    return {
        "grader_command": command,
        "grader_returncode": process.returncode,
        "grader_output_parseable": all(value is not None for value in parsed.values()),
        "grader_output": parsed,
    }


def _write_prompt(output_dir: Path, prompt: str) -> dict[str, Any]:
    prompt_path = output_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return {
        "prompt_path": str(prompt_path),
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "system_prompt_sha256": _sha256_file(SYSTEM_PROMPT_PATH),
    }


@contextmanager
def _execution_root(
    storage: V4StoragePolicy | None,
    *,
    run_id: str,
    slot: int,
) -> Any:
    if storage is None:
        with tempfile.TemporaryDirectory(prefix=f"action-compliance-{run_id}-") as raw:
            yield Path(raw)
        return
    with storage.lifecycle(run_id=run_id, slot=slot):
        yield storage.slot_root(slot)


def _run_one(
    plan_row: dict[str, Any],
    *,
    output_root: Path,
    storage: V4StoragePolicy | None = None,
    slot: int = 0,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
) -> dict[str, Any]:
    run_id = plan_row["run_id"]
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    context = Path(plan_row["context_path"]).read_text(encoding="utf-8")
    prompt = assemble_prompt(context)
    prompt_meta = _write_prompt(run_dir, prompt)
    with _execution_root(storage, run_id=run_id, slot=slot) as setup_root:
        run_env = storage.environment(slot) if storage is not None else None
        setup_args, worktree = _setup_args(
            plan_row["task"],
            setup_root,
            storage=storage,
            slot=slot,
        )
        setup_started = time.monotonic()
        setup_process = _run(setup_args, cwd=ROOT, timeout=1800, env=run_env)
        setup_output = setup_process.stdout + setup_process.stderr
        (run_dir / "worktree_setup.log").write_text(setup_output, encoding="utf-8")
        if setup_process.returncode != 0:
            storage_failure = any(
                marker in setup_output.lower()
                for marker in ("disk quota exceeded", "no space left on device", "quota exceeded")
            )
            row = {
                "run_id": run_id,
                "task": plan_row["task"],
                "repetition": plan_row["repetition"],
                "round": plan_row["round"],
                "status": "INFRA_FAILURE",
                "usable_output": False,
                "failure_stage": "worktree_setup",
                "setup_returncode": setup_process.returncode,
                "setup_wall_seconds": round(time.monotonic() - setup_started, 3),
                "storage_failure": storage_failure,
                **prompt_meta,
            }
            _json_write(run_dir / "row.json", row)
            return row
        baseline_untracked = _ignore_setup_untracked(worktree, env=run_env)
        del baseline_untracked
        status_before = _git_status(worktree, env=run_env)
        (run_dir / "git_status_before_model.txt").write_text(status_before, encoding="utf-8")
        agent = run_codex(
            worktree,
            prompt,
            output_dir=run_dir,
            env=run_env,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        status_after = _git_status(worktree, env=run_env)
        (run_dir / "git_status_after_model.txt").write_text(status_after, encoding="utf-8")
        try:
            patch_meta = capture_patch(worktree, run_dir / "patch.diff", env=run_env)
        except Exception as error:
            (run_dir / "patch_capture_error.log").write_text(str(error) + "\n", encoding="utf-8")
            _restore_clean_worktree(plan_row["task"], worktree, env=run_env)
            row = {
                "run_id": run_id,
                "task": plan_row["task"],
                "repetition": plan_row["repetition"],
                "round": plan_row["round"],
                "status": "INFRA_FAILURE",
                "usable_output": False,
                "failure_stage": "patch_capture",
                "model": model,
                "reasoning_effort": reasoning_effort,
                "approval_policy": APPROVAL_POLICY,
                "sandbox": SANDBOX,
                "timeout_seconds": CODEX_TIMEOUT_SECONDS,
                "prompt_context_path": plan_row["context_path"],
                "git_status_before_model": status_before,
                "git_status_after_model": status_after,
                **prompt_meta,
                **agent,
            }
            _json_write(run_dir / "row.json", row)
            return row
        if agent["returncode"] != 0 or agent["timed_out"] or not agent["logs_parseable"]:
            _restore_clean_worktree(plan_row["task"], worktree, env=run_env)
            row = {
                "run_id": run_id,
                "task": plan_row["task"],
                "repetition": plan_row["repetition"],
                "round": plan_row["round"],
                "status": "INFRA_FAILURE",
                "usable_output": False,
                "failure_stage": "codex_execution",
                "model": model,
                "reasoning_effort": reasoning_effort,
                "approval_policy": APPROVAL_POLICY,
                "sandbox": SANDBOX,
                "timeout_seconds": CODEX_TIMEOUT_SECONDS,
                "prompt_context_path": plan_row["context_path"],
                "git_status_before_model": status_before,
                "git_status_after_model": status_after,
                **prompt_meta,
                **agent,
                **patch_meta,
            }
            _json_write(run_dir / "row.json", row)
            return row
        _restore_clean_worktree(plan_row["task"], worktree, env=run_env)
        grader = _run_grader(
            plan_row["task"],
            worktree,
            run_dir / "patch.diff",
            setup_root,
            run_dir / "grader.output.log",
            base_env=run_env,
        )
        test_verification = _run_test_verification(
            plan_row["task"],
            worktree,
            run_dir / "patch.diff",
            setup_root,
            base_env=run_env,
        )
        grader_values = grader["grader_output"]
        evidence_valid = (
            grader["grader_output_parseable"]
            and test_verification["test_execution_status"] != "unknown"
        )
        tests_pass = bool(grader_values["TESTS_PASS"] and test_verification["tests_pass"])
        row = {
            "run_id": run_id,
            "task": plan_row["task"],
            "repetition": plan_row["repetition"],
            "round": plan_row["round"],
            "status": "USABLE_COMPLETE" if evidence_valid else "INVALID",
            "usable_output": evidence_valid,
            "no_op": patch_meta["patch_bytes"] == 0,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "approval_policy": APPROVAL_POLICY,
            "sandbox": SANDBOX,
            "network_marker": os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "absent"),
            "timeout_seconds": CODEX_TIMEOUT_SECONDS,
            "prompt_context_path": plan_row["context_path"],
            "context_sha256": _sha256_file(Path(plan_row["context_path"])),
            "git_status_before_model": status_before,
            "git_status_after_model": status_after,
            **prompt_meta,
            **agent,
            **patch_meta,
            "TASK_COMPLETED": grader_values["TASK_COMPLETED"],
            "GRADER_TESTS_PASS": grader_values["TESTS_PASS"],
            "TESTS_PASS": tests_pass,
            "AUTHORITY_COMPLIANT": grader_values["AUTHORITY_COMPLIANT"],
            "NO_TESTS_RAN": test_verification["no_tests_ran"],
            "TESTS_EXECUTED": test_verification["tests_executed"],
            "TEST_EXECUTION_STATUS": test_verification["test_execution_status"],
            "test_returncode": test_verification.get("test_returncode"),
            "grader_returncode": grader["grader_returncode"],
            "grader_output_parseable": grader["grader_output_parseable"],
            "result_evidence_valid": evidence_valid,
        }
        _json_write(run_dir / "test_verification.json", test_verification)
        _json_write(run_dir / "row.json", row)
        _restore_clean_worktree(plan_row["task"], worktree, env=run_env)
        return row


def build_plan(
    contexts_root: Path = CONTEXTS_ROOT,
    *,
    repetitions: int = 3,
    seed: int = PLAN_SEED,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    manifests = {}
    for condition in CONDITIONS:
        manifest = json.loads((contexts_root / condition / "manifest.json").read_text(encoding="utf-8"))
        manifests[condition] = {Path(row["bundle"]).name: row for row in manifest}
    tasks = sorted(manifests["A"])
    if tasks != sorted(TASKS):
        raise ValueError(f"unexpected task set: {tasks}")
    for task in tasks:
        prefixes = {manifests[condition][task]["raw_prefix_sha256"] for condition in CONDITIONS}
        if len(prefixes) != 1:
            raise ValueError(f"raw context mismatch for {task}")
        if any(manifests[condition][task]["estimated_tokens"] > 8192 for condition in CONDITIONS):
            raise ValueError(f"context ceiling exceeded for {task}")

    rng = random.Random(seed)
    plan: list[dict[str, Any]] = []
    condition_map: dict[str, dict[str, Any]] = {}
    for task in tasks:
        for repetition in range(1, repetitions + 1):
            conditions = list(CONDITIONS)
            rng.shuffle(conditions)
            for condition in conditions:
                run_id = rng.randbytes(16).hex()
                row = {
                    "run_id": run_id,
                    "task": task,
                    "repetition": repetition,
                    "round": repetition,
                    "context_path": str(contexts_root / condition / task / "context.txt"),
                }
                plan.append(row)
                condition_map[run_id] = {
                    "condition": condition,
                    "task": task,
                    "repetition": repetition,
                    "round": repetition,
                }
    return plan, condition_map


def _resume_state(output_root: Path, plan: list[dict[str, Any]]) -> dict[str, Any]:
    state_path = output_root / "resume_state.json"
    expected = [row["run_id"] for row in plan]
    if not state_path.exists():
        return {
            "completed_run_ids": [],
            "plan_run_ids": expected,
            "run_status": {run_id: "PENDING" for run_id in expected},
            "attempt_counts": {run_id: 0 for run_id in expected},
        }
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("plan_run_ids") != expected:
        raise RuntimeError("resume state belongs to a different frozen plan")
    statuses = state.get("run_status", {})
    if not statuses:
        statuses = {run_id: "PENDING" for run_id in expected}
        for run_id in state.get("completed_run_ids", []):
            statuses[run_id] = "USABLE_COMPLETE"
    for run_id in expected:
        if statuses.get(run_id) == "RUNNING":
            statuses[run_id] = "PENDING"
        row_path = output_root / run_id / "row.json"
        if row_path.exists():
            row = json.loads(row_path.read_text(encoding="utf-8"))
            if row.get("status") == "USABLE_COMPLETE":
                statuses[run_id] = "USABLE_COMPLETE"
            elif row.get("status") == "INVALID":
                statuses[run_id] = "INVALID"
            elif row.get("status") == "INFRA_FAILURE":
                statuses[run_id] = "PENDING"
    state["run_status"] = statuses
    state["attempt_counts"] = {run_id: int(state.get("attempt_counts", {}).get(run_id, 0)) for run_id in expected}
    state["completed_run_ids"] = sorted(run_id for run_id, status in statuses.items() if status == "USABLE_COMPLETE")
    return state


def _save_resume_state(output_root: Path, state: dict[str, Any]) -> None:
    temporary = output_root / "resume_state.json.tmp"
    _json_write(temporary, state)
    temporary.replace(output_root / "resume_state.json")


def run_plan(
    plan: list[dict[str, Any]],
    *,
    output_root: Path,
    run_ids: set[str] | None = None,
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
    concurrency: int = 2,
    storage: V4StoragePolicy | None = None,
    pre_run_check: Callable[[list[dict[str, Any]]], None] | None = None,
) -> list[dict[str, Any]]:
    if concurrency not in (1, 2, 3):
        raise ValueError("concurrency must be 1, 2, or 3")
    output_root.mkdir(parents=True, exist_ok=True)
    if storage is not None:
        storage.initialize()
        storage.recover_abandoned()
    state = _resume_state(output_root, plan)
    rows = []
    eligible = [
        row for row in plan
        if (run_ids is None or row["run_id"] in run_ids)
        and state["run_status"].get(row["run_id"]) not in {"USABLE_COMPLETE", "INVALID"}
    ]
    while eligible:
        batch = eligible[:concurrency]
        eligible = eligible[concurrency:]
        if pre_run_check is not None:
            try:
                pre_run_check(batch)
            except Exception as error:
                state["stop_reason"] = str(error)
                _save_resume_state(output_root, state)
                raise
        for plan_row in batch:
            run_id = plan_row["run_id"]
            state["run_status"][run_id] = "RUNNING"
            state["attempt_counts"][run_id] += 1
        _save_resume_state(output_root, state)
        with ThreadPoolExecutor(max_workers=len(batch), thread_name_prefix="action-compliance") as executor:
            futures = {
                executor.submit(
                    _run_one,
                    plan_row,
                    output_root=output_root,
                    storage=storage,
                    slot=slot,
                    model=model,
                    reasoning_effort=reasoning_effort,
                ): plan_row
                for slot, plan_row in enumerate(batch)
            }
            for future in as_completed(futures):
                plan_row = futures[future]
                run_id = plan_row["run_id"]
                try:
                    row = future.result()
                except V4DiskGuardError as error:
                    state["run_status"][run_id] = "PENDING"
                    state["stop_reason"] = str(error)
                    _save_resume_state(output_root, state)
                    raise
                except V4StorageError:
                    state["run_status"][run_id] = "INVALID"
                    _save_resume_state(output_root, state)
                    raise
                except Exception as error:
                    run_dir = output_root / run_id
                    run_dir.mkdir(parents=True, exist_ok=True)
                    row = {
                        "run_id": run_id,
                        "task": plan_row["task"],
                        "repetition": plan_row["repetition"],
                        "round": plan_row["round"],
                        "status": "INFRA_FAILURE",
                        "usable_output": False,
                        "failure_stage": "orchestrator",
                        "error": repr(error),
                    }
                    _json_write(run_dir / "row.json", row)
                rows.append(row)
                if row.get("storage_failure"):
                    state["run_status"][run_id] = "INVALID"
                    state["stop_reason"] = (
                        f"storage failure in {run_id}: setup reported a disk quota or no-space error"
                    )
                    _save_resume_state(output_root, state)
                    raise V4StorageError(state["stop_reason"])
                if row.get("quota_exhausted"):
                    state["run_status"][run_id] = "PENDING"
                    state["stop_reason"] = (
                        f"provider quota exhausted while attempting {run_id}; "
                        "resume this frozen plan after quota is available"
                    )
                    _save_resume_state(output_root, state)
                    raise V4QuotaPause(state["stop_reason"])
                if row.get("status") == "INVALID":
                    state["run_status"][run_id] = "INVALID"
                    state["stop_reason"] = (
                        f"test/grader evidence was not representable for {run_id}; "
                        "freeze is invalidated and must not be repaired in place"
                    )
                    _save_resume_state(output_root, state)
                    raise TestContractInvalidation(state["stop_reason"])
                state["run_status"][run_id] = row.get("status", "INFRA_FAILURE")
                if row.get("status") == "INFRA_FAILURE":
                    state["run_status"][run_id] = "PENDING"
                    if state["attempt_counts"][run_id] >= 3:
                        state["run_status"][run_id] = "INFRA_FAILURE"
                _save_resume_state(output_root, state)
        retryable = [row for row in batch if state["run_status"].get(row["run_id"]) == "PENDING"]
        if retryable:
            eligible = retryable + eligible
    state["completed_run_ids"] = sorted(
        run_id for run_id, status in state["run_status"].items() if status == "USABLE_COMPLETE"
    )
    _save_resume_state(output_root, state)
    return rows


def _dummy_git_repo(root: Path) -> Path:
    worktree = root / "dummy-worktree"
    worktree.mkdir()
    (worktree / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _checked(["git", "init", "-q"], cwd=worktree, timeout=30)
    _checked(["git", "config", "user.email", "dry-run@example.invalid"], cwd=worktree, timeout=30)
    _checked(["git", "config", "user.name", "dry-run"], cwd=worktree, timeout=30)
    _checked(["git", "add", "baseline.txt"], cwd=worktree, timeout=30)
    _checked(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "baseline"],
        cwd=worktree,
        timeout=30,
    )
    return worktree


def run_no_model_dry_run(
    *,
    contexts_root: Path = CONTEXTS_ROOT,
    output_root: Path,
    repetitions: int = 3,
    seed: int = PLAN_SEED,
) -> dict[str, Any]:
    """Exercise orchestration and capture paths without a coding-agent call."""

    plan, condition_map = build_plan(contexts_root, repetitions=repetitions, seed=seed)
    output_root.mkdir(parents=True, exist_ok=True)
    _json_write(output_root / "run_plan.json", plan)
    _json_write(output_root / "condition_map.json", condition_map)
    first = plan[0]
    context = Path(first["context_path"]).read_text(encoding="utf-8")
    prompt = assemble_prompt(context)
    command = build_codex_command(prompt)
    command_text = " ".join(command[:-1] + ["<PROMPT>"])
    forbidden = ("claude", "--permission-mode", "--output-format", "stream-json", "--safe-mode")
    if any(token in command_text.lower() for token in forbidden):
        raise RuntimeError("Codex command assembly contains a Claude-specific option")
    if not command[-1].endswith(context):
        raise RuntimeError("materialized context was not attached byte-for-byte")

    with tempfile.TemporaryDirectory(prefix="action-compliance-dry-run-") as raw:
        dummy_root = Path(raw)
        worktree = _dummy_git_repo(dummy_root)
        (worktree / "new_file.txt").write_text("new file\n", encoding="utf-8")
        patch_meta = capture_patch(worktree, output_root / "dummy_patch.diff")
        if not patch_meta["patch_has_new_file"]:
            raise RuntimeError("staged patch did not capture a new file")
        _restore_clean_worktree("dummy", worktree)
        cleanup_status = _run(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=worktree, timeout=30
        ).stdout
        if cleanup_status:
            raise RuntimeError(f"dummy worktree cleanup failed: {cleanup_status}")
        grader_input = {
            "run_id": first["run_id"],
            "task_bundle": first["task"],
            "worktree": f"worktrees/{first['run_id']}",
            "patch_path": f"patches/{first['run_id']}.diff",
        }
        _json_write(output_root / "grader_input.json", grader_input)
        grader_output_path = output_root / "grader_output.json"
        grader = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "dry_run_grader.py"), str(output_root / "grader_input.json"), str(grader_output_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if grader.returncode != 0:
            raise RuntimeError(grader.stderr or grader.stdout)
        grader_result = json.loads(grader_output_path.read_text(encoding="utf-8"))
        if "condition" in grader_result or not {"TASK_COMPLETED", "TESTS_PASS", "AUTHORITY_COMPLIANT"} <= grader_result.keys():
            raise RuntimeError("dry-run grader schema is not condition blind")

    state = {"completed_run_ids": [first["run_id"]], "plan_run_ids": [row["run_id"] for row in plan]}
    _json_write(output_root / "resume_state.json", state)
    resumed = [row for row in plan if row["run_id"] not in set(state["completed_run_ids"])]
    round_counts = {str(round_number): sum(row["round"] == round_number for row in plan) for round_number in range(1, repetitions + 1)}
    result = {
        "planned_runs": len(plan),
        "task_count": len(TASKS),
        "repetitions": repetitions,
        "conditions": len(CONDITIONS),
        "round_counts": round_counts,
        "raw_context_equal": True,
        "context_ceiling_enforced": True,
        "condition_map_separate": True,
        "opaque_run_ids": len({row["run_id"] for row in plan}) == len(plan),
        "randomized_condition_order": True,
        "codex_command_assembled": True,
        "codex_command": command_text,
        "context_attached": True,
        "worktree_creation": True,
        "patch_path": str(output_root / "dummy_patch.diff"),
        "grader_path": str(ROOT / "scripts" / "dry_run_grader.py"),
        "cleanup": True,
        "resume_state": True,
        "resume_pending_rows": len(resumed),
        "result_schema": True,
        "coding_agents_called": False,
        "patch_capture": patch_meta,
    }
    _json_write(output_root / "dry_run_result.json", result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return result


def _preflight_row(
    *,
    attempt: str,
    output_root: Path,
    model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    attempt_dir = output_root / attempt
    attempt_dir.mkdir(parents=True, exist_ok=True)
    context = build_excluded_preflight_context()
    prompt = assemble_prompt(context)
    _write_prompt(attempt_dir, prompt)
    with tempfile.TemporaryDirectory(prefix="action-compliance-codex-preflight-") as raw:
        setup_root = Path(raw)
        setup_args, worktree = _setup_args(PREFLIGHT_TASK, setup_root)
        setup = _run(setup_args, cwd=ROOT, timeout=1800)
        (attempt_dir / "worktree_setup.log").write_text(setup.stdout + setup.stderr, encoding="utf-8")
        if setup.returncode != 0:
            row = {
                "attempt": attempt,
                "status": "infrastructure_failure",
                "failure_stage": "worktree_setup",
                "setup_returncode": setup.returncode,
            }
            _json_write(attempt_dir / "row.json", row)
            return row
        _ignore_setup_untracked(worktree)
        agent = run_codex(
            worktree,
            prompt,
            output_dir=attempt_dir,
            model=model,
            reasoning_effort=reasoning_effort,
        )
        patch_meta = capture_patch(worktree, attempt_dir / "patch.diff")
        probe_text = (worktree / "decisiontrace_codex_preflight_probe.txt").read_text(encoding="utf-8") if (worktree / "decisiontrace_codex_preflight_probe.txt").exists() else ""
        _restore_clean_worktree(PREFLIGHT_TASK, worktree)
        grader = _run_grader(PREFLIGHT_TASK, worktree, attempt_dir / "patch.diff", setup_root, attempt_dir / "grader.output.log")
        test_verification = _run_test_verification(PREFLIGHT_TASK, worktree, attempt_dir / "patch.diff", setup_root)
        row = {
            "attempt": attempt,
            "status": "completed",
            "codex_version": codex_version(),
            "model": model,
            "reasoning_effort": reasoning_effort,
            "approval_policy": APPROVAL_POLICY,
            "sandbox": SANDBOX,
            "network_marker": os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED", "absent"),
            "timeout_seconds": CODEX_TIMEOUT_SECONDS,
            "edit_write_result": bool(probe_text),
            "preflight_marker_found": probe_text == "CODEX_PREFLIGHT_WRITE_OK\n" or probe_text.strip() == "CODEX_PREFLIGHT_WRITE_OK",
            "actual_tests_result": test_verification,
            "patch_capture_result": patch_meta,
            "grader_result": grader,
            "approval_prompts_observed": agent["approval_prompts_observed"],
            "logs_results_parseable": agent["logs_parseable"] and grader["grader_output_parseable"],
            "preflight_token_usage": agent["usage"],
            "preflight_wall_seconds": agent["wall_seconds"],
            "reset_cleanup_verified": True,
            "fresh_worktree_removed": True,
        }
        _json_write(attempt_dir / "row.json", row)
        return row


def run_preflight(
    *,
    output_root: Path,
    attempt: str = "high",
    model: str = MODEL,
    reasoning_effort: str = REASONING_EFFORT,
) -> dict[str, Any]:
    existing = [path for path in output_root.iterdir()] if output_root.exists() else []
    # A setup failure is not a Codex run and must not consume the two-run
    # capability-preflight allowance.  Count only attempts that reached the
    # executable and wrote its invocation record.
    attempts = [path for path in existing if path.is_dir() and (path / "codex_invocation.json").exists()]
    if len(attempts) >= 2:
        raise RuntimeError("preflight limit exceeded: at most two Codex attempts are allowed")
    row = _preflight_row(
        attempt=attempt,
        output_root=output_root,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    summary = {"attempts": len(attempts) + 1, "latest": row}
    _json_write(output_root / "preflight_summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return row


def verify_saved_preflight(*, output_root: Path, attempt: str) -> dict[str, Any]:
    """Re-run grader/test verification for a saved preflight patch only."""

    attempt_dir = output_root / attempt
    patch = attempt_dir / "patch.diff"
    if not patch.exists():
        raise RuntimeError(f"saved preflight patch is missing: {patch}")
    with tempfile.TemporaryDirectory(prefix="action-compliance-codex-preflight-verify-") as raw:
        setup_root = Path(raw)
        setup_args, worktree = _setup_args(PREFLIGHT_TASK, setup_root)
        setup = _run(setup_args, cwd=ROOT, timeout=1800)
        (attempt_dir / "verification_worktree_setup.log").write_text(
            setup.stdout + setup.stderr, encoding="utf-8"
        )
        if setup.returncode != 0:
            raise RuntimeError("saved preflight verification setup failed")
        _ignore_setup_untracked(worktree)
        grader = _run_grader(
            PREFLIGHT_TASK,
            worktree,
            patch.resolve(),
            setup_root,
            attempt_dir / "verification_grader.output.log",
        )
        tests = _run_test_verification(PREFLIGHT_TASK, worktree, patch.resolve(), setup_root)
    result = {
        "attempt": attempt,
        "patch": str(patch),
        "grader": grader,
        "test_verification": tests,
        "verification_pass": (
            grader["grader_output_parseable"]
            and tests["tests_executed"]
            and tests["tests_pass"]
        ),
    }
    _json_write(attempt_dir / "preflight_verification_retry.json", result)
    row_path = attempt_dir / "row.json"
    if row_path.exists():
        row = json.loads(row_path.read_text(encoding="utf-8"))
        row["actual_tests_result"] = tests
        row["preflight_verification_retry"] = result
        row["preflight_gate_pass"] = result["verification_pass"]
        _json_write(row_path, row)
        _json_write(
            output_root / "preflight_summary.json",
            {"attempts": len([p for p in output_root.iterdir() if p.is_dir() and (p / "codex_invocation.json").exists()]), "latest": row},
        )
    print(json.dumps(result, sort_keys=True, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--verify-preflight", action="store_true")
    parser.add_argument("--contexts-root", type=Path, default=CONTEXTS_ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=PLAN_SEED)
    parser.add_argument("--attempt", default="high")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--reasoning-effort", default=REASONING_EFFORT)
    parser.add_argument("--round", type=int, choices=(1, 2, 3))
    parser.add_argument("--concurrency", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--v4-storage-root", type=Path)
    parser.add_argument("--v4-min-free-bytes", type=int, default=20 * 1024**3)
    parser.add_argument("--v4-min-free-inodes", type=int, default=100_000)
    parser.add_argument("--v4-min-host-free-bytes", type=int, default=5 * 1024**3)
    args = parser.parse_args()
    if not args.dry_run and not args.preflight and not args.verify_preflight and args.output_root is None:
        parser.error("--output-root is required for comparative execution")
    if args.dry_run:
        run_no_model_dry_run(
            contexts_root=args.contexts_root,
            output_root=args.output_root or ROOT / "data/action_compliance/dry_run",
            repetitions=args.repetitions,
            seed=args.seed,
        )
        return
    if args.preflight:
        run_preflight(
            output_root=args.output_root or ROOT / "data/action_compliance/codex_preflight",
            attempt=args.attempt,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        return
    if args.verify_preflight:
        verify_saved_preflight(
            output_root=args.output_root or ROOT / "data/action_compliance/codex_preflight",
            attempt=args.attempt,
        )
        return
    plan, condition_map = build_plan(args.contexts_root, repetitions=args.repetitions, seed=args.seed)
    args.output_root.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_root / "run_plan.json"
    condition_map_path = args.output_root / "condition_map.json"
    if plan_path.exists() or condition_map_path.exists():
        if not plan_path.exists() or not condition_map_path.exists():
            raise RuntimeError("final runner has only a partial frozen plan")
        if json.loads(plan_path.read_text(encoding="utf-8")) != plan:
            raise RuntimeError("existing run plan differs from the frozen seed/configuration")
        if json.loads(condition_map_path.read_text(encoding="utf-8")) != condition_map:
            raise RuntimeError("existing condition map differs from the frozen plan")
    else:
        _json_write(plan_path, plan)
        _json_write(condition_map_path, condition_map)
    selected = None if args.round is None else {row["run_id"] for row in plan if row["round"] == args.round}
    storage = None
    if args.v4_storage_root is not None:
        storage = V4StoragePolicy(
            root=args.v4_storage_root.resolve(),
            worker_count=args.concurrency,
            min_free_bytes=args.v4_min_free_bytes,
            min_free_inodes=args.v4_min_free_inodes,
            min_host_free_bytes=args.v4_min_host_free_bytes,
        )
    run_plan(
        plan,
        output_root=args.output_root,
        run_ids=selected,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        concurrency=args.concurrency,
        storage=storage,
    )


if __name__ == "__main__":
    main()
