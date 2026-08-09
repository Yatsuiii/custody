"""The gateway is second-line defence, so it is tested as if the first line failed.

Every case here assumes an untrusted memory somehow exists and asks whether the
export still leaves. If the split in service.py is working none of this should
ever fire in practice, which is exactly why it must be tested in isolation.
"""

from __future__ import annotations

import unittest

from custody.action import Denial, Export, ExportGateway
from custody.origin import CustodyRecord, Origin, Trust

EXTERNAL = "archive@external.example"


def record(trust: Trust, origin: Origin = Origin.TOOL, tool: str | None = "fetch_page"):
    return CustodyRecord(
        origin=origin,
        trust=trust,
        author="assistant",
        invocation_id="inv-1",
        content_sha256="d" * 64,
        source_tool=tool,
    )


class EgressRequiresATrustedAuthorization(unittest.TestCase):
    def test_an_export_citing_untrusted_content_is_refused(self):
        gateway = ExportGateway()
        decision = gateway.request(
            Export(EXTERNAL, "records", cited=(record(Trust.UNTRUSTED),))
        )
        self.assertFalse(decision.allowed)
        self.assertIs(decision.denial, Denial.UNTRUSTED_CITATION)
        self.assertEqual(gateway.sent, [])

    def test_an_export_citing_nothing_is_refused(self):
        """An unmotivated egress is what a laundered instruction looks like once
        the memory behind it has been forgotten."""
        gateway = ExportGateway()
        decision = gateway.request(Export(EXTERNAL, "records"))
        self.assertFalse(decision.allowed)
        self.assertIs(decision.denial, Denial.UNCITED)

    def test_an_export_citing_only_trusted_content_is_allowed(self):
        gateway = ExportGateway()
        decision = gateway.request(
            Export(
                EXTERNAL,
                "records",
                cited=(record(Trust.TRUSTED, Origin.USER, tool=None),),
            )
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(len(gateway.sent), 1)

    def test_one_untrusted_citation_among_many_still_refuses(self):
        """Mixing a real authorization with a poisoned one must not launder it."""
        gateway = ExportGateway()
        decision = gateway.request(
            Export(
                EXTERNAL,
                "records",
                cited=(
                    record(Trust.TRUSTED, Origin.USER, tool=None),
                    record(Trust.UNTRUSTED),
                ),
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(len(decision.offending), 1)


class RefusalsExplainThemselves(unittest.TestCase):
    def test_a_refusal_names_the_source_it_objected_to(self):
        gateway = ExportGateway()
        decision = gateway.request(
            Export(EXTERNAL, "records", cited=(record(Trust.UNTRUSTED, tool="scrape"),))
        )
        self.assertIn("scrape", decision.reason())

    def test_an_uncited_refusal_says_so_rather_than_naming_a_source(self):
        decision = ExportGateway().request(Export(EXTERNAL, "records"))
        self.assertIn("no remembered content", decision.reason())

    def test_allowed_decisions_are_retained_too(self):
        """A gateway that records only refusals cannot show it let the right
        things through."""
        gateway = ExportGateway()
        gateway.request(Export(EXTERNAL, "a", cited=(record(Trust.TRUSTED),)))
        gateway.request(Export(EXTERNAL, "b", cited=(record(Trust.UNTRUSTED),)))
        self.assertEqual(len(gateway.decisions), 2)
        self.assertEqual(len(gateway.denials()), 1)


if __name__ == "__main__":
    unittest.main()
