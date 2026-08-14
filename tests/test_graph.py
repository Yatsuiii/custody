"""G3: a tool trusted on day one, demoted on day N, and everything it touched
pulled regardless of hop count or which department wrote it.

Records are built directly rather than through `take_custody`, because the
graph module must not care how `derived_from` was populated. Origin labelling
supplies hop one for real, from actual events (see `test_origin.py`); these
tests supply further hops synthetically to prove the traversal itself is
correct, across departments, before anything wires cross-session retrieval
into `derived_from`.
"""

from __future__ import annotations

import unittest

from custody.graph import CustodyGraph
from custody.origin import CustodyRecord, Origin, ToolTrust, Trust, digest, take_custody
from custody.revision import RevisionAlgorithmMismatch
from tests.test_origin import FakeContent, FakeEvent, FakePart, FakeResponse


def record(
    record_id: str,
    *,
    source_tool: str | None = None,
    source_revision: str | None = None,
    derived_from: tuple[str, ...] = (),
    trust: Trust = Trust.TRUSTED,
    origin: Origin = Origin.MODEL,
    author: str = "assistant",
    content: str | None = None,
) -> CustodyRecord:
    return CustodyRecord(
        origin=origin,
        trust=trust,
        author=author,
        invocation_id=f"inv-{record_id}",
        content_sha256=digest(content) if content is not None else "x" * 64,
        source_tool=source_tool,
        source_revision=source_revision,
        id=record_id,
        derived_from=derived_from,
    )


