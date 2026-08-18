"""Mines ~20 verified engineering decisions for the DecisionTrace benchmark v0.

Two channels only, chosen because the substrate audit found them reliable
(generic keyword search over issue trackers was noisy and didn't scale):

1. Revert-PR pairs in rust-lang/rust, kubernetes/kubernetes,
   elastic/elasticsearch. A merged PR whose title/body says "revert" and
   references an earlier PR number gives: the original decision, a stated
   rationale (the revert PR's own body — real text, not inferred), a
   citation (both PR numbers), and a supersession fact for free.

2. "Alternatives Considered" sections in kubernetes/enhancements KEPs — a
   structural guarantee in that repo's proposal template, not a search
   artifact.

Every rationale_quote is a contiguous substring of a live-fetched PR/file
body, picked by a keyword-cued sentence match, never model-generated or
paraphrased. A human spot-checks a sample afterward (see SESSION_CONTRACT.md
gate 1/2) but the extraction itself needs no judgment call to be truthful.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from gh_util import gh_json

REVERT_REPOS = [
    "rust-lang/rust",
    "kubernetes/kubernetes",
    "elastic/elasticsearch",
]
PER_REPO_TARGET = 16
KEP_TARGET = 30

DATA_DIR = Path(__file__).parent / "data"
RATIONALE_CUES = re.compile(
    r"\b(decided|because|since|breaks?|regression|causes?|caused|"
    r"in favor of|instead of|reverting because|we chose|too risky|"
    r"rolled? ?back)\b",
    re.IGNORECASE,
)
# Stricter than RATIONALE_CUES: RATIONALE_CUES matches generic words like
# "because"/"since" that fire just as often on prose explaining why the
# CHOSEN design works as on prose rejecting an alternative — a KEP's
# "## Alternatives Considered" section routinely contains both. This tier
# requires explicit rejection/negative framing, so it can't grab a sentence
# that's actually justifying the chosen approach. Used for kep_alternatives
# only (require_rejection=True below); revert_pair mining is unaffected —
# a revert PR body is inherently about undoing something, so the original
# looser cues were never the problem there (94% rationale-match, untouched).
REJECTION_CUES = re.compile(
    r"\b(rejected|ruled out|dismissed|discarded|abandoned|"
    r"not (?:used|chosen|preferred|selected|followed|supported)|"
    r"chose not to|decided against|considered but|too (?:risky|complex|"
    r"difficult|intricate)|we chose not|not preferred to|"
    r"was not (?:the )?(?:chosen|preferred|used)|disadvantages?)\b",
    re.IGNORECASE,
)
MARKDOWN_HEADER_LINE = re.compile(r"^#{1,6}\s.*$", re.MULTILINE)
REVERT_REF = re.compile(
    r"revert(?:s|ed|ing)?\s*(?:of\s*)?(?:[\w.-]+/[\w.-]+)?#(\d+)", re.IGNORECASE
)


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    return re.split(r"(?<=[.!?])\s+", text)


BOILERPLATE = re.compile(r"^(r\?|@rustbot|@bors|cc @|ping @)", re.IGNORECASE)
URL = re.compile(r"https?://\S+")


def _is_url_junk(s: str) -> bool:
    stripped = URL.sub("", s)
    return len(stripped.strip()) < 25


def pick_quote(
    body: str, max_len: int = 320, require_rejection: bool = False
) -> tuple[str, bool] | None:
    """Returns (quote, has_rationale_cue). Only a cue-bearing sentence is
    accepted — a fallback longest-sentence was tried earlier and produced
    too much boilerplate (zulip links, "cc @x") to trust as a rationale.

    require_rejection=True uses REJECTION_CUES instead of the looser
    RATIONALE_CUES, so the picked sentence must actually be about an
    alternative being rejected, not just contain "because"/"since" —
    see REJECTION_CUES' docstring-comment for why this matters for KEPs."""
    if require_rejection:
        # ATX headers ("### Alternative: X") have no sentence-ending
        # punctuation, so sentences()'s whitespace-collapse glues the raw
        # header label onto whatever prose follows it, contaminating the
        # first candidate sentence in every subsection. Strip header lines
        # first so only real prose is split into candidates. Only applied
        # here, not the default path, so revert_pair mining (PR bodies,
        # essentially never headered) is byte-identical to before.
        body = MARKDOWN_HEADER_LINE.sub("", body or "")
    cands = [
        s.strip() for s in sentences(body)
        if not BOILERPLATE.match(s.strip()) and not _is_url_junk(s)
    ]
    cues = REJECTION_CUES if require_rejection else RATIONALE_CUES
    for s in cands:
        if cues.search(s) and 25 < len(s) <= max_len:
            return s, True
    return None


