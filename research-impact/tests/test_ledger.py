"""The log: identity by content, replay by fold, and no in-place edits."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from keel import ledger
from keel.model import EdgeStatus, Relation
from keel.program import digest_of

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PROGRAM = json.loads((FIXTURES / "arc_program.json").read_text(encoding="utf-8"))
GENESIS = (ledger.event(ledger.PROGRAM_DECLARED, PROGRAM, "2026-08-15T00:00:00Z"),)


class AnEventIsItsContent(unittest.TestCase):
    def test_the_same_action_twice_is_one_event(self):
        first = ledger.event("source_added", {"id": "S-1"}, "2026-08-15T00:00:00Z")
        later = ledger.event("source_added", {"id": "S-1"}, "2026-09-01T00:00:00Z")
        self.assertEqual(first.id, later.id)
        self.assertEqual(ledger.append((first,), later), (first,))

    def test_a_different_payload_is_a_different_event(self):
        first = ledger.event("source_added", {"id": "S-1"})
        other = ledger.event("source_added", {"id": "S-2"})
        self.assertNotEqual(first.id, other.id)
        self.assertEqual(len(ledger.append((first,), other)), 2)


class ReplayIsAFold(unittest.TestCase):
    def test_two_folds_of_one_log_agree_exactly(self):
        self.assertEqual(
            digest_of(ledger.replay(GENESIS)), digest_of(ledger.replay(GENESIS))
        )

    def test_a_rejection_changes_status_rather_than_removing_history(self):
        program = ledger.replay(GENESIS)
        edge = next(e for e in program.edges.values()
                    if e.relation is Relation.CONTRADICTS)
        after = ledger.replay(
            ledger.append(GENESIS, ledger.reject(edge, "human:owner", "why"))
        )
        self.assertEqual(after.edges[edge.id].status, EdgeStatus.REJECTED)
        self.assertEqual(len(after.edges), len(program.edges))

    def test_confirming_a_proposed_relation_records_the_human(self):
        program = ledger.replay(GENESIS)
        edge = next(iter(program.edges.values()))
        after = ledger.replay(
            ledger.append(GENESIS, ledger.confirm(edge, "human:owner"))
        )
        self.assertEqual(after.edges[edge.id].status, EdgeStatus.CONFIRMED)

    def test_restating_an_edge_that_was_never_recorded_is_an_error(self):
        broken = ledger.event(ledger.EDGE_REJECTED, {"edge": "e-nope"})
        with self.assertRaises(ValueError):
            ledger.replay(ledger.append(GENESIS, broken))

    def test_an_unknown_event_kind_is_an_error_rather_than_a_shrug(self):
        with self.assertRaises(ValueError):
            ledger.replay((ledger.event("invented_kind", {}),))

    def test_a_log_that_folds_into_a_broken_program_is_refused(self):
        fabricated = ledger.event(ledger.CLAIM_ADDED, {
            "source": "S-R1", "text": "not in the log",
            "excerpt": "a sentence that does not occur in the run log",
        })
        with self.assertRaises(ValueError):
            ledger.replay(ledger.append(GENESIS, fabricated))


if __name__ == "__main__":
    unittest.main()
