"""Phase 2 gate: run the whole loop offline and write one evidence artifact.

This script proves nothing by itself. It produces `proof-out/phase2.json`, which
`scripts/phase2_judge.py` then reads without trusting a word of it: the judge
replays the recorded event log, recomputes every state, and compares the result
against its own expectation of what should have moved. Producer and judge are
split for the same reason a lab keeps analysis separate from the run.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from keel import ingest, ledger, program as program_module, propose, report  # noqa: E402
from keel.model import Source  # noqa: E402
from keel.propagate import evaluate  # noqa: E402

FIXTURES = ROOT / "fixtures"
OUT = ROOT / "proof-out" / "phase2.json"

CLAIM_BOUNDARY = (
    "Offline and deterministic. The semantic step (does this excerpt support or "
    "contradict this assumption) is a recorded fixture judgment, not a live "
    "model call, so this artifact proves the propagation, admission, replay and "
    "override behaviour only. It does not measure how accurately a model makes "
    "that judgment, and it does not touch any cloud service."
)


def _source(raw: dict) -> Source:
    return Source(
        raw["id"], raw["title"], raw["text"], raw["kind"], raw["produced_by"]
    )


def _step(name: str, log: tuple, admission: ingest.Admission, note: str) -> dict:
    state = evaluate(ledger.replay(log))
    return {
        "step": name,
        "note": note,
        "admitted": list(admission.admitted),
        "refused": list(admission.refused),
        "log_length": len(log),
        "state_digest": state.digest(),
    }


def _ingest(log: tuple, source: Source, raw: list[dict], at: str) -> tuple:
    current = ledger.replay(log)
    proposals = ingest.proposals_from(raw, "model:fixture-judge")
    admission = ingest.ingest(current, source, proposals, at)
    return ledger.extend(log, list(admission.events)), admission


def main() -> int:
    at = datetime.now(UTC).isoformat()
    fixture = json.loads((FIXTURES / "arc_program.json").read_text(encoding="utf-8"))
    evidence = json.loads((FIXTURES / "evidence.json").read_text(encoding="utf-8"))

    log = (ledger.event(ledger.PROGRAM_DECLARED, fixture, at),)
    baseline = evaluate(ledger.replay(log))
    steps = [{
        "step": "baseline",
        "note": "the program as declared, before any new evidence",
        "admitted": [], "refused": [],
        "log_length": len(log),
        "state_digest": baseline.digest(),
    }]

    log, admission = _ingest(
        log, _source(evidence["irrelevant_paper"]["source"]),
        evidence["irrelevant_paper"]["proposals"], at,
    )
    steps.append(_step(
        "irrelevant_paper", log, admission,
        "a paper about tokenisation; one proposal is UNRELATED, one is under "
        "the confidence floor. Nothing may move.",
    ))

    log, admission = _ingest(
        log, _source(evidence["new_paper"]["source"]),
        evidence["new_paper"]["proposals"], at,
    )
    after = evaluate(ledger.replay(log))
    impact = report.change_report(ledger.replay(log), baseline, after)
    steps.append(_step(
        "new_evidence", log, admission,
        "the paper that contradicts A2 and settles A6",
    ))

    log, admission = _ingest(
        log, _source(evidence["new_paper"]["source"]),
        evidence["fabricated"]["proposals"], at,
    )
    steps.append(_step(
        "fabricated_provenance", log, admission,
        "a plausible sentence attributed to the real paper, which does not "
        "occur in it",
    ))

    log, admission = _ingest(
        log, _source(evidence["new_paper"]["source"]),
        evidence["new_paper"]["proposals"], at,
    )
    steps.append(_step(
        "duplicate_ingestion", log, admission,
        "the same paper and the same judgments, ingested a second time",
    ))

    replacement = _replacement(ledger.replay(log), after)

    log = _override(log, ledger.replay(log), at)
    steps.append({
        "step": "human_override",
        "note": "the researcher rejects the machine-proposed contradiction "
                "against A2; its consequences must reverse, and nothing else "
                "may move",
        "admitted": [], "refused": [],
        "log_length": len(log),
        "state_digest": evaluate(ledger.replay(log)).digest(),
    })

    artifact = {
        "proof_id": uuid.uuid4().hex,
        "at": at,
        "claim_boundary": CLAIM_BOUNDARY,
        "fixture": "fixtures/arc_program.json",
        "evidence_fixture": "fixtures/evidence.json",
        "baseline_states": baseline.as_dict(),
        "impact_states": after.as_dict(),
        "final_states": evaluate(ledger.replay(log)).as_dict(),
        "impact_report": impact,
        "replacement": replacement,
        "steps": steps,
        "log": ledger.log_as_dicts(log),
        "replay_digests": _replay_digests(log),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(report.render(impact))
    print(f"\nwrote {OUT.relative_to(ROOT)}  proof {artifact['proof_id']}")
    return 0


def _replacement(current, state) -> dict:
    spec = propose.slots(current, state)
    candidate = propose.draft(
        spec, "E8",
        "Re-run the coordinate ablation with rotary encodings ablated rather "
        "than coordinate features removed, on the held-out families only.",
    )
    valid, problems = propose.check(current, state, spec, candidate)
    unsafe = propose.Candidate(
        "E9", (*spec.may_rely_on, *spec.targets), spec.discriminates,
        spec.targets[:1], "the same sweep as E4, rebuilt on the contested premise",
    )
    unsafe_valid, unsafe_problems = propose.check(current, state, spec, unsafe)
    return {
        "slots": spec.as_dict(),
        "candidate": {
            "id": candidate.id, "requires": list(candidate.requires),
            "tests": list(candidate.tests), "establishes": list(candidate.establishes),
            "method": candidate.method, "valid": valid, "problems": problems,
        },
        "refused_candidate": {
            "id": unsafe.id, "requires": list(unsafe.requires),
            "tests": list(unsafe.tests), "establishes": list(unsafe.establishes),
            "valid": unsafe_valid, "problems": unsafe_problems,
        },
    }


def _override(log: tuple, current, at: str) -> tuple:
    contradiction = next(
        edge for edge in current.edges.values()
        if edge.target == "A2" and str(edge.relation) == "CONTRADICTS"
    )
    return ledger.append(
        log, ledger.reject(contradiction, "human:program-owner",
                           "probe result is on 2048-token sequences; ours are 512",
                           at)
    )


def _replay_digests(log: tuple) -> list[str]:
    """Two independent folds of the same log. They have to agree."""
    return [
        program_module.digest_of(ledger.replay(log)),
        program_module.digest_of(ledger.replay(log)),
    ]


if __name__ == "__main__":
    raise SystemExit(main())
