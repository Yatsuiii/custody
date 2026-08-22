"""Collect the preregistered candidate primary sources without running systems.

This script is discovery-only. It copies pinned proposal files from shallow
primary-repository clones and fetches selected GitHub records. It never imports
the benchmark adapter, resolver, runner, prompts, predictions, or answer key.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "prospective" / "discovery" / "source_cache.json"

REPOSITORIES = {
    "python/peps": Path("/tmp/decisiontrace-peps"),
    "rust-lang/rfcs": Path("/tmp/decisiontrace-rfcs"),
    "swiftlang/swift-evolution": Path("/tmp/decisiontrace-swift-evolution"),
    "golang/proposal": Path("/tmp/decisiontrace-go-proposal"),
    "kubernetes/enhancements": Path("/tmp/decisiontrace-k8s-enhancements"),
}

FILES = {
    "python/peps": [
        "peps/pep-0247.rst", "peps/pep-0248.rst", "peps/pep-0249.rst",
        "peps/pep-0333.rst", "peps/pep-3333.rst", "peps/pep-0409.rst",
        "peps/pep-0415.rst", "peps/pep-0452.rst", "peps/pep-0612.rst",
    ],
    "rust-lang/rfcs": [
        "text/0769-sound-generic-drop.md", "text/1183-swap-out-jemalloc.md",
        "text/1201-naked-fns.md", "text/1238-nonparametric-dropck.md",
        "text/1522-conservative-impl-trait.md", "text/1951-expand-impl-trait.md",
        "text/1974-global-allocators.md", "text/2071-impl-trait-existential-types.md",
        "text/2203-const-repeat-expr.md", "text/2515-type_alias_impl_trait.md",
        "text/2920-inline-const.md", "text/2972-constrained-naked.md",
        "text/3498-lifetime-capture-rules-2024.md",
    ],
    "swiftlang/swift-evolution": [
        "proposals/0030-property-behavior-decls.md",
        "proposals/0258-property-wrappers.md",
        "proposals/0303-swiftpm-extensible-build-tools.md",
        "proposals/0325-swiftpm-additional-plugin-apis.md",
        "proposals/0474-yielding-accessors.md",
    ],
    "golang/proposal": [
        "design/go2draft-contracts.md", "design/43651-type-parameters.md",
    ],
    "kubernetes/enhancements": [
        "keps/sig-scheduling/583-coscheduling/kep.yaml",
        "keps/sig-scheduling/583-coscheduling/README.md",
        "keps/sig-scheduling/5832-decouple-podgroup-api/kep.yaml",
        "keps/sig-scheduling/5832-decouple-podgroup-api/README.md",
        "keps/sig-scheduling/4671-gang-scheduling/kep.yaml",
        "keps/sig-scheduling/4671-gang-scheduling/README.md",
    ],
}

PULL_REQUESTS = {
    "rust-lang/rfcs": [769, 1183, 1201, 1238, 1522, 1951, 1974, 2071, 2203, 2515, 2920, 2972, 3498],
    "swiftlang/swift": [90516, 91475, 91494],
    "kubernetes/kubernetes": [137464, 137909, 137946, 139008],
    "hashicorp/terraform": [35720, 35827],
    "opentofu/opentofu": [2403, 2404],
    "envoyproxy/envoy": [45103, 45321],
    "llvm/llvm-project": [205775, 213769, 213911],
    "python/cpython": [23702, 25449],
}

GO_ISSUES = [43651, 60078, 61405]
GO_ACCEPTANCE_COMMENTS = [776944155, 1642774250, 1782052910]


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True)


def gh_json(*args: str) -> dict:
    return json.loads(command("gh", *args))


def main() -> None:
    cache: dict = json.loads(OUT.read_text()) if OUT.exists() else {
        "collection_started_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "source-only prospective discovery; no system outputs",
        "repositories": {}, "files": {}, "pull_requests": {},
        "go_issues": {}, "go_acceptance_comments": {},
    }
    for repository, checkout in REPOSITORIES.items():
        if not checkout.joinpath(".git").exists():
            raise SystemExit(f"missing primary-source clone: {checkout}")
        revision = command("git", "-C", str(checkout), "rev-parse", "HEAD").strip()
        cache["repositories"][repository] = {"revision": revision}
        for relative in FILES[repository]:
            content = checkout.joinpath(relative).read_text()
            key = f"{repository}:{relative}"
            cache["files"][key] = {
                "repository": repository,
                "path": relative,
                "revision": revision,
                "url": f"https://github.com/{repository}/blob/{revision}/{relative}",
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "content": content,
            }

    fields = "number,title,body,state,isDraft,createdAt,closedAt,mergedAt,mergeCommit,url"
    for repository, numbers in PULL_REQUESTS.items():
        for number in numbers:
            record = gh_json(
                "pr", "view", str(number), "--repo", repository,
                "--json", fields,
            )
            cache["pull_requests"][f"{repository}#{number}"] = record

    for number in GO_ISSUES:
        cache["go_issues"][str(number)] = gh_json(
            "api", f"repos/golang/go/issues/{number}"
        )
    for comment_id in GO_ACCEPTANCE_COMMENTS:
        cache["go_acceptance_comments"][str(comment_id)] = gh_json(
            "api", f"repos/golang/go/issues/comments/{comment_id}"
        )

    cache["collection_completed_at"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(OUT),
        "repositories": len(cache["repositories"]),
        "files": len(cache["files"]),
        "pull_requests": len(cache["pull_requests"]),
        "issues": len(cache["go_issues"]),
        "comments": len(cache["go_acceptance_comments"]),
    }, indent=2))


if __name__ == "__main__":
    main()
