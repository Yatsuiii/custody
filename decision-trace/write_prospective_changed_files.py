"""Write the exact path inventory for the prospective research branch."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE = "8cbf14d7b809722d5c4f0fb89202317fa8681df3"
OUTPUT = ROOT / "CHANGED_FILES_AUTHORITY_PROSPECTIVE.txt"


def main() -> None:
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", BASE, "--", "."], text=True,
        cwd=ROOT,
    ).splitlines()
    relative = [item.removeprefix("decision-trace/") for item in tracked]
    pending = [
        "AUTHORITY_PROSPECTIVE_OUTCOME_LEDGER.md",
        "CHANGED_FILES_AUTHORITY_PROSPECTIVE.txt",
        "POSTRUN_AUTHORITY_VALIDITY_AUDIT.md",
        "RESULTS_AUTHORITY_PROSPECTIVE.md",
        "data/prospective/failures.jsonl",
        "data/prospective/scores.json",
        "data/prospective/validity_audit.json",
        "grade_authority_prospective.py",
        "test_grade_authority_prospective.py",
        "write_prospective_changed_files.py",
    ]
    paths = sorted(set(relative + pending))
    OUTPUT.write_text("\n".join(paths) + "\n")
    print(f"wrote {len(paths)} exact changed paths")


if __name__ == "__main__":
    main()
