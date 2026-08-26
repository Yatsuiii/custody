#!/usr/bin/env python3
"""Create the V2 freeze manifest without overwriting V1 history."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "ACTION_COMPLIANCE_BUNDLE_INGEST_AUDIT.md",
    "ACTION_COMPLIANCE_BUNDLE_INPUT_POLICY.json",
    "ACTION_COMPLIANCE_CLAUDE_OUTPUT_EXCLUSION.md",
    "ACTION_COMPLIANCE_SPARSE_CHECKOUT_INVALIDATION.md",
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V2.json",
    "ACTION_COMPLIANCE_CODEX_BACKEND_V2_SHA256.txt",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "ACTION_COMPLIANCE_RUN_PROTOCOL.md",
    "ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL_V2.md",
    "ACTION_COMPLIANCE_PRE_RUN_AUDIT.md",
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
    "scripts/create_action_compliance_manifest_v2.py",
    "scripts/create_action_compliance_backend_hash_v2.py",
    "scripts/dry_run_action_compliance_v2.py",
    "scripts/replay_action_compliance_sanity_v2.py",
    "scripts/run_action_compliance_codex.py",
    "scripts/setup_action_compliance_full_worktree.py",
    "scripts/verify_action_compliance_v2_worktrees.py",
    "scripts/dry_run_grader.py",
    "scripts/generate_action_compliance_summaries.py",
    "scripts/generate_action_compliance_summaries_claude.py",
    "scripts/prepare_action_compliance_bundle.py",
    "scripts/verify_action_compliance_bundle.py",
    "scripts/verify_action_compliance_contexts.py",
    "scripts/verify_authority_freeze.py",
)
DIRECTORIES = (
    "data/action_compliance/bundle_inputs",
    "data/action_compliance/bundle_runs",
    "data/action_compliance/contexts",
    "data/action_compliance/cost_pilot",
    "data/action_compliance/v2_worktree_verification",
    "data/action_compliance/sanity_replay_v2",
    "data/action_compliance/v2_dry_run",
    "data/action_compliance/codex_preflight_v2",
    "data/action_compliance/summaries_claude",
    "data/action_compliance/dev_corpus",
    "data/action_compliance/holdout_v2_runs",
)
EXCLUDE_NAMES = frozenset({"ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V2_SHA256.txt"})


def files() -> list[Path]:
    paths = {ROOT / relative for relative in FILES}
    for directory in DIRECTORIES:
        path = ROOT / directory
        if path.exists():
            paths.update(candidate for candidate in path.rglob("*") if candidate.is_file())
    return sorted(path for path in paths if path.exists() and path.name not in EXCLUDE_NAMES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V2_SHA256.txt")
    args = parser.parse_args()
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}" for path in files()]
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(lines)}")
    print(f"manifest={args.output}")


if __name__ == "__main__":
    main()
