"""The durable catalog has one job `TrustCatalog` cannot: survive a restart.
Every test opens a fresh `SqliteTrustCatalog` against a temp file rather than
reusing one connection, to prove durability rather than assume it.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from custody.catalog import Denial, Grant, Vouch
from custody.origin import Trust
from custody.store import SqliteTrustCatalog


def grant(department: str, tool: str) -> Grant:
    return Grant(
        department=department,
        tool=tool,
        vouched_by=f"{department}-admin",
        vouched_at="2026-08-10T00:00:00Z",
    )


class GrantsSurviveARestart(unittest.TestCase):
    def test_a_grant_recorded_before_a_restart_applies_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.db"
            first = SqliteTrustCatalog(path)
            first.request(Vouch("sales", grant("sales", "crm_lookup")))
            first.close()

            reopened = SqliteTrustCatalog(path)
            trust = reopened.trust_for("sales")
            reopened.close()

        self.assertIs(trust.of("crm_lookup"), Trust.TRUSTED)

    def test_a_denial_is_still_a_denial_after_reload(self):
        """The refusal is the audit trail, not a side effect to discard: it
        has to be there on reload the same as an allowed grant."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.db"
            first = SqliteTrustCatalog(path)
            first.request(Vouch("sales", grant("support", "evil_tool")))
            first.close()

            reopened = SqliteTrustCatalog(path)
            denials = reopened.denials()
            trust = reopened.trust_for("support")
            reopened.close()

        self.assertEqual(len(denials), 1)
        self.assertIs(denials[0].denial, Denial.WRONG_DEPARTMENT)
        self.assertIs(trust.of("evil_tool"), Trust.UNTRUSTED)

    def test_trust_does_not_leak_between_departments_after_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.db"
            first = SqliteTrustCatalog(path)
            first.request(Vouch("sales", grant("sales", "crm_lookup")))
            first.close()

            reopened = SqliteTrustCatalog(path)
            sales_trust = reopened.trust_for("sales")
            support_trust = reopened.trust_for("support")
            reopened.close()

        self.assertIs(sales_trust.of("crm_lookup"), Trust.TRUSTED)
        self.assertIs(support_trust.of("crm_lookup"), Trust.UNTRUSTED)

    def test_a_grant_recorded_after_reload_is_appended_not_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.db"
            first = SqliteTrustCatalog(path)
            first.request(Vouch("sales", grant("sales", "crm_lookup")))
            first.close()

            reopened = SqliteTrustCatalog(path)
            reopened.request(Vouch("sales", grant("sales", "payroll_lookup")))
            reopened.close()

            third = SqliteTrustCatalog(path)
            trust = third.trust_for("sales")
            third.close()

        self.assertIs(trust.of("crm_lookup"), Trust.TRUSTED)
        self.assertIs(trust.of("payroll_lookup"), Trust.TRUSTED)


if __name__ == "__main__":
    unittest.main()
