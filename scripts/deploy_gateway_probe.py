"""Deploy the deterministic Gateway probe with Agent Identity at creation.

Agent Identity cannot be retrofitted onto an existing Runtime. Keeping this as
a separate command makes the one material cloud creation explicit; subsequent
evidence runs reuse the same Runtime and mutate only its target IAP condition.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentplatform import Client, types  # noqa: E402
from google.auth import load_credentials_from_file  # noqa: E402

from live.gateway_probe import GatewayProbe  # noqa: E402

PROJECT_NUMBER = "742122658452"
PROJECT = "project-988bc9fe-092c-4b32-90c"
DISPLAY_NAME = "custody-gateway-probe"
GATEWAY = "custody-fleet-egress"
ADC = REPO_ROOT / ".gcloud" / "application_default_credentials.json"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def main() -> int:
    project = _required("CUSTODY_PROJECT")
    if project != PROJECT:
        raise SystemExit(f"CUSTODY_PROJECT must be the owned proof project {PROJECT}")
    if not ADC.exists():
        raise SystemExit(
            "repo-local ADC is absent; run gcloud auth application-default login"
        )
    region = os.environ.get("CUSTODY_LOCATION", "us-central1")
    endpoint = os.environ.get("CUSTODY_GATEWAY_MCP_URL") or (
        "https://custody-export-mcp-anexdhueiq-uc.a.run.app/mcp"
    )
    credentials, _ = load_credentials_from_file(
        ADC,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    client = Client(
        credentials=credentials,
        project=project,
        location=region,
    )
    gateway = f"projects/{project}/locations/{region}/agentGateways/{GATEWAY}"
    probe = GatewayProbe(endpoint)
    package_config = {
        "display_name": DISPLAY_NAME,
        "description": (
            "Deterministic Custody probe for Agent Gateway IAP enforcement."
        ),
        "staging_bucket": f"gs://custody-agent-staging-{PROJECT_NUMBER}",
        "gcs_dir_name": "gateway-probe",
        "requirements": [
            "google-cloud-aiplatform[agent_engines]==1.163.0",
            "httpx==0.28.1",
            "cloudpickle==3.1.2",
            "pydantic==2.13.4",
        ],
        "extra_packages": ["live/gateway_probe"],
        "agent_framework": "custom",
        "python_version": "3.12",
        "min_instances": 0,
        "max_instances": 1,
        "labels": {"custody-proof": "agent-gateway"},
    }
    existing = [
        item.api_resource
        for item in client.agent_engines.list(
            config={"filter": f'display_name="{DISPLAY_NAME}"'}
        )
        if item.api_resource is not None
    ]
    if existing:
        remote = client.agent_engines.update(
            name=existing[0].name,
            agent=probe,
            config=package_config,
        )
        if remote.api_resource is None:
            raise RuntimeError("Agent Platform returned no updated Runtime resource")
        print(remote.api_resource.model_dump_json(indent=2, exclude_none=True))
        return 0

    remote = client.agent_engines.create(
        agent=probe,
        config={
            **package_config,
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "agent_gateway_config": {
                "agent_to_anywhere_config": {"agent_gateway": gateway}
            },
        },
    )
    if remote.api_resource is None:
        raise RuntimeError("Agent Platform returned no Runtime resource")
    print(remote.api_resource.model_dump_json(indent=2, exclude_none=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
