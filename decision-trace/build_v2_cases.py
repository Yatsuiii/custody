"""Derives the v2 benchmark cases from live source documents.

v0 asked one broad question per KEP ("what alternatives were considered?")
and graded it against one arbitrarily-selected sentence. v2 asks one
targeted question per named alternative and grades it against that
alternative's own disposition span. See BENCHMARK_V2_SPEC.md for why, and
BENCHMARK_FAILURE_AUDIT.md for the evidence that forced it.

No model is in the loop here: every field is either copied from the frozen
v0 decision row or is a verbatim span of the live source. Rules V1-V6 are
fixed by the spec and applied uniformly, before any score exists.

Writes data/v2/cases.jsonl and data/v2/exclusions.json, and prints the
structural report that gates Vertex spend.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from run_conditions import fetch_target_document, load_decisions

DATA_DIR = Path(__file__).parent / "data"
V2_DIR = DATA_DIR / "v2"
SOURCES_DIR = V2_DIR / "sources"
MAX_EVIDENCE = 1200
MIN_EVIDENCE = 40

FENCE = re.compile(r"^(?:```|~~~)", re.MULTILINE)
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
ALT_TITLE = re.compile(r"^alternatives?(\s+considered)?$", re.IGNORECASE)
BULLET = re.compile(r"^[ \t]{0,1}[-*][ \t]+(.+?)[ \t]*$", re.MULTILINE)
ENUM_PREFIX = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:rejected\s+)?(?:alternative\s*:\s*)?", re.IGNORECASE
)
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
URL = re.compile(r"https?://\S+")

META_NAME = re.compile(
    r"^((detailed\s+)?(comparison|analysis)|summary|table|notes?|"
    r"references?|see also|open questions?|background|goals?|non-goals?|"
    r"related)\b",
    re.IGNORECASE,
)
# An alternative is named by a noun phrase for an option. A heading that is
# a question, or whose head noun is a meta word, is a discussion topic or a
# group label: KEP-5501's Alternatives section is written as a design FAQ
# ("How should outdated messages be handled?") and KEP-3488 groups its real
# options under "Type checking alternatives". Neither can be substituted
# into "was X considered, and why wasn't it adopted?" and yield a sensible
# question, so neither becomes a case.
META_HEAD_NOUN = frozenset({
    "alternative", "alternatives", "consideration", "considerations",
    "considered", "criteria", "criterion", "analysis", "justification",
    "comparison", "summary", "notes", "note", "question", "questions",
    "options", "overview",
})
# Headings that are a *part of* an alternative's write-up rather than an
# alternative themselves. A KEP that gives each alternative its own
# `#### Disadvantages` heading must not turn "Disadvantages" into a case.
PART_NAME = re.compile(
    r"^(advantages?|disadvantages?|pros|cons|drawbacks?|description|"
    r"why[ \t]+(rejected|not)|notes?|summary|examples?)\b",
    re.IGNORECASE,
)
# A labelled "why this was not taken" sub-part. v0's ground truth broke by
# splitting such a bullet at its first period and keeping the lead-in
# clause; taking the whole labelled part instead makes that impossible.
DISPOSITION_LABEL = re.compile(
    r"^[ \t]*(?:[-*+][ \t]*)?\**[ \t]*"
    r"(?:why[ \t]+(?:rejected|not(?:[ \t]+chosen)?)|disadvantages?|cons|"
    r"drawbacks?|reasons?[ \t]+for[ \t]+reject\w*)\b",
    re.IGNORECASE | re.MULTILINE,
)
# Sibling labels that end a disposition part.
PART_LABEL = re.compile(
    r"^[ \t]*(?:[-*+][ \t]*)?\**[ \t]*"
    r"(?:advantages?|pros|description|summary|why[ \t]+rejected|"
    r"disadvantages?|cons|drawbacks?|notes?)\b",
    re.IGNORECASE | re.MULTILINE,
)


def fence_spans(text: str) -> list[tuple[int, int]]:
    spans, open_at = [], None
    for m in FENCE.finditer(text):
        if open_at is None:
            open_at = m.start()
        else:
            spans.append((open_at, m.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def headings(text: str) -> list[tuple[int, int, str, int]]:
    """(offset, level, title, body_start) for real headings only.

    Fence-aware: a `# comment` line inside a code block is not a heading.
    Without this, KEP-3488 appears to have a 15K over-capture it does not
    have, and the audit would chase a defect that is not there."""
    fences = fence_spans(text)
    return [
        (m.start(), len(m.group(1)), m.group(2).strip(), m.end())
        for m in HEADING.finditer(text)
        if not any(a <= m.start() < b for a, b in fences)
    ]


def section_span(text: str, hs: list, i: int) -> tuple[int, int]:
    """Extent of heading i: to the next heading of the same or shallower
    level. v0 terminated at the next `##` regardless of where it started,
    which over-ran by 6914 characters on KEP-1205."""
    _, lvl, _, body_start = hs[i]
    for j in range(i + 1, len(hs)):
        if hs[j][1] <= lvl:
            return body_start, hs[j][0]
    return body_start, len(text)


def canonical_alternatives(text: str):
    """Shallowest heading titled Alternatives / Alternatives Considered."""
    hs = headings(text)
    cands = [i for i, h in enumerate(hs) if ALT_TITLE.match(h[2])]
    if not cands:
        return None
    best = min(cands, key=lambda i: (hs[i][1], hs[i][0]))
    s, e = section_span(text, hs, best)
    return best, hs[best][1], s, e


def named_alternatives(text: str) -> list[tuple[str, str]]:
    """(name, body) per named alternative: the *leaf-most* non-part headings
    inside the canonical Alternatives section.

    Leaf-most, because KEPs group at different depths. KEP-2876 lists its
    alternatives flat at level 3, while KEP-3488 groups them ("Policy
    definition and configuration separation alternatives") and names the
    real options a level deeper. Taking immediate children would give
    KEP-3488 four group labels instead of its actual alternatives, which is
    precisely the alternative the v0 card lost. A heading whose own name is
    a part label (Advantages, Disadvantages, ...) is not a candidate, so its
    parent stays the alternative and keeps that part in its body.

    Sections written as prose bullets rather than headings yield nothing:
    there the option name and its rationale are fused into one sentence, so
    no name can be extracted without leaking the reason into the query.
    Those KEPs are excluded by document shape, before any score exists."""
    can = canonical_alternatives(text)
    if not can:
        return []
    idx, lvl, s, e = can
    hs = headings(text)
    inside = [j for j in range(idx + 1, len(hs)) if hs[j][0] < e]
    candidates = [
        j for j in inside
        if not PART_NAME.match(clean_name(hs[j][2]))
        and is_option_name(clean_name(hs[j][2]))
    ]
    out = []
    for j in candidates:
        bs, be = section_span(text, hs, j)
        has_child_alternative = any(
            k != j and bs <= hs[k][0] < be for k in candidates
        )
        if has_child_alternative:
            continue
        out.append((hs[j][2], text[bs:be].strip()))
    return out


def clean_name(raw: str) -> str:
    """Heading text as an option name: drop enumeration, an `Alternative:`
    prefix, and markdown that wraps the whole name. Inline backticks are
    kept, since stripping only the leading one turns
    "`/matchRules` subresource" into "/matchRules` subresource"."""
    name = LINK.sub(r"\1", ENUM_PREFIX.sub("", raw)).strip()
    for mark in ("**", "*", "`"):
        while name.startswith(mark) and name.endswith(mark) and len(name) > 2 * len(mark):
            name = name[len(mark):-len(mark)].strip()
    return name


def substantive_len(text: str) -> int:
    return len(URL.sub("", LINK.sub(r"\1", text)).strip())


def is_option_name(name: str) -> bool:
    """Whether a heading names an option rather than a discussion topic."""
    if name.endswith("?") or META_NAME.match(name):
        return False
    words = re.findall(r"[A-Za-z]+", name)
    return bool(words) and words[-1].lower() not in META_HEAD_NOUN


def disposition_span(body: str) -> tuple[str, str]:
    """(verbatim span, tier). 'labelled' when the alternative states its own
    Why-Rejected/Disadvantages part, 'body' when the whole write-up is the
    evidence.

    Deliberately not gated on cue words. Requiring a keyword from a fixed
    list is the exact failure that produced v0's invalid ground truth: it
    drops "so there is not a clear way for this to be implemented" while
    admitting "requests would be rejected once the token expired". The
    document's own structure already carries the disposition, since the
    heading sits under a section titled Alternatives, so the body is
    evidence for why the option was not taken whether or not it happens to
    contain the word "rejected"."""
    m = DISPOSITION_LABEL.search(body)
    if m:
        end = len(body)
        for nxt in PART_LABEL.finditer(body, m.end()):
            end = nxt.start()
            break
        span, tier = body[m.start():end].strip(), "labelled"
    else:
        span, tier = body.strip(), "body"
    if len(span) > MAX_EVIDENCE:
        cut = span.rfind(". ", 0, MAX_EVIDENCE)
        span = span[:cut + 1] if cut > MIN_EVIDENCE else span[:MAX_EVIDENCE]
    return span, tier


def shares_6gram(a: str, b: str) -> bool:
    wa, wb = a.lower().split(), b.lower().split()
    if len(wa) < 6 or len(wb) < 6:
        return False
    grams = {tuple(wb[i:i + 6]) for i in range(len(wb) - 5)}
    return any(tuple(wa[i:i + 6]) in grams for i in range(len(wa) - 5))


def source_for(d: dict) -> str:
    """Live source, cached under data/v2/sources/ so repeated structural
    runs cost no GitHub calls."""
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    dest = SOURCES_DIR / f"{d['decision_id']}.txt"
    if not dest.exists():
        dest.write_text(fetch_target_document(d))
    return dest.read_text()


def kep_cases(d: dict, source: str) -> tuple[list[dict], list[dict]]:
    cases, dropped = [], []

    def drop(name, reason):
        dropped.append({"decision_id": d["decision_id"], "alternative": name,
                        "reason": reason})

    if canonical_alternatives(source) is None:
        drop(None, "V1_no_canonical_alternatives_section")
        return cases, dropped
    for raw_name, body in named_alternatives(source):
        name = clean_name(raw_name)
        # Short real names like "Rego" and "Expr" are alternatives; what has
        # to go is a heading that is only a link or is empty once markdown
        # is stripped.
        if not is_option_name(name) or substantive_len(name) < 3:
            drop(name, "V3_meta_or_degenerate_name")
            continue
        quote, tier = disposition_span(body)
        if substantive_len(quote) < MIN_EVIDENCE:
            drop(name, "V5_disposition_too_short")
            continue
        if shares_6gram(name, quote):
            drop(name, "V6_name_leaks_rationale")
            continue
        cases.append({
            "case_id": f"{d['decision_id']}::{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:60]}",
            "decision_id": d["decision_id"],
            "repo": d["repo"],
            "source": "kep_alternative",
            "context": d["context"],
            "chosen": d["chosen"],
            "alternative_name": name,
            "evidence_quote": quote,
            "evidence_tier": tier,
            "citation": d["citation"],
            "superseded_by": None,
        })
    return cases, dropped


def revert_case(d: dict) -> dict:
    """Carried over byte-identical from v0: same query inputs, same target.
    Repairing the one revert row that failed would be rewriting a failed
    ground truth, so it is left exactly as it is."""
    return {
        "case_id": d["decision_id"],
        "decision_id": d["decision_id"],
        "repo": d["repo"],
        "source": "revert_pair",
        "context": d["context"],
        "chosen": d["chosen"],
        "alternative_name": d["rejected"],
        "evidence_quote": d["rationale_quote"],
        "evidence_tier": "v0_carryover",
        "citation": d["citation"],
        "superseded_by": d["superseded_by"],
        "reason": d["rationale_card"],
    }


def main() -> None:
    decisions = load_decisions()
    cases, dropped = [], []
    per_kep = {}
    for d in decisions:
        if d["source"] == "revert_pair":
            cases.append(revert_case(d))
            continue
        got, bad = kep_cases(d, source_for(d))
        cases.extend(got)
        dropped.extend(bad)
        per_kep[d["decision_id"]] = len(got)

    V2_DIR.mkdir(parents=True, exist_ok=True)
    with (V2_DIR / "cases.jsonl").open("w") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    (V2_DIR / "exclusions.json").write_text(json.dumps(dropped, indent=1))

    by_source = Counter(c["source"] for c in cases)
    by_tier = Counter(c["evidence_tier"] for c in cases)
    print(f"cases: {len(cases)}  (clusters/decisions: {len({c['decision_id'] for c in cases})})")
    print(f"by source: {dict(by_source)}")
    print(f"by evidence tier: {dict(by_tier)}")
    print(f"excluded alternatives: {len(dropped)} -> {dict(Counter(x['reason'] for x in dropped))}")
    print(f"\nalternatives per KEP (min/median/max): "
          f"{min(per_kep.values())}/"
          f"{sorted(per_kep.values())[len(per_kep) // 2]}/{max(per_kep.values())}")
    for did, n in sorted(per_kep.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>2d}  {did}")

    verified = sum(
        1 for c in cases
        if c["source"] == "revert_pair"
        or re.search(r"\s+".join(re.escape(t) for t in c["evidence_quote"].split()),
                     source_for(next(d for d in decisions
                                     if d["decision_id"] == c["decision_id"])))
    )
    print(f"\nevidence verified verbatim in live source: {verified}/{len(cases)}")


if __name__ == "__main__":
    main()
