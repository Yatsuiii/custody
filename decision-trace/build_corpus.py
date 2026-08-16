"""Builds decoy corpora for the embedding-RAG condition.

For each repo used in decisions.jsonl, pulls a pool of real merged PRs (or,
for kubernetes/enhancements, other KEP files) so the RAG condition has real
decoys to discriminate against instead of a single-document gimme. The
decision's own citation PRs/files are excluded from its repo's pool.
"""

from __future__ import annotations

import base64
import json
import random
import subprocess
from pathlib import Path
from gh_util import gh_json

DATA_DIR = Path(__file__).parent / "data"
POOL_SIZE = 150
random.seed(20260816)


def own_citation_numbers(decisions: list[dict], repo: str) -> set[int]:
    nums = set()
    for d in decisions:
        if d["repo"] != repo:
            continue
        c = d["citation"]
        if "original_pr" in c:
            nums.add(c["original_pr"]["number"])
            nums.add(c["revert_pr"]["number"])
    return nums


def build_pr_corpus(repo: str, exclude: set[int]) -> list[dict]:
    search = gh_json(
        "api", "-X", "GET", "search/issues",
        "-f", f"q=repo:{repo} is:pr is:merged",
        "-f", "per_page=100", "-f", "sort=updated",
    )
    items = search.get("items", []) if isinstance(search, dict) else []
    pool = []
    for item in items:
        if len(pool) >= POOL_SIZE:
            break
        num = item["number"]
        if num in exclude:
            continue
        pool.append({
            "id": f"{repo}#{num}",
            "text": f"PR #{num}: {item.get('title', '')}\n\n{item.get('body') or ''}",
        })
    return pool


def build_kep_corpus(exclude_paths: set[str]) -> list[dict]:
    """Real sample of the repo's ~657 KEP READMEs, not filtered by keyword —
    a keyword-restricted pool (files matching "Alternatives Considered")
    only yields ~26 files total, too thin to be a real decoy set. Full text,
    no truncation: rag_index.py chunks by section, so a doc's real content
    isn't cut off before a downstream retrieval step sees it."""
    repo = "kubernetes/enhancements"
    all_paths = gh_json(
        "api", "-X", "GET", f"repos/{repo}/git/trees/master", "-f", "recursive=true",
    )
    candidates = [
        t["path"] for t in all_paths["tree"]
        if t["path"].startswith("keps/") and t["path"].endswith("README.md")
        and t["path"] not in exclude_paths
    ]
    sample = random.sample(candidates, min(POOL_SIZE, len(candidates)))
    pool = []
    for path in sample:
        try:
            content = gh_json("api", f"repos/{repo}/contents/{path}")
        except subprocess.CalledProcessError:
            continue
        if not isinstance(content, dict) or "content" not in content:
            continue
        try:
            text = base64.b64decode(content["content"]).decode("utf-8", errors="ignore")
        except Exception:
            continue
        pool.append({"id": path, "text": text})
    return pool


def main() -> None:
    decisions = [json.loads(line) for line in (DATA_DIR / "decisions.jsonl").open()]
    corpus_dir = DATA_DIR / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    pr_repos = {d["repo"] for d in decisions if "original_pr" in d["citation"]}
    for repo in pr_repos:
        exclude = own_citation_numbers(decisions, repo)
        pool = build_pr_corpus(repo, exclude)
        out = corpus_dir / f"{repo.replace('/', '-')}.jsonl"
        with out.open("w") as f:
            for rec in pool:
                f.write(json.dumps(rec) + "\n")
        print(f"{repo}: {len(pool)} decoy PRs -> {out}")

    kep_decisions = [d for d in decisions if "file" in d["citation"]]
    if kep_decisions:
        exclude_paths = {d["citation"]["file"]["path"] for d in kep_decisions}
        pool = build_kep_corpus(exclude_paths)
        out = corpus_dir / "kubernetes-enhancements.jsonl"
        with out.open("w") as f:
            for rec in pool:
                f.write(json.dumps(rec) + "\n")
        print(f"kubernetes/enhancements: {len(pool)} decoy KEPs -> {out}")


if __name__ == "__main__":
    main()
