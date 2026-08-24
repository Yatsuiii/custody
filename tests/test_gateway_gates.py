"""Adversarial tests for the independent Agent Gateway evidence judge."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime, timedelta

from scripts.gateway_gates import CLAIM_BOUNDARY, judge

NOW = datetime(2026, 8, 13, 8, tzinfo=UTC)
PROOF_ID = "0123456789abcdef0123456789abcdef"
PROJECT = "project-1"
PROJECT_NUMBER = "123456789"
REGION = "us-central1"
ENGINE_ID = "987654321"
GATEWAY_ID = "custody-fleet-egress"
GATEWAY = f"projects/{PROJECT}/locations/{REGION}/agentGateways/{GATEWAY_ID}"
GATEWAY_NUMBER = (
    f"projects/{PROJECT_NUMBER}/locations/{REGION}/agentGateways/{GATEWAY_ID}"
)
EXTENSION = (
    f"projects/{PROJECT}/locations/{REGION}/authzExtensions/custody-fleet-iap-enforced"
)
EXTENSION_NUMBER = (
    f"projects/{PROJECT_NUMBER}/locations/{REGION}/authzExtensions/"
    "custody-fleet-iap-enforced"
)
MCP_ID = "agentregistry-00000000-0000-0000-abcd-0123456789ab"
MCP_RESOURCE = f"projects/{PROJECT}/locations/{REGION}/mcpServers/{MCP_ID}"
MCP_REGISTRY_REFERENCE = (
    f"projects/{PROJECT_NUMBER}/locations/{REGION}/mcpServers/{MCP_ID}"
)
MCP_URL = "https://custody-export-mcp-abc-uc.a.run.app/mcp"
ENGINE = f"projects/{PROJECT_NUMBER}/locations/{REGION}/reasoningEngines/{ENGINE_ID}"
PRINCIPAL = (
    "principal://agents.global.org-123.system.id.goog/resources/aiplatform/"
    f"projects/{PROJECT_NUMBER}/locations/{REGION}/reasoningEngines/{ENGINE_ID}"
)
AUTHZ_OWNER = "396106114361"
CLIENT_CERT_FINGERPRINT = "fixture-client-cert-sha256"
IAP_RESOURCE = (
    f"projects/{PROJECT_NUMBER}/locations/{REGION}/iap_web/agentRegistry/"
    f"mcpServers/{MCP_ID}"
)


def _times() -> dict[str, str]:
    return {
        "createTime": (NOW - timedelta(hours=2)).isoformat(),
        "updateTime": (NOW - timedelta(hours=1)).isoformat(),
    }


def _policy(expression: str, etag: str, *, title: str) -> dict:
    return {
        "bindings": [
            {
                "role": "roles/iap.egressor",
                "members": [PRINCIPAL],
                "condition": {
                    "title": title,
                    "expression": expression,
                },
            }
        ],
        "etag": etag,
        "version": 3,
    }


def _ledger(
    count: int,
    *,
    last: str | None,
    instance: str = "instance-1",
) -> dict:
    return {
        "revision": "v2",
        "instance_id": instance,
        "dispatch_count": count,
        "forwarding_dispatch_count": 0,
        "last_dispatched_at": last,
    }


def _gateway_log(
    *,
    trace_id: str,
    status: int,
    result: str,
    timestamp: datetime,
    tool_name: str = "lookup_customer",
) -> dict:
    return {
        "insertId": f"insert-{trace_id}",
        "timestamp": timestamp.isoformat(),
        "receiveTimestamp": (timestamp + timedelta(seconds=1)).isoformat(),
        "trace": trace_id,
        "traceSampled": True,
        "logName": (
            f"projects/{PROJECT}/logs/networkservices.googleapis.com%2Fgateway_requests"
        ),
        "resource": {
            "type": "networkservices.googleapis.com/Gateway",
            "labels": {
                "resource_container": f"projects/{PROJECT_NUMBER}",
                "location": REGION,
                "gateway_name": GATEWAY_ID,
                "gateway_type": "SECURE_WEB_GATEWAY",
                "network_name": "custody-managed-gateway-network",
            },
        },
        "httpRequest": {
            "requestMethod": "POST",
            "requestUrl": MCP_URL,
            "status": status,
            **({"serverIp": "34.143.72.2:443"} if status == 200 else {}),
        },
        "jsonPayload": {
            "authzPolicyInfo": {
                "result": result,
                "policies": [
                    {
                        "name": (
                            f"projects/{AUTHZ_OWNER}/locations/"
                            f"{REGION}/authzPolicies/"
                            "custody-fleet-request-authz"
                        ),
                        "result": result,
                    }
                ],
            },
            "mtls": {
                "clientCertSha256Fingerprint": CLIENT_CERT_FINGERPRINT,
            },
            "agentGatewayInfo": {
                "agentRegistryResource": MCP_RESOURCE,
                "mcpInfo": {
                    "method": "tools/call",
                    "parameter": tool_name,
                },
            },
        },
    }


def _server_dispatch_log(
    *, trace_id: str, customer_id: str, timestamp: datetime
) -> dict:
    dispatched_at = (timestamp - timedelta(milliseconds=100)).isoformat()
    return {
        "insertId": "server-dispatch-1",
        "logName": f"projects/{PROJECT}/logs/run.googleapis.com%2Fstdout",
        "timestamp": timestamp.isoformat(),
        "receiveTimestamp": (timestamp + timedelta(seconds=1)).isoformat(),
        "severity": "INFO",
        "resource": {
            "type": "cloud_run_revision",
            "labels": {
                "project_id": PROJECT,
                "location": REGION,
                "service_name": "custody-export-mcp",
                "revision_name": "custody-export-mcp-00002",
            },
        },
        "jsonPayload": {
            "severity": "INFO",
            "message": "Custody Gateway lookup reached the owned MCP handler",
            "event": "custody.gateway.lookup.dispatched.v1",
            "proof_id": PROOF_ID,
            "trace_id": trace_id,
            "customer_id": customer_id,
            "instance_id": "instance-1",
            "dispatch_id": 8,
            "forwarding_requested": False,
            "forwarding_dispatch_count": 0,
            "revision": "v2",
            "server_dispatched_at": dispatched_at,
        },
    }


def _iap_audit_log(
    *, before_etag: str, after_etag: str, timestamp: datetime, insert_id: str
) -> dict:
    binding = {"members": [PRINCIPAL], "role": "roles/iap.egressor"}
    return {
        "insertId": insert_id,
        "logName": (f"projects/{PROJECT}/logs/cloudaudit.googleapis.com%2Factivity"),
        "timestamp": timestamp.isoformat(),
        "receiveTimestamp": (timestamp + timedelta(seconds=1)).isoformat(),
        "resource": {
            "type": "audited_resource",
            "labels": {"project_id": PROJECT},
        },
        "protoPayload": {
            "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
            "authenticationInfo": {
                "principalEmail": "owner@example.invalid",
                "principalSubject": "user:owner@example.invalid",
            },
            "authorizationInfo": [
                {
                    "granted": True,
                    "permission": "iap.webServices.setIamPolicy",
                    "permissionType": "ADMIN_WRITE",
                    "resourceAttributes": {
                        "name": IAP_RESOURCE,
                        "service": "iap.googleapis.com",
                        "type": "iap.googleapis.com/WebService",
                    },
                }
            ],
            "methodName": (
                "google.cloud.iap.v1.IdentityAwareProxyAdminService.SetIamPolicy"
            ),
            "request": {
                "@type": "type.googleapis.com/google.iam.v1.SetIamPolicyRequest",
                "policy": {"bindings": [binding], "etag": before_etag},
                "resource": IAP_RESOURCE,
            },
            "resourceName": IAP_RESOURCE,
            "response": {
                "@type": "type.googleapis.com/google.iam.v1.Policy",
                "bindings": [binding],
                "etag": after_etag,
            },
            "serviceName": "iap.googleapis.com",
            "status": {},
        },
    }


def valid_evidence() -> dict:
    allow_trace = "a" * 32
    scope_trace = "b" * 32
    expiry_trace = "c" * 32
    deny_trace = "d" * 32
    allow_customer = f"custody-gateway-{PROOF_ID}-allow"
    deny_customer = f"custody-gateway-{PROOF_ID}-deny"
    before_time = (NOW - timedelta(minutes=30)).isoformat()
    allow_time = (NOW - timedelta(minutes=14)).isoformat()
    allow_expires = (
        (NOW - timedelta(minutes=6))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    tool = {
        "name": "lookup_customer",
        "inputSchema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }
    allow_before = _ledger(7, last=before_time)
    allow_after = _ledger(8, last=allow_time)
    return {
        "schema_version": 2,
        "proof_id": PROOF_ID,
        "started_at": (NOW - timedelta(minutes=18)).isoformat(),
        "captured_at": (NOW - timedelta(minutes=1)).isoformat(),
        "project": PROJECT,
        "project_number": PROJECT_NUMBER,
        "region": REGION,
        "claim_boundary": CLAIM_BOUNDARY,
        "gateway": {
            **_times(),
            "name": GATEWAY,
            "etag": "gateway-etag",
            "protocols": ["MCP"],
            "registries": [
                f"//agentregistry.googleapis.com/projects/{PROJECT}/locations/{REGION}"
            ],
            "googleManaged": {"governedAccessPath": "AGENT_TO_ANYWHERE"},
            "agentGatewayCard": {
                "mtlsEndpoint": "gateway.example.internal:443",
                "rootCertificates": ["-----BEGIN CERTIFICATE-----"],
                "serviceExtensionsServiceAccount": (
                    f"service-{AUTHZ_OWNER}@gcp-sa-dep.iam.gserviceaccount.com"
                ),
            },
        },
        "extension": {
            **_times(),
            "name": EXTENSION,
            "service": "iap.googleapis.com",
            "failOpen": False,
            "timeout": "1s",
            "metadata": {"iapPolicyVersion": "V1"},
        },
        "authz_policy": {
            **_times(),
            "name": (
                f"projects/{PROJECT_NUMBER}/locations/{REGION}/authzPolicies/"
                "custody-fleet-request-authz"
            ),
            # v1 omits policyProfile; the API contract defaults it to REQUEST_AUTHZ.
            "target": {"resources": [GATEWAY_NUMBER]},
            "action": "CUSTOM",
            "customProvider": {"authzExtension": {"resources": [EXTENSION_NUMBER]}},
        },
        "cloud_run": {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "annotations": {
                    "run.googleapis.com/urls": (f'["{MCP_URL.removesuffix("/mcp")}"]')
                },
                "creationTimestamp": (NOW - timedelta(days=1)).isoformat(),
                "labels": {
                    "cloud.googleapis.com/location": REGION,
                    "custody-proof": "stale-registry",
                },
                "name": "custody-export-mcp",
                "namespace": PROJECT_NUMBER,
            },
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {"autoscaling.knative.dev/maxScale": "1"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "env": [
                                    {
                                        "name": "CUSTODY_MCP_REVISION",
                                        "value": "v2",
                                    }
                                ],
                                "image": (
                                    f"{REGION}-docker.pkg.dev/{PROJECT}/custody/"
                                    "custody-export-mcp:proof"
                                ),
                            }
                        ]
                    },
                },
                "traffic": [{"latestRevision": True, "percent": 100}],
            },
            "status": {
                "conditions": [{"type": "Ready", "status": "True"}],
                "latestCreatedRevisionName": "custody-export-mcp-00002",
                "latestReadyRevisionName": "custody-export-mcp-00002",
                "traffic": [
                    {
                        "latestRevision": True,
                        "percent": 100,
                        "revisionName": "custody-export-mcp-00002",
                    }
                ],
                "url": MCP_URL.removesuffix("/mcp"),
            },
        },
        "registry": {
            "service": {
                **_times(),
                "name": (
                    f"projects/{PROJECT}/locations/{REGION}/services/custody-export-mcp"
                ),
                "registryResource": MCP_REGISTRY_REFERENCE,
                "interfaces": [{"protocolBinding": "JSONRPC", "url": MCP_URL}],
                "mcpServerSpec": {
                    "type": "TOOL_SPEC",
                    "content": {"tools": [tool]},
                },
            },
            "projection": {
                **_times(),
                "name": MCP_RESOURCE,
                "mcpServerId": (
                    f"urn:mcp:projects-{PROJECT_NUMBER}:projects:{PROJECT_NUMBER}:"
                    f"locations:{REGION}:agentregistry:services:"
                    "custody-export-mcp"
                ),
                "attributes": {
                    "agentregistry.googleapis.com/system/RuntimeReference": {
                        "uri": (
                            "//agentregistry.googleapis.com/"
                            f"projects/{PROJECT_NUMBER}/locations/{REGION}/"
                            "services/custody-export-mcp"
                        )
                    }
                },
                "interfaces": [{"protocolBinding": "JSONRPC", "url": MCP_URL}],
                "tools": [copy.deepcopy(tool)],
            },
            "iap_policy_initial": _policy(
                "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
                "in ['custody_policy_canary', '']",
                "initial-etag",
                title="Custody no-registered-tool negative control",
            ),
            "iap_policy_allow": _policy(
                "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
                "== '' || "
                f"(request.time < timestamp('{allow_expires}') && "
                "api.getAttribute('iap.googleapis.com/mcp.toolName', '') == "
                "'lookup_customer')",
                "allow-etag",
                title=f"Custody temporary lookup admission/{PROOF_ID}",
            ),
            "iap_policy_deny": _policy(
                "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
                "in ['custody_policy_canary', '']",
                "deny-etag",
                title="Custody no-registered-tool negative control",
            ),
            "iap_policy_allow_applied_at": (NOW - timedelta(minutes=16)).isoformat(),
            "iap_policy_allow_expires_at": allow_expires,
            "iap_policy_deny_applied_at": (NOW - timedelta(minutes=4)).isoformat(),
            "iap_policy_audit_logs": {
                "allow": _iap_audit_log(
                    before_etag="initial-etag",
                    after_etag="allow-etag",
                    timestamp=NOW - timedelta(minutes=16, seconds=30),
                    insert_id="audit-allow",
                ),
                "deny": _iap_audit_log(
                    before_etag="allow-etag",
                    after_etag="deny-etag",
                    timestamp=NOW - timedelta(minutes=4, seconds=30),
                    insert_id="audit-deny",
                ),
            },
        },
        "runtime": {
            "agent_engine": {
                **_times(),
                "name": ENGINE,
                "displayName": "Custody Gateway Probe",
                "spec": {
                    "identityType": "AGENT_IDENTITY",
                    "effectiveIdentity": PRINCIPAL.removeprefix("principal://"),
                    "deploymentSpec": {
                        "agentGatewayConfig": {
                            "agentToAnywhereConfig": {"agentGateway": GATEWAY}
                        }
                    },
                },
            },
            "registered_agent": {
                **_times(),
                "name": (
                    f"projects/{PROJECT}/locations/{REGION}/agents/"
                    "agentregistry-runtime-1"
                ),
                "uid": "agentregistry-runtime-1",
                "agentId": (
                    f"urn:agent:projects-{PROJECT_NUMBER}:projects:"
                    f"{PROJECT_NUMBER}:locations:{REGION}:aiplatform:"
                    f"reasoningEngines:{ENGINE_ID}"
                ),
                "attributes": {
                    "agentregistry.googleapis.com/system/RuntimeIdentity": {
                        "principal": PRINCIPAL
                    },
                    "agentregistry.googleapis.com/system/RuntimeReference": {
                        "uri": (
                            "//aiplatform.googleapis.com/"
                            f"projects/{PROJECT_NUMBER}/locations/{REGION}/"
                            f"reasoningEngines/{ENGINE_ID}"
                        )
                    },
                },
            },
        },
        "allow_control": {
            "trace_id": allow_trace,
            "customer_id": allow_customer,
            "result": {
                "ok": True,
                "is_error": False,
                "proof_id": PROOF_ID,
                "customer_id": allow_customer,
                "tool_name": "lookup_customer",
                "data": {
                    "customer_id": allow_customer,
                    "company": f"Synthetic Customer {allow_customer}",
                    "plan": "enterprise",
                    "region": REGION,
                    "server_revision": "v2",
                    "instance_id": "instance-1",
                    "dispatch_id": 8,
                    "forwarding_requested": False,
                    "forwarded_to": None,
                    "forwarding_status": "not-requested",
                },
            },
            "evidence_before": allow_before,
            "evidence_after": allow_after,
        },
        "scope_control": {
            "trace_id": scope_trace,
            "customer_id": deny_customer,
            "tool_name": "custody_policy_canary",
            "result": {
                "ok": False,
                "proof_id": PROOF_ID,
                "customer_id": deny_customer,
                "tool_name": "custody_policy_canary",
                "error_type": "ClientError",
                "error": "403 Forbidden: Egress request is not authorized.",
            },
            "evidence_before": copy.deepcopy(allow_after),
            "evidence_after": copy.deepcopy(allow_after),
        },
        "expiry_control": {
            "trace_id": expiry_trace,
            "customer_id": deny_customer,
            "tool_name": "lookup_customer",
            "result": {
                "ok": False,
                "proof_id": PROOF_ID,
                "customer_id": deny_customer,
                "tool_name": "lookup_customer",
                "error_type": "ClientError",
                "error": "403 Forbidden: Egress request is not authorized.",
            },
            "evidence_before": copy.deepcopy(allow_after),
            "evidence_after": copy.deepcopy(allow_after),
        },
        "deny_control": {
            "trace_id": deny_trace,
            "customer_id": deny_customer,
            "result": {
                "ok": False,
                "proof_id": PROOF_ID,
                "customer_id": deny_customer,
                "tool_name": "lookup_customer",
                "error_type": "ClientError",
                "error": "403 Forbidden: Egress request is not authorized.",
            },
            "evidence_before": copy.deepcopy(allow_after),
            "evidence_after": copy.deepcopy(allow_after),
        },
        "gateway_logs": {
            "allow": [
                _gateway_log(
                    trace_id=allow_trace,
                    status=200,
                    result="ALLOWED",
                    timestamp=NOW - timedelta(minutes=14),
                )
            ],
            "scope": [
                _gateway_log(
                    trace_id=scope_trace,
                    status=403,
                    result="DENIED",
                    timestamp=NOW - timedelta(minutes=13),
                    tool_name="custody_policy_canary",
                )
            ],
            "expiry": [
                _gateway_log(
                    trace_id=expiry_trace,
                    status=403,
                    result="DENIED",
                    timestamp=NOW - timedelta(minutes=5),
                )
            ],
            "deny": [
                _gateway_log(
                    trace_id=deny_trace,
                    status=403,
                    result="DENIED",
                    timestamp=NOW - timedelta(minutes=2),
                )
            ],
        },
        "server_dispatch_log": _server_dispatch_log(
            trace_id=allow_trace,
            customer_id=allow_customer,
            timestamp=(NOW - timedelta(minutes=14) + timedelta(milliseconds=100)),
        ),
    }


class GatewayGateJudgeTests(unittest.TestCase):
    def test_valid_live_artifact_passes_every_gate(self):
        self.assertTrue(all(judge(valid_evidence(), now=NOW).values()))

    def test_proof_duration_is_bounded(self):
        evidence = valid_evidence()
        evidence["started_at"] = (NOW - timedelta(minutes=22)).isoformat()
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_coherent_foreign_dispatch_graft_cannot_pass(self):
        evidence = valid_evidence()
        foreign_proof = "e" * 32
        foreign_customer = f"custody-gateway-{foreign_proof}-allow"
        allow = evidence["allow_control"]
        allow["customer_id"] = foreign_customer
        allow["result"]["proof_id"] = foreign_proof
        allow["result"]["customer_id"] = foreign_customer
        allow["result"]["data"].update(
            {
                "customer_id": foreign_customer,
                "company": f"Synthetic Customer {foreign_customer}",
                "instance_id": "foreign-instance",
                "dispatch_id": 71,
            }
        )
        foreign_before = _ledger(
            70,
            last=(NOW - timedelta(minutes=30)).isoformat(),
            instance="foreign-instance",
        )
        foreign_after = _ledger(
            71,
            last=(NOW - timedelta(minutes=14)).isoformat(),
            instance="foreign-instance",
        )
        allow["evidence_before"] = foreign_before
        allow["evidence_after"] = foreign_after
        for name in ("scope_control", "expiry_control", "deny_control"):
            evidence[name]["evidence_before"] = copy.deepcopy(foreign_after)
            evidence[name]["evidence_after"] = copy.deepcopy(foreign_after)
        dispatch = evidence["server_dispatch_log"]["jsonPayload"]
        dispatch.update(
            {
                "proof_id": foreign_proof,
                "customer_id": foreign_customer,
                "instance_id": "foreign-instance",
                "dispatch_id": 71,
            }
        )
        gates = judge(evidence, now=NOW)
        self.assertFalse(gates["allow_reached_owned_mcp"])
        self.assertFalse(gates["server_dispatch_binds_allow"])

    def test_broad_historical_allow_cannot_be_claimed_as_safe_start(self):
        evidence = valid_evidence()
        initial = evidence["registry"]["iap_policy_initial"]
        initial["bindings"][0]["condition"] = {
            "title": "Historical broad admission",
            "expression": "true",
        }
        self.assertFalse(
            judge(evidence, now=NOW)["exact_server_expiring_iap_transition"]
        )

    def test_server_dispatch_log_is_required_and_structurally_bound(self):
        mutations = {
            "missing": lambda evidence: evidence.pop("server_dispatch_log"),
            "wrong_proof": lambda evidence: evidence["server_dispatch_log"][
                "jsonPayload"
            ].update({"proof_id": "f" * 32}),
            "wrong_revision": lambda evidence: evidence["server_dispatch_log"][
                "resource"
            ]["labels"].update({"revision_name": "custody-export-mcp-99999-forged"}),
            "wrong_instance": lambda evidence: evidence["server_dispatch_log"][
                "jsonPayload"
            ].update({"instance_id": "forged"}),
            "wrong_counter": lambda evidence: evidence["server_dispatch_log"][
                "jsonPayload"
            ].update({"dispatch_id": 7}),
            "forwarding": lambda evidence: evidence["server_dispatch_log"][
                "jsonPayload"
            ].update({"forwarding_requested": True}),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                evidence = valid_evidence()
                mutate(evidence)
                gates = judge(evidence, now=NOW)
                self.assertFalse(gates.get("server_dispatch_binds_allow", False))

    def test_scope_control_cannot_hide_a_dispatch(self):
        evidence = valid_evidence()
        dispatched = copy.deepcopy(evidence["scope_control"]["evidence_after"])
        dispatched["dispatch_count"] += 1
        dispatched["last_dispatched_at"] = (NOW - timedelta(minutes=12)).isoformat()
        evidence["scope_control"]["evidence_after"] = dispatched
        for name in ("expiry_control", "deny_control"):
            evidence[name]["evidence_before"] = copy.deepcopy(dispatched)
            evidence[name]["evidence_after"] = copy.deepcopy(dispatched)
        self.assertFalse(judge(evidence, now=NOW)["temporary_allow_is_tool_scoped"])

    def test_scope_requires_a_server_gateway_403_without_dispatch(self):
        mutations = {
            "status": lambda entry: entry["httpRequest"].update({"status": 200}),
            "decision": lambda entry: entry["jsonPayload"]["authzPolicyInfo"].update(
                {"result": "ALLOWED"}
            ),
            "server_ip": lambda entry: entry["httpRequest"].update(
                {"serverIp": "34.143.72.2:443"}
            ),
            "wrong_tool": lambda entry: entry["jsonPayload"]["agentGatewayInfo"][
                "mcpInfo"
            ].update({"parameter": "lookup_customer"}),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                evidence = valid_evidence()
                mutate(evidence["gateway_logs"]["scope"][0])
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_expiry_field_and_policy_cannot_be_tampered(self):
        for mutation in ("field_only", "coherent_excessive_ttl"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                expiry = (
                    (NOW + timedelta(minutes=15))
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                evidence["registry"]["iap_policy_allow_expires_at"] = expiry
                if mutation == "coherent_excessive_ttl":
                    condition = evidence["registry"]["iap_policy_allow"]["bindings"][0][
                        "condition"
                    ]
                    condition["expression"] = (
                        "api.getAttribute('iap.googleapis.com/mcp.toolName', "
                        "'') == '' || "
                        f"(request.time < timestamp('{expiry}') && "
                        "api.getAttribute('iap.googleapis.com/mcp.toolName', "
                        "'') == 'lookup_customer')"
                    )
                self.assertFalse(
                    judge(evidence, now=NOW)["exact_server_expiring_iap_transition"]
                )

    def test_expiry_control_must_follow_server_expiry_without_dispatch(self):
        evidence = valid_evidence()
        evidence["gateway_logs"]["expiry"][0]["timestamp"] = (
            NOW - timedelta(minutes=7)
        ).isoformat()
        self.assertFalse(judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"])

    def test_stale_artifact_cannot_pass(self):
        evidence = valid_evidence()
        evidence["captured_at"] = (NOW - timedelta(hours=25)).isoformat()
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_broader_claim_boundary_cannot_pass(self):
        evidence = valid_evidence()
        evidence["claim_boundary"] = "All Custody egress is secure."
        self.assertFalse(judge(evidence, now=NOW)["fresh_bounded_live_evidence"])

    def test_fail_open_or_dry_run_extension_cannot_pass(self):
        for mutation in ("fail_open", "dry_run"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                if mutation == "fail_open":
                    evidence["extension"]["failOpen"] = True
                else:
                    evidence["extension"]["metadata"]["iamEnforcementMode"] = "DRY_RUN"
                self.assertFalse(
                    judge(evidence, now=NOW)["enforced_registered_tool_request_authz"]
                )

    def test_omitted_fail_open_uses_the_enforced_false_default(self):
        evidence = valid_evidence()
        del evidence["extension"]["failOpen"]
        self.assertTrue(
            judge(evidence, now=NOW)["enforced_registered_tool_request_authz"]
        )

    def test_content_policy_or_wrong_target_cannot_pass(self):
        for mutation in ("content", "target"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                if mutation == "content":
                    evidence["authz_policy"]["policyProfile"] = "CONTENT_AUTHZ"
                else:
                    evidence["authz_policy"]["target"]["resources"] = [
                        GATEWAY + "-other"
                    ]
                self.assertFalse(
                    judge(evidence, now=NOW)["enforced_registered_tool_request_authz"]
                )

    def test_runtime_without_agent_identity_or_gateway_binding_cannot_pass(self):
        for mutation in ("service_account", "other_gateway"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                spec = evidence["runtime"]["agent_engine"]["spec"]
                if mutation == "service_account":
                    spec["identityType"] = "SERVICE_ACCOUNT"
                else:
                    spec["deploymentSpec"]["agentGatewayConfig"][
                        "agentToAnywhereConfig"
                    ]["agentGateway"] = GATEWAY + "-other"
                self.assertFalse(
                    judge(evidence, now=NOW)["runtime_identity_and_registry_bound"]
                )

    def test_unbound_registry_identity_cannot_pass(self):
        evidence = valid_evidence()
        attributes = evidence["runtime"]["registered_agent"]["attributes"]
        attributes["agentregistry.googleapis.com/system/RuntimeIdentity"][
            "principal"
        ] = PRINCIPAL.replace(ENGINE_ID, "other-engine")
        self.assertFalse(
            judge(evidence, now=NOW)["runtime_identity_and_registry_bound"]
        )

    def test_wrong_project_number_cannot_pass_resource_binding(self):
        evidence = valid_evidence()
        evidence["project_number"] = "999999999"
        self.assertFalse(all(judge(evidence, now=NOW).values()))

    def test_broad_or_wrong_principal_iap_policy_cannot_pass(self):
        for mutation in ("broad", "principal"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                binding = evidence["registry"]["iap_policy_allow"]["bindings"][0]
                if mutation == "broad":
                    binding["condition"]["expression"] = "true"
                else:
                    binding["members"] = [PRINCIPAL + "-other"]
                self.assertFalse(
                    judge(evidence, now=NOW)["exact_server_expiring_iap_transition"]
                )

    def test_semantically_equivalent_but_nonexact_cel_cannot_pass(self):
        allow_expires = valid_evidence()["registry"]["iap_policy_allow_expires_at"]
        for expression in (
            'api.getAttribute("iap.googleapis.com/mcp.toolName", "") == "" '
            f'|| (request.time < timestamp("{allow_expires}") && '
            'api.getAttribute("iap.googleapis.com/mcp.toolName", "") == '
            '"lookup_customer")',
            "api.getAttribute('iap.googleapis.com/mcp.toolName','') == '' || "
            f"(request.time < timestamp('{allow_expires}') && "
            "api.getAttribute('iap.googleapis.com/mcp.toolName','') == "
            "'lookup_customer')",
        ):
            with self.subTest(expression=expression):
                evidence = valid_evidence()
                evidence["registry"]["iap_policy_allow"]["bindings"][0]["condition"][
                    "expression"
                ] = expression
                self.assertFalse(
                    judge(evidence, now=NOW)["exact_server_expiring_iap_transition"]
                )

    def test_previous_all_expiring_cel_shape_cannot_pass(self):
        """The rejected schema-v1 shape also expired empty-name handshake
        traffic, which could stall MCP initialize after the lease expired.
        The judge must not accept it as the canonical temporary admission.
        """
        evidence = valid_evidence()
        allow_expires = evidence["registry"]["iap_policy_allow_expires_at"]
        evidence["registry"]["iap_policy_allow"]["bindings"][0]["condition"][
            "expression"
        ] = (
            f"request.time < timestamp('{allow_expires}') && "
            "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
            "in ['lookup_customer', '']"
        )
        self.assertFalse(
            judge(evidence, now=NOW)["exact_server_expiring_iap_transition"]
        )

    def test_deny_snapshot_that_still_allows_tool_cannot_pass(self):
        evidence = valid_evidence()
        deny_policy = evidence["registry"]["iap_policy_deny"]
        deny_policy["bindings"][0]["condition"]["expression"] = (
            "api.getAttribute('iap.googleapis.com/mcp.toolName', '') "
            "in ['lookup_customer', '']"
        )
        self.assertFalse(
            judge(evidence, now=NOW)["exact_server_expiring_iap_transition"]
        )

    def test_fabricated_iap_audit_etag_chain_cannot_pass(self):
        for phase in ("allow", "deny"):
            with self.subTest(phase=phase):
                evidence = valid_evidence()
                evidence["registry"]["iap_policy_audit_logs"][phase]["protoPayload"][
                    "response"
                ]["etag"] = "fabricated-etag"
                self.assertFalse(
                    judge(evidence, now=NOW)["server_audited_iap_etag_chain"]
                )

    def test_etag_across_base64_alphabets_still_binds_the_audit_chain(self):
        """gcloud's policy readback and the raw Admin Activity payload have
        been observed to encode the same etag bytes with different base64
        alphabets (url-safe vs standard). An equivalent etag must still bind.
        """
        evidence = valid_evidence()
        registry = evidence["registry"]
        registry["iap_policy_initial"]["etag"] = "etag-a_b-c="
        registry["iap_policy_audit_logs"]["allow"]["protoPayload"]["request"]["policy"][
            "etag"
        ] = "etag-a/b+c="
        self.assertTrue(judge(evidence, now=NOW)["server_audited_iap_etag_chain"])

    def test_unrelated_audit_actor_or_resource_cannot_pass(self):
        evidence = valid_evidence()
        audit = evidence["registry"]["iap_policy_audit_logs"]["allow"]
        audit["protoPayload"]["request"]["resource"] = "projects/other"
        self.assertFalse(judge(evidence, now=NOW)["server_audited_iap_etag_chain"])

    def test_fabricated_allow_result_cannot_replace_dispatch_evidence(self):
        evidence = valid_evidence()
        evidence["allow_control"]["passed"] = True
        evidence["allow_control"]["result"]["data"]["dispatch_id"] = 7
        self.assertFalse(judge(evidence, now=NOW)["allow_reached_owned_mcp"])

    def test_result_cannot_claim_a_different_serving_revision(self):
        evidence = valid_evidence()
        evidence["allow_control"]["result"]["data"]["server_revision"] = "v1"
        self.assertFalse(judge(evidence, now=NOW)["allow_reached_owned_mcp"])

    def test_a_genuinely_different_but_self_consistent_revision_still_passes(self):
        """S1's own claim is IAP/Gateway/identity enforcement, not which
        tool-revision digest happens to be deployed. R1, R2, and S1 share
        one Cloud Run service, and R2's own proof deliberately ends on a
        different revision than R1's; this proof must not depend on which
        one is currently live, only that every source agrees with every
        other source about it.
        """
        evidence = valid_evidence()
        for env in evidence["cloud_run"]["spec"]["template"]["spec"]["containers"][0][
            "env"
        ]:
            if env["name"] == "CUSTODY_MCP_REVISION":
                env["value"] = "v1"
        for control in (
            "allow_control",
            "scope_control",
            "expiry_control",
            "deny_control",
        ):
            evidence[control]["evidence_before"]["revision"] = "v1"
            evidence[control]["evidence_after"]["revision"] = "v1"
        evidence["allow_control"]["result"]["data"]["server_revision"] = "v1"
        evidence["server_dispatch_log"]["jsonPayload"]["revision"] = "v1"
        self.assertTrue(all(judge(evidence, now=NOW).values()))

    def test_a_v1_shaped_tool_result_with_no_forwarding_fields_still_passes(self):
        """v1's lookup_customer tool predates forward_to and returns no
        forwarding_requested/forwarded_to/forwarding_status keys at all --
        legitimately absent, not unbound, since this probe never requests a
        forward under either schema.
        """
        evidence = valid_evidence()
        data = evidence["allow_control"]["result"]["data"]
        for key in ("forwarding_requested", "forwarded_to", "forwarding_status"):
            data.pop(key, None)
        self.assertTrue(all(judge(evidence, now=NOW).values()))

    def test_result_from_another_process_cannot_pass(self):
        evidence = valid_evidence()
        evidence["allow_control"]["result"]["data"]["instance_id"] = "other"
        self.assertFalse(judge(evidence, now=NOW)["allow_reached_owned_mcp"])

    def test_unowned_or_multiprocess_cloud_run_target_cannot_pass(self):
        for mutation in (
            "namespace",
            "max_scale",
            "url",
            "missing_label",
            "empty_label",
        ):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                cloud_run = evidence["cloud_run"]
                if mutation == "namespace":
                    cloud_run["metadata"]["namespace"] = "999"
                elif mutation == "max_scale":
                    cloud_run["spec"]["template"]["metadata"]["annotations"][
                        "autoscaling.knative.dev/maxScale"
                    ] = "2"
                elif mutation == "missing_label":
                    del cloud_run["metadata"]["labels"]["custody-proof"]
                elif mutation == "empty_label":
                    cloud_run["metadata"]["labels"]["custody-proof"] = ""
                else:
                    cloud_run["status"]["url"] = "https://attacker.invalid"
                self.assertFalse(
                    judge(evidence, now=NOW)["owned_cloud_run_target_bound"]
                )

    def test_denied_call_that_dispatched_or_changed_instance_cannot_pass(self):
        for mutation in ("dispatch", "instance"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                after = evidence["deny_control"]["evidence_after"]
                if mutation == "dispatch":
                    after["dispatch_count"] += 1
                else:
                    after["instance_id"] = "instance-2"
                evidence["deny_control"]["blocked"] = True
                self.assertFalse(
                    judge(evidence, now=NOW)["deny_stopped_before_dispatch"]
                )

    def test_denied_result_without_a_real_error_cannot_pass(self):
        evidence = valid_evidence()
        evidence["deny_control"]["result"]["error_type"] = ""
        evidence["deny_control"]["blocked"] = True
        self.assertFalse(judge(evidence, now=NOW)["deny_stopped_before_dispatch"])

    def test_mutated_gateway_denial_log_cannot_pass(self):
        mutations = {
            "trace": lambda entry: entry.update(
                {"trace": f"projects/{PROJECT}/traces/{'b' * 32}"}
            ),
            "tool": lambda entry: entry["jsonPayload"]["agentGatewayInfo"][
                "mcpInfo"
            ].update({"parameter": "other_tool"}),
            "status": lambda entry: entry["httpRequest"].update({"status": 200}),
            "decision": lambda entry: entry["jsonPayload"]["authzPolicyInfo"].update(
                {"result": "ALLOWED"}
            ),
            "nested_decision": lambda entry: entry["jsonPayload"]["authzPolicyInfo"][
                "policies"
            ][0].update({"result": "ALLOWED"}),
            "policy": lambda entry: entry["jsonPayload"]["authzPolicyInfo"]["policies"][
                0
            ].update(
                {
                    "name": "projects/396106114361/locations/us-central1/"
                    "authzPolicies/other-policy"
                }
            ),
            "resource": lambda entry: entry["resource"]["labels"].update(
                {"gateway_name": "other-gateway"}
            ),
            "log_name": lambda entry: entry.update(
                {
                    "logName": (
                        f"projects/{PROJECT}/logs/"
                        "networkservices.googleapis.com%2Fother"
                    )
                }
            ),
            "server_ip": lambda entry: entry["httpRequest"].update(
                {"serverIp": "34.143.72.2:443"}
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                evidence = valid_evidence()
                mutate(evidence["gateway_logs"]["deny"][0])
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_policy_log_owner_must_derive_from_gateway_card(self):
        for mutation in ("service_account", "policy_owner"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                if mutation == "service_account":
                    evidence["gateway"]["agentGatewayCard"][
                        "serviceExtensionsServiceAccount"
                    ] = "service-999@gcp-sa-dep.iam.gserviceaccount.com"
                else:
                    policy = evidence["gateway_logs"]["deny"][0]["jsonPayload"][
                        "authzPolicyInfo"
                    ]["policies"][0]
                    policy["name"] = policy["name"].replace(AUTHZ_OWNER, "999")
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_gateway_mtls_fingerprint_must_be_identical_and_nonempty(self):
        for fingerprint in ("", "different-fingerprint"):
            with self.subTest(fingerprint=fingerprint):
                evidence = valid_evidence()
                evidence["gateway_logs"]["deny"][0]["jsonPayload"]["mtls"][
                    "clientCertSha256Fingerprint"
                ] = fingerprint
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_allow_must_have_server_ip_and_deny_must_not(self):
        for mutation in ("allow_missing", "deny_present"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                if mutation == "allow_missing":
                    del evidence["gateway_logs"]["allow"][0]["httpRequest"]["serverIp"]
                else:
                    evidence["gateway_logs"]["deny"][0]["httpRequest"]["serverIp"] = (
                        "34.143.72.2:443"
                    )
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_policy_and_log_chronology_is_strict(self):
        mutations = {
            "allow_before_policy": lambda evidence: evidence["gateway_logs"]["allow"][
                0
            ].update({"timestamp": (NOW - timedelta(minutes=6)).isoformat()}),
            "deny_policy_before_allow_log": lambda evidence: evidence[
                "registry"
            ].update(
                {"iap_policy_deny_applied_at": (NOW - timedelta(minutes=5)).isoformat()}
            ),
            "deny_before_policy": lambda evidence: evidence["gateway_logs"]["deny"][
                0
            ].update({"timestamp": (NOW - timedelta(minutes=4)).isoformat()}),
            "deny_after_capture": lambda evidence: evidence["gateway_logs"]["deny"][
                0
            ].update({"timestamp": NOW.isoformat()}),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                evidence = valid_evidence()
                mutate(evidence)
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_stale_or_duplicate_gateway_log_cannot_pass(self):
        for mutation in ("stale", "duplicate"):
            with self.subTest(mutation=mutation):
                evidence = valid_evidence()
                if mutation == "stale":
                    evidence["gateway_logs"]["deny"][0]["timestamp"] = (
                        NOW - timedelta(hours=2)
                    ).isoformat()
                else:
                    evidence["gateway_logs"]["deny"].append(
                        copy.deepcopy(evidence["gateway_logs"]["deny"][0])
                    )
                self.assertFalse(
                    judge(evidence, now=NOW)["gateway_logs_correlate_enforcement"]
                )

    def test_malformed_evidence_is_a_clean_failure(self):
        evidence = valid_evidence()
        del evidence["runtime"]["registered_agent"]["attributes"]
        self.assertEqual(judge(evidence, now=NOW), {"well_formed_evidence": False})

    def test_cyclic_or_excessively_deep_result_is_a_clean_failure(self):
        cyclic = valid_evidence()
        cyclic["allow_control"]["result"]["cycle"] = cyclic["allow_control"]["result"]
        self.assertEqual(judge(cyclic, now=NOW), {"well_formed_evidence": False})

        deep = valid_evidence()
        cursor = deep["allow_control"]["result"]
        for _ in range(40):
            child = {}
            cursor["child"] = child
            cursor = child
        self.assertEqual(judge(deep, now=NOW), {"well_formed_evidence": False})

    def test_malformed_nested_scalars_are_clean_failures(self):
        mutations = (
            lambda evidence: evidence.update({"gateway_logs": 7}),
            lambda evidence: evidence["gateway_logs"].update({"deny": 7}),
            lambda evidence: evidence["gateway_logs"]["allow"][0].update(
                {"jsonPayload": 7}
            ),
            lambda evidence: evidence["gateway_logs"]["allow"][0]["jsonPayload"].update(
                {"authzPolicyInfo": 7}
            ),
            lambda evidence: evidence["registry"].update({"iap_policy_allow": 7}),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                evidence = valid_evidence()
                mutate(evidence)
                self.assertEqual(
                    judge(evidence, now=NOW),
                    {"well_formed_evidence": False},
                )


if __name__ == "__main__":
    unittest.main()
