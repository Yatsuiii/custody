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


def pick_quote(body: str, max_len: int = 320) -> tuple[str, bool] | None:
    """Returns (quote, has_rationale_cue). Only a cue-bearing sentence is
    accepted — a fallback longest-sentence was tried earlier and produced
    too much boilerplate (zulip links, "cc @x") to trust as a rationale."""
    cands = [
        s.strip() for s in sentences(body)
        if not BOILERPLATE.match(s.strip()) and not _is_url_junk(s)
    ]
    for s in cands:
        if RATIONALE_CUES.search(s) and 25 < len(s) <= max_len:
            return s, True
    return None


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
        m = re.search(
            r"##\s*Alternatives(?: Considered)?\s*\n(.*?)(?:\n##\s|\Z)",
            text, re.IGNORECASE | re.DOTALL,
        )
        if not m:
            continue
        alt_section = m.group(1).strip()
        picked = pick_quote(alt_section)
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
