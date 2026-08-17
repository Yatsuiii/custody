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
    Admission,
    ApprovedTool,
    AttestationAuthority,
    Denial,
    InMemoryNonceLedger,
    RevisionCatalog,
    RuntimeBinding,
    ToolCallDenied,
    ToolDefinition,
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


class AMalformedLiveSurfaceFailsClosed(unittest.TestCase):
    """Gate 3: the revision check itself erroring must not be mistaken for
    "nothing changed". A live ``tools/list`` read that comes back
    malformed -- truncated, the wrong shape, a tool missing its name -- is
    exactly what a compromised or broken MCP server can produce, and it
    must refuse to become a ``ToolSurface`` at all rather than silently
    parse into an empty one that then gets treated as "no tools to admit,
    proceed".
    """

    def test_a_non_object_result_is_refused(self):
        with self.assertRaises(ToolSurfaceError):
            surface({"result": "not an object"})

    def test_a_missing_tools_key_is_refused(self):
        with self.assertRaises(ToolSurfaceError):
            surface({"result": {}})

    def test_a_non_list_tools_value_is_refused(self):
        with self.assertRaises(ToolSurfaceError):
            surface({"result": {"tools": "fetch_page"}})

    def test_a_tool_entry_that_is_not_an_object_is_refused(self):
        with self.assertRaises(ToolSurfaceError):
            surface({"result": {"tools": ["fetch_page"]}})

    def test_a_tool_entry_missing_a_name_is_refused(self):
        payload = {
            "result": {"tools": [{"description": "no name field at all"}]}
        }
        with self.assertRaises(ToolSurfaceError):
            surface(payload)

    def test_a_parse_failure_never_produces_a_surface_to_admit_against(self):
        """A caller that cannot build a ``ToolSurface`` from a malformed
        live read has nothing to pass to ``RevisionCatalog.admit`` at all;
        the empty ``Admission`` that results from never calling it denies
        every tool by construction (`Admission.allows` on an empty tuple),
        the same default-deny an unknown department already gets in
        `FirestoreRevisionCatalogTests.test_no_pins_for_a_department_
        denies_as_missing_not_a_crash`."""
        with self.assertRaises(ToolSurfaceError):
            surface({"result": {"tools": "not a list"}})

        with self.assertRaises(ToolCallDenied):
            Admission().require("fetch_page")


