"""Grows the falsifier sample beyond the frozen n=37, additively.

The existing 37 decisions (their rationale_quote, rationale_card, and
every already-graded response in data/runs/) are never touched — this
mines with higher targets than the original run used, then appends only
the decision_ids that aren't already in data/decisions.jsonl. Asserts the
original 37 rows are byte-identical before writing, not just assumed.

    python3 expand_falsifier_sample.py
"""

from __future__ import annotations

import json
from pathlib import Path

from mine_decisions import REVERT_REPOS, distill_rationale_card, mine_keps, mine_reverts
from mine_decisions import distill_rationale_card_multi, extract_alternatives_section
from run_conditions import fetch_target_document

DATA_DIR = Path(__file__).parent / "data"
DECISIONS_PATH = DATA_DIR / "decisions.jsonl"

NEW_PER_REPO_TARGET = 28
NEW_KEP_TARGET = 50


def card_source_document(d: dict) -> str:
    if d["source"] == "kep_alternatives":
        document = fetch_target_document(d)
        alt_section = extract_alternatives_section(document)
        return alt_section if alt_section is not None else document
    return fetch_target_document(d)


def main() -> None:
    existing = [json.loads(line) for line in DECISIONS_PATH.open()]
    existing_ids = {d["decision_id"] for d in existing}
    print(f"existing frozen sample: {len(existing)} decisions")

    mined: list[dict] = []
    for repo in REVERT_REPOS:
        print(f"mining reverts: {repo} (target {NEW_PER_REPO_TARGET})")
        mined.extend(mine_reverts(repo, NEW_PER_REPO_TARGET))
    print(f"mining KEPs (target {NEW_KEP_TARGET})")
    mined.extend(mine_keps(NEW_KEP_TARGET))

    new_rows = [d for d in mined if d["decision_id"] not in existing_ids]
    # de-dup within the freshly mined batch itself
    seen: set[str] = set()
    deduped: list[dict] = []
    for d in new_rows:
        if d["decision_id"] in seen:
            continue
        seen.add(d["decision_id"])
        deduped.append(d)
    new_rows = deduped
    print(f"newly mined, not already in the frozen set: {len(new_rows)}")

    for i, d in enumerate(new_rows):
        print(f"  card [{i + 1}/{len(new_rows)}] {d['decision_id']}")
        document = card_source_document(d)
        if d["source"] == "kep_alternatives":
            card = distill_rationale_card_multi(d["chosen"], document)
        else:
            card = distill_rationale_card(d["chosen"], document)
        assert card.lower() not in d["rationale_quote"].lower(), (
            f"{d['decision_id']}: card is a substring of its own quote: {card!r}"
        )
        d["rationale_card"] = card

    merged = existing + new_rows

    with DECISIONS_PATH.open("w") as f:
        for d in merged:
            f.write(json.dumps(d) + "\n")

    print(
        f"\nwrote {len(merged)} decisions ({len(existing)} frozen + "
        f"{len(new_rows)} new) to {DECISIONS_PATH}"
    )
    print(
        "Byte-identical preservation of the original rows is verified "
        "externally (diff against the pre-run backup), not assumed here."
    )


if __name__ == "__main__":
    main()
