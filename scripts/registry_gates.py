"""Judge the live stale-Registry artifact independently of its producer."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custody.origin import digest  # noqa: E402
from custody.revision import DIGEST_ALGORITHM, ToolSurface  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-registry-attack.json"


def _content_digest(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return digest(canonical)


def _registry_resources_are_bound(evidence: dict, registry: dict) -> bool:
    """Bind the writable Service and projection without assuming ID vs number."""
    service = registry["service"].split("/")
    projection = registry["registry_resource"].split("/")
    return (
        len(service) == 6
        and service[0] == "projects"
        and service[1] == evidence["project"]
        and service[2] == "locations"
        and service[4] == "services"
        and service[5] == evidence["cloud_run"]["service"]
        and len(projection) == 6
        and projection[0] == "projects"
        and bool(projection[1])
        and projection[2] == "locations"
        and projection[3] == service[3]
        and projection[4] == "mcpServers"
        and bool(projection[5])
        and evidence.get("registry_region", service[3]) == service[3]
    )


def judge(evidence: dict, *, now: datetime | None = None) -> dict[str, bool]:
    proof_id = evidence["proof_id"]
    captured = datetime.fromisoformat(evidence["captured_at"])
    current = now or datetime.now(UTC)
    if captured.tzinfo is None or captured > current + timedelta(minutes=5):
        return {"fresh_live_evidence": False}

    cloud = evidence["cloud_run"]
    registry = evidence["registry"]
    surfaces = evidence["surfaces"]
    registered_v1 = evidence["registered_v1_control"]
    negative = evidence["negative_control"]
    governed = evidence["governed"]
    revocation = evidence["revocation"]
    selected = governed["selected_denial"] or {}
    server = cloud["service"]
    approved_surface = ToolSurface.from_tools_list(
        server=server, payload=registry["content_before_v2"]
    )
    registry_after_surface = ToolSurface.from_tools_list(
        server=server, payload=registry["content_after_v2"]
    )
    live_v1_surface = ToolSurface.from_tools_list(
        server=server, payload=surfaces["live_v1"]
    )
    live_v2_surface = ToolSurface.from_tools_list(
        server=server, payload=surfaces["live_v2"]
    )
    if not all(
        len(surface.tools) == 1
        for surface in (
            approved_surface,
            registry_after_surface,
            live_v1_surface,
            live_v2_surface,
        )
    ):
        return {"single_tool_surface": False}
    approved_tool = approved_surface.tools[0]
    registry_after_tool = registry_after_surface.tools[0]
    live_v1_tool = live_v1_surface.tools[0]
    live_v2_tool_definition = live_v2_surface.tools[0]
    approved_revision = approved_tool.revision
    observed_revision = live_v2_tool_definition.revision
    v1_tool = live_v1_tool.definition
    v2_tool = live_v2_tool_definition.definition

    prefix = f"{proof_id}:"
    expected_removed = {
        f"{prefix}v1-root",
        f"{prefix}sales",
        f"{prefix}support",
        f"{prefix}finance",
    }
    expected_survivors = {
        f"{prefix}v2-root",
        f"{prefix}v2-child",
        f"{prefix}unrelated",
    }
    result_value = negative["result"]["value"] or {}
    v1_result_value = registered_v1["result"]["value"] or {}
    bindings = revocation["root_bindings"]
    return {
        "fresh_live_evidence": current - captured <= timedelta(hours=24),
        "same_url_two_cloud_run_revisions": (
            cloud["same_url"]
            and cloud["v1_revision"] != cloud["v2_revision"]
            and cloud["v1_health"]["revision"] == "v1"
            and cloud["v2_health"]["revision"] == "v2"
        ),
        "registry_snapshot_is_stale": (
            registry["update_time_before_v2"] == registry["update_time_after_v2"]
            and registry["content_before_v2"] == registry["content_after_v2"]
            and approved_revision == registry_after_tool.revision
            and approved_revision == live_v1_tool.revision
            and approved_tool.definition == live_v1_tool.definition
            and surfaces["v1_admitted"] is True
            and registry["endpoint"] == negative["registry_endpoint_used"]
            and registry["endpoint"] == registered_v1["registry_endpoint_used"]
            and registry["endpoint"] == f"{cloud['url']}/mcp"
            and _registry_resources_are_bound(evidence, registry)
        ),
        "registered_v1_dispatched": (
            registered_v1["dispatch_count_after"]
            == registered_v1["dispatch_count_before"] + 1
            and registered_v1["instance_id_before"]
            == registered_v1["instance_id_after"]
            and registered_v1["instance_id_before"]
            == cloud["v1_health"]["instance_id"]
            and v1_result_value.get("customer_id")
            == registered_v1["arguments"]["customer_id"]
            and v1_result_value.get("server_revision") == "v1"
            and v1_result_value.get("instance_id")
            == registered_v1["instance_id_after"]
        ),
        "live_surface_changed": (
            surfaces["approved_revision"] == approved_revision
            and surfaces["observed_revision"] == observed_revision
            and approved_revision != observed_revision
            and v1_tool["name"] == v2_tool["name"] == "lookup_customer"
            and "forward_to" not in v1_tool["inputSchema"]["properties"]
            and "forward_to" in v2_tool["inputSchema"]["properties"]
            and v1_tool["annotations"]["readOnlyHint"] is True
            and v2_tool["annotations"]["readOnlyHint"] is False
        ),
        "negative_control_dispatched_v2": (
            negative["dispatch_count_after"]
            == negative["dispatch_count_before"] + 1
            and negative["instance_id_before"] == negative["instance_id_after"]
            and negative["instance_id_before"]
            == cloud["v2_health"]["instance_id"]
            and result_value.get("customer_id")
            == negative["arguments"]["customer_id"]
            and result_value.get("forwarded_to")
            == negative["arguments"]["forward_to"]
            and result_value.get("server_revision") == "v2"
            and result_value.get("instance_id") == negative["instance_id_after"]
            and result_value.get("forwarding_requested") is True
            and negative["result"]["protocol_result"]["is_error"] is False
            and negative["forwarding_dispatch_count_after"]
            == negative["forwarding_dispatch_count_before"] + 1
        ),
        "custody_blocked_before_dispatch": (
            governed["blocked"]
            and selected.get("reason") == "revision_mismatch"
            and selected.get("expected_revision")
            == approved_revision
            and selected.get("observed_revision")
            == observed_revision
            and governed["dispatch_count_after"]
            == governed["dispatch_count_before"]
            and governed["instance_id_before"] == governed["instance_id_after"]
            and governed["instance_id_before"] == negative["instance_id_after"]
            and governed["forwarding_dispatch_count_after"]
            == governed["forwarding_dispatch_count_before"]
        ),
        "revision_specific_descendants_revoked": (
            set(revocation["removed"]) == expected_removed
            and set(revocation["survivors"]) == expected_survivors
            and revocation["revoked_revision"] == approved_revision
            and bindings["v1"]["tool_id"] == approved_tool.tool_id
            and bindings["v1"]["origin"] == "tool"
            and bindings["v1"]["source_revision"] == approved_revision
            and bindings["v1"]["content_sha256"]
            == _content_digest(v1_result_value)
            and bindings["v2"]["tool_id"] == approved_tool.tool_id
            and bindings["v2"]["origin"] == "tool"
            and bindings["v2"]["source_revision"] == observed_revision
            and bindings["v2"]["content_sha256"]
            == _content_digest(result_value)
            and revocation["live_memory_bank_deletion"] is False
        ),
        "runtime_binding_also_blocked": _runtime_binding_also_blocked(
            evidence.get("runtime_binding"), approved_tool=approved_tool
        ),
    }


def _runtime_binding_also_blocked(runtime_binding: dict | None, *, approved_tool) -> bool:
    """Old evidence captured before this field existed fails this gate
    rather than crashing the judge: a missing field is not the same claim
    as a present-but-wrong one, but neither one is PASS."""
    if not runtime_binding:
        return False
    approved = runtime_binding.get("approved") or {}
    observed = runtime_binding.get("observed_on_identical_declared_surface") or {}
    selected = runtime_binding.get("selected_denial") or {}
    return bool(
        approved.get("revision_name")
        and approved.get("image_digest")
        and observed.get("revision_name")
        and observed.get("image_digest")
        and approved != observed
        and runtime_binding.get("denied") is True
        and selected.get("tool_id") == approved_tool.tool_id
        and selected.get("reason") == "runtime_drift"
        and selected.get("expected_revision") == approved_tool.revision
    )


def main() -> int:
    if not OUT.exists():
        print("[BLOCKED] no proof-out/live-registry-attack.json")
        print("          run make live-registry-attack")
        return 2
    try:
        evidence = json.loads(OUT.read_text())
        gates = judge(evidence)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] malformed live Registry evidence: {error}")
        return 1
    for name, passed in gates.items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    ok = bool(gates) and all(gates.values())
    if not ok:
        recorded = evidence.get("digest_algorithm")
        if recorded and recorded != DIGEST_ALGORITHM:
            print(
                f"          note: evidence was captured under "
                f"{recorded!r} (code_revision "
                f"{evidence.get('code_revision', 'unknown')}), this build "
                f"digests under {DIGEST_ALGORITHM!r}; re-run "
                f"make live-registry-attack"
            )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
