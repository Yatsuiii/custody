"""Attest a Gateway proof artifact against current Google Cloud readbacks.

The offline judge proves that an artifact is internally coherent.  This module
closes the remaining authenticity gap by reading the resources and log entries
from a code-owned Google Cloud scope, then comparing those server readbacks to
the artifact at the decoded JSON boundary. The Runtime comparison removes the
SDK-only ``trafficConfig`` field, which the REST GET does not return.

Only read operations are exposed by the production client.  Evidence may
select its per-run log entries, but it cannot select a project, region,
Gateway, Registry service, Cloud Run service, or Agent Runtime.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(os.environ.get("CLOUDSDK_CONFIG", REPO_ROOT / ".gcloud"))

# These values are deliberately independent of the evidence producer.  They
# are the trust anchor that prevents a coherent artifact from redirecting live
# attestation to attacker-selected resources.
PROJECT = "project-988bc9fe-092c-4b32-90c"
PROJECT_NUMBER = "742122658452"
REGION = "us-central1"
ENGINE_ID = "5289382654590844928"
GATEWAY_ID = "custody-fleet-egress"
EXTENSION_ID = "custody-fleet-iap-enforced"
AUTHZ_POLICY_ID = "custody-fleet-request-authz"
SERVICE_ID = "custody-export-mcp"
RUNTIME_REFERENCE = "agentregistry.googleapis.com/system/RuntimeReference"

GATE_NAMES = (
    "live_attestation_available",
    "trusted_project_identity",
    "live_gateway_configuration",
    "live_registry_runtime_target",
    "live_final_deny_policy",
    "live_gateway_log_entries",
    "live_server_dispatch_log",
    "live_iap_audit_entries",
)

_TRACE_ID = re.compile(r"[0-9a-f]{32}")
_PROOF_ID = re.compile(r"[0-9a-f]{32}")
_INSERT_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_CLOUD_RUN_REVISION = re.compile(
    rf"{re.escape(SERVICE_ID)}-[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?"
)
_SERVER_DISPATCH_EVENT = "custody.gateway.lookup.dispatched.v1"
_CLOCK_SKEW_BOUND = 1.0
_PROJECTION_NAME = re.compile(
    rf"projects/(?:{re.escape(PROJECT)}|{PROJECT_NUMBER})/"
    rf"locations/{REGION}/mcpServers/(?P<id>[A-Za-z0-9-]+)"
)
_IAP_SET_POLICY_METHOD = (
    "google.cloud.iap.v1.IdentityAwareProxyAdminService.SetIamPolicy"
)
_READ_PREFIXES = (
    ("projects", "describe"),
    ("network-services", "agent-gateways", "describe"),
    ("service-extensions", "authz-extensions", "describe"),
    ("network-security", "authz-policies", "describe"),
    ("agent-registry", "services", "describe"),
    ("agent-registry", "mcp-servers", "describe"),
    ("agent-registry", "agents", "list"),
    ("run", "services", "describe"),
    ("iap", "web", "get-iam-policy"),
    ("logging", "read"),
)


class CloudReadClient(Protocol):
    """Minimal injectable boundary for authenticated Google Cloud reads."""

    def json(self, *arguments: str) -> Any:
        """Return decoded JSON from one allowlisted gcloud read."""

    def rest_json(self, url: str) -> Any:
        """Return decoded JSON from one authenticated HTTPS GET."""


@dataclass(frozen=True)
class GcloudReadClient:
    """Use Custody's isolated gcloud configuration for read-only attestation."""

    def json(self, *arguments: str) -> Any:
        if not any(arguments[: len(prefix)] == prefix for prefix in _READ_PREFIXES):
            raise ValueError("live attestation attempted a non-read gcloud call")
        return json.loads(
            self._run(
                *arguments,
                f"--project={PROJECT}",
                "--quiet",
                "--format=json",
            )
        )

    def rest_json(self, url: str) -> Any:
        if url != _runtime_url():
            raise ValueError("live attestation attempted an untrusted REST read")
        token = self._run("auth", "print-access-token", "--quiet").strip()
        if not token:
            raise RuntimeError("gcloud returned an empty access token")
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)

    @staticmethod
    def _run(*arguments: str) -> str:
        environment = os.environ.copy()
        environment["CLOUDSDK_CONFIG"] = str(CONFIG)
        environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
        completed = subprocess.run(
            ["gcloud", *arguments],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
            timeout=120,
        )
        return completed.stdout


