"""Prove R2: an allowed ``tools/call`` is cryptographically bound to the
``tools/list`` read that authorized it, closing the TOCTOU R1 left open.

R1 (`scripts/live_registry_attack.py`) proves Custody refuses a changed
revision when its own client-side admission check runs. That check happens
at read time; nothing before this bound the specific dispatch to the
specific read. This producer proves the owned MCP server itself now closes
that window: a token minted from one ``tools/list`` read is refused, by the
server, at the instant of dispatch, if presented after the server's live
digest has changed underneath it, or if presented a second time at all.

Claim boundary, stated here because every other live proof in this repo
states its own: this closes the declared-surface TOCTOU only. It does not,
and cannot, detect a behavior-only change under an identical ``tools/list``;
that would need the server to attest its own running code identity, a
different problem, left open. The consumed-nonce set is process-local, the
same single-owned-instance scope R1 and S1 already require.

    make live-revision-binding
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
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastmcp import Client  # noqa: E402

from custody.revision import DIGEST_ALGORITHM, Denial, SurfaceAttestation  # noqa: E402

OUT = REPO_ROOT / "proof-out" / "live-revision-binding.json"
FAILURE = REPO_ROOT / "proof-out" / "live-revision-binding.failure.json"
CONFIG = REPO_ROOT / ".gcloud"
SERVER_SOURCE = REPO_ROOT / "live" / "registry_attack" / "server"
#: The custody package server.py imports; vendored into the Cloud Build
#: context (this directory, not the repo root) before every build, and
#: removed afterward so the working tree never carries a build artifact.
VENDORED_CUSTODY = SERVER_SOURCE / "custody"
VENDORED_FILES = ("__init__.py", "origin.py", "revision.py", "nonce_ledger.py")
SERVICE = "custody-export-mcp"
DISPLAY_NAME = "Custody Export MCP"
TOOL_NAME = "lookup_customer"
ATTESTATION_META_KEY = "custody_attestation"
#: Comfortably longer than one Cloud Run revision swap takes in this proof;
#: see server.py's ``_configured_attestation_ttl_seconds`` for why a live,
#: redeploy-spanning proof needs this higher than the 45s production default.
PROOF_TTL_SECONDS = "900"

CLAIM_BOUNDARY = (
    "Proves a tools/call dispatch is refused by the owned MCP server itself, "
    "at the instant of execution, when the presented token was minted "
    "against a tools/list read that no longer matches the server's live "
    "digest, that a structurally valid token cannot be replayed within one "
    "process, and (when nonce_ledger_backend is 'firestore') that a token "
    "consumed by one process is still refused by a genuinely fresh process "
    "serving the same digest afterward. It does not detect a behavior-only "
    "change under an identical tools/list."
)


class Cloud:
    """The proof's cloud boundary, including its isolated gcloud state."""

    def __init__(self, project: str, region: str, repository: str, config: Path):
        self.project = project
        self.region = region
        self.repository = repository
        self.config = config

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
    if not project:
        raise RuntimeError("no gcloud project is configured")
    return project


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


def _vendor_custody() -> None:
    """Copy the pure, dependency-free custody modules server.py imports
    into the Cloud Build context, since that context is this directory, not
    the repo root (see the Dockerfile's own comment on this)."""
    VENDORED_CUSTODY.mkdir(exist_ok=True)
    for name in VENDORED_FILES:
        shutil.copy2(REPO_ROOT / "custody" / name, VENDORED_CUSTODY / name)


def _remove_vendored_custody() -> None:
    shutil.rmtree(VENDORED_CUSTODY, ignore_errors=True)


def _deploy(
    cloud: Cloud,
    *,
    image: str,
    revision: str,
    secret: str,
    firestore_project: str | None = None,
) -> dict[str, Any]:
    parts = [
        f"CUSTODY_MCP_REVISION={revision}",
        f"CUSTODY_ATTESTATION_SECRET={secret}",
        f"CUSTODY_ATTESTATION_TTL_SECONDS={PROOF_TTL_SECONDS}",
    ]
    if firestore_project:
        parts.append(f"CUSTODY_FIRESTORE_PROJECT={firestore_project}")
    env_vars = ",".join(parts)
    cloud.run(
        "run",
        "deploy",
        SERVICE,
        f"--image={image}",
        f"--region={cloud.region}",
        "--allow-unauthenticated",
        "--max-instances=1",
        f"--set-env-vars={env_vars}",
        "--labels=custody-proof=revision-binding",
    )
    return cloud.json(
        "run", "services", "describe", SERVICE, f"--region={cloud.region}"
    )


async def _tools_list_with_attestation(url: str) -> dict[str, SurfaceAttestation]:
    """One token per tool, taken from ``_meta`` on the real live response."""
    async with Client(url) as client:
        tools = await client.list_tools()
    tokens: dict[str, SurfaceAttestation] = {}
    for tool in tools:
        raw = (tool.meta or {}).get(ATTESTATION_META_KEY)
        if not isinstance(raw, dict):
            continue
        tokens[tool.name] = SurfaceAttestation(
            tool_id=str(raw["tool_id"]),
            revision=str(raw["revision"]),
            nonce=str(raw["nonce"]),
            issued_at=float(raw["issued_at"]),
            expires_at=float(raw["expires_at"]),
            signature=str(raw["signature"]),
        )
    return tokens


