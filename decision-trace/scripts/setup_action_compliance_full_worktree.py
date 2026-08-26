#!/usr/bin/env python3
"""Create a complete pinned checkout for an action-compliance task.

Checkout mechanics are intentionally shared across all tasks: initialize one
repository, fetch the pinned commit shallowly with blob filtering, and checkout
the complete tree. Task-specific cache preparation is kept below the common
checkout boundary because it does not constrain which files the agent may edit.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY312 = "/home/Yatsuiii/.pyenv/versions/3.12.13/bin/python"
SETUP_METADATA_NAME = ".decisiontrace_setup_metadata.json"

REPOSITORIES = {
    "task-01-k8s-postfilter-victims": ("https://github.com/kubernetes/kubernetes.git", "9874e76ac44442ebfa33c824e2c57bcb9f0d2e5e"),
    "task-02-django-index-together-superseded": ("https://github.com/django/django.git", "879e5d587b84e6fc961829611999431778eb9f6a"),
    "task-go-01-maps-sorted-keys": ("https://github.com/golang/go.git", "56ebf80e57db9f61981fc0636fc6419dc6f68eda"),
    "task-03-pip-inline-script-metadata": ("https://github.com/pypa/pip.git", "b35182d8f7245f046eed2975275c57b54ce3ba56"),
    "task-04-cpython-locale-encoding-scope": ("https://github.com/python/cpython.git", "261a452a1300eeeae1428ffd6e6623329c085e2c"),
    "task-05-packaging-manylinux-aliases": ("https://github.com/pypa/packaging.git", "19fbc45b24ca0d577c9b256bb404b0dbaf4903da"),
    "task-06-opentofu-static-source-scope": ("https://github.com/opentofu/opentofu.git", "3fdc8090501234c55093078255969ecbc46f2fe2"),
    "task-07-axum-optional-typed-header": ("https://github.com/tokio-rs/axum.git", "fd11d8efde4895a2159a29dcd586a7db99917057"),
}


def run(args: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", **(env or {})},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def checked(args: list[str], *, cwd: Path, env: dict[str, str] | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    process = run(args, cwd=cwd, env=env, timeout=timeout)
    if process.returncode != 0:
        raise RuntimeError((process.stdout + process.stderr).strip())
    return process


def checkout(task: str, worktree: Path, source_cache: Path | None = None) -> str:
    repository, pinned_sha = REPOSITORIES[task]
    remote = str(source_cache) if source_cache is not None else repository
    if worktree.exists():
        raise RuntimeError(f"worktree already exists: {worktree}")
    worktree.mkdir(parents=True)
    checked(["git", "init", "-q"], cwd=worktree, timeout=60)
    checked(["git", "remote", "add", "origin", remote], cwd=worktree, timeout=60)
    # No sparse-checkout command is permitted in this V2 setup.
    fetch_args = ["git", "fetch", "--filter=blob:none", "--depth", "1", "origin", pinned_sha]
    if source_cache is not None:
        fetch_args = ["git", "fetch", "--no-tags", "--depth", "1", "origin", pinned_sha]
    checked(fetch_args, cwd=worktree, timeout=1800)
    checked(["git", "checkout", "-q", "FETCH_HEAD"], cwd=worktree, timeout=1800)
    actual = checked(["git", "rev-parse", "HEAD"], cwd=worktree, timeout=60).stdout.strip()
    if actual != pinned_sha:
        raise RuntimeError(f"pinned SHA mismatch: expected {pinned_sha}, got {actual}")
    sparse = run(["git", "config", "--get", "core.sparseCheckout"], cwd=worktree, timeout=60)
    if sparse.returncode == 0 and sparse.stdout.strip().lower() == "true":
        raise RuntimeError("V2 full-worktree invariant failed: sparse checkout is enabled")
    status = checked(["git", "status", "--porcelain=v1"], cwd=worktree, timeout=60).stdout
    if status.strip():
        raise RuntimeError(f"fresh full worktree is dirty:\n{status}")
    return pinned_sha


def prepare_dependencies(
    task: str,
    worktree: Path,
    *,
    go_cache: Path | None,
    go_module_cache: Path | None,
    cargo_home: Path | None,
    cargo_target: Path | None,
    python_wheelhouse: Path | None,
    python: str,
) -> None:
    if task == "task-02-django-index-together-superseded":
        checked([python, "-m", "venv", ".venv"], cwd=worktree, timeout=300)
        pip = str(worktree / ".venv" / "bin" / "pip")
        if python_wheelhouse is not None:
            checked(
                [pip, "install", "--no-index", "--find-links", str(python_wheelhouse), "setuptools"],
                cwd=worktree,
                timeout=300,
            )
            checked(
                [
                    pip,
                    "install",
                    "--no-index",
                    "--find-links",
                    str(python_wheelhouse),
                    "--no-build-isolation",
                    "-q",
                    "-e",
                    ".",
                ],
                cwd=worktree,
                timeout=1800,
            )
        else:
            checked([pip, "install", "-q", "-e", "."], cwd=worktree, timeout=1800)
    elif task == "task-go-01-maps-sorted-keys":
        assert go_cache is not None
        goroot = checked(["go", "env", "GOROOT"], cwd=worktree, timeout=60).stdout.strip()
        maps_dir = worktree / "src" / "maps"
        mapping = {
            str(Path(goroot) / "src" / "maps" / source.name): str(source)
            for source in maps_dir.glob("*.go")
        }
        (worktree / "overlay.json").write_text(json.dumps({"Replace": mapping}, indent=2) + "\n", encoding="utf-8")
        checked(
            ["go", "test", f"-overlay={worktree / 'overlay.json'}", "maps"],
            cwd=worktree,
            env={
                "GOWORK": "off",
                "GOCACHE": str(go_cache),
                **({"GOMODCACHE": str(go_module_cache)} if go_module_cache is not None else {}),
            },
            timeout=900,
        )
    elif task == "task-06-opentofu-static-source-scope":
        assert go_cache is not None
        module_cache = go_module_cache or (go_cache / "modules")
        checked(
            ["go", "mod", "download"],
            cwd=worktree,
            env={"GOCACHE": str(go_cache / "build"), "GOMODCACHE": str(module_cache)},
            timeout=1800,
        )
        checked(
            ["go", "test", "./internal/configs", "-run", "^$", "-count=1"],
            cwd=worktree,
            env={"GOCACHE": str(go_cache / "build"), "GOMODCACHE": str(module_cache)},
            timeout=1800,
        )
    elif task == "task-07-axum-optional-typed-header":
        assert cargo_home is not None and cargo_target is not None
        checked(
            ["cargo", "test", "--manifest-path", str(worktree / "Cargo.toml"), "-p", "axum-extra", "--features", "typed-header", "typed_header", "--no-run"],
            cwd=worktree,
            env={"CARGO_HOME": str(cargo_home), "CARGO_TARGET_DIR": str(cargo_target)},
            timeout=1800,
        )
    elif task in {
        "task-01-k8s-postfilter-victims",
        "task-03-pip-inline-script-metadata",
        "task-04-cpython-locale-encoding-scope",
        "task-05-packaging-manylinux-aliases",
    }:
        if task in {"task-03-pip-inline-script-metadata", "task-05-packaging-manylinux-aliases"}:
            checked([sys.executable, "-c", "import pytest"], cwd=worktree, timeout=60)
        return
    else:
        raise ValueError(f"unknown task: {task}")


def build_interpreter_contract(
    task: str,
    worktree: Path,
    *,
    go_cache: Path | None,
    go_module_cache: Path | None,
    cargo_home: Path | None,
    cargo_target: Path | None,
    setup_python: str,
) -> dict[str, object]:
    """Publish the interpreter and complete test-command contract.

    Dependency setup is the only place that knows whether a task needs a
    worktree virtualenv or a pinned host interpreter.  Test verification and
    graders must read this result instead of independently guessing.
    """

    host_interpreter = str(Path(sys.executable).resolve())
    if task == "task-02-django-index-together-superseded":
        # Keep the venv launcher path. Resolving its symlink to the base Python
        # silently bypasses the venv's site-packages (including Django).
        interpreter_kind = "worktree_venv"
    elif task == "task-04-cpython-locale-encoding-scope":
        interpreter_kind = "pinned_host_python"
    elif task in {"task-03-pip-inline-script-metadata", "task-05-packaging-manylinux-aliases"}:
        interpreter_kind = "setup_host_python"
    else:
        interpreter_kind = "non_python_test_runner"

    if task == "task-01-k8s-postfilter-victims":
        interpreter = "go"
        test_command = [
            "go",
            "test",
            "./pkg/scheduler/framework/preemption/...",
            "./pkg/scheduler/framework/plugins/defaultpreemption/...",
        ]
        test_cwd = "."
        test_env = {
            "GOWORK": "off",
            **({"GOCACHE": str(go_cache)} if go_cache is not None else {}),
            **({"GOMODCACHE": str(go_module_cache)} if go_module_cache is not None else {}),
        }
        test_runner = "go-test"
    elif task == "task-02-django-index-together-superseded":
        interpreter = str(worktree / ".venv" / "bin" / "python")
        test_command = [interpreter, "runtests.py", "model_indexes", "-v1"]
        test_cwd = "tests"
        test_env = {}
        test_runner = "django-runtests"
    elif task == "task-go-01-maps-sorted-keys":
        if go_cache is None:
            raise RuntimeError("task-go-01 requires a Go cache for its test contract")
        interpreter = "go"
        test_command = ["go", "test", f"-overlay={worktree / 'overlay.json'}", "maps"]
        test_cwd = "."
        test_env = {
            "GOWORK": "off",
            "GOCACHE": str(go_cache),
            **({"GOMODCACHE": str(go_module_cache)} if go_module_cache is not None else {}),
        }
        test_runner = "go-test"
    elif task == "task-03-pip-inline-script-metadata":
        interpreter = host_interpreter
        test_command = [
            interpreter,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "--confcutdir=tests/unit",
            "tests/unit/test_script_metadata.py",
        ]
        test_cwd = "."
        test_env = {"PYTHONPATH": str(worktree / "src")}
        test_runner = "pytest"
    elif task == "task-04-cpython-locale-encoding-scope":
        interpreter = os.path.abspath(setup_python)
        test_command = [interpreter, "Lib/test/test__pyio_locale.py"]
        test_cwd = "."
        test_env = {}
        test_runner = "cpython-unittest"
    elif task == "task-05-packaging-manylinux-aliases":
        interpreter = host_interpreter
        test_command = [interpreter, "-m", "pytest", "-q", "tests/test_manylinux_pep600.py"]
        test_cwd = "."
        test_env = {"PYTHONPATH": str(worktree)}
        test_runner = "pytest"
    elif task == "task-06-opentofu-static-source-scope":
        if go_cache is None:
            raise RuntimeError("task-06 requires a Go cache for its test contract")
        interpreter = "go"
        test_command = ["go", "test", "./internal/configs", "-run", "^TestDecisionTrace", "-count=1"]
        test_cwd = "."
        test_env = {
            "GOCACHE": str(go_cache / "build"),
            "GOMODCACHE": str(go_module_cache or (go_cache / "modules")),
        }
        test_runner = "go-test"
    elif task == "task-07-axum-optional-typed-header":
        if cargo_home is None or cargo_target is None:
            raise RuntimeError("task-07 requires Cargo paths for its test contract")
        interpreter = "cargo"
        test_command = [
            "cargo",
            "test",
            "--offline",
            "-p",
            "axum-extra",
            "--features",
            "typed-header",
            "--test",
            "decisiontrace_optional_typed_header",
            "--",
            "--nocapture",
        ]
        test_cwd = "."
        test_env = {"CARGO_HOME": str(cargo_home), "CARGO_TARGET_DIR": str(cargo_target)}
        test_runner = "cargo-test"
    else:
        raise ValueError(f"unknown task: {task}")

    for label, executable in (("grader_interpreter", host_interpreter), ("interpreter", interpreter)):
        if os.sep in executable:
            valid = Path(executable).is_file() and os.access(executable, os.X_OK)
        else:
            valid = shutil.which(executable) is not None
        if not valid:
            raise RuntimeError(f"{label} is not executable or unavailable: {executable}")

    return {
        "contract_version": "test-command-v2",
        "task": task,
        "setup_interpreter": host_interpreter,
        "setup_python_argument": os.path.abspath(setup_python),
        "grader_interpreter": host_interpreter,
        "interpreter": interpreter,
        "test_command": test_command,
        "test_cwd": test_cwd,
        "test_env": test_env,
        "test_runner": test_runner,
        "interpreter_kind": interpreter_kind,
        "pinned_sha": REPOSITORIES[task][1],
        "full_worktree": True,
        "sparse_checkout": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=sorted(REPOSITORIES), required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--go-cache", type=Path)
    parser.add_argument("--go-module-cache", type=Path)
    parser.add_argument("--cargo-home", type=Path)
    parser.add_argument("--cargo-target", type=Path)
    parser.add_argument("--source-cache", type=Path)
    parser.add_argument("--python-wheelhouse", type=Path)
    parser.add_argument("--python", default=PY312)
    args = parser.parse_args()
    pinned_sha = checkout(args.task, args.worktree, source_cache=args.source_cache)
    for path in (args.go_cache, args.go_module_cache, args.cargo_home, args.cargo_target, args.python_wheelhouse):
        if path is not None:
            path.mkdir(parents=True, exist_ok=True)
    prepare_dependencies(
        args.task,
        args.worktree,
        go_cache=args.go_cache,
        go_module_cache=args.go_module_cache,
        cargo_home=args.cargo_home,
        cargo_target=args.cargo_target,
        python_wheelhouse=args.python_wheelhouse,
        python=args.python,
    )
    metadata = build_interpreter_contract(
        args.task,
        args.worktree,
        go_cache=args.go_cache,
        go_module_cache=args.go_module_cache,
        cargo_home=args.cargo_home,
        cargo_target=args.cargo_target,
        setup_python=args.python,
    )
    (args.worktree / SETUP_METADATA_NAME).write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    status = checked(["git", "status", "--porcelain=v1"], cwd=args.worktree, timeout=60).stdout
    print(json.dumps({**metadata, "status_porcelain": status}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FULL_WORKTREE_SETUP_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
