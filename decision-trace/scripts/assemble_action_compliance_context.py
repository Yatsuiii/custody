#!/usr/bin/env python3
"""Materialize one fair A/B/C context envelope per neutral task bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from action_compliance_context import assemble_context, proof_text  # noqa: E402
from bundle_source import LocalBundleSource  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assemble_one(
    bundle_dir: Path,
    condition: str,
    output_dir: Path,
    system_prompt: str,
    summary_root: Path | None,
    proof_root: Path | None,
) -> dict:
    source = LocalBundleSource(bundle_dir)
    summary = None
    proof = None
    if condition == "B":
        if summary_root is None:
            raise ValueError("Arm B requires --summary-root")
        summary = (summary_root / bundle_dir.name / "summary.txt").read_text(encoding="utf-8")
    elif condition == "C":
        if proof_root is None:
            raise ValueError("Arm C requires --proof-root")
        proof = proof_text(proof_root / bundle_dir.name / "authority_proof.json")
    envelope = assemble_context(
        source, condition, system_prompt, summary=summary, authority_proof=proof
    )
    task_out = output_dir / bundle_dir.name
    _write(task_out / "context.txt", envelope.context_text)
    metadata = {
        "condition": condition,
        "bundle": str(bundle_dir),
        "raw_content_sha256": envelope.raw_content_sha256,
        "raw_prefix_sha256": envelope.raw_prefix_sha256,
        "context_sha256": envelope.context_sha256,
        "raw_bytes": envelope.raw_bytes,
        "context_bytes": envelope.context_bytes,
        "system_bytes": envelope.system_bytes,
        "total_bytes": envelope.total_bytes,
        "raw_words": envelope.raw_words,
        "context_words": envelope.context_words,
        "estimated_tokens": envelope.estimated_tokens,
    }
    _write(task_out / "metadata.json", json.dumps(metadata, sort_keys=True, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundles_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--condition", choices=("A", "B", "C"), required=True)
    parser.add_argument("--system-prompt", type=Path, required=True)
    parser.add_argument("--summary-root", type=Path)
    parser.add_argument("--proof-root", type=Path)
    args = parser.parse_args()
    system_prompt = args.system_prompt.read_text(encoding="utf-8")
    rows = [
        assemble_one(
            bundle_dir,
            args.condition,
            args.output_root,
            system_prompt,
            args.summary_root,
            args.proof_root,
        )
        for bundle_dir in sorted(path for path in args.bundles_root.iterdir() if path.is_dir())
    ]
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "manifest.json").write_text(
        json.dumps(rows, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(rows, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
