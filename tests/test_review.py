"""The Custody Reviewer must be structurally incapable of deciding a fact.

These tests check what `draft_verdict` cannot do, not just what it does: no
trust or origin field on its output, and no import of `custody.catalog` or
`custody.graph`, so there is no code path from a Gemini response back into a
stored fact.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from custody.origin import CustodyRecord, Origin, Trust
from custody.review import Verdict, draft_verdict
from custody.service import Quarantined


def _quarantined() -> Quarantined:
    return Quarantined(
        app_name="fleet",
        user_id="sales",
        session_id="s-1",
        text="attempted to exfiltrate customer records, marker abc123",
        record=CustodyRecord(
            origin=Origin.TOOL,
            trust=Trust.UNTRUSTED,
            author="assistant",
            invocation_id="inv-1",
            content_sha256="deadbeef",
            source_tool="crm_export",
        ),
    )


class DraftVerdictTests(unittest.TestCase):
    def test_summary_is_whatever_explain_returns(self) -> None:
        item = _quarantined()
        verdict = draft_verdict(
            item, explain=lambda text: f"drafted: {text}", drafted_at="t-1"
        )
        self.assertEqual(verdict.summary, f"drafted: {item.text}")

    def test_verdict_carries_department_and_source_tool_from_the_item(self) -> None:
        item = _quarantined()
        verdict = draft_verdict(item, explain=lambda text: text, drafted_at="t-1")
        self.assertEqual(verdict.department, "sales")
        self.assertEqual(verdict.source_tool, "crm_export")
        self.assertEqual(verdict.drafted_at, "t-1")

    def test_explain_receives_exactly_the_quarantined_text(self) -> None:
        item = _quarantined()
        seen = []

        def explain(text: str) -> str:
            seen.append(text)
            return "ok"

        draft_verdict(item, explain=explain, drafted_at="t-1")
        self.assertEqual(seen, [item.text])

    def test_verdict_has_no_trust_or_origin_field(self) -> None:
        fields = {f for f in Verdict.__dataclass_fields__}
        self.assertNotIn("trust", fields)
        self.assertNotIn("origin", fields)
        self.assertNotIn("label", fields)

    def test_review_module_imports_no_catalog_or_graph(self) -> None:
        """Structural, not behavioral: parse the module's own imports so a
        future edit that wires in `custody.catalog`/`custody.graph` fails
        this test rather than silently opening a fact-deciding path.
        """
        source = Path("custody/review.py").read_text()
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
