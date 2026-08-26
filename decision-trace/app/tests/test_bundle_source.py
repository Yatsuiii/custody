from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bundle_source import BundleInputError, LocalBundleSource  # noqa: E402


def _write_bundle(root: Path) -> None:
    (root / "artifacts").mkdir(parents=True)
    (root / "requested_change.txt").write_text("Implement the requested change.\n")
    (root / "artifacts" / "artifact_001.md").write_text(
        "# A source title\n\nSource: https://example.test/issue/1\n"
        "The proposal was explicitly declined.\n"
    )


def test_local_source_neutralizes_identity_and_derives_only_transport_metadata(tmp_path):
    _write_bundle(tmp_path)
    source = LocalBundleSource(tmp_path)

    assert source.requested_change().startswith("Implement")
    artifacts = source.list_artifacts()
    assert [artifact.source_id for artifact in artifacts] == ["artifact_001"]
    assert artifacts[0].source_url == "https://example.test/issue/1"
    assert artifacts[0].title == "A source title"
    assert artifacts[0].source_type == "document"


@pytest.mark.parametrize("forbidden", [
    "TASK.md",
    "grader.py",
    "SANITY_RESULTS.md",
    "sanity_patch_compliant.diff",
    "ACTION_COMPLIANCE_LEDGER.md",
])
def test_local_source_rejects_forbidden_benchmark_files(tmp_path, forbidden):
    _write_bundle(tmp_path)
    (tmp_path / forbidden).write_text("adversarial benchmark truth")

    with pytest.raises(BundleInputError):
        LocalBundleSource(tmp_path)


def test_local_source_rejects_non_neutral_artifact_names(tmp_path):
    _write_bundle(tmp_path)
    (tmp_path / "artifacts" / "pep_722_rejected.md").write_text("source")

    with pytest.raises(BundleInputError):
        LocalBundleSource(tmp_path)
