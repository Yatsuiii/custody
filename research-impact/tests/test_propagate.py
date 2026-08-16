"""Propagation over the real fixture: blast radius, chains, and self-evidence."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from keel import ingest, ledger
from keel.model import Relation, Source, Strength
from keel.propagate import evaluate, explain

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PROGRAM = json.loads((FIXTURES / "arc_program.json").read_text(encoding="utf-8"))
GENESIS = (ledger.event(ledger.PROGRAM_DECLARED, PROGRAM, "2026-08-15T00:00:00Z"),)

CONTRADICTS_A2 = Source(
    "S-T1", "A fixture paper",
    "Linear probes recover absolute row and column indices from flattened "
    "grids with 94.6% accuracy.",
)


def admit(log: tuple, source: Source, proposals: list[ingest.Proposal]) -> tuple:
    admission = ingest.ingest(ledger.replay(log), source, proposals)
    return ledger.extend(log, list(admission.events))


def proposal(target: str, relation: Relation, excerpt: str) -> ingest.Proposal:
    return ingest.Proposal(
        target, relation, Strength.STRONG, 0.9, excerpt, "a claim", "model:test"
    )


class TheProgramAsDeclared(unittest.TestCase):
    def setUp(self):
        self.state = evaluate(ledger.replay(GENESIS))

    def test_assumptions_start_where_their_evidence_puts_them(self):
        self.assertEqual(self.state.state_of("A1"), "SUPPORTED")
        self.assertEqual(self.state.state_of("A5"), "UNKNOWN")

    def test_a_weak_contradiction_is_on_the_record_without_moving_a_state(self):
        self.assertEqual(self.state.state_of("A4"), "SUPPORTED")
        contradictions = [
            e for e in ledger.replay(GENESIS).edges.values()
            if e.target == "A4" and e.relation is Relation.CONTRADICTS
        ]
        self.assertEqual(len(contradictions), 1)

    def test_planned_work_starts_planned(self):
        for node in ("E4", "E5", "E6", "E7"):
            self.assertEqual(self.state.state_of(node), "PLANNED")


class NewEvidenceAgainstOneAssumption(unittest.TestCase):
    def setUp(self):
        self.before = evaluate(ledger.replay(GENESIS))
        self.log = admit(GENESIS, CONTRADICTS_A2, [
            proposal("A2", Relation.CONTRADICTS,
                     "Linear probes recover absolute row and column indices"),
        ])
        self.program = ledger.replay(self.log)
        self.after = evaluate(self.program)

    def test_the_blast_radius_is_exactly_the_true_descendants(self):
        moved = {
            node for node in self.after.nodes
            if self.before.state_of(node) != self.after.state_of(node)
        }
        self.assertEqual(moved, {"A2", "H1", "E4"})

    def test_the_experiment_that_only_shares_a_hypothesis_survives(self):
        """E6 tests H1 too. Testing a shaken hypothesis is not depending on it."""
        self.assertEqual(self.after.state_of("H1"), "REQUIRES_REVIEW")
        self.assertEqual(self.after.state_of("E6"), "PLANNED")

    def test_the_chain_from_a_stale_experiment_reaches_a_quoted_sentence(self):
        chain = explain(self.program, self.after, "E4")
        self.assertEqual(chain["state"], "STALE")
        step = chain["because"][0]
        self.assertEqual(step["relation"], "REQUIRES")
        leaf = step["then"]["because"][0]
        self.assertEqual(leaf["relation"], "CONTRADICTS")
        self.assertIn("Linear probes recover", leaf["excerpt"])
        self.assertEqual(leaf["source"], "S-T1")

    def test_a_rejected_relation_puts_everything_back(self):
        edge = next(e for e in self.program.edges.values()
                    if e.target == "A2" and e.relation is Relation.CONTRADICTS)
        reverted = evaluate(ledger.replay(ledger.append(
            self.log, ledger.reject(edge, "human:owner", "different regime")
        )))
        self.assertEqual(reverted.as_dict(), self.before.as_dict())


class AnExperimentCannotSettleItsOwnQuestion(unittest.TestCase):
    """E6 establishes A5. Evidence E6 produced must not make E6 redundant."""

    OWN_RESULT = Source(
        "S-T2", "E6 run log",
        "One-step accuracy tracked full-task solve rate at r=0.88 across 100 "
        "tasks.",
        kind="result", produced_by="E6",
    )
    SOMEONE_ELSE = Source(
        "S-T3", "Another group's paper",
        "One-step accuracy tracked full-task solve rate at r=0.88 across 100 "
        "tasks.",
    )
    EXCERPT = "One-step accuracy tracked full-task solve rate at r=0.88"

    def state_after(self, source: Source):
        log = admit(GENESIS, source,
                    [proposal("A5", Relation.SUPPORTS, self.EXCERPT)])
        return evaluate(ledger.replay(log))

    def test_its_own_result_settles_the_question_without_retiring_the_work(self):
        state = self.state_after(self.OWN_RESULT)
        self.assertEqual(state.state_of("A5"), "SUPPORTED")
        self.assertEqual(state.state_of("E6"), "PLANNED")

    def test_the_same_finding_from_elsewhere_makes_it_redundant(self):
        state = self.state_after(self.SOMEONE_ELSE)
        self.assertEqual(state.state_of("A5"), "SUPPORTED")
        self.assertEqual(state.state_of("E6"), "REDUNDANT")


if __name__ == "__main__":
    unittest.main()
