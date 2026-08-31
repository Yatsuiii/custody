"""Prove live Agent Gateway IAP enforcement with a deterministic Runtime.

This producer is intentionally not the judge.  It collects raw Cloud resource
descriptions, two exact IAP policy snapshots, the owned MCP server's dispatch
ledger, Agent Runtime results, and trace-bound Gateway logs.  The independent
``scripts/gateway_gates.py`` module derives the verdict from those facts.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplatform import Client  # noqa: E402
from agentplatform._genai import _agent_engines_utils  # noqa: E402
from google.auth import load_credentials_from_file  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-gateway.json"
FAILURE = REPO_ROOT / "proof-out" / "live-gateway.failure.json"
CONFIG = Path(os.environ.get("CLOUDSDK_CONFIG", REPO_ROOT / ".gcloud"))
ADC = CONFIG / "application_default_credentials.json"

PROJECT = "project-988bc9fe-092c-4b32-90c"
PROJECT_NUMBER = "742122658452"
REGION = "us-central1"
ENGINE_ID = "5289382654590844928"
GATEWAY_ID = "custody-fleet-egress"
EXTENSION_ID = "custody-fleet-iap-enforced"
AUTHZ_POLICY_ID = "custody-fleet-request-authz"
SERVICE_ID = "custody-export-mcp"
TOOL_NAME = "lookup_customer"
DENY_CANARY = "custody_policy_canary"
RUNTIME_REFERENCE = "agentregistry.googleapis.com/system/RuntimeReference"
RUNTIME_IDENTITY = "agentregistry.googleapis.com/system/RuntimeIdentity"
IAP_PROPAGATION_SECONDS = 150
GCLOUD_TIMEOUT_SECONDS = 120
TEMPORARY_ALLOW_TTL = timedelta(minutes=10)
POLICY_ATTEMPTS = 3
RUNTIME_QUERY_TIMEOUT_SECONDS = 90
GATEWAY_LOG_POLL_ATTEMPTS = 18
GATEWAY_LOG_POLL_INTERVAL_SECONDS = 5

EXPECTED_RUNTIME_REFERENCE = (
    f"//aiplatform.googleapis.com/projects/{PROJECT_NUMBER}/locations/{REGION}/"
    f"reasoningEngines/{ENGINE_ID}"
)
EXPECTED_PRINCIPAL = (
    "principal://agents.global.org-521713171342.system.id.goog/resources/"
    f"aiplatform/projects/{PROJECT_NUMBER}/locations/{REGION}/"
    f"reasoningEngines/{ENGINE_ID}"
)
EXPECTED_MCP_ENDPOINT = (
    "https://custody-export-mcp-anexdhueiq-uc.a.run.app/mcp"
)

CLAIM_BOUNDARY = (
    "Proves IAP REQUEST_AUTHZ enforcement for one owned Agent Runtime identity "
    "calling one registered MCP server through one Agent Gateway. It does not "
    "prove all egress is covered, repair stale Registry metadata, or remove "
    "Custody's allowed-call TOCTOU boundary."
)

DENY_EXPRESSION = (
    "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
    f"in ['{DENY_CANARY}', '']"
)
DENY_TITLE = "Custody no-registered-tool negative control"
ALLOW_TITLE_PREFIX = "Custody temporary lookup admission/"
_PROOF_ID = re.compile(r"[0-9a-f]{32}")
_PROJECTION = re.compile(
    rf"projects/{PROJECT_NUMBER}/locations/{REGION}/mcpServers/"
    r"(?P<id>[A-Za-z0-9-]+)"
)
_TEMPORARY_ALLOW = re.compile(
    r"api\.getAttribute\('iap\.googleapis\.com/mcp\.toolName', ''\) == '' \|\| "
    r"\(request\.time < timestamp\('(?P<expires>[^']+)'\) && "
    r"api\.getAttribute\('iap\.googleapis\.com/mcp\.toolName', ''\) == "
    r"'lookup_customer'\)"
)


def _canonical_etag(value: object) -> str:
    """IAP etags are opaque base64. ``gcloud ... get-iam-policy`` returns the
    URL-safe alphabet (``-``/``_``); the same value inside a raw Admin
    Activity audit payload has been observed in the standard alphabet
    (``+``/``/``). Compare on one canonical form so an equivalent etag is not
    rejected as a different one.
    """
    return str(value).replace("-", "+").replace("_", "/")


def _rfc3339_seconds(value: datetime) -> str:
    """Return the one canonical timestamp representation used in policy CEL."""
    if value.tzinfo is None:
        raise ValueError("policy expiry must include a timezone")
    return (
        value.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class TemporaryAdmission:
    """One proof-owned, server-expiring IAP admission lease."""

    proof_id: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if _PROOF_ID.fullmatch(self.proof_id) is None:
            raise ValueError("temporary admission proof_id is malformed")
        if self.expires_at.tzinfo is None:
            raise ValueError("temporary admission expiry has no timezone")
        object.__setattr__(
            self,
            "expires_at",
            self.expires_at.astimezone(UTC).replace(microsecond=0),
        )

    @property
    def title(self) -> str:
        return f"{ALLOW_TITLE_PREFIX}{self.proof_id}"

    @property
    def expression(self) -> str:
        """Handshake passthrough stays independent of the expiring tool lease.

        The empty-name clause never depends on ``request.time``, so MCP
        initialize and other unclassified handshake traffic keeps working
        after the lease expires. Only the registered tool name is time-boxed.
        """
        expires = _rfc3339_seconds(self.expires_at)
        return (
            "api.getAttribute('iap.googleapis.com/mcp.toolName', '') == '' || "
            f"(request.time < timestamp('{expires}') && "
            "api.getAttribute('iap.googleapis.com/mcp.toolName', '') == "
            "'lookup_customer')"
        )


class ActiveAdmissionError(RuntimeError):
    """Another unexpired proof owns the dedicated IAP mutation boundary."""


class GatewayProofError(RuntimeError):
    """Carry both the primary failure and cleanup/readback evidence."""

    def __init__(
        self,
        *,
        proof_id: str,
        phase: str,
        primary: BaseException,
        recovery_error: BaseException | None,
        final_policy: dict[str, Any] | None,
        allow_expires_at: str | None,
    ) -> None:
        super().__init__(f"Gateway proof failed during {phase}: {primary}")
        self.proof_id = proof_id
        self.phase = phase
        self.primary = primary
        self.recovery_error = recovery_error
        self.final_policy = final_policy
        self.allow_expires_at = allow_expires_at


@dataclass(frozen=True)
class Cloud:
    """Run gcloud only against Custody's isolated authenticated configuration."""

    def run(self, *arguments: str, capture: bool = False) -> str:
        environment = os.environ.copy()
        environment["CLOUDSDK_CONFIG"] = str(CONFIG)
        environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
        completed = subprocess.run(
            [
                "gcloud",
                *arguments,
                f"--project={PROJECT}",
                "--quiet",
            ],
            check=True,
            capture_output=capture,
            text=True,
            env=environment,
            timeout=GCLOUD_TIMEOUT_SECONDS,
        )
        return completed.stdout

    def json(self, *arguments: str) -> Any:
        return json.loads(self.run(*arguments, "--format=json", capture=True))


