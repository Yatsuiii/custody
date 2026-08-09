"""G4: department A cannot raise trust for department B's tools, and content
quarantined in A never surfaces in B's retrieval.

`test_catalog.py` proves the catalog refuses a cross-department vouch on its
own. This file proves the refusal actually holds at the enforcement point: a
real `CustodyMemoryService` per department, sharing one catalog, and one
adversarial attempt from each side.
"""

from __future__ import annotations

import unittest

from custody.catalog import Grant, TrustCatalog, Vouch
from custody.origin import Origin
from custody.service import CustodyMemoryService, InMemoryQuarantine
from tests.test_service import FakeSession, RecordingMemory, tool

COMPROMISED_TOOL = "backdoor_tool"


def grant(department: str, tool_name: str) -> Grant:
    return Grant(
        department=department,
        tool=tool_name,
        vouched_by=f"{department}-admin",
        vouched_at="2026-08-10T00:00:00Z",
    )


class ATrustedToolInOneDepartmentStaysUntrustedInAnother(
    unittest.IsolatedAsyncioTestCase
):
    async def test_sales_trusting_a_tool_does_not_trust_it_for_support(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("sales", grant("sales", "crm_lookup")))

        sales = CustodyMemoryService(
            RecordingMemory(), InMemoryQuarantine(), catalog=catalog, department="sales"
        )
        support = CustodyMemoryService(
            RecordingMemory(),
            InMemoryQuarantine(),
            catalog=catalog,
            department="support",
        )

        sales_split = await sales.add_session_to_memory(
            FakeSession(id="s-1", user_id="sales", events=[tool("crm_lookup", "500")])
        )
        support_split = await support.add_session_to_memory(
            FakeSession(id="s-2", user_id="support", events=[tool("crm_lookup", "500")])
        )

        self.assertEqual(sales_split.withheld, 0, "sales vouched for it")
        self.assertEqual(support_split.withheld, 1, "support never did")
        (quarantined,) = support_split.quarantined
        self.assertIs(quarantined.record.origin, Origin.TOOL)

    async def test_a_grant_recorded_after_a_service_is_built_still_applies(self):
        """The catalog is consulted fresh on every write, not snapshotted at
        construction, because trust changes over the life of a deployment."""
        catalog = TrustCatalog()
        service = CustodyMemoryService(
            RecordingMemory(), InMemoryQuarantine(), catalog=catalog, department="sales"
        )

        before = await service.add_session_to_memory(
            FakeSession(id="s-1", events=[tool("crm_lookup", "500")])
        )
        self.assertEqual(before.withheld, 1)

        catalog.request(Vouch("sales", grant("sales", "crm_lookup")))

        after = await service.add_session_to_memory(
            FakeSession(id="s-2", events=[tool("crm_lookup", "600")])
        )
        self.assertEqual(after.withheld, 0)


class TwoAdversarialVouchesAreBothRefusedAndAudited(unittest.TestCase):
    """The G4 proof shape named in the contract, run against two real
    department boundaries at once rather than one attempt in isolation."""

    def test_neither_department_can_write_into_the_others_boundary(self):
        catalog = TrustCatalog()
        first = catalog.request(Vouch("sales", grant("support", COMPROMISED_TOOL)))
        second = catalog.request(Vouch("support", grant("sales", COMPROMISED_TOOL)))

        self.assertFalse(first.allowed)
        self.assertFalse(second.allowed)
        self.assertEqual(len(catalog.denials()), 2)
        self.assertEqual(catalog.trust_for("sales").trusted, frozenset())
        self.assertEqual(catalog.trust_for("support").trusted, frozenset())


class QuarantineNeverCrossesADepartmentBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_content_quarantined_in_sales_is_invisible_to_support(self):
        shared_quarantine = InMemoryQuarantine()
        sales = CustodyMemoryService(RecordingMemory(), shared_quarantine)
        support = CustodyMemoryService(RecordingMemory(), shared_quarantine)

        await sales.add_session_to_memory(
            FakeSession(
                id="s-1",
                app_name="fleet",
                user_id="sales",
                events=[tool("fetch_page", "hostile content")],
            )
        )
        await support.add_session_to_memory(
            FakeSession(
                id="s-2",
                app_name="fleet",
                user_id="support",
                events=[tool("fetch_page", "different hostile content")],
            )
        )

        sales_view = shared_quarantine.held(app_name="fleet", user_id="sales")
        support_view = shared_quarantine.held(app_name="fleet", user_id="support")

        self.assertEqual(len(sales_view), 1)
        self.assertEqual(len(support_view), 1)
        self.assertNotEqual(sales_view[0].text, support_view[0].text)
        self.assertNotIn(sales_view[0], support_view)


if __name__ == "__main__":
    unittest.main()
