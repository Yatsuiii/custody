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
import shutil
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
    DIGEST_ALGORITHM,
    Denial,
    RevisionCatalog,
    RuntimeBinding,
    SurfaceAttestation,
    ToolCallDenied,
    ToolSurface,
)

OUT = REPO_ROOT / "proof-out" / "live-registry-attack.json"
FAILURE = REPO_ROOT / "proof-out" / "live-registry-attack.failure.json"
SERVER_SOURCE = REPO_ROOT / "live" / "registry_attack" / "server"
#: The custody package server.py imports; vendored into the Cloud Build
#: context (this directory, not the repo root) before every build, and
#: removed afterward so the working tree never carries a build artifact.
#: Same vendoring live_revision_binding.py needs, for the same reason: R2
#: made server.py import custody.revision for its own dispatch attestation.
VENDORED_CUSTODY = SERVER_SOURCE / "custody"
VENDORED_FILES = ("__init__.py", "origin.py", "revision.py", "nonce_ledger.py")
SERVICE = "custody-export-mcp"
DISPLAY_NAME = "Custody Export MCP"
DEPARTMENT = "sales"
TOOL_NAME = "lookup_customer"
#: R2 made the owned server refuse any tools/call without a signed token
#: minted from a recent tools/list, unconditionally. Every direct call this
#: producer makes, governed or not, must present one.
ATTESTATION_META_KEY = "custody_attestation"


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


def _vendor_custody() -> None:
    """Copy the pure, dependency-free custody modules server.py imports
    into the Cloud Build context, since that context is this directory, not
    the repo root (see the Dockerfile's own comment on this)."""
    VENDORED_CUSTODY.mkdir(exist_ok=True)
    for name in VENDORED_FILES:
        shutil.copy2(REPO_ROOT / "custody" / name, VENDORED_CUSTODY / name)


def _remove_vendored_custody() -> None:
    shutil.rmtree(VENDORED_CUSTODY, ignore_errors=True)