@dataclass(frozen=True)
class RuntimeHandle:
    """Keep the SDK client alive with the Runtime transport it owns."""

    client: Client
    engine: Any
    resource: dict[str, Any]


@dataclass(frozen=True)
class PolicyApplication:
    """One etag-guarded IAP policy transition and its server readback."""

    previous: dict[str, Any]
    applied: dict[str, Any]
    applied_at: str


def _temporary_admission(
    policy: dict[str, Any], *, principal: str
) -> TemporaryAdmission | None:
    """Parse only Custody's canonical proof lease; reject lookalike CEL."""
    bindings = policy.get("bindings", [])
    if policy.get("version") != 3 or len(bindings) != 1:
        return None
    binding = bindings[0]
    if not isinstance(binding, dict):
        return None
    condition = binding.get("condition", {})
    if (
        binding.get("role") != "roles/iap.egressor"
        or binding.get("members") != [principal]
        or not isinstance(condition, dict)
    ):
        return None
    title = str(condition.get("title", ""))
    if not title.startswith(ALLOW_TITLE_PREFIX):
        return None
    proof_id = title.removeprefix(ALLOW_TITLE_PREFIX)
    if _PROOF_ID.fullmatch(proof_id) is None:
        return None
    expression = str(condition.get("expression", ""))
    match = _TEMPORARY_ALLOW.fullmatch(expression)
    if match is None:
        return None
    expires_at = datetime.fromisoformat(
        match.group("expires").replace("Z", "+00:00")
    )
    admission = TemporaryAdmission(proof_id, expires_at)
    return admission if admission.expression == expression else None


