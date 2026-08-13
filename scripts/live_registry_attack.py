"""Run the live stale-Agent-Registry attack and write falsifiable evidence.

The proof deliberately uses one Cloud Run URL for two revisions. Version 1 is
registered from its real MCP ``tools/list`` response. Version 2 mutates that
same tool while the Registry Service remains untouched. The negative control
calls the changed tool; Custody compares the durable Registry snapshot with
the live surface and refuses the same call before dispatch.

    make live-registry-attack
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastmcp import Client  # noqa: E402

from custody.graph import CustodyGraph  # noqa: E402
from custody.origin import CustodyRecord, Origin, Trust, digest  # noqa: E402
from custody.revision import (  # noqa: E402
    Denial,
    RevisionCatalog,
    ToolCallDenied,
    ToolSurface,
)

OUT = REPO_ROOT / "proof-out" / "live-registry-attack.json"
FAILURE = REPO_ROOT / "proof-out" / "live-registry-attack.failure.json"
SERVER_SOURCE = REPO_ROOT / "live" / "registry_attack" / "server"
SERVICE = "custody-export-mcp"
DISPLAY_NAME = "Custody Export MCP"
DEPARTMENT = "sales"
TOOL_NAME = "lookup_customer"


@dataclass(frozen=True)
class Cloud:
    """The proof's cloud boundary, including its isolated gcloud state."""

    project: str
    region: str
    repository: str
    config: Path

    def run(self, *arguments: str, capture: bool = False) -> str:
        environment = os.environ.copy()
        environment["CLOUDSDK_CONFIG"] = str(self.config)
        environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
        completed = subprocess.run(
            ["gcloud", *arguments, f"--project={self.project}", "--quiet"],
            check=True,
            capture_output=capture,
            text=True,
            env=environment,
        )
        return completed.stdout

    def json(self, *arguments: str) -> dict[str, Any]:
        return json.loads(self.run(*arguments, "--format=json", capture=True))


def _configured_project(config: Path) -> str:
    environment = os.environ.copy()
    environment["CLOUDSDK_CONFIG"] = str(config)
    completed = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    project = completed.stdout.strip()
    if not project or project == "(unset)":
        raise RuntimeError("CUSTODY_PROJECT or a repo-local gcloud project is required")
    return project


