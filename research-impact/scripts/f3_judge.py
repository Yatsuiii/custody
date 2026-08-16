"""Re-run the whole sequence from the recorded answers and recompute the verdict.

Every trajectory in the artifact is rebuilt by feeding the model's own recorded
output back through the same code path that produced it, so a state at step
seven is reproduced rather than believed. Then every metric and the
pre-registered kill condition are recomputed and compared with what the producer
claimed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import killcondition, seqscore, sequence, timeline  # noqa: E402
from bench.replay import ReplayModel, answers_for  # noqa: E402

DEFAULT_ARTIFACT = ROOT / "proof-out" / "f3-sequence.json"
LOCK = ROOT / "results" / "sequence-lock.json"


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


def _rebuild(row: dict, truths: dict) -> list:
    model = ReplayModel(answers_for(row))
    order = row["order"]
    if row["system"] == "B":
        return timeline.run_b(order, model)
    return timeline.run_a(order, model, persistent=(row["system"] == "A1"),
                          truth=truths[order])


def judge_lock(j: Judgement, artifact: dict) -> None:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    j.check("the artifact was produced against the locked sequence",
            artifact["sequence_digest"] == lock["digest"],
            artifact["sequence_digest"][:16])
    counts = lock["label_counts"]
    j.check("every document x assumption pair was adjudicated",
            sum(counts.values()) == len(lock["documents"]) * 8,
            json.dumps(counts, sort_keys=True))
    moved = {
        (doc, target) for doc in lock["orders"]["canonical"]
        for target, *_ in sequence.true_relations(doc)
    }
    stray = [pair for pair in lock["ambiguous_pairs"]
             if tuple(pair) in moved]
    j.check("no ambiguous pair is allowed to move the truth", not stray,
            str(lock["ambiguous_pairs"]))


def judge_rows(j: Judgement, artifact: dict, truths: dict) -> list[dict]:
    drifted, mis_scored, recomputed = [], [], []
    for row in artifact["rows"]:
        trail = _rebuild(row, truths)
        states = [snapshot.states for snapshot in trail]
        claimed = [step["states"] for step in row["trail"]]
        if states != claimed:
            drifted.append(f"{row['system']}:{row['order']}:{row['run']}")
        fresh = seqscore.score_trail(trail, truths[row["order"]], row["order"])
        fresh |= {"system": row["system"], "run": row["run"]}
        keys = ("end_accuracy", "correction_persistence", "regressions",
                "unnecessary_changes", "wrong_node_steps",
                "longest_error_survival")
        if any(fresh[key] != row[key] for key in keys):
            mis_scored.append(f"{row['system']}:{row['order']}:{row['run']}")
        for cost in ("prompt_tokens", "output_tokens", "seconds", "calls"):
            fresh[cost] = row[cost]
        recomputed.append(fresh)
    j.check("every recorded trajectory replays to the same states",
            not drifted, str(drifted[:4]))
    j.check("every recorded metric matches an independent recount",
            not mis_scored, str(mis_scored[:4]))
    return recomputed


def judge_totals(j: Judgement, artifact: dict, rows: list[dict]) -> dict:
    results = {}
    for system in ("A0", "A1", "B"):
        mine = [r for r in rows if r["system"] == system]
        results[system] = seqscore.aggregate_trails(mine)
        j.check(f"{system} aggregate is reproducible",
                results[system] == artifact["results"][system])
    verdict = killcondition.evaluate(results["A1"], results["B"])
    j.check("the pre-registered verdict is reproducible",
            verdict == artifact["kill_condition"],
            verdict["verdict"])
    return verdict


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ARTIFACT
    if not path.is_file():
        print(f"no artifact at {path}. Run `make bench-seq` first.")
        return 1
    artifact = json.loads(path.read_text(encoding="utf-8"))
    truths = {name: timeline.truth_trajectory(name) for name in sequence.ORDERS}
    j = Judgement()
    if artifact["mode"] not in ("live", "replay"):
        j.check("the artifact is a live measurement", False,
                f"mode is {artifact['mode']}, so no number here is a result")
    judge_lock(j, artifact)
    rows = judge_rows(j, artifact, truths)
    verdict = judge_totals(j, artifact, rows)
    print(f"judged {path.name}, proof {artifact['proof_id']}, "
          f"verdict {verdict['verdict']}\n")
    return j.report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
