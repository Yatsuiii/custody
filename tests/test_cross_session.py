"""G3, through the real enforcement point rather than a hand-built graph.

`test_graph.py` proves the traversal is correct once records carry the right
edges. This file proves the edges get there: two departments, two
`CustodyMemoryService.add_session_to_memory` calls, a real `load_memory`
retrieval bridging them, and a revocation that reaches across both.
"""

from __future__ import annotations

import unittest

from custody.origin import Origin, ToolTrust, Trust
from custody.service import CustodyMemoryService, InMemoryQuarantine
from tests.test_service import FakeSession, RecordingMemory, model, tool, user

COMPROMISED_TOOL = "crm_lookup"


class RetrievalBridgesTwoDepartmentsOnTheSameGraph(unittest.IsolatedAsyncioTestCase):
    async def test_a_second_departments_retrieval_inherits_the_first(self):
        trust = ToolTrust(trusted=frozenset({COMPROMISED_TOOL}))
        service = CustodyMemoryService(RecordingMemory(), InMemoryQuarantine(), trust)

        sales = FakeSession(
            id="sales-1",
            app_name="fleet",
            user_id="sales-team",
            events=[
                user("what does Acme owe?"),
                tool(COMPROMISED_TOOL, "balance: 500", inv="sales-inv-1"),
                model("Acme owes 500.", inv="sales-inv-1"),
            ],
        )
        sales_split = await service.add_session_to_memory(sales)
        self.assertEqual(sales_split.withheld, 0, "nothing quarantined day one")

        support = FakeSession(
            id="support-1",
            app_name="fleet",
            user_id="support-team",
            events=[
                tool("load_memory", "balance: 500", inv="support-inv-1"),
                model("Confirmed: balance is 500.", inv="support-inv-1"),
            ],
        )
        support_split = await service.add_session_to_memory(support)

        # The retrieval was resolved against sales' record, so it was not
        # quarantined even though load_memory itself is unvouched.
        self.assertEqual(support_split.withheld, 0)
        retrieval_record = support_split.trusted[0].record
        self.assertIs(retrieval_record.origin, Origin.TOOL)
        self.assertIs(retrieval_record.trust, Trust.TRUSTED)
        self.assertEqual(len(retrieval_record.derived_from), 1)

    async def test_revoking_the_original_tool_removes_both_departments_records(self):
        trust = ToolTrust(trusted=frozenset({COMPROMISED_TOOL}))
        service = CustodyMemoryService(RecordingMemory(), InMemoryQuarantine(), trust)

        await service.add_session_to_memory(
            FakeSession(
                id="sales-1",
                user_id="sales-team",
                events=[
                    tool(COMPROMISED_TOOL, "balance: 500", inv="sales-inv-1"),
                    model("Acme owes 500.", inv="sales-inv-1"),
                ],
            )
        )
        await service.add_session_to_memory(
            FakeSession(
                id="support-1",
                user_id="support-team",
                events=[
                    tool("load_memory", "balance: 500", inv="support-inv-1"),
                    model("Confirmed: balance is 500.", inv="support-inv-1"),
                ],
            )
        )

        before = len(service.graph)
        self.assertEqual(before, 4)  # 2 records per department

        revocation = service.graph.revoke(
            tool=COMPROMISED_TOOL, revocation_id="rev-1"
        )
        self.assertEqual(len(revocation.removed), 4)
        self.assertEqual(len(service.graph), 0)

        replay = service.graph.revoke(tool=COMPROMISED_TOOL, revocation_id="rev-1")
        self.assertEqual(replay, revocation)
        self.assertEqual(len(service.graph.revocations()), 1)


class AnUnresolvedRetrievalIsQuarantinedNotTrusted(unittest.IsolatedAsyncioTestCase):
    async def test_a_load_memory_call_that_matches_nothing_stays_untrusted(self):
        """No prior write means no citation to inherit, so the default deny
        for an unvouched tool holds. The mechanism upgrades trust only on
        proof, never assumes it."""
        service = CustodyMemoryService(RecordingMemory(), InMemoryQuarantine())
        session = FakeSession(
            events=[tool("load_memory", "content nobody wrote", inv="inv-1")]
        )
        split = await service.add_session_to_memory(session)
        self.assertEqual(split.withheld, 1)
        self.assertEqual(len(split.quarantined), 1)


if __name__ == "__main__":
    unittest.main()