def _runtime_url() -> str:
    return (
        f"https://{REGION}-aiplatform.googleapis.com/v1/projects/"
        f"{PROJECT_NUMBER}/locations/{REGION}/reasoningEngines/{ENGINE_ID}"
    )


def _runtime_reference() -> str:
    return (
        f"//aiplatform.googleapis.com/projects/{PROJECT_NUMBER}/locations/"
        f"{REGION}/reasoningEngines/{ENGINE_ID}"
    )


def _as_aware_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("log timestamp has no timezone")
    return parsed.astimezone(UTC)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _single_gateway_entry(evidence: dict[str, Any], phase: str) -> dict[str, Any]:
    entries = evidence["gateway_logs"][phase]
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError(f"{phase} must contain exactly one Gateway log")
    entry = entries[0]
    if not isinstance(entry, dict):
        raise TypeError(f"{phase} Gateway log must be an object")
    trace = entry.get("trace")
    insert_id = entry.get("insertId")
    if not isinstance(trace, str) or _TRACE_ID.fullmatch(trace) is None:
        raise ValueError(f"{phase} Gateway trace is not a trusted selector")
    control = evidence[f"{phase}_control"]
    if not isinstance(control, dict) or control.get("trace_id") != trace:
        raise ValueError(f"{phase} Gateway trace is not bound to its control")
    if not isinstance(insert_id, str) or _INSERT_ID.fullmatch(insert_id) is None:
        raise ValueError(f"{phase} Gateway insert ID is not a trusted selector")
    _as_aware_time(entry["timestamp"])
    return entry


def _audit_entry(evidence: dict[str, Any], phase: str) -> dict[str, Any]:
    entry = evidence["registry"]["iap_policy_audit_logs"][phase]
    if not isinstance(entry, dict):
        raise TypeError(f"{phase} IAP audit log must be an object")
    insert_id = entry.get("insertId")
    if not isinstance(insert_id, str) or _INSERT_ID.fullmatch(insert_id) is None:
        raise ValueError(f"{phase} IAP audit insert ID is not a trusted selector")
    _as_aware_time(entry["timestamp"])
    return entry


def _server_dispatch_entry(evidence: dict[str, Any]) -> dict[str, Any]:
    entry = evidence["server_dispatch_log"]
    if not isinstance(entry, dict):
        raise TypeError("server dispatch log must be an object")
    insert_id = entry.get("insertId")
    if not isinstance(insert_id, str) or _INSERT_ID.fullmatch(insert_id) is None:
        raise ValueError("server dispatch insert ID is not a trusted selector")
    timestamp = _as_aware_time(entry["timestamp"])
    started = _as_aware_time(evidence["started_at"])
    captured = _as_aware_time(evidence["captured_at"])
    if not started <= timestamp <= captured:
        raise ValueError("server dispatch log is outside the proof interval")
    return entry


def _window(entries: list[dict[str, Any]]) -> tuple[str, str]:
    timestamps = [_as_aware_time(entry["timestamp"]) for entry in entries]
    return (
        _rfc3339(min(timestamps) - timedelta(seconds=2)),
        _rfc3339(max(timestamps) + timedelta(seconds=2)),
    )


def _gateway_log_filter(entries: list[dict[str, Any]]) -> str:
    start, end = _window(entries)
    selectors = " OR ".join(
        f'(trace="{entry["trace"]}" AND insertId="{entry["insertId"]}")'
        for entry in entries
    )
    return " AND ".join(
        (
            (
                f'logName="projects/{PROJECT}/logs/'
                'networkservices.googleapis.com%2Fgateway_requests"'
            ),
            'resource.type="networkservices.googleapis.com/Gateway"',
            f'resource.labels.gateway_name="{GATEWAY_ID}"',
            f'resource.labels.location="{REGION}"',
            f'timestamp>="{start}"',
            f'timestamp<="{end}"',
            f"({selectors})",
        )
    )


def _audit_log_filter(entries: list[dict[str, Any]], projection_id: str) -> str:
    start, end = _window(entries)
    selectors = " OR ".join(f'insertId="{entry["insertId"]}"' for entry in entries)
    resource = (
        f"projects/{PROJECT_NUMBER}/locations/{REGION}/iap_web/"
        f"agentRegistry/mcpServers/{projection_id}"
    )
    return " AND ".join(
        (
            (f'logName="projects/{PROJECT}/logs/cloudaudit.googleapis.com%2Factivity"'),
            'protoPayload.serviceName="iap.googleapis.com"',
            f'protoPayload.methodName="{_IAP_SET_POLICY_METHOD}"',
            f'protoPayload.resourceName="{resource}"',
            f'timestamp>="{start}"',
            f'timestamp<="{end}"',
            f"({selectors})",
        )
    )


