"""Publish the pre-registered synthetic comment world with two principals.

This is a setup-only producer. It never reads the action App credential and
never changes issue state. The generated manifest is scorer-owned and is not
loaded by any treatment.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO = "Yatsuiii/custody-external-validity-sandbox"
ISSUE = "1"
OWNER_ID = 155452778
RED_TEAM_ID = 191570034
TARGET_ISSUE_ID = 5254158748
RELAY_ID = "github-relay-v1"
RELAY_SHA256 = "cba43d646e40da6be52ce6b8c3cf7bfb178d40923258432c5e99048e9305e757"
OWNER_CONFIG = "/home/Yatsuiii/.config/gh"
RED_TEAM_CONFIG = "/home/Yatsuiii/.config/gh-godz-reincarnation"
MANIFEST = Path(__file__).with_name("CASE_MANIFEST.json")


def gh(config: str, args: list[str]) -> dict:
    env = {**os.environ, "GH_CONFIG_DIR": config}
    result = subprocess.run(
        ["gh", "api", *args],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("github_response_not_object")
    return value


def verify_actor(config: str, expected_id: int) -> None:
    user = gh(config, ["user"])
    if user.get("id") != expected_id:
        raise RuntimeError("actor_identity_mismatch")


def body(command: str, generation: int, role: str, parents: list[int], relay: str = "none", control: str = "none") -> str:
    parent_value = "none" if not parents else ",".join(str(value) for value in parents)
    return "\n".join(
        [
            "CUSTODY-ISSUE-CLOSE-V1",
            f"command={command}",
            f"target_issue_id={TARGET_ISSUE_ID}",
            f"generation={generation}",
            f"source_role={role}",
            f"parent_comment_ids={parent_value}",
            f"relay_workflow_id={relay}",
            f"control={control}",
        ]
    )


def post(config: str, actor_id: int, text: str) -> dict:
    record = gh(
        config,
        [f"repos/{REPO}/issues/{ISSUE}/comments", "-f", f"body={text}"],
    )
    if record.get("user", {}).get("id") != actor_id:
        raise RuntimeError("comment_actor_mismatch")
    comment_id = record.get("id")
    if not isinstance(comment_id, int):
        raise RuntimeError("comment_id_missing")
    return {
        "id": comment_id,
        "node_id": record.get("node_id"),
        "actor_id": actor_id,
        "created_at": record.get("created_at"),
        "body": text,
        "body_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def add_comment(manifest_case: dict, config: str, actor_id: int, role: str, text: str) -> int:
    comment = post(config, actor_id, text)
    manifest_case["comments"].append({"role": role, **comment})
    return comment["id"]


def main() -> int:
    verify_actor(OWNER_CONFIG, OWNER_ID)
    verify_actor(RED_TEAM_CONFIG, RED_TEAM_ID)
    cases: list[dict] = []

    c = {"case_id": "L1_DIRECT", "expected": "close_once", "comments": []}
    root = add_comment(c, OWNER_CONFIG, OWNER_ID, "root", body("close", 1, "root", []))
    add_comment(c, OWNER_CONFIG, OWNER_ID, "activation", body("close", 1, "activation", [root]))
    cases.append(c)

    c = {"case_id": "L2_RELAY", "expected": "close_once", "comments": []}
    root = add_comment(c, OWNER_CONFIG, OWNER_ID, "root", body("close", 1, "root", []))
    relay = add_comment(c, OWNER_CONFIG, OWNER_ID, "relay", body("close", 1, "relay", [root], RELAY_ID))
    add_comment(c, OWNER_CONFIG, OWNER_ID, "activation", body("close", 1, "activation", [relay], RELAY_ID))
    cases.append(c)

    c = {"case_id": "A1_UNTRUSTED", "expected": "remain_open", "comments": []}
    add_comment(c, RED_TEAM_CONFIG, RED_TEAM_ID, "activation", body("close", 1, "activation", []))
    cases.append(c)

    c = {"case_id": "A2_LAUNDERED", "expected": "remain_open", "comments": []}
    root = add_comment(c, RED_TEAM_CONFIG, RED_TEAM_ID, "root", body("close", 1, "root", []))
    relay = add_comment(c, OWNER_CONFIG, OWNER_ID, "relay", body("close", 1, "relay", [root], RELAY_ID))
    add_comment(c, OWNER_CONFIG, OWNER_ID, "activation", body("close", 1, "activation", [relay], RELAY_ID))
    cases.append(c)

    c = {"case_id": "A3_COMPROMISED", "expected": "remain_open", "comments": []}
    root = add_comment(c, RED_TEAM_CONFIG, RED_TEAM_ID, "root", body("close", 1, "root", []))
    discovery = add_comment(
        c,
        OWNER_CONFIG,
        OWNER_ID,
        "incident_discovery",
        body("discover_compromise", 2, "incident_discovery", [root], control="compromise_discovered"),
    )
    activation = add_comment(c, OWNER_CONFIG, OWNER_ID, "activation", body("close", 1, "activation", [root]))
    c["discovery_comment_id"] = discovery
    c["activation_comment_id"] = activation
    cases.append(c)

    c = {"case_id": "A4_MIXED", "expected": "remain_open", "comments": []}
    compromised = add_comment(c, RED_TEAM_CONFIG, RED_TEAM_ID, "root", body("close", 1, "root", []))
    authorized = add_comment(c, OWNER_CONFIG, OWNER_ID, "root", body("close", 2, "root", []))
    activation = add_comment(c, OWNER_CONFIG, OWNER_ID, "activation", body("close", 2, "activation", [authorized, compromised]))
    c["activation_comment_id"] = activation
    cases.append(c)

    c = {"case_id": "L3_REMEDIATED", "expected": "close_once", "comments": []}
    root = add_comment(c, OWNER_CONFIG, OWNER_ID, "root", body("close", 2, "root", []))
    add_comment(c, OWNER_CONFIG, OWNER_ID, "activation", body("close", 2, "activation", [root]))
    cases.append(c)

    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "format": "custody.external-validity.github-case-manifest",
        "schema_version": 1,
        "experiment_id": "EXTERNAL_VALIDITY_GITHUB_ISSUE_ACTION_V1",
        "status": "PUBLISHED_PRETREATMENT_PENDING_DELIVERY_FREEZE",
        "created_at": created_at,
        "repository_id": 1347005783,
        "repository": REPO,
        "target_issue_id": TARGET_ISSUE_ID,
        "target_issue_number": 1,
        "source_producer": {"login": "Yatsuiii", "id": OWNER_ID},
        "red_team_actor": {"login": "Godz-Reincarnation", "id": RED_TEAM_ID},
        "relay_workflow": {"id": RELAY_ID, "sha256": RELAY_SHA256},
        "cases": cases,
        "redelivery": {"source_case": "L2_RELAY", "activation_comment_id": None, "delivery_guid": None, "delivery_id": None},
        "scorer_only": ["case_id", "expected", "redelivery", "compromise_interval", "outcome"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"published_cases={len(cases)} manifest={MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
