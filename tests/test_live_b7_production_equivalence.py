"""Local checks for the P7 harness boundary and independent scorer."""

from __future__ import annotations

import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from live.b7_production_equivalence import (
    B7_COLLECTIONS,
    COLLECTION_PREFIX,
    EXPERIMENT_ID,
    MAIN_SOURCE,
    PRODUCTION_B7_SHA,
    _issue_event,
    _prefixed_collection,
)
from live.b7_production_equivalence_gates import score_trace


def _action(allowed: bool, reason: str | None = None) -> dict[str, object]:
    return {
        "allowed": allowed,
        "dispatched": allowed,
        "effective_cap": "ACT" if allowed else "NONE",
        "reason": reason or ("CURRENT_AUTHORITY_RECEIPT" if allowed else "DENIED"),
    }


def _process(role: str, pid: int, **api: str) -> dict[str, object]:
    return {
        "role": role,
        "pid": pid,
        "startup": {"result": api},
        "command_audits": [
            {
                "scorer_field_paths": [],
                "private_key_input_paths": [],
            }
        ],
    }


def _record(parent_ids: list[str], roots: set[str]) -> dict[str, object]:
    return {
        "present": True,
        "direct_parent_ids": parent_ids,
        "dependencies": [
            {"kind": "SOURCE_AUTHORITY", "root_record_id": root}
            for root in sorted(roots)
        ],
    }


def _passing_raw() -> dict[str, object]:
    before = {
        name: _action(True)
        for name in (
            "before_pre",
            "before_bad1",
            "before_bad2",
            "before_post",
            "before_other",
            "before_mix",
            "identity_legitimate",
            "registered_legitimate",
            "cross_agent_before",
        )
    }
    before.update(
        {
            name: _action(False)
            for name in (
                "freeform_laundering",
                "mixed_invalid_support",
                "forged_receipt",
                "wrong_object",
                "wrong_scope",
                "stale_generation",
                "unrelated_replay",
            )
        }
    )
    before["wrong_scope"] = _action(False, "ACTION_SCOPE_MISMATCH")
    before["stale_generation"] = _action(False, "POLICY_GENERATION_MISMATCH")
    after = {
        name: _action(False, "REVOKED_AUTHORITY_ROOT")
        for name in (
            "after_bad1",
            "after_bad2",
            "after_mix",
            "after_cross_agent",
        )
    }
    after.update(
        {name: _action(True) for name in ("after_pre", "after_post", "after_other")}
    )
    records = {
        "D_PRE": _record(["R_PRE"], {"R_PRE"}),
        "D_BAD1": _record(["R_BAD_1"], {"R_BAD_1"}),
        "D_MIX": _record(["R_BAD_1", "R_OTHER"], {"R_BAD_1", "R_OTHER"}),
        "AGENT_B_BAD_CHILD": _record(["AGENT_A_BAD_CHILD"], {"R_BAD_1"}),
        "D_OTHER": _record(["R_OTHER"], {"R_OTHER"}),
    }
    history = {record_id: f"digest-{record_id}" for record_id in records}

    def root_key(root_id: str) -> list[object]:
        return [
            "issuer",
            f"receipt-{root_id}",
            f"upstream-{root_id}",
            "0" * 64,
            MAIN_SOURCE.as_list(),
            1,
            root_id,
        ]

    return {
        "experiment_id": EXPERIMENT_ID,
        "run_id": "test-run",
        "production_b7_sha": PRODUCTION_B7_SHA,
        "runner_commit": "1" * 40,
        "source_producer": "TEST-OWNED",
        "preflight": {
            "database_class": "FIRESTORE_NATIVE",
            "namespace_prefix": COLLECTION_PREFIX,
            "initial_collection_counts": {name: 0 for name in B7_COLLECTIONS},
            "git": {
                "production_sha_is_ancestor": True,
                "production_file_commit_diff": [],
                "tracked_worktree_dirty": [],
                "production_hashes": {"custody/authority.py": "a"},
            },
        },
        "production_hashes_after_treatment": {"custody/authority.py": "a"},
        "runner_source_sha256_before_treatment": "b",
        "runner_source_sha256_after_treatment": "b",
        "gate_source_sha256_before_treatment": "c",
        "gate_source_sha256_after_treatment": "c",
        "processes": [
            _process("SOURCE", 101),
            _process("POLICY", 102, authoritative_store="FirestoreAuthorityStore"),
            _process("MEMORY", 103, admission_api="AdmissionGate"),
            _process("GATEWAY", 104, gateway_api="AuthorityGateway"),
        ],
        "source": {"issuer_private_key_exported": False, "events": {}},
        "before_actions": before,
        "after_actions": after,
        "admissions": {
            name: {"admitted": True}
            for name in (
                "R_PRE",
                "R_BAD_1",
                "R_BAD_2",
                "R_POST",
                "R_OTHER",
                "R_REPLAY",
                "R_STALE",
            )
        },
        "derivations": {
            name: {"admitted": True}
            for name in (
                "D_PRE",
                "D_BAD1",
                "D_BAD2",
                "D_POST",
                "D_OTHER",
                "D_MIX",
                "AGENT_A_BAD_CHILD",
                "AGENT_B_BAD_CHILD",
                "D_FREEFORM",
                "D_MIX_INVALID",
            )
        },
        "control_admissions": {
            "FORGED_ROOT": {"reason": "SIGNATURE_INVALID"},
            "WRONG_OBJECT_ROOT": {"reason": "OBJECT_COMMITMENT_MISMATCH"},
            "R_REPLAY_ALIAS": {"reason": "ROOT_BINDING_MISMATCH"},
        },
        "before_snapshot": {"records": records, "history": history},
        "after_snapshot": {"records": records, "history": history},
        "final_snapshot": {
            "records": {"R_CRASH": {"present": True}},
            "history": {**history, "R_CRASH": "digest-crash"},
        },
        "post_kill_probe": {
            "record": {"present": False},
            "receipt_bound_root": None,
        },
        "final_crash_probe": {
            "record": {"present": True},
            "receipt_bound_root": "R_CRASH",
        },
        "immediate_post_kill_action": _action(False),
        "recovery_action": _action(True),
        "recovery": {
            "response": {
                "ok": True,
                "result": {"R_CRASH": {"admitted": True}},
            },
            "elapsed_seconds": 1.0,
        },
        "race_prepared": {"prepared": True, "state_read": False},
        "race_action": _action(False),
        "revocation": {
            "revocation": {"root_keys": [root_key("R_BAD_1"), root_key("R_BAD_2")]},
            "affected_record_ids": [
                "R_BAD_1",
                "R_BAD_2",
                "D_BAD1",
                "D_BAD2",
                "D_MIX",
                "AGENT_A_BAD_CHILD",
                "AGENT_B_BAD_CHILD",
            ],
        },
        "namespace_manifest_before_cleanup": {
            "custody": [
                {"id": record_id, "data_sha256": "c"}
                for record_id in [*records, "R_CRASH"]
            ]
        },
        "ordering_events": [
            {"name": "STALE_GATEWAY_PREPARED_ACTION"},
            {"name": "SELECTIVE_REVOCATION_AUTHORITATIVE"},
            {"name": "STALE_GATEWAY_EXECUTED_AFTER_REVOCATION_COMMIT"},
        ],
        "runtime_seconds": 1.0,
        "raw_trace_frozen_before_scoring": True,
        "treatment_scorer_reads": 0,
        "scorer_leakage": False,
        "payload_semantic_authority_inspection": False,
    }


class SourceBoundaryTests(unittest.TestCase):
    def test_source_event_is_object_bound_and_signed_by_process_local_key(self) -> None:
        key = Ed25519PrivateKey.generate()
        event = _issue_event(key, event_id="event-001", policy_key=MAIN_SOURCE)

        key.public_key().verify(
            bytes.fromhex(event.receipt.issuer_signature),
            event.receipt.canonical_bytes(),
        )
        self.assertEqual(
            event.receipt.upstream_object_commitment,
            event.source_object_commitment,
        )
        self.assertNotIn("true_origin", event.source_object)
        self.assertNotIn("scorer_truth", event.source_object)

    def test_namespace_adapter_cannot_address_non_b7_collection(self) -> None:
        for collection in B7_COLLECTIONS:
            self.assertEqual(
                _prefixed_collection(collection),
                f"{COLLECTION_PREFIX}__{collection}",
            )
        with self.assertRaisesRegex(RuntimeError, "P7_COLLECTION_NOT_AUTHORIZED"):
            _prefixed_collection("production_customer_data")


class IndependentGateTests(unittest.TestCase):
    def test_passing_raw_trace_scores_live_equivalence(self) -> None:
        result = score_trace(
            _passing_raw(),
            raw_trace_digest="d" * 64,
            cleanup={"cleanup_complete": True},
            recomputation_match=True,
            score_digest="e" * 64,
            runner_source_path=(
                Path(__file__).parent.parent / "live" / "b7_production_equivalence.py"
            ),
        )

        self.assertEqual(result["verdict"], "PRODUCTION-B7-LIVE-EQUIVALENCE-SUPPORTED")
        self.assertTrue(result["validity"]["valid"])
        self.assertEqual(
            result["metrics"]["affected_revocation_false_act"]["numerator"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
