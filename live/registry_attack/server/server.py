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
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import Middleware
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from custody.nonce_ledger import FirestoreNonceLedger
from custody.revision import (
    ApprovedTool,
    AttestationAuthority,
    Denial,
    InMemoryNonceLedger,
    NonceLedger,
    SurfaceAttestation,
    ToolSurface,
)


SUPPORTED_REVISIONS = frozenset({"v1", "v2"})
GATEWAY_DISPATCH_EVENT = "custody.gateway.lookup.dispatched.v1"
GATEWAY_UNBOUND_EVENT = "custody.gateway.lookup.unbound.v1"
#: R2: an allowed ``tools/call`` must carry the token minted by the most
#: recent ``tools/list`` read of this exact server, closing the window R1
#: left open between admission and dispatch.
ATTESTATION_DENIED_EVENT = "custody.attestation.denied.v1"
ATTESTATION_SERVER_LABEL = "custody-export-mcp"
_ATTESTATION_META_KEY = "custody_attestation"
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


def _configured_attestation_secret() -> bytes:
    """A random per-process fallback keeps import-time construction safe for
    anything that never dispatches a real tool call (offline tests, ad hoc
    imports). It is never adequate for a live proof: two Cloud Run revisions
    of ``custody-export-mcp`` are two different processes, and R2's negative
    control specifically needs a token minted by one to verify against the
    other, so the live deploy must always pass the same
    ``CUSTODY_ATTESTATION_SECRET`` explicitly to both revisions."""
    secret = os.environ.get("CUSTODY_ATTESTATION_SECRET", "").strip()
    return secret.encode("utf-8") if secret else uuid.uuid4().bytes


def _configured_attestation_ttl_seconds() -> float:
    """Default matches ``AttestationAuthority``'s own default (45s), a
    realistic dispatch window. A live redeploy-based proof needs a token
    minted before one Cloud Run revision swap to still be presentable after
    it, so the proof deploy overrides this higher; the mechanism being
    proved (digest recheck at dispatch) is unchanged either way."""
    raw = os.environ.get("CUSTODY_ATTESTATION_TTL_SECONDS", "").strip()
    return float(raw) if raw else 45.0


def _configured_nonce_ledger() -> NonceLedger:
    """Firestore-backed when a project is configured, so replay protection
    survives a restart and is shared across every instance sharing that
    project; pure in-process otherwise, so offline tests and a bare `python
    server.py` need no cloud account. Same env-var-gated pattern
    `custody/control_plane.py::_default_plane()` already uses."""
    project = os.environ.get("CUSTODY_FIRESTORE_PROJECT", "").strip()
    if not project:
        return InMemoryNonceLedger()
    from google.cloud import firestore

    return FirestoreNonceLedger(firestore.Client(project=project))


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
ATTESTATION = AttestationAuthority(
    _configured_attestation_secret(),
    _configured_attestation_ttl_seconds(),
    _ledger=_configured_nonce_ledger(),
)
mcp = FastMCP("Custody Export MCP")


def _tool_revision(tool) -> str:
    """The same canonical digest a client computes from a real ``tools/list``.

    Built fresh from the tool's own declared identity every time this is
    called, never from a cached value, so a dispatch-time recheck reflects
    what this server would return right now, not what it returned earlier.
    """
    raw = tool.to_mcp_tool(include_fastmcp_meta=False).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    surface = ToolSurface.from_tools_list(
        server=ATTESTATION_SERVER_LABEL, payload={"tools": [raw]}
    )
    return surface.tools[0].revision


def _dump_attestation(token: SurfaceAttestation) -> dict[str, object]:
    return {
        "tool_id": token.tool_id,
        "revision": token.revision,
        "nonce": token.nonce,
        "issued_at": token.issued_at,
        "expires_at": token.expires_at,
        "signature": token.signature,
    }


