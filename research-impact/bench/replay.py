"""Two models that make no network calls: one for testing, one for judging.

`SequenceStub` answers the sequence perfectly, so the harness can be exercised
offline. Its numbers are not results and the artifact records its mode.

`ReplayModel` returns answers recorded during a live run, in order. The judge
uses it to re-run the exact same code path over the exact same model output, so
a trajectory in an artifact can be reproduced rather than believed.
"""

from __future__ import annotations

import json

from .gemini import Call
from .sequence import DOCUMENTS, true_relations


def answers_for(row: dict) -> list[str]:
    """The model output a recorded run produced, in the order it was asked."""
    if row["system"] == "B":
        return [
            json.dumps(item["answer"])
            for step in row["trail"]
            for item in step["raw"].get("judgments", [])
        ]
    return [json.dumps(step["raw"]) for step in row["trail"]]


class ReplayModel:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.index = 0

    def describe(self) -> dict:
        return {"model": "replay", "api": "recorded answers, no network"}

    def ask(self, prompt: str, schema: dict) -> Call:
        if self.index >= len(self.answers):
            return Call("{}", 0, 0, 0.0, "replay exhausted")
        answer = self.answers[self.index]
        self.index += 1
        return Call(answer, 0, 0, 0.0)


class SequenceStub:
    """A perfect judge and a perfect state maintainer, for harness checks."""

    def __init__(self, order: str) -> None:
        self.order = order

    def describe(self) -> dict:
        return {"model": "stub", "api": "recorded, no network"}

    def ask(self, prompt: str, schema: dict) -> Call:
        if "ASSUMPTION UNDER TEST:" in prompt:
            return self._judge(prompt)
        return _call({"changed": [], "relations": []})

    def _judge(self, prompt: str) -> Call:
        target = prompt.split("ASSUMPTION UNDER TEST:", 1)[1]
        target = target.strip().split("\n", 1)[0].strip()
        document = next(
            (name for name in DOCUMENTS if f"DOCUMENT: {DOCUMENTS[name].title}"
             in prompt),
            "",
        )
        for assumption, relation, strength, sentence in true_relations(document):
            if assumption == target:
                return _call({"relation": relation, "sentence": sentence,
                              "strength": strength, "confidence": 0.9})
        return _call({"relation": "UNRELATED", "sentence": 0,
                      "strength": "NONE", "confidence": 0.0})


def _call(payload: dict) -> Call:
    text = json.dumps(payload)
    return Call(text, len(text) // 4, len(text) // 4, 0.001)