def _server_dispatch_log_filter(
    evidence: dict[str, Any], entry: dict[str, Any], revision: str
) -> str:
    """Select one server event without trusting artifact-selected resources."""
    proof_id = evidence.get("proof_id")
    allow = evidence["allow_control"]
    trace_id = allow.get("trace_id")
    customer_id = allow.get("customer_id")
    if not isinstance(proof_id, str) or _PROOF_ID.fullmatch(proof_id) is None:
        raise ValueError("proof ID is not a trusted server-log selector")
    if not isinstance(trace_id, str) or _TRACE_ID.fullmatch(trace_id) is None:
        raise ValueError("allow trace is not a trusted server-log selector")
    if customer_id != f"custody-gateway-{proof_id}-allow":
        raise ValueError("allow customer is not bound to the proof ID")
    if _CLOUD_RUN_REVISION.fullmatch(revision) is None:
        raise ValueError("Cloud Run returned an untrusted revision name")

    timestamp = _as_aware_time(entry["timestamp"])
    start = _rfc3339(timestamp - timedelta(seconds=2))
    end = _rfc3339(timestamp + timedelta(seconds=2))
    return " AND ".join(
        (
            f'logName="projects/{PROJECT}/logs/run.googleapis.com%2Fstdout"',
            'resource.type="cloud_run_revision"',
            f'resource.labels.project_id="{PROJECT}"',
            f'resource.labels.location="{REGION}"',
            f'resource.labels.service_name="{SERVICE_ID}"',
            f'resource.labels.revision_name="{revision}"',
            f'jsonPayload.event="{_SERVER_DISPATCH_EVENT}"',
            f'jsonPayload.proof_id="{proof_id}"',
            f'jsonPayload.trace_id="{trace_id}"',
            f'jsonPayload.customer_id="{customer_id}"',
            f'insertId="{entry["insertId"]}"',
            f'timestamp>="{start}"',
            f'timestamp<="{end}"',
        )
    )


def _projection_id(service: dict[str, Any]) -> str:
    match = _PROJECTION_NAME.fullmatch(str(service["registryResource"]))
    if match is None:
        raise ValueError("Registry service returned an untrusted projection")
    return match.group("id")


def _registered_runtime(agents: Any) -> dict[str, Any]:
    if not isinstance(agents, list):
        raise TypeError("Agent Registry list response was not a list")
    matches = []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        reference = agent.get("attributes", {}).get(RUNTIME_REFERENCE, {})
        if reference.get("uri") == _runtime_reference():
            matches.append(agent)
    if len(matches) != 1:
        raise ValueError("trusted Agent Runtime did not have one Registry agent")
    return matches[0]


def _entries_match(expected: list[dict[str, Any]], observed: Any) -> bool:
    if not isinstance(observed, list) or len(observed) != len(expected):
        return False
    if not all(isinstance(entry, dict) for entry in observed):
        return False
    expected_by_id = {entry.get("insertId"): entry for entry in expected}
    observed_by_id = {entry.get("insertId"): entry for entry in observed}
    return (
        len(expected_by_id) == len(expected)
        and len(observed_by_id) == len(observed)
        and expected_by_id == observed_by_id
    )


def _runtime_matches(expected: dict[str, Any], observed: Any) -> bool:
    """Compare the server view while excluding one SDK-enriched top-level field."""
    if not isinstance(observed, dict):
        return False
    expected_server_view = {
        key: value for key, value in expected.items() if key != "trafficConfig"
    }
    observed_server_view = {
        key: value for key, value in observed.items() if key != "trafficConfig"
    }
    return expected_server_view == observed_server_view


# Google reconciles these resources' own etag/updateTime on a schedule
# unrelated to any configuration change Custody would care about; comparing
# them exactly would fail a rereading done hours after the proof for reasons
# that have nothing to do with what the proof actually claims.
_VOLATILE_RESOURCE_FIELDS = ("etag", "updateTime")


def _config_matches(expected: dict[str, Any], observed: Any) -> bool:
    if not isinstance(observed, dict):
        return False
    expected_config = {
        key: value
        for key, value in expected.items()
        if key not in _VOLATILE_RESOURCE_FIELDS
    }
    observed_config = {
        key: value
        for key, value in observed.items()
        if key not in _VOLATILE_RESOURCE_FIELDS
    }
    return expected_config == observed_config


