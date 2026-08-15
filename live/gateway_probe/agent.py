"""Deterministic Agent Runtime workload for proving Gateway enforcement.

G1 already proves Gemini and ADK. This workload isolates the network-security
claim: Agent Runtime owns the process and SPIFFE identity, while four explicit
MCP JSON-RPC requests make Gateway classification independently observable.
"""

import json
import re
from typing import Any

import httpx

TRACE_ID = re.compile(r"[0-9a-f]{32}")


def _sse_json(response: httpx.Response) -> dict[str, Any]:
    """Decode the single JSON-RPC message returned by Streamable HTTP."""
    payloads = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    if len(payloads) != 1:
        raise ValueError(
            f"expected one MCP SSE data event; received {len(payloads)}"
        )
    payload = json.loads(payloads[0])
    if not isinstance(payload, dict):
        raise TypeError("MCP response payload must be an object")
    if error := payload.get("error"):
        raise RuntimeError(f"MCP JSON-RPC error: {error}")
    return payload


class _McpWireClient:
    """Expose one deep operation over the explicit MCP request sequence."""

    def __init__(self, url: str, trace_id: str):
        self._url = url
        self._headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "traceparent": f"00-{trace_id}-0000000000000001-01",
        }

    async def call(self, tool_name: str, customer_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            initialized = await self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "custody-gateway-probe",
                            "version": "1",
                        },
                    },
                },
            )
            session_id = initialized.headers.get("mcp-session-id")
            if not session_id:
                raise RuntimeError("MCP initialize omitted mcp-session-id")
            self._headers["Mcp-Session-Id"] = session_id
            _sse_json(initialized)

            notification = await self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
            )
            if notification.status_code != 202:
                raise RuntimeError(
                    "MCP initialized notification did not return 202"
                )

            listed = await self._post(
                client,
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            tools = _sse_json(listed).get("result", {}).get("tools", [])
            names = [tool.get("name") for tool in tools]
            if names != ["lookup_customer"]:
                raise RuntimeError(f"unexpected live MCP tool surface: {names}")

            call_params: dict[str, Any] = {
                "name": tool_name,
                "arguments": {"customer_id": customer_id},
            }
            # R2's SurfaceAttestationMiddleware binds a tools/call to the
            # tools/list read that authorized it: every tool in that read
            # carries a short-lived signed token in its own _meta, and the
            # server refuses to dispatch unless the caller presents it back.
            # This hand-rolled wire client predates R2, which landed on the
            # same MCP server this probe also calls; without round-tripping
            # the token every call here now fails with "dispatch attestation
            # missing" before ever reaching Gateway policy or the ledger.
            matched = next(
                (tool for tool in tools if tool.get("name") == tool_name), None
            )
            token = (matched or {}).get("_meta", {}).get("custody_attestation")
            if isinstance(token, dict):
                call_params["_meta"] = {"custody_attestation": token}

            called = await self._post(
                client,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": call_params,
                },
            )
            result = _sse_json(called).get("result")
            if not isinstance(result, dict):
                raise TypeError("MCP tools/call returned no result object")
            return result

    async def _post(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> httpx.Response:
        response = await client.post(
            self._url, headers=self._headers, json=payload
        )
        response.raise_for_status()
        return response


class GatewayProbe:
    """Make exactly one owned MCP tool call from Agent Runtime."""

    def __init__(self, mcp_url: str):
        self._mcp_url = mcp_url

    async def async_query(
        self,
        *,
        customer_id: str,
        trace_id: str,
        proof_id: str,
        tool_name: str = "lookup_customer",
    ) -> dict[str, Any]:
        """Return the tool result or the Gateway refusal as structured data."""
        if not TRACE_ID.fullmatch(trace_id):
            raise ValueError("trace_id must be 32 lowercase hexadecimal digits")
        if not customer_id.startswith("custody-gateway-"):
            raise ValueError("customer_id must identify a Custody gateway probe")
        if tool_name not in {"lookup_customer", "custody_policy_canary"}:
            raise ValueError("tool_name is outside the bounded Gateway proof")

        try:
            result = await _McpWireClient(self._mcp_url, trace_id).call(
                tool_name, customer_id
            )
        except Exception as error:  # The remote boundary reports policy denial.
            return {
                "ok": False,
                "customer_id": customer_id,
                "proof_id": proof_id,
                "tool_name": tool_name,
                "error_type": type(error).__name__,
                "error": str(error),
            }

        return {
            "ok": not bool(result.get("isError", False)),
            "customer_id": customer_id,
            "proof_id": proof_id,
            "tool_name": tool_name,
            "is_error": bool(result.get("isError", False)),
            "data": result,
        }
