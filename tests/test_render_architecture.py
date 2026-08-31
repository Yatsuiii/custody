"""Regression tests for the judge-facing architecture proof registry."""

from __future__ import annotations

import unittest

from scripts.render_architecture import (
    LIVE_PROOFS,
    widget_escalation,
    widget_onboarding,
)


class ArchitectureProofRegistryTests(unittest.TestCase):
    def test_every_proof_has_one_complete_registration(self):
        ids = [proof.id for proof in LIVE_PROOFS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("Onboarding", ids)
        self.assertIn("Escalation", ids)
        for proof in LIVE_PROOFS:
            with self.subTest(proof=proof.id):
                self.assertTrue(callable(proof.judge))
                self.assertTrue(callable(proof.widget))

    def test_onboarding_widget_keeps_the_draft_only_boundary_visible(self):
        widget = widget_onboarding({
            "request_text": "Please add this department.",
            "draft": {"evidence": "Drafted evidence for human review."},
        })
        self.assertIsNotNone(widget)
        self.assertIn("no trust grant", widget["a"]["label"])
        self.assertIn("draft only", widget["b"]["label"])

    def test_escalation_widget_requires_prior_deterministic_revocation(self):
        missing_revocation = widget_escalation({
            "setup": {"record_id": "probe", "revocation": {"removed": []}},
            "notice": {"summary": "Draft notice."},
        })
        self.assertIsNone(missing_revocation)

        widget = widget_escalation({
            "setup": {
                "record_id": "probe",
                "revocation": {"removed": ["probe"]},
            },
            "notice": {"summary": "Draft notice."},
        })
        self.assertIsNotNone(widget)
        self.assertIn("before Gemini", widget["a"]["value"])
        self.assertIn("draft only", widget["b"]["label"])


if __name__ == "__main__":
    unittest.main()
