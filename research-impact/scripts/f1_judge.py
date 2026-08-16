"""Re-derive the whole comparison from the model's own recorded answers.

The producer's scores are ignored. For System B this judge re-runs the
deterministic half itself, starting from the raw per-assumption judgments, so a
wrong propagation cannot be hidden in a summary. For Baseline A it re-reads the
JSON the model returned. Then it recomputes every metric and compares.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import harness, repair, score, systems, variants  # noqa: E402
from bench.holdout import HOLDOUT  # noqa: E402
from keel import ledger  # noqa: E402
from keel.propagate import evaluate  # noqa: E402

DEFAULT_ARTIFACT = ROOT / "proof-out" / "f1-dev.json"
SUITES = {"dev": variants.VARIANTS, "holdout": HOLDOUT}
COUNTERS = ("tp", "fp", "fn", "state_exact", "untouched_total",
            "untouched_disturbed", "provenance_contains_cause",
            "provenance_exact")


class Judgement:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.results.append((name, passed, detail))
        return passed

    def report(self) -> int:
        for name, passed, detail in self.results:
            print(("PASS  " if passed else "FAIL  ") + name
                  + (f"  {detail}" if detail else ""))
        failed = sum(1 for _, ok, _ in self.results if not ok)
        print(f"\n{len(self.results) - failed}/{len(self.results)} PASS")
        return 1 if failed else 0


def _rebuild_b(scenario, raw: list[dict], boundary: str) -> systems.Outcome:
    relations = []
    for item in raw:
        relation = systems.relation_for(item["target"], item["answer"], boundary)
        if relation is not None:
            relations.append(relation)
    log, admission = harness.admit(scenario.log, scenario.variant.document,
                                   relations, "model:judge")
    if scenario.variant.confirmed:
        log = harness.confirm_new_edges(log, admission)
    after = evaluate(ledger.replay(log))
    changed = {
        node: after.state_of(node) for node in after.nodes
        if scenario.before.state_of(node) != after.state_of(node)
    }
    return systems.Outcome(
        "B", changed,
        {node: list(after.nodes[node].because) for node in changed},
        raw=raw, boundary=boundary,
    )


def _rebuild_a(raw: list[dict], boundary: str) -> systems.Outcome:
    changed, because = {}, {}
    for item in (raw[0] if raw else {}).get("changed", []):
        node = str(item.get("node", ""))
        changed[node] = str(item.get("to", ""))
        because[node] = [str(ref) for ref in item.get("because", [])]
    return systems.Outcome("A", changed, because, boundary=boundary)


def judge_truth(j: Judgement, artifact: dict, scenarios: dict) -> None:
    recorded = {item["id"]: item for item in artifact["variants"]}
    mismatched = [
        name for name, scenario in scenarios.items()
        if recorded.get(name, {}).get("truth_changed") != scenario.truth_changed
    ]
    j.check("ground truth in the artifact matches the rebuilt scenarios",
            not mismatched, str(mismatched))
    empty = [name for name, s in scenarios.items() if not s.truth_changed]
    j.check("the benchmark includes variants where nothing may change",
            len(empty) >= 4, f"{len(empty)}: " + ", ".join(sorted(empty)))
    j.check("the benchmark covers at least fifteen variants",
            len(scenarios) >= 15, str(len(scenarios)))


def judge_rows(j: Judgement, artifact: dict, scenarios: dict) -> list[dict]:
    recomputed, drifted, mis_scored = [], [], []
    for row in artifact["rows"]:
        scenario = scenarios[row["variant"]]
        boundary = row.get("boundary", "v1")
        outcome = (_rebuild_b(scenario, row["raw"], boundary)
                   if row["system"] == "B"
                   else _rebuild_a(row["raw"], boundary))
        fresh = score.score_outcome(scenario, outcome)
        fresh["run"] = row["run"]
        fresh["config"] = row.get("config", row["system"])
        fresh["repair"] = repair.repair_cost(scenario, outcome)
        # The frozen dev artifact predates this metric. Absent is not wrong.
        if "repair" in row and fresh["repair"] != row["repair"]:
            mis_scored.append(f"repair:{fresh['config']}:{row['variant']}")
        if sorted(outcome.changed) != row["predicted_changed"]:
            drifted.append(f"{row['system']}:{row['variant']}:{row['run']}")
        if any(fresh[key] != row[key] for key in COUNTERS):
            mis_scored.append(f"{row['system']}:{row['variant']}:{row['run']}")
        if fresh["edge_errors"] != row["edge_errors"]:
            mis_scored.append(f"edges:{row['system']}:{row['variant']}")
        for cost in ("prompt_tokens", "output_tokens", "seconds", "calls",
                     "failures", "invalid_transitions"):
            fresh[cost] = row[cost]
        recomputed.append(fresh)
    j.check("every recorded affected set is reproducible from the raw answers",
            not drifted, str(drifted[:6]))
    j.check("every recorded score matches an independent recount",
            not mis_scored, str(mis_scored[:6]))
    return recomputed


def judge_totals(j: Judgement, artifact: dict, rows: list[dict]) -> None:
    for key, claimed in artifact["results"].items():
        mine = [r for r in rows if r["config"] == key]
        j.check(f"{key} aggregate is reproducible",
                score.aggregate(mine) == claimed["aggregate"])
        j.check(f"{key} stability is reproducible",
                score.stability(mine) == claimed["stability"])
        if "repair" in claimed:
            j.check(f"{key} correction locality is reproducible",
                    repair.aggregate_repair(mine) == claimed["repair"])


def judge_asymmetries(j: Judgement, rows: list[dict], scenarios: dict) -> None:
    """What System B gets for free, stated precisely enough to be falsified.

    The first version of this check asserted that B's justifications always
    equal ground truth's, which is not what "the engine wrote them" means and
    is false: a wrong semantic judgment produces a real edge that then appears,
    correctly, in the justification of everything downstream of it. The holdout
    caught that. The two properties that actually hold are below.
    """
    b_rows = [r for r in rows if r["system"] == "B"]
    j.check("System B never emitted an impossible state, by construction",
            all(not r["invalid_transitions"] for r in b_rows))
    dangling = [
        f"{r['config']}:{r['variant']}:{node}"
        for r in b_rows for node, refs in r.get("because", {}).items()
        for ref in refs
        if ref not in _known_ids(scenarios[r["variant"]], r)
    ]
    j.check("every justification System B cites is a real edge in its own graph",
            not dangling, str(dangling[:4]))
    unexplained = [
        f"{r['config']}:{r['variant']}:{r['run']}" for r in b_rows
        if not r["edge_errors"] and r["provenance_exact"] != r["state_exact"]
    ]
    j.check("System B has no provenance error without a semantic error",
            not unexplained, str(unexplained[:4]))


def _known_ids(scenario, row: dict) -> set[str]:
    """Rebuild B's own graph so its citations can be checked against it."""
    relations = [
        systems.relation_for(item["target"], item["answer"],
                             row.get("boundary", "v1"))
        for item in row["raw"]
    ]
    log, _ = harness.admit(scenario.log, scenario.variant.document,
                           [r for r in relations if r is not None],
                           "model:judge")
    program = ledger.replay(log)
    return set(program.edges) | set(program.decisions)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ARTIFACT
    if not path.is_file():
        print(f"no artifact at {path}. Run `make bench` first.")
        return 1
    artifact = json.loads(path.read_text(encoding="utf-8"))
    suite = SUITES[artifact.get("suite", "dev")]
    scenarios = {v.id: harness.build(v) for v in suite}
    j = Judgement()
    if artifact["mode"] != "live":
        j.check("the artifact is a live measurement", False,
                f"mode is {artifact['mode']}, so no number here is a result")
    judge_truth(j, artifact, scenarios)
    rows = judge_rows(j, artifact, scenarios)
    judge_totals(j, artifact, rows)
    judge_asymmetries(j, rows, scenarios)
    print(f"judged {path.name}, proof {artifact['proof_id']}, "
          f"mode {artifact['mode']}, suite {artifact.get('suite', 'dev')}\n")
    _print_recomputed(rows)
    return j.report()


RECOUNT = ("precision", "recall", "f1", "unrelated_preserved", "edge_errors")


def _print_recomputed(rows: list[dict]) -> None:
    """The judge's own numbers, not the producer's, for anyone reading along."""
    keys = sorted({row["config"] for row in rows})
    width = 18
    print("recomputed by the judge".ljust(34)
          + "".join(k.rjust(width) for k in keys))
    for key in RECOUNT:
        mine = {k: score.aggregate([r for r in rows if r["config"] == k])
                for k in keys}
        print(key.ljust(34) + "".join(str(mine[k][key]).rjust(width)
                                      for k in keys))
    for key in ("corrections_required", "nodes_repaired_per_correction",
                "residual_wrong_nodes_after_correction"):
        mine = {k: repair.aggregate_repair([r for r in rows if r["config"] == k])
                for k in keys}
        print(key.ljust(34) + "".join(str(mine[k][key]).rjust(width)
                                      for k in keys))
    print()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
