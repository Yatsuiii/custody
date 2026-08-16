"""Judge the phase 2 artifact without believing any claim it makes.

The producer writes states, digests and a report. This script ignores all three
and recomputes them from the recorded event log, then compares what it computed
against what should have happened, which is written here rather than read from
the artifact. A hand-edited proof file fails, because the log and the claims
would no longer agree.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from keel import ledger, program as program_module, propose  # noqa: E402
from keel.model import EVIDENCE_RELATIONS, normalize  # noqa: E402
from keel.propagate import GraphState, evaluate  # noqa: E402

DEFAULT_ARTIFACT = ROOT / "proof-out" / "phase2.json"

# What the new evidence must do, written here so the artifact cannot define its
# own success. A2 is contested by the paper; A6 is the question E7 was going to
# answer; everything else in the program is either downstream of those two or
# must not move at all.
EXPECTED_CHANGES = {
    "A2": ("SUPPORTED", "CONTESTED"),
    "A6": ("UNKNOWN", "SUPPORTED"),
    "H1": ("ACTIVE", "REQUIRES_REVIEW"),
    "E4": ("PLANNED", "STALE"),
    "E7": ("PLANNED", "REDUNDANT"),
}
EXPECTED_UNTOUCHED = ("A1", "A3", "A4", "A5", "H2", "E1", "E2", "E3", "E5", "E6")
EXPECTED_AFTER_OVERRIDE = {
    "A2": "SUPPORTED", "H1": "ACTIVE", "E4": "PLANNED",
    "A6": "SUPPORTED", "E7": "REDUNDANT",
}


class Judgement:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.results.append((name, passed, detail))
        return passed

    def report(self) -> int:
        for name, passed, detail in self.results:
            flag = "PASS" if passed else "FAIL"
            print(f"{flag}  {name}" + (f"  {detail}" if detail else ""))
        failed = sum(1 for _, passed, _ in self.results if not passed)
        print(f"\n{len(self.results) - failed}/{len(self.results)} PASS")
        return 1 if failed else 0


def _events(artifact: dict) -> list:
    return [
        ledger.Event(item["id"], item["kind"], item["at"], item["payload"])
        for item in artifact["log"]
    ]


def _states_at(events: list, length: int) -> GraphState:
    return evaluate(ledger.replay(tuple(events[:length])))


def _step(artifact: dict, name: str) -> dict:
    return next(item for item in artifact["steps"] if item["step"] == name)


def judge_fixture(j: Judgement, program) -> None:
    j.check(
        "fixture is a real program",
        len(program.hypotheses) >= 2
        and len(program.assumptions) >= 5
        and len(program.experiments) >= 6,
        f"{len(program.hypotheses)} hypotheses, {len(program.assumptions)} "
        f"assumptions, {len(program.experiments)} experiments",
    )
    relations = {str(e.relation) for e in program.edges.values()}
    j.check(
        "fixture carries evidence in both directions",
        {"SUPPORTS", "CONTRADICTS"} <= relations,
        ", ".join(sorted(relations)),
    )


def judge_impact(j: Judgement, artifact: dict, events: list) -> GraphState:
    baseline = _states_at(events, _step(artifact, "baseline")["log_length"])
    impact_step = _step(artifact, "new_evidence")
    after = _states_at(events, impact_step["log_length"])
    changed = {
        node: (baseline.state_of(node), after.state_of(node))
        for node in after.nodes
        if baseline.state_of(node) != after.state_of(node)
    }
    j.check("new evidence moves exactly the expected nodes",
            changed == EXPECTED_CHANGES, json.dumps(changed, sort_keys=True))
    j.check(
        "unrelated artifacts are untouched",
        all(baseline.state_of(n) == after.state_of(n) for n in EXPECTED_UNTOUCHED),
        ", ".join(EXPECTED_UNTOUCHED),
    )
    j.check("producer's claimed impact states match the recomputed ones",
            artifact["impact_states"] == after.as_dict())
    j.check("producer's claimed step digest matches the recomputed one",
            impact_step["state_digest"] == after.digest())
    return after


def judge_provenance(j: Judgement, program, state: GraphState) -> None:
    """Every change must be explained, and every excerpt must be real."""
    missing = [node for node in EXPECTED_CHANGES if not state.nodes[node].because]
    j.check("every change carries a justification", not missing, str(missing))
    dangling = [
        ref for node in EXPECTED_CHANGES for ref in state.nodes[node].because
        if ref not in program.edges and ref not in program.decisions
    ]
    j.check("every justification resolves to a recorded edge", not dangling,
            str(dangling))
    fabricated = []
    for edge in program.edges.values():
        if edge.relation not in EVIDENCE_RELATIONS:
            continue
        claim = program.claims[edge.source]
        source = program.sources[claim.source]
        if normalize(claim.excerpt) not in normalize(source.text):
            fabricated.append(edge.id)
    j.check("every admitted excerpt occurs in the document it cites",
            not fabricated, str(fabricated))


def judge_refusals(j: Judgement, artifact: dict, events: list) -> None:
    baseline_digest = _step(artifact, "baseline")["state_digest"]
    irrelevant = _step(artifact, "irrelevant_paper")
    reasons = {item["refused"] for item in irrelevant["refused"]}
    j.check("an irrelevant paper is refused, with reasons",
            not irrelevant["admitted"] and reasons == {"not_evidence",
                                                       "below_confidence"},
            ", ".join(sorted(reasons)))
    j.check("an irrelevant paper perturbs nothing",
            _states_at(events, irrelevant["log_length"]).digest()
            == baseline_digest)

    fabricated = _step(artifact, "fabricated_provenance")
    fab_reasons = {item["refused"] for item in fabricated["refused"]}
    impact_digest = _step(artifact, "new_evidence")["state_digest"]
    j.check("a fabricated excerpt is refused at ingestion",
            not fabricated["admitted"] and fab_reasons == {"excerpt_not_found"},
            ", ".join(sorted(fab_reasons)))
    j.check("a fabricated excerpt changes nothing",
            _states_at(events, fabricated["log_length"]).digest() == impact_digest)

    duplicate = _step(artifact, "duplicate_ingestion")
    dup_reasons = {item["refused"] for item in duplicate["refused"]}
    j.check("re-ingesting the same evidence is idempotent",
            not duplicate["admitted"] and dup_reasons == {"already_present"}
            and duplicate["log_length"] == fabricated["log_length"],
            ", ".join(sorted(dup_reasons)))


def judge_replay(j: Judgement, artifact: dict, events: list) -> None:
    first = program_module.digest_of(ledger.replay(tuple(events)))
    second = program_module.digest_of(ledger.replay(tuple(events)))
    j.check("replaying the log reproduces the same program", first == second, first)
    j.check("producer's replay digests match the judge's",
            set(artifact["replay_digests"]) == {first})


def judge_override(j: Judgement, artifact: dict, events: list) -> None:
    final = _states_at(events, _step(artifact, "human_override")["log_length"])
    actual = {node: final.state_of(node) for node in EXPECTED_AFTER_OVERRIDE}
    j.check(
        "a human override reverses exactly its own consequences",
        actual == EXPECTED_AFTER_OVERRIDE, json.dumps(actual, sort_keys=True),
    )
    j.check("producer's claimed final states match the recomputed ones",
            artifact["final_states"] == final.as_dict())


def judge_replacement(j: Judgement, artifact: dict, events: list) -> None:
    impact_length = _step(artifact, "duplicate_ingestion")["log_length"]
    program = ledger.replay(tuple(events[:impact_length]))
    state = _states_at(events, impact_length)
    spec = propose.slots(program, state)
    claimed = artifact["replacement"]
    j.check("the replacement's slots are recomputed, not asserted",
            spec.as_dict() == claimed["slots"], json.dumps(spec.as_dict()))
    candidate = claimed["candidate"]
    valid, problems = propose.check(
        program, state, spec,
        propose.Candidate(candidate["id"], tuple(candidate["requires"]),
                          tuple(candidate["tests"]),
                          tuple(candidate["establishes"])),
    )
    j.check("the proposed replacement survives the graph's own check",
            valid and not problems, str(problems))
    refused = claimed["refused_candidate"]
    bad_valid, bad_problems = propose.check(
        program, state, spec,
        propose.Candidate(refused["id"], tuple(refused["requires"]),
                          tuple(refused["tests"]),
                          tuple(refused["establishes"])),
    )
    j.check("a replacement built on the contested premise is refused",
            not bad_valid
            and any(p.startswith("relies_on_unsafe") for p in bad_problems),
            str(bad_problems))


def main(argv: list[str]) -> int:
    artifact_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_ARTIFACT
    if not artifact_path.is_file():
        print(f"no artifact at {artifact_path}. Run `make gate` first.")
        return 1
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    events = _events(artifact)
    j = Judgement()
    try:
        program = ledger.replay(tuple(events))
    except ValueError as broken:
        j.check("the recorded log replays into a valid program", False, str(broken))
        return j.report()
    j.check("the recorded log replays into a valid program", True)
    judge_fixture(j, program)
    after = judge_impact(j, artifact, events)
    judge_provenance(
        j, ledger.replay(tuple(events[:_step(artifact, "new_evidence")
                                      ["log_length"]])), after,
    )
    judge_refusals(j, artifact, events)
    judge_replay(j, artifact, events)
    judge_override(j, artifact, events)
    judge_replacement(j, artifact, events)
    print(f"judged {artifact_path.name}, proof {artifact['proof_id']}\n")
    return j.report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
