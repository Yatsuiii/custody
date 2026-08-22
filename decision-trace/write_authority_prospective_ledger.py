"""Render the pre-inference, source-adjudication ledger.

This reads no system output.  The ledger intentionally exposes the hidden
answer key for human review, while inference code is constrained to the
separate public files.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "prospective"
OUTPUT = ROOT / "AUTHORITY_PROSPECTIVE_LEDGER.md"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def esc(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def relation(artifact: dict) -> str:
    parts = []
    for label, field in (("replaces", "replaces"), ("reverts", "reverts"),
                         ("implements", "implements")):
        if artifact[field]:
            parts.append(f"{label} {', '.join(artifact[field])}")
    return "; ".join(parts) or "none"


def state_text(hidden: dict) -> str:
    decisions = ", ".join(hidden["expected_decision_ids"])
    return f"{hidden['expected_state']}: {decisions}" if decisions else hidden["expected_state"]


def evidence_text(hidden: dict) -> str:
    return " OR ".join(" + ".join(group) for group in hidden["acceptable_evidence_sets"])


def artifact_proof(artifact: dict) -> str:
    claims = []
    for proof in artifact["proofs"]:
        if "quote" in proof:
            claims.append(f"`{esc(proof['quote'])}`")
        elif "field" in proof:
            claims.append(f"{proof['field']}=`{esc(proof['value'])}`")
    return "; ".join(claims)


def main() -> None:
    timelines = json.loads((DATA / "timelines.json").read_text())
    checkpoints = read_jsonl(DATA / "checkpoints.jsonl")
    truth = read_jsonl(DATA / "ground_truth.jsonl")
    exclusions = json.loads((DATA / "discovery" / "exclusions.json").read_text())
    manifest = json.loads((DATA / "dataset_manifest.json").read_text())
    by_checkpoint = {row["checkpoint_id"]: row for row in checkpoints}
    hidden = {row["checkpoint_id"]: row for row in truth}
    checkpoint_by_timeline: dict[str, list[dict]] = {}
    for row in checkpoints:
        checkpoint_by_timeline.setdefault(row["timeline_id"], []).append(row)

    ecosystem_counts = Counter(t["ecosystem"] for t in timelines)
    scenario_counts = Counter(
        scenario for timeline in timelines for scenario in set(timeline["scenario_types"])
    )
    lines = [
        "# Prospective Authority Ground-Truth Ledger",
        "",
        "Status: **FROZEN BEFORE INFERENCE**. This ledger was produced only from pinned primary-source artifacts and the separately adjudicated answer key. No DecisionTrace, embedding-RAG, or full-context output existed during selection or adjudication.",
        "",
        "## Audit protocol",
        "",
        "- Unit: an ordered organizational-decision history queried at explicit checkpoints.",
        "- Allowed truth states: exactly one governing decision, multiple parallel governing decisions, unresolved, or no governing decision.",
        "- Authority requires an explicit source-grounded status/transition. Recency alone is never an authority transition.",
        "- Normalized scope names are public query keys grounded in artifact subjects; they are not hidden answer labels.",
        "- A merged code rollback governs the tested implementation scope. It does not change a separate policy scope unless a source says so.",
        "- Partial or qualified replacement is not promoted to a unique broad-scope winner; those checkpoints are unresolved.",
        "- The same researcher performed a second source-only pass over the required strata. No independent second annotator was available; this is recorded as a validity threat.",
        "",
        "## Frozen inventory",
        "",
        f"- Dataset SHA-256 (public timelines): `{manifest['timelines_sha256']}`",
        f"- Source-cache SHA-256: `{manifest['source_cache_sha256']}`",
        f"- Timelines: {len(timelines)}",
        f"- Checkpoints: {len(checkpoints)}",
        f"- Composition: {manifest['stats']['fully_real']} fully real, {manifest['stats']['hybrid']} hybrid, 0 fully synthetic",
        f"- Ecosystems: {', '.join(f'{name} {count}' for name, count in sorted(ecosystem_counts.items()))}",
        f"- Scenario-bearing timelines: {', '.join(f'{name} {count}' for name, count in sorted(scenario_counts.items()))}",
        "",
        "## Timeline-by-timeline adjudication",
        "",
    ]

    for index, timeline in enumerate(timelines, 1):
        lines.extend([
            f"### {index}. `{timeline['timeline_id']}` — {timeline['ecosystem']}",
            "",
            f"Composition: **{timeline['composition']}**. Repositories: {', '.join(timeline['repositories'])}. Scenarios: {', '.join(timeline['scenario_types'])}.",
            "",
            f"Audit note: {timeline['audit_note']}",
            "",
            "| Seq | Artifact / scope | Status / role | Explicit transition | Primary-source proof |",
            "|---:|---|---|---|---|",
        ])
        for artifact in timeline["artifacts"]:
            scopes = ", ".join(artifact["scopes"])
            lines.append(
                f"| {artifact['sequence']} | [{esc(artifact['artifact_id'])}]({artifact['source_url']}) / {esc(scopes)} "
                f"| {artifact['status']} / {artifact['role']} | {esc(relation(artifact))} | {artifact_proof(artifact)} |"
            )
        lines.extend([
            "",
            "| Checkpoint | Visible through | Queried scope(s) | Ground truth | Required evidence | Transition/adjudication |",
            "|---|---:|---|---|---|---|",
        ])
        for cp in checkpoint_by_timeline[timeline["timeline_id"]]:
            gt = hidden[cp["checkpoint_id"]]
            adjudication = gt["adjudication"] or (
                "Authority follows the visible explicit lifecycle state; no later artifact is visible."
            )
            lines.append(
                f"| `{cp['checkpoint_id']}` | {cp['visible_through']} | {esc(', '.join(cp['authority_scopes']))} "
                f"| {esc(state_text(gt))} | {esc(evidence_text(gt))} | {esc(adjudication)} |"
            )
        lines.append("")

    def timelines_with(scenario: str) -> list[str]:
        return [t["timeline_id"] for t in timelines if scenario in t["scenario_types"]]

    supersession_review = [
        "python-db-api", "python-wsgi", "python-exception-context",
        "python-hash-api", "rust-tait-capture", "rust-rpit-capture",
    ]
    revert_review = timelines_with("revert_after_implementation")
    proposal_review = [
        "rust-naked-functions", "rust-global-allocator", "rust-inline-const",
        "go-type-parameters", "go-loop-variables", "go-range-functions",
    ]
    parallel_review = timelines_with("parallel_scopes")
    ambiguous_review = timelines_with("conflicting_or_ambiguous")
    lines.extend([
        "## Required second-pass spot audit",
        "",
        "This was a separate source-only pass after the first adjudication and before any benchmark inference. Each listed timeline was re-opened against the pinned proof above; no ground truth changed during this pass.",
        "",
        f"- Supersession (6; minimum 5): {', '.join(f'`{x}`' for x in supersession_review)}.",
        f"- Revert (all {len(revert_review)}; minimum 5): {', '.join(f'`{x}`' for x in revert_review)}.",
        f"- Proposal not authoritative (6; minimum 5): {', '.join(f'`{x}`' for x in proposal_review)}.",
        f"- Parallel scope (all {len(parallel_review)}): {', '.join(f'`{x}`' for x in parallel_review)}.",
        f"- Ambiguous (all {len(ambiguous_review)}): {', '.join(f'`{x}`' for x in ambiguous_review)}.",
        "",
        "## Pre-output exclusions",
        "",
        "These candidates were excluded or narrowed before any system output. Qualified partial replacements remain in the benchmark only as unresolved broad-scope checkpoints.",
        "",
        "| Candidate | Pre-output reason |",
        "|---|---|",
    ])
    for item in exclusions:
        lines.append(f"| {esc(item['candidate'])} | {esc(item['reason'])} |")
    lines.extend([
        "",
        "## Independence attestation",
        "",
        "The collection order was source discovery → source-grounded adjudication → manual audit → dataset freeze. The prospective run directory did not exist during those steps. Once this ledger and the byte manifest are committed, inclusion, ground truth, scenario tags, prompts, model settings, and resolver bytes are immutable for the run.",
        "",
    ])
    OUTPUT.write_text("\n".join(lines))
    print(f"wrote {OUTPUT.name}: {len(timelines)} timelines, {len(checkpoints)} checkpoints")


if __name__ == "__main__":
    main()