def _load_attestation(fastmcp_context) -> SurfaceAttestation | None:
    """Pull a caller-presented token out of the request's ``_meta``.

    Reads it from ``Context.request_context.meta``, not
    ``MiddlewareContext.message.meta``: FastMCP's own dispatcher rebuilds
    ``CallToolRequestParams`` from just ``(name, arguments)`` before handing
    it to a middleware's ``on_call_tool``, discarding whatever ``_meta`` the
    real request carried. The low-level MCP SDK still holds the original,
    unmodified request meta in its own ``request_ctx`` contextvar for the
    duration of the call, which ``Context.request_context`` exposes; that is
    the only place this token survives to be read back.

    ``_meta`` is the one field a caller cannot smuggle tool identity into
    without also failing the signature check: it rides outside the fields
    ``_tool_revision`` digests (see ``ToolSurface.from_tools_list``).
    """
    if fastmcp_context is None:
        return None
    meta = fastmcp_context.request_context.meta
    raw = getattr(meta, _ATTESTATION_META_KEY, None) if meta is not None else None
    if not isinstance(raw, Mapping):
        return None
    try:
        return SurfaceAttestation(
            tool_id=str(raw["tool_id"]),
            revision=str(raw["revision"]),
            nonce=str(raw["nonce"]),
            issued_at=float(raw["issued_at"]),
            expires_at=float(raw["expires_at"]),
            signature=str(raw["signature"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _log_attestation_denial(tool_name: str, reason: Denial) -> None:
    snapshot = LEDGER.snapshot()
    _write_structured_log(
        {
            "severity": "WARNING",
            "message": "Custody dispatch attestation refused before invocation",
            "event": ATTESTATION_DENIED_EVENT,
            "tool_name": tool_name,
            "reason": reason.value,
            "instance_id": snapshot["instance_id"],
            "revision": snapshot["revision"],
            "dispatch_count": snapshot["dispatch_count"],
        }
    )


class SurfaceAttestationMiddleware(Middleware):
    """Binds an allowed ``tools/call`` to the ``tools/list`` read that
    authorized it (R2), closing the window R1 left open between admission
    and dispatch.

    Every ``tools/list`` response mints one short-lived, server-signed token
    per tool, carried in that tool's ``_meta``. A ``tools/call`` must present
    the matching token; this server recomputes the tool's live digest at the
    instant of dispatch and refuses to run it on any mismatch, expiry, replay,
    or invalid signature. This closes the declared-surface TOCTOU only: a
    behavior-only change under an identical ``tools/list`` is not, and cannot
    be, detected here, since nothing here attests the server's running code,
    only the schema it declares. The consumed-nonce set is process-local,
    the same single-owned-instance scope this proof's dispatch ledger
    already requires.
    """

    async def on_list_tools(self, context, call_next):
        tools = await call_next(context)
        attested = []
        for tool in tools:
            approved = ApprovedTool(
                tool_id=f"{ATTESTATION_SERVER_LABEL}/{tool.name}",
                runtime_name=tool.name,
                revision=_tool_revision(tool),
            )
            token = ATTESTATION.mint(tool=approved)
            meta = dict(tool.meta or {})
            meta[_ATTESTATION_META_KEY] = _dump_attestation(token)
            attested.append(tool.model_copy(update={"meta": meta}))
        return attested

    async def on_call_tool(self, context, call_next):
        tool_name = context.message.name
        token = _load_attestation(context.fastmcp_context)
        if token is None:
            _log_attestation_denial(tool_name, Denial.SIGNATURE_INVALID)
            raise ToolError(f"dispatch attestation missing for {tool_name}")

        tool = await context.fastmcp_context.fastmcp.get_tool(tool_name)
        denial = ATTESTATION.verify(token, live_revision=_tool_revision(tool))
        if denial is not None:
            _log_attestation_denial(tool_name, denial)
            raise ToolError(f"dispatch attestation refused: {denial.value}")

        return await call_next(context)


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
                "forwarding_dispatch_count": dispatch["forwarding_dispatch_count"],
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
            "forwarding_status": "simulated"
            if forwarding_requested
            else "not-requested",
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


mcp.add_middleware(SurfaceAttestationMiddleware())


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
