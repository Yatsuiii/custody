"""The durable graph has one job `CustodyGraph` cannot: survive a restart.
Every test opens a fresh `SqliteCustodyGraph` against a temp file rather than
reusing one connection, to prove durability rather than assume it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from custody.origin import ToolTrust, Trust, take_custody
from custody.store import SqliteCustodyGraph
from tests.test_graph import record
from tests.test_origin import FakeContent, FakeEvent, FakePart, FakeResponse


class RecordsSurviveARestart(unittest.TestCase):
    def test_a_record_added_before_a_restart_is_there_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.db"
            first = SqliteCustodyGraph(path)
            first.add(record("a", source_tool="crm_lookup"))
            first.close()

            second = SqliteCustodyGraph(path)
            found = second.resolve(record("a", source_tool="crm_lookup").content_sha256)
            second.close()

        self.assertIsNotNone(found)
        self.assertEqual(found.id, "a")


class RevocationSurvivesARestart(unittest.TestCase):
    def test_a_revoked_record_stays_removed_after_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.db"
            first = SqliteCustodyGraph(path)
            first.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
            first.add(record("b", derived_from=("a",), trust=Trust.UNTRUSTED))
            first.revoke(tool="evil_tool", revocation_id="rev-1")
            first.close()

            reopened = SqliteCustodyGraph(path)
            surviving = {r.id for r in reopened.records()}
            reopened.close()

        self.assertEqual(surviving, set())

    def test_replaying_the_revocation_after_reload_removes_nothing_further(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.db"
            first = SqliteCustodyGraph(path)
            first.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
            first.revoke(tool="evil_tool", revocation_id="rev-1")
            first.close()

            reopened = SqliteCustodyGraph(path)
            replay = reopened.revoke(tool="evil_tool", revocation_id="rev-1")
            revocations = reopened.revocations()
            reopened.close()

        self.assertEqual(replay.removed, ("a",))
        self.assertEqual(len(revocations), 1)

    def test_a_record_added_after_the_revocation_is_unaffected_by_reload(self):
        """The revocation log names a tool and an id, not a frozen record set,
        so replaying it after reload must not touch content added later."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.db"
            first = SqliteCustodyGraph(path)
            first.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
            first.revoke(tool="evil_tool", revocation_id="rev-1")
            first.add(record("clean", source_tool="payroll_lookup"))
            first.close()

            reopened = SqliteCustodyGraph(path)
            surviving = {r.id for r in reopened.records()}
            reopened.close()

        self.assertEqual(surviving, {"clean"})


class ItSatisfiesTheResolverPortInPractice(unittest.TestCase):
    """Not just structural compatibility: run it through `take_custody` as a
    real resolver, the way `CustodyMemoryService` would."""

    def test_a_retrieval_resolves_against_the_durable_graph(self):
        trust = ToolTrust(trusted=frozenset({"crm_lookup"}))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.db"
            graph = SqliteCustodyGraph(path)

            written = take_custody(
                [_tool_event("crm_lookup", "balance: 500", "inv-1")], trust
            )
            (original,) = written.admitted
            graph.add(original.record)
            graph.close()

            reopened = SqliteCustodyGraph(path)
            resolved = take_custody(
                [_tool_event("load_memory", "balance: 500", "inv-2")],
                resolver=reopened,
            )
            reopened.close()

        (admitted,) = resolved.admitted
        self.assertIs(admitted.record.trust, Trust.TRUSTED)
        self.assertEqual(admitted.record.derived_from, (original.record.id,))


def _tool_event(name: str, text: str, invocation: str):
    part = FakePart(function_response=FakeResponse(name=name, response=text))
    return FakeEvent("assistant", invocation, FakeContent([part]))


if __name__ == "__main__":
    unittest.main()
