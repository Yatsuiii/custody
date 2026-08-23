"""Production P2 admission tests using only the static source fixture."""

from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

from custody.authority import (
    AdmissionGate,
    AuthorityDataError,
    AuthorityOutput,
    Capability,
    DependencyKind,
    InMemoryAuthorityStore,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    SourceAuthorityEvent,
    TransformClass,
    TransformRef,
)


FIXTURES = Path(__file__).parent / "fixtures" / "b7"
SOURCE_POLICY = PolicyKey(
    "finance", "vendor_lookup", "lookup", "R1", "export.send"
)
IDENTITY_POLICY = PolicyKey(
    "finance", "custody", "identity", "R1", "export.send"
)
REGISTERED_POLICY = PolicyKey(
    "finance", "custody", "vendor_projection", "R1", "export.send"
)
FREEFORM_POLICY = PolicyKey(
    "finance", "model", "freeform", "R1", "export.send"
)
UNCONFIGURED_POLICY = PolicyKey(
    "finance", "custody", "unreviewed_transform", "R1", "export.send"
)


def _policy(
    key: PolicyKey,
    *,
    generation: int = 1,
    role: OperationRole = OperationRole.RELAY,
    cap: Capability = Capability.ACT,
) -> PolicySnapshot:
    return PolicySnapshot(
        policy_key=key,
        version=f"v{generation}",
        generation=generation,
        operation_role=role,
        caps={key.action_scope: cap},
    )


class B7AdmissionFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.event = SourceAuthorityEvent.from_json(
            (FIXTURES / "source_event.json").read_bytes()
        )
        self.store = InMemoryAuthorityStore()
        self.store.put_issuer_key(
            issuer_id=self.event.receipt.issuer_id,
            issuer_key_id=self.event.receipt.issuer_key_id,
            public_key=bytes.fromhex(
                (FIXTURES / "issuer_public_key.hex").read_text().strip()
            ),
        )
        self.store.put_policy(
            _policy(
                SOURCE_POLICY,
                generation=7,
                role=OperationRole.ORIGIN,
            )
        )
        for key in (IDENTITY_POLICY, REGISTERED_POLICY, FREEFORM_POLICY):
            self.store.put_policy(_policy(key))
        self.gate = AdmissionGate(
            store=self.store,
            source_policy_keys=(SOURCE_POLICY,),
            identity_policy_key=IDENTITY_POLICY,
            registered_policy_keys=(REGISTERED_POLICY,),
            freeform_policy_key=FREEFORM_POLICY,
        )

    def admit_root(self, record_id: str = "ROOT-01"):
        return self.gate.admit_source(
            self.event,
            AuthorityOutput(
                record_id=record_id,
                payload_digest=self.event.source_object_commitment,
            ),
        )


class SourceAdmissionIsObjectBound(B7AdmissionFixture):
    def test_verified_event_commits_one_exact_receipt_root(self) -> None:
        result = self.admit_root()

        self.assertTrue(result.admitted)
        self.assertEqual(result.reason, "ADMITTED")
        assert result.envelope is not None
        self.assertIs(result.envelope.transform_class, TransformClass.ROOT)
        self.assertEqual(result.envelope.support_root_ids, ("ROOT-01",))
        dependencies = self.store.dependencies("ROOT-01")
        self.assertEqual(len(dependencies), 1)
        self.assertIs(dependencies[0].kind, DependencyKind.SOURCE_AUTHORITY)
        self.assertEqual(
            dependencies[0].root_key_digest,
            result.envelope.support_root_key_digests[0],
        )

    def test_exact_replay_is_idempotent_but_new_root_replay_is_denied(self) -> None:
        first = self.admit_root()
        replay = self.admit_root()
        rebound = self.admit_root("ROOT-OTHER")

        self.assertTrue(first.admitted)
        self.assertEqual(replay, first)
        self.assertFalse(rebound.admitted)
        self.assertEqual(rebound.reason, "UNRELATED_RECEIPT_REPLAY")
        self.assertIsNone(self.store.envelope("ROOT-OTHER"))

    def test_source_receipt_cannot_authorize_different_output_bytes(self) -> None:
        result = self.gate.admit_source(
            self.event,
            AuthorityOutput.from_text(record_id="ROOT-01", text="relay rewrite"),
        )

        self.assertFalse(result.admitted)
        self.assertEqual(result.reason, "OUTPUT_OBJECT_COMMITMENT_MISMATCH")
        self.assertEqual(self.store.records(), ())

    def test_source_event_and_transform_policies_are_disjoint(self) -> None:
        with self.assertRaises(AuthorityDataError):
            AdmissionGate(
                store=self.store,
                source_policy_keys=(SOURCE_POLICY,),
                identity_policy_key=IDENTITY_POLICY,
                registered_policy_keys=(FREEFORM_POLICY,),
                freeform_policy_key=FREEFORM_POLICY,
            )
        with self.assertRaises(AuthorityDataError):
            AdmissionGate(
                store=self.store,
                source_policy_keys=(SOURCE_POLICY,),
                identity_policy_key=SOURCE_POLICY,
                registered_policy_keys=(REGISTERED_POLICY,),
                freeform_policy_key=FREEFORM_POLICY,
            )


