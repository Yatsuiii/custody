"""The benchmark itself has to be right before its numbers mean anything."""

from __future__ import annotations

import unittest

from bench import harness, score, systems, variants
from bench.stub import StubModel


class EveryVariantBuilds(unittest.TestCase):
    def test_all_fifteen_produce_a_scenario(self):
        self.assertEqual(len(variants.VARIANTS), 15)
        for variant in variants.VARIANTS:
            self.assertIsNotNone(harness.build(variant).before)

    def test_truth_is_computed_from_the_rules_not_typed_in(self):
        """No variant declares its expected answer, only its true relations."""
        for variant in variants.VARIANTS:
            self.assertFalse(hasattr(variant, "expected"))

    def test_the_spread_pushes_in_both_directions(self):
        sizes = [len(harness.build(v).truth_changed) for v in variants.VARIANTS]
        self.assertGreaterEqual(sum(1 for s in sizes if s == 0), 4)
        self.assertGreaterEqual(max(sizes), 5)


class TheGroundTruthSaysWhatTheVariantMeant(unittest.TestCase):
    def truth(self, name: str) -> dict:
        return harness.build(variants.by_id(name)).truth_changed

    def test_a_root_contradiction_reaches_every_layer(self):
        self.assertEqual(
            self.truth("V01-root-contradiction"),
            {"A2": "CONTESTED", "H1": "REQUIRES_REVIEW", "E4": "STALE"},
        )

    def test_a_leaf_contradiction_reaches_nothing_else(self):
        self.assertEqual(self.truth("V02-leaf-contradiction"),
                         {"A7": "CONTESTED"})

    def test_support_for_a_supported_assumption_changes_nothing(self):
        self.assertEqual(self.truth("V03-support-not-contradict"), {})

    def test_an_irrelevant_paper_changes_nothing(self):
        self.assertEqual(self.truth("V04-irrelevant-paper"), {})

    def test_a_second_pass_of_the_same_evidence_changes_nothing(self):
        self.assertEqual(self.truth("V08-duplicate-ingestion"), {})

    def test_a_rejected_relation_does_not_immunise_the_assumption(self):
        self.assertEqual(self.truth("V09-human-override")["A2"], "CONTESTED")

    def test_more_of_the_same_evidence_does_not_churn(self):
        self.assertEqual(self.truth("V10-more-of-the-same"), {})

    def test_work_already_invalidated_is_not_reported_again(self):
        scenario = harness.build(variants.by_id("V11-retired-hypothesis"))
        self.assertEqual(scenario.before.state_of("E5"), "INVALIDATED")
        self.assertNotIn("E5", scenario.truth_changed)

    def test_weak_evidence_changes_nothing(self):
        self.assertEqual(self.truth("V13-weak-evidence"), {})

    def test_a_confirmed_contradiction_invalidates_and_weakens(self):
        self.assertEqual(
            self.truth("V14-confirmed-invalidation"),
            {"A5": "INVALIDATED", "H2": "WEAKENED", "E6": "REDUNDANT"},
        )

    def test_finished_experiments_never_appear_in_the_truth(self):
        scenario = harness.build(variants.by_id("V15-completed-work-untouched"))
        self.assertEqual(
            scenario.truth_changed,
            {"A1": "CONTESTED", "A5": "CONTESTED", "H1": "REQUIRES_REVIEW",
             "H2": "REQUIRES_REVIEW", "E5": "STALE", "E6": "STALE"},
        )
        for finished in ("E1", "E2"):
            self.assertEqual(scenario.before.state_of(finished), "COMPLETED")


