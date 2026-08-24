"""Offline tests for the Firestore probe's terminal-evidence contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.firestore_contract_probe import _run_step
from scripts.run_firestore_contract_probe import (
    _load_child_result,
    _terminal_failure,
    _write_json_atomic,
)


class FirestoreProbeHarnessTests(unittest.TestCase):
    def test_atomic_artifact_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            _write_json_atomic(path, {"status": "PASS", "operations": []})
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                '{\n  "operations": [],\n  "status": "PASS"\n}\n',
            )

    def test_missing_child_artifact_is_harness_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child_result, error = _load_child_result(Path(directory) / "missing.json")
            self.assertIsNone(child_result)
            self.assertEqual(error, "child result artifact is missing")

    def test_nonterminal_child_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "child.json"
            _write_json_atomic(path, {"status": "START"})
            child_result, error = _load_child_result(path)
            self.assertIsNone(child_result)
            self.assertIn("no terminal status", error or "")

    def test_process_failure_is_explicit_and_non_security(self) -> None:
        result = _terminal_failure(
            start={"status": "START"},
            output=Path("result.json"),
            child_output=Path("child.json"),
            reason="child process disappeared",
            process={"returncode": -9},
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["classification"], "PROBE-HARNESS-FAIL")
        self.assertFalse(result["security_metrics"])

    def test_operation_failure_preserves_operation_and_exception_chain(self) -> None:
        operations: list[dict[str, object]] = []
        with self.assertRaisesRegex(RuntimeError, "sdk failure"):
            _run_step(
                operations,
                "transactional_read",
                "Transaction.get -> iterator",
                lambda: (_ for _ in ()).throw(RuntimeError("sdk failure")),
            )
        self.assertEqual(operations[0]["name"], "transactional_read")
        self.assertFalse(operations[0]["ok"])
        self.assertEqual(
            operations[0]["exception"]["type"],  # type: ignore[index]
            "RuntimeError",
        )


if __name__ == "__main__":
    unittest.main()
