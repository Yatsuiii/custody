"""Loads the falsifier's verified `decisions.jsonl` into the Stage 1 domain
model — BUILD_SCOPE.md Stage 2. Read-only against the frozen falsifier
data; never writes to `decision-trace/data/`.

Every `Evidence.quote` written here is copied verbatim from the source
record's `rationale_quote` or title field — nothing is paraphrased or
invented, preserving the falsifier's own verification discipline
(`mine_decisions.pick_quote()`) into the product's data.

Two source shapes, mirroring the two mining channels:

- `revert_pair`: becomes TWO Decisions — the original (now IMPLEMENTED,
  since it did exist in the repo before being reverted) and the revert
  record (REVERTED, carrying the rationale quote), linked by a REVERTS
  edge. This is the same shape Stage 1's hardcoded test used for the k8s
  delayed-preemption case; this loader applies it to every source row.
- `kep_alternatives`: becomes ONE Decision (ACCEPTED — a design choice was
  made; the falsifier data doesn't capture whether it was later revisited,
  so no supersession edge is invented). `rejected_alternatives` is left
  empty rather than reusing the mined `rejected` field's boilerplate
  placeholder text ("see rationale_quote...") as if it were a real
  alternative's name — that field only exists for the revert-pair shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from models import Decision, DecisionStatus, Evidence, RelationshipType


def _load_records(decisions_jsonl: Path) -> list[dict]:
    return [json.loads(line) for line in decisions_jsonl.open()]


def _revert_pair_to_decisions(record: dict) -> list[Decision]:
    original_pr = record["citation"]["original_pr"]
    revert_pr = record["citation"]["revert_pr"]
    original_id = f"{record['repo']}-pr-{original_pr['number']}"
    revert_id = f"{record['repo']}-pr-{revert_pr['number']}"

    original = Decision(
        id=original_id,
        subject=record["chosen"],
        current_status=DecisionStatus.IMPLEMENTED,
        chosen_approach=record["chosen"],
        introduced_at=record.get("date"),
        evidence=[Evidence(type="pr", url=original_pr["url"], quote=record["chosen"])],
    )
    revert = Decision(
        id=revert_id,
        subject=record["rejected"],
        current_status=DecisionStatus.REVERTED,
        rationale=record["rationale_quote"],
        evidence=[Evidence(
            type="revert_pr", url=revert_pr["url"], quote=record["rationale_quote"],
        )],
        related_decisions=[(original_id, RelationshipType.REVERTS)],
    )
    return [original, revert]


def _kep_alternatives_to_decision(record: dict) -> Decision:
    file_citation = record["citation"]["file"]
    return Decision(
        id=record["decision_id"],
        subject=record["chosen"],
        current_status=DecisionStatus.ACCEPTED,
        context=record.get("context"),
        chosen_approach=record["chosen"],
        rationale=record["rationale_quote"],
        evidence=[Evidence(
            type="proposal", url=file_citation["url"], quote=record["rationale_quote"],
        )],
    )


def load_decisions(decisions_jsonl: Path) -> list[Decision]:
    decisions: list[Decision] = []
    for record in _load_records(decisions_jsonl):
        if record["source"] == "revert_pair":
            decisions.extend(_revert_pair_to_decisions(record))
        elif record["source"] == "kep_alternatives":
            decisions.append(_kep_alternatives_to_decision(record))
        else:
            raise ValueError(f"unknown source type: {record['source']!r}")
    return decisions
