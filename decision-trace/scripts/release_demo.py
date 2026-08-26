"""Emit one deterministic authority proof from the frozen source corpus."""

from __future__ import annotations

import json
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

from authority import resolve_authority_with_proof  # noqa: E402
from loader import load_decisions  # noqa: E402

DEMO_SCOPE = "kep-keps-sig-storage-1979-object-storage-support"


def main() -> None:
    decisions = load_decisions(PROJECT_ROOT / "data" / "decisions.jsonl")
    proof = resolve_authority_with_proof(decisions, DEMO_SCOPE)

    if proof.authority_state != "GOVERNING":
        raise RuntimeError(f"expected a governing proof, got {proof.authority_state}")
    if proof.governing_decision_id != DEMO_SCOPE:
        raise RuntimeError(
            f"expected {DEMO_SCOPE!r} to govern, got {proof.governing_decision_id!r}"
        )

    governing = next(d for d in decisions if d.id == proof.governing_decision_id)
    if not governing.evidence:
        raise RuntimeError("governing decision has no source evidence")

    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    artifact = {
        "component": project["project"]["name"],
        "version": project["project"]["version"],
        "authority_proof": asdict(proof),
        "source_evidence": [asdict(item) for item in governing.evidence],
    }
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
