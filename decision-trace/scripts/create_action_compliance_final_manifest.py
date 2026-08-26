#!/usr/bin/env python3
"""Create the consolidated checksum manifest for the full 63-run package.

Extends the extractor-only run manifest (ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt)
with the extractor-v2 freeze, the v2 holdout outputs, the dev corpus, and the
blind randomized run plan, so a single file covers everything Phase 8 of the
action-compliance run protocol requires to be frozen before comparative
coding-agent output begins.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = (
    "ACTION_COMPLIANCE_BUNDLE_INGEST_AUDIT.md",
    "ACTION_COMPLIANCE_BUNDLE_INPUT_POLICY.json",
    "ACTION_COMPLIANCE_CLAUDE_OUTPUT_EXCLUSION.md",
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG.json",
    "ACTION_COMPLIANCE_CODEX_BACKEND_SHA256.txt",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "ACTION_COMPLIANCE_MANIFEST_SUPERSESSION.md",
    "ACTION_COMPLIANCE_INVENTORY_SHA256.txt",
    "ACTION_COMPLIANCE_RUN_PROTOCOL.md",
    "ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL.md",
    "ACTION_COMPLIANCE_PRE_RUN_AUDIT.md",
    "ACTION_COMPLIANCE_BUNDLE_DIAGNOSTIC_COMPARISON.md",
    "ACTION_COMPLIANCE_EXTRACTION_FAILURE_AUDIT.md",
    "EXTRACTION_DEV_CORPUS.md",
    "ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE.md",
    "ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt",
    "ACTION_COMPLIANCE_EXTRACTION_V2_REPORT.md",
    "ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt",
    "app/action_compliance_context.py",
    "app/action_compliance_extraction_v2.py",
    "app/bundle_source.py",
    "app/ingest.py",
    "app/authority.py",
    "app/tests/test_action_compliance_context.py",
    "app/tests/test_action_compliance_extraction_v2.py",
    "app/tests/test_bundle_fairness.py",
    "app/tests/test_bundle_ingest.py",
    "app/tests/test_bundle_source.py",
    "scripts/assemble_action_compliance_context.py",
    "scripts/create_action_compliance_run_manifest.py",
    "scripts/create_action_compliance_final_manifest.py",
    "scripts/dry_run_action_compliance.py",
    "scripts/create_action_compliance_backend_hash.py",
    "scripts/dry_run_grader.py",
    "scripts/generate_action_compliance_summaries.py",
    "scripts/generate_action_compliance_summaries_claude.py",
    "scripts/prepare_action_compliance_bundle.py",
    "scripts/replay_action_compliance_sanity.py",
    "scripts/run_action_compliance_codex.py",
    "scripts/run_action_compliance_bundle_ingestion.py",
    "scripts/run_action_compliance_bundle_ingestion_v2.py",
    "scripts/verify_action_compliance_bundle.py",
    "scripts/verify_action_compliance_contexts.py",
    "scripts/verify_authority_freeze.py",
)

DIRECTORIES = (
    "data/action_compliance/bundle_inputs",
    "data/action_compliance/bundle_runs",
    "data/action_compliance/contexts",
    "data/action_compliance/dry_run",
    "data/action_compliance/codex_preflight",
    "data/action_compliance/sanity_replay",
    "data/action_compliance/summaries_claude",
    "data/action_compliance/dev_corpus",
    "data/action_compliance/holdout_v2_runs",
)

EXCLUDE_NAMES = frozenset(
    {
        "ACTION_COMPLIANCE_RUN_MANIFEST_SHA256.txt",
        "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_SHA256.txt",
    }
)


def _files() -> list[Path]:
    paths = {ROOT / relative for relative in FILES}
    for directory in DIRECTORIES:
        root = ROOT / directory
        if root.exists():
            paths.update(path for path in root.rglob("*") if path.is_file())
    return sorted(
        path
        for path in paths
        if path.exists() and path.name not in EXCLUDE_NAMES
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_SHA256.txt",
    )
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
