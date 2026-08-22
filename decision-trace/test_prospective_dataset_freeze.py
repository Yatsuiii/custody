"""Fail if preregistration, prospective cases, evidence, or truth changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "data" / "prospective" / "dataset_freeze_sha256.json"


def test_prospective_dataset_is_byte_identical_to_pre_inference_freeze() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["dataset_commit"] == "dc2d4a69eef52145723fbc0882489abc7fb75252"
    assert manifest["algorithm"] == "sha256"
    for relative, expected in manifest["files"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative
