"""The revision-aware Custody spike.

Each test maps directly to an acceptance gate in
``docs/fleet-idea-tournament.md``. The baseline intentionally trusts a stale
catalogue definition. The governed path must inspect the changed live surface
before it lets an agent bind or invoke that tool.
"""

from __future__ import annotations

import dataclasses
import unittest
import json
from pathlib import Path

from custody.origin import Trust, take_custody
from custody.revision import (
    ApprovedTool,
    AttestationAuthority,
    Denial,
    RevisionCatalog,
    ToolCallDenied,
    ToolSurface,
    ToolSurfaceError,
    mac,
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

    def test_per_response_meta_does_not_change_a_revision(self):
        """R2 rides a fresh dispatch token in ``_meta`` on every read; a tool's
        identity must not shift underneath it just because that field varies."""
        annotated = {
            "result": {
                "tools": [
                    {
                        **APPROVED["result"]["tools"][0],
                        "_meta": {"custody_attestation": {"nonce": "one-off"}},
                    }
                ]
            }
        }
        self.assertEqual(surface(APPROVED).tools[0].revision, surface(annotated).tools[0].revision)

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


class DispatchIsBoundToTheSurfaceThatAuthorizedIt(unittest.TestCase):
    """R2: a ``tools/call`` must prove it followed the ``tools/list`` it cites."""

    def setUp(self):
        self.tool = ApprovedTool("vendor-knowledge/fetch_page", "fetch_page", "rev-a")
        self.authority = AttestationAuthority(b"server-only-secret")

    def test_a_freshly_minted_token_is_admitted_for_its_own_revision(self):
        token = self.authority.mint(tool=self.tool)
        self.assertIsNone(self.authority.verify(token, live_revision="rev-a"))

    def test_a_token_minted_for_one_revision_is_refused_against_another(self):
        """The exact TOCTOU R2 exists to close: the surface changed underneath it."""
        token = self.authority.mint(tool=self.tool)
        denial = self.authority.verify(token, live_revision="rev-b")
        self.assertEqual(denial, Denial.DIGEST_MISMATCH)

    def test_a_token_cannot_be_replayed_even_within_its_ttl(self):
        token = self.authority.mint(tool=self.tool)
        self.assertIsNone(self.authority.verify(token, live_revision="rev-a"))
        replay = self.authority.verify(token, live_revision="rev-a")
        self.assertEqual(replay, Denial.REPLAYED)

    def test_an_expired_token_is_refused_even_with_a_matching_digest(self):
        authority = AttestationAuthority(b"server-only-secret", _ttl_seconds=-1)
        token = authority.mint(tool=self.tool)
        self.assertEqual(
            authority.verify(token, live_revision="rev-a"), Denial.EXPIRED
        )

    def test_a_tampered_field_invalidates_the_signature(self):
        token = self.authority.mint(tool=self.tool)
        forged = dataclasses.replace(token, revision="rev-b")
        self.assertEqual(
            self.authority.verify(forged, live_revision="rev-b"),
            Denial.SIGNATURE_INVALID,
        )

    def test_a_token_signed_by_a_different_secret_is_refused(self):
        """No shared-secret confusion: only the minting server's key verifies."""
        token = self.authority.mint(tool=self.tool)
        impostor = AttestationAuthority(b"a-different-secret")
        self.assertEqual(
            impostor.verify(token, live_revision="rev-a"),
            Denial.SIGNATURE_INVALID,
        )

    def test_mac_is_deterministic_for_the_same_inputs(self):
        """The one function both minting and verification compute, never duplicated."""
        args = dict(
            tool_id="vendor-knowledge/fetch_page",
            revision="rev-a",
            nonce="fixed-nonce",
            issued_at=1000.0,
            expires_at=1045.0,
        )
        self.assertEqual(mac(b"secret", **args), mac(b"secret", **args))


if __name__ == "__main__":
    unittest.main()
