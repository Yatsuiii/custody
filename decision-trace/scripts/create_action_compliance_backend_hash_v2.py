#!/usr/bin/env python3
"""Hash the complete V2 execution backend before comparative output."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V2.json",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "scripts/run_action_compliance_codex.py",
    "scripts/setup_action_compliance_full_worktree.py",
    "scripts/verify_action_compliance_v2_worktrees.py",
    "scripts/replay_action_compliance_sanity_v2.py",
    "scripts/dry_run_action_compliance_v2.py",
)
OUTPUT = ROOT / "ACTION_COMPLIANCE_CODEX_BACKEND_V2_SHA256.txt"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    component_lines = [f"{digest(ROOT / relative)}  {relative}" for relative in COMPONENTS]
    backend = hashlib.sha256("\n".join(component_lines).encode()).hexdigest()
    OUTPUT.write_text(
        "backend_v2_sha256  " + backend + "\n" + "\n".join(component_lines) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