class DerivationPreservesAllRequiredSupport(B7AdmissionFixture):
    def setUp(self) -> None:
        super().setUp()
        root = self.admit_root()
        self.assertTrue(root.admitted)

    def test_identity_requires_exact_payload_and_forwards_support(self) -> None:
        output = AuthorityOutput(
            record_id="IDENTITY-01",
            payload_digest=self.event.source_object_commitment,
        )
        result = self.gate.admit_identity("ROOT-01", output)

        self.assertTrue(result.admitted)
        assert result.envelope is not None
        self.assertIs(result.envelope.transform_class, TransformClass.IDENTITY)
        self.assertEqual(result.envelope.direct_parent_ids, ("ROOT-01",))
        self.assertEqual(result.envelope.support_root_ids, ("ROOT-01",))
        self.assertEqual(
            self.store.dependencies("IDENTITY-01")[0].root_record_id,
            "ROOT-01",
        )

        changed = self.gate.admit_identity(
            "ROOT-01",
            AuthorityOutput.from_text(record_id="IDENTITY-BAD", text="changed"),
        )
        self.assertFalse(changed.admitted)
        self.assertEqual(changed.reason, "IDENTITY_PAYLOAD_MISMATCH")

    def test_registered_transform_keeps_every_parent_and_adds_policy(self) -> None:
        identity = self.gate.admit_identity(
            "ROOT-01",
            AuthorityOutput(
                record_id="IDENTITY-01",
                payload_digest=self.event.source_object_commitment,
            ),
        )
        self.assertTrue(identity.admitted)
        result = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("ROOT-01", "IDENTITY-01"),
            AuthorityOutput.from_text(
                record_id="REGISTERED-01", text="ACCOUNT-101"
            ),
        )

        self.assertTrue(result.admitted)
        assert result.envelope is not None
        self.assertEqual(
            result.envelope.direct_parent_ids, ("ROOT-01", "IDENTITY-01")
        )
        self.assertEqual(result.envelope.support_root_ids, ("ROOT-01",))
        dependencies = self.store.dependencies("REGISTERED-01")
        self.assertEqual(
            {dependency.kind for dependency in dependencies},
            {DependencyKind.SOURCE_AUTHORITY, DependencyKind.TRANSFORM_POLICY},
        )
        self.assertEqual(
            next(
                dependency
                for dependency in dependencies
                if dependency.kind is DependencyKind.TRANSFORM_POLICY
            ).policy_key,
            REGISTERED_POLICY,
        )

    def test_unconfigured_transform_cannot_select_registered_semantics(self) -> None:
        self.store.put_policy(_policy(UNCONFIGURED_POLICY))
        result = self.gate.admit_registered(
            TransformRef(UNCONFIGURED_POLICY),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="UNREVIEWED-01", text="rewrite"),
        )

        self.assertFalse(result.admitted)
        self.assertEqual(result.reason, "REGISTERED_TRANSFORM_NOT_CONFIGURED")
        self.assertIsNone(self.store.envelope("UNREVIEWED-01"))

    def test_freeform_retains_support_but_is_capped_at_inform(self) -> None:
        result = self.gate.admit_freeform(
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="FREEFORM-01", text="paraphrase"),
        )

        self.assertTrue(result.admitted)
        assert result.envelope is not None
        self.assertIs(result.envelope.transform_class, TransformClass.FREEFORM)
        self.assertIs(result.envelope.transform_cap, Capability.INFORM)
        self.assertEqual(result.envelope.support_root_ids, ("ROOT-01",))

    def test_missing_duplicate_and_conflicting_parent_inputs_fail_closed(self) -> None:
        missing = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("MISSING",),
            AuthorityOutput.from_text(record_id="MISSING-CHILD", text="value"),
        )
        duplicate = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("ROOT-01", "ROOT-01"),
            AuthorityOutput.from_text(record_id="DUPLICATE-CHILD", text="value"),
        )
        first = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="IMMUTABLE-01", text="first"),
        )
        conflict = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="IMMUTABLE-01", text="second"),
        )

        self.assertEqual(missing.reason, "MISSING_REQUIRED_PARENT")
        self.assertEqual(duplicate.reason, "DUPLICATE_REQUIRED_PARENT")
        self.assertTrue(first.admitted)
        self.assertFalse(conflict.admitted)
        self.assertEqual(conflict.reason, "ADMISSION_CONFLICT")

    def test_cross_agent_identity_forwarding_cannot_create_a_new_root(self) -> None:
        agent_a = self.gate.admit_identity(
            "ROOT-01",
            AuthorityOutput(
                record_id="AGENT-A",
                payload_digest=self.event.source_object_commitment,
            ),
        )
        agent_b = self.gate.admit_identity(
            "AGENT-A",
            AuthorityOutput(
                record_id="AGENT-B",
                payload_digest=self.event.source_object_commitment,
            ),
        )

        self.assertTrue(agent_a.admitted)
        self.assertTrue(agent_b.admitted)
        assert agent_b.envelope is not None
        self.assertIsNone(agent_b.envelope.authority_receipt)
        self.assertEqual(agent_b.envelope.support_root_ids, ("ROOT-01",))
        self.assertEqual(
            {
                dependency.root_record_id
                for dependency in self.store.dependencies("AGENT-B")
                if dependency.kind is DependencyKind.SOURCE_AUTHORITY
            },
            {"ROOT-01"},
        )

    def test_generation_change_during_record_id_reuse_never_rewrites_history(self) -> None:
        first = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="CHILD-01", text="first"),
        )
        before = self.store.envelope("CHILD-01")
        current = self.store.policy(REGISTERED_POLICY)
        assert current is not None
        self.store.put_policy(
            dataclasses.replace(current, version="v2", generation=2),
            expected_generation=1,
        )
        second = self.gate.admit_registered(
            TransformRef(REGISTERED_POLICY),
            ("ROOT-01",),
            AuthorityOutput.from_text(record_id="CHILD-01", text="second"),
        )

        self.assertTrue(first.admitted)
        self.assertFalse(second.admitted)
        self.assertEqual(self.store.envelope("CHILD-01"), before)


if __name__ == "__main__":
    unittest.main()
