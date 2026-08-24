"""The five-gate, revision-aware Custody falsification spike.

The two JSON fixtures stand in for an Agent Registry snapshot and a later live
MCP ``tools/list`` response. This script does not claim that either came from a
live Google project. It proves the deterministic mechanism required before that
cloud integration is worth building.

    make revision-spike
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.graph import CustodyGraph  # noqa: E402
from custody.origin import CustodyRecord, Origin, Trust, digest  # noqa: E402
from custody.revision import RevisionCatalog, ToolCallDenied, ToolSurface  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"
PROOF = REPO_ROOT / "proof-out" / "revision-spike.json"
DEPARTMENT = "sales"
SERVER = "vendor-knowledge"
TOOL = "vendor-knowledge/fetch_page"
DEMO_BEATS = {
    "breach": 45,
    "stale_registry_detection": 35,
    "selective_containment": 70,
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _record(
    record_id: str,
    *,
    source_tool: str | None = None,
    source_revision: str | None = None,
    derived_from: tuple[str, ...] = (),
) -> CustodyRecord:
    return CustodyRecord(
        origin=Origin.MODEL,
        trust=Trust.TRUSTED,
        author="assistant",
        invocation_id=f"inv-{record_id}",
        content_sha256=digest(record_id),
        source_tool=source_tool,
        source_revision=source_revision,
        id=record_id,
        derived_from=derived_from,
    )


def main() -> int:
    approved = ToolSurface.from_tools_list(
        server=SERVER, payload=_fixture("registry-approved.json")
    )
    changed = ToolSurface.from_tools_list(
        server=SERVER, payload=_fixture("registry-changed-live.json")
    )
    approved_revision = approved.tools[0].revision
    changed_revision = changed.tools[0].revision

    catalog = RevisionCatalog()
    catalog.approve(department=DEPARTMENT, surface=approved)
    governed = catalog.admit(department=DEPARTMENT, surface=changed)

    baseline_bound = "fetch_page" in {tool.runtime_name for tool in approved.tools}
    dispatched: list[str] = []
    try:
        governed.require("fetch_page")
        dispatched.append("fetch_page")
    except ToolCallDenied:
        pass

    graph = CustodyGraph()
    graph.extend(
        (
            _record("old-root", source_tool=TOOL, source_revision=approved_revision),
            _record("sales", derived_from=("old-root",)),
            _record("support", derived_from=("sales",)),
            _record("finance", derived_from=("support",)),
            _record("new-root", source_tool=TOOL, source_revision=changed_revision),
            _record("unrelated", source_tool="crm/lookup", source_revision="v1"),
        )
    )
    revocation = graph.revoke_revision(
        tool=TOOL, revision=approved_revision, revocation_id="revision-spike-1"
    )
    survivors = {record.id for record in graph.records()}

    results = {
        "G1_stale_registry_metadata": approved_revision != changed_revision,
        "G2_negative_control_binds_stale_snapshot": baseline_bound,
        "G3_governed_path_blocks_before_dispatch": not dispatched
        and not governed.allows("fetch_page"),
        "G4_revision_descendants_only": set(revocation.removed)
        == {"old-root", "sales", "support", "finance"}
        and survivors == {"new-root", "unrelated"},
        "G5_demo_story_fits_150_seconds": sum(DEMO_BEATS.values()) == 150,
    }
    artifact = {
        "fixtures": {
            "registry_snapshot": "tests/fixtures/registry-approved.json",
            "changed_live_tools_list": "tests/fixtures/registry-changed-live.json",
        },
        "revisions": {"approved": approved_revision, "changed": changed_revision},
        "admission_denials": [asdict(denial) for denial in governed.denied],
        "removed": list(revocation.removed),
        "survivors": sorted(survivors),
        "demo_beats_seconds": DEMO_BEATS,
        "gates": results,
    }
    PROOF.parent.mkdir(exist_ok=True)
    PROOF.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")

    for gate, passed in results.items():
        print(f"{gate}: {'PASS' if passed else 'FAIL'}")
    print(f"proof: {PROOF.relative_to(REPO_ROOT)}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
