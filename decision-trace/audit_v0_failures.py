"""Reproduces the measurements behind BENCHMARK_FAILURE_AUDIT.md.

Every quantitative claim in that document comes from here, so a reader can
re-derive it instead of trusting the prose. Runs offline against the frozen
v0 decisions, the cached sources under data/v2/sources/, and the recorded
runs in data/runs/structured/. No Vertex calls, no GitHub calls.

Reads v0 artifacts; writes nothing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from build_v2_cases import (
    canonical_alternatives,
    headings,
    named_alternatives,
)
from mine_decisions import (
    ALTERNATIVES_SECTION_RE,
    RATIONALE_CUES,
    REJECTION_CUES,
    pick_quote,
)
from run_conditions import RUNS_DIR, load_decisions, split_rationale_points

SOURCES = Path(__file__).parent / "data" / "v2" / "sources"

FAILURES = [
    "elastic-elasticsearch-revert-147071",
    "kep-keps-sig-storage-1979-object-storage-support",
    "kep-keps-sig-auth-1205-bound-service-account-tokens",
    "kep-keps-sig-auth-5681-conditional-authorization",
    "kep-keps-sig-api-machinery-3488-cel-admission-control",
    "kep-keps-sig-api-machinery-2523-consistent-resource-versions-semantics",
    "kep-keps-sig-node-5593-configure-the-max-crashloopbackoff-delay",
    "kep-keps-sig-api-machinery-2876-crd-validation-expression-language",
    "kep-keps-sig-node-6122-configurable-scaling-delay-with-pod-resource-exposure",
]


def flexible(quote: str) -> re.Pattern:
    """Whitespace-tolerant search, since pick_quote() collapses whitespace
    and the stored quote no longer matches the source byte for byte."""
    return re.compile(r"\s+".join(re.escape(t) for t in quote.split()), re.DOTALL)


def matched_heading_level(source: str) -> int:
    """The heading level v0's unanchored regex actually latched onto."""
    m = ALTERNATIVES_SECTION_RE.search(source)
    if not m:
        return 0
    line_start = source.rfind("\n", 0, m.start()) + 1
    line = source[line_start:source.find("\n", m.start())]
    return len(line) - len(line.lstrip("#"))


def report_section_overcapture(keps: list[dict]) -> None:
    print("\n== Defect 1: unanchored ALTERNATIVES_SECTION_RE ==")
    print(f"{'decision_id':56s} {'lvl':>3s} {'captured':>9s} {'true':>7s} {'over':>7s}")
    for d in keps:
        source = (SOURCES / f"{d['decision_id']}.txt").read_text()
        m = ALTERNATIVES_SECTION_RE.search(source)
        can = canonical_alternatives(source)
        if not (m and can):
            continue
        _, _, start, end = can
        lvl = matched_heading_level(source)
        over = len(m.group(1)) - (end - start)
        flag = "  <-- over-captures" if over > 100 else ""
        print(f"{d['decision_id'][:56]:56s} {lvl:>3d} {len(m.group(1)):>9d} "
              f"{end - start:>7d} {over:>7d}{flag}")


def report_stale_quotes(keps: list[dict]) -> None:
    print("\n== Defect 2: reextract_kep_quotes.py keeps the loose quote on no_pick ==")
    stale = []
    for d in keps:
        source = (SOURCES / f"{d['decision_id']}.txt").read_text()
        section = ALTERNATIVES_SECTION_RE.search(source)
        has_rejection = bool(REJECTION_CUES.search(d["rationale_quote"]))
        has_loose = bool(RATIONALE_CUES.search(d["rationale_quote"]))
        repick = pick_quote(section.group(1), require_rejection=True) if section else None
        if not has_rejection:
            stale.append((d["decision_id"], has_loose, repick is None))
    print(f"KEP ground truths with no rejection cue: {len(stale)} of {len(keps)}")
    print(f"  ...all carry a loose RATIONALE_CUES cue: "
          f"{all(s[1] for s in stale)}")
    print(f"  ...all are confirmed no_pick rows: {all(s[2] for s in stale)}")
    for did, _, _ in stale:
        print(f"    {did}")


def report_quote_placement(keps: list[dict]) -> None:
    print("\n== Are the targets inside a real Alternatives section? ==")
    for d in keps:
        source = (SOURCES / f"{d['decision_id']}.txt").read_text()
        can = canonical_alternatives(source)
        hit = flexible(d["rationale_quote"]).search(source)
        if not (can and hit):
            print(f"  UNLOCATABLE  {d['decision_id']}")
            continue
        _, _, start, end = can
        if not start <= hit.start() < end:
            hs = headings(source)
            enclosing = [h for h in hs if h[0] <= hit.start()]
            where = enclosing[-1][2] if enclosing else "?"
            print(f"  OUTSIDE      {d['decision_id'][:56]:56s} -> under {where!r}")


def report_card_vs_source(keps: list[dict]) -> None:
    print("\n== Defect 3: card capacity vs source cardinality ==")
    print(f"{'decision_id':56s} {'nAlt':>5s} {'card':>5s}")
    capped = 0
    for d in keps:
        source = (SOURCES / f"{d['decision_id']}.txt").read_text()
        n_alt = len(named_alternatives(source))
        n_card = len(split_rationale_points(d["rationale_card"]))
        if n_alt > n_card:
            capped += 1
        print(f"{d['decision_id'][:56]:56s} {n_alt:>5d} {n_card:>5d}")
    print(f"KEPs whose card holds fewer points than the source names: {capped}")


def report_generation(byid: dict) -> None:
    """Whether the model dropped a card point it was actually given."""
    print("\n== Was generation ever the bottleneck? ==")
    for did in FAILURES:
        run = json.loads((RUNS_DIR / "structured" / f"{did}.json").read_text())
        own = sum(1 for r in run["retrieved"] if r == did)
        total_points = len(split_rationale_points(byid[did]["rationale_card"]))
        print(f"  {did[:60]:60s} own slots {own}/5, card points {total_points}"
              f"{'  <-- budget evicted a point' if total_points > own else ''}")


def main() -> None:
    decisions = load_decisions()
    byid = {d["decision_id"]: d for d in decisions}
    keps = [d for d in decisions if d["source"] == "kep_alternatives"]
    missing = [d["decision_id"] for d in decisions
               if not (SOURCES / f"{d['decision_id']}.txt").exists()]
    if missing:
        raise SystemExit(f"run build_v2_cases.py first to cache sources: {missing}")

    print(f"v0 decisions: {len(decisions)} ({len(keps)} KEP), "
          f"structured failures audited: {len(FAILURES)}")
    report_section_overcapture(keps)
    report_stale_quotes(keps)
    report_quote_placement(keps)
    report_card_vs_source(keps)
    report_generation(byid)


if __name__ == "__main__":
    main()
