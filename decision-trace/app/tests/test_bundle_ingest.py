from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authority import resolve_authority_with_proof  # noqa: E402
from bundle_source import LocalBundleSource  # noqa: E402
from ingest import extract_bundle_decisions  # noqa: E402


def _bundle(root: Path, extra: str = "") -> None:
    (root / "artifacts").mkdir(parents=True)
    (root / "requested_change.txt").write_text("Implement a bounded change in package x.\n")
    (root / "artifacts" / "artifact_001.md").write_text(
        "# Accepted design\nSource: https://example.test/a\n"
        "The accepted design is the iterator form.\n" + extra
    )
    (root / "artifacts" / "artifact_002.md").write_text(
        "# Older proposal\nSource: https://example.test/b\n"
        "The proposal was declined.\n"
    )


def _response() -> str:
    return json.dumps({
        "requested_scope": "package x",
        "decisions": [
            {
                "artifact_id": "artifact_001",
                "subject": "Use iterator form",
                "current_status": "ACCEPTED",
                "role": "policy",
                "scopes": ["package x"],
                "chosen_approach": "iterator form",
                "rejected_alternatives": [],
                "rationale": "The accepted design is the iterator form.",
                "constraints": [],
                "partial_acceptance": False,
                "related_decisions": [],
                "evidence_quotes": [{
                    "artifact_id": "artifact_001",
                    "quote": "The accepted design is the iterator form.",
                }],
            },
            {
                "artifact_id": "artifact_002",
                "subject": "Use slice helper",
                "current_status": "PROPOSED",
                "role": "policy",
                "scopes": ["package x"],
                "chosen_approach": "slice helper",
                "rejected_alternatives": [],
                "rationale": "The proposal was declined.",
                "constraints": [],
                "partial_acceptance": False,
                "related_decisions": [],
                "evidence_quotes": [{
                    "artifact_id": "artifact_002",
                    "quote": "The proposal was declined.",
                }],
            },
        ],
        "uncertainty": [],
    })


def test_bundle_extraction_is_source_driven_and_resolves_without_manual_records(tmp_path):
    _bundle(tmp_path)
    result = extract_bundle_decisions(LocalBundleSource(tmp_path), generator=lambda _: _response())

    assert len(result.decisions) == 2
    assert all(decision.evidence for decision in result.decisions)
    assert result.decisions[0].current_status.value == "ACCEPTED"
    proof = resolve_authority_with_proof(list(result.decisions), result.requested_scope)
    assert proof.authority_state == "GOVERNING"
    assert proof.governing_decision_id == "bundle-artifact_001-decision-0"


def test_invalid_quote_is_dropped_not_repaired(tmp_path):
    _bundle(tmp_path)
    payload = json.loads(_response())
    payload["decisions"][0]["evidence_quotes"][0]["quote"] = "not in source"
    result = extract_bundle_decisions(
        LocalBundleSource(tmp_path), generator=lambda _: json.dumps(payload)
    )

    assert not result.decisions[0].evidence
    assert any("unverifiable evidence" in failure for failure in result.failures)


def test_minimal_directory_is_sufficient(tmp_path):
    _bundle(tmp_path)
    result = extract_bundle_decisions(LocalBundleSource(tmp_path), generator=lambda _: _response())
    assert result.decisions
