"""Revision-switchable MCP server for the stale Agent Registry proof.

The process exposes one stable MCP endpoint while ``CUSTODY_MCP_REVISION``
selects the tool contract registered at startup.  Dispatch evidence is kept
in-process by design; the live proof must pin Cloud Run to one instance and
verify ``instance_id`` before comparing counters.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from typing import Mapping

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse


SUPPORTED_REVISIONS = frozenset({"v1", "v2"})
GATEWAY_DISPATCH_EVENT = "custody.gateway.lookup.dispatched.v1"
GATEWAY_UNBOUND_EVENT = "custody.gateway.lookup.unbound.v1"
_GATEWAY_CUSTOMER_ID = re.compile(
    r"custody-gateway-(?P<proof_id>[0-9a-f]{32})-(?P<control>allow|deny)"
)
_TRACEPARENT = re.compile(
    r"00-(?P<trace_id>(?!0{32})[0-9a-f]{32})-"
    r"(?P<span_id>(?!0{16})[0-9a-f]{16})-[0-9a-f]{2}"
)
_STRUCTURED_LOG_LOCK = threading.Lock()


def _configured_revision() -> str:
    revision = os.environ.get("CUSTODY_MCP_REVISION", "v1").strip().lower()
    if revision not in SUPPORTED_REVISIONS:
        supported = ", ".join(sorted(SUPPORTED_REVISIONS))
        raise RuntimeError(
            f"unsupported CUSTODY_MCP_REVISION={revision!r}; expected {supported}"
        )
    return revision


class DispatchLedger:
    """Owns the process-local evidence needed to prove pre-dispatch blocking."""

    def __init__(self, *, revision: str) -> None:
        self._revision = revision
        self._instance_id = os.environ.get("HOSTNAME") or uuid.uuid4().hex
        self._lock = threading.Lock()
        self._dispatch_count = 0
        self._forwarding_dispatch_count = 0
        self._last_dispatched_at: str | None = None

    def record(self, *, forwarding_requested: bool) -> dict[str, object]:
        with self._lock:
            self._dispatch_count += 1
            if forwarding_requested:
                self._forwarding_dispatch_count += 1
            self._last_dispatched_at = datetime.now(UTC).isoformat()
            return self._snapshot_unlocked()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict[str, object]:
        return {
            "revision": self._revision,
            "instance_id": self._instance_id,
            "dispatch_count": self._dispatch_count,
            "forwarding_dispatch_count": self._forwarding_dispatch_count,
            "last_dispatched_at": self._last_dispatched_at,
        }


REVISION = _configured_revision()
LEDGER = DispatchLedger(revision=REVISION)
mcp = FastMCP("Custody Export MCP")


def _customer_record(customer_id: str) -> dict[str, object]:
    """Return deterministic synthetic data; the proof never handles real PII."""
    return {
        "customer_id": customer_id,
        "company": f"Synthetic Customer {customer_id}",
        "plan": "enterprise",
        "region": "us-central1",
    }


def _write_structured_log(event: Mapping[str, object]) -> None:
    """Write one atomic JSON line for Cloud Run's structured log collector."""
    try:
        with _STRUCTURED_LOG_LOCK:
            print(
                json.dumps(event, separators=(",", ":"), sort_keys=True),
                flush=True,
            )
    except OSError:
        # Telemetry must not change the lookup contract if stdout is unavailable.
        return


def _log_gateway_dispatch(
    customer_id: str,
    dispatch: Mapping[str, object],
    *,
    forwarding_requested: bool,
) -> None:
    """Bind an exact Gateway proof request to the server-owned dispatch fact."""
    customer_match = _GATEWAY_CUSTOMER_ID.fullmatch(customer_id)
    if customer_match is None:
        return

    try:
        traceparent = get_http_request().headers.get("traceparent", "")
    except RuntimeError:
        traceparent = ""
    trace_match = _TRACEPARENT.fullmatch(traceparent)
    if trace_match is None:
        _write_structured_log(
            {
                "severity": "WARNING",
                "message": "Gateway lookup dispatched without a valid traceparent",
                "event": GATEWAY_UNBOUND_EVENT,
                "proof_id": customer_match["proof_id"],
                "customer_id": customer_id,
                "instance_id": dispatch["instance_id"],
                "dispatch_id": dispatch["dispatch_count"],
                "forwarding_requested": forwarding_requested,
                "forwarding_dispatch_count": dispatch[
                    "forwarding_dispatch_count"
                ],
                "revision": dispatch["revision"],
                "server_dispatched_at": dispatch["last_dispatched_at"],
            }
        )
        return

    _write_structured_log(
        {
            "severity": "INFO",
            "message": "Custody Gateway lookup reached the owned MCP handler",
            "event": GATEWAY_DISPATCH_EVENT,
            "proof_id": customer_match["proof_id"],
            "trace_id": trace_match["trace_id"],
            "customer_id": customer_id,
            "instance_id": dispatch["instance_id"],
            "dispatch_id": dispatch["dispatch_count"],
            "forwarding_requested": forwarding_requested,
            "forwarding_dispatch_count": dispatch["forwarding_dispatch_count"],
            "revision": dispatch["revision"],
            "server_dispatched_at": dispatch["last_dispatched_at"],
        }
    )


def _record_lookup(
    customer_id: str, *, forwarding_requested: bool
) -> dict[str, object]:
    """Record a dispatch and emit its proof event from one server-owned snapshot."""
    dispatch = LEDGER.record(forwarding_requested=forwarding_requested)
    _log_gateway_dispatch(
        customer_id,
        dispatch,
        forwarding_requested=forwarding_requested,
    )
    return dispatch


if REVISION == "v1":

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Lookup customer",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        )
    )
    def lookup_customer(customer_id: str) -> dict[str, object]:
        """Read one synthetic customer record from the internal catalog."""
        dispatch = _record_lookup(customer_id, forwarding_requested=False)
        return {
            **_customer_record(customer_id),
            "server_revision": REVISION,
            "instance_id": dispatch["instance_id"],
            "dispatch_id": dispatch["dispatch_count"],
        }

else:

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Lookup or forward customer",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        )
    )
    def lookup_customer(
        customer_id: str,
        forward_to: str | None = None,
    ) -> dict[str, object]:
        """Read a synthetic customer and optionally queue an external forward."""
        forwarding_requested = forward_to is not None
        dispatch = _record_lookup(
            customer_id, forwarding_requested=forwarding_requested
        )
        return {
            **_customer_record(customer_id),
            "server_revision": REVISION,
            "instance_id": dispatch["instance_id"],
            "dispatch_id": dispatch["dispatch_count"],
            "forwarding_requested": forwarding_requested,
            "forwarded_to": forward_to,
            "forwarding_status": "simulated" if forwarding_requested else "not-requested",
        }


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    """Report readiness and bind it to the serving process and revision."""
    del request
    snapshot = LEDGER.snapshot()
    return JSONResponse(
        {
            "status": "ok",
            "revision": snapshot["revision"],
            "instance_id": snapshot["instance_id"],
        }
    )


@mcp.custom_route("/evidence", methods=["GET"])
async def evidence(request: Request) -> JSONResponse:
    """Expose process-local counters without retaining tool arguments or PII."""
    del request
    return JSONResponse(LEDGER.snapshot())


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
