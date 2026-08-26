#!/usr/bin/env python3
"""Generate Arm-B summaries with the frozen coding-agent model, no tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from generate_action_compliance_summaries import SUMMARY_PROMPT, _raw_context
from bundle_source import LocalBundleSource


MODEL = "claude-sonnet-4-5-20250929"
CLI_VERSION = "2.1.232"


def _summary(prompt: str, cwd: Path) -> tuple[str, dict]:
    command = [
        "claude",
        "--safe-mode",
        "--model", MODEL,
        "--print",
        "--no-session-persistence",
        "--output-format", "json",
        "--permission-mode", "dontAsk",
        "--tools", "",
        "--system-prompt", "Return only the requested context summary. Do not use tools.",
        prompt,
    ]
    process = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=300
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    payload = json.loads(process.stdout)
    text = payload.get("result")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Claude summary response did not contain a result")
    return text, {
        "model": MODEL,
        "cli_version": CLI_VERSION,
        "temperature": "backend default (Claude Code CLI exposes no temperature flag)",
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "response_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "usage": payload.get("usage"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundles_root", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for bundle_dir in sorted(path for path in args.bundles_root.iterdir() if path.is_dir()):
        source = LocalBundleSource(bundle_dir)
        prompt = SUMMARY_PROMPT + _raw_context(source)
        summary, metadata = _summary(prompt, Path.cwd())
        output_dir = args.output_root / bundle_dir.name
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "summary.txt").write_text(summary, encoding="utf-8")
        metadata.update({
            "bundle": str(bundle_dir),
            "summary_prompt_sha256": hashlib.sha256(SUMMARY_PROMPT.encode("utf-8")).hexdigest(),
        })
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        rows.append(metadata)
    (args.output_root / "summary_manifest.json").write_text(
        json.dumps(rows, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(rows, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