def _server_dispatch_is_bound(
    evidence: dict[str, Any], entry: dict[str, Any], revision: str
) -> bool:
    """Bind the server-authored event to the exact successful control call."""
    try:
        payload = entry["jsonPayload"]
        labels = entry["resource"]["labels"]
        allow = evidence["allow_control"]
        result = allow["result"]["data"]
        # The MCP result envelope carries the tool's structured output under
        # structuredContent; a flat data payload is kept as a fallback shape.
        if isinstance(result.get("structuredContent"), dict):
            result = result["structuredContent"]
        after = allow["evidence_after"]
        started = _as_aware_time(evidence["started_at"])
        dispatched = _as_aware_time(payload["server_dispatched_at"])
        logged = _as_aware_time(entry["timestamp"])
        received = _as_aware_time(entry["receiveTimestamp"])
        captured = _as_aware_time(evidence["captured_at"])
    except (KeyError, TypeError, ValueError):
        return False

    proof_id = evidence["proof_id"]
    trace_id = allow["trace_id"]
    customer_id = allow["customer_id"]
    instance_id = result.get("instance_id")
    dispatch_id = result.get("dispatch_id")
    return (
        entry.get("logName") == f"projects/{PROJECT}/logs/run.googleapis.com%2Fstdout"
        and entry.get("severity") == "INFO"
        and entry["resource"].get("type") == "cloud_run_revision"
        and labels.get("project_id") == PROJECT
        and labels.get("location") == REGION
        and labels.get("service_name") == SERVICE_ID
        and labels.get("revision_name") == revision
        and payload.get("event") == _SERVER_DISPATCH_EVENT
        and payload.get("proof_id") == proof_id
        and payload.get("trace_id") == trace_id
        and payload.get("customer_id") == customer_id
        # R1, R2, and S1 share one Cloud Run service; each proof's own
        # deploy steps move CUSTODY_MCP_REVISION independently (R2's own
        # proof deliberately ends on a different value than R1's), so S1
        # cannot pin a specific revision label -- only that every source
        # here agrees with the same live proof's own recorded ledger value.
        and isinstance(payload.get("revision"), str)
        and payload.get("revision") == after.get("revision")
        and payload.get("instance_id") == instance_id
        and payload.get("dispatch_id") == dispatch_id
        and payload.get("forwarding_requested") is False
        and payload.get("forwarding_dispatch_count")
        == after.get("forwarding_dispatch_count")
        # v1's lookup_customer tool has no forwarding concept at all (added
        # in v2 alongside forward_to), so these three keys are legitimately
        # absent from a v1 response, not unbound -- see the matching
        # comment in gateway_gates.py's offline counterpart.
        and result.get("forwarding_requested") in (False, None)
        and result.get("forwarded_to") is None
        and result.get("forwarding_status") in ("not-requested", None)
        and after.get("instance_id") == instance_id
        and after.get("dispatch_count") == dispatch_id
        and after.get("last_dispatched_at") == payload.get("server_dispatched_at")
        and started <= dispatched <= captured
        and started <= logged <= received <= captured
        # server_dispatched_at and the log entry's own timestamp are two
        # independent same-process clock reads for one event, not a causal
        # chain; require them near-coincident rather than strictly ordered.
        and abs((dispatched - logged).total_seconds()) <= _CLOCK_SKEW_BOUND
    )


def _read_initial(cloud: CloudReadClient) -> dict[str, Any]:
    calls = {
        "project": ("projects", "describe", PROJECT),
        "gateway": (
            "network-services",
            "agent-gateways",
            "describe",
            GATEWAY_ID,
            f"--location={REGION}",
        ),
        "extension": (
            "service-extensions",
            "authz-extensions",
            "describe",
            EXTENSION_ID,
            f"--location={REGION}",
        ),
        "authz_policy": (
            "network-security",
            "authz-policies",
            "describe",
            AUTHZ_POLICY_ID,
            f"--location={REGION}",
        ),
        "registry_service": (
            "agent-registry",
            "services",
            "describe",
            SERVICE_ID,
            f"--location={REGION}",
        ),
        "registered_agents": (
            "agent-registry",
            "agents",
            "list",
            f"--location={REGION}",
        ),
        "cloud_run": (
            "run",
            "services",
            "describe",
            SERVICE_ID,
            f"--region={REGION}",
        ),
    }
    with ThreadPoolExecutor(max_workers=len(calls) + 1) as executor:
        futures = {
            name: executor.submit(cloud.json, *arguments)
            for name, arguments in calls.items()
        }
        futures["agent_engine"] = executor.submit(cloud.rest_json, _runtime_url())
        return {name: future.result() for name, future in futures.items()}


