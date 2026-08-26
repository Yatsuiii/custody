from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from action_compliance_extraction_v2 import (  # noqa: E402
    extract_bundle_decisions_v2,
    normalize_scope,
)
from authority import resolve_authority_with_proof  # noqa: E402
from bundle_source import LocalBundleSource  # noqa: E402


def _bundle(root: Path) -> None:
    (root / "artifacts").mkdir(parents=True)
    (root / "requested_change.txt").write_text("Implement a bounded change in package x.\n")
    (root / "artifacts" / "artifact_001.md").write_text(
        "# Accepted design\nSource: https://example.test/a\n"
        "The accepted design is the iterator form.\n"
    )
    (root / "artifacts" / "artifact_002.md").write_text(
        "# Older proposal\nSource: https://example.test/b\n"
        "The proposal was declined and the iterator form replaced it.\n"
    )


def test_scope_normalization_reconciles_case_and_whitespace_noise(tmp_path):
    """Reproduces the v1 root cause: the model phrases requested_scope and a
    decision's scopes slightly differently (case/whitespace only). v1 would
    fail the resolver's exact-match with NO_GOVERNING_DECISION; v2's
    deterministic normalization must still resolve it."""
    _bundle(tmp_path)
    response = json.dumps({
        "requested_scope": "  Package-X  ",
        "decisions": [{
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
        }],
        "uncertainty": [],
    })
    result = extract_bundle_decisions_v2(
        LocalBundleSource(tmp_path), generator=lambda _: response
    )
    assert result.requested_scope == "package-x"
    assert result.decisions[0].related_components == ["package-x"]
    proof = resolve_authority_with_proof(list(result.decisions), result.requested_scope)
    assert proof.authority_state == "GOVERNING"


def test_requested_scope_with_no_matching_decision_is_flagged(tmp_path):
    """A scope mismatch the normalization can't fix (genuinely different
    slugs) must surface as an explicit failure, not silently pass through
    to a resolver call that will trivially return NO_GOVERNING_DECISION."""
    _bundle(tmp_path)
    response = json.dumps({
        "requested_scope": "unrelated-topic",
        "decisions": [{
            "artifact_id": "artifact_001",
            "subject": "Use iterator form",
            "current_status": "ACCEPTED",
            "role": "policy",
            "scopes": ["package-x"],
            "chosen_approach": "iterator form",
            "rejected_alternatives": [],
            "rationale": None,
            "constraints": [],
            "partial_acceptance": False,
            "related_decisions": [],
            "evidence_quotes": [],
        }],
        "uncertainty": [],
    })
    result = extract_bundle_decisions_v2(
        LocalBundleSource(tmp_path), generator=lambda _: response
    )
    assert any("matched no extracted decision" in failure for failure in result.failures)


def test_supersedes_edge_survives_deprecation_then_replacement_pattern(tmp_path):
    _bundle(tmp_path)
    response = json.dumps({
        "requested_scope": "package-x",
        "decisions": [
            {
                "artifact_id": "artifact_002",
                "subject": "Slice helper proposal",
                "current_status": "SUPERSEDED",
                "role": "policy",
                "scopes": ["package-x"],
                "chosen_approach": None,
                "rejected_alternatives": [],
                "rationale": None,
                "constraints": [],
                "partial_acceptance": False,
                "related_decisions": [],
                "evidence_quotes": [{
                    "artifact_id": "artifact_002",
                    "quote": "The proposal was declined and the iterator form replaced it.",
                }],
            },
            {
                "artifact_id": "artifact_001",
                "subject": "Use iterator form",
                "current_status": "ACCEPTED",
                "role": "policy",
                "scopes": ["package-x"],
                "chosen_approach": "iterator form",
                "rejected_alternatives": [],
                "rationale": None,
                "constraints": [],
                "partial_acceptance": False,
                "related_decisions": [{"target_index": 0, "relationship": "SUPERSEDES"}],
                "evidence_quotes": [],
            },
        ],
        "uncertainty": [],
    })
    result = extract_bundle_decisions_v2(
        LocalBundleSource(tmp_path), generator=lambda _: response
    )
    winner = next(d for d in result.decisions if d.subject == "Use iterator form")
    assert winner.related_decisions == [("bundle-artifact_002-decision-0", winner.related_decisions[0][1])]
    proof = resolve_authority_with_proof(list(result.decisions), result.requested_scope)
    assert proof.authority_state == "GOVERNING"
    assert proof.governing_decision_id == winner.id


def test_normalize_scope_is_idempotent_and_case_insensitive():
    assert normalize_scope("  Some   Scope--Name!! ") == "some-scope-name"
    assert normalize_scope(normalize_scope("Foo Bar")) == normalize_scope("Foo Bar")
