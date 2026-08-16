"""Loading a program, and refusing the ones that would evaluate to nonsense."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from keel.program import from_dict, load, to_dict

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

MINIMAL = {
    "questions": [{"id": "RQ1", "text": "a question"}],
    "hypotheses": [{"id": "H1", "question": "RQ1", "text": "a hypothesis"}],
    "assumptions": [{"id": "A1", "text": "an assumption"}],
    "experiments": [{"id": "E1", "lifecycle": "PLANNED", "text": "an experiment"}],
    "sources": [{"id": "S1", "title": "a note",
                 "text": "the grid is eleven cells wide"}],
    "claims": [{"ref": "CL1", "source": "S1", "text": "width is eleven",
                "excerpt": "the grid is eleven cells wide"}],
    "edges": [{"relation": "DEPENDS_ON", "source": "H1", "target": "A1"}],
}


def with_edges(*edges) -> dict:
    payload = json.loads(json.dumps(MINIMAL))
    payload["edges"] = list(edges)
    return payload


class TheFixtureProgram(unittest.TestCase):
    def test_it_loads(self):
        program = load(FIXTURES / "arc_program.json")
        self.assertEqual(len(program.hypotheses), 2)
        self.assertEqual(len(program.assumptions), 6)
        self.assertEqual(len(program.experiments), 7)

    def test_its_document_form_round_trips(self):
        program = load(FIXTURES / "arc_program.json")
        again = from_dict(to_dict(program))
        self.assertEqual(to_dict(program), to_dict(again))


class AMalformedProgramIsRefused(unittest.TestCase):
    def refuses(self, payload: dict, fragment: str):
        with self.assertRaises(ValueError) as raised:
            from_dict(payload)
        self.assertIn(fragment, str(raised.exception))

    def test_a_dependency_pointing_at_the_wrong_kind_of_node(self):
        self.refuses(
            with_edges({"relation": "DEPENDS_ON", "source": "H1", "target": "E1"}),
            "is not a assumptions",
        )

    def test_an_experiment_requiring_a_hypothesis(self):
        self.refuses(
            with_edges({"relation": "REQUIRES", "source": "E1", "target": "H1"}),
            "is not a assumptions",
        )

    def test_evidence_asserted_by_something_that_is_not_a_claim(self):
        self.refuses(
            with_edges({"relation": "SUPPORTS", "source": "E1", "target": "A1",
                        "strength": "STRONG"}),
            "is not a claim",
        )

    def test_evidence_with_no_strength(self):
        self.refuses(
            with_edges({"relation": "SUPPORTS", "source": "CL1", "target": "A1"}),
            "evidence with no strength",
        )

    def test_an_edge_pointing_at_itself(self):
        self.refuses(
            with_edges({"relation": "DEPENDS_ON", "source": "H1", "target": "H1"}),
            "points at itself",
        )

    def test_a_claim_quoting_a_sentence_its_source_does_not_contain(self):
        payload = json.loads(json.dumps(MINIMAL))
        payload["claims"][0]["excerpt"] = "the grid is ninety cells wide"
        self.refuses(payload, "excerpt is not in S1")

    def test_a_claim_quoting_a_document_that_does_not_exist(self):
        payload = json.loads(json.dumps(MINIMAL))
        payload["claims"][0]["source"] = "S-missing"
        self.refuses(payload, "unknown source")


if __name__ == "__main__":
    unittest.main()
