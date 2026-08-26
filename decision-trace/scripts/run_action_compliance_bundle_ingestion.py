#!/usr/bin/env python3
"""Freeze bundle-derived Decision records and AuthorityProofs.

The command has no benchmark-ground-truth input.  It writes the extraction
and resolver result before any diagnostic comparison is allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from authority import resolve_authority_with_proof  # noqa: E402
from bundle_source import LocalBundleSource  # noqa: E402
from ingest import BundleExtractionResult, extract_bundle_decisions  # noqa: E402


def _json_default(value):
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _proof_dict(proof):
    if proof is None:
        return None
    return asdict(proof)


def _decision_dict(decision):
    result = asdict(decision)
    result["current_status"] = decision.current_status.value
    result["related_decisions"] = [
        {"target": target, "relationship": relationship.value}
        for target, relationship in decision.related_decisions
    ]
    result["evidence"] = [asdict(evidence) for evidence in decision.evidence]
    return result


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, default=_json_default, sort_keys=True, indent=2) + "\n")


def freeze_bundle(bundle_dir: Path, output_dir: Path) -> dict:
    source = LocalBundleSource(bundle_dir)
    extraction: BundleExtractionResult = extract_bundle_decisions(source)
    proof = None
    if extraction.requested_scope:
        proof = resolve_authority_with_proof(
            list(extraction.decisions), extraction.requested_scope
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "decisions.json",
        {
            "requested_scope": extraction.requested_scope,
            "records": list(extraction.records),
            "decisions": [_decision_dict(decision) for decision in extraction.decisions],
            "uncertainty": list(extraction.uncertainty),
            "failures": list(extraction.failures),
        },
    )
    _write_json(output_dir / "authority_proof.json", _proof_dict(proof))
    raw_sha = hashlib.sha256(extraction.raw_response.encode("utf-8")).hexdigest()
    _write_json(output_dir / "extraction_metadata.json", {
        "bundle_dir": str(bundle_dir),
        "raw_model_response_sha256": raw_sha,
        "decision_count": len(extraction.decisions),
        "failure_count": len(extraction.failures),
        "proof_generated": proof is not None,
    })
    return {
        "bundle": str(bundle_dir),
        "decisions": len(extraction.decisions),
        "failures": len(extraction.failures),
        "authority_state": proof.authority_state if proof else "NOT_GENERATED",
        "governing_decision_id": proof.governing_decision_id if proof else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundles_root", type=Path)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    summaries = []
    for bundle_dir in sorted(path for path in args.bundles_root.iterdir() if path.is_dir()):
        summaries.append(freeze_bundle(bundle_dir, args.output_root / bundle_dir.name))
    _write_json(args.output_root / "run_summary.json", summaries)
    print(json.dumps(summaries, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
