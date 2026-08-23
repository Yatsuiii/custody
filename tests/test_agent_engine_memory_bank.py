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
from pathlib import Path

from google.genai.errors import ClientError

from custody.action import AuthorityAction, AuthorityGateway
from custody.adapters.memory_bank import (
    AgentEngineMemoryBank,
    RevokingAuthorityMemoryBank,
    RevokingMemoryBankGraph,
)
from custody.authority import (
    AdmissionGate,
    AuthorityConflict,
    AuthorityOutput,
    Capability,
    InMemoryAuthorityStore,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    RevocationController,
    SourceAuthorityEvent,
)
from custody.graph import CustodyGraph
from custody.origin import Admitted, CustodyRecord, Origin, ToolTrust, Trust
from custody.service import CustodyMemoryService, InMemoryQuarantine
from tests.test_origin import tool as tool_event
from tests.test_service import FakeSession


B7_FIXTURES = Path(__file__).parent / "fixtures" / "b7"


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

    async def get(self, *, name):
        raise self.error

    async def delete(self, *, name):
        self.calls.append(name)
        raise self.error


@dataclass
class _Memory:
    name: str
    fact: str
    metadata: dict


@dataclass
class _Retrieved:
    memory: _Memory | None


class _Pager:
    def __init__(self, values):
        self._values = iter(values)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._values)
        except StopIteration as error:
            raise StopAsyncIteration from error


@dataclass
class _RecordingMemoriesClient:
    memories: dict[str, _Memory] = field(default_factory=dict)

    async def create(self, *, name, fact, scope, config):
        del scope
        memory_name = f"{name}/memories/{config['memory_id']}"
        if memory_name in self.memories:
            raise ClientError(409, {"error": "exists"})
        self.memories[memory_name] = _Memory(
            name=memory_name,
            fact=fact,
            metadata=config["metadata"],
        )

    async def get(self, *, name):
        return self.memories[name]

    async def retrieve(self, *, name, scope, similarity_search_params):
        del name, scope, similarity_search_params
        return _Pager(_Retrieved(memory) for memory in self.memories.values())

    async def delete(self, *, name):
        self.memories.pop(name, None)


def _authority_environment():
    event = SourceAuthorityEvent.from_json(
        (B7_FIXTURES / "source_event.json").read_bytes()
    )
    source = event.receipt.policy_key
    identity = PolicyKey("finance", "custody", "identity", "R1", "export.send")
    registered = PolicyKey(
        "finance", "custody", "vendor_projection", "R1", "export.send"
    )
    freeform = PolicyKey("finance", "model", "freeform", "R1", "export.send")
    store = InMemoryAuthorityStore()
    store.put_issuer_key(
        issuer_id=event.receipt.issuer_id,
        issuer_key_id=event.receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (B7_FIXTURES / "issuer_public_key.hex").read_text().strip()
        ),
    )
    for snapshot in (
        PolicySnapshot(
            source,
            "v7",
            7,
            OperationRole.ORIGIN,
            {"export.send": Capability.ACT},
        ),
        *(
            PolicySnapshot(
                key,
                "v1",
                1,
                OperationRole.RELAY,
                {"export.send": Capability.ACT},
            )
            for key in (identity, registered, freeform)
        ),
    ):
        store.put_policy(snapshot)
    gate = AdmissionGate(
        store=store,
        source_policy_keys=(source,),
        identity_policy_key=identity,
        registered_policy_keys=(registered,),
        freeform_policy_key=freeform,
    )
    admitted = gate.admit_source(
        event,
        AuthorityOutput(
            record_id="ROOT-01",
            payload_digest=event.source_object_commitment,
        ),
    )
    assert admitted.admitted
    return event, store


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

        # The downstream failed before the memory became durable. The
        # provenance graph must not advertise a record that cannot be
        # retrieved or revoked from the memory substrate.
        self.assertEqual(len(service.graph), 0)


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

    async def test_b7_logical_block_survives_cleanup_failure(self):
        event, store = _authority_environment()
        client = _RaisingMemoriesClient(ClientError(503, {"error": "unavailable"}))
        revoking = RevokingAuthorityMemoryBank(
            RevocationController(store), client, "engines/1"
        )
        root_key = ReceiptRootKey.from_receipt(
            event.receipt, custody_root_record_id="ROOT-01"
        )

        with self.assertRaises(ClientError):
            await revoking.revoke_receipt_roots(
                revocation_id="root-rev-1", root_keys=(root_key,)
            )

        class Dispatcher:
            def dispatch(self, action):
                raise AssertionError(f"revoked action dispatched: {action}")

        execution = AuthorityGateway(store).execute(
            AuthorityAction("after-cleanup-failure", "export.send", {"value": 1}),
            ("ROOT-01",),
            Dispatcher(),
        )
        self.assertFalse(execution.decision.allowed)
        self.assertEqual(execution.decision.reason, "REVOKED_AUTHORITY_ROOT")


class B7MemoryIdentitySurvivesRetrieval(unittest.IsolatedAsyncioTestCase):
    async def test_committed_record_round_trips_with_exact_id_and_payload(self):
        event, store = _authority_environment()
        client = _RecordingMemoriesClient()
        bank = AgentEngineMemoryBank(
            memories=client,
            engine_name="engines/1",
            authority_state=store,
        )
        text = event.canonical_source_bytes.decode("utf-8")

        await bank.write_authority_record(
            app_name="fleet",
            user_id="platform-team",
            record_id="ROOT-01",
            text=text,
        )
        found = await bank.search_authority_memory(
            app_name="fleet", user_id="platform-team", query="account"
        )

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].record_id, "ROOT-01")
        self.assertEqual(found[0].fact, text)
        self.assertEqual(found[0].envelope_version, "b7/p2-v1")

    async def test_missing_or_changed_identity_metadata_fails_closed(self):
        event, store = _authority_environment()
        client = _RecordingMemoriesClient()
        bank = AgentEngineMemoryBank(client, "engines/1", store)
        text = event.canonical_source_bytes.decode("utf-8")
        await bank.write_authority_record(
            app_name="fleet",
            user_id="platform-team",
            record_id="ROOT-01",
            text=text,
        )
        memory = next(iter(client.memories.values()))
        memory.metadata = {}

        missing = await bank.search_authority_memory(
            app_name="fleet", user_id="platform-team", query="account"
        )
        memory.metadata = {
            "custody_record_id": {"string_value": "ROOT-OTHER"},
            "custody_envelope_version": {"string_value": "b7/p2-v1"},
        }
        changed = await bank.search_authority_memory(
            app_name="fleet", user_id="platform-team", query="account"
        )

        self.assertEqual(missing, ())
        self.assertEqual(changed, ())

    async def test_payload_change_and_conflicting_409_are_not_idempotent(self):
        event, store = _authority_environment()
        client = _RecordingMemoriesClient()
        bank = AgentEngineMemoryBank(client, "engines/1", store)
        text = event.canonical_source_bytes.decode("utf-8")
        await bank.write_authority_record(
            app_name="fleet",
            user_id="platform-team",
            record_id="ROOT-01",
            text=text,
        )
        memory = next(iter(client.memories.values()))
        memory.fact = "different"

        self.assertEqual(
            await bank.search_authority_memory(
                app_name="fleet", user_id="platform-team", query="account"
            ),
            (),
        )
        with self.assertRaises(AuthorityConflict):
            await bank.write_authority_record(
                app_name="fleet",
                user_id="platform-team",
                record_id="ROOT-01",
                text=text,
            )


if __name__ == "__main__":
    unittest.main()
