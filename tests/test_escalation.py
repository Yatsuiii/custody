"""The Escalation Agent drafts notices without gaining revocation power."""

from __future__ import annotations

import ast
import unittest
from dataclasses import dataclass
from pathlib import Path

from custody.escalation import Notice, draft_notice


@dataclass(frozen=True)
class FakeDemotion:
    department: str
    tool: str
    demoted_by: str
    demoted_at: str


DEMOTION = FakeDemotion(
    department="sales",
    tool="crm_export",
    demoted_by="security-review",
    demoted_at="2026-08-30T00:00:00Z",
)


class DraftNoticeTests(unittest.TestCase):
    def test_notice_carries_structural_demotion_fields_and_summary(self) -> None:
        notice = draft_notice(
            DEMOTION,
            explain=lambda text: f"drafted: {text}",
            drafted_at="t-2",
        )
        self.assertEqual(notice.department, "sales")
        self.assertEqual(notice.tool, "crm_export")
        self.assertIn("security-review", notice.summary)
        self.assertEqual(notice.drafted_at, "t-2")

    def test_explain_receives_the_complete_demotion_context(self) -> None:
        seen: list[str] = []

        def explain(text: str) -> str:
            seen.append(text)
            return "ok"

        draft_notice(DEMOTION, explain=explain, drafted_at="t-2")
        self.assertEqual(
            seen,
            [
                "The Auditor completed a revocation after this demotion.\n"
                "Department: sales\n"
                "Tool: crm_export\n"
                "Demotion recorded by: security-review\n"
                "Demotion recorded at: 2026-08-30T00:00:00Z"
            ],
        )

    def test_notice_has_no_fact_deciding_fields(self) -> None:
        fields = set(Notice.__dataclass_fields__)
        self.assertEqual(fields, {"department", "tool", "summary", "drafted_at"})
        self.assertNotIn("trust", fields)
        self.assertNotIn("origin", fields)
        self.assertNotIn("decision", fields)

    def test_escalation_module_imports_no_catalog_or_graph(self) -> None:
        source = Path("custody/escalation.py").read_text()
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
