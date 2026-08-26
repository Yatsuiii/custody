#!/usr/bin/env python3
"""Create the content-addressed V6 benchmark manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V6_SHA256.txt"
SUPERSEDED_OUTPUT = ROOT / "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V6_PRE_RUNTIME_BOUNDARY_FIX_SHA256.txt"
SUPERSEDED_OUTPUT_SHA256 = "0e8a02d2da4da13ea947d8681ae38e66b3fd4beddc4f0fde5b2f72309bcca84a"
RUNTIME_EVIDENCE_NAMES = frozenset({"host_launch_snapshot.json"})
FILES = (
    "ACTION_COMPLIANCE_BUNDLE_INGEST_AUDIT.md",
    "ACTION_COMPLIANCE_BUNDLE_INPUT_POLICY.json",
    "ACTION_COMPLIANCE_CLAUDE_OUTPUT_EXCLUSION.md",
    "ACTION_COMPLIANCE_SPARSE_CHECKOUT_INVALIDATION.md",
    "ACTION_COMPLIANCE_FULL_WORKTREE_V2_INVALIDATION.md",
    "ACTION_COMPLIANCE_V3_DISK_FAILURE_AUDIT.md",
    "ACTION_COMPLIANCE_V3_DISK_QUOTA_INVALIDATION.md",
    "ACTION_COMPLIANCE_V4_INVALIDATION.md",
    "ACTION_COMPLIANCE_V5_FREEZE_SUPERSESSION.md",
    "ACTION_COMPLIANCE_V6_MANIFEST_RUNTIME_BOUNDARY_AMENDMENT.md",
    "ACTION_COMPLIANCE_V6_GATE_REPORT.md",
    "ACTION_COMPLIANCE_FINAL_RUN_MANIFEST_V6_PRE_RUNTIME_BOUNDARY_FIX_SHA256.txt",
    "ACTION_COMPLIANCE_CODEX_BACKEND_CONFIG_V6.json",
    "ACTION_COMPLIANCE_CODEX_BACKEND_V6_SHA256.txt",
    "ACTION_COMPLIANCE_CODING_SYSTEM_PROMPT.txt",
    "ACTION_COMPLIANCE_RUN_PROTOCOL.md",
    "ACTION_COMPLIANCE_FINAL_RUN_PROTOCOL_V6.md",
    "ACTION_COMPLIANCE_V6_STORAGE_CONTRACT.md",
    "ACTION_COMPLIANCE_TEST_INTERPRETER_CONTRACT_V6.md",
    "ACTION_COMPLIANCE_PRE_RUN_AUDIT.md",
    "ACTION_COMPLIANCE_EXTRACTION_V2_REPORT.md",
    "ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE.md",
    "ACTION_COMPLIANCE_EXTRACTOR_V2_FREEZE_SHA256.txt",
    "ACTION_COMPLIANCE_HOLDOUT_V2_OUTPUT_SHA256.txt",
    "ACTION_COMPLIANCE_SPEC.md",
    "EXTRACTION_DEV_CORPUS.md",
    "app/action_compliance_context.py",
    "app/action_compliance_extraction_v2.py",
    "app/authority.py",
    "app/bundle_source.py",
    "app/ingest.py",
    "scripts/action_compliance_test_contract.py",
    "scripts/action_compliance_v4_storage.py",
    "scripts/assemble_action_compliance_context.py",
    "scripts/create_action_compliance_backend_hash_v6.py",
    "scripts/create_action_compliance_manifest_v6.py",
    "scripts/dry_run_action_compliance_v6.py",
    "scripts/replay_action_compliance_sanity_v6.py",
    "scripts/run_action_compliance_codex.py",
    "scripts/run_action_compliance_codex_v6.py",
    "scripts/setup_action_compliance_full_worktree.py",
    "scripts/stress_action_compliance_v6_storage.py",
    "scripts/verify_action_compliance_v6_storage.py",
    "scripts/verify_authority_freeze.py",
)
DIRECTORIES = (
    "pilot/task-01-k8s-postfilter-victims",
    "pilot/task-02-django-index-together-superseded",
    "pilot/task-03-pip-inline-script-metadata",
    "pilot/task-04-cpython-locale-encoding-scope",
    "pilot/task-05-packaging-manylinux-aliases",
    "pilot/task-06-opentofu-static-source-scope",
    "pilot/task-07-axum-optional-typed-header",
    "pilot/task-go-01-maps-sorted-keys",
    "data/action_compliance/bundle_inputs",
    "data/action_compliance/contexts",
    "data/action_compliance/summaries",
    "data/action_compliance/v6_sanity_replay",
    "data/action_compliance/v6_dry_run_host",
    "data/action_compliance/v6_dry_run_host_contract_v2",
    "data/action_compliance/v6_storage_stress",
    "data/action_compliance/v6_storage_recovery",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preserve_superseded_manifest() -> None:
    """Keep the failed pre-output freeze as immutable lineage evidence."""
    if SUPERSEDED_OUTPUT.exists():
        if _sha256(SUPERSEDED_OUTPUT) != SUPERSEDED_OUTPUT_SHA256:
            raise RuntimeError(f"superseded V6 manifest changed: {SUPERSEDED_OUTPUT}")
        return
    if not OUTPUT.exists() or _sha256(OUTPUT) != SUPERSEDED_OUTPUT_SHA256:
        raise RuntimeError("cannot preserve the expected superseded V6 manifest")
    SUPERSEDED_OUTPUT.write_bytes(OUTPUT.read_bytes())


def _is_frozen_artifact(path: Path) -> bool:
    """Exclude mutable host observations from immutable experiment inputs."""
    return (
        path.is_file()
        and path.name not in RUNTIME_EVIDENCE_NAMES
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def main() -> None:
    _preserve_superseded_manifest()
    paths = {ROOT / relative for relative in FILES}
    for relative in DIRECTORIES:
        directory = ROOT / relative
        if directory.exists():
            paths.update(
                path
                for path in directory.rglob("*")
                if _is_frozen_artifact(path)
            )
    paths = {
        path
        for path in paths
        if path.exists() and path != OUTPUT and _is_frozen_artifact(path)
    }
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}"
        for path in sorted(paths)
    ]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(lines)}")
    print(f"manifest={OUTPUT}")


if __name__ == "__main__":
    main()
