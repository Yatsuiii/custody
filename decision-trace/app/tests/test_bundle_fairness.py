from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bundle_source import BundleInputError, LocalBundleSource  # noqa: E402
from ingest import extract_bundle_decisions  # noqa: E402


def _make_root(root: Path) -> None:
    (root / "artifacts").mkdir(parents=True)
    (root / "requested_change.txt").write_text("Implement one source-backed change.\n")
    (root / "artifacts" / "artifact_001.md").write_text(
        "# Source\nhttps://example.test/source\nThe accepted choice is A.\n"
    )


def _model_response(prompt: str) -> str:
    assert "Implement one source-backed change." in prompt
    assert "The accepted choice is A." in prompt
    assert "TASK.md" not in prompt
    assert "authority_error_category" not in prompt
    return json.dumps({
        "requested_scope": "source-backed change",
        "decisions": [{
            "artifact_id": "artifact_001",
            "subject": "Choice A",
            "current_status": "ACCEPTED",
            "role": "policy",
            "scopes": ["source-backed change"],
            "chosen_approach": "A",
            "rejected_alternatives": [],
            "rationale": "The accepted choice is A.",
            "constraints": [],
            "partial_acceptance": False,
            "related_decisions": [],
            "evidence_quotes": [{
                "artifact_id": "artifact_001",
                "quote": "The accepted choice is A.",
            }],
        }],
        "uncertainty": [],
    })


def _fingerprint(result) -> str:
    payload = {
        "decisions": [
            {
                "id": d.id,
                "status": d.current_status.value,
                "scope": d.related_components,
                "edges": [(target, relation.value) for target, relation in d.related_decisions],
                "evidence": [(e.url, e.quote) for e in d.evidence],
            }
            for d in result.decisions
        ],
        "requested_scope": result.requested_scope,
        "failures": result.failures,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def test_forbidden_benchmark_files_cannot_affect_bundle_extraction(tmp_path):
    neutral = tmp_path / "neutral"
    _make_root(neutral)
    baseline = extract_bundle_decisions(LocalBundleSource(neutral), generator=_model_response)

    # These files stand in for every benchmark-only source.  They are outside
    # the adapter root and therefore cannot enter the model prompt.
    for name in (
        "TASK.md", "ACTION_COMPLIANCE_LEDGER.md", "grader.py",
        "sanity_patch_compliant.diff", "sanity_patch_violating.diff",
    ):
        (tmp_path / name).write_text("adversarial expected winner: NEVER READ")
    after = extract_bundle_decisions(LocalBundleSource(neutral), generator=_model_response)

    assert _fingerprint(baseline) == _fingerprint(after)


def test_forbidden_file_inside_bundle_is_rejected(tmp_path):
    _make_root(tmp_path)
    (tmp_path / "TASK.md").write_text("adversarial")
    with pytest.raises(BundleInputError):
        LocalBundleSource(tmp_path)


def test_minimal_directory_contains_only_allowed_inputs(tmp_path):
    _make_root(tmp_path)
    source = LocalBundleSource(tmp_path)
    assert source.requested_change()
    assert len(source.list_artifacts()) == 1
