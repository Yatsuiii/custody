"""Closes the class of bug Step 1-5 only closed one instance of: any future
change that invalidates any captured artifact must turn `make check` red,
not wait for a judge to notice by hand.

Each artifact already has its own offline judge, run live during proof
capture and again by `make gates` / `make registry-gates` etc. This module
adds nothing new to judge with, it only re-runs those same judges here, in
the test suite, against whatever the repo happens to have on disk right now.

Artifacts are gitignored (`.gitignore:5`), so a fresh clone has none of
them. Each artifact is skipped, not failed, when absent, to keep a fresh
clone green; a captured artifact that regresses must fail loud.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Callable

from scripts import (
    auditor_gates,
    chain_gates,
    escalation_gates,
    fleet_gates,
    gateway_gates,
    memory_deletion_gates,
    model_armor_gates,
    narration_gates,
    onboarding_gates,
    observability_gates,
    registry_gates,
    review_gates,
    revision_binding_gates,
    scheduler_gates,
)

PROOF_OUT = Path(__file__).parent.parent / "proof-out"

#: Freshness is a property of when an artifact was captured, not of whether
#: the code that produced it is still correct. A stale-but-otherwise-valid
#: artifact must not fail this suite; only a judge would fail it for real
#: expiry, and that judgment is time-of-run dependent, not something a test
#: suite should assert against a fixed clock.
FRESHNESS_KEYS = {"fresh_live_evidence", "fresh_bounded_live_evidence"}

#: Every artifact this project has ever captured, paired with the judge that
#: independently re-verifies it from evidence on disk. Verified against
#: R1_HANDOFF.md section 6: every mapping here was executed during the
#: judging pass this file's own regression was found in.
ARTIFACT_JUDGES: dict[str, Callable[[dict], dict[str, bool]]] = {
    "live-registry-attack.json": registry_gates.judge,
    "live-gateway.json": gateway_gates.judge,
    "live-revision-binding.json": revision_binding_gates.judge,
    "live-memory-deletion.json": memory_deletion_gates.judge,
    "live-model-armor.json": model_armor_gates.judge,
    "live-observability.json": observability_gates.judge,
    "live-chain.json": chain_gates.judge_offline,
    "live-fleet.json": fleet_gates.judge_offline,
    "live-narration.json": narration_gates.judge_offline,
    "live-review.json": review_gates.judge_offline,
    "live-auditor.json": auditor_gates.judge_offline,
    "live-onboarding.json": onboarding_gates.judge_offline,
    "live-escalation.json": escalation_gates.judge_offline,
    "live-scheduler.json": scheduler_gates.judge_offline,
}


class EveryStoredArtifactStillPassesItsOwnJudge(unittest.TestCase):
    def test_every_captured_artifact_passes_its_gates_except_freshness(self):
        checked = 0
        for filename, judge in ARTIFACT_JUDGES.items():
            path = PROOF_OUT / filename
            if not path.exists():
                continue
            checked += 1
            with self.subTest(artifact=filename):
                evidence = json.loads(path.read_text())
                gates = judge(evidence)
                failing = {
                    name: passed
                    for name, passed in gates.items()
                    if name not in FRESHNESS_KEYS and not passed
                }
                self.assertEqual(
                    failing,
                    {},
                    f"{filename} fails its own offline judge: {sorted(failing)}",
                )
        if checked == 0:
            self.skipTest("no proof-out/ artifacts present on this clone")


if __name__ == "__main__":
    unittest.main()