def _attest(evidence: dict[str, Any], cloud: CloudReadClient) -> dict[str, bool]:
    if not isinstance(evidence, dict):
        raise TypeError("Gateway evidence must be an object")

    expected_gateway_logs = [
        _single_gateway_entry(evidence, "allow"),
        _single_gateway_entry(evidence, "scope"),
        _single_gateway_entry(evidence, "expiry"),
        _single_gateway_entry(evidence, "deny"),
    ]
    expected_audit_logs = [
        _audit_entry(evidence, "allow"),
        _audit_entry(evidence, "deny"),
    ]
    expected_server_log = _server_dispatch_entry(evidence)

    live = _read_initial(cloud)
    service = live["registry_service"]
    projection_id = _projection_id(service)

    with ThreadPoolExecutor(max_workers=2) as executor:
        projection_future = executor.submit(
            cloud.json,
            "agent-registry",
            "mcp-servers",
            "describe",
            projection_id,
            f"--location={REGION}",
        )
        policy_future = executor.submit(
            cloud.json,
            "iap",
            "web",
            "get-iam-policy",
            "--resource-type=agent-registry",
            f"--mcp-server={projection_id}",
            f"--region={REGION}",
        )
        projection = projection_future.result()
        final_policy = policy_future.result()

    gateway_filter = _gateway_log_filter(expected_gateway_logs)
    audit_filter = _audit_log_filter(expected_audit_logs, projection_id)
    revision = str(live["cloud_run"]["status"]["latestReadyRevisionName"])
    server_filter = _server_dispatch_log_filter(evidence, expected_server_log, revision)
    with ThreadPoolExecutor(max_workers=3) as executor:
        gateway_logs_future = executor.submit(
            cloud.json,
            "logging",
            "read",
            gateway_filter,
            "--order=asc",
            "--limit=4",
        )
        audit_logs_future = executor.submit(
            cloud.json,
            "logging",
            "read",
            audit_filter,
            "--order=asc",
            "--limit=2",
        )
        server_log_future = executor.submit(
            cloud.json,
            "logging",
            "read",
            server_filter,
            "--order=asc",
            "--limit=1",
        )
        gateway_logs = gateway_logs_future.result()
        audit_logs = audit_logs_future.result()
        server_logs = server_log_future.result()

    registered_agent = _registered_runtime(live["registered_agents"])
    project = live["project"]
    trusted_project = (
        evidence.get("project") == PROJECT
        and str(evidence.get("project_number")) == PROJECT_NUMBER
        and evidence.get("region") == REGION
        and project.get("projectId") == PROJECT
        and str(project.get("projectNumber")) == PROJECT_NUMBER
        and project.get("lifecycleState") == "ACTIVE"
    )
    registry = evidence["registry"]
    runtime = evidence["runtime"]

    return {
        "live_attestation_available": True,
        "trusted_project_identity": trusted_project,
        "live_gateway_configuration": (
            _config_matches(evidence["gateway"], live["gateway"])
            and _config_matches(evidence["extension"], live["extension"])
            and _config_matches(evidence["authz_policy"], live["authz_policy"])
        ),
        "live_registry_runtime_target": (
            service == registry["service"]
            and projection == registry["projection"]
            and live["cloud_run"] == evidence["cloud_run"]
            and _runtime_matches(runtime["agent_engine"], live["agent_engine"])
            and registered_agent == runtime["registered_agent"]
        ),
        "live_final_deny_policy": final_policy == registry["iap_policy_deny"],
        "live_gateway_log_entries": _entries_match(expected_gateway_logs, gateway_logs),
        "live_server_dispatch_log": (
            _server_dispatch_is_bound(evidence, expected_server_log, revision)
            and _entries_match([expected_server_log], server_logs)
        ),
        "live_iap_audit_entries": _entries_match(expected_audit_logs, audit_logs),
    }


def attest_live(
    evidence: dict[str, Any], cloud: CloudReadClient | None = None
) -> dict[str, bool]:
    """Return fixed, clean-failure gates for live artifact authenticity."""
    try:
        return _attest(evidence, cloud or GcloudReadClient())
    except Exception:
        # Network/authentication failures and malformed remote payloads are
        # indistinguishable from unavailable proof: neither may pass a gate.
        return {name: False for name in GATE_NAMES}
