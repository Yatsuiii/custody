"""Idempotently provision Custody's three declarative Gateway resources."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(os.environ.get("CLOUDSDK_CONFIG", REPO_ROOT / ".gcloud"))
RESOURCE_DIR = REPO_ROOT / "live" / "gateway"
PROJECT = "project-988bc9fe-092c-4b32-90c"
REGION = "us-central1"


@dataclass(frozen=True)
class Resource:
    command: tuple[str, ...]
    resource_id: str
    filename: str


RESOURCES = (
    Resource(
        ("network-services", "agent-gateways", "import"),
        "custody-fleet-egress",
        "custody-fleet-egress.yaml",
    ),
    Resource(
        ("service-extensions", "authz-extensions", "import"),
        "custody-fleet-iap-enforced",
        "custody-fleet-iap-enforced.yaml",
    ),
    Resource(
        ("network-security", "authz-policies", "import"),
        "custody-fleet-request-authz",
        "custody-fleet-request-authz.yaml",
    ),
)


def _gcloud(*arguments: str) -> None:
    environment = os.environ.copy()
    environment["CLOUDSDK_CONFIG"] = str(CONFIG)
    environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    subprocess.run(
        [
            "gcloud",
            *arguments,
            f"--project={PROJECT}",
            "--quiet",
        ],
        check=True,
        env=environment,
    )


def main() -> int:
    _gcloud(
        "services",
        "enable",
        "agentregistry.googleapis.com",
        "aiplatform.googleapis.com",
        "iap.googleapis.com",
        "logging.googleapis.com",
        "networksecurity.googleapis.com",
        "networkservices.googleapis.com",
    )
    for resource in RESOURCES:
        _gcloud(
            *resource.command,
            resource.resource_id,
            f"--source={RESOURCE_DIR / resource.filename}",
            f"--location={REGION}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