@dataclass(frozen=True)
class DedicatedIapPolicy:
    """Own the only mutable boundary in this live proof.

    The Registry MCP projection is dedicated to Custody's synthetic proof. We
    still refuse to replace its IAP policy if another principal, role, or
    non-Custody binding is present. Every accepted replacement carries the
    immediately preceding server etag, so concurrent edits fail instead of
    being overwritten.
    """

    cloud: Cloud
    projection_id: str
    principal: str
    proof_id: str

    def __post_init__(self) -> None:
        if not self.projection_id or re.fullmatch(
            r"[A-Za-z0-9-]+", self.projection_id
        ) is None:
            raise ValueError("IAP projection ID is malformed")
        if self.principal != EXPECTED_PRINCIPAL:
            raise ValueError("IAP mutation principal is not the owned Runtime")
        if _PROOF_ID.fullmatch(self.proof_id) is None:
            raise ValueError("IAP mutation proof_id is malformed")

    def current(self) -> dict[str, Any]:
        """Read with bounded transient retries and validate every state."""
        last_error: BaseException | None = None
        for attempt in range(POLICY_ATTEMPTS):
            try:
                policy = self.cloud.json(
                    "iap",
                    "web",
                    "get-iam-policy",
                    "--resource-type=agent-registry",
                    f"--mcp-server={self.projection_id}",
                    f"--region={REGION}",
                )
                if not isinstance(policy, dict):
                    raise TypeError("IAP policy readback was not an object")
                self._require_exclusive_ownership(policy)
                return policy
            except (
                json.JSONDecodeError,
                OSError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as error:
                last_error = error
                if attempt + 1 < POLICY_ATTEMPTS:
                    time.sleep(attempt + 1)
        raise RuntimeError(
            "IAP policy readback failed after bounded retries"
        ) from last_error

    def prepare_safe_deny(self) -> dict[str, Any]:
        """Reject a live lease; repair an empty or expired dedicated policy."""
        current = self.current()
        if self._is_exact(current, expression=DENY_EXPRESSION, title=DENY_TITLE):
            return current
        admission = _temporary_admission(current, principal=self.principal)
        if admission is not None and admission.expires_at > datetime.now(UTC):
            raise ActiveAdmissionError(
                f"proof {admission.proof_id} owns IAP until "
                f"{_rfc3339_seconds(admission.expires_at)}"
            )
        return self.ensure_deny().applied

    def apply_temporary(self, admission: TemporaryAdmission) -> PolicyApplication:
        if admission.proof_id != self.proof_id:
            raise ValueError("cannot apply another proof's temporary admission")

        def source_is_safe(policy: dict[str, Any]) -> bool:
            return self._is_exact(
                policy, expression=DENY_EXPRESSION, title=DENY_TITLE
            )

        return self._apply_reconciled(
            expression=admission.expression,
            title=admission.title,
            phase="allow",
            source_is_safe=source_is_safe,
        )

    def ensure_deny(self) -> PolicyApplication:
        """Restore the safe state without stealing another proof's live lease."""

        def source_is_safe(policy: dict[str, Any]) -> bool:
            if policy.get("bindings") == []:
                return True
            if self._is_exact(
                policy, expression=DENY_EXPRESSION, title=DENY_TITLE
            ):
                return True
            admission = _temporary_admission(policy, principal=self.principal)
            return admission is not None and (
                admission.proof_id == self.proof_id
                or admission.expires_at <= datetime.now(UTC)
            )

        return self._apply_reconciled(
            expression=DENY_EXPRESSION,
            title=DENY_TITLE,
            phase="deny",
            source_is_safe=source_is_safe,
        )

    def _reject_unsafe_source(self, previous: dict[str, Any], *, phase: str) -> None:
        admission = _temporary_admission(previous, principal=self.principal)
        if admission is not None:
            raise ActiveAdmissionError(
                f"proof {admission.proof_id} owns the IAP policy"
            )
        raise RuntimeError(f"IAP {phase} source state is not replaceable")

    def _apply_reconciled(
        self,
        *,
        expression: str,
        title: str,
        phase: str,
        source_is_safe: Callable[[dict[str, Any]], bool],
    ) -> PolicyApplication:
        """Set with etag CAS; reconcile timeout/error by authoritative readback."""
        last_error: BaseException | None = None
        for attempt in range(POLICY_ATTEMPTS):
            previous = self.current()
            if self._is_exact(previous, expression=expression, title=title):
                return PolicyApplication(
                    previous=previous,
                    applied=previous,
                    applied_at=datetime.now(UTC).isoformat(),
                )
            if not source_is_safe(previous):
                self._reject_unsafe_source(previous, phase=phase)

            requested = {
                **_iap_policy(self.principal, expression, title=title),
                "etag": previous["etag"],
            }
            try:
                self._write_policy(requested, phase=phase)
            except (
                OSError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as error:
                last_error = error
            try:
                applied = self.current()
            except RuntimeError as error:
                last_error = error
                if attempt + 1 < POLICY_ATTEMPTS:
                    time.sleep(attempt + 1)
                continue
            if self._is_exact(applied, expression=expression, title=title):
                return PolicyApplication(
                    previous=previous,
                    applied=applied,
                    applied_at=datetime.now(UTC).isoformat(),
                )
            if applied.get("etag") != previous.get("etag"):
                raise RuntimeError(
                    f"IAP {phase} lost its etag race to another writer"
                ) from last_error
            if attempt + 1 < POLICY_ATTEMPTS:
                time.sleep(attempt + 1)
        raise RuntimeError(
            f"IAP {phase} did not reach its requested state after bounded retries"
        ) from last_error

    def _write_policy(self, requested: dict[str, Any], *, phase: str) -> None:
        path = OUT.parent / f"gateway-iap-{phase}-{self.proof_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(requested, indent=2, sort_keys=True) + "\n")
        try:
            self.cloud.run(
                "iap",
                "web",
                "set-iam-policy",
                str(path),
                "--resource-type=agent-registry",
                f"--mcp-server={self.projection_id}",
                f"--region={REGION}",
            )
        finally:
            path.unlink(missing_ok=True)

    def _require_exclusive_ownership(self, policy: dict[str, Any]) -> None:
        etag = policy.get("etag")
        if not etag:
            raise RuntimeError("IAP policy readback did not include an etag")
        bindings = policy.get("bindings", [])
        if not isinstance(bindings, list):
            raise RuntimeError("IAP policy bindings were not a list")
        if not bindings:
            return
        if len(bindings) != 1 or not isinstance(bindings[0], dict):
            raise RuntimeError("dedicated proof IAP policy has unrelated bindings")
        owned = self._is_exact(
            policy, expression=DENY_EXPRESSION, title=DENY_TITLE
        ) or _temporary_admission(
            policy, principal=self.principal
        ) is not None
        if not owned:
            raise RuntimeError("dedicated proof IAP policy has an unrelated binding")

    @staticmethod
    def _is_exact(
        policy: dict[str, Any],
        *,
        expression: str,
        title: str,
        principal: str = EXPECTED_PRINCIPAL,
    ) -> bool:
        bindings = policy.get("bindings", [])
        if len(bindings) != 1 or not isinstance(bindings[0], dict):
            return False
        binding = bindings[0]
        condition = binding.get("condition", {})
        return (
            policy.get("version") == 3
            and bool(policy.get("etag"))
            and binding.get("role") == "roles/iap.egressor"
            and binding.get("members") == [principal]
            and condition.get("title") == title
            and condition.get("expression") == expression
        )


def _json_get(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return json.loads(response.read())


def _only(items: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(items) != 1:
        raise RuntimeError(f"expected one {description}; received {len(items)}")
    return items[0]


def _projection_id(service: dict[str, Any]) -> str:
    match = _PROJECTION.fullmatch(str(service["registryResource"]))
    if match is None:
        raise ValueError("Registry service returned an unowned MCP projection")
    return match.group("id")


def _mcp_endpoint(service: dict[str, Any]) -> str:
    interfaces = service["interfaces"]
    if len(interfaces) != 1:
        raise RuntimeError("registered MCP service must expose one interface")
    interface = interfaces[0]
    endpoint = str(interface["url"])
    if (
        interface.get("protocolBinding") != "JSONRPC"
        or endpoint != EXPECTED_MCP_ENDPOINT
    ):
        raise ValueError("Registry interface is not the owned MCP endpoint")
    return endpoint


def _describe_resources(cloud: Cloud) -> dict[str, Any]:
    gateway = cloud.json(
        "network-services",
        "agent-gateways",
        "describe",
        GATEWAY_ID,
        f"--location={REGION}",
    )
    extension = cloud.json(
        "service-extensions",
        "authz-extensions",
        "describe",
        EXTENSION_ID,
        f"--location={REGION}",
    )
    authz_policy = cloud.json(
        "network-security",
        "authz-policies",
        "describe",
        AUTHZ_POLICY_ID,
        f"--location={REGION}",
    )
    service = cloud.json(
        "agent-registry",
        "services",
        "describe",
        SERVICE_ID,
        f"--location={REGION}",
    )
    projection = cloud.json(
        "agent-registry",
        "mcp-servers",
        "describe",
        _projection_id(service),
        f"--location={REGION}",
    )
    cloud_run = cloud.json(
        "run",
        "services",
        "describe",
        SERVICE_ID,
        f"--region={REGION}",
    )
    return {
        "gateway": gateway,
        "extension": extension,
        "authz_policy": authz_policy,
        "service": service,
        "projection": projection,
        "cloud_run": cloud_run,
    }


def _runtime_agent(cloud: Cloud) -> dict[str, Any]:
    for _ in range(20):
        agents = cloud.json(
            "agent-registry",
            "agents",
            "list",
            f"--location={REGION}",
        )
        matches = [
            agent
            for agent in agents
            if str(
                agent.get("attributes", {})
                .get(RUNTIME_REFERENCE, {})
                .get("uri", "")
            )
            == EXPECTED_RUNTIME_REFERENCE
            and agent.get("attributes", {})
            .get(RUNTIME_IDENTITY, {})
            .get("principal")
            == EXPECTED_PRINCIPAL
        ]
        if matches:
            return _only(matches, "Registry Agent bound to the Gateway Runtime")
        time.sleep(3)
    raise RuntimeError("Gateway Runtime did not appear in Agent Registry")


def _require_mutation_targets(
    resources: dict[str, Any], *, agent: dict[str, Any], endpoint: str
) -> None:
    """Validate every identity and resource before touching the IAP policy."""
    gateway = resources["gateway"]
    extension = resources["extension"]
    authz = resources["authz_policy"]
    service = resources["service"]
    projection = resources["projection"]
    cloud_run = resources["cloud_run"]
    projection_id = _projection_id(service)
    expected_gateway = (
        f"projects/{PROJECT}/locations/{REGION}/agentGateways/{GATEWAY_ID}"
    )
    expected_extension = (
        f"projects/{PROJECT}/locations/{REGION}/authzExtensions/{EXTENSION_ID}"
    )
    expected_authz = (
        f"projects/{PROJECT}/locations/{REGION}/authzPolicies/{AUTHZ_POLICY_ID}"
    )
    expected_service = (
        f"projects/{PROJECT}/locations/{REGION}/services/{SERVICE_ID}"
    )
    expected_projection_names = {
        f"projects/{owner}/locations/{REGION}/mcpServers/{projection_id}"
        for owner in (PROJECT, PROJECT_NUMBER)
    }
    target_names = set(authz.get("target", {}).get("resources", []))
    extension_names = set(
        authz.get("customProvider", {})
        .get("authzExtension", {})
        .get("resources", [])
    )
    valid_gateway_targets = {
        expected_gateway,
        f"projects/{PROJECT_NUMBER}/locations/{REGION}/agentGateways/{GATEWAY_ID}",
    }
    valid_extension_targets = {
        expected_extension,
        f"projects/{PROJECT_NUMBER}/locations/{REGION}/authzExtensions/{EXTENSION_ID}",
    }
    runtime_uri = (
        agent.get("attributes", {}).get(RUNTIME_REFERENCE, {}).get("uri")
    )
    runtime_principal = (
        agent.get("attributes", {}).get(RUNTIME_IDENTITY, {}).get("principal")
    )
    base_url = endpoint.removesuffix("/mcp")
    conditions = cloud_run.get("status", {}).get("conditions", [])
    safe = (
        gateway.get("name") == expected_gateway
        and gateway.get("protocols") == ["MCP"]
        and gateway.get("googleManaged", {}).get("governedAccessPath")
        == "AGENT_TO_ANYWHERE"
        and extension.get("name") == expected_extension
        and extension.get("service") == "iap.googleapis.com"
        and extension.get("metadata") == {"iapPolicyVersion": "V1"}
        and extension.get("failOpen", False) is False
        and authz.get("name") == expected_authz
        and authz.get("action") == "CUSTOM"
        and authz.get("policyProfile", "REQUEST_AUTHZ") == "REQUEST_AUTHZ"
        and target_names <= valid_gateway_targets
        and len(target_names) == 1
        and extension_names <= valid_extension_targets
        and len(extension_names) == 1
        and service.get("name") == expected_service
        and projection.get("name") in expected_projection_names
        and _mcp_endpoint(service) == endpoint
        and _mcp_endpoint(projection) == endpoint
        and cloud_run.get("metadata", {}).get("name") == SERVICE_ID
        and str(cloud_run.get("metadata", {}).get("namespace"))
        == PROJECT_NUMBER
        and cloud_run.get("metadata", {}).get("labels", {}).get(
            "cloud.googleapis.com/location"
        )
        == REGION
        and cloud_run.get("status", {}).get("url") == base_url
        and cloud_run.get("status", {}).get("latestReadyRevisionName")
        == cloud_run.get("status", {}).get("latestCreatedRevisionName")
        and any(
            condition.get("type") == "Ready"
            and condition.get("status") == "True"
            for condition in conditions
            if isinstance(condition, dict)
        )
        and runtime_uri == EXPECTED_RUNTIME_REFERENCE
        and runtime_principal == EXPECTED_PRINCIPAL
    )
    if not safe:
        raise RuntimeError("owned Gateway mutation target validation failed")


def _iap_policy(principal: str, expression: str, *, title: str) -> dict[str, Any]:
    return {
        "version": 3,
        "bindings": [
            {
                "role": "roles/iap.egressor",
                "members": [principal],
                "condition": {"title": title, "expression": expression},
            }
        ],
    }


def _enforce_extension(cloud: Cloud, proof_id: str) -> dict[str, Any]:
    """Remove DRY_RUN and read back the server-normalized extension."""
    current = cloud.json(
        "service-extensions",
        "authz-extensions",
        "describe",
        EXTENSION_ID,
        f"--location={REGION}",
    )
    if current.get("metadata") == {"iapPolicyVersion": "V1"}:
        return current

    path = OUT.parent / f"gateway-extension-enforced-{proof_id}.yaml"
    path.write_text(
        "\n".join(
            (
                f"name: {EXTENSION_ID}",
                "service: iap.googleapis.com",
                "failOpen: false",
                "timeout: 1s",
                "metadata:",
                '  iapPolicyVersion: "V1"',
                "",
            )
        )
    )
    try:
        cloud.run(
            "service-extensions",
            "authz-extensions",
            "import",
            EXTENSION_ID,
            f"--source={path}",
            f"--location={REGION}",
        )
    finally:
        path.unlink(missing_ok=True)
    extension = cloud.json(
        "service-extensions",
        "authz-extensions",
        "describe",
        EXTENSION_ID,
        f"--location={REGION}",
    )
    if extension.get("metadata") != {"iapPolicyVersion": "V1"}:
        raise RuntimeError("AuthzExtension is not in enforced IAP V1 mode")
    return extension


def _wait_for_iap_convergence(phase: str) -> None:
    """Respect IAM's eventual-consistency window before one control action."""
    print(
        f"Waiting {IAP_PROPAGATION_SECONDS}s for IAP {phase} convergence...",
        flush=True,
    )
    deadline = time.monotonic() + IAP_PROPAGATION_SECONDS
    next_update = time.monotonic() + 30
    while (remaining := deadline - time.monotonic()) > 0:
        time.sleep(min(5, remaining))
        if time.monotonic() >= next_update:
            print(f"IAP {phase} convergence still in progress...", flush=True)
            next_update += 30


def _wait_for_server_expiry(expires_at: datetime) -> None:
    """Wait for the CEL request.time boundary plus a small clock margin."""
    target = expires_at.astimezone(UTC) + timedelta(seconds=5)
    print(
        "Waiting for the server-enforced temporary admission to expire...",
        flush=True,
    )
    next_update = time.monotonic() + 30
    while (remaining := (target - datetime.now(UTC)).total_seconds()) > 0:
        time.sleep(min(5, remaining))
        if time.monotonic() >= next_update:
            print(
                f"Temporary admission expires in {max(0, int(remaining))}s...",
                flush=True,
            )
            next_update += 30


def _require_allow_control(
    before: dict[str, Any], result: dict[str, Any], after: dict[str, Any]
) -> None:
    dispatched_once = (
        result.get("ok") is True
        and before.get("instance_id") == after.get("instance_id")
        and isinstance(before.get("dispatch_count"), int)
        and after.get("dispatch_count") == before["dispatch_count"] + 1
    )
    if not dispatched_once:
        details = {"before": before, "result": result, "after": after}
        raise RuntimeError(
            "allow control did not dispatch exactly once: "
            + json.dumps(details, sort_keys=True)
        )


def _require_deny_control(
    before: dict[str, Any], result: dict[str, Any], after: dict[str, Any]
) -> None:
    error = str(result.get("error", "")).casefold()
    denied_without_dispatch = (
        result.get("ok") is False
        and bool(result.get("error_type"))
        and "403" in error
        and "forbidden" in error
        and before == after
    )
    if not denied_without_dispatch:
        details = {"before": before, "result": result, "after": after}
        raise RuntimeError(
            "deny control did not fail before dispatch: "
            + json.dumps(details, sort_keys=True)
        )


def _require_scope_control(
    before: dict[str, Any], result: dict[str, Any], after: dict[str, Any]
) -> None:
    """Prove temporary admission is tool-scoped rather than a broad allow."""
    error = str(result.get("error", "")).casefold()
    scoped = (
        result.get("ok") is False
        and result.get("tool_name") == DENY_CANARY
        and "403" in error
        and "forbidden" in error
        and before == after
    )
    if not scoped:
        raise RuntimeError(
            "temporary admission did not reject the non-admitted tool: "
            + json.dumps(
                {"before": before, "result": result, "after": after},
                sort_keys=True,
            )
        )


def _agent_engine() -> RuntimeHandle:
    if not ADC.exists():
        raise RuntimeError(
            "repo-local ADC is absent; run gcloud auth application-default login"
        )
    credentials, _ = load_credentials_from_file(
        ADC,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = Client(
        credentials=credentials,
        project=PROJECT,
        location=REGION,
    )
    engine = client.agent_engines.get(
        name=(
            f"projects/{PROJECT_NUMBER}/locations/{REGION}/reasoningEngines/"
            f"{ENGINE_ID}"
        )
    )
    # Version 1.163 exposes the operation schema but can fail to bind it while
    # deserializing. Registering from that server-owned schema uses the same
    # installed SDK wrapper; it does not call a private transport directly.
    if not callable(getattr(engine, "async_query", None)):
        _agent_engines_utils._register_api_methods_or_raise(agent_engine=engine)
    if engine.api_resource is None:
        raise RuntimeError("Agent Platform returned no Runtime API resource")
    raw = engine.api_resource.model_dump(mode="json", by_alias=True, exclude_none=True)
    return RuntimeHandle(client=client, engine=engine, resource=raw)


async def _invoke(
    engine: Any,
    *,
    customer_id: str,
    trace_id: str,
    proof_id: str,
    tool_name: str = TOOL_NAME,
) -> dict[str, Any]:
    result = await asyncio.wait_for(
        engine.async_query(
            customer_id=customer_id,
            trace_id=trace_id,
            proof_id=proof_id,
            tool_name=tool_name,
            http_options={
                "headers": {
                    "traceparent": f"00-{trace_id}-0000000000000001-01",
                },
            },
        ),
        timeout=RUNTIME_QUERY_TIMEOUT_SECONDS,
    )
    if not isinstance(result, dict):
        raise TypeError("Gateway Runtime returned a non-object result")
    return result


def _gateway_logs(
    cloud: Cloud, trace_id: str, *, tool_name: str = TOOL_NAME
) -> list[dict[str, Any]]:
    query = (
        'resource.type="networkservices.googleapis.com/Gateway" '
        f'AND trace="{trace_id}"'
    )
    last: list[dict[str, Any]] = []
    for _ in range(GATEWAY_LOG_POLL_ATTEMPTS):
        try:
            last = cloud.json(
                "logging",
                "read",
                query,
                "--freshness=1h",
                "--order=asc",
                "--limit=100",
            )
        except (
            json.JSONDecodeError,
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            time.sleep(GATEWAY_LOG_POLL_INTERVAL_SECONDS)
            continue
        tool_logs = [
            entry
            for entry in last
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
        if tool_logs:
            return tool_logs
        time.sleep(GATEWAY_LOG_POLL_INTERVAL_SECONDS)
    bound = GATEWAY_LOG_POLL_ATTEMPTS * GATEWAY_LOG_POLL_INTERVAL_SECONDS
    raise RuntimeError(
        f"no trace-bound Gateway tools/call log for {trace_id} within "
        f"{bound}s: {last}"
    )


def _server_dispatch_log(
    cloud: Cloud, *, proof_id: str, trace_id: str, customer_id: str
) -> dict[str, Any]:
    """Read the one Cloud Run-authored event binding this exact dispatch."""
    query = " AND ".join(
        (
            'resource.type="cloud_run_revision"',
            f'resource.labels.service_name="{SERVICE_ID}"',
            'jsonPayload.event="custody.gateway.lookup.dispatched.v1"',
            f'jsonPayload.proof_id="{proof_id}"',
            f'jsonPayload.trace_id="{trace_id}"',
            f'jsonPayload.customer_id="{customer_id}"',
        )
    )
    last: list[dict[str, Any]] = []
    for _ in range(18):
        try:
            last = cloud.json(
                "logging",
                "read",
                query,
                "--freshness=1h",
                "--order=asc",
                "--limit=10",
            )
        except (
            json.JSONDecodeError,
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            time.sleep(5)
            continue
        if isinstance(last, list) and len(last) == 1:
            return last[0]
        time.sleep(5)
    raise RuntimeError(
        "no unique server-authored dispatch log for this proof: "
        f"{last}"
    )


def _iap_audit_logs(
    cloud: Cloud,
    *,
    projection_id: str,
    principal: str,
    initial_etag: str,
    allow_etag: str,
    deny_etag: str,
) -> dict[str, dict[str, Any]]:
    """Read the server-authored etag chain for both IAP policy writes."""
    resource = (
        f"projects/{PROJECT_NUMBER}/locations/{REGION}/iap_web/agentRegistry/"
        f"mcpServers/{projection_id}"
    )
    query = (
        'protoPayload.methodName="google.cloud.iap.v1.'
        'IdentityAwareProxyAdminService.SetIamPolicy" '
        f'AND protoPayload.resourceName="{resource}"'
    )

    def matches(
        entry: dict[str, Any], *, before: str, after: str
    ) -> bool:
        payload = entry.get("protoPayload", {})
        request = payload.get("request", {})
        requested = request.get("policy", {})
        response = payload.get("response", {})
        expected_binding = {
            "members": [principal],
            "role": "roles/iap.egressor",
        }
        auth = payload.get("authenticationInfo", {})
        principal_email = auth.get("principalEmail")
        authorization = payload.get("authorizationInfo", [])
        return (
            entry.get("logName")
            == f"projects/{PROJECT}/logs/cloudaudit.googleapis.com%2Factivity"
            and bool(entry.get("insertId"))
            and entry.get("resource", {}).get("type") == "audited_resource"
            and entry.get("resource", {}).get("labels", {}).get("project_id")
            == PROJECT
            and payload.get("serviceName") == "iap.googleapis.com"
            and payload.get("methodName")
            == (
                "google.cloud.iap.v1.IdentityAwareProxyAdminService."
                "SetIamPolicy"
            )
            and payload.get("resourceName") == resource
            and isinstance(principal_email, str)
            and bool(principal_email)
            and auth.get("principalSubject") == f"user:{principal_email}"
            and len(authorization) == 1
            and authorization[0].get("granted") is True
            and authorization[0].get("permission")
            == "iap.webServices.setIamPolicy"
            and payload.get("status") == {}
            and request.get("resource") == resource
            and _canonical_etag(requested.get("etag")) == _canonical_etag(before)
            and _canonical_etag(response.get("etag")) == _canonical_etag(after)
            and requested.get("bindings") == [expected_binding]
            and response.get("bindings") == [expected_binding]
        )

    last: list[dict[str, Any]] = []
    for _ in range(18):
        try:
            last = cloud.json(
                "logging",
                "read",
                query,
                "--freshness=1h",
                "--order=asc",
                "--limit=200",
            )
        except (
            json.JSONDecodeError,
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            time.sleep(5)
            continue
        allow = [
            entry
            for entry in last
            if matches(entry, before=initial_etag, after=allow_etag)
        ]
        deny = [
            entry
            for entry in last
            if matches(entry, before=allow_etag, after=deny_etag)
        ]
        if len(allow) == len(deny) == 1:
            return {"allow": allow[0], "deny": deny[0]}
        time.sleep(5)
    raise RuntimeError(f"IAP audit log etag chain was incomplete: {last}")


def _best_effort_policy(iap: DedicatedIapPolicy | None) -> dict[str, Any] | None:
    if iap is None:
        return None
    try:
        return iap.current()
    except Exception:
        return None


async def _prove(proof_id: str) -> dict[str, Any]:
    cloud = Cloud()
    started_at = datetime.now(UTC).isoformat()
    phase = "resource_validation"
    iap: DedicatedIapPolicy | None = None
    admission: TemporaryAdmission | None = None
    allow_application: PolicyApplication | None = None
    deny_application: PolicyApplication | None = None
    try:
        resources = _describe_resources(cloud)
        service = resources["service"]
        projection_id = _projection_id(service)
        endpoint = _mcp_endpoint(service)
        agent = _runtime_agent(cloud)
        principal = agent["attributes"][RUNTIME_IDENTITY]["principal"]
        _require_mutation_targets(resources, agent=agent, endpoint=endpoint)
        runtime = _agent_engine()
        expected_engine_name = (
            f"projects/{PROJECT_NUMBER}/locations/{REGION}/reasoningEngines/"
            f"{ENGINE_ID}"
        )
        if runtime.resource.get("name") != expected_engine_name:
            raise RuntimeError("Agent Platform returned an unowned Runtime")

        resources["extension"] = _enforce_extension(cloud, proof_id)
        resources["authz_policy"] = cloud.json(
            "network-security",
            "authz-policies",
            "describe",
            AUTHZ_POLICY_ID,
            f"--location={REGION}",
        )
        _require_mutation_targets(resources, agent=agent, endpoint=endpoint)

        iap = DedicatedIapPolicy(
            cloud,
            projection_id=projection_id,
            principal=principal,
            proof_id=proof_id,
        )
        phase = "startup_reconciliation"
        initial_policy = iap.prepare_safe_deny()
        admission = TemporaryAdmission(
            proof_id=proof_id,
            expires_at=datetime.now(UTC) + TEMPORARY_ALLOW_TTL,
        )
        phase = "temporary_allow"
        allow_application = iap.apply_temporary(admission)
        _wait_for_iap_convergence("allow")
        if datetime.now(UTC) >= admission.expires_at:
            raise RuntimeError("temporary IAP admission expired before control")
        phase = "allow_control"
        allow_trace = uuid.uuid4().hex
        allow_customer = f"custody-gateway-{proof_id}-allow"
        allow_before = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
        allow_result = await _invoke(
            runtime.engine,
            customer_id=allow_customer,
            trace_id=allow_trace,
            proof_id=proof_id,
        )
        allow_after = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
        _require_allow_control(allow_before, allow_result, allow_after)
        allow_logs = _gateway_logs(cloud, allow_trace)
        dispatch_log = _server_dispatch_log(
            cloud,
            proof_id=proof_id,
            trace_id=allow_trace,
            customer_id=allow_customer,
        )
        phase = "allow_scope_control"
        scope_trace = uuid.uuid4().hex
        scope_customer = f"custody-gateway-{proof_id}-deny"
        scope_before = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
        scope_result = await _invoke(
            runtime.engine,
            customer_id=scope_customer,
            trace_id=scope_trace,
            proof_id=proof_id,
            tool_name=DENY_CANARY,
        )
        scope_after = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
        _require_scope_control(scope_before, scope_result, scope_after)
        scope_logs = _gateway_logs(
            cloud, scope_trace, tool_name=DENY_CANARY
        )
        phase = "allow_expiry_control"
        _wait_for_server_expiry(admission.expires_at)
        expiry_trace = uuid.uuid4().hex
        expiry_customer = f"custody-gateway-{proof_id}-deny"
        expiry_before = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
        expiry_result = await _invoke(
            runtime.engine,
            customer_id=expiry_customer,
            trace_id=expiry_trace,
            proof_id=proof_id,
        )
        expiry_after = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
        _require_deny_control(expiry_before, expiry_result, expiry_after)
        expiry_logs = _gateway_logs(cloud, expiry_trace)
        phase = "safe_deny_restore"
        deny_application = iap.ensure_deny()
    except Exception as primary:
        recovery_error: BaseException | None = None
        if iap is not None:
            try:
                iap.ensure_deny()
            except Exception as error:
                recovery_error = error
        raise GatewayProofError(
            proof_id=proof_id,
            phase=phase,
            primary=primary,
            recovery_error=recovery_error,
            final_policy=_best_effort_policy(iap),
            allow_expires_at=(
                _rfc3339_seconds(admission.expires_at)
                if admission is not None
                else None
            ),
        ) from primary

    if (
        iap is None
        or admission is None
        or allow_application is None
        or deny_application is None
    ):
        raise RuntimeError("IAP policy transition evidence is incomplete")
    phase = "deny_control"
    _wait_for_iap_convergence("deny")
    deny_trace = uuid.uuid4().hex
    deny_customer = f"custody-gateway-{proof_id}-deny"
    deny_before = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
    deny_result = await _invoke(
        runtime.engine,
        customer_id=deny_customer,
        trace_id=deny_trace,
        proof_id=proof_id,
    )
    deny_after = _json_get(endpoint.removesuffix("/mcp") + "/evidence")
    _require_deny_control(deny_before, deny_result, deny_after)

    phase = "log_collection"
    deny_logs = _gateway_logs(cloud, deny_trace)
    iap_audit_logs = _iap_audit_logs(
        cloud,
        projection_id=projection_id,
        principal=principal,
        initial_etag=initial_policy["etag"],
        allow_etag=allow_application.applied["etag"],
        deny_etag=deny_application.applied["etag"],
    )
    captured_at = datetime.now(UTC).isoformat()
    return {
        "schema_version": 2,
        "proof_id": proof_id,
        "started_at": started_at,
        "captured_at": captured_at,
        "project": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "claim_boundary": CLAIM_BOUNDARY,
        "gateway": resources["gateway"],
        "extension": resources["extension"],
        "authz_policy": resources["authz_policy"],
        "cloud_run": resources["cloud_run"],
        "registry": {
            "service": service,
            "projection": resources["projection"],
            "iap_policy_initial": initial_policy,
            "iap_policy_allow": allow_application.applied,
            "iap_policy_allow_applied_at": allow_application.applied_at,
            "iap_policy_allow_expires_at": _rfc3339_seconds(
                admission.expires_at
            ),
            "iap_policy_deny": deny_application.applied,
            "iap_policy_deny_applied_at": deny_application.applied_at,
            "iap_policy_audit_logs": iap_audit_logs,
        },
        "runtime": {
            "agent_engine": runtime.resource,
            "registered_agent": agent,
        },
        "allow_control": {
            "trace_id": allow_trace,
            "customer_id": allow_customer,
            "result": allow_result,
            "evidence_before": allow_before,
            "evidence_after": allow_after,
        },
        "scope_control": {
            "trace_id": scope_trace,
            "customer_id": scope_customer,
            "tool_name": DENY_CANARY,
            "result": scope_result,
            "evidence_before": scope_before,
            "evidence_after": scope_after,
        },
        "expiry_control": {
            "trace_id": expiry_trace,
            "customer_id": expiry_customer,
            "tool_name": TOOL_NAME,
            "result": expiry_result,
            "evidence_before": expiry_before,
            "evidence_after": expiry_after,
        },
        "deny_control": {
            "trace_id": deny_trace,
            "customer_id": deny_customer,
            "result": deny_result,
            "evidence_before": deny_before,
            "evidence_after": deny_after,
        },
        "gateway_logs": {
            "allow": allow_logs,
            "scope": scope_logs,
            "expiry": expiry_logs,
            "deny": deny_logs,
        },
        "server_dispatch_log": dispatch_log,
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.unlink(missing_ok=True)
    FAILURE.unlink(missing_ok=True)
    proof_id = uuid.uuid4().hex
    try:
        evidence = asyncio.run(_prove(proof_id))
    except Exception as error:
        failure = {
            "schema_version": 1,
            "proof_id": proof_id,
            "captured_at": datetime.now(UTC).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if isinstance(error, GatewayProofError):
            failure.update(
                {
                    "phase": error.phase,
                    "primary_error_type": type(error.primary).__name__,
                    "primary_error": str(error.primary),
                    "recovery_error_type": (
                        type(error.recovery_error).__name__
                        if error.recovery_error is not None
                        else None
                    ),
                    "recovery_error": (
                        str(error.recovery_error)
                        if error.recovery_error is not None
                        else None
                    ),
                    "allow_expires_at": error.allow_expires_at,
                    "final_policy_readback": error.final_policy,
                    "safe_deny_restored": (
                        error.final_policy is not None
                        and DedicatedIapPolicy._is_exact(
                            error.final_policy,
                            expression=DENY_EXPRESSION,
                            title=DENY_TITLE,
                        )
                    ),
                }
            )
        FAILURE.write_text(json.dumps(failure, indent=2) + "\n")
        raise
    OUT.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    print(f"Gateway evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
