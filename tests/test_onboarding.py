"""The Onboarding Agent drafts a vouch request without gaining write power."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from custody.onboarding import VouchDraft, draft_vouch


REQUEST = "We need the CRM export tool for the sales pipeline."


class DraftVouchTests(unittest.TestCase):
    def test_draft_carries_request_fields_and_human_evidence(self) -> None:
        draft = draft_vouch(
            REQUEST,
            department="sales",
            explain=lambda text: f"reviewed: {text}",
            drafted_at="t-1",
        )
        self.assertEqual(draft.department, "sales")
        self.assertEqual(draft.tool, "CRM export")
        self.assertEqual(draft.evidence, f"reviewed: {REQUEST}")
        self.assertEqual(draft.drafted_at, "t-1")

    def test_explain_receives_exactly_the_request_text(self) -> None:
        seen: list[str] = []

        def explain(text: str) -> str:
            seen.append(text)
            return "ok"

        draft_vouch(
            REQUEST,
            department="sales",
            explain=explain,
            drafted_at="t-1",
        )
        self.assertEqual(seen, [REQUEST])

    def test_draft_has_no_fact_deciding_fields(self) -> None:
        fields = set(VouchDraft.__dataclass_fields__)
        self.assertEqual(fields, {"department", "tool", "evidence", "drafted_at"})
        self.assertNotIn("trust", fields)
        self.assertNotIn("origin", fields)
        self.assertNotIn("decision", fields)

    def test_onboarding_module_imports_no_catalog_or_graph(self) -> None:
        source = Path("custody/onboarding.py").read_text()
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("custody.catalog", imported_modules)
        self.assertNotIn("custody.graph", imported_modules)


if __name__ == "__main__":
    unittest.main()