def _json_get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def _wait_for_revision(url: str, revision: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            health = _json_get(f"{url}/health")
            if health.get("revision") == revision:
                return health
        except (OSError, ValueError, urllib.error.HTTPError) as error:
            last_error = error
        time.sleep(2)
    raise RuntimeError(
        f"Cloud Run did not serve MCP revision {revision}: {last_error}"
    )


async def _tools_list(url: str) -> dict[str, Any]:
    async with Client(url) as client:
        tools = await client.list_tools()
    return {
        "tools": [
            tool.model_dump(mode="json", by_alias=True, exclude_none=True)
            for tool in tools
        ]
    }


async def _call_tool(url: str, arguments: dict[str, str]) -> dict[str, Any]:
    async with Client(url) as client:
        result = await client.call_tool(TOOL_NAME, arguments)
    dumped = {
        "content": [
            item.model_dump(mode="json", by_alias=True, exclude_none=True)
            for item in result.content
        ],
        "structured_content": result.structured_content,
        "data": result.data,
        "meta": result.meta,
        "is_error": result.is_error,
    }
    text = next(
        (
            item.get("text")
            for item in dumped.get("content", [])
            if item.get("type") == "text"
        ),
        None,
    )
    try:
        parsed = json.loads(text) if text else None
    except json.JSONDecodeError:
        parsed = text
    return {"protocol_result": dumped, "value": parsed}


def _service(cloud: Cloud) -> dict[str, Any] | None:
    try:
        return cloud.json(
            "agent-registry",
            "services",
            "describe",
            SERVICE,
            f"--location={cloud.region}",
        )
    except subprocess.CalledProcessError as error:
        if "NOT_FOUND" not in (error.stderr or ""):
            raise
        return None


def _register_v1(
    cloud: Cloud, *, endpoint: str, tools: dict[str, Any], proof_id: str
) -> dict[str, Any]:
    spec = OUT.parent / f"registry-toolspec-v1-{proof_id}.json"
    spec.write_text(json.dumps(tools, indent=2, sort_keys=True) + "\n")
    common = (
        SERVICE,
        f"--location={cloud.region}",
        f"--display-name={DISPLAY_NAME}",
        "--description=Live stale-metadata proof for Custody",
        "--mcp-server-spec-type=tool-spec",
        f"--mcp-server-spec-content={spec}",
        f"--interfaces=url={endpoint},protocolBinding=jsonrpc",
    )
    if _service(cloud) is None:
        cloud.run("agent-registry", "services", "create", *common)
    else:
        cloud.run("agent-registry", "services", "update", *common)
    return cloud.json(
        "agent-registry",
        "services",
        "describe",
        SERVICE,
        f"--location={cloud.region}",
    )


def _registry_content(service: dict[str, Any]) -> dict[str, Any]:
    content = service["mcpServerSpec"]["content"]
    return json.loads(content) if isinstance(content, str) else content


def _wait_for_projection(cloud: Cloud, registry_resource: str) -> dict[str, Any]:
    identifier = registry_resource.rsplit("/", 1)[-1]
    last_error: Exception | None = None
    for _ in range(20):
        try:
            return cloud.json(
                "agent-registry",
                "mcp-servers",
                "describe",
                identifier,
                f"--location={cloud.region}",
            )
        except subprocess.CalledProcessError as error:
            last_error = error
        time.sleep(3)
    raise RuntimeError(f"Registry MCP projection was not readable: {last_error}")


def _deploy(cloud: Cloud, *, image: str, revision: str) -> dict[str, Any]:
    cloud.run(
        "run",
        "deploy",
        SERVICE,
        f"--image={image}",
        f"--region={cloud.region}",
        "--allow-unauthenticated",
        "--max-instances=1",
        f"--set-env-vars=CUSTODY_MCP_REVISION={revision}",
        "--labels=custody-proof=stale-registry",
    )
    return cloud.json(
        "run",
        "services",
        "describe",
        SERVICE,
        f"--region={cloud.region}",
    )


def _record(
    proof_id: str,
    name: str,
    *,
    source_tool: str | None = None,
    source_revision: str | None = None,
    derived_from: tuple[str, ...] = (),
    live_value: object | None = None,
) -> CustodyRecord:
    record_id = f"{proof_id}:{name}"
    evidence_text = (
        record_id
        if live_value is None
        else json.dumps(
            live_value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
    )
    return CustodyRecord(
        origin=Origin.TOOL if source_tool else Origin.MODEL,
        trust=Trust.TRUSTED,
        author="assistant",
        invocation_id=f"live-registry-{name}",
        content_sha256=digest(evidence_text),
        source_tool=source_tool,
        source_revision=source_revision,
        id=record_id,
        derived_from=tuple(f"{proof_id}:{parent}" for parent in derived_from),
    )


def _revision_revocation(
    *,
    proof_id: str,
    tool_id: str,
    approved_revision: str,
    observed_revision: str,
    live_v1_value: object,
    live_v2_value: object,
) -> dict[str, Any]:
    graph = CustodyGraph()
    v1_root = _record(
        proof_id,
        "v1-root",
        source_tool=tool_id,
        source_revision=approved_revision,
        live_value=live_v1_value,
    )
    v2_root = _record(
        proof_id,
        "v2-root",
        source_tool=tool_id,
        source_revision=observed_revision,
        live_value=live_v2_value,
    )
    graph.extend(
        (
            v1_root,
            _record(proof_id, "sales", derived_from=("v1-root",)),
            _record(proof_id, "support", derived_from=("sales",)),
            _record(proof_id, "finance", derived_from=("support",)),
            v2_root,
            _record(proof_id, "v2-child", derived_from=("v2-root",)),
            _record(
                proof_id,
                "unrelated",
                source_tool="crm/lookup",
                source_revision="crm-v1",
            ),
        )
    )
    revoked = graph.revoke_revision(
        tool=tool_id,
        revision=approved_revision,
        revocation_id=f"live-registry-{proof_id}",
    )
    records = {record.id: record for record in graph.records()}
    v1_text = json.dumps(
        live_v1_value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    surviving_v2_root = records[f"{proof_id}:v2-root"]
    return {
        "source": "live MCP call results and Registry revision digests",
        "live_memory_bank_deletion": False,
        "revoked_revision": approved_revision,
        "removed": list(revoked.removed),
        "survivors": sorted(record.id for record in graph.records()),
        "root_bindings": {
            "v1": {
                "origin": v1_root.origin.value,
                "tool_id": tool_id,
                "source_revision": approved_revision,
                "content_sha256": digest(v1_text),
            },
            "v2": {
                "origin": surviving_v2_root.origin.value,
                "tool_id": surviving_v2_root.source_tool,
                "source_revision": surviving_v2_root.source_revision,
                "content_sha256": surviving_v2_root.content_sha256,
            },
        },
    }


async def _prove() -> dict[str, Any]:
    proof_id = uuid.uuid4().hex
    config = Path(os.environ.get("CLOUDSDK_CONFIG", REPO_ROOT / ".gcloud"))
    project = os.environ.get("CUSTODY_PROJECT") or _configured_project(config)
    region = os.environ.get("CUSTODY_REGISTRY_REGION", "us-central1")
    repository = os.environ.get("CUSTODY_ARTIFACT_REPOSITORY", "custody")
    cloud = Cloud(project, region, repository, config)
    image = os.environ.get("CUSTODY_REGISTRY_ATTACK_IMAGE") or (
        f"{region}-docker.pkg.dev/{project}/{repository}/"
        f"custody-export-mcp:{proof_id[:12]}"
    )

    print("[1/8] Enabling Agent Registry and building the MCP image...", flush=True)
    cloud.run("services", "enable", "agentregistry.googleapis.com")
    if os.environ.get("CUSTODY_REGISTRY_ATTACK_IMAGE"):
        print(f"      reusing verified image {image}", flush=True)
    else:
        cloud.run(
            "builds",
            "submit",
            str(SERVER_SOURCE),
            f"--tag={image}",
            f"--region={region}",
        )

    print("[2/8] Deploying v1 and reading its real tools/list...", flush=True)
    v1_service = _deploy(cloud, image=image, revision="v1")
    v1_status = v1_service["status"]
    url = v1_status["url"]
    v1_revision_name = v1_status["latestReadyRevisionName"]
    v1_health = await asyncio.to_thread(_wait_for_revision, url, "v1")
    endpoint = f"{url}/mcp"
    live_v1_payload = await _tools_list(endpoint)
    live_v1 = ToolSurface.from_tools_list(server=SERVICE, payload=live_v1_payload)

    print("[3/8] Registering the exact v1 snapshot in Agent Registry...", flush=True)
    registry_before = await asyncio.to_thread(
        _register_v1,
        cloud,
        endpoint=endpoint,
        tools=live_v1_payload,
        proof_id=proof_id,
    )
    registry_resource = registry_before["registryResource"]
    projection = await asyncio.to_thread(
        _wait_for_projection, cloud, registry_resource
    )
    approved_payload = _registry_content(registry_before)
    approved = ToolSurface.from_tools_list(server=SERVICE, payload=approved_payload)
    catalog = RevisionCatalog()
    catalog.approve(department=DEPARTMENT, surface=approved)
    admitted_v1 = catalog.admit(department=DEPARTMENT, surface=live_v1)
    admitted_v1.require(TOOL_NAME)
    registry_endpoint = registry_before["interfaces"][0]["url"]
    if registry_endpoint != endpoint:
        raise RuntimeError("Agent Registry changed the registered MCP endpoint")
    customer_id = f"cust-{proof_id[:12]}"
    before_v1_call = await asyncio.to_thread(_json_get, f"{url}/evidence")
    registered_v1_call = await _call_tool(
        registry_endpoint, {"customer_id": customer_id}
    )
    after_v1_call = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print("[4/8] Deploying v2 to the same URL without updating Registry...", flush=True)
    v2_service = _deploy(cloud, image=image, revision="v2")
    v2_status = v2_service["status"]
    if v2_status["url"] != url:
        raise RuntimeError("Cloud Run URL changed between revisions")
    v2_revision_name = v2_status["latestReadyRevisionName"]
    v2_health = await asyncio.to_thread(_wait_for_revision, url, "v2")
    live_v2_payload = await _tools_list(registry_endpoint)
    live_v2 = ToolSurface.from_tools_list(server=SERVICE, payload=live_v2_payload)

    print("[5/8] Proving the durable Registry snapshot stayed on v1...", flush=True)
    registry_after = await asyncio.to_thread(_service, cloud)
    if registry_after is None:
        raise RuntimeError("Agent Registry Service disappeared during the proof")

    print("[6/8] Running the ungoverned negative control...", flush=True)
    forward_to = "external-audit@example.invalid"
    before_control = await asyncio.to_thread(_json_get, f"{url}/evidence")
    negative = await _call_tool(
        registry_endpoint,
        {"customer_id": customer_id, "forward_to": forward_to},
    )
    after_control = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print("[7/8] Applying deterministic Custody admission before dispatch...", flush=True)
    governed = catalog.admit(department=DEPARTMENT, surface=live_v2)
    governed_blocked = False
    try:
        governed.require(TOOL_NAME)
        await _call_tool(
            registry_endpoint,
            {"customer_id": customer_id, "forward_to": forward_to},
        )
    except ToolCallDenied:
        governed_blocked = True
    after_governed = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print("[8/8] Revoking only v1 descendants in CustodyGraph...", flush=True)
    approved_tool = approved.tools[0]
    observed_tool = live_v2.tools[0]
    revocation = _revision_revocation(
        proof_id=proof_id,
        tool_id=approved_tool.tool_id,
        approved_revision=approved_tool.revision,
        observed_revision=observed_tool.revision,
        live_v1_value=registered_v1_call["value"],
        live_v2_value=negative["value"],
    )
    denial = next(
        (
            item
            for item in governed.denied
            if item.tool_id == approved_tool.tool_id
        ),
        None,
    )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "project": project,
        "registry_region": region,
        "claim_boundary": (
            "Detects declared MCP tool-surface drift. It does not detect a "
            "behavior-only change whose tools/list definition is identical. "
            "The mismatch path blocks before dispatch, but an allowed call is "
            "not cryptographically atomic with the preceding surface read."
        ),
        "cloud_run": {
            "service": SERVICE,
            "url": url,
            "image": image,
            "v1_revision": v1_revision_name,
            "v2_revision": v2_revision_name,
            "same_url": v2_status["url"] == url,
            "v1_health": v1_health,
            "v2_health": v2_health,
        },
        "registry": {
            "service": registry_before["name"],
            "registry_resource": registry_resource,
            "projected_mcp_server": projection,
            "endpoint": registry_before["interfaces"][0]["url"],
            "update_time_before_v2": registry_before["updateTime"],
            "update_time_after_v2": registry_after["updateTime"],
            "content_before_v2": approved_payload,
            "content_after_v2": _registry_content(registry_after),
        },
        "surfaces": {
            "live_v1": live_v1_payload,
            "live_v2": live_v2_payload,
            "approved_revision": approved_tool.revision,
            "observed_revision": observed_tool.revision,
            "v1_admitted": admitted_v1.allows(TOOL_NAME),
        },
        "registered_v1_control": {
            "registry_endpoint_used": registry_endpoint,
            "arguments": {"customer_id": customer_id},
            "result": registered_v1_call,
            "dispatch_count_before": before_v1_call["dispatch_count"],
            "dispatch_count_after": after_v1_call["dispatch_count"],
            "instance_id_before": before_v1_call["instance_id"],
            "instance_id_after": after_v1_call["instance_id"],
        },
        "negative_control": {
            "registry_endpoint_used": registry_endpoint,
            "arguments": {"customer_id": customer_id, "forward_to": forward_to},
            "result": negative,
            "dispatch_count_before": before_control["dispatch_count"],
            "dispatch_count_after": after_control["dispatch_count"],
            "instance_id_before": before_control["instance_id"],
            "instance_id_after": after_control["instance_id"],
            "forwarding_dispatch_count_before": before_control[
                "forwarding_dispatch_count"
            ],
            "forwarding_dispatch_count_after": after_control[
                "forwarding_dispatch_count"
            ],
        },
        "governed": {
            "blocked": governed_blocked,
            "denials": [asdict(item) for item in governed.denied],
            "expected_denial": Denial.REVISION_MISMATCH.value,
            "selected_denial": asdict(denial) if denial else None,
            "dispatch_count_before": after_control["dispatch_count"],
            "dispatch_count_after": after_governed["dispatch_count"],
            "instance_id_before": after_control["instance_id"],
            "instance_id_after": after_governed["instance_id"],
            "forwarding_dispatch_count_before": after_control[
                "forwarding_dispatch_count"
            ],
            "forwarding_dispatch_count_after": after_governed[
                "forwarding_dispatch_count"
            ],
        },
        "revocation": revocation,
    }


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    try:
        evidence = asyncio.run(_prove())
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
        print(f"live Registry attack failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live Registry evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
