#!/usr/bin/env python3
"""Create a neutral local bundle from a frozen task fixture.

This is a preparation tool, not an authority interpreter.  It extracts only
the literal requested-change block and copies source bytes under neutral
artifact names.  The resulting directory is the only input accepted by
LocalBundleSource.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def _requested_change(task_file: Path) -> str:
    lines = task_file.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next((i + 1 for i, line in enumerate(lines) if line.startswith("## requested_change")), None)
    if start is None:
        raise ValueError(f"no requested_change section: {task_file}")
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "".join(lines[start:end])


def prepare(task_dir: Path, output_dir: Path) -> None:
    source_dir = task_dir / "context_bundle"
    if not source_dir.is_dir():
        raise ValueError(f"missing context_bundle: {source_dir}")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    (output_dir / "requested_change.txt").write_text(
        _requested_change(task_dir / "TASK.md"), encoding="utf-8"
    )
    source_files = sorted(path for path in source_dir.iterdir() if path.is_file())
    for index, source_file in enumerate(source_files, start=1):
        target = artifact_dir / f"artifact_{index:03d}.md"
        target.write_bytes(source_file.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    prepare(args.task_dir, args.output_dir)


if __name__ == "__main__":
    main()
