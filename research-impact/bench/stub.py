"""A recorded stand-in for the model, so the harness can be tested for free.

It answers the bounded question perfectly and the monolithic question sloppily,
which is a hypothesis about the result, not a finding. Nothing produced with it
may be reported as a measurement: the artifact records its mode for exactly that
reason.
"""

from __future__ import annotations

import json

from .gemini import Call


class StubModel:
    DISTANCE = {"STRONG": ("DIRECT", True), "MODERATE": ("ONE_STEP", True),
                "WEAK": ("ONE_STEP", False)}

    def __init__(self, scenario, spurious: str = "") -> None:
        self.scenario = scenario
        self.spurious = spurious or self._an_untouched_experiment()

    def _an_untouched_experiment(self) -> str:
        """A node that exists and should not move, so the stub's noise is real."""
        return next(
            (node for node, entry in sorted(self.scenario.before.nodes.items())
             if entry.kind == "experiment" and entry.state == "PLANNED"
             and node not in self.scenario.truth_changed),
            "",
        )

    def describe(self) -> dict:
        return {"model": "stub", "project": None, "location": None,
                "api": "recorded, no network"}

    def ask(self, prompt: str, schema: dict) -> Call:
        if "ASSUMPTION UNDER TEST:" in prompt:
            return self._judge(prompt, "inference_distance" in prompt)
        return self._baseline()

    def _judge(self, prompt: str, v2: bool) -> Call:
        marker = prompt.split("ASSUMPTION UNDER TEST:", 1)[1]
        target = marker.strip().split("\n", 1)[0].strip()
        for item in self.scenario.variant.truth:
            if item.target == target:
                answer = {"relation": item.relation, "sentence": item.sentence,
                          "confidence": item.confidence}
                return _call(answer | self._shape(item.strength, v2))
        return _call({"relation": "UNRELATED", "sentence": 0,
                      "confidence": 0.0} | self._shape("WEAK", v2))

    def _shape(self, strength: str, v2: bool) -> dict:
        if not v2:
            return {"strength": strength}
        distance, same = self.DISTANCE[strength]
        return {"inference_distance": distance, "same_setting": same}

    def _baseline(self) -> Call:
        changed = [
            {"node": node, "from": self.scenario.before.state_of(node),
             "to": state, "because": list(self.scenario.truth_because[node])}
            for node, state in sorted(self.scenario.truth_changed.items())
        ]
        if self.spurious and self.spurious not in self.scenario.truth_changed:
            changed.append({"node": self.spurious, "from": "PLANNED",
                            "to": "STALE", "because": []})
        return _call({"changed": changed})


def _call(payload: dict) -> Call:
    text = json.dumps(payload)
    return Call(text, len(text) // 4, len(text) // 4, 0.001)
