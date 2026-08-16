"""The admission boundary: what a model is allowed to get past, and why not."""

from __future__ import annotations

import unittest

from keel import ingest
from keel.model import Relation, Source, Strength
from keel.program import from_dict

PAPER = Source(
    "S-X", "A fixture paper",
    "Linear probes recover absolute row and column indices with 94.6% accuracy. "
    "We observe no effect outside the grid domain.",
)

PROGRAM = from_dict({
    "assumptions": [{"id": "A1", "text": "position is not recoverable"}],
    "hypotheses": [],
    "experiments": [],
})


def proposal(**overrides) -> ingest.Proposal:
    fields = {
        "target": "A1",
        "relation": Relation.CONTRADICTS,
        "strength": Strength.STRONG,
        "confidence": 0.9,
        "excerpt": "Linear probes recover absolute row and column indices",
        "claim": "position is recoverable",
        "proposed_by": "model:test",
    }
    fields.update(overrides)
    return ingest.Proposal(**fields)


def reasons(admission: ingest.Admission) -> list[str]:
    return [item["refused"] for item in admission.refused]


class WhatGetsIn(unittest.TestCase):
    def test_a_well_formed_proposal_is_admitted_as_a_claim_and_an_edge(self):
        admission = ingest.ingest(PROGRAM, PAPER, [proposal()])
        self.assertEqual(reasons(admission), [])
        self.assertEqual(
            [item.kind for item in admission.events],
            ["source_added", "claim_added", "edge_proposed"],
        )

    def test_case_and_spacing_are_formatting_not_content(self):
        admission = ingest.ingest(PROGRAM, PAPER, [
            proposal(excerpt="linear  probes\nRECOVER absolute row and column"),
        ])
        self.assertEqual(reasons(admission), [])


class WhatIsRefused(unittest.TestCase):
    def refuse(self, **overrides) -> list[str]:
        return reasons(ingest.ingest(PROGRAM, PAPER, [proposal(**overrides)]))

    def test_an_excerpt_that_is_not_in_the_document(self):
        self.assertEqual(
            self.refuse(excerpt="probes recover position with 99.9% accuracy"),
            ["excerpt_not_found"],
        )

    def test_a_relation_outside_the_vocabulary(self):
        self.assertEqual(self.refuse(relation=Relation.UNRELATED), ["not_evidence"])

    def test_a_target_that_does_not_exist(self):
        self.assertEqual(self.refuse(target="A9"), ["unknown_target"])

    def test_a_judgment_with_no_strength(self):
        self.assertEqual(self.refuse(strength=None), ["strength_missing"])

    def test_a_judgment_below_the_confidence_floor(self):
        self.assertEqual(self.refuse(confidence=0.41), ["below_confidence"])

    def test_one_bad_proposal_does_not_sink_the_batch(self):
        admission = ingest.ingest(PROGRAM, PAPER, [
            proposal(), proposal(excerpt="not in the paper at all"),
        ])
        self.assertEqual(len(admission.admitted), 1)
        self.assertEqual(reasons(admission), ["excerpt_not_found"])

    def test_a_document_that_changed_under_the_same_id_refuses_everything(self):
        stored = from_dict({
            "assumptions": [{"id": "A1", "text": "position is not recoverable"}],
            "sources": [{"id": "S-X", "title": "A fixture paper",
                         "text": "an entirely different document"}],
        })
        admission = ingest.ingest(stored, PAPER, [proposal()])
        self.assertEqual(reasons(admission), ["source_text_conflict"])
        self.assertEqual(admission.events, ())


class ParsingWhatAJudgeReturned(unittest.TestCase):
    def test_a_word_outside_the_vocabulary_becomes_a_refusable_proposal(self):
        parsed = ingest.proposals_from(
            [{"target": "A1", "relation": "PROBABLY_RELATED", "confidence": 0.9}],
            "model:test",
        )
        self.assertEqual(parsed[0].relation, Relation.UNRELATED)
        self.assertIsNone(parsed[0].strength)

    def test_a_missing_confidence_reads_as_no_confidence(self):
        parsed = ingest.proposals_from(
            [{"target": "A1", "relation": "SUPPORTS", "strength": "STRONG"}],
            "model:test",
        )
        self.assertEqual(parsed[0].confidence, 0.0)


if __name__ == "__main__":
    unittest.main()
