"""Correction locality, tested on cases where the right answer is known."""

from __future__ import annotations

import unittest

from bench import harness, repair, systems, variants
from keel import ledger
from keel.propagate import evaluate


def judgment(target: str, relation: str, strength: str, sentence: int) -> dict:
    return {
        "target": target,
        "answer": {"relation": relation, "sentence": sentence,
                   "strength": strength, "confidence": 0.9},
    }


def outcome_b(scenario, raw: list[dict]) -> systems.Outcome:
    """Run the real System B pipeline over a fixed set of judgments."""
    relations = [
        systems.relation_for(item["target"], item["answer"], "v1")
        for item in raw
    ]
    log, admission = harness.admit(
        scenario.log, scenario.variant.document,
        [r for r in relations if r is not None], "model:judge",
    )
    if scenario.variant.confirmed:
        log = harness.confirm_new_edges(log, admission)
    after = evaluate(ledger.replay(log))
    changed = {
        node: after.state_of(node) for node in after.nodes
        if scenario.before.state_of(node) != after.state_of(node)
    }
    return systems.Outcome("B", changed, {}, raw=raw)


class AnAnswerThatIsAlreadyRight(unittest.TestCase):
    def setUp(self):
        self.scenario = harness.build(
            variants.by_id("V01-root-contradiction")
        )

    def test_costs_nothing_to_correct(self):
        cost = repair.repair_cost(
            self.scenario, outcome_b(self.scenario,
                                     [judgment("A2", "CONTRADICTS", "STRONG", 1)])
        )
        self.assertEqual(cost["corrections_required"], 0)
        self.assertEqual(cost["wrong_nodes_before"], 0)
        self.assertEqual(cost["residual_wrong_nodes"], 0)


class OneWrongRelationAmplifiesThenRepairs(unittest.TestCase):
    """The claim under test: one rejection restores every consequence."""

    def setUp(self):
        self.scenario = harness.build(variants.by_id("V13-weak-evidence"))
        # The dev set's real failure: WEAK evidence called MODERATE, which
        # propagates where the truth says it should not.
        self.cost = repair.repair_cost(
            self.scenario,
            outcome_b(self.scenario,
                      [judgment("A4", "CONTRADICTS", "MODERATE", 1)]),
        )

    def test_one_judgment_produced_several_wrong_nodes(self):
        self.assertGreater(self.cost["wrong_nodes_before"], 1)

    def test_but_only_one_correction_is_needed(self):
        self.assertEqual(self.cost["corrections_required"], 1)

    def test_and_that_correction_leaves_nothing_wrong(self):
        self.assertEqual(self.cost["residual_wrong_nodes"], 0)

    def test_the_ratio_is_reported_as_nodes_per_correction(self):
        self.assertEqual(
            self.cost["nodes_per_correction"], self.cost["wrong_nodes_before"]
        )

    def test_what_is_corrected_is_a_relation_not_a_state(self):
        self.assertIn("relation", self.cost["correction_target"])


class TheBaselineIsCorrectedNodeByNode(unittest.TestCase):
    def setUp(self):
        self.scenario = harness.build(variants.by_id("V01-root-contradiction"))

    def test_every_wrong_node_is_its_own_edit(self):
        wrong = dict(self.scenario.truth_changed) | {"E5": "STALE"}
        wrong.pop("E4")
        cost = repair.repair_cost(
            self.scenario, systems.Outcome("A", wrong, {})
        )
        self.assertEqual(cost["corrections_required"], 2)
        self.assertEqual(cost["nodes_per_correction"], 1.0)
        self.assertIn("final states", cost["correction_target"])


class AggregatingAcrossRuns(unittest.TestCase):
    def test_it_divides_nodes_by_corrections(self):
        rows = [
            {"repair": {"wrong_nodes_before": 4, "corrections_required": 1,
                        "residual_wrong_nodes": 0}},
            {"repair": {"wrong_nodes_before": 3, "corrections_required": 2,
                        "residual_wrong_nodes": 1}},
            {"repair": {"wrong_nodes_before": 0, "corrections_required": 0,
                        "residual_wrong_nodes": 0}},
        ]
        totals = repair.aggregate_repair(rows)
        self.assertEqual(totals["wrong_nodes"], 7)
        self.assertEqual(totals["corrections_required"], 3)
        self.assertEqual(totals["nodes_repaired_per_correction"], 2.333)
        self.assertEqual(totals["residual_wrong_nodes_after_correction"], 1)
        self.assertEqual(totals["rows_needing_no_correction"], 1)


if __name__ == "__main__":
    unittest.main()
