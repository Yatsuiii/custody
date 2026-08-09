"""The durable quarantine has one job the in-memory one cannot: survive a
process restart. Every test here opens a fresh `SqliteQuarantine` against a
temp file rather than reusing one connection, to prove durability rather than
assume it.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from custody.origin import CustodyRecord, Origin, ToolTrust, Trust
from custody.service import CustodyMemoryService, Quarantined
from custody.store import SqliteQuarantine
from tests.test_origin import FakeContent, FakeEvent, FakePart, FakeResponse


def item(
    *,
    app_name: str = "fleet",
    user_id: str = "platform-team",
    session_id: str = "week-1",
    text: str = "hostile content",
    content_sha256: str = "a" * 64,
    record_id: str = "inv-1:0:0",
    derived_from: tuple[str, ...] = (),
) -> Quarantined:
    return Quarantined(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
        text=text,
        record=CustodyRecord(
            origin=Origin.TOOL,
            trust=Trust.UNTRUSTED,
            author="assistant",
            invocation_id="inv-1",
            content_sha256=content_sha256,
            source_tool="fetch_page",
            id=record_id,
            derived_from=derived_from,
        ),
    )


class QuarantineSurvivesARestart(unittest.TestCase):
    def test_an_item_held_before_a_restart_is_held_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quarantine.db"

            first = SqliteQuarantine(path)
            first.hold(item())
            first.close()

            second = SqliteQuarantine(path)
            held = second.held(app_name="fleet", user_id="platform-team")
            second.close()

        self.assertEqual(len(held), 1)
        self.assertEqual(held[0].text, "hostile content")

    def test_the_custody_record_round_trips_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quarantine.db"
            store = SqliteQuarantine(path)
            store.hold(item(record_id="inv-1:0:0", derived_from=("inv-0:0:0",)))
            (held,) = store.held(app_name="fleet", user_id="platform-team")
            store.close()

        record = held.record
        self.assertIs(record.origin, Origin.TOOL)
        self.assertIs(record.trust, Trust.UNTRUSTED)
        self.assertEqual(record.source_tool, "fetch_page")
        self.assertEqual(record.id, "inv-1:0:0")
        self.assertEqual(record.derived_from, ("inv-0:0:0",))


class WritesAreIdempotent(unittest.TestCase):
    def test_holding_the_same_item_twice_is_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteQuarantine(Path(tmp) / "quarantine.db")
            duplicate = item()
            store.hold(duplicate)
            store.hold(duplicate)
            held = store.held(app_name="fleet", user_id="platform-team")
            store.close()

        self.assertEqual(len(held), 1)

    def test_a_replayed_session_after_a_crash_does_not_double_quarantine(self):
        """The scenario the idempotency key exists for: the same content,
        quarantined again because the caller does not know it already was."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quarantine.db"
            crashed = SqliteQuarantine(path)
            crashed.hold(item(session_id="week-1", content_sha256="b" * 64))
            crashed.close()

            replayed = SqliteQuarantine(path)
            replayed.hold(item(session_id="week-1", content_sha256="b" * 64))
            held = replayed.held(app_name="fleet", user_id="platform-team")
            replayed.close()

        self.assertEqual(len(held), 1)

    def test_different_content_in_the_same_session_is_two_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteQuarantine(Path(tmp) / "quarantine.db")
            store.hold(item(session_id="week-1", content_sha256="a" * 64))
            store.hold(item(session_id="week-1", content_sha256="b" * 64))
            held = store.held(app_name="fleet", user_id="platform-team")
            store.close()

        self.assertEqual(len(held), 2)


class QuarantineIsScoped(unittest.TestCase):
    def test_items_from_a_different_user_are_not_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteQuarantine(Path(tmp) / "quarantine.db")
            store.hold(item(user_id="platform-team"))
            store.hold(item(user_id="sales-team", content_sha256="c" * 64))
            held = store.held(app_name="fleet", user_id="platform-team")
            store.close()

        self.assertEqual(len(held), 1)
        self.assertEqual(held[0].user_id, "platform-team")

    def test_items_from_a_different_app_are_not_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteQuarantine(Path(tmp) / "quarantine.db")
            store.hold(item(app_name="fleet"))
            store.hold(item(app_name="other-app", content_sha256="c" * 64))
            held = store.held(app_name="fleet", user_id="platform-team")
            store.close()

        self.assertEqual(len(held), 1)


@dataclass
class FakeSession:
    id: str = "s-1"
    app_name: str = "fleet"
    user_id: str = "u-1"
    events: list = field(default_factory=list)


@dataclass
class RecordingMemory:
    written: list = field(default_factory=list)

    async def add_session_to_memory(self, session) -> None:
        self.written.extend(session.events)

    async def search_memory(self, *, app_name, user_id, query):
        del app_name, user_id, query
        return list(self.written)


class ItSatisfiesTheQuarantineStorePortInPractice(unittest.IsolatedAsyncioTestCase):
    """Not just structural compatibility: run it through the real enforcement
    point and read the quarantine back from a fresh connection, the way the
    Custody Reviewer would after a restart."""

    async def test_the_governed_service_writes_through_to_the_durable_store(self):
        session = FakeSession(
            events=[
                FakeEvent(
                    "assistant",
                    "inv-1",
                    FakeContent(
                        [FakePart(function_response=FakeResponse("fetch_page", "hostile"))]
                    ),
                ),
                FakeEvent("assistant", "inv-1", FakeContent([FakePart(text="summary")])),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quarantine.db"
            quarantine = SqliteQuarantine(path)
            service = CustodyMemoryService(RecordingMemory(), quarantine, ToolTrust())
            await service.add_session_to_memory(session)
            quarantine.close()

            reopened = SqliteQuarantine(path)
            held = reopened.held(app_name="fleet", user_id="u-1")
            reopened.close()

        self.assertEqual(len(held), 2)
        self.assertEqual(
            {h.record.origin for h in held}, {Origin.TOOL, Origin.DERIVED}
        )


if __name__ == "__main__":
    unittest.main()
