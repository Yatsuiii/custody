"""Fail if prompts, retrieval, parsing, runner, or model helper changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "data" / "prospective" / "run_protocol_freeze_sha256.json"


def test_prospective_run_protocol_is_byte_identical() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["protocol_commit"] == "d8fefb85020aff1021268d0d8b78279e1db75536"
    assert manifest["algorithm"] == "sha256"
    for relative, expected in manifest["files"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative
