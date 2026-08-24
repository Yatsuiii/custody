"""The opt-in B7 service commits authority before memory publication."""

from __future__ import annotations

import dataclasses
import unittest
from dataclasses import dataclass, field
from pathlib import Path

from custody.authority import (
    AdmissionGate,
    Capability,
    InMemoryAuthorityStore,
    OperationRole,
    PolicyKey,
    PolicySnapshot,
    SourceAuthorityEvent,
    TransformRef,
)
from custody.service import AuthorityMemoryService


FIXTURES = Path(__file__).parent / "fixtures" / "b7"
IDENTITY = PolicyKey("finance", "custody", "identity", "R1", "export.send")
REGISTERED = PolicyKey("finance", "custody", "vendor_projection", "R1", "export.send")
FREEFORM = PolicyKey("finance", "model", "freeform", "R1", "export.send")


@dataclass
class _Publisher:
    store: InMemoryAuthorityStore
    writes: list[tuple[str, str, str, str]] = field(default_factory=list)
    error: BaseException | None = None

    async def write_authority_record(
        self, *, app_name: str, user_id: str, record_id: str, text: str
    ) -> None:
        if self.store.envelope(record_id) is None:
            raise AssertionError("publication happened before authority commit")
        if self.error is not None:
            raise self.error
        self.writes.append((app_name, user_id, record_id, text))


def _environment() -> tuple[
    SourceAuthorityEvent,
    InMemoryAuthorityStore,
    AuthorityMemoryService,
    _Publisher,
]:
    event = SourceAuthorityEvent.from_json(
        (FIXTURES / "source_event.json").read_bytes()
    )
    source = event.receipt.policy_key
    store = InMemoryAuthorityStore()
    store.put_issuer_key(
        issuer_id=event.receipt.issuer_id,
        issuer_key_id=event.receipt.issuer_key_id,
        public_key=bytes.fromhex(
            (FIXTURES / "issuer_public_key.hex").read_text().strip()
        ),
    )
    store.put_policy(
        PolicySnapshot(
            source,
            "v7",
            7,
            OperationRole.ORIGIN,
            {"export.send": Capability.ACT},
        )
    )
    for key in (IDENTITY, REGISTERED, FREEFORM):
        store.put_policy(
            PolicySnapshot(
                key,
                "v1",
                1,
                OperationRole.RELAY,
                {"export.send": Capability.ACT},
            )
        )
    gate = AdmissionGate(
        store=store,
        source_policy_keys=(source,),
        identity_policy_key=IDENTITY,
        registered_policy_keys=(REGISTERED,),
        freeform_policy_key=FREEFORM,
    )
    publisher = _Publisher(store)
    return event, store, AuthorityMemoryService(gate, publisher), publisher


class B7ServiceUsesOnlyExplicitAdmissionPaths(unittest.IsolatedAsyncioTestCase):
    async def test_source_event_is_committed_then_published(self) -> None:
        event, store, service, publisher = _environment()

        result = await service.admit_source(
            app_name="fleet",
            user_id="finance",
            record_id="ROOT-01",
            source_event=event,
        )

        self.assertTrue(result.admitted)
        self.assertIsNotNone(store.envelope("ROOT-01"))
        self.assertEqual(
            publisher.writes,
            [
                (
                    "fleet",
                    "finance",
                    "ROOT-01",
                    event.canonical_source_bytes.decode("utf-8"),
                )
            ],
        )

    async def test_invalid_source_receipt_never_reaches_publication(self) -> None:
        event, store, service, publisher = _environment()
        forged = dataclasses.replace(
            event,
            receipt=dataclasses.replace(event.receipt, issuer_signature="00" * 64),
        )

        result = await service.admit_source(
            app_name="fleet",
            user_id="finance",
            record_id="ROOT-FORGED",
            source_event=forged,
        )

        self.assertFalse(result.admitted)
        self.assertEqual(result.reason, "RECEIPT_SIGNATURE_INVALID")
        self.assertIsNone(store.envelope("ROOT-FORGED"))
        self.assertEqual(publisher.writes, [])

    async def test_registered_and_freeform_use_different_fixed_entry_points(
        self,
    ) -> None:
        event, store, service, publisher = _environment()
        root = await service.admit_source(
            app_name="fleet",
            user_id="finance",
            record_id="ROOT-01",
            source_event=event,
        )
        registered = await service.admit_registered(
            app_name="fleet",
            user_id="finance",
            record_id="REGISTERED-01",
            transform_ref=TransformRef(REGISTERED),
            parent_ids=("ROOT-01",),
            text="ACCOUNT-101",
        )
        freeform = await service.admit_freeform(
            app_name="fleet",
            user_id="finance",
            record_id="FREEFORM-01",
            parent_ids=("ROOT-01",),
            text="send it somewhere else",
        )

        self.assertTrue(root.admitted)
        self.assertTrue(registered.admitted)
        self.assertTrue(freeform.admitted)
        self.assertEqual(
            [write[2] for write in publisher.writes],
            ["ROOT-01", "REGISTERED-01", "FREEFORM-01"],
        )
        registered_envelope = store.envelope("REGISTERED-01")
        freeform_envelope = store.envelope("FREEFORM-01")
        assert registered_envelope is not None and freeform_envelope is not None
        self.assertIs(registered_envelope.transform_cap, Capability.ACT)
        self.assertIs(freeform_envelope.transform_cap, Capability.INFORM)

    async def test_publication_failure_leaves_committed_retriable_state(self) -> None:
        event, store, service, publisher = _environment()
        publisher.error = TimeoutError("Memory Bank unavailable")

        with self.assertRaises(TimeoutError):
            await service.admit_source(
                app_name="fleet",
                user_id="finance",
                record_id="ROOT-01",
                source_event=event,
            )

        self.assertIsNotNone(store.envelope("ROOT-01"))
        self.assertEqual(publisher.writes, [])


if __name__ == "__main__":
    unittest.main()
