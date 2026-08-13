"""Adversarial checks for the independent D2 selective-deletion evidence judge."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime

from custody.memory_bank import memory_id_for
from scripts.memory_deletion_gates import judge

ENGINE = "projects/p/locations/us-central1/reasoningEngines/e"


def valid_evidence() -> dict:
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "engine_name": ENGINE,
        "claim_boundary": "not G1's ingest_events path.",
        "sales_record_id": "inv-sales:0:0",
        "finance_record_id": "inv-finance:0:0",
        "sales_fact": "ALPHA fact",
        "finance_fact": "BRAVO fact",
        "before_facts": ["ALPHA fact", "BRAVO fact"],
        "after_facts": ["BRAVO fact"],
        "revocation": {
            "id": "rev-1",
            "tool": "sales/lookup",
            "removed": ["inv-sales:0:0"],
        },
        "deleted_memory_name": f"{ENGINE}/memories/{memory_id_for('inv-sales:0:0')}",
        "surviving_memory_name": (
            f"{ENGINE}/memories/{memory_id_for('inv-finance:0:0')}"
        ),
    }


class MemoryDeletionGateJudgeTests(unittest.TestCase):
    def test_valid_artifact_passes_every_gate(self):
        gates = judge(valid_evidence())
        self.assertTrue(gates)
        self.assertTrue(all(gates.values()), gates)

    def test_the_sales_fact_still_present_after_revoke_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["after_facts"] = ["ALPHA fact", "BRAVO fact"]
        gates = judge(evidence)
        self.assertFalse(gates["sales_fact_gone_finance_fact_present_after_revoke"])

    def test_a_fabricated_memory_name_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["deleted_memory_name"] = f"{ENGINE}/memories/not-the-real-mapping"
        gates = judge(evidence)
        self.assertFalse(gates["deleted_memory_name_matches_the_recomputed_mapping"])

    def test_revoking_the_wrong_record_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["revocation"]["removed"] = ["inv-finance:0:0"]
        gates = judge(evidence)
        self.assertFalse(gates["only_sales_tool_revoked"])

    def test_a_missing_claim_boundary_cannot_pass(self):
        evidence = copy.deepcopy(valid_evidence())
        evidence["claim_boundary"] = "everything works, no caveats"
        gates = judge(evidence)
        self.assertFalse(gates["claim_boundary_names_ingest_events_as_out_of_scope"])


if __name__ == "__main__":
    unittest.main()
