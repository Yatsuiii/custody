"""Prove the real Provenance Auditor: a demotion recorded now and a
revocation applied later, asynchronously, on the deployed Cloud Scheduler
auditor's own clock, against the live control plane.

Closes the fleet-review finding that `/auditor` was a heartbeat pretending
to be a trust-re-examination agent: `/vouch` grants, the new `/demote`
withdraws, and `/auditor`'s sweep is the only thing that ever calls
`CustodyGraph.revoke` on a demotion's behalf, on the Scheduler's schedule,
not the demoter's request.

    make live-auditor
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.catalog import Demotion  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-auditor.json"
FAILURE = REPO_ROOT / "proof-out" / "live-auditor.failure.json"

CLAIM_BOUNDARY = (
    "Proves /demote and /auditor's sweep are genuinely decoupled against "
    "the live, Firestore-backed control plane: a demotion is recorded and "
    "durable, but the graph is unchanged until the next /auditor tick "
    "revokes it, deterministically, no model involved. Does not itself "
    "prove cross-cold-start durability of the demotion log beyond what one "
    "process's HTTP calls can show; that mechanism (create-fails-if-exists, "
    "replay-on-construction) is covered offline in "
    "tests/test_firestore_store.py::FirestoreDemotionLogTests, the same "
    "split G5 already uses between its live seed-record proof and its "
    "offline Firestore replay tests."
)


def _service_url(*, project: str, region: str, service: str) -> str:
    command = [
        "gcloud",
        "run",
        "services",
        "describe",
        service,
        f"--project={project}",
        f"--region={region}",
        "--format=json",
    ]
    described = json.loads(
        subprocess.run(command, check=True, capture_output=True, text=True).stdout
    )
    return described["status"]["url"]


def _json_request(url: str, payload: dict | None = None, *, method: str | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method or ("POST" if body is not None else "GET"),
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def _prove() -> dict[str, object]:
    proof_id = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT")
    region = os.environ.get("CUSTODY_REGION", "us-central1")
    service = os.environ.get("CUSTODY_CONTROL_PLANE_SERVICE", "custody-control-plane")
    if not project:
        raise SystemExit("CUSTODY_PROJECT is required")

    url = _service_url(project=project, region=region, service=service)

    department = f"auditor-probe-{proof_id[:12]}"
    tool = f"auditor_probe_tool_{proof_id[:8]}"
    invocation_id = f"auditor-probe-{proof_id[:12]}"
    record_id = f"{invocation_id}:0:0"

    vouch = _json_request(
        f"{url}/vouch",
        {
            "actor_department": department,
            "department": department,
            "tool": tool,
            "vouched_by": "auditor-proof",
            "vouched_at": datetime.now(UTC).isoformat(),
        },
    )
    if not vouch["allowed"]:
        raise RuntimeError(f"vouch was refused: {vouch}")

    run = _json_request(
        f"{url}/sessions",
        {
            "department": department,
            "app_name": "custody-auditor-probe",
            "session_id": invocation_id,
            "events": [
                {
                    "author": "assistant",
                    "invocation_id": invocation_id,
                    "parts": [
                        {
                            "tool": tool,
                            "response": f"auditor probe fact {proof_id[:8]}",
                        }
                    ],
                }
            ],
        },
    )
    if run["admitted"] != 1:
        raise RuntimeError(f"expected one admitted record, got: {run}")

    before_demotion = _json_request(f"{url}/custody/{record_id}")
    if before_demotion is None or before_demotion.get("revocation_id") is not None:
        raise RuntimeError(f"record not in expected pre-demotion state: {before_demotion}")

    demoted_at = datetime.now(UTC).isoformat()
    demote = _json_request(
        f"{url}/demote",
        {
            "actor_department": department,
            "department": department,
            "tool": tool,
            "demoted_by": "auditor-proof",
            "demoted_at": demoted_at,
        },
    )
    if not demote["allowed"]:
        raise RuntimeError(f"demote was refused: {demote}")

    expected_revocation_id = Demotion(
        actor_department=department,
        department=department,
        tool=tool,
        demoted_by="auditor-proof",
        demoted_at=demoted_at,
    ).id()

    after_demotion_before_sweep = _json_request(f"{url}/custody/{record_id}")
    if (
        after_demotion_before_sweep is None
        or after_demotion_before_sweep.get("revocation_id") is not None
    ):
        raise RuntimeError(
            "demotion took effect before the Auditor swept it: "
            f"{after_demotion_before_sweep}"
        )

    sweep = _json_request(f"{url}/auditor", {})
    if expected_revocation_id not in sweep["swept_revocations"]:
        raise RuntimeError(
            f"expected revocation id {expected_revocation_id} not in sweep: {sweep}"
        )

    after_sweep = _json_request(f"{url}/custody/{record_id}")
    if (
        after_sweep is None
        or after_sweep.get("revocation_id") != expected_revocation_id
        or after_sweep.get("revoked_at") is None
    ):
        raise RuntimeError(
            "record should carry the swept revocation after the Auditor "
            f"tick, durable-store discipline: {after_sweep}"
        )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "claim_boundary": CLAIM_BOUNDARY,
        "service_url": url,
        "department": department,
        "tool": tool,
        "record_id": record_id,
        "vouch": vouch,
        "run": run,
        "before_demotion": before_demotion,
        "demote": demote,
        "demoted_at": demoted_at,
        "expected_revocation_id": expected_revocation_id,
        "after_demotion_before_sweep": after_demotion_before_sweep,
        "sweep": sweep,
        "after_sweep": after_sweep,
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    try:
        evidence = _prove()
    except Exception as error:
        FAILURE.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now(UTC).isoformat(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"live auditor proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live auditor evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