class ScoringArithmetic(unittest.TestCase):
    def setUp(self):
        self.scenario = harness.build(variants.by_id("V01-root-contradiction"))

    def outcome(self, changed: dict, because: dict | None = None):
        return systems.Outcome("X", changed, because or {})

    def test_a_perfect_answer_scores_perfectly(self):
        row = score.score_outcome(
            self.scenario,
            self.outcome(dict(self.scenario.truth_changed),
                         {k: list(v) for k, v
                          in self.scenario.truth_because.items()}),
        )
        self.assertEqual((row["tp"], row["fp"], row["fn"]), (3, 0, 0))
        self.assertEqual(row["untouched_disturbed"], 0)
        self.assertEqual(row["provenance_exact"], 3)

    def test_an_extra_node_costs_precision_and_disturbs_the_untouched(self):
        answer = dict(self.scenario.truth_changed) | {"E5": "STALE"}
        row = score.score_outcome(self.scenario, self.outcome(answer))
        self.assertEqual((row["tp"], row["fp"], row["fn"]), (3, 1, 0))
        self.assertEqual(row["untouched_disturbed"], 1)

    def test_a_missing_node_costs_recall(self):
        answer = dict(self.scenario.truth_changed)
        answer.pop("E4")
        row = score.score_outcome(self.scenario, self.outcome(answer))
        self.assertEqual((row["tp"], row["fp"], row["fn"]), (2, 0, 1))

    def test_the_right_node_in_the_wrong_state_is_a_hit_but_not_exact(self):
        answer = dict(self.scenario.truth_changed) | {"A2": "INVALIDATED"}
        row = score.score_outcome(self.scenario, self.outcome(answer))
        self.assertEqual(row["tp"], 3)
        self.assertEqual(row["state_exact"], 2)

    def test_aggregate_micro_averages_across_rows(self):
        rows = [
            {"tp": 3, "fp": 1, "fn": 0, "state_exact": 3, "untouched_total": 10,
             "untouched_disturbed": 1, "provenance_contains_cause": 3,
             "provenance_exact": 2, "invalid_transitions": [], "failures": [],
             "edge_errors": [], "edge_judgments": 6,
             "prompt_tokens": 10, "output_tokens": 5, "seconds": 1.0,
             "calls": 1},
            {"tp": 1, "fp": 0, "fn": 2, "state_exact": 1, "untouched_total": 10,
             "untouched_disturbed": 0, "provenance_contains_cause": 0,
             "provenance_exact": 0, "invalid_transitions": ["x"],
             "edge_errors": ["strength_inflated:A4"], "edge_judgments": 6,
             "failures": [], "prompt_tokens": 10, "output_tokens": 5,
             "seconds": 1.0, "calls": 1},
        ]
        totals = score.aggregate(rows)
        self.assertEqual(totals["precision"], 0.8)
        self.assertEqual(totals["recall"], 0.6667)
        self.assertEqual(totals["unrelated_preserved"], 0.95)
        self.assertEqual(totals["invalid_transitions"], 1)
        self.assertEqual(totals["edge_errors"], 1)


class ForbiddenOutputsAreCaught(unittest.TestCase):
    def setUp(self):
        self.scenario = harness.build(variants.by_id("V01-root-contradiction"))

    def problems(self, changed: dict) -> list[str]:
        return score.invalid_transitions(
            self.scenario, systems.Outcome("X", changed, {})
        )

    def test_a_state_outside_the_vocabulary(self):
        self.assertIn("impossible_state:A2=BROKEN", self.problems({"A2": "BROKEN"}))

    def test_a_machine_retiring_a_hypothesis(self):
        self.assertIn("machine_retirement:H1", self.problems({"H1": "RETIRED"}))

    def test_re_judging_finished_work(self):
        self.assertIn("finished_work_re_judged:E1", self.problems({"E1": "STALE"}))

    def test_a_node_that_does_not_exist(self):
        self.assertIn("unknown_node:E99", self.problems({"E99": "STALE"}))


class TheStubRunsBothSystems(unittest.TestCase):
    def test_a_perfect_bounded_judge_reproduces_the_truth(self):
        scenario = harness.build(variants.by_id("V05-two-assumptions"))
        outcome = systems.run_system_b(scenario, StubModel(scenario))
        self.assertEqual(outcome.changed, scenario.truth_changed)

    def test_the_baseline_path_parses_and_scores(self):
        scenario = harness.build(variants.by_id("V05-two-assumptions"))
        outcome = systems.run_baseline_a(scenario, StubModel(scenario, "E5"))
        row = score.score_outcome(scenario, outcome)
        self.assertEqual(row["fp"], 1)
        self.assertEqual(row["fn"], 0)


if __name__ == "__main__":
    unittest.main()
