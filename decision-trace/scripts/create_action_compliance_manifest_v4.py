#!/usr/bin/env python3
"""Create the V4 content-addressed benchmark freeze."""

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
    "ACTION_COMPLIANCE_FULL_WORKTREE_V2_INVALIDATION.md",
    "ACTION_COMPLIANCE_V3_DISK_FAILURE_AUDIT.md",
    "ACTION_COMPLIANCE_V3_DISK_QUOTA_INVALIDATION.md",
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V4.json",
    "ACTION_COMPLIANCE_CODEX_BACKEND_V4_SHA256.txt",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "ACTION_COMPLIANCE_RUN_PROTOCOL.md",
    "ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL_V3.md",
    "ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL_V4.md",
    "ACTION_COMPLIANCE_V4_STORAGE_CONTRACT.md",
    "ACTION_COMPLIANCE_V4_PRE_RUN_GATE_REPORT.md",
    "ACTION_COMPLIANCE_TEST_INTERPRETER_CONTRACT_V3.md",
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
    "scripts/action_compliance_v4_storage.py",
    "scripts/assemble_action_compliance_context.py",
    "scripts/create_action_compliance_backend_hash_v4.py",
    "scripts/create_action_compliance_manifest_v4.py",
    "scripts/dry_run_action_compliance_v3.py",
    "scripts/dry_run_action_compliance_v4.py",
    "scripts/replay_action_compliance_sanity_v3.py",
    "scripts/replay_action_compliance_sanity_v4.py",
    "scripts/run_action_compliance_codex.py",
    "scripts/run_action_compliance_codex_v4.py",
    "scripts/run_action_compliance_v4_preflight.py",
    "scripts/setup_action_compliance_full_worktree.py",
    "scripts/stress_action_compliance_v4_storage.py",
    "scripts/verify_action_compliance_v4_storage.py",
    "scripts/verify_action_compliance_bundle.py",
    "scripts/verify_action_compliance_contexts.py",
    "scripts/verify_authority_freeze.py",
    "scripts/dry_run_grader.py",
    "scripts/generate_action_compliance_summaries.py",
    "scripts/generate_action_compliance_summaries_claude.py",
    "scripts/prepare_action_compliance_bundle.py",
    "scripts/prepare_action_compliance_v4_sources.py",
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
    "data/action_compliance/test_interpreter_contract_v3",
    "data/action_compliance/v3_dry_run",
    "data/action_compliance/v4_storage_stress_v2",
    "data/action_compliance/v4_storage_stress_attempt_1",
    "data/action_compliance/v4_storage_stress_final8",
    "data/action_compliance/v4_dry_run_final4",
    "data/action_compliance/v4_dry_run_final5",
    "data/action_compliance/v4_sanity_replay",
    "data/action_compliance/v4_sanity_replay_final",
    "data/action_compliance/v4_codex_preflight",
    "data/action_compliance/v4_codex_preflight_retry",
    "data/action_compliance/v4_codex_preflight_host_v2",
    "data/action_compliance/v4_storage_stress_final9",
)
OUTPUT_NAME = "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V4_SHA256.txt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT_NAME)
    args = parser.parse_args()
    paths = {ROOT / relative for relative in FILES}
    paths.add(ROOT / "data/action_compliance/v4_execution_storage/source_mirrors.json")
    paths.add(ROOT / "data/action_compliance/v4_storage_recovery_test.json")
    for directory in DIRECTORIES:
        path = ROOT / directory
        if path.exists():
            paths.update(candidate for candidate in path.rglob("*") if candidate.is_file())
    for directory in (ROOT / "data/action_compliance/v4_dry_run", ROOT / "data/action_compliance/v4_sanity_replay"):
        if directory.exists():
            paths.update(candidate for candidate in directory.rglob("*") if candidate.is_file())
    paths = {path for path in paths if path.exists() and path.name != OUTPUT_NAME}
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}"
        for path in sorted(paths)
    ]
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(lines)}")
    print(f"manifest={args.output}")


if __name__ == "__main__":
    main()
