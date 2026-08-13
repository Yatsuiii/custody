"""Adversarial tests for server-authored Gateway dispatch evidence."""

from __future__ import annotations

import asyncio
import inspect
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from live.registry_attack.server import server


PROOF_ID = "c4b935f570c14c098802ab11fb8d198e"
TRACE_ID = "1dfe95b7ef8b4ca6ac3581f70ed8a165"
CUSTOMER_ID = f"custody-gateway-{PROOF_ID}-allow"
TRACEPARENT = f"00-{TRACE_ID}-0000000000000001-01"


def _request(traceparent: str) -> SimpleNamespace:
    return SimpleNamespace(headers={"traceparent": traceparent})


def _logged_event(output: io.StringIO) -> dict[str, object]:
    lines = output.getvalue().splitlines()
    if len(lines) != 1:
        raise AssertionError(f"expected one structured log line, got {lines!r}")
    event = json.loads(lines[0])
    if not isinstance(event, dict):
        raise AssertionError("structured log must decode to an object")
    return event


class GatewayDispatchLogTests(unittest.TestCase):
    def test_gateway_lookup_binds_request_to_server_owned_snapshot(self) -> None:
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"HOSTNAME": "owned-cloud-run-instance"}),
            patch.object(server, "LEDGER", server.DispatchLedger(revision="v2")),
            patch.object(server, "get_http_request", return_value=_request(TRACEPARENT)),
            redirect_stdout(output),
        ):
            dispatch = server._record_lookup(
                CUSTOMER_ID, forwarding_requested=False
            )

        event = _logged_event(output)
        self.assertEqual(event["event"], server.GATEWAY_DISPATCH_EVENT)
        self.assertEqual(event["proof_id"], PROOF_ID)
        self.assertEqual(event["trace_id"], TRACE_ID)
        self.assertEqual(event["customer_id"], CUSTOMER_ID)
        self.assertEqual(event["instance_id"], dispatch["instance_id"])
        self.assertEqual(event["dispatch_id"], dispatch["dispatch_count"])
        self.assertIs(event["forwarding_requested"], False)
        self.assertEqual(event["forwarding_dispatch_count"], 0)
        self.assertEqual(event["revision"], dispatch["revision"])
        self.assertEqual(
            event["server_dispatched_at"], dispatch["last_dispatched_at"]
        )
        self.assertEqual(event["severity"], "INFO")
        self.assertIsNotNone(
            datetime.fromisoformat(str(event["server_dispatched_at"])).tzinfo
        )

    def test_noncanonical_customer_cannot_emit_proof_grade_event(self) -> None:
        dispatch = {
            "revision": "v2",
            "instance_id": "owned-instance",
            "dispatch_count": 7,
            "forwarding_dispatch_count": 0,
            "last_dispatched_at": "2026-08-13T08:28:10+00:00",
        }
        invalid_ids = (
            f"custody-gateway-{PROOF_ID}-allow-extra",
            f"custody-gateway-{PROOF_ID.upper()}-allow",
            f"custody-gateway-{PROOF_ID}-replay",
            "custody-registry-attack",
        )

        for customer_id in invalid_ids:
            with self.subTest(customer_id=customer_id):
                output = io.StringIO()
                with (
                    patch.object(
                        server,
                        "get_http_request",
                        side_effect=AssertionError("request context must not be read"),
                    ),
                    redirect_stdout(output),
                ):
                    server._log_gateway_dispatch(
                        customer_id, dispatch, forwarding_requested=False
                    )
                self.assertEqual(output.getvalue(), "")

    def test_invalid_traceparent_emits_only_non_proof_warning(self) -> None:
        dispatch = {
            "revision": "v2",
            "instance_id": "owned-instance",
            "dispatch_count": 7,
            "forwarding_dispatch_count": 0,
            "last_dispatched_at": "2026-08-13T08:28:10+00:00",
        }
        invalid_headers = (
            "",
            f"00-{'0' * 32}-0000000000000001-01",
            f"00-{TRACE_ID}-{'0' * 16}-01",
            TRACEPARENT.upper(),
            f"01-{TRACE_ID}-0000000000000001-01",
            f"{TRACEPARENT}-replayed",
        )

        for traceparent in invalid_headers:
            with self.subTest(traceparent=traceparent):
                output = io.StringIO()
                with (
                    patch.object(
                        server,
                        "get_http_request",
                        return_value=_request(traceparent),
                    ),
                    redirect_stdout(output),
                ):
                    server._log_gateway_dispatch(
                        CUSTOMER_ID, dispatch, forwarding_requested=False
                    )
                event = _logged_event(output)
                self.assertEqual(event["event"], server.GATEWAY_UNBOUND_EVENT)
                self.assertNotIn("trace_id", event)

    def test_missing_http_context_cannot_fabricate_bound_trace(self) -> None:
        dispatch = {
            "revision": "v2",
            "instance_id": "owned-instance",
            "dispatch_count": 7,
            "forwarding_dispatch_count": 0,
            "last_dispatched_at": "2026-08-13T08:28:10+00:00",
        }
        output = io.StringIO()
        with (
            patch.object(
                server,
                "get_http_request",
                side_effect=RuntimeError("No active HTTP request found."),
            ),
            redirect_stdout(output),
        ):
            server._log_gateway_dispatch(
                CUSTOMER_ID, dispatch, forwarding_requested=False
            )

        event = _logged_event(output)
        self.assertEqual(event["event"], server.GATEWAY_UNBOUND_EVENT)
        self.assertNotIn("trace_id", event)

    def test_mcp_tool_schema_has_no_evidence_parameters(self) -> None:
        tools = asyncio.run(server.mcp.get_tools())
        tool = tools["lookup_customer"]
        properties = tool.parameters["properties"]

        self.assertIn("customer_id", properties)
        self.assertNotIn("proof_id", properties)
        self.assertNotIn("trace_id", properties)
        self.assertNotIn("dispatch_id", properties)
        parameters = inspect.signature(tool.fn).parameters
        self.assertEqual(set(parameters), set(properties))


if __name__ == "__main__":
    unittest.main()
