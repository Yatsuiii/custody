#!/usr/bin/env python3
"""Verify byte-identical raw prefixes across materialized A/B/C contexts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _raw_prefix(path: Path, derived_marker: str) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "\n\nDERIVED CONTEXT — "
    if marker in text:
        prefix, suffix = text.split(marker, 1)
        if not suffix.startswith(derived_marker):
            raise ValueError(f"unexpected derived section in {path}")
        return prefix
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contexts_root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    task_names = sorted(
        path.name for path in (args.contexts_root / "A").iterdir() if path.is_dir()
    )
    rows = []
    for task_name in task_names:
        prefixes = {
            condition: _raw_prefix(
                args.contexts_root / condition / task_name / "context.txt",
                {"A": "", "B": "ARM B SUMMARY", "C": "ARM C AUTHORITYPROOF"}[condition],
            )
            for condition in "ABC"
        }
        hashes = {
            condition: hashlib.sha256(prefix.encode("utf-8")).hexdigest()
            for condition, prefix in prefixes.items()
        }
        if len(set(hashes.values())) != 1:
            raise SystemExit(f"raw prefix mismatch for {task_name}: {hashes}")
        rows.append({"task": task_name, "raw_prefix_sha256": hashes["A"]})
    result = {"task_count": len(rows), "all_equal": True, "tasks": rows}
    print(json.dumps(result, sort_keys=True, indent=2) if args.json else "A/B/C_RAW_PREFIX_EQUAL=true")


if __name__ == "__main__":
    main()
