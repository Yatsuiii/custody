"""Failure injection for the live Memory Bank write path (D2).

`AgentEngineMemoryBank.write_record` is the one place a trusted record
actually leaves the process and reaches Vertex AI Memory Bank. Every other
test of this project's memory boundary (`test_service.py`,
`test_adk_memory_bank.py`) exercises the happy path: the downstream accepts
the write. None of them ask what happens when it does not.

This closes that gap for the judge-named failure: Memory Bank unreachable
must deny/quarantine the write, not silently report success. The mock
client raises exactly what the real SDK raises on an outage
(`google.genai.errors.ClientError`, matching the 409-swallowing branch
`write_record` already special-cases) and on a bare network failure
(`TimeoutError`, which is not a `ClientError` at all), so both shapes of
"unreachable" are covered.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field

from google.genai.errors import ClientError

from custody.adapters.memory_bank import AgentEngineMemoryBank, RevokingMemoryBankGraph
from custody.graph import CustodyGraph
from custody.origin import Admitted, CustodyRecord, Origin, ToolTrust, Trust
from custody.service import CustodyMemoryService, InMemoryQuarantine
from tests.test_origin import tool as tool_event
from tests.test_service import FakeSession


def _admitted(record_id: str = "inv-1:0:0") -> Admitted:
    record = CustodyRecord(
        origin=Origin.TOOL,
        trust=Trust.TRUSTED,
        author="crm_lookup",
        invocation_id="inv-1",
        content_sha256="sha-1",
        source_tool="crm_lookup",
        id=record_id,
    )
    return Admitted(text="the account renews in March", record=record, event_index=0)


@dataclass
class _RaisingMemoriesClient:
    """Stands in for `agent_engines.memories`: every call raises the same
    configured error, so a `create` failure looks exactly like the live
    outage it is meant to model."""

    error: BaseException
    calls: list = field(default_factory=list)

    async def create(self, *, name, fact, scope, config):
        self.calls.append((name, fact, scope, config))
        raise self.error

    async def retrieve(self, *, name, scope, similarity_search_params):
        raise self.error

    async def delete(self, *, name):
        self.calls.append(name)
        raise self.error


class WriteRecordFailsClosedOnAnUnreachableMemoryBank(unittest.IsolatedAsyncioTestCase):
    async def test_a_503_from_the_live_service_is_not_swallowed(self):
        """The one non-409 branch `write_record` already carves out. A
        service-unavailable response must still reach the caller as a
        failure, not be mistaken for the 409-already-written case."""
        client = _RaisingMemoriesClient(ClientError(503, {"error": "unavailable"}))
        bank = AgentEngineMemoryBank(memories=client, engine_name="engines/1")

        with self.assertRaises(ClientError):
            await bank.write_record(
                app_name="fleet", user_id="platform-team", admitted=_admitted()
            )
        self.assertEqual(len(client.calls), 1)

    async def test_a_bare_timeout_is_not_swallowed_either(self):
        """Not every outage arrives as a `ClientError`: a dropped connection
        or a client-side timeout raises its own stdlib exception, and the
        409 special case must not be written broadly enough to catch it."""
        client = _RaisingMemoriesClient(TimeoutError("memory bank unreachable"))
        bank = AgentEngineMemoryBank(memories=client, engine_name="engines/1")

        with self.assertRaises(TimeoutError):
            await bank.write_record(
                app_name="fleet", user_id="platform-team", admitted=_admitted()
            )

    async def test_a_409_replay_is_still_treated_as_already_written(self):
        """Sanity control for the two tests above: this is the one error
        shape that must NOT propagate, so the failure-injection tests are
        proven to test the unreachable case specifically, not any error at
        all."""
        client = _RaisingMemoriesClient(ClientError(409, {"error": "exists"}))
        bank = AgentEngineMemoryBank(memories=client, engine_name="engines/1")

        await bank.write_record(
            app_name="fleet", user_id="platform-team", admitted=_admitted()
        )  # must not raise


class SessionWriteFailsClosedThroughTheGuardedService(unittest.IsolatedAsyncioTestCase):
    """The end-to-end path: a session carrying trusted content, guarded by
    `CustodyMemoryService`, with a `write_record` downstream that cannot
    reach Memory Bank. Nothing about `add_session_to_memory` may report
    success when the actual write never landed."""

    async def test_an_unreachable_memory_bank_fails_the_whole_session_write(self):
        client = _RaisingMemoriesClient(ClientError(503, {"error": "unavailable"}))
        downstream = AgentEngineMemoryBank(memories=client, engine_name="engines/1")
        service = CustodyMemoryService(
            downstream=downstream,
            quarantine=InMemoryQuarantine(),
            tools=ToolTrust(frozenset({"crm_lookup"})),
        )
        session = FakeSession(
            events=[tool_event("crm_lookup", {"note": "the account renews in March"})]
        )

        with self.assertRaises(ClientError):
            await service.add_session_to_memory(session)


class RevokeFailsClosedOnAnUnreachableMemoryBank(unittest.IsolatedAsyncioTestCase):
    async def test_a_revoke_that_cannot_reach_memory_bank_does_not_report_success(self):
        """D2's selective-deletion path: revoking a tool removes the graph
        edges and deletes each descendant's memory. If the delete call
        cannot reach Memory Bank, the revocation must not be reported as
        having cleaned up memory it never touched."""
        graph = CustodyGraph()
        graph.add(_admitted().record)
        client = _RaisingMemoriesClient(ClientError(503, {"error": "unavailable"}))
        revoking = RevokingMemoryBankGraph(
            graph=graph, memories=client, engine_name="engines/1"
        )

        with self.assertRaises(ClientError):
            await revoking.revoke(tool="crm_lookup", revocation_id="rev-1")


if __name__ == "__main__":
    unittest.main()
