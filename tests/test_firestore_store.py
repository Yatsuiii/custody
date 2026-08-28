"""Offline tests for the Firestore-backed durable custody graph (G5).

Uses a fake client implementing the narrow surface `FirestoreCustodyGraph`
calls, so this suite stays pure and networkless like the rest of `make check`.
The fake's `create_time` progresses monotonically per write, which is enough
to test replay ordering without a real Firestore instance.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from google.api_core.exceptions import AlreadyExists, DeadlineExceeded, ServiceUnavailable

from custody.catalog import Demotion
from custody.firestore_store import (
    FirestoreAuditorLog,
    FirestoreCustodyGraph,
    FirestoreDemotionLog,
    FirestoreRevisionCatalog,
)
from custody.origin import CustodyRecord, Origin, Trust
from custody.revision import Denial, RuntimeBinding, ToolSurface

_EPOCH = datetime(2026, 8, 13, tzinfo=UTC)


def _deep_merge(base: dict, incoming: dict) -> dict:
    merged = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class _FakeSnapshot:
    def __init__(self, data: dict | None, create_time: datetime | None) -> None:
        self._data = data
        self.create_time = create_time
        self.exists = data is not None

    def to_dict(self) -> dict:
        return dict(self._data or {})


class _FakeDocument:
    def __init__(self, collection: "_FakeCollection", doc_id: str) -> None:
        self._collection = collection
        self.id = doc_id

    def create(self, data: dict) -> None:
        if self.id in self._collection.docs:
            raise AlreadyExists(f"{self.id} already exists")
        self._collection.docs[self.id] = (
            dict(data),
            self._collection.client.tick(),
        )

    def set(self, data: dict, merge: bool = False) -> None:
        """Enough of real Firestore's ``set`` for ``FirestoreRevisionCatalog``:
        a plain overwrite, or a merge that recursively merges nested maps
        rather than replacing them, matching the real service's documented
        merge behavior for map fields."""
        existing = self._collection.docs.get(self.id)
        if not merge or existing is None:
            self._collection.docs[self.id] = (dict(data), self._collection.client.tick())
            return
        merged = _deep_merge(dict(existing[0]), data)
        self._collection.docs[self.id] = (merged, self._collection.client.tick())

    def get(self) -> _FakeSnapshot:
        entry = self._collection.docs.get(self.id)
        if entry is None:
            return _FakeSnapshot(None, None)
        data, create_time = entry
        return _FakeSnapshot(data, create_time)


class _FakeCollection:
    def __init__(self, client: "FakeFirestoreClient") -> None:
        self.docs: dict[str, tuple[dict, datetime]] = {}
        self.client = client

    def document(self, doc_id: str) -> _FakeDocument:
        return _FakeDocument(self, doc_id)

    def stream(self):
        for data, create_time in list(self.docs.values()):
            yield _FakeSnapshot(data, create_time)

    def limit(self, count: int) -> "_FakeCollection":
        limited = _FakeCollection(self.client)
        limited.docs = dict(list(self.docs.items())[:count])
        return limited


class FakeFirestoreClient:
    """Backing store that survives across `FirestoreCustodyGraph` instances.

    Mirrors the point of the real thing: construct a second graph against the
    same client and it must replay to the same state, the way a Cloud Run
    cold start replays against the same real Firestore database. One shared
    clock across collections, because real Firestore server timestamps are
    globally ordered, not per-collection.
    """

    def __init__(self) -> None:
        self._collections: dict[str, _FakeCollection] = {}
        self._clock = _EPOCH

    def tick(self) -> datetime:
        self._clock += timedelta(milliseconds=1)
        return self._clock

    def collection(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection(self))


def _record(*, id: str, source_tool: str = "crm_lookup", derived_from=()) -> CustodyRecord:
    return CustodyRecord(
        origin=Origin.TOOL,
        trust=Trust.TRUSTED,
        author="crm_lookup",
        invocation_id="inv-1",
        content_sha256=f"sha-{id}",
        source_tool=source_tool,
        id=id,
        derived_from=derived_from,
    )


class FirestoreCustodyGraphTests(unittest.TestCase):
    def test_add_stamps_server_admitted_at(self) -> None:
        client = FakeFirestoreClient()
        graph = FirestoreCustodyGraph(client)

        graph.add(_record(id="r1"))

        (stored,) = graph.records()
        self.assertIsNotNone(stored.admitted_at)
        self.assertEqual(stored.admitted_at, client.collection("custody").document("r1").get().create_time.isoformat())

    def test_duplicate_add_is_a_no_op_not_an_error(self) -> None:
        client = FakeFirestoreClient()
        graph = FirestoreCustodyGraph(client)
        graph.add(_record(id="r1"))
        first_admitted_at = graph.records()[0].admitted_at

        graph.add(_record(id="r1"))

        self.assertEqual(len(graph), 1)
        self.assertEqual(graph.records()[0].admitted_at, first_admitted_at)

    def test_cold_start_replays_records_and_revocations(self) -> None:
        client = FakeFirestoreClient()
        first = FirestoreCustodyGraph(client)
        first.add(_record(id="r1"))
        first.add(_record(id="r2", derived_from=("r1",)))
        first.revoke(tool="crm_lookup", revocation_id="rev-1")

        second = FirestoreCustodyGraph(client)

        self.assertEqual(len(second), 0)
        self.assertEqual(len(second.revocations()), 1)
        self.assertEqual(second.revocations()[0].removed, ("r1", "r2"))

    def test_revoke_is_idempotent_across_processes(self) -> None:
        client = FakeFirestoreClient()
        first = FirestoreCustodyGraph(client)
        first.add(_record(id="r1"))
        applied = first.revoke(tool="crm_lookup", revocation_id="rev-1")

        second = FirestoreCustodyGraph(client)
        replayed = second.revoke(tool="crm_lookup", revocation_id="rev-1")

        self.assertEqual(applied.removed, replayed.removed)
        self.assertEqual(len(client.collection("revocations").docs), 1)

    def test_record_returns_a_revoked_record_with_its_revocation(self) -> None:
        client = FakeFirestoreClient()
        graph = FirestoreCustodyGraph(client)
        graph.add(_record(id="r1"))
        graph.revoke(tool="crm_lookup", revocation_id="rev-1")

        found = graph.record("r1")

        self.assertIsNotNone(found)
        record, revocation = found
        self.assertEqual(record.id, "r1")
        self.assertIsNotNone(revocation)
        self.assertEqual(revocation.id, "rev-1")
        self.assertIsNotNone(revocation.revoked_at)
        self.assertLess(record.admitted_at, revocation.revoked_at)

    def test_record_of_a_live_record_has_no_revocation(self) -> None:
        client = FakeFirestoreClient()
        graph = FirestoreCustodyGraph(client)
        graph.add(_record(id="r1"))

        found = graph.record("r1")

        self.assertIsNotNone(found)
        _, revocation = found
        self.assertIsNone(revocation)

    def test_unknown_record_id_returns_none(self) -> None:
        client = FakeFirestoreClient()
        graph = FirestoreCustodyGraph(client)

        self.assertIsNone(graph.record("does-not-exist"))

    def test_replay_order_follows_server_creation_time_not_insertion_order(self) -> None:
        client = FakeFirestoreClient()
        collection = client.collection("custody")
        # Insert out of causal order to prove replay sorts by create_time,
        # not by whatever order stream() happens to enumerate documents in.
        collection.docs["r2"] = (
            {
                "origin": "tool",
                "trust": "trusted",
                "author": "crm_lookup",
                "invocation_id": "inv-1",
                "content_sha256": "sha-r2",
                "source_tool": "crm_lookup",
                "source_revision": None,
                "id": "r2",
                "derived_from": [],
            },
            _EPOCH + timedelta(seconds=2),
        )
        collection.docs["r1"] = (
            {
                "origin": "tool",
                "trust": "trusted",
                "author": "crm_lookup",
                "invocation_id": "inv-1",
                "content_sha256": "sha-r1",
                "source_tool": "crm_lookup",
                "source_revision": None,
                "id": "r1",
                "derived_from": [],
            },
            _EPOCH + timedelta(seconds=1),
        )

        graph = FirestoreCustodyGraph(client)

        admitted = {record.id: record.admitted_at for record in graph.records()}
        self.assertLess(admitted["r1"], admitted["r2"])


class FirestoreAuditorLogTests(unittest.TestCase):
    def test_the_first_heartbeat_ever_is_reported_as_such(self) -> None:
        client = FakeFirestoreClient()
        log = FirestoreAuditorLog(client)

        self.assertTrue(log.heartbeat("2026-08-13"))

    def test_a_second_day_is_not_the_first_run(self) -> None:
        client = FakeFirestoreClient()
        log = FirestoreAuditorLog(client)
        log.heartbeat("2026-08-13")

        self.assertFalse(log.heartbeat("2026-08-14"))

    def test_a_retried_call_on_the_same_day_is_a_no_op(self) -> None:
        client = FakeFirestoreClient()
        log = FirestoreAuditorLog(client)
        log.heartbeat("2026-08-13")

        log.heartbeat("2026-08-13")

        self.assertEqual(len(client.collection("auditor").docs), 1)

    def test_reload_against_the_same_client_sees_prior_heartbeats(self) -> None:
        client = FakeFirestoreClient()
        FirestoreAuditorLog(client).heartbeat("2026-08-13")

        second = FirestoreAuditorLog(client)

        self.assertFalse(second.heartbeat("2026-08-14"))


def _demotion(*, department: str = "sales", tool: str = "crm_lookup") -> Demotion:
    return Demotion(
        actor_department=department,
        department=department,
        tool=tool,
        demoted_by=f"{department}-admin",
        demoted_at="2026-08-14T00:00:00Z",
    )


class FirestoreDemotionLogTests(unittest.TestCase):
    def test_a_recorded_demotion_is_returned_by_all(self) -> None:
        client = FakeFirestoreClient()
        log = FirestoreDemotionLog(client)

        log.record(_demotion())

        self.assertEqual(len(log.all()), 1)
        self.assertEqual(log.all()[0].tool, "crm_lookup")

    def test_a_retried_record_is_a_no_op_not_a_duplicate(self) -> None:
        client = FakeFirestoreClient()
        log = FirestoreDemotionLog(client)

        log.record(_demotion())
        log.record(_demotion())

        self.assertEqual(len(client.collection("demotions").docs), 1)
        self.assertEqual(len(log.all()), 1)

    def test_a_cold_start_replays_prior_demotions(self) -> None:
        client = FakeFirestoreClient()
        FirestoreDemotionLog(client).record(_demotion())

        second = FirestoreDemotionLog(client)

        self.assertEqual(len(second.all()), 1)
        self.assertEqual(second.all()[0].tool, "crm_lookup")


def _surface(tool_id: str = "crm_lookup", schema: str = "a") -> ToolSurface:
    payload = {
        "result": {
            "tools": [
                {
                    "name": tool_id,
                    "description": schema,
                    "inputSchema": {"type": "object"},
                }
            ]
        }
    }
    return ToolSurface.from_tools_list(server="crm", payload=payload)


class FirestoreRevisionCatalogTests(unittest.TestCase):
    """Durability proven the same way FirestoreCustodyGraph's own docstring
    proves it: construct a second instance against the same fake client and
    confirm it sees what the first wrote, with no shared in-memory state."""

    def test_a_pin_approved_through_one_instance_is_seen_by_a_second(self) -> None:
        client = FakeFirestoreClient()
        first = FirestoreRevisionCatalog(client)
        first.approve(department="sales", surface=_surface())

        second = FirestoreRevisionCatalog(client)
        admission = second.admit(department="sales", surface=_surface())

        self.assertTrue(admission.allows("crm_lookup"))
        self.assertEqual(admission.denied, ())

    def test_a_changed_live_surface_still_denies_through_the_durable_backend(self) -> None:
        client = FakeFirestoreClient()
        FirestoreRevisionCatalog(client).approve(department="sales", surface=_surface())

        admission = FirestoreRevisionCatalog(client).admit(
            department="sales", surface=_surface(schema="changed")
        )

        self.assertFalse(admission.allows("crm_lookup"))
        self.assertEqual(admission.denied[0].reason, Denial.REVISION_MISMATCH)

    def test_approving_one_tool_does_not_clobber_a_sibling_tools_pin(self) -> None:
        """The merge semantics that matter: two approve() calls for the same
        department, different tools, must not overwrite each other."""
        client = FakeFirestoreClient()
        catalog = FirestoreRevisionCatalog(client)
        catalog.approve(department="sales", surface=_surface(tool_id="crm_lookup"))
        catalog.approve(department="sales", surface=_surface(tool_id="billing_lookup"))

        admission = catalog.admit(
            department="sales", surface=_surface(tool_id="crm_lookup")
        )
        self.assertTrue(admission.allows("crm_lookup"))

        billing_admission = FirestoreRevisionCatalog(client).admit(
            department="sales", surface=_surface(tool_id="billing_lookup")
        )
        self.assertTrue(billing_admission.allows("billing_lookup"))

    def test_a_runtime_binding_survives_the_round_trip(self) -> None:
        client = FakeFirestoreClient()
        binding = RuntimeBinding("rev-a", "sha256:aaa")
        FirestoreRevisionCatalog(client).approve(
            department="sales", surface=_surface(), runtime_binding=binding
        )

        matching = FirestoreRevisionCatalog(client).admit(
            department="sales", surface=_surface(), observed_runtime=binding
        )
        self.assertTrue(matching.allows("crm_lookup"))

        drifted = FirestoreRevisionCatalog(client).admit(
            department="sales",
            surface=_surface(),
            observed_runtime=RuntimeBinding("rev-b", "sha256:bbb"),
        )
        self.assertEqual(drifted.denied[0].reason, Denial.RUNTIME_DRIFT)

    def test_no_pins_for_a_department_denies_as_missing_not_a_crash(self) -> None:
        client = FakeFirestoreClient()
        catalog = FirestoreRevisionCatalog(client)

        admission = catalog.admit(department="unknown", surface=_surface())

        self.assertEqual(admission.allowed, ())
        self.assertEqual(admission.denied, ())

    def test_different_tools_are_kept_as_distinct_demotions(self) -> None:
        client = FakeFirestoreClient()
        log = FirestoreDemotionLog(client)

        log.record(_demotion(tool="crm_lookup"))
        log.record(_demotion(tool="other_tool"))

        self.assertEqual(
            {d.tool for d in log.all()}, {"crm_lookup", "other_tool"}
        )


class _OutageDocument:
    """A document read that always raises, modeling an unreachable Firestore
    backend (Agent Registry's durable pin store)."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def get(self):
        raise self._error


class _OutageCollection:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def document(self, doc_id: str) -> _OutageDocument:
        return _OutageDocument(self._error)


class _OutageFirestoreClient:
    """Every Registry pin read times out or errors; nothing about this
    client ever returns a snapshot a caller could mistake for "no pins"."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def collection(self, name: str) -> _OutageCollection:
        return _OutageCollection(self._error)


class FirestoreRevisionCatalogFailsClosedOnAnUnreachableRegistry(unittest.TestCase):
    """Gate 2: Agent Registry unreachable must block dispatch, not default
    to trust. `FirestoreRevisionCatalog.admit` is the one place a live pin
    read happens; if it silently degraded to "no pins" on a network error,
    that would be indistinguishable from `test_no_pins_for_a_department_
    denies_as_missing_not_a_crash` above -- correct for an unknown
    department, wrong for a known one whose approval simply could not be
    read this instant.
    """

    def test_a_timeout_reading_pins_propagates_rather_than_admitting(self) -> None:
        client = _OutageFirestoreClient(DeadlineExceeded("agent registry timed out"))
        catalog = FirestoreRevisionCatalog(client)

        with self.assertRaises(DeadlineExceeded):
            catalog.admit(department="sales", surface=_surface())

    def test_a_service_unavailable_error_also_propagates(self) -> None:
        client = _OutageFirestoreClient(ServiceUnavailable("agent registry unreachable"))
        catalog = FirestoreRevisionCatalog(client)

        with self.assertRaises(ServiceUnavailable):
            catalog.admit(department="sales", surface=_surface())


if __name__ == "__main__":
    unittest.main()
