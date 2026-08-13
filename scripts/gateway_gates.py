"""Independently judge the live Agent Gateway enforcement artifact.

The producer is intentionally untrusted.  This module derives every verdict
from raw Google Cloud resource descriptions, IAM policies, control results,
the owned MCP server's process-local ledger, and Cloud Logging entries.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "proof-out" / "live-gateway.json"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.gateway_live_attestation import attest_live  # noqa: E402

GATEWAY_ID = "custody-fleet-egress"
EXTENSION_ID = "custody-fleet-iap-enforced"
AUTHZ_POLICY_ID = "custody-fleet-request-authz"
MCP_SERVICE_ID = "custody-export-mcp"
TOOL_NAME = "lookup_customer"
RUNTIME_IDENTITY = "agentregistry.googleapis.com/system/RuntimeIdentity"
RUNTIME_REFERENCE = "agentregistry.googleapis.com/system/RuntimeReference"
CLAIM_BOUNDARY = (
    "Proves IAP REQUEST_AUTHZ enforcement for one owned Agent Runtime identity "
    "calling one registered MCP server through one Agent Gateway. It does not "
    "prove all egress is covered, repair stale Registry metadata, or remove "
    "Custody's allowed-call TOCTOU boundary."
)

_HEX_ID = re.compile(r"[0-9a-f]{32}")
_MCP_RESOURCE = re.compile(
    r"projects/(?P<owner>[^/]+)/locations/(?P<region>[^/]+)/"
    r"mcpServers/(?P<id>[^/]+)"
)
_REASONING_ENGINE = re.compile(
    r"projects/(?P<owner>[^/]+)/locations/(?P<region>[^/]+)/"
    r"reasoningEngines/(?P<engine_id>[^/]+)"
)
_REGISTERED_AGENT = re.compile(
    r"projects/(?P<owner>[^/]+)/locations/(?P<region>[^/]+)/"
    r"agents/(?P<id>[^/]+)"
)
_PRINCIPAL = re.compile(
    r"principal://(?P<trust_domain>[^/]+)/resources/aiplatform/"
    r"projects/(?P<project_number>\d+)/locations/(?P<region>[^/]+)/"
    r"reasoningEngines/(?P<engine_id>[^/]+)"
)
_RUNTIME_REFERENCE = re.compile(
    r"//aiplatform\.googleapis\.com/projects/(?P<project_number>\d+)/"
    r"locations/(?P<region>[^/]+)/reasoningEngines/(?P<engine_id>[^/]+)"
)
_SERVICE_EXTENSION_ACCOUNT = re.compile(
    r"service-(?P<owner>\d+)@gcp-sa-dep\.iam\.gserviceaccount\.com"
)
_IAP_SET_POLICY_METHOD = (
    "google.cloud.iap.v1.IdentityAwareProxyAdminService.SetIamPolicy"
)
_ALLOW_TITLE_PREFIX = "Custody temporary lookup admission/"
_DENY_TITLE = "Custody no-registered-tool negative control"
_DENY_CANARY = "custody_policy_canary"
_SERVER_DISPATCH_EVENT = "custody.gateway.lookup.dispatched.v1"
_MAX_PROOF_DURATION = timedelta(minutes=20)
_MAX_ALLOW_TTL = timedelta(minutes=10)
_MAX_WALK_DEPTH = 32
_MAX_WALK_NODES = 2_000
_CLOCK_SKEW_BOUND = 1.0


def _name(project: str, region: str, collection: str, resource_id: str) -> str:
    return f"projects/{project}/locations/{region}/{collection}/{resource_id}"


def _resource_aliases(
    *,
    project: str,
    project_number: str,
    region: str,
    collection: str,
    resource_id: str,
) -> set[str]:
    """Google normalizes some policy references from project ID to number."""
    return {
        _name(owner, region, collection, resource_id)
        for owner in (project, project_number)
    }


def _canonical_etag(value: object) -> str:
    """IAP etags are opaque base64. ``gcloud ... get-iam-policy`` returns the
    URL-safe alphabet (``-``/``_``); the same value inside a raw Admin
    Activity audit payload has been observed in the standard alphabet
    (``+``/``/``). Compare on one canonical form so an equivalent etag is not
    rejected as a different one.
    """
    return str(value).replace("-", "+").replace("_", "/")


def _aware_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(UTC)


def _rfc3339_seconds(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _resource_has_server_times(resource: dict[str, Any], captured: datetime) -> bool:
    created = _aware_time(resource["createTime"])
    updated = _aware_time(resource["updateTime"])
    return created <= updated <= captured + timedelta(minutes=5)


def _trust_domain_is_bound(trust_domain: str, project_number: str) -> bool:
    return (
        trust_domain
        == f"agents.global.project-{project_number}.system.id.goog"
        or re.fullmatch(r"agents\.global\.org-\d+\.system\.id\.goog", trust_domain)
        is not None
    )


def _single_binding(policy: dict[str, Any]) -> dict[str, Any]:
    bindings = policy["bindings"]
    if not isinstance(bindings, list) or len(bindings) != 1:
        raise ValueError("IAP policy must contain exactly one binding")
    binding = bindings[0]
    if not isinstance(binding, dict):
        raise TypeError("IAP policy binding must be an object")
    return binding


def _policy_is_exact(
    policy: dict[str, Any], *, principal: str, expression: str, title: str
) -> bool:
    binding = _single_binding(policy)
    condition = binding.get("condition", {})
    return (
        policy.get("version") == 3
        and bool(policy.get("etag"))
        and binding.get("role") == "roles/iap.egressor"
        and binding.get("members") == [principal]
        and condition.get("title") == title
        and condition.get("expression") == expression
    )


def _initial_policy_is_safe_deny(
    policy: dict[str, Any], *, principal: str, deny_expression: str
) -> bool:
    """A successful run must start after reconciliation to exact safe deny."""
    return _policy_is_exact(
        policy,
        principal=principal,
        expression=deny_expression,
        title=_DENY_TITLE,
    )


def _cloud_run_is_bound(
    resource: dict[str, Any], *, project: str, project_number: str,
    region: str, endpoint: str, captured: datetime,
) -> bool:
    """Bind the public MCP URL and ledger assumptions to one owned service."""
    metadata = resource["metadata"]
    spec = resource["spec"]
    template = spec["template"]
    template_metadata = template["metadata"]
    template_spec = template["spec"]
    status = resource["status"]
    containers = template_spec["containers"]
    if not isinstance(containers, list) or len(containers) != 1:
        return False
    container = containers[0]
    environment = container.get("env", [])
    if not isinstance(environment, list):
        return False
    revisions = [
        item.get("value")
        for item in environment
        if isinstance(item, dict) and item.get("name") == "CUSTODY_MCP_REVISION"
    ]
    conditions = status["conditions"]
    traffic = status["traffic"]
    requested_traffic = spec["traffic"]
    base_url = endpoint.removesuffix("/mcp").rstrip("/")
    urls = json.loads(metadata["annotations"]["run.googleapis.com/urls"])
    image_prefix = f"{region}-docker.pkg.dev/{project}/"
    created = _aware_time(metadata["creationTimestamp"])
    latest = status["latestReadyRevisionName"]
    return (
        resource["apiVersion"] == "serving.knative.dev/v1"
        and resource["kind"] == "Service"
        and metadata["name"] == MCP_SERVICE_ID
        and str(metadata["namespace"]) == project_number
        and metadata["labels"]["cloud.googleapis.com/location"] == region
        and metadata["labels"].get("custody-proof") == "stale-registry"
        and created <= captured + timedelta(minutes=5)
        and isinstance(urls, list)
        and base_url in urls
        and template_metadata["annotations"][
            "autoscaling.knative.dev/maxScale"
        ]
        == "1"
        and revisions == ["v2"]
        and isinstance(container.get("image"), str)
        and container["image"].startswith(image_prefix)
        and "/custody-export-mcp:" in container["image"]
        and requested_traffic == [{"latestRevision": True, "percent": 100}]
        and len(traffic) == 1
        and traffic[0].get("latestRevision") is True
        and traffic[0].get("percent") == 100
        and traffic[0].get("revisionName") == latest
        and status["latestCreatedRevisionName"] == latest
        and status["url"].rstrip("/") == base_url
        and any(
            isinstance(condition, dict)
            and condition.get("type") == "Ready"
            and condition.get("status") == "True"
            for condition in conditions
        )
    )


def _iap_audit_transition_is_bound(
    entry: dict[str, Any],
    *,
    project: str,
    resource: str,
    principal: str,
    before_etag: str,
    after_etag: str,
    started: datetime,
    applied: datetime,
    captured: datetime,
) -> bool:
    payload = entry["protoPayload"]
    auth = payload["authenticationInfo"]
    authorization = payload["authorizationInfo"]
    request = payload["request"]
    requested_policy = request["policy"]
    response = payload["response"]
    event_time = _aware_time(entry["timestamp"])
    received = _aware_time(entry["receiveTimestamp"])
    binding = {"members": [principal], "role": "roles/iap.egressor"}
    principal_email = auth.get("principalEmail")
    return (
        entry.get("logName")
        == f"projects/{project}/logs/cloudaudit.googleapis.com%2Factivity"
        and bool(entry.get("insertId"))
        and entry["resource"]["type"] == "audited_resource"
        and entry["resource"]["labels"].get("project_id") == project
        and started <= event_time <= applied <= captured
        and event_time <= received <= captured
        and payload.get("@type")
        == "type.googleapis.com/google.cloud.audit.AuditLog"
        and payload.get("serviceName") == "iap.googleapis.com"
        and payload.get("methodName") == _IAP_SET_POLICY_METHOD
        and payload.get("resourceName") == resource
        and isinstance(principal_email, str)
        and bool(principal_email)
        and auth.get("principalSubject") == f"user:{principal_email}"
        and authorization
        == [
            {
                "granted": True,
                "permission": "iap.webServices.setIamPolicy",
                "permissionType": "ADMIN_WRITE",
                "resourceAttributes": {
                    "name": resource,
                    "service": "iap.googleapis.com",
                    "type": "iap.googleapis.com/WebService",
                },
            }
        ]
        and request.get("@type")
        == "type.googleapis.com/google.iam.v1.SetIamPolicyRequest"
        and request.get("resource") == resource
        and _canonical_etag(requested_policy.get("etag"))
        == _canonical_etag(before_etag)
        and requested_policy.get("bindings") == [binding]
        and response.get("@type")
        == "type.googleapis.com/google.iam.v1.Policy"
        and _canonical_etag(response.get("etag")) == _canonical_etag(after_etag)
        and response.get("bindings") == [binding]
        and payload.get("status") == {}
    )


def _tool_definitions(service: dict[str, Any]) -> list[dict[str, Any]]:
    content = service["mcpServerSpec"]["content"]
    if isinstance(content, str):
        content = json.loads(content)
    tools = content["tools"]
    if not isinstance(tools, list):
        raise TypeError("Registry tools must be a list")
    return tools


def _one_interface(resource: dict[str, Any]) -> dict[str, Any]:
    interfaces = resource["interfaces"]
    if not isinstance(interfaces, list) or len(interfaces) != 1:
        raise ValueError("Registry resource must expose exactly one interface")
    interface = interfaces[0]
    if not isinstance(interface, dict):
        raise TypeError("Registry interface must be an object")
    return interface


def _walk_dicts(value: object) -> Iterator[dict[str, Any]]:
    """Walk decoded JSON with explicit depth/node bounds and cycle rejection."""
    stack: list[tuple[object, int]] = [(value, 0)]
    seen: set[int] = set()
    visited = 0
    while stack:
        current, depth = stack.pop()
        if not isinstance(current, (dict, list)):
            continue
        identity = id(current)
        if identity in seen:
            raise ValueError("evidence contains a repeated or cyclic container")
        seen.add(identity)
        visited += 1
        if visited > _MAX_WALK_NODES or depth > _MAX_WALK_DEPTH:
            raise ValueError("evidence nesting exceeds the judge's bound")
        if isinstance(current, dict):
            yield current
            children = current.values()
        else:
            children = current
        stack.extend((child, depth + 1) for child in children)


def _customer_payload(result: object, customer_id: str) -> dict[str, Any] | None:
    matches = [
        item
        for item in _walk_dicts(result)
        if item.get("customer_id") == customer_id
        and item.get("company") == f"Synthetic Customer {customer_id}"
        and item.get("plan") == "enterprise"
        and item.get("region") == "us-central1"
    ]
    if not matches:
        return None
    canonical = {
        json.dumps(item, sort_keys=True, separators=(",", ":")) for item in matches
    }
    return matches[0] if len(canonical) == 1 else None


def _counter(snapshot: dict[str, Any], field: str) -> int:
    value = snapshot[field]
    if type(value) is not int or value < 0:  # bool is not valid counter evidence.
        raise TypeError(f"{field} must be a non-negative integer")
    return value


def _authz_is_bound(
    payload: dict[str, Any], *, policy_name: str | None, decision: str
) -> bool:
    info = payload["authzPolicyInfo"]
    policies = info["policies"]
    if not isinstance(policies, list) or len(policies) != 1:
        return False
    policy = policies[0]
    if not isinstance(policy, dict):
        return False
    return (
        info.get("result") == decision
        and policy.get("result") == decision
        and policy_name is not None
        and policy.get("name") == policy_name
    )


def _log_is_bound(
    entry: dict[str, Any],
    *,
    project: str,
    project_number: str,
    region: str,
    trace_id: str,
    projection_names: set[str],
    endpoint: str,
    status: int,
    decision: str,
    policy_name: str | None,
    client_cert_fingerprint: str,
    forwarded: bool,
    tool_name: str,
    started: datetime,
    captured: datetime,
) -> bool:
    resource = entry["resource"]
    labels = resource["labels"]
    request = entry["httpRequest"]
    payload = entry["jsonPayload"]
    gateway_info = payload["agentGatewayInfo"]
    mcp = gateway_info["mcpInfo"]
    mtls = payload["mtls"]
    timestamp = _aware_time(entry["timestamp"])
    server_ip_is_bound = (
        isinstance(request.get("serverIp"), str) and bool(request["serverIp"])
        if forwarded
        else "serverIp" not in request
    )
    return (
        started <= timestamp <= captured
        and entry["trace"] == trace_id
        and bool(entry.get("insertId"))
        and entry.get("logName")
        == (
            f"projects/{project}/logs/"
            "networkservices.googleapis.com%2Fgateway_requests"
        )
        and resource["type"] == "networkservices.googleapis.com/Gateway"
        and labels.get("resource_container")
        in {project_number, f"projects/{project_number}"}
        and labels.get("location") == region
        and labels.get("gateway_name") == GATEWAY_ID
        and labels.get("gateway_type") == "SECURE_WEB_GATEWAY"
        and bool(labels.get("network_name"))
        and request["requestMethod"] == "POST"
        and request["status"] == status
        and server_ip_is_bound
        and str(request["requestUrl"]).rstrip("/") == endpoint.rstrip("/")
        and gateway_info["agentRegistryResource"] in projection_names
        and mcp["method"] == "tools/call"
        and mcp["parameter"] == tool_name
        and mtls.get("clientCertSha256Fingerprint")
        == client_cert_fingerprint
        and _authz_is_bound(
            payload, policy_name=policy_name, decision=decision
        )
    )


def _single_tool_log(
    entries: list[dict[str, Any]], *, tool_name: str
) -> dict[str, Any] | None:
    """Return one relevant Gateway log; reject absence and ambiguity alike."""
    if not isinstance(entries, list):
        raise TypeError("Gateway logs must be lists")
    candidates = [
        entry
        for entry in entries
        if entry.get("jsonPayload", {})
        .get("agentGatewayInfo", {})
        .get("mcpInfo", {})
        .get("method")
        == "tools/call"
        and entry.get("jsonPayload", {})
        .get("agentGatewayInfo", {})
        .get("mcpInfo", {})
        .get("parameter")
        == tool_name
    ]
    return candidates[0] if len(candidates) == 1 else None


def _server_dispatch_is_bound(
    entry: dict[str, Any],
    *,
    evidence: dict[str, Any],
    cloud_run_revision: str,
    allow_payload: dict[str, Any],
    allow_before: dict[str, Any],
    allow_after: dict[str, Any],
    started: datetime,
    captured: datetime,
) -> bool:
    """Bind one Cloud Run-authored event to the exact admitted dispatch."""
    allow = evidence["allow_control"]
    payload = entry["jsonPayload"]
    labels = entry["resource"]["labels"]
    dispatched = _aware_time(payload["server_dispatched_at"])
    logged = _aware_time(entry["timestamp"])
    received = _aware_time(entry["receiveTimestamp"])
    dispatch_id = allow_payload.get("dispatch_id")
    instance_id = allow_payload.get("instance_id")
    forwarding_count = _counter(allow_after, "forwarding_dispatch_count")
    return (
        bool(entry.get("insertId"))
        and entry.get("logName")
        == (
            f"projects/{evidence['project']}/logs/"
            "run.googleapis.com%2Fstdout"
        )
        and entry.get("severity") == "INFO"
        and entry["resource"].get("type") == "cloud_run_revision"
        and labels.get("project_id") == evidence["project"]
        and labels.get("location") == evidence["region"]
        and labels.get("service_name") == MCP_SERVICE_ID
        and labels.get("revision_name") == cloud_run_revision
        and payload.get("event") == _SERVER_DISPATCH_EVENT
        and payload.get("proof_id") == evidence["proof_id"]
        and payload.get("trace_id") == allow["trace_id"]
        and payload.get("customer_id") == allow["customer_id"]
        and payload.get("revision")
        == allow_payload.get("server_revision")
        == allow_after.get("revision")
        == allow_before.get("revision")
        == "v2"
        and payload.get("instance_id")
        == instance_id
        == allow_before.get("instance_id")
        == allow_after.get("instance_id")
        and payload.get("dispatch_id")
        == dispatch_id
        == allow_after.get("dispatch_count")
        and type(payload.get("dispatch_id")) is int
        and payload.get("forwarding_requested") is False
        and allow_payload.get("forwarding_requested") is False
        and allow_payload.get("forwarded_to") is None
        and allow_payload.get("forwarding_status") == "not-requested"
        and payload.get("forwarding_dispatch_count")
        == forwarding_count
        == _counter(allow_before, "forwarding_dispatch_count")
        and type(payload.get("forwarding_dispatch_count")) is int
        and payload.get("server_dispatched_at")
        == allow_after.get("last_dispatched_at")
        and started <= dispatched <= captured
        and started <= logged <= received <= captured
        # server_dispatched_at and the log entry's own timestamp are two
        # independent same-process clock reads for one event, not a causal
        # chain; require them near-coincident rather than strictly ordered.
        and abs((dispatched - logged).total_seconds()) <= _CLOCK_SKEW_BOUND
    )


def _blocked_control_is_bound(
    control: dict[str, Any],
    *,
    proof_id: str,
    tool_name: str,
    expected_snapshot: dict[str, Any],
) -> bool:
    """Require a 403 generated before any mutation of the owned MCP ledger."""
    result = control["result"]
    before = control["evidence_before"]
    after = control["evidence_after"]
    customer_id = control["customer_id"]
    error = str(result.get("error", "")).casefold()
    # Validate counter types even though exact snapshot equality is the primary
    # no-dispatch invariant; this prevents bool/string counter grafts.
    for snapshot in (before, after):
        _counter(snapshot, "dispatch_count")
        _counter(snapshot, "forwarding_dispatch_count")
    return (
        control.get("tool_name", tool_name) == tool_name
        and result.get("ok") is False
        and bool(result.get("error_type"))
        and result.get("proof_id") == proof_id
        and result.get("customer_id") == customer_id
        and result.get("tool_name") == tool_name
        and customer_id == f"custody-gateway-{proof_id}-deny"
        and "403" in error
        and "forbidden" in error
        and before == expected_snapshot
        and after == before
    )


def _require_bound_region_match(
    match: re.Match[str] | None,
    *,
    project: str,
    project_number: str,
    region: str,
    description: str,
) -> re.Match[str]:
    if (
        match is None
        or match.group("owner") not in {project, project_number}
        or match.group("region") != region
    ):
        raise ValueError(f"{description} belongs to another project or region")
    return match


def _evidence_is_fresh(
    *,
    proof_id: str,
    project_number: str,
    started: datetime,
    captured: datetime,
    now: datetime,
) -> bool:
    return (
        _HEX_ID.fullmatch(proof_id) is not None
        and project_number.isdecimal()
        and started <= captured
        and captured - started <= _MAX_PROOF_DURATION
        and captured <= now + timedelta(minutes=5)
        and now - captured <= timedelta(hours=24)
    )


def _judge(evidence: dict[str, Any], *, now: datetime) -> dict[str, bool]:
    if evidence["schema_version"] != 2:
        raise ValueError("unsupported Gateway evidence schema")
    proof_id = evidence["proof_id"]
    started = _aware_time(evidence["started_at"])
    captured = _aware_time(evidence["captured_at"])
    project = evidence["project"]
    project_number = str(evidence["project_number"])
    region = evidence["region"]

    gateway = evidence["gateway"]
    extension = evidence["extension"]
    authz_policy = evidence["authz_policy"]
    cloud_run = evidence["cloud_run"]
    registry = evidence["registry"]
    runtime = evidence["runtime"]
    allow = evidence["allow_control"]
    scope = evidence["scope_control"]
    expiry = evidence["expiry_control"]
    deny = evidence["deny_control"]
    logs = evidence["gateway_logs"]
    server_dispatch_log = evidence["server_dispatch_log"]

    gateway_name = _name(project, region, "agentGateways", GATEWAY_ID)
    extension_name = _name(project, region, "authzExtensions", EXTENSION_ID)
    policy_names = _resource_aliases(
        project=project,
        project_number=project_number,
        region=region,
        collection="authzPolicies",
        resource_id=AUTHZ_POLICY_ID,
    )
    policy_gateway_names = _resource_aliases(
        project=project,
        project_number=project_number,
        region=region,
        collection="agentGateways",
        resource_id=GATEWAY_ID,
    )
    policy_extension_names = _resource_aliases(
        project=project,
        project_number=project_number,
        region=region,
        collection="authzExtensions",
        resource_id=EXTENSION_ID,
    )
    registry_name = (
        f"//agentregistry.googleapis.com/projects/{project}/locations/{region}"
    )

    service = registry["service"]
    projection = registry["projection"]
    service_projection_match = _MCP_RESOURCE.fullmatch(service["registryResource"])
    projection_match = _MCP_RESOURCE.fullmatch(projection["name"])
    if service_projection_match is None or projection_match is None:
        raise ValueError("malformed Registry MCP resource name")
    projection_names = {service["registryResource"], projection["name"]}
    service_interface = _one_interface(service)
    projection_interface = _one_interface(projection)
    endpoint = service_interface["url"]
    service_tools = _tool_definitions(service)
    projection_tools = projection["tools"]
    if len(service_tools) != 1 or len(projection_tools) != 1:
        raise ValueError("proof requires one exact registered tool")
    service_tool = service_tools[0]
    projection_tool = projection_tools[0]

    engine = runtime["agent_engine"]
    registered_agent = runtime["registered_agent"]
    engine_name = engine["name"]
    engine_match = _require_bound_region_match(
        _REASONING_ENGINE.fullmatch(engine_name),
        project=project,
        project_number=project_number,
        region=region,
        description="Runtime resource",
    )
    engine_id = engine_match.group("engine_id")
    registered_agent_match = _require_bound_region_match(
        _REGISTERED_AGENT.fullmatch(registered_agent["name"]),
        project=project,
        project_number=project_number,
        region=region,
        description="registered Runtime agent",
    )

    attributes = registered_agent["attributes"]
    principal = attributes[RUNTIME_IDENTITY]["principal"]
    reference = attributes[RUNTIME_REFERENCE]["uri"]
    principal_match = _PRINCIPAL.fullmatch(principal)
    reference_match = _RUNTIME_REFERENCE.fullmatch(reference)
    if principal_match is None or reference_match is None:
        raise ValueError("malformed Agent Identity or Runtime Reference")

    allow_expires_raw = registry["iap_policy_allow_expires_at"]
    allow_expires = _aware_time(allow_expires_raw)
    allow_expiry_is_canonical = (
        str(allow_expires_raw) == _rfc3339_seconds(allow_expires)
    )
    allow_expression = (
        "api.getAttribute('iap.googleapis.com/mcp.toolName', '') == '' || "
        f"(request.time < timestamp('{allow_expires_raw}') && "
        "api.getAttribute('iap.googleapis.com/mcp.toolName', '') == "
        "'lookup_customer')"
    )
    allow_title = f"{_ALLOW_TITLE_PREFIX}{proof_id}"
    deny_expression = (
        "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
        f"in ['{_DENY_CANARY}', '']"
    )
    initial_policy = registry["iap_policy_initial"]
    allow_policy = registry["iap_policy_allow"]
    deny_policy = registry["iap_policy_deny"]
    if not all(
        isinstance(policy, dict)
        for policy in (initial_policy, allow_policy, deny_policy)
    ):
        raise TypeError("IAP policy snapshots must be objects")
    allow_policy_applied = _aware_time(
        registry["iap_policy_allow_applied_at"]
    )
    deny_policy_applied = _aware_time(
        registry["iap_policy_deny_applied_at"]
    )
    audit_logs = registry["iap_policy_audit_logs"]
    if not isinstance(audit_logs, dict):
        raise TypeError("IAP policy audit logs must be an object")

    deployment = engine["spec"]["deploymentSpec"]
    output_card = gateway["agentGatewayCard"]
    service_account = output_card.get("serviceExtensionsServiceAccount")
    service_account_match = (
        _SERVICE_EXTENSION_ACCOUNT.fullmatch(service_account)
        if isinstance(service_account, str)
        else None
    )
    authz_owner = (
        service_account_match.group("owner")
        if service_account_match is not None
        else None
    )
    logged_policy_name = (
        _name(authz_owner, region, "authzPolicies", AUTHZ_POLICY_ID)
        if authz_owner is not None
        else None
    )
    metadata = extension["metadata"]
    authz_profile = authz_policy.get("policyProfile", "REQUEST_AUTHZ")

    claim_is_bounded = evidence["claim_boundary"] == CLAIM_BOUNDARY
    fresh = _evidence_is_fresh(
        proof_id=proof_id,
        project_number=project_number,
        started=started,
        captured=captured,
        now=now,
    )

    gateway_policy_bound = (
        gateway["name"] == gateway_name
        and gateway["protocols"] == ["MCP"]
        and gateway["googleManaged"]["governedAccessPath"]
        == "AGENT_TO_ANYWHERE"
        and [item.rstrip("/") for item in gateway["registries"]]
        == [registry_name]
        and _resource_has_server_times(gateway, captured)
        and bool(gateway.get("etag"))
        and bool(output_card.get("mtlsEndpoint"))
        and bool(output_card.get("rootCertificates"))
        and service_account_match is not None
        and extension["name"] == extension_name
        and extension["service"] == "iap.googleapis.com"
        and extension.get("failOpen", False) is False
        and float(str(extension["timeout"]).removesuffix("s")) == 1.0
        and metadata == {"iapPolicyVersion": "V1"}
        and _resource_has_server_times(extension, captured)
        and authz_policy["name"] in policy_names
        and len(authz_policy["target"]["resources"]) == 1
        and authz_policy["target"]["resources"][0] in policy_gateway_names
        and authz_profile == "REQUEST_AUTHZ"
        and authz_policy["action"] == "CUSTOM"
        and authz_policy["customProvider"]["authzExtension"]["resources"]
        and len(
            authz_policy["customProvider"]["authzExtension"]["resources"]
        )
        == 1
        and authz_policy["customProvider"]["authzExtension"]["resources"][0]
        in policy_extension_names
        and _resource_has_server_times(authz_policy, captured)
    )

    registry_resources_bound = (
        service["name"]
        == _name(project, region, "services", MCP_SERVICE_ID)
        and service_projection_match.group("owner") == project_number
        and projection_match.group("owner") in {project, project_number}
        and service_projection_match.group("id") == projection_match.group("id")
        and service_projection_match.group("region") == region
        and projection_match.group("region") == region
        and endpoint.startswith(f"https://{MCP_SERVICE_ID}-")
        and endpoint.endswith(".run.app/mcp")
        and service_interface.get("protocolBinding") == "JSONRPC"
        and projection_interface["url"] == endpoint
        and service_tool["name"] == projection_tool["name"] == TOOL_NAME
        and service_tool["annotations"]["readOnlyHint"] is True
        and projection_tool["annotations"]["readOnlyHint"] is True
        and projection["mcpServerId"]
        == (
            f"urn:mcp:projects-{project_number}:projects:{project_number}:"
            f"locations:{region}:agentregistry:services:{MCP_SERVICE_ID}"
        )
        and projection["attributes"][RUNTIME_REFERENCE]["uri"]
        == (
            f"//agentregistry.googleapis.com/projects/{project_number}/"
            f"locations/{region}/services/{MCP_SERVICE_ID}"
        )
        and _resource_has_server_times(service, captured)
        and _resource_has_server_times(projection, captured)
    )
    cloud_run_bound = _cloud_run_is_bound(
        cloud_run,
        project=project,
        project_number=project_number,
        region=region,
        endpoint=endpoint,
        captured=captured,
    )

    runtime_identity_bound = (
        engine["spec"]["identityType"] == "AGENT_IDENTITY"
        and not engine["spec"].get("serviceAccount")
        and deployment["agentGatewayConfig"]["agentToAnywhereConfig"][
            "agentGateway"
        ]
        == gateway_name
        and _resource_has_server_times(engine, captured)
        and registered_agent_match.group("id") == registered_agent["uid"]
        and _resource_has_server_times(registered_agent, captured)
        and registered_agent["agentId"]
        == (
            f"urn:agent:projects-{project_number}:projects:{project_number}:"
            f"locations:{region}:aiplatform:reasoningEngines:{engine_id}"
        )
        and principal_match.group("region") == region
        and principal_match.group("engine_id") == engine_id
        and reference_match.group("region") == region
        and reference_match.group("engine_id") == engine_id
        and principal_match.group("project_number")
        == reference_match.group("project_number")
        == project_number
        and _trust_domain_is_bound(
            principal_match.group("trust_domain"), project_number
        )
        and engine["spec"]["effectiveIdentity"]
        == principal.removeprefix("principal://")
    )

    policies_bound = (
        allow_expiry_is_canonical
        and _initial_policy_is_safe_deny(
            initial_policy, principal=principal, deny_expression=deny_expression
        )
        and initial_policy["etag"] != allow_policy["etag"]
        and _policy_is_exact(
            allow_policy,
            principal=principal,
            expression=allow_expression,
            title=allow_title,
        )
        and _policy_is_exact(
            deny_policy,
            principal=principal,
            expression=deny_expression,
            title=_DENY_TITLE,
        )
        and allow_policy["etag"] != deny_policy["etag"]
        and started <= allow_policy_applied < allow_expires
        and timedelta(0) < allow_expires - allow_policy_applied <= _MAX_ALLOW_TTL
        and allow_expires < deny_policy_applied <= captured
    )
    audit_resource = (
        f"projects/{project_number}/locations/{region}/iap_web/agentRegistry/"
        f"mcpServers/{projection_match.group('id')}"
    )
    allow_audit = audit_logs["allow"]
    deny_audit = audit_logs["deny"]
    if not isinstance(allow_audit, dict) or not isinstance(deny_audit, dict):
        raise TypeError("IAP audit entries must be objects")
    allow_audit_time = _aware_time(allow_audit["timestamp"])
    deny_audit_time = _aware_time(deny_audit["timestamp"])
    audit_chain_bound = (
        allow_audit.get("insertId") != deny_audit.get("insertId")
        and _iap_audit_transition_is_bound(
            allow_audit,
            project=project,
            resource=audit_resource,
            principal=principal,
            before_etag=initial_policy["etag"],
            after_etag=allow_policy["etag"],
            started=started,
            applied=allow_policy_applied,
            captured=captured,
        )
        and _iap_audit_transition_is_bound(
            deny_audit,
            project=project,
            resource=audit_resource,
            principal=principal,
            before_etag=allow_policy["etag"],
            after_etag=deny_policy["etag"],
            started=started,
            applied=deny_policy_applied,
            captured=captured,
        )
        and allow_audit_time <= allow_policy_applied
        and allow_policy_applied < allow_expires < deny_audit_time
        and deny_audit_time <= deny_policy_applied
    )

    allow_before = allow["evidence_before"]
    allow_after = allow["evidence_after"]
    scope_after = scope["evidence_after"]
    expiry_after = expiry["evidence_after"]
    allow_customer = allow["customer_id"]
    allow_payload = _customer_payload(allow["result"], allow_customer)
    allow_count_before = _counter(allow_before, "dispatch_count")
    allow_count_after = _counter(allow_after, "dispatch_count")
    allow_forward_before = _counter(allow_before, "forwarding_dispatch_count")
    allow_forward_after = _counter(allow_after, "forwarding_dispatch_count")

    allow_reached_mcp = (
        allow["result"]["ok"] is True
        and allow["result"]["is_error"] is False
        and allow["result"].get("tool_name") == TOOL_NAME
        and allow["result"]["proof_id"] == proof_id
        and allow["result"]["customer_id"] == allow_customer
        and allow_customer == f"custody-gateway-{proof_id}-allow"
        and allow_payload is not None
        and allow_payload.get("server_revision")
        == allow_before["revision"]
        == allow_after["revision"]
        == "v2"
        and allow_payload.get("dispatch_id") == allow_count_after
        and allow_payload.get("instance_id")
        == allow_before["instance_id"]
        == allow_after["instance_id"]
        and allow_count_after == allow_count_before + 1
        and allow_forward_after == allow_forward_before
        and allow_after["last_dispatched_at"]
        != allow_before.get("last_dispatched_at")
    )
    scope_is_narrow = _blocked_control_is_bound(
        scope,
        proof_id=proof_id,
        tool_name=_DENY_CANARY,
        expected_snapshot=allow_after,
    )
    expiry_is_enforced = _blocked_control_is_bound(
        expiry,
        proof_id=proof_id,
        tool_name=TOOL_NAME,
        expected_snapshot=scope_after,
    )
    deny_stopped_before_dispatch = _blocked_control_is_bound(
        deny,
        proof_id=proof_id,
        tool_name=TOOL_NAME,
        expected_snapshot=expiry_after,
    )

    trace_ids = [
        allow["trace_id"],
        scope["trace_id"],
        expiry["trace_id"],
        deny["trace_id"],
    ]
    traces_are_bound = (
        all(
            isinstance(trace_id, str)
            and _HEX_ID.fullmatch(trace_id) is not None
            and trace_id != "0" * 32
            for trace_id in trace_ids
        )
        and len(set(trace_ids)) == len(trace_ids)
    )
    allow_log = _single_tool_log(logs["allow"], tool_name=TOOL_NAME)
    scope_log = _single_tool_log(logs["scope"], tool_name=_DENY_CANARY)
    expiry_log = _single_tool_log(logs["expiry"], tool_name=TOOL_NAME)
    deny_log = _single_tool_log(logs["deny"], tool_name=TOOL_NAME)
    logs_correlate = False
    server_dispatch_bound = False
    if (
        traces_are_bound
        and allow_log is not None
        and scope_log is not None
        and expiry_log is not None
        and deny_log is not None
    ):
        allow_log_time = _aware_time(allow_log["timestamp"])
        scope_log_time = _aware_time(scope_log["timestamp"])
        expiry_log_time = _aware_time(expiry_log["timestamp"])
        deny_log_time = _aware_time(deny_log["timestamp"])
        allow_fingerprint = allow_log["jsonPayload"]["mtls"].get(
            "clientCertSha256Fingerprint"
        )
        certificate_is_bound = (
            isinstance(allow_fingerprint, str)
            and bool(allow_fingerprint)
            and all(
                log["jsonPayload"]["mtls"].get(
                    "clientCertSha256Fingerprint"
                )
                == allow_fingerprint
                for log in (scope_log, expiry_log, deny_log)
            )
        )
        chronology_is_bound = (
            allow_audit_time
            <= allow_policy_applied
            <= allow_log_time
            < scope_log_time
            < allow_expires
            <= expiry_log_time
            < deny_audit_time
            <= deny_policy_applied
            < deny_log_time
            <= captured
        )
        logs_correlate = (
            certificate_is_bound
            and chronology_is_bound
            and _log_is_bound(
                allow_log,
                project=project,
                project_number=project_number,
                region=region,
                trace_id=allow["trace_id"],
                projection_names=projection_names,
                endpoint=endpoint,
                status=200,
                decision="ALLOWED",
                policy_name=logged_policy_name,
                client_cert_fingerprint=allow_fingerprint,
                forwarded=True,
                tool_name=TOOL_NAME,
                started=started,
                captured=captured,
            )
            and _log_is_bound(
                scope_log,
                project=project,
                project_number=project_number,
                region=region,
                trace_id=scope["trace_id"],
                projection_names=projection_names,
                endpoint=endpoint,
                status=403,
                decision="DENIED",
                policy_name=logged_policy_name,
                client_cert_fingerprint=allow_fingerprint,
                forwarded=False,
                tool_name=_DENY_CANARY,
                started=started,
                captured=captured,
            )
            and _log_is_bound(
                expiry_log,
                project=project,
                project_number=project_number,
                region=region,
                trace_id=expiry["trace_id"],
                projection_names=projection_names,
                endpoint=endpoint,
                status=403,
                decision="DENIED",
                policy_name=logged_policy_name,
                client_cert_fingerprint=allow_fingerprint,
                forwarded=False,
                tool_name=TOOL_NAME,
                started=started,
                captured=captured,
            )
            and _log_is_bound(
                deny_log,
                project=project,
                project_number=project_number,
                region=region,
                trace_id=deny["trace_id"],
                projection_names=projection_names,
                endpoint=endpoint,
                status=403,
                decision="DENIED",
                policy_name=logged_policy_name,
                client_cert_fingerprint=allow_fingerprint,
                forwarded=False,
                tool_name=TOOL_NAME,
                started=started,
                captured=captured,
            )
        )
        server_dispatch_bound = (
            allow_reached_mcp
            and _server_dispatch_is_bound(
                server_dispatch_log,
                evidence=evidence,
                cloud_run_revision=cloud_run["status"][
                    "latestReadyRevisionName"
                ],
                allow_payload=allow_payload,
                allow_before=allow_before,
                allow_after=allow_after,
                started=started,
                captured=captured,
            )
            and _aware_time(server_dispatch_log["receiveTimestamp"])
            <= scope_log_time
        )

    return {
        "fresh_bounded_live_evidence": fresh and claim_is_bounded,
        "enforced_registered_tool_request_authz": gateway_policy_bound,
        "owned_cloud_run_target_bound": cloud_run_bound,
        "runtime_identity_and_registry_bound": (
            registry_resources_bound and runtime_identity_bound
        ),
        "exact_server_expiring_iap_transition": policies_bound,
        "server_audited_iap_etag_chain": audit_chain_bound,
        "allow_reached_owned_mcp": allow_reached_mcp,
        "server_dispatch_binds_allow": server_dispatch_bound,
        "temporary_allow_is_tool_scoped": scope_is_narrow,
        "temporary_allow_expires_server_side": expiry_is_enforced,
        "deny_stopped_before_dispatch": deny_stopped_before_dispatch,
        "gateway_logs_correlate_enforcement": logs_correlate,
    }


def judge(
    evidence: dict[str, Any], *, now: datetime | None = None
) -> dict[str, bool]:
    """Return clean failure evidence for every malformed or incomplete artifact."""
    try:
        if not isinstance(evidence, dict):
            raise TypeError("Gateway evidence must be an object")
        return _judge(evidence, now=now or datetime.now(UTC))
    except (
        AttributeError,
        KeyError,
        IndexError,
        RecursionError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {"well_formed_evidence": False}


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-gateway.json")
        print("          run make live-gateway")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live Gateway evidence: {error}")
        return 1
    gates = judge(evidence)
    if gates and all(gates.values()):
        gates.update(attest_live(evidence))
    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if gates and all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
