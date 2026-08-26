#!/usr/bin/env python3
"""Create the content hash for the V5 execution backend."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V5.json",
    "ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL_V5.md",
    "ACTION_COMPLIANCE_V5_STORAGE_CONTRACT.md",
    "ACTION_COMPLIANCE_TEST_INTERPRETER_CONTRACT_V4.md",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "scripts/action_compliance_test_contract.py",
    "scripts/action_compliance_v4_storage.py",
    "scripts/run_action_compliance_codex.py",
    "scripts/run_action_compliance_codex_v5.py",
    "scripts/setup_action_compliance_full_worktree.py",
    "scripts/dry_run_action_compliance_v5.py",
    "scripts/replay_action_compliance_sanity_v5.py",
    "scripts/stress_action_compliance_v5_storage.py",
    "scripts/verify_action_compliance_v5_storage.py",
    "pilot/task-01-k8s-postfilter-victims/grader.py",
    "pilot/task-02-django-index-together-superseded/grader.py",
    "pilot/task-03-pip-inline-script-metadata/grader.py",
    "pilot/task-04-cpython-locale-encoding-scope/grader.py",
    "pilot/task-05-packaging-manylinux-aliases/grader.py",
    "pilot/task-06-opentofu-static-source-scope/grader.py",
    "pilot/task-07-axum-optional-typed-header/grader.py",
    "pilot/task-go-01-maps-sorted-keys/grader.py",
)
OUTPUT = ROOT / "ACTION_COMPLIANCE_CODEX_BACKEND_V5_SHA256.txt"


def main() -> None:
    lines = [
        f"{hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}  {relative}"
        for relative in COMPONENTS
    ]
    backend = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    OUTPUT.write_text(
        "backend_v5_sha256  " + backend + "\n" + "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