async def _call_with_token(
    url: str, token: SurfaceAttestation, *, customer_id: str
) -> dict[str, Any]:
    """Dispatch with a specific attestation token, never letting the client
    library mint a fresh one: the whole point is presenting a token bound to
    a different (possibly stale) surface read than the one just fetched."""
    async with Client(url) as client:
        result = await client.call_tool_mcp(
            TOOL_NAME,
            {"customer_id": customer_id},
            meta={ATTESTATION_META_KEY: asdict(token)},
        )
    is_error = bool(result.isError)
    text = next(
        (item.text for item in result.content if getattr(item, "type", None) == "text"),
        None,
    )
    return {"is_error": is_error, "text": text}


def _gcloud_logging_read(cloud: Cloud, *arguments: str) -> Any:
    environment = os.environ.copy()
    environment["CLOUDSDK_CONFIG"] = str(cloud.config)
    environment["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    completed = subprocess.run(
        [
            "gcloud",
            "logging",
            "read",
            *arguments,
            f"--project={cloud.project}",
            "--quiet",
            "--format=json",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=60,
    )
    return json.loads(completed.stdout)


def _poll_for_denial(
    cloud: Cloud, *, revision_name: str, nonce: str, reason: Denial
) -> dict[str, Any]:
    query = " AND ".join(
        (
            f'logName="projects/{cloud.project}/logs/run.googleapis.com%2Fstdout"',
            'resource.type="cloud_run_revision"',
            f'resource.labels.service_name="{SERVICE}"',
            f'resource.labels.revision_name="{revision_name}"',
            'jsonPayload.event="custody.attestation.denied.v1"',
            f'jsonPayload.reason="{reason.value}"',
        )
    )
    last: list[dict[str, Any]] = []
    for _ in range(20):
        try:
            last = _gcloud_logging_read(
                cloud, query, "--freshness=1h", "--order=desc", "--limit=10"
            )
        except (json.JSONDecodeError, OSError, subprocess.CalledProcessError):
            time.sleep(3)
            continue
        matches = [entry for entry in last if isinstance(entry, dict)]
        if matches:
            return matches[0]
        time.sleep(3)
    raise RuntimeError(
        f"no denial log with reason={reason.value} found for revision "
        f"{revision_name} (nonce {nonce})"
    )


async def _prove() -> dict[str, Any]:
    proof_id = uuid.uuid4().hex
    secret = uuid.uuid4().hex
    project = os.environ.get("CUSTODY_PROJECT") or _configured_project(CONFIG)
    region = os.environ.get("CUSTODY_REGISTRY_REGION", "us-central1")
    repository = os.environ.get("CUSTODY_ARTIFACT_REPOSITORY", "custody")
    cloud = Cloud(project, region, repository, CONFIG)
    image = (
        f"{region}-docker.pkg.dev/{project}/{repository}/"
        f"custody-export-mcp:{proof_id[:12]}"
    )
    customer_id = f"cust-{proof_id[:12]}"
    firestore_project = os.environ.get("CUSTODY_FIRESTORE_PROJECT", "").strip() or None

    print(
        "[1/7] Vendoring custody/revision.py and building the MCP image...", flush=True
    )
    cloud.run("services", "enable", "run.googleapis.com")
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

    print("[2/7] Deploying v1 and minting a real dispatch token...", flush=True)
    v1_service = _deploy(
        cloud,
        image=image,
        revision="v1",
        secret=secret,
        firestore_project=firestore_project,
    )
    v1_status = v1_service["status"]
    url = v1_status["url"]
    v1_revision_name = v1_status["latestReadyRevisionName"]
    await asyncio.to_thread(_wait_for_revision, url, "v1")
    endpoint = f"{url}/mcp"
    v1_tokens = await _tools_list_with_attestation(endpoint)
    v1_token = v1_tokens[TOOL_NAME]
    # A second, distinct v1 token, never dispatched, reserved for the digest
    # mismatch control below. With a durable ledger, a nonce already spent
    # by v1_token (positive_control) would be refused as REPLAYED by any
    # process sharing that ledger, v2 included, before the digest is ever
    # compared -- correctly stronger, but it means the same already-spent
    # token can no longer isolate DIGEST_MISMATCH specifically. A token
    # that was minted but never presented anywhere keeps that isolation.
    v1_mismatch_tokens = await _tools_list_with_attestation(endpoint)
    v1_mismatch_token = v1_mismatch_tokens[TOOL_NAME]

    print(
        "[3/7] Positive control: dispatching once with the fresh v1 token...",
        flush=True,
    )
    before_positive = await asyncio.to_thread(_json_get, f"{url}/evidence")
    positive = await _call_with_token(endpoint, v1_token, customer_id=customer_id)
    after_positive = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print("[4/7] Replay control: reusing the same token a second time...", flush=True)
    replay = await _call_with_token(endpoint, v1_token, customer_id=customer_id)
    replay_denial = await asyncio.to_thread(
        _poll_for_denial,
        cloud,
        revision_name=v1_revision_name,
        nonce=v1_token.nonce,
        reason=Denial.REPLAYED,
    )
    after_replay = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print("[5/7] Redeploying to v2 on the same URL and secret...", flush=True)
    v2_service = _deploy(
        cloud,
        image=image,
        revision="v2",
        secret=secret,
        firestore_project=firestore_project,
    )
    v2_status = v2_service["status"]
    if v2_status["url"] != url:
        raise RuntimeError("Cloud Run URL changed between revisions")
    v2_revision_name = v2_status["latestReadyRevisionName"]
    await asyncio.to_thread(_wait_for_revision, url, "v2")
    before_mismatch = await asyncio.to_thread(_json_get, f"{url}/evidence")
    mismatch = await _call_with_token(
        endpoint, v1_mismatch_token, customer_id=customer_id
    )
    mismatch_denial = await asyncio.to_thread(
        _poll_for_denial,
        cloud,
        revision_name=v2_revision_name,
        nonce=v1_mismatch_token.nonce,
        reason=Denial.DIGEST_MISMATCH,
    )
    after_mismatch = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print(
        "[6/7] Positive control on v2: a fresh token dispatches normally...", flush=True
    )
    v2_tokens = await _tools_list_with_attestation(endpoint)
    v2_token = v2_tokens[TOOL_NAME]
    v2_positive = await _call_with_token(endpoint, v2_token, customer_id=customer_id)
    after_v2_positive = await asyncio.to_thread(_json_get, f"{url}/evidence")

    print(
        "[7/7] Redeploying v1 again (fresh process, unchanged digest) and "
        "replaying the original v1 token...",
        flush=True,
    )
    v1_restart_service = _deploy(
        cloud,
        image=image,
        revision="v1",
        secret=secret,
        firestore_project=firestore_project,
    )
    v1_restart_status = v1_restart_service["status"]
    if v1_restart_status["url"] != url:
        raise RuntimeError("Cloud Run URL changed between revisions")
    v1_restart_revision_name = v1_restart_status["latestReadyRevisionName"]
    if v1_restart_revision_name == v1_revision_name:
        raise RuntimeError(
            "redeploying v1 again did not yield a new Cloud Run revision; "
            "the restart-durability proof needs a genuinely fresh process"
        )
    await asyncio.to_thread(_wait_for_revision, url, "v1")
    before_restart_replay = await asyncio.to_thread(_json_get, f"{url}/evidence")
    restart_replay = await _call_with_token(endpoint, v1_token, customer_id=customer_id)
    restart_replay_denial = await asyncio.to_thread(
        _poll_for_denial,
        cloud,
        revision_name=v1_restart_revision_name,
        nonce=v1_token.nonce,
        reason=Denial.REPLAYED,
    )
    after_restart_replay = await asyncio.to_thread(_json_get, f"{url}/evidence")

    return {
        "schema_version": 1,
        "proof_id": proof_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "code_revision": _git_revision(),
        "digest_algorithm": DIGEST_ALGORITHM,
        "project": project,
        "claim_boundary": CLAIM_BOUNDARY,
        "nonce_ledger_backend": "firestore" if firestore_project else "in_memory",
        "cloud_run": {
            "service": SERVICE,
            "url": url,
            "image": image,
            "v1_revision": v1_revision_name,
            "v2_revision": v2_revision_name,
            "v1_restart_revision": v1_restart_revision_name,
        },
        "v1_token": asdict(v1_token),
        "v2_token": asdict(v2_token),
        "positive_control": {
            "result": positive,
            "dispatch_count_before": before_positive["dispatch_count"],
            "dispatch_count_after": after_positive["dispatch_count"],
            "instance_id": after_positive["instance_id"],
        },
        "replay_control": {
            "result": replay,
            "denied": replay["is_error"],
            "denial_log": replay_denial,
            "dispatch_count_before": after_positive["dispatch_count"],
            "dispatch_count_after": after_replay["dispatch_count"],
        },
        "digest_mismatch_control": {
            "result": mismatch,
            "denied": mismatch["is_error"],
            "denial_log": mismatch_denial,
            "dispatch_count_before": before_mismatch["dispatch_count"],
            "dispatch_count_after": after_mismatch["dispatch_count"],
            "instance_id_before": before_mismatch["instance_id"],
            "instance_id_after": after_mismatch["instance_id"],
        },
        "v2_positive_control": {
            "result": v2_positive,
            "dispatch_count_before": after_mismatch["dispatch_count"],
            "dispatch_count_after": after_v2_positive["dispatch_count"],
        },
        "restart_replay_control": {
            "result": restart_replay,
            "denied": restart_replay["is_error"],
            "denial_log": restart_replay_denial,
            "dispatch_count_before": before_restart_replay["dispatch_count"],
            "dispatch_count_after": after_restart_replay["dispatch_count"],
            "instance_id_before": before_restart_replay["instance_id"],
            "instance_id_after": after_restart_replay["instance_id"],
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
        print(f"live revision binding proof failed: {error}", file=sys.stderr)
        return 1
    OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"live revision binding evidence written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
