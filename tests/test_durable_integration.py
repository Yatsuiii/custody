"""The reason durability exists: G3 and G4 both have to hold across a Cloud
Run restart, not just within one process's lifetime. This test simulates a
redeploy between every phase by closing every connection and opening fresh
ones against the same paths, the way a new container would.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from custody.catalog import Vouch
from custody.origin import Origin
from custody.service import CustodyMemoryService
from custody.store import SqliteCustodyGraph, SqliteQuarantine, SqliteTrustCatalog
from tests.test_cross_department import grant
from tests.test_service import FakeSession, RecordingMemory, model, tool, user

COMPROMISED_TOOL = "crm_lookup"


class G3AndG4SurviveARestart(unittest.IsolatedAsyncioTestCase):
    async def test_revocation_and_isolation_both_hold_after_a_simulated_redeploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            graph_path = Path(tmp) / "graph.db"
            catalog_path = Path(tmp) / "catalog.db"
            sales_quarantine_path = Path(tmp) / "sales-quarantine.db"
            support_quarantine_path = Path(tmp) / "support-quarantine.db"

            # -- deploy one: sales vouches for its tool and writes memory --
            catalog = SqliteTrustCatalog(catalog_path)
            catalog.request(Vouch("sales", grant("sales", COMPROMISED_TOOL)))

            graph = SqliteCustodyGraph(graph_path)
            sales = CustodyMemoryService(
                RecordingMemory(),
                SqliteQuarantine(sales_quarantine_path),
                graph=graph,
                catalog=catalog,
                department="sales",
            )
            await sales.add_session_to_memory(
                _session(
                    "sales-1",
                    "sales",
                    [
                        user("what does Acme owe?"),
                        tool(COMPROMISED_TOOL, "500", inv="sales-inv-1"),
                        model("Acme owes 500.", inv="sales-inv-1"),
                    ],
                )
            )
            catalog.close()
            graph.close()
            sales.quarantine.close()

            # -- redeploy: fresh connections, fresh service instances --
            catalog = SqliteTrustCatalog(catalog_path)
            graph = SqliteCustodyGraph(graph_path)
            support = CustodyMemoryService(
                RecordingMemory(),
                SqliteQuarantine(support_quarantine_path),
                graph=graph,
                catalog=catalog,
                department="support",
            )

            # G4 still holds: support never vouched for crm_lookup, so its own
            # call to it is quarantined even though sales already trusts it.
            support_direct = await support.add_session_to_memory(
                _session("support-0", "support", [tool(COMPROMISED_TOOL, "500", inv="s0")])
            )
            self.assertEqual(support_direct.withheld, 1)

            # But a load_memory retrieval of sales' own restatement resolves
            # against the graph, which survived the redeploy intact.
            support_retrieval = await support.add_session_to_memory(
                _session(
                    "support-1",
                    "support",
                    [
                        tool("load_memory", "Acme owes 500.", inv="support-inv-1"),
                        model("Confirmed: Acme owes 500.", inv="support-inv-1"),
                    ],
                )
            )
            self.assertEqual(support_retrieval.withheld, 0)
            retrieval_record = support_retrieval.trusted[0].record
            self.assertIs(retrieval_record.origin, Origin.TOOL)
            self.assertEqual(len(retrieval_record.derived_from), 1)

            before_revocation = len(graph)
            catalog.close()
            graph.close()
            support.quarantine.close()

            # -- second redeploy: revoke, from a graph that never held state
            # in memory except what it just loaded from disk --
            graph = SqliteCustodyGraph(graph_path)
            self.assertEqual(len(graph), before_revocation)

            revocation = graph.revoke(tool=COMPROMISED_TOOL, revocation_id="rev-1")
            # A lower bound would pass even if revocation emptied the graph, and
            # over-removal is the dangerous direction: pulling memories that
            # never descended from the tool is silent data loss. Assert what
            # survived, not only how much went.
            self.assertEqual(len(revocation.removed), before_revocation - 1)
            surviving_records = graph.records()
            self.assertEqual(len(surviving_records), 1)
            self.assertIs(surviving_records[0].origin, Origin.USER)
            self.assertIsNone(surviving_records[0].source_tool)
            surviving = len(graph)
            graph.close()

            # -- third redeploy: replay must be a no-op --
            graph = SqliteCustodyGraph(graph_path)
            replay = graph.revoke(tool=COMPROMISED_TOOL, revocation_id="rev-1")
            self.assertEqual(replay, revocation)
            self.assertEqual(len(graph), surviving)
            self.assertEqual(len(graph.revocations()), 1)
            graph.close()


def _session(session_id: str, department: str, events: list):
    return FakeSession(
        id=session_id, app_name="fleet", user_id=department, events=events
    )


if __name__ == "__main__":
    unittest.main()