def _git_revision() -> str:
    """The git SHA of HEAD at capture time, so a later reader can tell a
    stored digest apart from a code-version boundary instead of guessing."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return completed.stdout.strip()


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
    raise RuntimeError(f"Cloud Run did not serve MCP revision {revision}: {last_error}")


async def _tools_list(url: str) -> dict[str, Any]:
    async with Client(url) as client:
        tools = await client.list_tools()
    return {
        "tools": [
            tool.model_dump(mode="json", by_alias=True, exclude_none=True)
            for tool in tools
        ]
    }


async def _fresh_attestation(url: str) -> SurfaceAttestation:
    """Mint a dispatch token for ``TOOL_NAME`` from a ``tools/list`` read
    taken immediately before use. A token minted this close to its call
    always matches the server's live revision, so server-side attestation
    passes trivially regardless of which revision is deployed; only
    Custody's own client-side ``RevisionCatalog.admit`` compares against a
    stale *approved* pin, which is the mechanism this proof demonstrates."""
    async with Client(url) as client:
        tools = await client.list_tools()
    (tool,) = (t for t in tools if t.name == TOOL_NAME)
    raw = (tool.meta or {}).get(ATTESTATION_META_KEY)
    if not isinstance(raw, dict):
        raise RuntimeError(f"server did not attest {TOOL_NAME} in tools/list")
    return SurfaceAttestation(
        tool_id=str(raw["tool_id"]),
        revision=str(raw["revision"]),
        nonce=str(raw["nonce"]),
        issued_at=float(raw["issued_at"]),
        expires_at=float(raw["expires_at"]),
        signature=str(raw["signature"]),
    )


async def _call_tool(
    url: str, arguments: dict[str, str], *, token: SurfaceAttestation
) -> dict[str, Any]:
    async with Client(url) as client:
        result = await client.call_tool(
            TOOL_NAME, arguments, meta={ATTESTATION_META_KEY: asdict(token)}
        )
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


def _deploy(
    cloud: Cloud, *, image: str, revision: str, firestore_project: str | None = None
) -> dict[str, Any]:
    env_vars = f"CUSTODY_MCP_REVISION={revision}"
    if firestore_project:
        env_vars += f",CUSTODY_FIRESTORE_PROJECT={firestore_project}"
    cloud.run(
        "run",
        "deploy",
        SERVICE,
        f"--image={image}",
        f"--region={cloud.region}",
        "--allow-unauthenticated",
        "--max-instances=1",
        f"--set-env-vars={env_vars}",
        "--labels=custody-proof=stale-registry",
    )
    return cloud.json(
        "run",
        "services",
        "describe",
        SERVICE,
        f"--region={cloud.region}",
    )


def _resolved_image_digest(cloud: Cloud, revision_name: str) -> str:
    """The image digest Cloud Run actually pinned this revision to, not the
    build tag that requested it: proves what code is genuinely running,
    which a tag alone cannot (a tag can be repointed after the fact).

    Cloud Run resolves a tag-based ``--image`` to a digest at deploy time
    and records the resolved ``name@sha256:...`` reference directly in the
    revision's own ``spec.containers[0].image`` (Knative Revision schema;
    there is no separate ``status.containerStatuses`` field here, unlike
    the Pod-style status some other Kubernetes-flavored APIs expose).
    """
    revision = cloud.json(
        "run",
        "revisions",
        "describe",
        revision_name,
        f"--region={cloud.region}",
    )
    try:
        image_reference = revision["spec"]["containers"][0]["image"]
    except (KeyError, IndexError) as error:
        raise RuntimeError(
            f"could not read spec.containers[0].image from revision "
            f"{revision_name}: {error}"
        ) from error
    if "@sha256:" not in image_reference:
        raise RuntimeError(
            f"revision {revision_name}'s image {image_reference!r} was not "
            f"resolved to a digest by Cloud Run"
        )
    return image_reference.rsplit("@", 1)[1]


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
    firestore_project = os.environ.get("CUSTODY_FIRESTORE_PROJECT", "").strip() or None
    if firestore_project:
        from google.cloud import firestore

        from custody.firestore_store import FirestoreRevisionCatalog

        catalog = FirestoreRevisionCatalog(firestore.Client(project=firestore_project))
    else:
        catalog = RevisionCatalog()
    image = os.environ.get("CUSTODY_REGISTRY_ATTACK_IMAGE") or (
        f"{region}-docker.pkg.dev/{project}/{repository}/"
        f"custody-export-mcp:{proof_id[:12]}"
    )

    print("[1/8] Enabling Agent Registry and building the MCP image...", flush=True)
    cloud.run("services", "enable", "agentregistry.googleapis.com")
    if os.environ.get("CUSTODY_REGISTRY_ATTACK_IMAGE"):
        print(f"      reusing verified image {image}", flush=True)
    else:
        _vendor_custody()
        try:
            cloud.run(
                "builds",
                "submit",
                str(SERVER_SOURCE),
                f"--tag={image}",
                f"--region={region}",
            )
        finally:
            _remove_vendored_custody()

    print("[2/8] Deploying v1 and reading its real tools/list...", flush=True)
    v1_service = _deploy(
        cloud, image=image, revision="v1", firestore_project=firestore_project
    )
    v1_status = v1_service["status"]
    url = v1_status["url"]
    v1_revision_name = v1_status["latestReadyRevisionName"]
    v1_health = await asyncio.to_thread(_wait_for_revision, url, "v1")
    v1_image_digest = await asyncio.to_thread(
        _resolved_image_digest, cloud, v1_revision_name
    )
    v1_binding = RuntimeBinding(v1_revision_name, v1_image_digest)
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
    projection = await asyncio.to_thread(_wait_for_projection, cloud, registry_resource)
    approved_payload = _registry_content(registry_before)
    approved = ToolSurface.from_tools_list(server=SERVICE, payload=approved_payload)
    catalog.approve(department=DEPARTMENT, surface=approved, runtime_binding=v1_binding)
    admitted_v1 = catalog.admit(
        department=DEPARTMENT, surface=live_v1, observed_runtime=v1_binding
    )
    admitted_v1.require(TOOL_NAME)
    registry_endpoint = registry_before["interfaces"][0]["url"]
    if registry_endpoint != endpoint:
        raise RuntimeError("Agent Registry changed the registered MCP endpoint")
    customer_id = f"cust-{proof_id[:12]}"
    before_v1_call = await asyncio.to_thread(_json_get, f"{url}/evidence")
    v1_token = await _fresh_attestation(registry_endpoint)
    registered_v1_call = await _call_tool(
        registry_endpoint, {"customer_id": customer_id}, token=v1_token
    )
    after_v1_call = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print("[4/8] Deploying v2 to the same URL without updating Registry...", flush=True)
    v2_service = _deploy(
        cloud, image=image, revision="v2", firestore_project=firestore_project
    )
    v2_status = v2_service["status"]
    if v2_status["url"] != url:
        raise RuntimeError("Cloud Run URL changed between revisions")
    v2_revision_name = v2_status["latestReadyRevisionName"]
    v2_health = await asyncio.to_thread(_wait_for_revision, url, "v2")
    v2_image_digest = await asyncio.to_thread(
        _resolved_image_digest, cloud, v2_revision_name
    )
    v2_binding = RuntimeBinding(v2_revision_name, v2_image_digest)
    live_v2_payload = await _tools_list(registry_endpoint)
    live_v2 = ToolSurface.from_tools_list(server=SERVICE, payload=live_v2_payload)

    # A same-schema, different-image swap: the declared surface (live_v1)
    # is unchanged, but the runtime binding observed is v2's. Proves
    # RUNTIME_DRIFT catches the class of drift a surface digest alone
    # cannot see, using real GCP-sourced revision/image data end to end.
    runtime_only_admission = catalog.admit(
        department=DEPARTMENT, surface=live_v1, observed_runtime=v2_binding
    )
    runtime_only_denial = next(
        (
            item
            for item in runtime_only_admission.denied
            if item.tool_id == approved.tools[0].tool_id
        ),
        None,
    )

    print("[5/8] Proving the durable Registry snapshot stayed on v1...", flush=True)
    registry_after = await asyncio.to_thread(_service, cloud)
    if registry_after is None:
        raise RuntimeError("Agent Registry Service disappeared during the proof")

    print("[6/8] Running the ungoverned negative control...", flush=True)
    forward_to = "external-audit@example.invalid"
    before_control = await asyncio.to_thread(_json_get, f"{url}/evidence")
    negative_token = await _fresh_attestation(registry_endpoint)
    negative = await _call_tool(
        registry_endpoint,
        {"customer_id": customer_id, "forward_to": forward_to},
        token=negative_token,
    )
    after_control = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print(
        "[7/8] Applying deterministic Custody admission before dispatch...", flush=True
    )
    governed = catalog.admit(
        department=DEPARTMENT, surface=live_v2, observed_runtime=v2_binding
    )
    governed_blocked = False
    try:
        governed.require(TOOL_NAME)
        governed_token = await _fresh_attestation(registry_endpoint)
        await _call_tool(
            registry_endpoint,
            {"customer_id": customer_id, "forward_to": forward_to},
            token=governed_token,
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
        (item for item in governed.denied if item.tool_id == approved_tool.tool_id),
        None,
    )

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "code_revision": _git_revision(),
        "digest_algorithm": DIGEST_ALGORITHM,
        "project": project,
        "registry_region": region,
        "claim_boundary": (
            "Detects declared MCP tool-surface drift, and now also detects a "
            "same-schema, different-image swap via a Cloud Run revision name "
            "and resolved image digest bound into the approval alongside the "
            "surface digest. It does not cryptographically attest the "
            "running code itself; that remains Binary Authorization "
            "territory. The mismatch path blocks before dispatch, but an "
            "allowed call is not cryptographically atomic with the "
            "preceding surface read."
        ),
        "revision_catalog_backend": "firestore" if firestore_project else "in_memory",
        "cloud_run": {
            "service": SERVICE,
            "url": url,
            "image": image,
            "v1_revision": v1_revision_name,
            "v2_revision": v2_revision_name,
            "v1_image_digest": v1_image_digest,
            "v2_image_digest": v2_image_digest,
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
        "runtime_binding": {
            "approved": {
                "revision_name": v1_binding.revision_name,
                "image_digest": v1_binding.image_digest,
            },
            "observed_on_identical_declared_surface": {
                "revision_name": v2_binding.revision_name,
                "image_digest": v2_binding.image_digest,
            },
            "denied": runtime_only_denial is not None,
            "expected_denial": Denial.RUNTIME_DRIFT.value,
            "selected_denial": (
                asdict(runtime_only_denial) if runtime_only_denial else None
            ),
        },
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
