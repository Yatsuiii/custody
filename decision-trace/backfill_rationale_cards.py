"""One-off backfill: adds `rationale_card` to every row of data/decisions.jsonl
without re-mining (re-running mine_decisions.py against live search results
could change which 37 decisions are in the set; this only enriches the
existing frozen rows).

Fetches each decision's already-cited source document (same fetch used by
run_conditions.fetch_target_document) and asks Gemini to distill a one-line,
paraphrased rationale from it (mine_decisions.distill_rationale_card).
Asserts the distilled card is not a substring of rationale_quote before
writing, per docs/FALSIFIER_CONFOUND_HANDOFF.md section 4.1.
"""

from __future__ import annotations

import json
from pathlib import Path

from mine_decisions import (
    distill_rationale_card,
    distill_rationale_card_multi,
    extract_alternatives_section,
)
from run_conditions import fetch_target_document

DATA_DIR = Path(__file__).parent / "data"
DECISIONS_PATH = DATA_DIR / "decisions.jsonl"


def card_source_document(d: dict) -> str:
    """The text actually handed to distill_rationale_card. For KEPs this
    must be the '## Alternatives Considered' section specifically, not the
    raw multi-thousand-word file — mine_keps() only ever extracted
    rationale_quote from that section, and the raw file's first 8000 chars
    (distill_rationale_card's truncation limit) frequently don't reach it,
    which silently fed the model the wrong part of the document."""
    if d["source"] == "kep_alternatives":
        document = fetch_target_document(d)
        alt_section = extract_alternatives_section(document)
        if alt_section is not None:
            return alt_section
        return document
    return fetch_target_document(d)


def main(regenerate_source: str | None = None) -> None:
    """regenerate_source: if given (e.g. 'kep_alternatives'), force-
    regenerate every row of that source uniformly, even if it already has
    a rationale_card — applying an improved method to the whole affected
    population rather than cherry-picking rows after seeing their scores.
    Rows of other sources are still only backfilled if missing a card."""
    decisions = [json.loads(line) for line in DECISIONS_PATH.open()]

    for i, d in enumerate(decisions):
        needs_card = "rationale_card" not in d
        force = regenerate_source is not None and d["source"] == regenerate_source
        if not needs_card and not force:
            continue
        print(f"[{i + 1}/{len(decisions)}] {d['decision_id']}")
        document = card_source_document(d)
        if d["source"] == "kep_alternatives":
            card = distill_rationale_card_multi(d["chosen"], document)
        else:
            card = distill_rationale_card(d["chosen"], document)
        assert card.lower() not in d["rationale_quote"].lower(), (
            f"{d['decision_id']}: distilled card is a substring of "
            f"rationale_quote, rejects the point of distillation: {card!r}"
        )
        d["rationale_card"] = card

    with DECISIONS_PATH.open("w") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")
    print(f"wrote {len(decisions)} decisions with rationale_card to {DECISIONS_PATH}")


if __name__ == "__main__":
    import sys

    source_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(regenerate_source=source_arg)
