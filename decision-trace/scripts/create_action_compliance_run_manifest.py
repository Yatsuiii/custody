#!/usr/bin/env python3
"""Create the deterministic checksum manifest for the no-agent run package."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "ACTION_COMPLIANCE_BUNDLE_INGEST_AUDIT.md",
    "ACTION_COMPLIANCE_BUNDLE_INPUT_POLICY.json",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "ACTION_COMPLIANCE_INVENTORY_SHA256.txt",
    "ACTION_COMPLIANCE_RUN_PROTOCOL.md",
    "ACTION_COMPLIANCE_BUNDLE_DIAGNOSTIC_COMPARISON.md",
    "app/action_compliance_context.py",
    "app/bundle_source.py",
    "app/ingest.py",
    "app/tests/test_action_compliance_context.py",
    "app/tests/test_bundle_fairness.py",
    "app/tests/test_bundle_ingest.py",
    "app/tests/test_bundle_source.py",
    "scripts/assemble_action_compliance_context.py",
    "scripts/create_action_compliance_run_manifest.py",
    "scripts/dry_run_action_compliance.py",
    "scripts/dry_run_grader.py",
    "scripts/generate_action_compliance_summaries.py",
    "scripts/generate_action_compliance_summaries_claude.py",
    "scripts/prepare_action_compliance_bundle.py",
    "scripts/replay_action_compliance_sanity.py",
    "scripts/run_action_compliance_bundle_ingestion.py",
    "scripts/verify_action_compliance_bundle.py",
    "scripts/verify_action_compliance_contexts.py",
    "scripts/verify_authority_freeze.py",
)
DIRECTORIES = (
    "data/action_compliance/bundle_inputs",
    "data/action_compliance/bundle_runs",
    "data/action_compliance/contexts",
    "data/action_compliance/dry_run",
    "data/action_compliance/sanity_replay",
    "data/action_compliance/summaries_claude",
)


def _files() -> list[Path]:
    paths = {ROOT / relative for relative in FILES}
    for directory in DIRECTORIES:
        root = ROOT / directory
        if root.exists():
            paths.update(path for path in root.rglob("*") if path.is_file())
    return sorted(path for path in paths if path.exists() and path.name != "ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt")
    args = parser.parse_args()
    lines = []
    for path in _files():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(lines)}")
    print(f"manifest={args.output}")


if __name__ == "__main__":
    main()