class TheDigestAlgorithmIsPinned(unittest.TestCase):
    """A digest is a stored fact, so its algorithm is a wire contract.

    Changing canonicalization silently redefines every revision already
    written to the graph, to Firestore, to Agent Registry, and to every
    captured artifact. This test exists so that change cannot be made
    accidentally: it must be made together with a version bump. The
    fixture is inline, not read from ``proof-out/``, which is gitignored
    and would let this test silently skip on a fresh clone.
    """

    def test_a_known_definition_digests_to_a_known_value(self):
        definition = {
            "name": "fetch_page",
            "description": "Fetch a supplier knowledge page.",
            "inputSchema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        }
        tool = ToolDefinition("vendor-knowledge", "fetch_page", definition)
        self.assertEqual(
            tool.revision,
            "sha256/2:e4f57e5b8647a7faa6d5c7c114ca9e1e0ae3b6fe17e384253398c17dd150bcfa",
            "the digest algorithm changed underneath a stored fact; bump "
            "the version and update every stored revision's consumer, "
            "do not just update this expected value",
        )


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

    def test_an_algorithm_boundary_denies_under_its_own_reason_not_revision_mismatch(self):
        """A tooling change on Custody's own side must never read like a
        security event: an operator hunting REVISION_MISMATCH here would be
        chasing a compromise that never happened."""
        catalog = RevisionCatalog()
        approved_tool = surface(APPROVED).tools[0]
        catalog.approve(department="sales", surface=surface(APPROVED))
        # Simulate a pin approved before the digest was versioned: bare hex,
        # no algorithm prefix, same tool_id.
        catalog._approved[("sales", approved_tool.tool_id)] = ApprovedTool(
            approved_tool.tool_id, approved_tool.runtime_name, "bare-legacy-hex"
        )

        admission = catalog.admit(department="sales", surface=surface(APPROVED))

        self.assertEqual(len(admission.denied), 1)
        self.assertEqual(admission.denied[0].reason, Denial.ALGORITHM_SUPERSEDED)
        self.assertNotEqual(admission.denied[0].reason, Denial.REVISION_MISMATCH)

    def test_a_same_schema_different_image_swap_denies_under_runtime_drift(self):
        """The gap R1's declared-surface check cannot see by itself: an
        identical tools/list schema, backed by different running code."""
        catalog = RevisionCatalog()
        catalog.approve(
            department="sales",
            surface=surface(APPROVED),
            runtime_binding=RuntimeBinding("rev-a", "sha256:aaa"),
        )

        admission = catalog.admit(
            department="sales",
            surface=surface(APPROVED),
            observed_runtime=RuntimeBinding("rev-b", "sha256:bbb"),
        )

        self.assertEqual(len(admission.denied), 1)
        self.assertEqual(admission.denied[0].reason, Denial.RUNTIME_DRIFT)
        self.assertNotEqual(admission.denied[0].reason, Denial.REVISION_MISMATCH)

    def test_a_matching_runtime_binding_admits_normally(self):
        catalog = RevisionCatalog()
        binding = RuntimeBinding("rev-a", "sha256:aaa")
        catalog.approve(
            department="sales", surface=surface(APPROVED), runtime_binding=binding
        )

        admission = catalog.admit(
            department="sales", surface=surface(APPROVED), observed_runtime=binding
        )

        self.assertTrue(admission.allows("fetch_page"))
        self.assertEqual(admission.denied, ())

    def test_no_runtime_binding_on_the_approval_skips_the_check_entirely(self):
        """Opt-in: an approval that never pinned a runtime identity must not
        be silently held to one, or every existing caller breaks."""
        admission = self.catalog.admit(
            department="sales",
            surface=surface(APPROVED),
            observed_runtime=RuntimeBinding("whatever", "sha256:anything"),
        )

        self.assertTrue(admission.allows("fetch_page"))
        self.assertEqual(admission.denied, ())

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

    def test_a_shared_ledger_catches_a_replay_across_two_authority_instances(self):
        """The pluggability point a durable ledger needs: two
        ``AttestationAuthority`` instances (standing in for two Cloud Run
        processes, or one process before and after a restart) sharing one
        ``NonceLedger`` must agree a nonce is spent, even though neither
        holds the other's in-process state."""
        ledger = InMemoryNonceLedger()
        first_process = AttestationAuthority(b"server-only-secret", _ledger=ledger)
        second_process = AttestationAuthority(b"server-only-secret", _ledger=ledger)

        token = first_process.mint(tool=self.tool)
        self.assertIsNone(first_process.verify(token, live_revision="rev-a"))

        replay = second_process.verify(token, live_revision="rev-a")

        self.assertEqual(replay, Denial.REPLAYED)

    def test_two_unshared_ledgers_do_not_see_each_others_consumption(self):
        """The negative control: without a shared ledger, a second process
        has no way to know the nonce was already spent. This is the exact
        gap a process-local ``InMemoryNonceLedger`` cannot close by itself
        — proving the durability property has to come from the ledger
        implementation, not from ``AttestationAuthority`` itself."""
        first_process = AttestationAuthority(b"server-only-secret")
        second_process = AttestationAuthority(b"server-only-secret")

        token = first_process.mint(tool=self.tool)
        self.assertIsNone(first_process.verify(token, live_revision="rev-a"))

        replayed_on_a_fresh_process = second_process.verify(token, live_revision="rev-a")

        self.assertIsNone(replayed_on_a_fresh_process)

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