class RevocationWalksTheDerivationGraph(unittest.TestCase):
    def test_the_direct_culprit_is_removed(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        revocation = graph.revoke(tool="evil_tool", revocation_id="rev-1")
        self.assertEqual(revocation.removed, ("a",))
        self.assertEqual(len(graph), 0)

    def test_a_restatement_two_hops_downstream_is_removed(self):
        """Department A's tool response, restated in department A, cited in B."""
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.add(record("b", derived_from=("a",), trust=Trust.UNTRUSTED))
        graph.add(record("c", derived_from=("b",), trust=Trust.UNTRUSTED))
        revocation = graph.revoke(tool="evil_tool", revocation_id="rev-1")
        self.assertEqual(set(revocation.removed), {"a", "b", "c"})
        self.assertEqual(len(graph), 0)

    def test_records_descended_from_a_different_tool_survive(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.add(record("b", derived_from=("a",), trust=Trust.UNTRUSTED))
        graph.add(record("clean", source_tool="payroll_lookup"))
        graph.revoke(tool="evil_tool", revocation_id="rev-1")
        self.assertEqual([r.id for r in graph.records()], ["clean"])

    def test_a_record_with_two_parents_survives_unless_both_are_pulled(self):
        """A restatement citing both a poisoned and a clean record is still tainted."""
        graph = CustodyGraph()
        graph.add(record("evil", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.add(record("clean", source_tool="payroll_lookup"))
        graph.add(record("mixed", derived_from=("evil", "clean")))
        graph.revoke(tool="evil_tool", revocation_id="rev-1")
        self.assertEqual([r.id for r in graph.records()], ["clean"])


class RevocationIsIdempotent(unittest.TestCase):
    def test_replaying_the_same_revocation_id_removes_nothing_further(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.add(record("b", derived_from=("a",), trust=Trust.UNTRUSTED))
        first = graph.revoke(tool="evil_tool", revocation_id="rev-1")
        second = graph.revoke(tool="evil_tool", revocation_id="rev-1")
        self.assertEqual(first, second)
        self.assertEqual(len(graph), 0)

    def test_replaying_produces_no_duplicate_audit_record(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.revoke(tool="evil_tool", revocation_id="rev-1")
        graph.revoke(tool="evil_tool", revocation_id="rev-1")
        self.assertEqual(len(graph.revocations()), 1)

    def test_a_later_revocation_of_a_different_tool_is_a_separate_record(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.add(record("b", source_tool="other_tool", trust=Trust.UNTRUSTED))
        graph.revoke(tool="evil_tool", revocation_id="rev-1")
        graph.revoke(tool="other_tool", revocation_id="rev-2")
        self.assertEqual(len(graph.revocations()), 2)
        self.assertEqual(len(graph), 0)


class DescendantsCanBePreviewedWithoutRemoving(unittest.TestCase):
    def test_descendants_does_not_mutate_the_graph(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="evil_tool", trust=Trust.UNTRUSTED))
        graph.add(record("b", derived_from=("a",), trust=Trust.UNTRUSTED))
        preview = graph.descendants("evil_tool")
        self.assertEqual(set(preview), {"a", "b"})
        self.assertEqual(len(graph), 2)


class RevisionRevocationIsPrecise(unittest.TestCase):
    def test_one_tool_revision_removes_only_its_descendants(self):
        graph = CustodyGraph()
        tool = "vendor-knowledge/fetch_page"
        graph.add(record("old-root", source_tool=tool, source_revision="old"))
        graph.add(record("sales", derived_from=("old-root",)))
        graph.add(record("support", derived_from=("sales",)))
        graph.add(record("finance", derived_from=("support",)))
        graph.add(record("new-root", source_tool=tool, source_revision="new"))
        graph.add(record("unrelated", source_tool="crm/lookup", source_revision="x"))

        revocation = graph.revoke_revision(
            tool=tool, revision="old", revocation_id="revision-rev-1"
        )

        self.assertEqual(
            set(revocation.removed), {"old-root", "sales", "support", "finance"}
        )
        self.assertEqual(revocation.revision, "old")
        self.assertEqual(
            {record.id for record in graph.records()}, {"new-root", "unrelated"}
        )


class RevisionRevocationFailsLoudAcrossAnAlgorithmBoundary(unittest.TestCase):
    """The fail-open bug: a canonicalization change makes every stored
    `source_revision` an unrecognized string. Silently finding no roots for
    it looks identical to "this revision has no descendants" and lets a
    revision-specific revocation report success while removing nothing."""

    def test_asking_under_an_older_algorithm_than_what_is_stored_raises(self):
        graph = CustodyGraph()
        tool = "vendor-knowledge/fetch_page"
        graph.add(record("root", source_tool=tool, source_revision="sha256/2:abc"))

        with self.assertRaises(RevisionAlgorithmMismatch):
            graph.revoke_revision(
                tool=tool, revision="bare-legacy-hex", revocation_id="rev-1"
            )
        self.assertEqual(len(graph), 1)

    def test_a_genuinely_empty_revision_under_the_matching_algorithm_does_not_raise(self):
        graph = CustodyGraph()
        tool = "vendor-knowledge/fetch_page"
        graph.add(record("root", source_tool=tool, source_revision="sha256/2:abc"))

        revocation = graph.revoke_revision(
            tool=tool, revision="sha256/2:never-admitted", revocation_id="rev-1"
        )
        self.assertEqual(revocation.removed, ())
        self.assertEqual(len(graph), 1)

    def test_no_records_for_the_tool_at_all_does_not_raise(self):
        graph = CustodyGraph()
        graph.add(record("unrelated", source_tool="crm/lookup", source_revision="x"))

        revocation = graph.revoke_revision(
            tool="vendor-knowledge/fetch_page",
            revision="sha256/2:abc",
            revocation_id="rev-1",
        )
        self.assertEqual(revocation.removed, ())
        self.assertEqual(len(graph), 1)


class ResolveFindsARecordByItsContent(unittest.TestCase):
    def test_a_matching_digest_returns_the_record(self):
        graph = CustodyGraph()
        r = record("a", source_tool="crm_lookup")
        graph.add(r)
        self.assertEqual(graph.resolve(r.content_sha256), r)

    def test_no_match_returns_none(self):
        graph = CustodyGraph()
        graph.add(record("a", source_tool="crm_lookup"))
        self.assertIsNone(graph.resolve("z" * 64))


def retrieval(text: str, invocation: str = "inv-2") -> FakeEvent:
    """A `load_memory` call, returning one piece of text."""
    part = FakePart(function_response=FakeResponse(name="load_memory", response=text))
    return FakeEvent("assistant", invocation, FakeContent([part]))


def restatement(text: str, invocation: str = "inv-2") -> FakeEvent:
    return FakeEvent("assistant", invocation, FakeContent([FakePart(text=text)]))


class RetrievalIsAttributedAsACitation(unittest.TestCase):
    """The mechanism `derived_from` needs to reach across a session boundary:
    a `load_memory` response is not new content, it is a citation of
    something this graph already governed."""

    def test_a_retrieval_matching_the_graph_inherits_its_lineage(self):
        graph = CustodyGraph()
        trust = ToolTrust(trusted=frozenset({"crm_lookup"}))

        # Day one, department A: a trusted lookup, written and added to the graph.
        written = take_custody(
            [FakeEvent(
                "assistant",
                "inv-1",
                FakeContent([FakePart(
                    function_response=FakeResponse("crm_lookup", "balance: 500")
                )]),
            )],
            trust,
        )
        (looked_up,) = written.admitted
        graph.add(looked_up.record)

        # Day three, department B: an unrelated invocation retrieves the exact
        # same text via load_memory. Without a resolver, take_custody cannot
        # know this is old content: load_memory is unvouched, so it starts
        # untrusted.
        unresolved = take_custody([retrieval("balance: 500")])
        (before,) = unresolved.admitted
        self.assertIs(before.record.trust, Trust.UNTRUSTED)
        self.assertEqual(before.record.derived_from, ())

        resolved = take_custody([retrieval("balance: 500")], resolver=graph)
        (after,) = resolved.admitted
        self.assertIs(after.record.trust, Trust.TRUSTED)
        self.assertEqual(after.record.derived_from, (looked_up.record.id,))

    def test_a_restatement_of_the_retrieval_chains_to_it_not_the_original(self):
        graph = CustodyGraph()
        graph.add(record("original", source_tool="crm_lookup", content="balance: 500"))

        custody = take_custody(
            [retrieval("balance: 500"), restatement("Balance is 500.")],
            resolver=graph,
        )
        (loaded, restated) = custody.admitted

        self.assertEqual(loaded.record.derived_from, ("original",))
        # The restatement is one hop from the retrieval, which is itself one
        # hop from the original: two hops on the graph, not a shortcut.
        self.assertEqual(restated.record.derived_from, (loaded.record.id,))

    def test_an_unresolved_retrieval_stays_untrusted(self):
        """Content that matches nothing in the graph proves nothing about
        where it came from, so it is left exactly as take_custody decided:
        untrusted by default, not laundered into trust by the attempt."""
        graph = CustodyGraph()
        graph.add(record("unrelated", source_tool="payroll_lookup"))
        custody = take_custody([retrieval("never written before")], resolver=graph)
        (result,) = custody.admitted
        self.assertIs(result.record.trust, Trust.UNTRUSTED)
        self.assertEqual(result.record.derived_from, ())


if __name__ == "__main__":
    unittest.main()
