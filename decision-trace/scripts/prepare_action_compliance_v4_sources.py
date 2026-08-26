#!/usr/bin/env python3
"""Prepare complete pinned local source mirrors for V4 worktrees."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from setup_action_compliance_full_worktree import REPOSITORIES


def checked(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=3600)
    if process.returncode != 0:
        raise RuntimeError((process.stdout + process.stderr).strip())
    return process


def prepare(root: Path) -> dict[str, object]:
    source_root = root / "sources"
    source_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for task in sorted(REPOSITORIES):
        repository, pinned_sha = REPOSITORIES[task]
        mirror = source_root / f"{task}.git"
        if not mirror.exists():
            mirror.mkdir(parents=True)
            checked(["git", "init", "--bare", "-q", str(mirror)], cwd=root)
            checked(["git", "--git-dir", str(mirror), "remote", "add", "origin", repository], cwd=root)
        checked(
            ["git", "--git-dir", str(mirror), "fetch", "--no-tags", "--depth", "1", "origin", pinned_sha],
            cwd=root,
        )
        checked(["git", "--git-dir", str(mirror), "cat-file", "-e", f"{pinned_sha}^{{commit}}"], cwd=root)
        records.append(
            {
                "task": task,
                "repository": repository,
                "pinned_sha": pinned_sha,
                "mirror": str(mirror),
                "bytes": sum(item.stat().st_size for item in mirror.rglob("*") if item.is_file()),
            }
        )
    result = {"source_root": str(source_root), "tasks": records}
    path = root / "source_mirrors.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-root", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.storage_root.resolve())
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"V4_SOURCE_PREPARE_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
