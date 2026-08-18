"""One-off: re-extracts rationale_quote for the existing 19 kep_alternatives
rows using the stricter REJECTION_CUES tier (require_rejection=True), in
place of the original looser RATIONALE_CUES pick.

Does NOT re-mine (no new GitHub search) — same 19 decision_ids, same
already-cited file, same '## Alternatives Considered' section text. Only
which sentence within that section counts as the ground-truth quote can
change. See mine_decisions.REJECTION_CUES for why the original pick was
frequently grabbing a sentence about the chosen design rather than a
rejected alternative for this document type.

Applied uniformly to all 19 rows, not cherry-picked to the ones that
previously failed grading — same anti-p-hacking discipline as every prior
fix in this project.
"""

from __future__ import annotations

import json
from pathlib import Path

from mine_decisions import extract_alternatives_section, pick_quote
from run_conditions import fetch_target_document

DATA_DIR = Path(__file__).parent / "data"
DECISIONS_PATH = DATA_DIR / "decisions.jsonl"


def main() -> None:
    decisions = [json.loads(line) for line in DECISIONS_PATH.open()]
    changed = 0
    unchanged = 0
    no_pick = []

    for i, d in enumerate(decisions):
        if d["source"] != "kep_alternatives":
            continue
        print(f"[{i + 1}/{len(decisions)}] {d['decision_id']}")
        document = fetch_target_document(d)
        alt_section = extract_alternatives_section(document)
        if alt_section is None:
            no_pick.append(d["decision_id"])
            continue
        picked = pick_quote(alt_section, require_rejection=True)
        if picked is None:
            no_pick.append(d["decision_id"])
            continue
        quote, has_cue = picked
        assert d["rationale_card"].lower() not in quote.lower(), (
            f"{d['decision_id']}: existing rationale_card is a substring "
            f"of the newly re-extracted rationale_quote: {quote!r}"
        )
        if quote != d["rationale_quote"]:
            print(f"  OLD: {d['rationale_quote'][:100]!r}")
            print(f"  NEW: {quote[:100]!r}")
            changed += 1
        else:
            unchanged += 1
        d["rationale_quote"] = quote
        d["quote_has_rationale_cue"] = has_cue

    with DECISIONS_PATH.open("w") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")
    print(
        f"\ndone: {changed} quotes changed, {unchanged} unchanged, "
        f"{len(no_pick)} could not find any rejection-cue sentence: {no_pick}"
    )


if __name__ == "__main__":
    main()
