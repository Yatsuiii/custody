"""P0 contract tests for B7's production wire values.

These tests pin representation only.  They do not sign a receipt, verify a
receipt, calculate an action verdict, or import a research runner.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import unittest
from pathlib import Path

import custody.authority as authority
from custody.authority import (
    AdmissionEnvelope,
    AdmissionState,
    AuthorityDataError,
    AuthorityDependency,
    AuthorityReceipt,
    AuthorityVerifier,
    Capability,
    DependencyKind,
    FORBIDDEN_RUNTIME_FIELDS,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    ReceiptRootKey,
    SourceAuthorityEvent,
    TransformClass,
    VerificationReason,
    canonical_json_bytes,
)


FIXTURES = Path(__file__).parent / "fixtures" / "b7"

POLICY_KEY = PolicyKey("finance", "vendor_lookup", "lookup", "R1", "export.send")
SOURCE_OBJECT = {
    "record_id": "SRC-01",
    "department": "finance",
    "source": "vendor_lookup",
    "operation": "lookup",
    "revision": "R1",
    "action_scope": "export.send",
    "value": "ACCOUNT-101",
}
SOURCE_OBJECT_COMMITMENT = (
    "5c42e62a02ef680d3720485d48bb85f988d13b29eac63db317e38c8161a45809"
)
ROOT_KEY_DIGEST = "196faabe589dddfdb535e4c50c2ff674ea189bfb120ead72cd4657e79a0d6df5"
_DEFAULT_PUBLIC_KEY = object()
PAYLOAD_DIGEST = "08dc153fd61e0d59c844b8b48c54455e1a8b6076b71845a86f229ce5fe08d95c"


def receipt_mapping() -> dict[str, object]:
    return {
        "receipt_version": "1",
        "receipt_id": "receipt-001",
        "issuer_id": "vendor-source-authority",
        "issuer_key_id": "issuer-ed25519-v1",
        "policy_key": POLICY_KEY.as_list(),
        "granting_generation": 7,
        "granted_cap": "ACT",
        "action_scope": "export.send",
        "source_revision": "R1",
        "upstream_record_id": "SRC-01",
        "upstream_object_commitment": SOURCE_OBJECT_COMMITMENT,
        "issuer_signature": "00" * 64,
    }


def receipt() -> AuthorityReceipt:
    return AuthorityReceipt.from_mapping(receipt_mapping())


def root_envelope_mapping() -> dict[str, object]:
    return {
        "schema_version": "b7/p2-v1",
        "record_id": "ROOT-01",
        "payload_digest": PAYLOAD_DIGEST,
        "admission_state": "COMMITTED",
        "transform_class": "ROOT",
        "direct_parent_ids": [],
        "support_root_ids": ["ROOT-01"],
        "support_root_key_digests": [ROOT_KEY_DIGEST],
        "own_policy_key": POLICY_KEY.as_list(),
        "own_policy_version": "v7",
        "own_granting_generation": 7,
        "bound_cap": "ACT",
        "transform_cap": "ACT",
        "authority_receipt": receipt_mapping(),
        "source_object_claim": dict(SOURCE_OBJECT),
        "admitted_at": "2026-08-24T12:00:00Z",
        "supersedes_record_id": None,
    }


def signed_event() -> SourceAuthorityEvent:
    return SourceAuthorityEvent.from_json((FIXTURES / "source_event.json").read_bytes())


def signed_event_mapping() -> dict[str, object]:
    return json.loads((FIXTURES / "source_event.json").read_text())


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value))
    return set()


class _FixtureTrustStore:
    def __init__(self, public_key: bytes | None = None) -> None:
        self.public_key = public_key

    def public_key_for(self, *, issuer_id: str, issuer_key_id: str) -> bytes | None:
        if (
            issuer_id == "vendor-source-authority"
            and issuer_key_id == "issuer-ed25519-v1"
        ):
            return self.public_key
        return None


class _FixtureAuthorityState:
    def __init__(self, snapshot: PolicySnapshot | None = None) -> None:
        self.snapshot = snapshot
        self.receipt_roots: dict[str, str] = {}

    def policy(self, key: PolicyKey) -> PolicySnapshot | None:
        if self.snapshot is not None and self.snapshot.policy_key == key:
            return self.snapshot
        return None

    def envelope(self, record_id: str):
        del record_id
        return None

    def dependencies(self, record_id: str):
        del record_id
        return ()

    def is_root_revoked(self, root_key_digest: str) -> bool:
        del root_key_digest
        return False

    def root_record_id_for_receipt(self, receipt: AuthorityReceipt) -> str | None:
        return self.receipt_roots.get(receipt.binding_digest)


def fixture_policy(**changes: object) -> PolicySnapshot:
    value = json.loads((FIXTURES / "policy_snapshot.json").read_text())
    value.update(changes)
    return PolicySnapshot.from_mapping(value)


def fixture_verifier(
    *,
    state: _FixtureAuthorityState | None = None,
    public_key: bytes | None | object = _DEFAULT_PUBLIC_KEY,
) -> tuple[AuthorityVerifier, _FixtureAuthorityState]:
    if public_key is _DEFAULT_PUBLIC_KEY:
        public_key = bytes.fromhex(
            (FIXTURES / "issuer_public_key.hex").read_text().strip()
        )
    assert public_key is None or isinstance(public_key, bytes)
    state = state or _FixtureAuthorityState(fixture_policy())
    return (
        AuthorityVerifier(
            trust_store=_FixtureTrustStore(public_key),
            state=state,
        ),
        state,
    )


class ClosedValuesStayClosed(unittest.TestCase):
    def test_capability_meet_is_the_all_required_input_bound(self) -> None:
        self.assertIs(
            Capability.meet((Capability.ACT, Capability.INFORM, Capability.ACT)),
            Capability.INFORM,
        )
        self.assertIs(
            Capability.meet((Capability.ACT, Capability.NONE)), Capability.NONE
        )

    def test_empty_or_untyped_capability_meets_are_rejected(self) -> None:
        with self.assertRaises(AuthorityDataError):
            Capability.meet(())
        with self.assertRaises(AuthorityDataError):
            Capability.meet((Capability.ACT, "INFORM"))  # type: ignore[arg-type]

    def test_unknown_caps_transforms_roles_and_states_are_rejected(self) -> None:
        for enum_type, value in (
            (Capability, "EXECUTE"),
            (TransformClass, "PARAPHRASE"),
            (OperationRole, "TRUSTED_RELAY"),
            (AdmissionState, "ACTIVE"),
            (DependencyKind, "AUTHORITY"),
        ):
            with self.subTest(enum_type=enum_type.__name__):
                with self.assertRaises(ValueError):
                    enum_type(value)


class PolicyValuesAreStable(unittest.TestCase):
    def test_policy_key_has_the_frozen_five_element_representation(self) -> None:
        self.assertEqual(
            POLICY_KEY.canonical_bytes(),
            b'["finance","vendor_lookup","lookup","R1","export.send"]\n',
        )
        self.assertEqual(
            POLICY_KEY.digest,
            "81913b1cdfcadb31df8461aab1823900fc05efb05400e9ffcdb876cc3360cf43",
        )

    def test_policy_key_parser_requires_a_json_array_of_five_strings(self) -> None:
        for malformed in (
            tuple(POLICY_KEY.as_list()),
            POLICY_KEY.as_list()[:-1],
            ["finance", "vendor", "lookup", "R1", 7],
        ):
            with self.subTest(malformed=malformed):
                with self.assertRaises(AuthorityDataError):
                    PolicyKey.from_value(malformed)

    def test_policy_snapshot_copies_and_freezes_its_cap_map(self) -> None:
        caps = {"export.send": Capability.ACT}
        snapshot = PolicySnapshot(
            policy_key=POLICY_KEY,
            version="v7",
            generation=7,
            operation_role=OperationRole.ORIGIN,
            caps=caps,
        )
        caps["export.send"] = Capability.NONE

        self.assertIs(snapshot.caps["export.send"], Capability.ACT)
        with self.assertRaises(TypeError):
            snapshot.caps["other"] = Capability.ACT  # type: ignore[index]

    def test_policy_snapshot_parser_rejects_unknown_fields_and_caps(self) -> None:
        value = {
            "policy_key": POLICY_KEY.as_list(),
            "version": "v7",
            "generation": 7,
            "operation_role": "ORIGIN",
            "caps": {"export.send": "ACT"},
        }
        self.assertEqual(PolicySnapshot.from_mapping(value).as_dict(), value)

        with self.assertRaises(AuthorityDataError):
            PolicySnapshot.from_mapping({**value, "expected_allow": True})
        with self.assertRaises(AuthorityDataError):
            PolicySnapshot.from_mapping({**value, "caps": {"export.send": "ADMIN"}})


class ReceiptSchemaIsFrozen(unittest.TestCase):
    def test_dataclass_fields_are_exactly_gate_1b_r3(self) -> None:
        self.assertEqual(
            {field.name for field in dataclasses.fields(AuthorityReceipt)},
            {
                "receipt_version",
                "receipt_id",
                "issuer_id",
                "issuer_key_id",
                "policy_key",
                "granting_generation",
                "granted_cap",
                "action_scope",
                "source_revision",
                "upstream_record_id",
                "upstream_object_commitment",
                "issuer_signature",
            },
        )
        self.assertEqual(
            set(AuthorityReceipt.__dataclass_fields__),
            {field.name for field in dataclasses.fields(AuthorityReceipt)},
        )

    def test_unsigned_receipt_bytes_are_the_frozen_p2_fixture(self) -> None:
        expected = (
            b'{"action_scope":"export.send","granted_cap":"ACT",'
            b'"granting_generation":7,"issuer_id":"vendor-source-authority",'
            b'"issuer_key_id":"issuer-ed25519-v1","policy_key":'
            b'["finance","vendor_lookup","lookup","R1","export.send"],'
            b'"receipt_id":"receipt-001","receipt_version":"1",'
            b'"source_revision":"R1","upstream_object_commitment":'
            b'"5c42e62a02ef680d3720485d48bb85f988d13b29eac63db317e38c8161a45809",'
            b'"upstream_record_id":"SRC-01"}\n'
        )
        parsed = receipt()

        self.assertEqual(parsed.canonical_bytes(), expected)
        self.assertEqual(
            hashlib.sha256(parsed.canonical_bytes()).hexdigest(),
            "e4136369073c3fac08dbb5ca4f6aaa4a49f42ce45eea5f03628f8207b551ba11",
        )

    def test_mapping_order_does_not_change_receipt_bytes(self) -> None:
        reversed_mapping = dict(reversed(tuple(receipt_mapping().items())))
        self.assertEqual(
            AuthorityReceipt.from_mapping(reversed_mapping).canonical_bytes(),
            receipt().canonical_bytes(),
        )

    def test_receipt_round_trips_through_strict_json(self) -> None:
        original = receipt()
        payload = canonical_json_bytes(original.as_dict())
        self.assertEqual(AuthorityReceipt.from_json(payload), original)

    def test_unknown_and_missing_receipt_fields_are_rejected(self) -> None:
        unknown = {**receipt_mapping(), "ground_truth": "benign"}
        missing = receipt_mapping()
        missing.pop("issuer_key_id")

        for malformed in (unknown, missing):
            with self.subTest(fields=sorted(malformed)):
                with self.assertRaises(AuthorityDataError):
                    AuthorityReceipt.from_mapping(malformed)

    def test_unknown_versions_caps_and_malformed_scalar_types_are_rejected(
        self,
    ) -> None:
        mutations = (
            {"receipt_version": "2"},
            {"granted_cap": "ADMIN"},
            {"granting_generation": True},
            {"granting_generation": -1},
            {"policy_key": tuple(POLICY_KEY.as_list())},
            {"upstream_object_commitment": SOURCE_OBJECT_COMMITMENT.upper()},
            {"issuer_signature": "00" * 63},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                with self.assertRaises(AuthorityDataError):
                    AuthorityReceipt.from_mapping({**receipt_mapping(), **mutation})

    def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected(self) -> None:
        with self.assertRaises(AuthorityDataError):
            AuthorityReceipt.from_json('{"receipt_version":"1","receipt_version":"1"}')
        with self.assertRaises(AuthorityDataError):
            canonical_json_bytes({"generation": float("nan")})


class ReceiptRootIdentityIsExact(unittest.TestCase):
    def test_root_key_is_the_exact_gate_1c_r3_tuple(self) -> None:
        key = ReceiptRootKey.from_receipt(receipt(), custody_root_record_id="ROOT-01")
        self.assertEqual(
            key.as_list(),
            [
                "vendor-source-authority",
                "receipt-001",
                "SRC-01",
                SOURCE_OBJECT_COMMITMENT,
                POLICY_KEY.as_list(),
                7,
                "ROOT-01",
            ],
        )
        self.assertEqual(key.digest, ROOT_KEY_DIGEST)
        self.assertEqual(ReceiptRootKey.from_value(key.as_list()), key)

    def test_every_identity_field_mutation_changes_the_root_key(self) -> None:
        base = ReceiptRootKey.from_receipt(receipt(), custody_root_record_id="ROOT-01")
        mutations = (
            dataclasses.replace(base, issuer_id="other-issuer"),
            dataclasses.replace(base, receipt_id="receipt-002"),
            dataclasses.replace(base, upstream_record_id="SRC-02"),
            dataclasses.replace(base, upstream_object_commitment="1" * 64),
            dataclasses.replace(
                base,
                policy_key=dataclasses.replace(POLICY_KEY, action_scope="payroll.read"),
            ),
            dataclasses.replace(base, granting_generation=8),
            dataclasses.replace(base, custody_root_record_id="ROOT-02"),
        )

        self.assertEqual(len({base.digest, *(item.digest for item in mutations)}), 8)

    def test_payload_metadata_does_not_change_root_identity(self) -> None:
        envelope = AdmissionEnvelope.from_mapping(root_envelope_mapping())
        changed_payload = dataclasses.replace(envelope, payload_digest="f" * 64)

        before = ReceiptRootKey.from_receipt(
            envelope.authority_receipt, custody_root_record_id=envelope.record_id
        )
        after = ReceiptRootKey.from_receipt(
            changed_payload.authority_receipt,
            custody_root_record_id=changed_payload.record_id,
        )
        self.assertEqual(before, after)


class SourceEventsExcludeScorerTruth(unittest.TestCase):
    def test_source_object_canonicalization_and_commitment_are_pinned(self) -> None:
        event = SourceAuthorityEvent(SOURCE_OBJECT, receipt())
        self.assertEqual(
            event.canonical_source_bytes,
            (
                b'{"action_scope":"export.send","department":"finance",'
                b'"operation":"lookup","record_id":"SRC-01",'
                b'"revision":"R1","source":"vendor_lookup",'
                b'"value":"ACCOUNT-101"}\n'
            ),
        )
        self.assertEqual(event.source_object_commitment, SOURCE_OBJECT_COMMITMENT)

    def test_source_object_is_deeply_copied_and_immutable(self) -> None:
        source = {"record_id": "SRC-01", "nested": {"items": [1, 2]}}
        event = SourceAuthorityEvent(source, receipt())
        source["nested"]["items"].append(3)  # type: ignore[index,union-attr]

        self.assertEqual(
            event.as_dict()["source_object"],
            {"nested": {"items": [1, 2]}, "record_id": "SRC-01"},
        )
        with self.assertRaises(TypeError):
            event.source_object["other"] = 1  # type: ignore[index]

    def test_every_frozen_scorer_field_is_rejected_at_any_depth(self) -> None:
        for field in FORBIDDEN_RUNTIME_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(AuthorityDataError):
                    SourceAuthorityEvent(
                        {"record_id": "SRC-01", "metadata": {field: True}},
                        receipt(),
                    )

    def test_equivalent_casing_and_punctuation_cannot_bypass_exclusion(self) -> None:
        for field in ("trueOrigin", "expected-action", "Scorer Truth"):
            with self.subTest(field=field):
                with self.assertRaises(AuthorityDataError):
                    SourceAuthorityEvent({field: True}, receipt())

    def test_event_parser_rejects_extra_runtime_context(self) -> None:
        with self.assertRaises(AuthorityDataError):
            SourceAuthorityEvent.from_mapping(
                {
                    "source_object": SOURCE_OBJECT,
                    "receipt": receipt_mapping(),
                    "expected_allow": True,
                }
            )

    def test_core_has_no_constructible_authority_producer(self) -> None:
        self.assertFalse(hasattr(authority, "AuthorityProducer"))
        self.assertNotIn("AuthorityProducer", authority.__all__)


class StaticSourceReceiptsVerifyAgainstCurrentState(unittest.TestCase):
    def test_fixture_is_pre_signed_label_free_and_byte_pinned(self) -> None:
        payload = (FIXTURES / "source_event.json").read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "b85b0895ceea636c13e41e9f1bba436f42a3a8e32e77b2c97dfe4b96dc92c99c",
        )
        self.assertTrue(
            FORBIDDEN_RUNTIME_FIELDS.isdisjoint(_nested_keys(json.loads(payload)))
        )

    def test_valid_source_owned_receipt_verifies(self) -> None:
        verifier, _ = fixture_verifier()

        result = verifier.verify(
            signed_event(),
            custody_root_record_id="ROOT-01",
            required_policy_key=POLICY_KEY,
        )

        self.assertTrue(result.verified)
        self.assertIs(result.reason, VerificationReason.VERIFIED)
        self.assertEqual(result.root_key_digest, ROOT_KEY_DIGEST)
        self.assertEqual(result.current_generation, 7)

    def test_forged_signature_is_rejected(self) -> None:
        value = signed_event_mapping()
        raw_receipt = value["receipt"]
        raw_receipt["issuer_signature"] = "00" * 64
        verifier, _ = fixture_verifier()

        result = verifier.verify(
            SourceAuthorityEvent.from_mapping(value),
            custody_root_record_id="ROOT-01",
            required_policy_key=POLICY_KEY,
        )

        self.assertFalse(result.verified)
        self.assertIs(result.reason, VerificationReason.SIGNATURE_INVALID)

    def test_wrong_object_and_record_bindings_are_rejected(self) -> None:
        object_changed = signed_event_mapping()
        object_changed["source_object"]["value"] = "ATTACKER-ACCOUNT"
        record_changed = signed_event_mapping()
        record_changed["source_object"]["record_id"] = "SRC-OTHER"
        verifier, _ = fixture_verifier()

        outcomes = (
            (
                SourceAuthorityEvent.from_mapping(object_changed),
                VerificationReason.OBJECT_COMMITMENT_MISMATCH,
            ),
            (
                SourceAuthorityEvent.from_mapping(record_changed),
                VerificationReason.UPSTREAM_RECORD_MISMATCH,
            ),
        )
        for event, reason in outcomes:
            with self.subTest(reason=reason.value):
                result = verifier.verify(
                    event,
                    custody_root_record_id="ROOT-01",
                    required_policy_key=POLICY_KEY,
                )
                self.assertFalse(result.verified)
                self.assertIs(result.reason, reason)

    def test_wrong_policy_scope_and_revision_bindings_are_rejected(self) -> None:
        wrong_policy = dataclasses.replace(POLICY_KEY, source="payroll_lookup")
        wrong_scope = signed_event_mapping()
        wrong_scope["receipt"]["action_scope"] = "payroll.read"
        wrong_revision = signed_event_mapping()
        wrong_revision["receipt"]["source_revision"] = "R2"
        verifier, _ = fixture_verifier()

        outcomes = (
            (
                signed_event(),
                wrong_policy,
                VerificationReason.POLICY_KEY_MISMATCH,
            ),
            (
                SourceAuthorityEvent.from_mapping(wrong_scope),
                POLICY_KEY,
                VerificationReason.SCOPE_MISMATCH,
            ),
            (
                SourceAuthorityEvent.from_mapping(wrong_revision),
                POLICY_KEY,
                VerificationReason.REVISION_MISMATCH,
            ),
        )
        for event, policy, reason in outcomes:
            with self.subTest(reason=reason.value):
                result = verifier.verify(
                    event,
                    custody_root_record_id="ROOT-01",
                    required_policy_key=policy,
                )
                self.assertFalse(result.verified)
                self.assertIs(result.reason, reason)

    def test_missing_or_malformed_trust_anchor_fails_closed(self) -> None:
        for key, reason in (
            (None, VerificationReason.MISSING_TRUST_ANCHOR),
            (b"too-short", VerificationReason.MALFORMED_TRUST_ANCHOR),
        ):
            with self.subTest(reason=reason.value):
                verifier, _ = fixture_verifier(public_key=key)
                result = verifier.verify(
                    signed_event(),
                    custody_root_record_id="ROOT-01",
                    required_policy_key=POLICY_KEY,
                )
                self.assertFalse(result.verified)
                self.assertIs(result.reason, reason)

    def test_missing_stale_relay_or_underpowered_policy_fails_closed(self) -> None:
        states = (
            (
                _FixtureAuthorityState(None),
                VerificationReason.MISSING_CURRENT_POLICY,
            ),
            (
                _FixtureAuthorityState(fixture_policy(generation=8)),
                VerificationReason.STALE_GENERATION,
            ),
            (
                _FixtureAuthorityState(fixture_policy(operation_role="RELAY")),
                VerificationReason.POLICY_ROLE_MISMATCH,
            ),
            (
                _FixtureAuthorityState(fixture_policy(caps={"other.scope": "ACT"})),
                VerificationReason.CAP_MISSING,
            ),
            (
                _FixtureAuthorityState(fixture_policy(caps={"export.send": "INFORM"})),
                VerificationReason.CAP_EXCEEDED,
            ),
        )
        for state, reason in states:
            with self.subTest(reason=reason.value):
                verifier, _ = fixture_verifier(state=state)
                result = verifier.verify(
                    signed_event(),
                    custody_root_record_id="ROOT-01",
                    required_policy_key=POLICY_KEY,
                )
                self.assertFalse(result.verified)
                self.assertIs(result.reason, reason)

    def test_receipt_cannot_be_rebound_to_an_unrelated_custody_root(self) -> None:
        state = _FixtureAuthorityState(fixture_policy())
        state.receipt_roots[signed_event().receipt.binding_digest] = "ROOT-01"
        verifier, _ = fixture_verifier(state=state)

        replay = verifier.verify(
            signed_event(),
            custody_root_record_id="ROOT-02",
            required_policy_key=POLICY_KEY,
        )

        self.assertFalse(replay.verified)
        self.assertIs(replay.reason, VerificationReason.ROOT_BINDING_MISMATCH)

    def test_source_claim_missing_a_binding_field_fails_closed(self) -> None:
        value = signed_event_mapping()
        value["source_object"].pop("operation")
        verifier, _ = fixture_verifier()

        result = verifier.verify(
            SourceAuthorityEvent.from_mapping(value),
            custody_root_record_id="ROOT-01",
            required_policy_key=POLICY_KEY,
        )

        self.assertFalse(result.verified)
        self.assertIs(result.reason, VerificationReason.SOURCE_CLAIM_MALFORMED)


class DependenciesAndEnvelopesAreStrict(unittest.TestCase):
    def test_source_dependency_round_trips_without_dropping_identity(self) -> None:
        value = {
            "record_id": "MEM-01",
            "kind": "SOURCE_AUTHORITY",
            "policy_key": POLICY_KEY.as_list(),
            "granting_generation": 7,
            "root_record_id": "ROOT-01",
            "root_key_digest": ROOT_KEY_DIGEST,
            "action_scope": "export.send",
            "receipt_id": "receipt-001",
        }
        dependency = AuthorityDependency.from_mapping(value)
        self.assertEqual(dependency.as_dict(), value)
        self.assertEqual(
            dependency,
            AuthorityDependency.from_mapping(json.loads(dependency.canonical_bytes())),
        )

    def test_transform_dependency_cannot_carry_receipt_root_identity(self) -> None:
        value = {
            "record_id": "MEM-01",
            "kind": "TRANSFORM_POLICY",
            "policy_key": POLICY_KEY.as_list(),
            "granting_generation": 7,
            "root_record_id": "MEM-01",
            "root_key_digest": ROOT_KEY_DIGEST,
            "action_scope": "export.send",
            "receipt_id": "receipt-001",
        }
        with self.assertRaises(AuthorityDataError):
            AuthorityDependency.from_mapping(value)

    def test_root_envelope_round_trips_and_has_a_pinned_canonical_digest(self) -> None:
        envelope = AdmissionEnvelope.from_mapping(root_envelope_mapping())
        reparsed = AdmissionEnvelope.from_json(envelope.canonical_bytes())

        self.assertEqual(reparsed, envelope)
        self.assertTrue(envelope.canonical_bytes().endswith(b"\n"))
        self.assertEqual(len(envelope.canonical_bytes()), 1340)
        self.assertEqual(
            hashlib.sha256(envelope.canonical_bytes()).hexdigest(),
            "e98894118202931fdff15c8eef85678864eea9a9aced07d8fa7179c4c5674444",
        )

    def test_envelope_parser_rejects_unknown_missing_and_unknown_enum_fields(
        self,
    ) -> None:
        unknown = {**root_envelope_mapping(), "expected_action": "ALLOW"}
        missing = root_envelope_mapping()
        missing.pop("support_root_ids")
        unknown_transform = {
            **root_envelope_mapping(),
            "transform_class": "PARAPHRASE",
        }

        for malformed in (unknown, missing, unknown_transform):
            with self.subTest(fields=sorted(malformed)):
                with self.assertRaises(AuthorityDataError):
                    AdmissionEnvelope.from_mapping(malformed)

    def test_root_support_must_match_the_exact_receipt_root(self) -> None:
        for mutation in (
            {"support_root_ids": ["ROOT-02"]},
            {"support_root_key_digests": ["f" * 64]},
            {"direct_parent_ids": ["PARENT-01"]},
            {"authority_receipt": None},
            {"source_object_claim": None},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(AuthorityDataError):
                    AdmissionEnvelope.from_mapping(
                        {**root_envelope_mapping(), **mutation}
                    )

    def test_transform_shapes_cannot_smuggle_fresh_root_authority(self) -> None:
        derived = {
            **root_envelope_mapping(),
            "record_id": "MEM-01",
            "transform_class": "IDENTITY",
            "direct_parent_ids": ["ROOT-01"],
            "authority_receipt": None,
            "source_object_claim": None,
        }
        self.assertEqual(
            AdmissionEnvelope.from_mapping(derived).transform_class,
            TransformClass.IDENTITY,
        )

        for mutation in (
            {"direct_parent_ids": []},
            {"direct_parent_ids": ["ROOT-01", "ROOT-02"]},
            {"authority_receipt": receipt_mapping()},
            {"source_object_claim": SOURCE_OBJECT},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(AuthorityDataError):
                    AdmissionEnvelope.from_mapping({**derived, **mutation})

    def test_registered_requires_a_parent_and_freeform_is_bounded_to_inform(
        self,
    ) -> None:
        base = {
            **root_envelope_mapping(),
            "record_id": "MEM-01",
            "authority_receipt": None,
            "source_object_claim": None,
        }
        with self.assertRaises(AuthorityDataError):
            AdmissionEnvelope.from_mapping(
                {**base, "transform_class": "REGISTERED", "direct_parent_ids": []}
            )
        with self.assertRaises(AuthorityDataError):
            AdmissionEnvelope.from_mapping(
                {**base, "transform_class": "FREEFORM", "transform_cap": "ACT"}
            )

        freeform = AdmissionEnvelope.from_mapping(
            {**base, "transform_class": "FREEFORM", "transform_cap": "INFORM"}
        )
        self.assertIs(freeform.transform_cap, Capability.INFORM)


if __name__ == "__main__":
    unittest.main()
