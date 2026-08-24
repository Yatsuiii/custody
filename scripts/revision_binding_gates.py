"""Judge the live R2 revision-binding artifact independently of its producer.

Two tiers, same discipline as every other live gate here: an offline judge
first rejects a structurally inconsistent or fabricated claim, then an
independent live reread confirms the two denial log entries the producer
claims actually exist in Cloud Logging, by their own server-issued insert
ID, and that both Cloud Run revisions it names were really deployed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUT = REPO_ROOT / "proof-out" / "live-revision-binding.json"
CONFIG = REPO_ROOT / ".gcloud"


def judge(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    if captured.tzinfo is None or captured > current + timedelta(minutes=5):
        return {"fresh_live_evidence": False}

    cloud = evidence["cloud_run"]
    v1_token = evidence["v1_token"]
    v2_token = evidence["v2_token"]
    positive = evidence["positive_control"]
    replay = evidence["replay_control"]
    mismatch = evidence["digest_mismatch_control"]
    v2_positive = evidence["v2_positive_control"]

    return {
        "fresh_live_evidence": current - captured <= timedelta(hours=24),
        "same_url_two_cloud_run_revisions": (
            cloud["v1_revision"] != cloud["v2_revision"]
            and bool(cloud["v1_revision"])
            and bool(cloud["v2_revision"])
        ),
        "v1_and_v2_tokens_have_different_revisions": (
            v1_token["revision"] != v2_token["revision"]
            and v1_token["nonce"] != v2_token["nonce"]
        ),
        "positive_control_dispatched_once": (
            positive["result"]["is_error"] is False
            and positive["dispatch_count_after"]
            == positive["dispatch_count_before"] + 1
        ),
        "replay_was_refused_without_a_second_dispatch": (
            replay["denied"] is True
            and replay["dispatch_count_after"] == replay["dispatch_count_before"]
            and replay["denial_log"]["jsonPayload"]["reason"] == "replayed"
            and replay["denial_log"]["jsonPayload"]["revision"] == "v1"
        ),
        "stale_revision_token_was_refused_on_v2_with_no_dispatch": (
            mismatch["denied"] is True
            and mismatch["dispatch_count_after"] == mismatch["dispatch_count_before"]
            and mismatch["dispatch_count_before"] == 0
            and mismatch["instance_id_before"] == mismatch["instance_id_after"]
            and mismatch["denial_log"]["jsonPayload"]["reason"] == "digest_mismatch"
            and mismatch["denial_log"]["jsonPayload"]["revision"] == "v2"
        ),
        "denial_logs_are_bound_to_the_stale_token_nonce": (
            replay["denial_log"]["jsonPayload"].get("tool_name") == "lookup_customer"
            and mismatch["denial_log"]["jsonPayload"].get("tool_name")
            == "lookup_customer"
        ),
        "fresh_v2_token_dispatched_normally": (
            v2_positive["result"]["is_error"] is False
            and v2_positive["dispatch_count_after"]
            == v2_positive["dispatch_count_before"] + 1
        ),
        "claim_boundary_states_the_behavior_only_gap": (
            "behavior-only" in evidence.get("claim_boundary", "")
        ),
        "replay_survives_process_restart": _replay_survives_process_restart(
            evidence, cloud=cloud
        ),
    }


def _replay_survives_process_restart(evidence: dict, *, cloud: dict) -> bool:
    """The durable-ledger proof: old evidence captured before this control
    existed fails this gate rather than crashing the judge, same discipline
    as ``registry_gates.py``'s ``runtime_binding_also_blocked``. A run with
    ``nonce_ledger_backend`` still ``in_memory`` genuinely should fail this
    too — that is the pre-fix state, not a malformed artifact."""
    restart = evidence.get("restart_replay_control")
    restart_revision = cloud.get("v1_restart_revision")
    if not restart or not restart_revision:
        return False
    return bool(
        evidence.get("nonce_ledger_backend") == "firestore"
        and restart_revision != cloud.get("v1_revision")
        and restart["denied"] is True
        and restart["dispatch_count_after"] == restart["dispatch_count_before"]
        and restart["instance_id_before"] == restart["instance_id_after"]
        and restart["denial_log"]["jsonPayload"]["reason"] == "replayed"
        and restart["denial_log"]["jsonPayload"]["revision"] == "v1"
        and restart["denial_log"]["jsonPayload"].get("tool_name") == "lookup_customer"
    )


def _gcloud_json(*arguments: str) -> Any:
    environment = os.environ.copy()
    environment["CLOUDSDK_CONFIG"] = str(CONFIG)
    environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    completed = subprocess.run(
        ["gcloud", *arguments, "--quiet", "--format=json"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )
    return json.loads(completed.stdout)


def live_reread(evidence: dict) -> dict[str, bool]:
    """Independently confirm the producer's claimed log entries and Cloud
    Run revisions still exist, by their own server-issued identifiers,
    rather than trusting the producer's narration of them."""
    project = evidence["project"]
    cloud = evidence["cloud_run"]
    results: dict[str, bool] = {}

    controls = [
        ("replay", evidence["replay_control"]),
        ("digest_mismatch", evidence["digest_mismatch_control"]),
    ]
    if evidence.get("restart_replay_control"):
        controls.append(("restart_replay", evidence["restart_replay_control"]))

    for label, control in controls:
        insert_id = control["denial_log"].get("insertId")
        query = " AND ".join(
            (
                f'logName="projects/{project}/logs/run.googleapis.com%2Fstdout"',
                f'resource.labels.service_name="{cloud["service"]}"',
                f'insertId="{insert_id}"',
            )
        )
        try:
            reread = _gcloud_json(
                "logging", "read", query, "--project", project, "--limit=1"
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ):
            reread = []
        results[f"{label}_denial_log_rereads_live"] = (
            isinstance(reread, list)
            and len(reread) == 1
            and reread[0].get("jsonPayload") == control["denial_log"].get("jsonPayload")
        )

    revisions = [
        ("v1", cloud["v1_revision"]),
        ("v2", cloud["v2_revision"]),
    ]
    if cloud.get("v1_restart_revision"):
        revisions.append(("v1_restart", cloud["v1_restart_revision"]))

    for label, revision_name in revisions:
        try:
            described = _gcloud_json(
                "run",
                "revisions",
                "describe",
                revision_name,
                f"--region={os.environ.get('CUSTODY_REGISTRY_REGION', 'us-central1')}",
                "--project",
                project,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ):
            described = {}
        results[f"{label}_revision_exists_live"] = (
            described.get("metadata", {}).get("name") == revision_name
        )

    return results


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-revision-binding.json")
        print("          run make live-revision-binding")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live revision-binding evidence: {error}")
        return 1

    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")

    if not gates or not all(gates.values()):
        return 1

    for name, passed in live_reread(evidence).items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
        gates[name] = passed

    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