ALTERNATIVES_SECTION_RE = re.compile(
    r"##\s*Alternatives(?: Considered)?\s*\n(.*?)(?:\n##\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def extract_alternatives_section(text: str) -> str | None:
    """Pulls just the '## Alternatives Considered' section out of a raw KEP
    file. Shared by mine_keps() (for rationale_quote extraction) and the
    rationale_card backfill, so both always look at the same section rather
    than one seeing the extracted section and the other re-fetching and
    truncating the whole multi-thousand-word file, which for long KEPs cuts
    the Alternatives section off entirely before it reaches the model."""
    m = ALTERNATIVES_SECTION_RE.search(text)
    return m.group(1).strip() if m else None


CARD_PROMPT = """A real DecisionTrace record distills a discussion into a \
short, structured card rather than pasting a raw quote from it. Read the \
source document below, which explains a real engineering decision: "{chosen}" \
is the option that was ultimately used. Write ONE sentence (max 200 \
characters), in your own words, stating the key reasoning the document gives \
for that outcome — whether that means "{chosen}" itself was later reverted/\
rejected, or an alternative to it was rejected in its favor. Paraphrase the \
reasoning; do not copy any contiguous phrase of more than a few words \
verbatim from the source. Output only the sentence, no preamble.

SOURCE DOCUMENT
{document}"""


def distill_rationale_card(chosen: str, document: str) -> str:
    """Abstractive one-line rationale for a decision, generated from the
    full source document (never from rationale_quote itself, so the model
    has no verbatim string to fall back on copying)."""
    import vertex

    prompt = CARD_PROMPT.format(chosen=chosen, document=document[:8000])
    return vertex.generate(prompt).strip().strip('"')


CARD_PROMPT_MULTI = """A real DecisionTrace record distills a discussion \
into a short, structured card rather than pasting a raw quote from it. \
Read the source document below, which explains a real engineering \
decision: "{chosen}" is the option that was ultimately used.

Some documents like this discuss only one alternative that was rejected in \
favor of "{chosen}"; others discuss several genuinely distinct \
alternatives, each rejected for its own reason. Look for how many DISTINCT \
rejected alternatives the document actually names.

- If there is only one, write ONE sentence (max 200 characters) stating, \
in your own words, the key reasoning.
- If there are multiple distinct ones, write one short sentence per \
alternative (max 150 characters each, up to 6), each on its own line \
starting with "- ", naming the alternative and its specific reason for \
rejection. List every genuinely distinct alternative the document names, \
even minor ones — do not stop early or merge separate alternatives into \
one generic sentence.

In both cases: paraphrase the reasoning; do not copy any contiguous phrase \
of more than a few words verbatim from the source. Output only the \
sentence(s), no preamble, no summary line above or below them.

SOURCE DOCUMENT
{document}"""


def distill_rationale_card_multi(chosen: str, document: str) -> str:
    """Like distill_rationale_card, but allowed to cover multiple distinct
    rejected alternatives as separate short points instead of collapsing a
    multi-alternative section into one lossy sentence. Exists because a
    one-sentence card is structurally unable to represent a KEP's
    Alternatives Considered section when that section discusses more than
    one alternative — the model has to pick which one to lead with, and
    that pick won't reliably match whichever single sentence
    pick_quote() happened to extract as ground truth. See the
    'Multi-point rationale cards' session contract entry for the diagnosis."""
    import vertex

    prompt = CARD_PROMPT_MULTI.format(chosen=chosen, document=document[:8000])
    return vertex.generate(prompt).strip().strip('"')


def mine_reverts(repo: str, target: int) -> list[dict]:
    found: list[dict] = []
    search = gh_json(
        "api", "-X", "GET", "search/issues",
        "-f", f"q=repo:{repo} is:pr is:merged revert in:title",
        "-f", "per_page=100",
    )
    items = search.get("items", []) if isinstance(search, dict) else []
    for item in items:
        if len(found) >= target:
            break
        revert_num = item["number"]
        try:
            revert_pr = gh_json(
                "pr", "view", str(revert_num), "--repo", repo,
                "--json", "number,title,body,mergedAt,url",
            )
        except subprocess.CalledProcessError:
            continue
        if not revert_pr.get("mergedAt"):
            continue
        m = REVERT_REF.search(f"{revert_pr['title']} {revert_pr['body'] or ''}")
        if not m:
            continue
        original_num = int(m.group(1))
        picked = pick_quote(revert_pr["body"] or "")
        if not picked:
            continue
        quote, has_cue = picked
        try:
            original_pr = gh_json(
                "pr", "view", str(original_num), "--repo", repo,
                "--json", "number,title,body,mergedAt,url",
            )
        except subprocess.CalledProcessError:
            continue
        found.append({
            "repo": repo,
            "decision_id": f"{repo.replace('/', '-')}-revert-{original_num}",
            "source": "revert_pair",
            "chosen": original_pr["title"],
            "rejected": f"reverted in #{revert_num}: {revert_pr['title']}",
            "rationale_quote": quote,
            "quote_has_rationale_cue": has_cue,
            "citation": {
                "original_pr": {"number": original_num, "url": original_pr["url"]},
                "revert_pr": {"number": revert_num, "url": revert_pr["url"]},
            },
            "superseded_by": revert_num,
            "date": original_pr.get("mergedAt"),
            "context": original_pr["title"],
        })
    return found


def mine_keps(target: int) -> list[dict]:
    found: list[dict] = []
    repo = "kubernetes/enhancements"
    results = gh_json(
        "search", "code", "Alternatives Considered",
        "--repo", repo, "--extension", "md", "--limit", "100",
        "--json", "path,url",
    )
    for item in results:
        if len(found) >= target:
            break
        path = item["path"]
        try:
            content = gh_json("api", f"repos/{repo}/contents/{path}")
        except subprocess.CalledProcessError:
            continue
        if not isinstance(content, dict) or "content" not in content:
            continue
        import base64
        try:
            text = base64.b64decode(content["content"]).decode("utf-8", errors="ignore")
        except Exception:
            continue
        alt_section = extract_alternatives_section(text)
        if alt_section is None:
            continue
        picked = pick_quote(alt_section, require_rejection=True)
        if not picked:
            continue
        quote, has_cue = picked
        title_m = re.search(r"^#\s*(.+)$", text, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else path
        kep_slug = path.replace("/README.md", "").replace("/", "-")
        found.append({
            "repo": repo,
            "decision_id": f"kep-{kep_slug}",
            "source": "kep_alternatives",
            "chosen": title,
            "rejected": "see rationale_quote (alternatives section)",
            "rationale_quote": quote,
            "quote_has_rationale_cue": has_cue,
            "citation": {
                "file": {
                    "path": path,
                    "url": f"https://github.com/{repo}/blob/master/{path}",
                }
            },
            "superseded_by": None,
            "date": None,
            "context": title,
        })
    return found


def main() -> None:
    import sys

    decisions: list[dict] = []
    for repo in REVERT_REPOS:
        decisions.extend(mine_reverts(repo, PER_REPO_TARGET))
    decisions.extend(mine_keps(KEP_TARGET))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_name = sys.argv[1] if len(sys.argv) > 1 else "decisions.jsonl"
    out_path = DATA_DIR / out_name
    with out_path.open("w") as f:
        for d in decisions:
            f.write(json.dumps(d) + "\n")
    print(f"wrote {len(decisions)} decisions to {out_path}")


if __name__ == "__main__":
    main()
