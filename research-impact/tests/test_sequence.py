"""The longitudinal fixture and its metrics, checked before they are trusted."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from bench import seqscore, sequence, timeline
from bench.harness import base_program
from bench.replay import SequenceStub

LOCK = Path(__file__).resolve().parent.parent / "results" / "sequence-lock.json"


class TheAdjudicationIsExhaustive(unittest.TestCase):
    def setUp(self):
        self.assumptions = [a["id"] for a
                            in base_program(sequence.PROGRAM)["assumptions"]]

    def test_every_document_is_judged_against_every_assumption(self):
        for document in sequence.DOCUMENTS:
            for assumption in self.assumptions:
                self.assertIn(
                    sequence.label_for(document, assumption),
                    (sequence.RELATION, sequence.NO_RELATION,
                     sequence.AMBIGUOUS),
                )

    def test_debatable_pairs_are_marked_rather_than_guessed(self):
        self.assertEqual(sequence.ambiguous_pairs(),
                         (("D5", "B7"), ("D8", "B7")))

    def test_an_ambiguous_pair_never_moves_the_truth(self):
        for document, assumption in sequence.ambiguous_pairs():
            targets = [t for t, *_ in sequence.true_relations(document)]
            self.assertNotIn(assumption, targets)

    def test_the_lock_file_matches_the_code(self):
        locked = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertEqual(locked["label_counts"],
                         {"RELATION": 8, "NO_RELATION": 70, "AMBIGUOUS": 2})


class TheTrajectoryIsWhatTheSequenceMeant(unittest.TestCase):
    def setUp(self):
        self.trail = timeline.truth_trajectory("canonical")

    def moved(self, step: int) -> dict:
        before = self.trail[step - 1].states
        return {k: v for k, v in self.trail[step].states.items()
                if before[k] != v}

    def test_a_weak_signal_moves_nothing(self):
        self.assertEqual(self.moved(1), {})

    def test_repeating_the_same_finding_moves_nothing(self):
        self.assertEqual(self.moved(2), {})

    def test_contesting_a_settled_assumption_reactivates_its_experiment(self):
        self.assertEqual(self.trail[0].states["F6"], "REDUNDANT")
        self.assertEqual(self.moved(3),
                         {"B4": "CONTESTED", "F6": "PLANNED",
                          "H5": "REQUIRES_REVIEW"})

    def test_an_ambiguous_document_moves_nothing(self):
        self.assertEqual(self.moved(4), {})

    def test_support_against_a_standing_contradiction_moves_nothing(self):
        self.assertEqual(self.moved(6), {})

    def test_the_last_document_moves_nothing_at_all(self):
        self.assertEqual(self.moved(9), {})

    def test_all_three_orders_end_in_the_same_place(self):
        ends = {name: timeline.truth_trajectory(name)[-1].states
                for name in sequence.ORDERS}
        self.assertEqual(len({json.dumps(s, sort_keys=True)
                              for s in ends.values()}), 1)


class TheMetricsMeasureWhatTheyClaim(unittest.TestCase):
    def setUp(self):
        self.truth = timeline.truth_trajectory("canonical")

    def test_a_perfect_run_scores_perfectly(self):
        trail = timeline.run_b("canonical", SequenceStub("canonical"))
        row = seqscore.score_trail(trail, self.truth, "canonical")
        self.assertEqual(row["end_accuracy"], 1.0)
        self.assertEqual(row["regressions"], 0)
        self.assertEqual(row["unnecessary_changes"], 0)
        self.assertEqual(row["correction_persistence"], 1.0)

    def test_a_wrong_node_is_counted_every_step_it_stays_wrong(self):
        trail = timeline.run_b("canonical", SequenceStub("canonical"))
        broken = [
            timeline.Snapshot(s.step, s.document,
                              dict(s.states) | {"B1": "INVALIDATED"})
            for s in trail
        ]
        row = seqscore.score_trail(broken, self.truth, "canonical")
        self.assertEqual(row["wrong_node_steps"], len(trail))
        self.assertEqual(row["longest_error_survival"], len(trail))

    def test_order_agreement_counts_the_largest_matching_group(self):
        rows = [
            {"order": "canonical", "run": 1, "end_state": {"B1": "SUPPORTED"}},
            {"order": "swap-early", "run": 1, "end_state": {"B1": "SUPPORTED"}},
            {"order": "swap-late", "run": 1, "end_state": {"B1": "CONTESTED"}},
        ]
        self.assertEqual(seqscore.orders_agreeing(rows), 2)


if __name__ == "__main__":
    unittest.main()
