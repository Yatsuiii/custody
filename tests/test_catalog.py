"""G4, half one: department A cannot raise trust for department B's tools.

Every case here asks whether a vouch changes the boundary it names or the
boundary that asked for it. The catalog is deliberately dumb about anything
else: it does not check the tool is real, does not check the evidence, only
whether the actor and the department in the grant agree.
"""

from __future__ import annotations

import unittest

from custody.catalog import Demotion, Denial, Grant, TrustCatalog, Vouch
from custody.origin import Trust


def grant(department: str, tool: str, *, by: str = "admin") -> Grant:
    return Grant(
        department=department,
        tool=tool,
        vouched_by=by,
        vouched_at="2026-08-10T00:00:00Z",
    )


def demotion(department: str, tool: str, *, by: str = "admin") -> Demotion:
    return Demotion(
        actor_department=department,
        department=department,
        tool=tool,
        demoted_by=by,
        demoted_at="2026-08-14T00:00:00Z",
    )


class ADepartmentVouchesForItsOwnTools(unittest.TestCase):
    def test_an_own_department_vouch_is_allowed(self):
        catalog = TrustCatalog()
        decision = catalog.request(Vouch("sales", grant("sales", "crm_lookup")))
        self.assertTrue(decision.allowed)

    def test_the_grant_is_visible_in_trust_for_that_department(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("sales", grant("sales", "crm_lookup")))
        trust = catalog.trust_for("sales")
        self.assertIs(trust.of("crm_lookup"), Trust.TRUSTED)


class ADepartmentCannotVouchForAnothers(unittest.TestCase):
    def test_a_cross_department_vouch_is_refused(self):
        catalog = TrustCatalog()
        decision = catalog.request(Vouch("sales", grant("support", "evil_tool")))
        self.assertFalse(decision.allowed)
        self.assertIs(decision.denial, Denial.WRONG_DEPARTMENT)

    def test_a_refused_vouch_never_takes_effect(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("sales", grant("support", "evil_tool")))
        self.assertIs(catalog.trust_for("support").of("evil_tool"), Trust.UNTRUSTED)
        self.assertEqual(catalog.grants("support"), ())

    def test_two_adversarial_attempts_are_both_refused_and_audited(self):
        """The G4 proof shape: two departments, two attempts on each other's
        boundary, both refused, both retained for audit."""
        catalog = TrustCatalog()
        catalog.request(Vouch("sales", grant("support", "evil_tool")))
        catalog.request(Vouch("support", grant("sales", "backdoor_tool")))

        denials = catalog.denials()
        self.assertEqual(len(denials), 2)
        self.assertTrue(all(d.denial is Denial.WRONG_DEPARTMENT for d in denials))
        self.assertEqual(catalog.grants("sales"), ())
        self.assertEqual(catalog.grants("support"), ())

    def test_the_refusal_names_both_boundaries(self):
        catalog = TrustCatalog()
        decision = catalog.request(Vouch("sales", grant("support", "evil_tool")))
        self.assertIn("sales", decision.reason())
        self.assertIn("support", decision.reason())


class TrustDoesNotLeakBetweenDepartments(unittest.TestCase):
    def test_a_tool_trusted_in_one_department_is_untrusted_in_another(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("sales", grant("sales", "crm_lookup")))
        self.assertIs(catalog.trust_for("sales").of("crm_lookup"), Trust.TRUSTED)
        self.assertIs(catalog.trust_for("support").of("crm_lookup"), Trust.UNTRUSTED)

    def test_trust_for_is_computed_fresh_not_cached(self):
        """A grant recorded after the first read must still be visible."""
        catalog = TrustCatalog()
        self.assertIs(catalog.trust_for("sales").of("crm_lookup"), Trust.UNTRUSTED)
        catalog.request(Vouch("sales", grant("sales", "crm_lookup")))
        self.assertIs(catalog.trust_for("sales").of("crm_lookup"), Trust.TRUSTED)


class ADepartmentDemotesItsOwnTools(unittest.TestCase):
    def test_an_own_department_demotion_is_allowed_and_withdraws_trust(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("sales", grant("sales", "crm_lookup")))
        decision = catalog.demote(demotion("sales", "crm_lookup"))
        self.assertTrue(decision.allowed)
        self.assertIs(catalog.trust_for("sales").of("crm_lookup"), Trust.UNTRUSTED)

    def test_a_demotion_is_visible_in_outstanding_demotions(self):
        catalog = TrustCatalog()
        catalog.demote(demotion("sales", "crm_lookup"))
        outstanding = [d.demotion for d in catalog.demotion_decisions if d.allowed]
        self.assertEqual([d.tool for d in outstanding], ["crm_lookup"])


class ADepartmentCannotDemoteAnothers(unittest.TestCase):
    def test_a_cross_department_demotion_is_refused(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("support", grant("support", "helpdesk_tool")))
        decision = catalog.demote(
            Demotion(
                actor_department="sales",
                department="support",
                tool="helpdesk_tool",
                demoted_by="sales-admin",
                demoted_at="2026-08-14T00:00:00Z",
            )
        )
        self.assertFalse(decision.allowed)
        self.assertIs(decision.denial, Denial.WRONG_DEPARTMENT)

    def test_a_refused_demotion_leaves_trust_intact(self):
        catalog = TrustCatalog()
        catalog.request(Vouch("support", grant("support", "helpdesk_tool")))
        catalog.demote(
            Demotion(
                actor_department="sales",
                department="support",
                tool="helpdesk_tool",
                demoted_by="sales-admin",
                demoted_at="2026-08-14T00:00:00Z",
            )
        )
        self.assertIs(catalog.trust_for("support").of("helpdesk_tool"), Trust.TRUSTED)


class ADemotionsIdIsDeterministic(unittest.TestCase):
    def test_the_same_demotion_recorded_twice_has_the_same_id(self):
        first = demotion("sales", "crm_lookup")
        second = demotion("sales", "crm_lookup")
        self.assertEqual(first.id(), second.id())

    def test_a_different_tool_has_a_different_id(self):
        self.assertNotEqual(
            demotion("sales", "crm_lookup").id(),
            demotion("sales", "other_tool").id(),
        )


if __name__ == "__main__":
    unittest.main()
