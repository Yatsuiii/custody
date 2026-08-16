"""The state rules, tested one rule at a time, without a graph in the way."""

from __future__ import annotations

import unittest

from keel.model import (
    AssumptionState,
    Edge,
    EdgeStatus,
    ExperimentState,
    HypothesisState,
    Relation,
    Strength,
)
from keel.policy import assumption_state, experiment_state, hypothesis_state


def evidence(
    identifier: str,
    relation: Relation,
    strength: Strength = Strength.MODERATE,
    status: EdgeStatus = EdgeStatus.PROPOSED,
    confidence: float = 0.9,
) -> Edge:
    return Edge(identifier, relation, "c-1", "A1", status, strength, confidence)


def link(identifier: str, relation: Relation, source: str, target: str) -> Edge:
    return Edge(identifier, relation, source, target)


class AnAssumptionReadsOnlyItsEvidence(unittest.TestCase):
    def test_no_evidence_is_unknown_rather_than_believed(self):
        self.assertEqual(assumption_state([])[0], AssumptionState.UNKNOWN)

    def test_support_alone_supports(self):
        state, because = assumption_state([evidence("e1", Relation.SUPPORTS)])
        self.assertEqual(state, AssumptionState.SUPPORTED)
        self.assertEqual(because, ("e1",))

    def test_contradiction_alone_contests(self):
        state, _ = assumption_state([evidence("e1", Relation.CONTRADICTS)])
        self.assertEqual(state, AssumptionState.CONTESTED)

    def test_strong_confirmed_contradiction_invalidates(self):
        state, because = assumption_state([
            evidence("e1", Relation.CONTRADICTS, Strength.STRONG,
                     EdgeStatus.CONFIRMED),
        ])
        self.assertEqual(state, AssumptionState.INVALIDATED)
        self.assertEqual(because, ("e1",))

    def test_standing_support_turns_invalidation_into_a_contest(self):
        """The reason it was believed does not disappear when it is challenged."""
        state, because = assumption_state([
            evidence("e1", Relation.CONTRADICTS, Strength.STRONG,
                     EdgeStatus.CONFIRMED),
            evidence("e2", Relation.SUPPORTS),
        ])
        self.assertEqual(state, AssumptionState.CONTESTED)
        self.assertEqual(because, ("e1", "e2"))

    def test_weak_evidence_is_recorded_but_does_not_move_the_state(self):
        state, _ = assumption_state([
            evidence("e1", Relation.CONTRADICTS, Strength.WEAK),
        ])
        self.assertEqual(state, AssumptionState.UNKNOWN)

    def test_low_confidence_does_not_move_the_state(self):
        state, _ = assumption_state([
            evidence("e1", Relation.CONTRADICTS, confidence=0.4),
        ])
        self.assertEqual(state, AssumptionState.UNKNOWN)

    def test_a_rejected_relation_stops_counting(self):
        state, _ = assumption_state([
            evidence("e1", Relation.CONTRADICTS, status=EdgeStatus.REJECTED),
            evidence("e2", Relation.SUPPORTS),
        ])
        self.assertEqual(state, AssumptionState.SUPPORTED)


class AHypothesisReadsItsDependencies(unittest.TestCase):
    def setUp(self):
        self.depends = [link("d1", Relation.DEPENDS_ON, "H1", "A1")]

    def test_healthy_dependencies_leave_it_active(self):
        state, because = hypothesis_state(
            self.depends, {"A1": AssumptionState.SUPPORTED}, [], None
        )
        self.assertEqual(state, HypothesisState.ACTIVE)
        self.assertEqual(because, ())

    def test_an_unknown_dependency_is_not_a_change(self):
        state, _ = hypothesis_state(
            self.depends, {"A1": AssumptionState.UNKNOWN}, [], None
        )
        self.assertEqual(state, HypothesisState.ACTIVE)

    def test_a_contested_dependency_asks_for_review(self):
        state, because = hypothesis_state(
            self.depends, {"A1": AssumptionState.CONTESTED}, [], None
        )
        self.assertEqual(state, HypothesisState.REQUIRES_REVIEW)
        self.assertEqual(because, ("d1",))

    def test_an_invalidated_dependency_weakens_it(self):
        state, _ = hypothesis_state(
            self.depends, {"A1": AssumptionState.INVALIDATED}, [], None
        )
        self.assertEqual(state, HypothesisState.WEAKENED)

    def test_only_a_human_decision_retires_it(self):
        state, because = hypothesis_state(
            self.depends, {"A1": AssumptionState.INVALIDATED}, [], "d-99"
        )
        self.assertEqual(state, HypothesisState.RETIRED)
        self.assertEqual(because, ("d-99",))


class AnExperimentReadsItsPremises(unittest.TestCase):
    def setUp(self):
        self.requires = [link("r1", Relation.REQUIRES, "E1", "A1")]
        self.tests = [link("t1", Relation.TESTS, "E1", "H1")]
        self.establishes = [link("s1", Relation.ESTABLISHES, "E1", "A2")]
        self.healthy = {"A1": AssumptionState.SUPPORTED,
                        "A2": AssumptionState.UNKNOWN}
        self.live = {"H1": HypothesisState.ACTIVE}

    def judge(self, lifecycle, assumptions, hypotheses, settled=frozenset()):
        return experiment_state(
            lifecycle, self.requires, self.tests, self.establishes,
            assumptions, hypotheses, settled,
        )

    def test_finished_work_is_never_re_judged(self):
        broken = {"A1": AssumptionState.INVALIDATED,
                  "A2": AssumptionState.UNKNOWN}
        state, because = self.judge(ExperimentState.COMPLETED, broken, self.live)
        self.assertEqual(state, ExperimentState.COMPLETED)
        self.assertEqual(because, ())

    def test_a_planned_experiment_on_a_shaken_premise_goes_stale(self):
        shaken = {"A1": AssumptionState.CONTESTED, "A2": AssumptionState.UNKNOWN}
        state, because = self.judge(ExperimentState.PLANNED, shaken, self.live)
        self.assertEqual(state, ExperimentState.STALE)
        self.assertEqual(because, ("r1",))

    def test_a_settled_question_makes_planned_work_redundant(self):
        state, because = self.judge(
            ExperimentState.PLANNED, self.healthy, self.live, frozenset({"A2"})
        )
        self.assertEqual(state, ExperimentState.REDUNDANT)
        self.assertEqual(because, ("s1",))

    def test_a_broken_premise_outranks_a_settled_question(self):
        """It cannot answer anything, including the question that settled."""
        shaken = {"A1": AssumptionState.CONTESTED, "A2": AssumptionState.SUPPORTED}
        state, _ = self.judge(
            ExperimentState.PLANNED, shaken, self.live, frozenset({"A2"})
        )
        self.assertEqual(state, ExperimentState.STALE)

    def test_retiring_the_hypothesis_invalidates_the_work_that_tested_it(self):
        state, because = self.judge(
            ExperimentState.PLANNED, self.healthy,
            {"H1": HypothesisState.RETIRED},
        )
        self.assertEqual(state, ExperimentState.INVALIDATED)
        self.assertEqual(because, ("t1",))

    def test_healthy_premises_leave_it_planned(self):
        state, _ = self.judge(ExperimentState.PLANNED, self.healthy, self.live)
        self.assertEqual(state, ExperimentState.PLANNED)


if __name__ == "__main__":
    unittest.main()
