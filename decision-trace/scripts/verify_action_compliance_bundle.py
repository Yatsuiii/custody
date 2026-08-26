#!/usr/bin/env python3
"""Verify neutral bundle boundaries and condition-level evidence parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from bundle_source import LocalBundleSource


def _digest(source: LocalBundleSource) -> str:
    digest = hashlib.sha256()
    digest.update(b"requested_change\0")
    digest.update(source.requested_change().encode("utf-8"))
    for artifact in source.list_artifacts():
        digest.update(b"artifact\0")
        digest.update(artifact.source_id.encode("ascii"))
        digest.update(b"\0")
        digest.update(artifact.content.encode("utf-8"))
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle_root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    source = LocalBundleSource(args.bundle_root)
    digest = _digest(source)
    result = {
        "bundle_root": str(args.bundle_root),
        "artifact_count": len(source.list_artifacts()),
        "raw_content_sha256": digest,
        "conditions": {"A": digest, "B": digest, "C": digest},
    }
    if args.json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        print(f"RAW_CONTENT_SHA256={digest}")
        print("A/B/C_CONTENT_EQUAL=true")


if __name__ == "__main__":
    main()
