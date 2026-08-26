#!/usr/bin/env python3
"""Hash the complete V3 execution backend before comparative output."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = (
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V3.json",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "scripts/run_action_compliance_codex.py",
    "scripts/setup_action_compliance_full_worktree.py",
    "scripts/dry_run_action_compliance_v3.py",
    "scripts/replay_action_compliance_sanity_v3.py",
)
OUTPUT = ROOT / "ACTION_COMPLIANCE_CODEX_BACKEND_V3_SHA256.txt"


def main() -> None:
    lines = [
        f"{hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()}  {relative}"
        for relative in COMPONENTS
    ]
    backend = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    OUTPUT.write_text("backend_v3_sha256  " + backend + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
