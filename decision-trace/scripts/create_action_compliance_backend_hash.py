#!/usr/bin/env python3
"""Freeze the hash surface for the Codex backend and prompt serializer."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG.json",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "scripts/run_action_compliance_codex.py",
    "scripts/dry_run_action_compliance.py",
)


def main() -> None:
    lines = []
    for relative in FILES:
        path = ROOT / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}")
    payload = "\n".join(lines) + "\n"
    backend_digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    output = f"backend_sha256  {backend_digest}\n" + payload
    (ROOT / "ACTION_COMPLIANCE_CODEX_BACKEND_SHA256.txt").write_text(output, encoding="utf-8")
    print(output, end="")


if __name__ == "__main__":
    main()
