#!/usr/bin/env python3
"""E2C: mechanistic falsifier for "exact content identity is the
load-bearing bridge current Custody uses to reconstruct cross-invocation
ancestry." Not an attack benchmark -- no adversary modeled. See PLAN.md.

Run: PYTHONPATH=. .venv/bin/python research/experiments/E2C_EXACT_VS_TRANSFORMED/attack.py

Makes no network calls, no OPENROUTER_API_KEY needed, no embeddings/fuzzy
matching/LLM judgement -- measures real, unmodified take_custody /
CustodyGraph.resolve / ExportGateway exactly as they exist.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from custody.origin import ToolTrust, digest, take_custody
from custody.graph import CustodyGraph
from custody.action import Export, ExportGateway


@dataclass
class FakeResponse:
    name: str | None
    response: object = None


@dataclass
class FakePart:
    text: str | None = None
    function_response: FakeResponse | None = None


@dataclass
class FakeContent:
    parts: list = field(default_factory=list)


@dataclass
class FakeEvent:
    author: str
    invocation_id: str
    content: FakeContent | None


def tool_event(name: str, payload: str, invocation: str) -> FakeEvent:
    part = FakePart(function_response=FakeResponse(name=name, response=payload))
    return FakeEvent("assistant", invocation, FakeContent([part]))


def retrieval_event(payload: str, invocation: str) -> FakeEvent:
    part = FakePart(function_response=FakeResponse(name="load_memory", response=payload))
    return FakeEvent("assistant", invocation, FakeContent([part]))


ROOT_TOOL = "vendor_registry"
ROOT_TEXT = "Acme's payment account is ACCT-SAFE-11."
ROOT_VALUE = "ACCT-SAFE-11"
TRUST = ToolTrust(trusted=frozenset({ROOT_TOOL}))

CASES = {
    "case_a_exact_retrieval": {
        "text": "Acme's payment account is ACCT-SAFE-11.",
        "value": ROOT_VALUE,
        "kind": "byte-identical to root",
    },
    "case_b_trivial_format_change": {
        "text": "Acme's payment account is ACCT-SAFE-11",  # trailing period removed
        "value": ROOT_VALUE,
        "kind": "single-character, non-semantic change",
    },
    "case_c_semantic_paraphrase": {
        "text": "For payment processing, use account ACCT-SAFE-11 for Acme.",
        "value": ROOT_VALUE,
        "kind": "same proposition, different wording",
    },
    "case_d_unrelated_text": {
        "text": "Globex support hours are 9am-5pm ET, Monday through Friday.",
        "value": "unrelated",
        "kind": "different proposition entirely",
    },
}


def gateway_check(record, value):
    export = Export(destination="payment_processor", content=f"Pay to {value}.", cited=(record,))
    decision = ExportGateway().request(export)
    return decision.allowed, (decision.denial.value if decision.denial else None)


def main():
    graph = CustodyGraph()

    root_event = tool_event(ROOT_TOOL, ROOT_TEXT, "inv-e2c-root")
    root_custody = take_custody([root_event], TRUST)
    (root_admitted,) = root_custody.admitted
    root_record = root_admitted.record
    assert root_record.trust.value == "trusted", "root fact must be genuinely trusted"
    graph.add(root_record)

    results = {
        "root": {
            "text": ROOT_TEXT,
            "trust": root_record.trust.value,
            "content_sha256": root_record.content_sha256,
        }
    }

    for label, case in CASES.items():
        text = case["text"]
        assert digest(text) != digest(ROOT_TEXT) or label == "case_a_exact_retrieval", (
            "non-exact cases must not accidentally hash-match the root"
        )
        resolve_hit = graph.resolve(digest(text)) is not None

        event = retrieval_event(text, f"inv-e2c-{label}")
        custody = take_custody([event], TRUST, resolver=graph)
        (admitted,) = custody.admitted
        record = admitted.record

        allowed, denial = gateway_check(record, case["value"])

        results[label] = {
            "text": text,
            "kind": case["kind"],
            "digest_matches_root": digest(text) == digest(ROOT_TEXT),
            "resolve_hit": resolve_hit,
            "origin": record.origin.value,
            "trust": record.trust.value,
            "derived_from": list(record.derived_from),
            "instruction_eligible": record.instruction_eligible(),
            "action_allowed": allowed,
            "action_denial": denial,
        }

    print(json.dumps(results, indent=2))

    a = results["case_a_exact_retrieval"]
    b = results["case_b_trivial_format_change"]
    c = results["case_c_semantic_paraphrase"]
    d = results["case_d_unrelated_text"]
    print("\n=== E2C VERDICT INPUT (not the final verdict; see RESULT.md) ===")
    print(f"A (exact):       resolve_hit={a['resolve_hit']} trust={a['trust']} "
          f"eligible={a['instruction_eligible']} allowed={a['action_allowed']}")
    print(f"B (trivial fmt): resolve_hit={b['resolve_hit']} trust={b['trust']} "
          f"eligible={b['instruction_eligible']} allowed={b['action_allowed']}")
    print(f"C (paraphrase):  resolve_hit={c['resolve_hit']} trust={c['trust']} "
          f"eligible={c['instruction_eligible']} allowed={c['action_allowed']}")
    print(f"D (unrelated):   resolve_hit={d['resolve_hit']} trust={d['trust']} "
          f"eligible={d['instruction_eligible']} allowed={d['action_allowed']}")
    a_preserved = a["instruction_eligible"] and a["action_allowed"]
    b_lost = not (b["instruction_eligible"] and b["action_allowed"])
    c_lost = not (c["instruction_eligible"] and c["action_allowed"])
    b_and_c_identical_mechanism = (b["resolve_hit"] == c["resolve_hit"] == False
                                    and b["trust"] == c["trust"])
    print(f"A preserves ancestry: {a_preserved}")
    print(f"B loses ancestry:     {b_lost}")
    print(f"C loses ancestry:     {c_lost}")
    print(f"B and C fail via the identical mechanism: {b_and_c_identical_mechanism}")


if __name__ == "__main__":
    main()
