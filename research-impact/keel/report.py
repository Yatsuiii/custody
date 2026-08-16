"""The change report: what moved, what did not, and the chain for each.

The sentences here are assembled from the recorded justifications, not written
by a model. That is deliberate. A generated paragraph that happens to describe
the right chain is indistinguishable, on screen, from a generated paragraph that
does not, and the whole product claim is that a reader never has to tell those
two apart.
"""

from __future__ import annotations

from .model import Program, digest
from .propagate import Change, GraphState, diff, explain

RELATION_PHRASE = {
    "DEPENDS_ON": "depends on",
    "REQUIRES": "requires",
    "TESTS": "tests",
    "ESTABLISHES": "would establish",
    "SUPPORTS": "is supported by",
    "CONTRADICTS": "is contradicted by",
}


def change_report(program: Program, before: GraphState, after: GraphState) -> dict:
    changed, unchanged = diff(before, after)
    return {
        "changed": [_change(program, after, item) for item in changed],
        "unchanged": [
            {"node": node, "kind": after.nodes[node].kind,
             "state": after.nodes[node].state}
            for node in unchanged
        ],
        "counts": _counts(changed, unchanged),
        "before_digest": before.digest(),
        "after_digest": after.digest(),
        "unchanged_digest": digest(
            [[node, after.nodes[node].state] for node in unchanged]
        ),
    }


def _change(program: Program, after: GraphState, item: Change) -> dict:
    return {
        "node": item.node,
        "kind": item.kind,
        "was": item.was,
        "now": item.now,
        "because": list(item.because),
        "headline": headline(program, after, item),
        "chain": explain(program, after, item.node),
    }


def _counts(changed: list[Change], unchanged: list[str]) -> dict:
    counts: dict[str, int] = {"changed": len(changed), "unchanged": len(unchanged)}
    for item in changed:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    return counts


def headline(program: Program, after: GraphState, item: Change) -> str:
    """One line, built from the justification edges, never from prose."""
    parts = []
    for ref in item.because:
        edge = program.edges.get(ref)
        if edge is None:
            decision = program.decisions.get(ref)
            if decision is not None:
                parts.append(f"{decision.actor} decided {decision.kind}")
            continue
        phrase = RELATION_PHRASE.get(str(edge.relation), str(edge.relation))
        other = edge.target if edge.source == item.node else edge.source
        if edge.source == item.node:
            parts.append(f"it {phrase} {other}, now {after.state_of(other)}")
        else:
            parts.append(f"it {phrase} {_quote(program, edge.source)}")
    reason = "; ".join(dict.fromkeys(parts)) or "no justification recorded"
    return f"{item.node} {item.was or 'new'} -> {item.now} because {reason}"


def _quote(program: Program, claim_ref: str) -> str:
    claim = program.claims.get(claim_ref)
    if claim is None:
        return claim_ref
    source = program.sources.get(claim.source)
    title = claim.source if source is None else source.title
    return f"{claim_ref} ({title})"


def render(report: dict) -> str:
    lines = ["CHANGED"]
    for item in report["changed"]:
        lines.append(f"  {item['headline']}")
    lines.append("UNCHANGED")
    for item in report["unchanged"]:
        lines.append(f"  {item['node']} stays {item['state']}")
    counts = report["counts"]
    lines.append(f"{counts['changed']} changed, {counts['unchanged']} unchanged")
    return "\n".join(lines)
