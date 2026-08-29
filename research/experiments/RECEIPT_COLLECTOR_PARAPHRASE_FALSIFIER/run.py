"""Falsifies (or confirms) TRUSTED_COMPUTING_BASE.md's context/receipt
collector status: "Unproven across current retrieval and server-side
Memory Bank transformations... hidden input can receive an incomplete but
trusted-looking output."

Tests the real, shipped `custody.origin.take_custody` resolver path
against the exact paraphrase divergence pattern found in this repository's
own committed live evidence (`proof-out/g1.json`), not a synthetic string.

Run: python3 research/experiments/RECEIPT_COLLECTOR_PARAPHRASE_FALSIFIER/run.py
No network access or credentials required -- pure offline call into
production code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from custody.graph import CustodyGraph
from custody.origin import CustodyRecord, Origin, Trust, digest, take_custody

OUT_DIR = Path(__file__).parent
FIXTURE = OUT_DIR / "fixture.json"


@dataclass(frozen=True)
class FakeResponse:
    name: str
    response: str


@dataclass(frozen=True)
class FakePart:
    text: str | None = None
    function_response: FakeResponse | None = None


@dataclass(frozen=True)
class FakeContent:
    parts: list[FakePart]


@dataclass(frozen=True)
class FakeEvent:
    author: str
    invocation_id: str
    content: FakeContent


def retrieval(text: str, invocation: str = "inv-1") -> FakeEvent:
    """A `load_memory` call, returning one piece of text -- mirrors
    `tests/test_graph.py`'s helper of the same name, reimplemented here
    so this falsifier has no dependency on the test suite."""
    part = FakePart(function_response=FakeResponse(name="load_memory", response=text))
    return FakeEvent("assistant", invocation, FakeContent([part]))


def record_for(record_id: str, content: str) -> CustodyRecord:
    return CustodyRecord(
        origin=Origin.MODEL,
        trust=Trust.TRUSTED,
        author="assistant",
        invocation_id=f"inv-{record_id}",
        content_sha256=digest(content),
        source_tool="crm_lookup",
        source_revision=None,
        id=record_id,
        derived_from=(),
    )


def main() -> dict:
    fixture = json.loads(FIXTURE.read_text())
    submitted_fact = fixture["submitted_fact"]
    retrieved_facts = fixture["retrieved_facts"]

    # The retrieved_facts entry that is NOT byte-identical to submitted_fact
    # -- this is the real paraphrase Memory Bank actually produced.
    paraphrased = next((f for f in retrieved_facts if f != submitted_fact), None)
    assert paraphrased is not None, (
        "fixture's retrieved_facts contained no paraphrase of submitted_fact; "
        "this falsifier requires the real divergence to exist in the fixture"
    )

    graph = CustodyGraph()
    graph.add(record_for("original-1", submitted_fact))

    paraphrase_result = take_custody(
        [retrieval(paraphrased)], resolver=graph
    )
    (paraphrase_admitted,) = paraphrase_result.admitted

    exact_match_result = take_custody(
        [retrieval(submitted_fact)], resolver=graph
    )
    (exact_match_admitted,) = exact_match_result.admitted

    paraphrase_trust = paraphrase_admitted.record.trust
    paraphrase_derived_from = paraphrase_admitted.record.derived_from
    exact_trust = exact_match_admitted.record.trust
    exact_derived_from = exact_match_admitted.record.derived_from

    # H1: paraphrase resolves TRUSTED anyway (the TCB doc's feared direction).
    h1_confirmed = paraphrase_trust is Trust.TRUSTED
    # H2: paraphrase falls through to the same default-deny path an
    # unrelated, never-before-seen retrieval takes.
    h2_confirmed = (
        paraphrase_trust is Trust.UNTRUSTED and paraphrase_derived_from == ()
    )
    control_valid = (
        exact_trust is Trust.TRUSTED and exact_derived_from == ("original-1",)
    )

    return {
        "fixture_source": fixture["source"],
        "submitted_fact": submitted_fact,
        "paraphrased_retrieved_fact": paraphrased,
        "paraphrase_result": {
            "trust": paraphrase_trust.value,
            "derived_from": list(paraphrase_derived_from),
        },
        "exact_match_control_result": {
            "trust": exact_trust.value,
            "derived_from": list(exact_derived_from),
        },
        "control_valid": control_valid,
        "h1_confirmed_silent_false_trust": h1_confirmed,
        "h2_confirmed_safe_fail_closed": h2_confirmed,
    }


if __name__ == "__main__":
    result = main()
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2))

    print(f"submitted_fact:          {result['submitted_fact']!r}")
    print(f"paraphrased retrieval:   {result['paraphrased_retrieved_fact']!r}")
    print()
    print(f"paraphrase -> trust:        {result['paraphrase_result']['trust']}")
    print(f"paraphrase -> derived_from: {result['paraphrase_result']['derived_from']}")
    print()
    print(f"control    -> trust:        {result['exact_match_control_result']['trust']}")
    print(f"control    -> derived_from: {result['exact_match_control_result']['derived_from']}")
    print()
    print(f"control valid (resolver mechanism itself works): {result['control_valid']}")
    print(f"H1 confirmed (silent false trust, matches TCB doc's fear): {result['h1_confirmed_silent_false_trust']}")
    print(f"H2 confirmed (safe fail-closed):                           {result['h2_confirmed_safe_fail_closed']}")
