from pathlib import Path

import pytest

from action_compliance_context import assemble_context
from bundle_source import LocalBundleSource


def _bundle(tmp_path: Path) -> LocalBundleSource:
    root = tmp_path / "bundle"
    (root / "artifacts").mkdir(parents=True)
    (root / "requested_change.txt").write_text("Implement the requested change.\n")
    (root / "artifacts" / "artifact_001.md").write_text("# Source\nA decision.\n")
    return LocalBundleSource(root)


def test_all_conditions_share_raw_prefix(tmp_path: Path) -> None:
    source = _bundle(tmp_path)
    system = "system\n"
    a = assemble_context(source, "A", system)
    b = assemble_context(source, "B", system, summary="summary\n")
    c = assemble_context(source, "C", system, authority_proof="proof\n")
    assert a.raw_text == b.raw_text == c.raw_text
    assert a.raw_content_sha256 == b.raw_content_sha256 == c.raw_content_sha256
    assert a.raw_prefix_sha256 == b.raw_prefix_sha256 == c.raw_prefix_sha256
    assert "DERIVED CONTEXT" not in a.context_text
    assert "ARM B SUMMARY" in b.context_text
    assert "ARM C AUTHORITYPROOF" in c.context_text


def test_derived_sections_are_exclusive(tmp_path: Path) -> None:
    source = _bundle(tmp_path)
    with pytest.raises(ValueError):
        assemble_context(source, "A", "system", summary="not allowed")
    with pytest.raises(ValueError):
        assemble_context(source, "B", "system")
    with pytest.raises(ValueError):
        assemble_context(source, "C", "system", summary="wrong")
