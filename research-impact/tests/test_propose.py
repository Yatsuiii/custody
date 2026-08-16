"""The replacement experiment: computed slots, and a check with teeth."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from keel import ingest, ledger, propose
from keel.model import Source
from keel.propagate import evaluate

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PROGRAM = json.loads((FIXTURES / "arc_program.json").read_text(encoding="utf-8"))
EVIDENCE = json.loads((FIXTURES / "evidence.json").read_text(encoding="utf-8"))


def after_the_paper() -> tuple:
    log = (ledger.event(ledger.PROGRAM_DECLARED, PROGRAM, "2026-08-15T00:00:00Z"),)
    raw = EVIDENCE["new_paper"]["source"]
    source = Source(raw["id"], raw["title"], raw["text"], raw["kind"],
                    raw["produced_by"])
    proposals = ingest.proposals_from(
        EVIDENCE["new_paper"]["proposals"], "model:fixture-judge"
    )
    admission = ingest.ingest(ledger.replay(log), source, proposals)
    log = ledger.extend(log, list(admission.events))
    program = ledger.replay(log)
    return program, evaluate(program)


class TheSlotsAreComputed(unittest.TestCase):
    def setUp(self):
        self.program, self.state = after_the_paper()
        self.spec = propose.slots(self.program, self.state)

    def test_the_open_question_is_the_contested_assumption(self):
        self.assertEqual(self.spec.targets, ("A2",))

    def test_the_hypotheses_to_discriminate_are_the_shaken_ones(self):
        self.assertEqual(self.spec.discriminates, ("H1",))

    def test_what_may_be_relied_on_excludes_the_contested_premise(self):
        self.assertNotIn("A2", self.spec.may_rely_on)
        self.assertEqual(self.spec.may_rely_on, ("A3",))

    def test_it_names_the_work_it_replaces(self):
        self.assertEqual(self.spec.supersedes, ("E4", "E7"))


class TheCheckHasTeeth(unittest.TestCase):
    def setUp(self):
        self.program, self.state = after_the_paper()
        self.spec = propose.slots(self.program, self.state)

    def check(self, candidate: propose.Candidate):
        return propose.check(self.program, self.state, self.spec, candidate)

    def test_the_drafted_candidate_passes(self):
        valid, problems = self.check(propose.draft(self.spec, "E8", "a method"))
        self.assertTrue(valid)
        self.assertEqual(problems, [])

    def test_a_candidate_standing_on_the_contested_premise_is_refused(self):
        valid, problems = self.check(
            propose.Candidate("E9", ("A2", "A3"), ("H1",), ("A2",))
        )
        self.assertFalse(valid)
        self.assertIn("relies_on_unsafe_assumption:A2", problems)

    def test_a_candidate_that_answers_nothing_open_is_refused(self):
        valid, problems = self.check(
            propose.Candidate("E10", ("A3",), ("H1",), ("A5",))
        )
        self.assertFalse(valid)
        self.assertIn("does_not_target_an_open_question", problems)

    def test_a_candidate_naming_a_node_that_does_not_exist_is_refused(self):
        valid, problems = self.check(
            propose.Candidate("E11", ("A99",), ("H1",), ("A2",))
        )
        self.assertFalse(valid)
        self.assertIn("unknown_assumption:A99", problems)

    def test_a_candidate_that_tests_a_retired_hypothesis_is_refused(self):
        log = ledger.append(
            (ledger.event(ledger.PROGRAM_DECLARED, PROGRAM, "2026-08-15T00:00:00Z"),),
            ledger.event(ledger.DECISION_RECORDED, {
                "id": "d-1", "actor": "human:owner", "kind": "retire_hypothesis",
                "target": "H1", "rationale": "superseded by H3",
            }),
        )
        program = ledger.replay(log)
        state = evaluate(program)
        spec = propose.slots(program, state)
        valid, problems = propose.check(
            program, state, spec, propose.Candidate("E12", ("A3",), ("H1",), ("A2",))
        )
        self.assertFalse(valid)
        self.assertIn("tests_no_live_hypothesis", problems)


class WhatTheJudgeReadsIsWhatTheModelWrote(unittest.TestCase):
    def test_the_method_is_the_only_free_text_in_a_candidate(self):
        program, state = after_the_paper()
        spec = propose.slots(program, state)
        drafted = propose.draft(spec, "E8", "any prose at all")
        self.assertEqual(drafted.requires, spec.may_rely_on)
        self.assertEqual(drafted.tests, spec.discriminates)
        self.assertEqual(drafted.establishes, spec.targets[:1])


if __name__ == "__main__":
    unittest.main()
