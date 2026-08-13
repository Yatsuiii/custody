"""The revision-aware Custody spike.

Each test maps directly to an acceptance gate in
``docs/fleet-idea-tournament.md``. The baseline intentionally trusts a stale
catalogue definition. The governed path must inspect the changed live surface
before it lets an agent bind or invoke that tool.
"""

from __future__ import annotations

import unittest
import json
from pathlib import Path

from custody.origin import Trust, take_custody
from custody.revision import (
    Denial,
    RevisionCatalog,
    ToolCallDenied,
    ToolSurface,
    ToolSurfaceError,
)
from tests.test_origin import FakeContent, FakeEvent, FakePart, FakeResponse


FIXTURES = Path(__file__).parent / "fixtures"
APPROVED = json.loads((FIXTURES / "registry-approved.json").read_text())
CHANGED = json.loads((FIXTURES / "registry-changed-live.json").read_text())


def surface(payload: dict) -> ToolSurface:
    return ToolSurface.from_tools_list(server="vendor-knowledge", payload=payload)


class StaleRegistryMetadataIsReproducible(unittest.TestCase):
    def test_schema_key_order_and_tool_order_do_not_change_a_revision(self):
        reordered = {
            "result": {
                "tools": [
                    {
                        "inputSchema": APPROVED["result"]["tools"][0]["inputSchema"],
                        "name": "fetch_page",
                        "description": "Fetch a supplier knowledge page.",
                    }
                ]
            }
        }
        self.assertEqual(surface(APPROVED).tools[0].revision, surface(reordered).tools[0].revision)

    def test_changed_live_tools_list_has_a_different_revision_than_the_snapshot(self):
        self.assertNotEqual(surface(APPROVED).tools[0].revision, surface(CHANGED).tools[0].revision)

    def test_duplicate_runtime_names_are_refused_as_ambiguous(self):
        payload = {"result": {"tools": [APPROVED["result"]["tools"][0]] * 2}}
        with self.assertRaises(ToolSurfaceError):
            surface(payload)


class RevisionMismatchBlocksBindingBeforeInvocation(unittest.TestCase):
    def setUp(self):
        self.catalog = RevisionCatalog()
        self.catalog.approve(department="sales", surface=surface(APPROVED))

    def test_negative_control_admits_the_changed_tool_when_it_trusts_stale_registry_metadata(self):
        """The baseline never inspects the runtime surface, so it binds it."""
        stale_catalogue_tools = {tool.runtime_name for tool in surface(APPROVED).tools}
        self.assertIn("fetch_page", stale_catalogue_tools)

    def test_governed_path_refuses_changed_tool_before_dispatch(self):
        admission = self.catalog.admit(department="sales", surface=surface(CHANGED))
        invoked: list[str] = []

        with self.assertRaises(ToolCallDenied):
            admission.require("fetch_page")
            invoked.append("fetch_page")

        self.assertEqual(invoked, [])
        self.assertFalse(admission.allows("fetch_page"))
        self.assertEqual(admission.denied[0].reason, Denial.REVISION_MISMATCH)

    def test_admitted_tool_output_is_bound_to_server_qualified_revision(self):
        admission = self.catalog.admit(department="sales", surface=surface(APPROVED))
        event = FakeEvent(
            "assistant",
            "inv-1",
            FakeContent([FakePart(function_response=FakeResponse("fetch_page", "safe"))]),
        )

        (admitted,) = take_custody([event], admission.trust()).admitted

        self.assertIs(admitted.record.trust, Trust.TRUSTED)
        self.assertEqual(admitted.record.source_tool, "vendor-knowledge/fetch_page")
        self.assertEqual(admitted.record.source_revision, surface(APPROVED).tools[0].revision)


if __name__ == "__main__":
    unittest.main()
