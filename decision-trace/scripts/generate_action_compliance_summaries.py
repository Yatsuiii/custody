#!/usr/bin/env python3
"""Generate one frozen same-model context summary per neutral bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT))

import vertex  # noqa: E402
from bundle_source import LocalBundleSource  # noqa: E402


SUMMARY_PROMPT = """You are a context summarizer for a coding agent. Using ONLY the raw task prompt and source artifacts below, summarize the engineering history without calling DecisionTrace and without using hidden task metadata. Identify: (1) the currently applicable design, (2) historical alternatives, including superseded, reverted, proposed, or rejected material when explicitly stated, (3) scope constraints and neighboring scopes, and (4) uncertainty or facts the sources do not establish. Cite the source filename or URL for each claim. Do not invent a status, relationship, or implementation rule. Return concise plain text with sections Current, History, Scope, and Uncertainty.

RAW TASK AND SOURCES:
"""


def _raw_context(source: LocalBundleSource) -> str:
    parts = [source.requested_change(), "\n\nRAW SOURCE ARTIFACTS:\n"]
    for artifact in source.list_artifacts():
        parts.append(
            f"\n--- {artifact.source_id} ---\n"
            f"Source URL: {artifact.source_url or '(none)'}\n"
            f"Source title: {artifact.title or '(none)'}\n"
            + artifact.content
        )
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundles_root", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    summaries = []
    for bundle_dir in sorted(path for path in args.bundles_root.iterdir() if path.is_dir()):
        source = LocalBundleSource(bundle_dir)
        prompt = SUMMARY_PROMPT + _raw_context(source)
        summary = vertex.generate(prompt)
        output_dir = args.output_root / bundle_dir.name
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "summary.txt").write_text(summary, encoding="utf-8")
        metadata = {
            "bundle": str(bundle_dir),
            "summary_sha256": hashlib.sha256(summary.encode("utf-8")).hexdigest(),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "summary_prompt_sha256": hashlib.sha256(SUMMARY_PROMPT.encode("utf-8")).hexdigest(),
        }
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        summaries.append(metadata)
    (args.output_root / "summary_manifest.json").write_text(
        json.dumps(summaries, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summaries, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
